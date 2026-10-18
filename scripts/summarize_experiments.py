"""Recompute the analysis from saved trials without additional API requests."""
from pathlib import Path
import csv
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from experiments import aggregate, evaluate, CASES


def run():
    folder=ROOT/'evidence/experiments'
    rows=[];changes=[]
    for path in sorted((folder/'trials').glob('*.json')):
        row=json.loads(path.read_text(encoding='utf-8'))
        revised=evaluate(next(c for c in CASES if c['id']==row['case']),row['traces'])
        if revised['checks']!=row['checks']:
            changes.append({'trial':row['trial_id'],'original_checks':row['checks'],'revised_checks':revised['checks']})
        row.update(revised);rows.append(row)
    summary=aggregate(rows)
    analysis={'note':'Analysis-only revision: normalize Unicode apostrophes in the refusal check. Original scores and all raw responses are retained unchanged.',
              'changed_trials':changes,'summary':summary}
    (folder/'scoring_revision.json').write_text(json.dumps(analysis,indent=2),encoding='utf-8')
    columns=['setup','passed','trials','pass_rate','mean_seconds','mean_calls','mean_answer_words','prompt_tokens','completion_tokens']
    with (ROOT/'evidence/comparison.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');writer.writeheader();writer.writerows(summary)
    lines=['# Experiment results','',
        'The final run contains **192 live trials**: 12 setups × 8 fixed scenarios × 2 repetitions. Lead collection uses two turns. Requests were shuffled with seed 503 and ran with four workers. All setups used `gpt-4.1-mini`. Both default personas passed 16/16 functional trials.',
        '', '| Setup | Passed | Mean seconds per trial | Mean model calls | Mean final answer words |',
        '|---|---:|---:|---:|---:|']
    for s in summary:
        lines.append(f"| {s['setup']} | {s['passed']}/{s['trials']} | {s['mean_seconds']:.2f} | {s['mean_calls']:.2f} | {s['mean_answer_words']:.1f} |")
    lines += ['', '## What changed and what stayed fixed','',
        '- `mira_default` and `sami_default` compare complete persona bundles: role, style, and default generation settings. They do not isolate persona wording from temperature.',
        '- The CoT-style condition adds a private step-by-step prompt. It returns the same brief public summary/answer format. No private chain-of-thought is collected, and the experiment cannot verify internal reasoning.',
        '- Zero-shot removes the worked examples. Instruction placement moves only the operational instructions/examples between the system and current user message; the protocol, factual sources, and safety constraints stay system-level.',
        '- The minimal condition replaces the detailed operational rules with one generic instruction, retaining the examples and common protocol.',
        '- Temperature, frequency penalty, presence penalty, and token-budget conditions each change one setting relative to Mira. The top-p pair uses temperature 1 in both conditions and changes only top-p, from 1 to 0.5. Top-k is not accepted by this API and is never sent.',
        '', '## Observations','',
        'The detailed instruction block mattered most on the multi-quote task. Both minimal-instruction repetitions substituted a four-person team for the requested five students in the two-session quote. The default instructions explicitly preserve the requested quantities, and both personas returned USD 240 with successful matching tool observations.',
        '',
        'Zero-shot attempted to save a lead before an email was supplied in one trial. Validation rejected the attempt; after the next user message, the correct lead was saved. Worked examples avoided that premature action in the default trials. A 180-token completion limit truncated one comparison response after successful tools. The error was shown instead of presenting an incomplete answer as a pass.',
        '',
        'The private step-by-step prompt, higher penalties, and top-p change did not improve functional success over the default on this case set. Several setups tied at 16/16, so there is no unique accuracy winner. The low-temperature Mira condition had shorter answers; observed timing differences are descriptive and may reflect provider/network scheduling under four-worker concurrency.',
        '', '## Evidence and scoring limits','',
        'The checker requires completed turns, required successful tools, selected factual values, correct target quote arguments, exact lead contact fields, and no unrequested writes. Naturalness and overall helpfulness are assessed separately through examples, not assigned a fabricated numeric score. Passing these checks does not prove every sentence is correct.',
        '',
        'The final run used 433 attempted API requests. Token totals in `comparison.csv` cover responses returned by the adapter; the truncated response is not included in those totals. Two repetitions and eight scenarios support an exploratory comparison, not statistical significance or universal reliability.',
        '',
        'All trial inputs, actual replies, tool arguments, returned observations, model settings, usage, and latencies are under `evidence/experiments/trials/`. `plan.json` preserves the source snapshot used for the run. `manifest.json` hashes the original JSON artifacts. The original summary scored the minimal condition at 13/16 because a typographic apostrophe hid a correct refusal; `scoring_revision.json` documents the correction to 14/16 without changing responses.',
        '',
        'The first full run is retained in `evidence/experiments_initial/`. It exposed the quote-quantity issue and a checker that incorrectly required the target quote to be last. `scoring_revision.json` there separates re-scoring from real model improvements. The second run followed the instruction fix; it is a fresh run, not a selection of only passing trials.',
        '',
        'Quote totals are planning estimates using the published unit prices and an explicit grouping calculation. They do not establish availability or approval for multiple teams/sessions. Staff must confirm feasibility.',
    ]
    (ROOT/'docs/experiment_results.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Updated result table and analysis from saved trials; no API calls.')


if __name__=='__main__':run()
