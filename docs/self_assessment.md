# C4 self-assessment

Assessed against all three pages of the supplied C4 assignment on 18 October 2026. This is an estimated evaluation, not an instructor-assigned grade.

## Requirement mapping

| Requirement | Implementation | Evidence | Status |
|---|---|---|---|
| Goal, audience, tools, and limitations | Notebook section 1; README | Business PDF and summary reused from C3 | PASS |
| One permitted framework | `ReActAgent.build_graph` uses LangGraph StateGraph | Actual compiled graph in notebook section 4 | PASS |
| Manually implement ReAct rather than use a prebuilt executor | `model_node`, `next_node`, `action_node`, `observation_node`, `final_node`, `repair_node` | Multi-action unit test and real quote trials | PASS |
| System behavior and tool descriptions | `prompts.PROTOCOL`, `build_messages`, `TOOL_SCHEMAS` | Notebook sections 3 and 5; source snapshots in experiment plans | PASS |
| Detect suggested action | `model_node` reads and validates native `tool_calls` | `test_multi_action_observation_loop_and_final_parse` | PASS |
| Execute, return observation, and repeat | Action/observation nodes; matching `tool_call_id` | Real quote trial has lookup, multiple calculations, then final answer | PASS |
| Parse final answer | `parse_final`; format repair and step budget | Invalid final JSON, repair, and limit tests | PASS |
| At least two distinct personas and matching settings | `personas.PERSONAS`: Mira service guide and Sami project reviewer | 16 live trials per default persona; technical-advice examples | PASS |
| CoT-style versus direct prompting | `PromptOptions.cot` | 16 live trials for each condition; public summaries only | PASS for prompting comparison; internal reasoning is not observable |
| Zero-shot versus few-shot | `PromptOptions.few_shot`; two worked examples | 16 trials each; premature action in zero-shot retained | PASS |
| System versus in-message instructions | `PromptOptions.instruction_role` | Controlled role-placement comparison; protocol held fixed | PASS |
| Vary generation configurations | Temperature, top-p, two penalties, completion limit | 12-setup plan; actual settings in every trace | PASS; top-k unsupported and omitted |
| Log experiments and compare | `experiments.py`, `summarize_experiments.py` | 192 final trials, CSV, summaries, source snapshots, and hash manifest | PASS |
| Separate, clear instructions with explicit input/output and worked example | `INSTRUCTIONS`, `EXAMPLES` | Notebook section 3; reduced-instruction ablation | PASS |
| Answer all five reflection questions in notebook or PDF | Notebook section 12 and `docs/reflection.md` | Evidence-linked answers with limits and failure analysis | PASS |
| Working assistant | `app.py` with persona and configuration controls | Offline suite, fresh-kernel notebook, real Gradio queue check, and live browser checks | PASS within tested scope |

## Strict estimated grade

| Published criterion | Maximum | Estimate | Reason |
|---|---:|---:|---|
| Use-case summary and write-up | 10 | 10 | Clear continuation of C3 with explicit audience, goals, tools, and limits |
| ReAct logic manually implemented | 30 | 30 | Explicit graph decisions, real actions, matching observations, repeated calls, parsing, repair, and bounded errors |
| Persona design and configuration | 20 | 18 | Roles and defaults differ and are tested, but styles overlap on routine service/lead questions |
| Configuration experiments and comparison | 15 | 14 | Controlled live matrix with retained failures; only two repetitions and eight cases |
| Clear instructions | 10 | 10 | Separate instructions, explicit I/O, worked examples, quantity preservation, and demonstrated ablation effect |
| Creativity, clarity, and reflection | 15 | 13 | Practical two-role extension and grounded reflection; naturalness judgments lack independent human ratings |
| **Total** | **100** | **95** | Estimated range 93–97 depending on the instructor's assessment of depth and presentation |

## Verification and remaining limits

The automated suite covers the graph, tool validation and storage, observation IDs, memory isolation, deduplication, API-failure handling, final parsing, prompt controls, evaluation checks, and interface construction. The notebook executes in a fresh kernel without paid calls. Gradio's real HTTP/queue is exercised with a scripted model; real API persona/tool behavior is established separately by the experiment trials and browser rehearsal.

Both default personas passed 16/16 final functional trials. That is a small benchmark result, not a general reliability guarantee. A scorer correction recognizes a valid refusal with a typographic apostrophe; the original output and scores remain intact. The reduced-instruction, zero-shot, and short-token failures remain in the final study.

The main weaknesses are limited repetitions, no held-out benchmark, no independent human style ratings, finite history, and model-dependent intent interpretation. Error paths are tested with injected failures rather than deliberate provider outages. Quote grouping is an explicit estimate assumption; it does not prove multi-team availability. Local JSONL is not a production database, and cross-turn retries are not idempotent.

C4 has no listed bonus or explicit video requirement in the supplied assignment. Hugging Face hosting is not claimed. The submission is the complete runnable project and executed notebook, including the experiments and reflection. The course PDFs, credentials, environment, runtime logs, and local scratch files are excluded from the repository.
