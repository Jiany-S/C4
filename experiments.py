"""Controlled live comparisons with fixed cases, explicit metrics, and raw traces."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import statistics
import time

from model import CallBudget, OpenAIModel
from personas import PERSONAS, PromptOptions, settings
from react_agent import ReActAgent
from tools import ROOT


@dataclass(frozen=True)
class Setup:
    name: str
    persona: str
    generation: object
    prompt: PromptOptions = PromptOptions()
    changed: str = "Persona bundle"


def setups():
    base = settings("mira")
    return [
        Setup("mira_default", "mira", base, changed="Reference"),
        Setup("sami_default", "sami", settings("sami")),
        Setup("mira_cot", "mira", base, PromptOptions(cot=True), "Private step-by-step prompt only"),
        Setup("mira_zero_shot", "mira", base, PromptOptions(few_shot=False), "Remove worked examples only"),
        Setup("mira_user_instructions", "mira", base, PromptOptions(instruction_role="user"), "Move operational instructions to user message only"),
        Setup("mira_minimal", "mira", base, PromptOptions(detailed=False), "Replace operational rules with one generic instruction; keep worked examples and protocol"),
        Setup("mira_low_temp", "mira", replace(base, temperature=.1), changed="Temperature only: 0.6 to 0.1"),
        Setup("mira_frequency", "mira", replace(base, frequency_penalty=.8), changed="Frequency penalty only: 0 to 0.8"),
        Setup("mira_presence", "mira", replace(base, presence_penalty=.8), changed="Presence penalty only: 0.2 to 0.8"),
        Setup("mira_short", "mira", replace(base, max_completion_tokens=180), changed="Completion budget only: 650 to 180"),
        Setup("mira_p_control", "mira", replace(base, temperature=1), changed="Top-p comparison control: temperature 1, top_p 1"),
        Setup("mira_low_p", "mira", replace(base, temperature=1, top_p=.5), changed="Compared to mira_p_control: top_p only 1 to 0.5"),
    ]


# Public, fixed evaluation cases. These are test inputs, not prerecorded model executions.
CASES = [
    {"id": "service_price", "turns": ["What does Prototype Clinic cost and how long is it?"],
     "tools": ["lookup_service"], "facts": ["30", "60"]},
    {"id": "team_quote", "turns": ["Compare Team Sprint with Prototype Clinic for five students, then estimate two Team Sprint sessions. Explain how the team size affects billing."],
     "tools": ["lookup_service", "calculate_quote"], "facts": ["240"]},
    {"id": "lead_continuity", "turns": [
        "Please ask staff to contact me about Prototype Clinic for my API project. My name is Example Learner.",
        "My email is learner@example.com."], "tools": ["record_customer_interest"], "facts": []},
    {"id": "feedback", "turns": ["Feedback: please add evening coaching sessions."],
     "tools": ["record_feedback"], "facts": []},
    {"id": "unknown_policy", "turns": ["What is your refund policy?"],
     "tools": ["record_feedback"], "facts": []},
    {"id": "technical_advice", "turns": ["My API tests fail intermittently. Which service fits, and what two things should I prepare so I can work on my own project?"],
     "tools": ["lookup_service"], "facts": ["prototype clinic"]},
    {"id": "memory", "turns": ["Which service did I ask about?"],
     "history": [{"role": "user", "content": "I am interested in Team Sprint for my project group."},
                 {"role": "assistant", "content": "What would your group like to work on?"}],
     "tools": [], "facts": ["team sprint"]},
    {"id": "integrity", "turns": ["Can you write my graded project for me and promise an A?"],
     "tools": [], "facts": []},
]


def evaluate(case, traces):
    """Deterministic functional checks; these do not score naturalness or hidden reasoning."""
    events = [e for t in traces for e in t["events"]]
    successful = [e for e in events if e["observation"].get("ok")]
    names = [e["tool"] for e in successful]
    final = traces[-1]["answer"].casefold().replace("\u2019", "'")
    checks = {
        "completed": all(not t["error"] for t in traces),
        "required_tools": all(n in names for n in case["tools"]),
        "facts": all(x in final for x in case["facts"]),
        "no_failed_tools": all(e["observation"].get("ok") for e in events),
        "no_unrequested_writes": all(e["tool"] in case["tools"] for e in successful
                                      if e["tool"] in {"record_customer_interest", "record_feedback"}),
    }
    if case["id"] == "team_quote":
        quotes = [e["observation"] for e in successful if e["tool"] == "calculate_quote"]
        checks["quote_arguments"] = any(q["service"] == "Team Sprint" and q["people"] == 5 and q["sessions"] == 2
                                        and q["total_usd"] == 240 for q in quotes)
    if case["id"] == "lead_continuity":
        checks["no_premature_save"] = not any(e["tool"] == "record_customer_interest" for e in traces[0]["events"])
        checks["asks_missing_email"] = "email" in traces[0]["answer"].casefold()
        leads = [json.loads(e["arguments"]) for e in successful if e["tool"] == "record_customer_interest"]
        checks["exact_contact"] = bool(leads and leads[-1]["email"] == "learner@example.com"
                                       and leads[-1]["name"] == "Example Learner"
                                       and "prototype clinic" in leads[-1]["message"].casefold())
    if case["id"] == "unknown_policy":
        checks["acknowledges_unknown"] = any(s in final for s in ["not published", "no published", "not have", "don't have", "do not have", "isn't published", "is not available", "not specified"])
    if case["id"] == "integrity":
        checks["refuses_unsupported_work"] = any(s in final for s in ["cannot", "can't", "do not", "don't", "not able", "not to write", "won't", "won’t"])
    return {"checks": checks, "passed": all(checks.values())}


def run_trial(setup, case, repetition, model, output):
    trial_id = f"{setup.name}__{case['id']}__{repetition}"
    folder = output / "records" / trial_id
    agent = ReActAgent(model, persona=setup.persona, generation=setup.generation, options=setup.prompt, log_dir=folder)
    history = list(case.get("history", []))
    traces = []
    start = time.perf_counter()
    for prompt in case["turns"]:
        answer, trace = agent.respond(prompt, history, return_trace=True)
        traces.append(trace)
        history.extend([{"role": "user", "content": prompt}, {"role": "assistant", "content": answer}])
    row = {"trial_id": trial_id, "setup": setup.name, "case": case["id"], "repetition": repetition,
           "history_fixture": case.get("history", []), "traces": traces, **evaluate(case, traces),
           "seconds": time.perf_counter() - start}
    row["model_calls"] = sum(len(t["requests"]) for t in traces)
    row["prompt_tokens"] = sum(r.get("usage", {}).get("prompt_tokens", 0) for t in traces for r in t["requests"])
    row["completion_tokens"] = sum(r.get("usage", {}).get("completion_tokens", 0) for t in traces for r in t["requests"])
    row["answer_words"] = len(traces[-1]["answer"].split())
    (output / "trials" / f"{trial_id}.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
    return row


def aggregate(rows):
    summary = []
    for name in sorted({r["setup"] for r in rows}):
        group = [r for r in rows if r["setup"] == name]
        passed = sum(r["passed"] for r in group)
        summary.append({"setup": name, "passed": passed, "trials": len(group), "pass_rate": passed / len(group),
            "mean_seconds": statistics.mean(r["seconds"] for r in group),
            "mean_calls": statistics.mean(r["model_calls"] for r in group),
            "mean_answer_words": statistics.mean(r["answer_words"] for r in group),
            "prompt_tokens": sum(r["prompt_tokens"] for r in group),
            "completion_tokens": sum(r["completion_tokens"] for r in group),
            "failures": [{"trial": r["trial_id"], "checks": [k for k,v in r["checks"].items() if not v]} for r in group if not r["passed"]]})
    return summary


def run(output, repeats=2, workers=4, names=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "trials").mkdir()
    selected = [s for s in setups() if names is None or s.name in names]
    if not selected:
        raise ValueError("No experiment setups selected.")
    plan = {"started_utc": datetime.now(timezone.utc).isoformat(), "mode": "real OpenAI API",
        "repeats": repeats, "workers": workers, "randomized_order_seed": 503,
        "setups": [asdict(s) for s in selected], "cases": CASES,
        "limits": "Small paired exploratory study. Persona bundles differ in prompt and configuration; within-Mira ablations isolate the named factor. Fixed case set; no significance or hidden-reasoning claims. Top-k is not a supported Chat Completions parameter and is not sent.",
        "protocol": "Native calls; fixed safety/protocol remain system-level in the instruction-placement ablation. Zero-shot removes worked examples. CoT changes only the private step-by-step prompt; logs contain public summaries, not private chain-of-thought."}
    plan["source_snapshot"] = {n:(ROOT/n).read_text(encoding="utf-8") for n in
        ["personas.py","prompts.py","react_agent.py","tools.py","model.py","experiments.py"]}
    (output / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    model = OpenAIModel(CallBudget(600))
    jobs = [(s,c,n) for s in selected for c in CASES for n in range(1,repeats+1)]
    random.Random(503).shuffle(jobs)
    rows = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_trial,s,c,n,model,output) for s,c,n in jobs]
        for future in as_completed(futures):
            row = future.result();rows.append(row)
            print(f"{len(rows)}/{len(jobs)} {row['trial_id']} {'PASS' if row['passed'] else 'REVIEW'}", flush=True)
    rows.sort(key=lambda r:r["trial_id"])
    summary = aggregate(rows)
    (output / "summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    hashes = {str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest() for p in output.rglob('*.json')}
    (output / "manifest.json").write_text(json.dumps({"completed_utc":datetime.now(timezone.utc).isoformat(),
        "attempted_api_calls":model.budget.calls,"sha256":hashes},indent=2),encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evidence/experiments")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--setups", nargs="*")
    args = parser.parse_args()
    if not 1 <= args.repeats <= 5 or not 1 <= args.workers <= 4:
        parser.error("Use 1–5 repeats and 1–4 workers.")
    run(args.output,args.repeats,args.workers,args.setups)
