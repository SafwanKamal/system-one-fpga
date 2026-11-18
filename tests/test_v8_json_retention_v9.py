import copy
import hashlib
import json
from sysone.v2.v8_json_retention_v9 import manifest,prepare,execute,summarize


def encode(text):return [0]*110


def test_six_fresh_cases_balanced_lengths_and_bounded_requests():
    spec=manifest();data=prepare(spec,encode)
    assert len(data)==spec['maximum_inferences']==236
    assert sorted(len(c['steps']) for c in spec['cases'])==[16,16,32,32,64,64]
    assert len({c['seed'] for c in spec['cases']})==6
    assert all(c['mode']=='retention' for c in spec['cases'])
    assert not spec['closed_loop_included'] and not spec['board_access'] and not spec['full_sweep_started']


def test_independent_event_replay_matches_all_frozen_snapshots():
    spec=manifest();data=prepare(spec,encode)
    for c in spec['cases']:
        state=copy.deepcopy(c['initial'])
        rs=[r for r in data if r['case_id']==c['id'] and r['suite']=='primary']
        for step,row in zip(c['steps'],rs):
            event=step['observation']
            if event:
                e=event['entity']
                if event['status']=='ok':state[e][0]=event['count']
                else:assert 'count' not in event
                state[e][1]=event['status']
            assert row['state']==state
            e=step['entity'];assert row['expected']==[state[e][1],e,state[e][0]]
            assert json.dumps({k:dict(count=v[0],status=v[1]) for k,v in state.items()},separators=(',',':')) in row['prompt']


def test_wrong_answers_cannot_rewrite_later_state_or_leak_gold():
    data=prepare(manifest(),encode);before=copy.deepcopy(data)
    def infer(job):
        assert set(job)=={'id','prompt','prompt_ids','output_tokens'}
        return dict(generated_text='["error","A",9999]',terminal_eos=True)
    rows=[execute(j,infer) for j in data]
    assert data==before
    assert all(r['state']==j['state'] for r,j in zip(rows,before))
    assert all(9999 not in [v[0] for v in j['state'].values()] for j in data)


def test_exact_repeat_controls_and_unique_input_reporting():
    data=prepare(manifest(),lambda t:list(hashlib.sha256(t.encode()).digest()));index={r['id']:r for r in data}
    repeats=[r for r in data if r['suite']=='repeat'];assert len(repeats)==12
    for r in repeats:
        primary=index[r['repeat_of']]
        assert r['prompt']==primary['prompt'] and r['prompt_ids']==primary['prompt_ids']
    rows=[dict(j,correct=True,parsed=True,category='correct',generated_text='same') for j in data]
    result=summarize(rows)
    assert result['primary']['n']==224 and result['repeat_count']==12 and result['repeat_text_mismatches']==0
    assert 1<result['unique_inputs']['n']<224
    assert all(c['all_correct'] and c['longest_correct_run']==c['n'] for c in result['chains'].values())


def test_long_gap_keeps_initial_count_missing_status_until_final_refresh():
    data=prepare(manifest(),encode)
    rs=[r for r in data if r['case_id']=='long-gap-64' and r['suite']=='primary']
    assert max(r['query_age'] for r in rs if r['entity']=='A')>=60
    assert all(r['state']['A']==rs[0]['state']['A'] for r in rs[:-1])
    assert rs[-1]['state']['A'][1]=='ok'


def test_unparseable_and_wrong_fields_are_distinct():
    j=prepare(manifest(),encode)[0]
    bad=execute(j,lambda job:dict(generated_text='{"count":',terminal_eos=False))
    assert bad['category']=='extraction-budget' and bad['wrong_fields']==[]
    text=json.dumps(['error',j['entity'],j['expected'][2]+1])
    wrong=execute(j,lambda job:dict(generated_text=text,terminal_eos=True))
    assert wrong['category']=='parsed-wrong' and set(wrong['wrong_fields'])=={'status','count'}
