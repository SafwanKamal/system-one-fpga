import copy
import json
from collections import Counter
from sysone.v2.v8_json_retention_v10 import (development,evaluation,prompt,development_summary,execute)
from sysone.v2.v8_json_retention_v9 import manifest as old_manifest,prepare as old_prepare


def encode(text):return [0]*120


def test_development_is_paired_and_balanced_across_status_entity_and_distractors():
    spec,jobs=development(encode)
    assert spec['maximum_inferences']==len(jobs)==72
    selected=[r for r in jobs if r['policy']=='status-copy']
    assert len({json.dumps([r['state'],r['entity']],sort_keys=True) for r in selected})==36
    assert Counter(r['expected'][0] for r in selected)=={'ok':12,'missing':12,'error':12}
    assert Counter((r['state']['A'][1],r['state']['B'][1],r['entity']) for r in selected)=={
        (a,b,e):2 for a in ('ok','missing','error') for b in ('ok','missing','error') for e in ('A','B')}
    for a,b in zip(jobs[::2],jobs[1::2]):
        assert a['state']==b['state'] and a['expected']==b['expected'] and a['prompt']!=b['prompt']


def test_evaluation_tasks_are_fresh_against_development_and_v9():
    _,dev=development(encode);spec,jobs=evaluation(encode)
    sig=lambda j:json.dumps([j['state'],j['entity']],sort_keys=True)
    prior={sig(j) for j in dev+old_prepare(old_manifest(),encode)}
    assert all(sig(j) not in prior for j in jobs)
    assert len(jobs)==236 and all(j['policy']=='status-copy' for j in jobs)
    assert all(c['mode']=='retention' for c in spec['cases'])
    assert not spec['closed_loop_included'] and not spec['board_access'] and not spec['full_sweep_started']


def test_independent_replay_of_resampled_and_swapped_observations():
    spec,jobs=evaluation(encode);index={r['id']:r for r in jobs}
    for c in spec['cases']:
        state=copy.deepcopy(c['initial'])
        for i,step in enumerate(c['steps'],1):
            event=step['observation']
            if event:
                e=event['entity']
                if event['status']=='ok':state[e][0]=event['count']
                state[e][1]=event['status']
            r=index[f'{c["id"]}-{i:03d}'];e=step['entity']
            assert r['state']==state and r['expected']==[state[e][1],e,state[e][0]]
            assert r['prompt']==prompt(state,e,'status-copy')
    for r in jobs:
        if r['suite']=='repeat':assert r['prompt']==index[r['repeat_of']]['prompt']


def test_strict_predeclared_development_gate_and_no_semantic_repair():
    _,jobs=development(encode)
    rows=[dict(j,correct=True,parsed=True) for j in jobs]
    assert development_summary(rows)['gate_passed']
    rows[1]['correct']=False
    assert not development_summary(rows)['gate_passed']
    job=jobs[1];raw=json.dumps(dict(entity=job['entity'],count=job['expected'][2],status='latest'))
    def infer(request):
        assert set(request)=={'id','prompt','prompt_ids','output_tokens'}
        return dict(generated_text=raw,terminal_eos=True)
    row=execute(job,infer)
    assert not row['parsed'] and not row['correct'] and row['observed'] is None


def test_development_revision_reuses_only_development_and_explicitly_requests_entity():
    _,all_jobs=development(encode);spec,revised=development(encode,include_original=False)
    assert spec['maximum_inferences']==len(revised)==36
    old=[j for j in all_jobs if j['policy']=='status-copy']
    assert revised==old
    assert all(f'State.{j["entity"]}.status' in j['prompt'] and f'State.{j["entity"]}.count' in j['prompt'] for j in revised)
