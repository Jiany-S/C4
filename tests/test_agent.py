import json
from copy import deepcopy
from types import SimpleNamespace
import pytest
from model import CallBudget, ModelError, OpenAIModel
from personas import Generation, PERSONAS, PromptOptions
from prompts import EXAMPLES, INSTRUCTIONS, build_messages
from react_agent import ReActAgent, normalize_history, parse_final
from tools import CATALOG, TOOL_SCHEMAS, Tools, load_business


def final(answer="Done", summary="The observation supports this answer."):
    return {"role": "assistant", "content": json.dumps({"answer": answer, "decision_summary": summary})}


def action(name, args, call_id="call_1"):
    return {"role": "assistant", "content": None, "tool_calls": [{"id": call_id, "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}]}


class ScriptedModel:
    mode = "mock"

    def __init__(self, *replies):
        self.replies = list(replies)
        self.inputs = []

    def complete(self, messages, generation):
        self.inputs.append(deepcopy(messages))
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return {"message": item, "usage": {}, "settings": generation.options()}


def test_business_sources_and_catalog():
    text = load_business()
    assert "[business_summary.txt]" in text and "[about_business.pdf]" in text
    assert all(name in text for name in CATALOG)


def test_personas_have_different_roles_and_config():
    a, b = PERSONAS.values()
    assert a.role != b.role and a.traits != b.traits and a.generation != b.generation
    assert a.generation.model == b.generation.model


def test_multi_action_observation_loop_and_final_parse(tmp_path):
    model = ScriptedModel(action("lookup_service", {"service": "Team Sprint"}),
        action("calculate_quote", {"service": "Team Sprint", "people": 5, "sessions": 2}, "call_2"),
        final("The estimate is USD 240, not a confirmed booking."))
    agent = ReActAgent(model, log_dir=tmp_path)
    answer, trace = agent.respond("Estimate two Team Sprint sessions for five students.", return_trace=True)
    assert "240" in answer and trace["steps"] == 3
    assert [e["tool"] for e in trace["events"]] == ["lookup_service", "calculate_quote"]
    assert model.inputs[1][-1]["role"] == "tool" and model.inputs[1][-1]["tool_call_id"] == "call_1"
    assert json.loads(model.inputs[2][-1]["content"])["total_usd"] == 240
    assert "model" in agent.graph.get_graph().nodes


def test_real_record_and_observation_return(tmp_path):
    args = {"name": "Example Learner", "email": "learner@example.com", "message": "Prototype Clinic"}
    model = ScriptedModel(action("record_customer_interest", args), final("Your follow-up request was recorded."))
    answer, trace = ReActAgent(model, log_dir=tmp_path).respond(
        "Contact me about Prototype Clinic. Example Learner, learner@example.com", return_trace=True)
    record = json.loads((tmp_path/"leads.jsonl").read_text())
    assert record["email"] == args["email"]
    assert record["id"] == trace["events"][0]["observation"]["record_id"]
    assert record["id"] in model.inputs[1][-1]["content"]


def test_feedback_saved(tmp_path):
    model = ScriptedModel(action("record_feedback", {"question": "Please add evening sessions"}), final())
    ReActAgent(model, log_dir=tmp_path).respond("Please add evening sessions")
    assert json.loads((tmp_path/"feedback.jsonl").read_text())["question"] == "Please add evening sessions"


def test_error_after_write_keeps_record_id(tmp_path):
    model = ScriptedModel(action("record_feedback", {"question": "Refund policy?"}), ModelError("API unavailable"))
    answer, trace = ReActAgent(model, log_dir=tmp_path).respond("Refund policy?", return_trace=True)
    assert "API unavailable" in answer and trace["events"][0]["observation"]["record_id"] in answer


def test_missing_contact_is_rejected_by_dispatch(tmp_path):
    obs = Tools(tmp_path).execute("record_customer_interest", json.dumps({
        "name": "Invented", "email": "invented@example.com", "message": "Clinic"}), "I need help")
    assert obs["ok"] is False and not (tmp_path/"leads.jsonl").exists()


@pytest.mark.parametrize("name,args", [
    ("unknown", {}), ("lookup_service", {"service": "not published"}),
    ("lookup_service", {"service": 3}), ("calculate_quote", {"service": "Team Sprint", "people": True, "sessions": 1}),
    ("calculate_quote", {"service": "Team Sprint", "people": 0, "sessions": 1}),
    ("record_feedback", {"question": ""}), ("record_feedback", {"question": "test", "extra": "bad"}),
    ("record_customer_interest", {"name": "Learner", "email": "bad", "message": "Clinic"}),
])
def test_invalid_tool_inputs(tmp_path, name, args):
    assert not Tools(tmp_path).execute(name, json.dumps(args), "Learner bad")["ok"]


def test_storage_error(tmp_path, monkeypatch):
    tool = Tools(tmp_path)
    def fail(*args):
        raise OSError("disk")
    monkeypatch.setattr(tool.log, "append", fail)
    assert tool.record_feedback("Add evenings")["ok"] is False


def test_duplicate_calls_reuse_observation(tmp_path):
    a = action("record_feedback", {"question": "Evenings"})
    b = action("record_feedback", {"question": "Evenings"}, "call_2")
    model = ScriptedModel(a, b, final())
    _, trace = ReActAgent(model, log_dir=tmp_path).respond("Evenings", return_trace=True)
    assert len((tmp_path/"feedback.jsonl").read_text().splitlines()) == 1
    assert trace["events"][1]["reused"] is True


def test_final_protocol_repair(tmp_path):
    model = ScriptedModel({"role": "assistant", "content": "not JSON"}, final("Repaired"))
    assert ReActAgent(model, log_dir=tmp_path).respond("Hello") == "Repaired"
    assert "exactly two" in model.inputs[1][-1]["content"]


def test_step_limit_prevents_unobserved_action(tmp_path):
    model = ScriptedModel(action("record_feedback", {"question": "Evenings"}))
    answer, trace = ReActAgent(model, log_dir=tmp_path, max_steps=1).respond("Evenings", return_trace=True)
    assert "not executed" in answer and not trace["events"] and not (tmp_path/"feedback.jsonl").exists()


def test_memory_and_session_isolation(tmp_path):
    model = ScriptedModel(final(), final())
    agent = ReActAgent(model, log_dir=tmp_path)
    history = [{"role": "user", "content": "I asked about Team Sprint"}, {"role": "assistant", "content": "Okay"}]
    agent.respond("What did I ask?", history)
    agent.respond("Hello")
    assert history[0] in model.inputs[0]
    assert all(m["content"] != history[0]["content"] for m in model.inputs[1])
    assert len(history) == 2


def test_prompt_ablation_changes_only_selected_layer():
    history = [{"role": "user", "content": "Earlier question"}]
    base = build_messages("facts", "mira", PromptOptions(), history, "hello")
    zero = build_messages("facts", "mira", PromptOptions(few_shot=False), history, "hello")
    cot = build_messages("facts", "mira", PromptOptions(cot=True), history, "hello")
    user = build_messages("facts", "mira", PromptOptions(instruction_role="user"), history, "hello")
    assert EXAMPLES in base[0]["content"] and EXAMPLES not in zero[0]["content"]
    assert "Think step by step privately" in cot[0]["content"]
    assert INSTRUCTIONS not in user[0]["content"] and INSTRUCTIONS in user[-1]["content"]
    assert user[1] == base[1] == history[0]


@pytest.mark.parametrize("text", ['{}', '{"answer":"x"}', '{"answer":3,"decision_summary":"x"}'])
def test_bad_final_rejected(text):
    with pytest.raises(ValueError):
        parse_final({"content": text})


def test_api_adapter_preserves_config_and_tools():
    seen = {}
    def create(**kwargs):
        seen.update(kwargs)
        from openai.types.chat import ChatCompletion
        return ChatCompletion(id="test", created=0, model="gpt-4.1-mini", object="chat.completion", choices=[{
            "index": 0, "finish_reason": "stop", "message": final()}],
            usage={"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8})
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    generation = Generation(temperature=.3, top_p=.9, frequency_penalty=.4, presence_penalty=.5, max_completion_tokens=200)
    result = OpenAIModel(client=client).complete([{"role": "user", "content": "Hi"}], generation)
    assert result["usage"]["total_tokens"] == 8
    assert all(seen[k] == v for k,v in generation.options().items())
    assert seen["tools"] == TOOL_SCHEMAS and seen["store"] is False
    assert "top_k" not in seen


def test_budget_limit():
    budget = CallBudget(1);budget.take()
    with pytest.raises(ModelError):
        budget.take()


def test_gradio_history_text_blocks():
    assert normalize_history([{"role":"user", "content":[{"type":"text","text":"Hello"}]}]) == [{"role":"user","content":"Hello"}]
