# Reflection

## Which persona gave the most helpful or natural results

Mira is the better entry point for students who need help choosing a service. Her advice is conversational and ends with a practical next step. Sami is more useful when a student already has a technical blocker. In the saved intermittent-test example, Sami asks for a reproducible test case and relevant environment constraints; Mira asks for the current test code and a description of the problem. Both stay within coaching rather than doing the student's work.

Both defaults passed 16/16 functional trials, so this preference comes from the saved answer styles and their intended roles, not an accuracy difference. The difference is clearest in technical preparation advice and less obvious in routine price or contact collection replies. There was no independent human preference study.

## Which prompt and configuration combination performed best

There was no unique functional winner: both default personas and several ablations passed 16/16. For normal service intake, the practical choice is Mira with the detailed instructions and worked examples in the system message, temperature 0.6, top-p 1, frequency penalty 0, presence penalty 0.2, and a 650-token completion limit. For technical scoping, Sami uses the same protocol and instructions with temperature 0.1 and both penalties 0.

The defaults were retained because they serve different roles and handle the recorded tasks without unnecessary tuning. Low-temperature Mira also passed and produced shorter answers on average. Timing differences are too small and noisy to establish a best configuration. Raising penalties and changing top-p added no functional benefit on these cases. A 180-token limit failed once on a long comparison, so it is too restrictive for the full task set.

The CoT-style condition also passed 16/16, but did not improve success over the default. It asks for private step-by-step thinking while retaining the same short public output format. This tests the effect of that prompt wording; it cannot establish what internal reasoning occurred.

## How well did the agent reason and use tools

The graph explicitly alternates model decisions, tool execution, and returned observations. For the comparison of two Team Sprint sessions for five students, the saved default trace reads the service catalog, calculates comparison quotes, requests the exact five-person two-session quote, and then returns USD 240. The tool observation includes the people, sessions, billing units, and total. The final answer is parsed only after the observations are returned with matching call IDs.

Lead collection demonstrates multi-turn context: after a name and service are supplied, the assistant asks for the missing email and reuses the earlier details. Feedback and unknown-policy questions produce actual local records. A tool call is not counted as success unless its observation has ok=true. Duplicate calls within a turn reuse the original observation.

The first experiment run exposed a genuine mistake: some answers used four people for the requested five-person total. The grouping capacity was being confused with the user's quantity. The revised instructions preserve the exact quantities, and both default personas passed the repeated quote case in the final run. This is improvement on a fixed development benchmark, not evidence of performance on unseen tasks.

## Did the instructions block change behavior noticeably

Yes, particularly on quantity preservation and premature actions. With the reduced operational instructions, both final quote repetitions substituted four people for the requested five-person two-session estimate. The detailed-instruction defaults used the correct quantities and returned USD 240. The minimal condition scored 14/16 after a documented scoring correction.

Removing the worked examples caused one premature lead-save attempt before an email was supplied. The validator rejected it, so no invented contact was saved, and the later email message completed the lead correctly. The default examples explicitly show asking for the missing email instead of calling the writing tool. Zero-shot scored 15/16; the default scored 16/16.

Moving operational instructions into the current user message did not reduce success in this small run. The protocol and safety constraints stayed at system level, so this does not show that arbitrary user-level instructions are equally robust. The test set contains only eight scenarios with two repetitions.

## What were the biggest implementation challenges

The main challenge was separating a model's requested action from a completed action. The graph must validate arguments, execute the function, return the exact observation, and let the model continue before accepting a final answer. Error handling also has to retain record IDs when a later model call fails after a successful write.

The second challenge was keeping the comparisons interpretable. Persona bundles intentionally change both wording and default settings, while the within-Mira ablations change one factor at a time. A separate top-p control keeps temperature fixed. The first scorer mistakenly checked only the last quote in a comparison; another check missed a refusal containing a typographic apostrophe. Both corrections are documented separately, and the original scores and responses remain available.

The final limitation is evaluation scope. Functional checks can verify selected facts, arguments, and saved records, but cannot prove naturalness, complete factual accuracy, or private reasoning quality. Two repetitions provide an exploratory comparison. Quotes are planning estimates using unit prices and grouping assumptions; they do not confirm availability. Local JSONL logging, finite history, and model-dependent interpretation remain classroom-prototype limits.
