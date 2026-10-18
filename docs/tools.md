# Tool contracts

The schemas in `tools.py` are included in the system prompt and sent through OpenAI's native function interface. The model requests actions; the graph's `act` node validates and executes them, and `observe` returns JSON with the original call ID.

| Tool | Required inputs | Successful observation |
|---|---|---|
| `lookup_service` | `service`: exact name or `all` | Published service name, duration, unit price, billing unit, capacity, and purpose |
| `calculate_quote` | `service`, integer `people` (1–100), integer `sessions` (1–20) | Exact input quantities, billing units per session, total USD, and `booking_confirmed: false` |
| `record_customer_interest` | Customer-supplied `email`, `name`, `message` | `ok: true`, generated record ID, `kind: leads`, and local JSONL storage |
| `record_feedback` | `question`: feedback or unanswered business question | `ok: true`, generated record ID, `kind: feedback`, and local JSONL storage |

Quotes multiply the published unit price by billing units and sessions. For Team Sprint, the estimate assumes `ceil(people / 4)` teams; other services bill per student. This grouping is an estimating assumption, not confirmation that multiple teams can attend or that staff are available. No discounts are assumed.

Writing tools persist generated UUIDs and UTC timestamps in `logs/leads.jsonl` or `logs/feedback.jsonl`. The record ID in the observation matches the stored record. Validation rejects unknown tools, invalid JSON, missing/extra fields, wrong types, unsupported quantities, and malformed contacts. Lead dispatch checks that the name and email occur in the user's recent messages; deciding whether the request expresses consent remains model-dependent.

Failed execution returns `ok: false` with a safe error. The model receives the failed observation and can ask for corrected information or explain the failure. It must not claim a successful save. Equivalent calls within the same turn reuse the observation to avoid duplicate writes; this does not deduplicate retries in different turns.

Each turn has a maximum of six model steps. A tool action is not executed at the final step because a model call must remain available to read its observation. Invalid final JSON is repaired within the same budget. Incomplete model responses remain errors, with their returned usage and finish reason retained in the trace. Failed requests count toward the turn’s step count. If the API fails after a successful save, the error reply includes the saved record IDs. Trace-storage errors do not turn a successful tool write into a failure.

Runtime traces contain the persona, exact generation settings, prompt condition, input/history, actual model replies, tool arguments, observations, usage, timing, final answer, and safe errors. They contain no API key and are ignored by Git. Only fictional evaluation data is included in the submitted evidence folders.
