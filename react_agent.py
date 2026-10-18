"""The manual ReAct state machine. No prebuilt executor or ToolNode is used."""
from __future__ import annotations

import json
from typing import TypedDict
from langgraph.graph import END, START, StateGraph
from model import ModelError
from personas import PERSONAS, PromptOptions
from prompts import build_messages
from tools import ROOT, JsonLog, Tools, load_business


class AgentState(TypedDict):
    messages: list
    user_text: str
    steps: int
    pending: list
    observations: list
    events: list
    requests: list
    cache: dict
    answer: str
    error: str
    decision_summary: str


def normalize_history(history):
    result = []
    for m in (history or [])[-24:]:
        if not isinstance(m, dict) or m.get("role") not in {"user", "assistant"}:
            continue
        text = m.get("content", "")
        if isinstance(text, list):
            text = "\n".join(x.get("text", "") for x in text if isinstance(x, dict) and x.get("type") == "text")
        if isinstance(text, str) and text.strip():
            result.append({"role": m["role"], "content": text[:6000]})
    return result


def parse_final(message):
    """Accept a final answer only after explicit protocol and type checks."""
    if message.get("tool_calls"):
        raise ValueError("Tool calls must be observed before a final answer.")
    obj = json.loads(message.get("content") or "")
    if not isinstance(obj, dict) or set(obj) != {"answer", "decision_summary"}:
        raise ValueError("Final JSON requires answer and decision_summary.")
    if not all(isinstance(obj[k], str) and obj[k].strip() for k in obj):
        raise ValueError("Final fields must be nonempty strings.")
    if len(obj["decision_summary"]) > 800:
        raise ValueError("The public decision summary must be brief.")
    return obj


class ReActAgent:
    def __init__(self, model, *, persona="mira", generation=None, options=None,
                 root=ROOT, log_dir=None, max_steps=6):
        if persona not in PERSONAS or not 1 <= max_steps <= 12:
            raise ValueError("Unknown persona or invalid step limit.")
        self.model = model
        self.persona = persona
        self.generation = generation or PERSONAS[persona].generation
        self.options = options or PromptOptions()
        self.knowledge = load_business(root)
        self.tools = Tools(log_dir if log_dir is not None else ROOT / "logs")
        self.max_steps = max_steps
        self.graph = self.build_graph()

    def build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("model", self.model_node)
        graph.add_node("act", self.action_node)
        graph.add_node("observe", self.observation_node)
        graph.add_node("finalize", self.final_node)
        graph.add_node("repair", self.repair_node)
        graph.add_edge(START, "model")
        graph.add_conditional_edges("model", self.next_node,
                                    {"act": "act", "finalize": "finalize", "end": END})
        graph.add_edge("act", "observe")
        graph.add_edge("observe", "model")
        graph.add_conditional_edges("finalize", lambda s: "end" if s["answer"] or s["error"] else "repair",
                                    {"end": END, "repair": "repair"})
        graph.add_edge("repair", "model")
        return graph.compile()

    def model_node(self, state):
        if state["steps"] >= self.max_steps:
            return {"error": "The assistant reached its step limit before completing the response."}
        try:
            result = self.model.complete(state["messages"], self.generation)
            msg = result["message"]
            calls = msg.get("tool_calls", [])
            if not isinstance(calls, list) or len(calls) > 4:
                raise ModelError("The model returned an invalid number of tool calls.")
            ids = set()
            for call in calls:
                if (not isinstance(call, dict) or not isinstance(call.get("id"), str)
                        or call["id"] in ids or call.get("type") != "function"
                        or not call["id"] or not isinstance(call.get("function"), dict)
                        or not isinstance(call["function"].get("name"), str)
                        or not isinstance(call["function"].get("arguments"), str)):
                    raise ModelError("The model returned malformed tool calls.")
                ids.add(call["id"])
            return {"messages": [*state["messages"], msg], "pending": calls,
                    "error": ("Step limit reached; the last requested action was not executed."
                              if calls and state["steps"] + 1 >= self.max_steps else ""),
                    "steps": state["steps"] + 1, "requests": [*state["requests"], result]}
        except ModelError as exc:
            return {"error": str(exc)}

    def next_node(self, state):
        if state["error"]:
            return "end"
        # Keep one model call available to read observations after any action.
        return "act" if state["pending"] else "finalize"

    def action_node(self, state):
        observations, events, cache = [], list(state["events"]), dict(state["cache"])
        for call in state["pending"]:
            name = call["function"].get("name", "")
            arguments = call["function"].get("arguments", "")
            try:
                canonical = json.dumps(json.loads(arguments), sort_keys=True, separators=(",", ":"))
            except (ValueError, TypeError):
                canonical = str(arguments)
            key = name + ":" + canonical
            reused = key in cache
            observation = cache[key] if reused else self.tools.execute(name, arguments, state["user_text"])
            cache[key] = observation
            observations.append({"role": "tool", "tool_call_id": call["id"],
                                 "content": json.dumps(observation, ensure_ascii=False)})
            events.append({"tool_call_id": call["id"], "tool": name, "arguments": arguments,
                           "observation": observation, "reused": reused})
        return {"observations": observations, "events": events, "cache": cache}

    def observation_node(self, state):
        """Return every execution result with the original tool-call ID, then loop."""
        return {"messages": [*state["messages"], *state["observations"]], "pending": [], "observations": []}

    def final_node(self, state):
        try:
            obj = parse_final(state["messages"][-1])
            return {"answer": obj["answer"], "decision_summary": obj["decision_summary"]}
        except (ValueError, TypeError):
            if state["steps"] >= self.max_steps:
                return {"error": "The model did not return a valid final answer within the step limit."}
            return {"answer": ""}

    def repair_node(self, state):
        return {"messages": [*state["messages"], {"role": "user", "content":
            'Return a valid final JSON object with exactly two nonempty string fields: decision_summary and answer. '
            'If an action is still needed, request it through the tool interface first.'}]}

    def respond(self, message, history=None, *, return_trace=False):
        history = normalize_history(history)
        if not isinstance(message, str) or not message.strip() or len(message) > 6000:
            answer = "Please enter a question of 1–6000 characters."
            return (answer, {"error": answer}) if return_trace else answer
        state = {"messages": build_messages(self.knowledge, self.persona, self.options, history, message),
                 "user_text": "\n".join([m["content"] for m in history if m["role"] == "user"] + [message]),
                 "steps": 0, "pending": [], "observations": [], "events": [], "requests": [], "cache": {},
                 "answer": "", "error": "", "decision_summary": ""}
        state = self.graph.invoke(state, {"recursion_limit": 4 * self.max_steps + 4})
        answer = state["answer"] or state["error"]
        if state["error"]:
            saved = [e["observation"]["record_id"] for e in state["events"] if e["observation"].get("record_id")]
            if saved:
                answer += " Records already saved: " + ", ".join(dict.fromkeys(saved)) + "."
        trace = {"mode": getattr(self.model, "mode", "mock"), "persona": self.persona,
                 "generation": self.generation.options(), "prompt_options": self.options.__dict__,
                 "input": message, "history": history, "steps": state["steps"], "events": state["events"],
                 "requests": state["requests"], "decision_summary": state["decision_summary"],
                 "answer": answer, "error": state["error"]}
        try:
            self.tools.log.append("traces", trace)
        except OSError:
            trace["trace_storage_error"] = True
        return (answer, trace) if return_trace else answer
