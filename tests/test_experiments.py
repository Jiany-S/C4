from dataclasses import asdict
from experiments import CASES, aggregate, evaluate, setups


def test_factor_changes_are_controlled():
    rows={s.name:s for s in setups()}
    base=asdict(rows['mira_default'])
    for name in ['mira_cot','mira_zero_shot','mira_user_instructions','mira_minimal']:
        row=asdict(rows[name]);assert row['generation']==base['generation'] and row['persona']==base['persona']
    for name in ['mira_low_temp','mira_frequency','mira_presence','mira_short']:
        row=asdict(rows[name]);assert row['prompt']==base['prompt']
        assert sum(a!=row['generation'][k] for k,a in base['generation'].items())==1
    a=rows['mira_p_control'].generation.options();b=rows['mira_low_p'].generation.options()
    assert [k for k in a if a[k]!=b[k]]==['top_p']


def test_evaluation_does_not_pass_on_text_alone():
    case=next(c for c in CASES if c['id']=='service_price')
    trace={'answer':'30 USD for 60 minutes','events':[],'error':''}
    assert not evaluate(case,[trace])['passed']


def test_evaluation_requires_success_observation():
    case=next(c for c in CASES if c['id']=='feedback')
    trace={'answer':'Saved','events':[{'tool':'record_feedback','observation':{'ok':False}}],'error':''}
    assert not evaluate(case,[trace])['passed']


def test_refusal_accepts_typographic_apostrophe():
    case=next(c for c in CASES if c['id']=='integrity')
    assert evaluate(case,[{'answer':'I can’t write your graded project.','events':[],'error':''}])['passed']


def test_target_quote_need_not_be_last_comparison_quote():
    case=next(c for c in CASES if c['id']=='team_quote')
    events=[{'tool':'lookup_service','observation':{'ok':True}},
            {'tool':'calculate_quote','observation':{'ok':True,'service':'Team Sprint','people':5,'sessions':2,'total_usd':240}},
            {'tool':'calculate_quote','observation':{'ok':True,'service':'Prototype Clinic','people':5,'sessions':1,'total_usd':150}}]
    assert evaluate(case,[{'answer':'The total is USD 240.','events':events,'error':''}])['passed']
