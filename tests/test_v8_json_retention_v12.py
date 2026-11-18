import copy
import json
from sysone.v2.v8_json_retention_v12 import prepare,execute
from sysone.v2.v8_json_retention_v10 import evaluation,prompt
from sysone.v2.v8_json_fpga_qualification_v11 import prepare as qualification


def encode(text):return [1]*129


def test_lengths_fixed_prompt_and_fresh_state_query_identities():
    spec,jobs=prepare(encode)
    assert len(jobs)==spec['maximum_inferences']==236
    assert sorted(len(c['steps']) for c in spec['cases'])==[16,16,32,32,64,64]
    assert sum(j['suite']=='primary' for j in jobs)==224
    assert spec['closed_loop_included'] is False and spec['full_sweep_started'] is False
    sig=lambda j:json.dumps([j['state'],j['entity']],sort_keys=True)
    prior={sig(j) for j in evaluation(encode)[1]+qualification(encode)[1]}
    assert all(sig(j) not in prior for j in jobs)
    assert all(j['prompt']==prompt(j['state'],j['entity'],'status-copy') for j in jobs)


def test_independent_replay_and_exact_repeats():
    spec,jobs=prepare(encode);index={j['id']:j for j in jobs}
    for case in spec['cases']:
        state=copy.deepcopy(case['initial'])
        for i,step in enumerate(case['steps'],1):
            event=step['observation']
            if event:
                e=event['entity']
                if event['status']=='ok':state[e][0]=event['count']
                state[e][1]=event['status']
            j=index[f'{case["id"]}-{i:03d}'];e=step['entity']
            assert j['state']==state and j['expected']==[state[e][1],e,state[e][0]]
    for j in jobs:
        if j['suite']=='repeat':
            original=index[j['repeat_of']]
            assert j['prompt']==original['prompt'] and j['prompt_ids']==original['prompt_ids']


def test_inference_receives_no_oracle_and_wrong_answers_remain_read_only():
    _,jobs=prepare(encode);before=copy.deepcopy(jobs)
    def infer(request):
        assert set(request)=={'id','prompt','prompt_ids','output_tokens'}
        return dict(generated_text='["ok","A",9999]',terminal_eos=True)
    for job in jobs:execute(job,infer)
    assert jobs==before
