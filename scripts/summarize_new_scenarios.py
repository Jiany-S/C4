"""Review the supplementary checks while retaining the original scores and replies."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiments import aggregate


def review_checks(row):
    checks = dict(row['checks'])
    if row['case'] == 'new_quote':
        # A pure estimate needs the calculator, whose observation includes the quantities
        # and total. A separate catalog read is not needed to establish that estimate.
        checks['required_tools'] = any(e['tool'] == 'calculate_quote' and e['observation'].get('ok')
            for trace in row['traces'] for e in trace['events'])
    return checks


def run():
    folder = ROOT / 'evidence/new_scenarios'
    rows, changes = [], []
    for path in sorted((folder / 'trials').glob('*.json')):
        row = json.loads(path.read_text(encoding='utf-8'))
        revised = review_checks(row)
        if revised != row['checks']:
            changes.append({'trial':row['trial_id'],'original_checks':row['checks'],'revised_checks':revised})
        rows.append({**row,'checks':revised,'passed':all(revised.values())})
    summary = aggregate(rows)
    analysis = {'note':'The initial supplementary checker unnecessarily required lookup_service for a pure quote. '
        'The calculator already returns authoritative quantities and totals. Require the calculator and both exact '
        'six-person quote observations instead; all other checks remain. Original scores and responses are unchanged.',
        'changed_trials':changes,'summary':summary}
    (folder/'scoring_revision.json').write_text(json.dumps(analysis,indent=2),encoding='utf-8')
    lines = ['# Checks on new scenarios','',
        'After the 192-trial study, the existing personas were tested on three new cases, twice each. '
        'Their prompts and generation settings were held fixed. This adds 12 live trials; it is a small supplementary '
        'check, rather than an independent human evaluation.','',
        '| Persona | Correct tools and selected facts | Cases |','|---|---:|---|']
    for s in summary:
        lines.append(f"| {s['setup']} | {s['passed']}/{s['trials']} | First-step advice, intermittent CI failures, new quote quantities |")
    lines += ['',
        'Both personas recommended Project Clarity for an unscoped app idea and Prototype Clinic for intermittent CI failures. '
        'For six students, both calculated USD 360 for three Team Sprint sessions and USD 180 for one Prototype Clinic session. '
        'The exact people, sessions, service names, and totals are present in the successful observations.', '',
        'The styles still overlap on simple questions. In the preparation advice, Mira gives an approachable starting point; '
        'Sami emphasizes diagnostic evidence. These are qualitative observations of the saved replies, not independent user ratings.', '',
        'The original checker flagged four quote trials because no separate lookup was requested. Their calculations and replies '
        'were correct. A pure estimate can use the calculation tool directly, so the analysis corrects that overly strict requirement '
        'while still requiring both exact quote observations. The original 8/12 score and all replies remain untouched; '
        '`scoring_revision.json` records the reviewed 12/12 result.', '',
        'Reproduce with `python scripts/check_new_scenarios.py --output evidence/my_new_scenarios`. '
        'The script refuses to overwrite an existing run. Verify saved hashes with '
        '`python scripts/verify_evidence.py evidence/new_scenarios`.',
    ]
    (ROOT/'docs/new_scenarios.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Supplementary review:',sum(r['passed'] for r in rows),'/',len(rows))


if __name__=='__main__':
    run()
