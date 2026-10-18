"""Supplementary live checks on new cases with the persona prompts held fixed."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiments import Setup, aggregate, run_trial
from model import CallBudget, OpenAIModel
from personas import PERSONAS

CASES = [
    {"id":"first_step", "turns":["I feel overwhelmed by my app idea and haven't settled the scope. Which service should I start with, and what is one small thing I can prepare?"],
     "tools":["lookup_service"], "facts":["project clarity"]},
    {"id":"ci_failure", "turns":["My API tests pass locally but fail intermittently in CI. Which service would help me diagnose this, and what two pieces of evidence should I bring?"],
     "tools":["lookup_service"], "facts":["prototype clinic"]},
    {"id":"new_quote", "turns":["For six students, estimate three Team Sprint sessions and compare that with one Prototype Clinic session. Keep the two totals separate."],
     "tools":["calculate_quote"], "facts":["360","180"]},
]


def run(output=None):
    output = Path(output) if output is not None else ROOT / 'evidence/new_scenarios'
    output.mkdir(exist_ok=False)
    (output / 'trials').mkdir()
    selected = [Setup(f'{key}_default',key,p.generation) for key,p in PERSONAS.items()]
    plan = {'mode':'real OpenAI API','started_utc':datetime.now(timezone.utc).isoformat(),
        'purpose':'New-case check after the original 192-trial study; prompts and persona settings unchanged. No tuning after these outcomes.',
        'repetitions':2,'setups':[asdict(s) for s in selected],'cases':CASES,
        'source_snapshot':{n:(ROOT/n).read_text(encoding='utf-8') for n in
            ['prompts.py','personas.py','react_agent.py','model.py','tools.py','scripts/check_new_scenarios.py']}}
    (output / 'plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    model = OpenAIModel(CallBudget(80))
    rows = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(run_trial,s,c,n,model,output) for s in selected for c in CASES for n in [1,2]]
        for future in as_completed(futures):
            row=future.result()
            if row['case']=='new_quote':
                quotes=[e['observation'] for t in row['traces'] for e in t['events']
                        if e['tool']=='calculate_quote' and e['observation'].get('ok')]
                row['checks']['exact_new_quantities'] = (
                    any(q['service']=='Team Sprint' and q['people']==6 and q['sessions']==3 and q['total_usd']==360 for q in quotes)
                    and any(q['service']=='Prototype Clinic' and q['people']==6 and q['sessions']==1 and q['total_usd']==180 for q in quotes))
                row['passed']=all(row['checks'].values())
                (output/'trials'/f"{row['trial_id']}.json").write_text(json.dumps(row,indent=2),encoding='utf-8')
            rows.append(row)
            print(row['trial_id'], 'PASS' if row['passed'] else 'REVIEW',flush=True)
    summary=aggregate(rows)
    (output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    hashes={str(p.relative_to(output)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in output.rglob('*.json')}
    (output/'manifest.json').write_text(json.dumps({'attempted_api_calls':model.budget.calls,
        'completed_utc':datetime.now(timezone.utc).isoformat(),'sha256':hashes},indent=2),encoding='utf-8')


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output')
    run(parser.parse_args().output)
