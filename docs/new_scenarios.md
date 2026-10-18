# Checks on new scenarios

After the 192-trial study, the existing personas were tested on three new cases, twice each. Their prompts and generation settings were held fixed. This adds 12 live trials; it is a small supplementary check, rather than an independent human evaluation.

| Persona | Correct tools and selected facts | Cases |
|---|---:|---|
| mira_default | 6/6 | First-step advice, intermittent CI failures, new quote quantities |
| sami_default | 6/6 | First-step advice, intermittent CI failures, new quote quantities |

Both personas recommended Project Clarity for an unscoped app idea and Prototype Clinic for intermittent CI failures. For six students, both calculated USD 360 for three Team Sprint sessions and USD 180 for one Prototype Clinic session. The exact people, sessions, service names, and totals are present in the successful observations.

The styles still overlap on simple questions. In the preparation advice, Mira gives an approachable starting point; Sami emphasizes diagnostic evidence. These are qualitative observations of the saved replies, not independent user ratings.

The original checker flagged four quote trials because no separate lookup was requested. Their calculations and replies were correct. A pure estimate can use the calculation tool directly, so the analysis corrects that overly strict requirement while still requiring both exact quote observations. The original 8/12 score and all replies remain untouched; `scoring_revision.json` records the reviewed 12/12 result.

Reproduce with `python scripts/check_new_scenarios.py --output evidence/my_new_scenarios`. The script refuses to overwrite an existing run. Verify saved hashes with `python scripts/verify_evidence.py evidence/new_scenarios`.
