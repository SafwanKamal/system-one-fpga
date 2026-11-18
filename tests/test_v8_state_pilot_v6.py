import copy,json
import pytest
from sysone.v2.v8_state_pilot_v6 import (manifest,make_cases,prompt,campaign,apply_observation,expected,render,summarize,normalize)
from sysone.v2.v8_benchmark import reduce_observed,transition


def fake(spec,overrides=None):
    answers={}
    for c in spec['cases']:
        state=copy.deepcopy(c['initial'])
        for i,step in enumerate(c['steps'],1):
            if c['mode']=='retention':state=apply_observation(state,step['observation'])
            answer=expected(c,state,step)
            for prefix,arms in [('control',('J','C')),('chain',('H','J','C'))]:
                for arm in arms:answers[f'{prefix}-{c["id"]}-{arm}-{i:02d}']=answer
            if c['mode']=='closed-loop':state=reduce_observed(state,answer)
    answers.update(overrides or {})
    def infer(job):
        assert set(job)=={'id','prompt','prompt_ids','output_tokens'}
        return dict(generated_text=json.dumps(answers[job['id']]),terminal_eos=True,seconds=1)
    return infer


def test_fresh_splits_and_closed_loop_tasks_exclude_all_previous_tasks():
    from sysone.v2.v8_benchmark_protocol_v2 import cases as v2
    from sysone.v2.v8_benchmark_protocol_v3 import cases as v3
    from sysone.v2.v8_benchmark_protocol_v4 import cases as v4
    from sysone.v2.v8_chain_pilot_v5 import manifest as v5
    sig=lambda state,step:json.dumps([state,step],sort_keys=True)
    previous={sig(c['state'],c['step']) for fn in (v2,v3,v4) for split in ('development','qualification') for c in fn(split)}
    for c in v5()['chains']:
        state=c['initial']
        for step in c['steps']:
            previous.add(sig(state,step));state=reduce_observed(state,transition(state,step))
    spec=manifest();seen=set()
    for c in spec['cases']:
        state=c['initial']
        for step in c['steps']:
            if c['mode']=='retention':state=apply_observation(state,step['observation'])
            key=sig(state,step);assert key not in seen and key not in previous;seen.add(key)
            if c['mode']=='closed-loop':state=reduce_observed(state,expected(c,state,step))
    assert len(spec['cases'])==4 and spec['maximum_inferences']==160


@pytest.mark.parametrize('text',[
    '[{"name":"A","count":127,"status":"ok"}]',
    '```json\n[{"name":"A","count":"127","status":"OK"}]\n```',
    '{"name":"A","status":"ok","count":127}'])
def test_generic_record_container_and_name_alias_do_not_change_values(text):
    r=normalize(text,terminal=True)
    assert r['record']==['ok','A',127] and not r['native_format']


@pytest.mark.parametrize('text',[
    '[{"name":"A","count":127,"status":"ok"},{"name":"B","count":228,"status":"ok"}]',
    '[{"name":"A","entity":"B","count":127,"status":"ok"}]',
    '[{"name":"A","count":true,"status":"ok"}]',
    '[{"name":"A","count":79-6,"status":"ok"}]',
    '[{"name":"A","count":127,"count":128,"status":"ok"}]'])
def test_extra_container_support_does_not_adjudicate_or_calculate(text):
    with pytest.raises(ValueError):normalize(text,terminal=True)


@pytest.mark.parametrize('arm',['J','C'])
def test_state_arms_ignore_feedback_and_history_for_exact_control_alignment(arm):
    c=make_cases('heldout')[1];state=c['initial']
    a=prompt(c,1,state,arm,history=[('assistant','WRONG')],accepted=False)[0]
    b=prompt(c,1,state,arm)[0]
    assert a==b and 'Previous reply' not in a and 'WRONG' not in a
    assert render(state,arm) in a


def test_missing_observation_preserves_actual_count_and_refresh_replaces_status():
    initial={'A':[137,'ok'],'B':[228,'error']}
    result=apply_observation(initial,dict(entity='A',status='missing'))
    assert result['A']==[137,'missing'] and initial['A']==[137,'ok']
    result=apply_observation(result,dict(entity='A',status='ok',count=141))
    assert result['A']==[141,'ok']
    with pytest.raises(ValueError):apply_observation(initial,dict(entity='A',status='error',count=0))


def test_retention_wrong_answers_never_rewrite_trusted_tool_state():
    spec=manifest();key='chain-development-retention-C-01'
    rows=campaign(spec,lambda text:[0]*10,fake(spec,{key:['error','A',999]}),lambda row:None)
    lookup={r['id']:r for r in rows};first=lookup[key];next_row=lookup['chain-development-retention-C-02']
    assert not first['correct'] and first['state_after']==first['state_before']
    assert next_row['state_before']['A'][0]!=999 and next_row['matches_snapshot_control_input']
    assert next_row['correct']
    assert all(r['matches_snapshot_control_input'] for r in rows
        if r['suite']=='dependent' and r['mode']=='retention' and r['arm'] in ('J','C'))


def test_closed_loop_bad_counts_propagate_with_gold_never_committed():
    spec=manifest();key='chain-development-closed-loop-C-01'
    rows=campaign(spec,lambda text:[0]*10,fake(spec,{key:['ok','A',999]}),lambda row:None)
    lookup={r['id']:r for r in rows};r=lookup['chain-development-closed-loop-C-02']
    assert r['state_before']['A'][0]==999 and '999' in r['prompt']
    assert r['state_matches_snapshot_control'] is False
    assert lookup['control-development-closed-loop-C-02']['state_before']['A'][0]!=999


def test_history_retains_raw_replies_and_tool_events_and_capacity_is_separate():
    spec=manifest()
    def encode(text):return [0]*(400 if text.count('<|im_start|>assistant')>=3 else 10)
    rows=campaign(spec,encode,fake(spec),lambda row:None);lookup={r['id']:r for r in rows}
    r=lookup['chain-development-retention-H-03']
    assert r['status']=='context_exhausted' and r['correct'] is None
    assert 'Tool observation' in r['prompt'] and '"ok"' in r['prompt']
    assert 'Initial state' in r['prompt'] and 'State '+render(r['state_before'],'J') not in r['prompt']
    assert lookup['chain-development-retention-J-08']['correct']
    s=summarize(rows)['chains']['development-retention/H']
    assert s['survival']['8'] is None and s['context_exhausted_at']==3
