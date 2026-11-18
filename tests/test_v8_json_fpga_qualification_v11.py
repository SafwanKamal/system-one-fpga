import copy
import json
from collections import Counter
from sysone.v2.v8_json_fpga_qualification_v11 import prepare,execute,cpu_prompt_file_bytes
from sysone.v2.v8_json_retention_v10 import prompt


def test_fixed_prompt_two_traces_and_non_ok_repeat_coverage():
    spec,jobs=prepare(lambda text:[1]*129)
    assert len(jobs)==spec['maximum_inferences']==20
    primary=[j for j in jobs if j['suite']=='primary']
    assert Counter(j['expected'][0] for j in primary)=={'ok':6,'missing':4,'error':6}
    assert Counter(j['entity'] for j in primary)=={'A':8,'B':8}
    index={j['id']:j for j in primary}
    for j in jobs:
        assert j['prompt']==prompt(j['state'],j['entity'],'status-copy')
        if j['suite']=='repeat':assert j['prompt']==index[j['repeat_of']]['prompt']
    assert not spec['full_sweep_started'] and not spec['closed_loop_included']


def test_independent_trace_replay_and_wrong_answers_never_rewrite_state():
    spec,jobs=prepare(lambda text:[1]*129);frozen=copy.deepcopy(jobs)
    for c in spec['cases']:
        state=copy.deepcopy(c['initial'])
        chain=[r for r in jobs if r['case_id']==c['id'] and r['suite']=='primary']
        for step,row in zip(c['steps'],chain):
            event=step['observation']
            if event:
                e=event['entity']
                if event['status']=='ok':state[e][0]=event['count']
                state[e][1]=event['status']
            e=step['entity'];assert row['state']==state and row['expected']==[state[e][1],e,state[e][0]]
    def infer(job):
        assert set(job)=={'id','prompt','prompt_ids','output_tokens'}
        return dict(generated_text=json.dumps(['ok','A',9999]),terminal_eos=True)
    for row in jobs:execute(row,infer)
    assert jobs==frozen


def test_cpu_file_framing_preserves_frozen_chat_prefix_after_cli_one_lf_removal():
    _,jobs=prepare(lambda text:[1]*129)
    for job in jobs:
        framed=cpu_prompt_file_bytes(job['prompt'])
        assert framed.endswith(b'\n\n\n')
        assert framed[:-1].decode('utf-8')==job['prompt']
