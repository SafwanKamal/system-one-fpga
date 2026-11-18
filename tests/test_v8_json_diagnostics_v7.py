import copy
import json
import pytest
from sysone.v2.v8_json_diagnostics_v7 import (manifest,reference,admission,classify,campaign,make_prompt,audit_v6)
from sysone.v2.v8_benchmark import transition


@pytest.mark.parametrize('count,result',[(49,52),(50,53),(51,48),(-2,1)])
def test_conditional_boundary_independent_reference(count,result):
    state={'A':[count,'error'],'B':[117,'ok']}
    step=dict(entity='A',op='conditional',number=3)
    assert reference(state,step)==['ok','A',result]==list(transition(state,step))


def test_admission_cannot_repair_or_check_arithmetic():
    state={'A':[90,'ok'],'B':[60,'ok']};step=dict(entity='A',op='add',number=3)
    assert admission(state,step,['ok','A',999])==(True,None)
    assert admission(state,step,['ok','B',93])==(False,'wrong-target')
    step['op']='missing'
    assert admission(state,step,['missing','A',999])==(False,'preserve-count-contract')
    assert admission(state,step,['ok','A',90])==(True,None) # wrong status remains measurable
    assert state['A'][0]==90


def test_attribution_separates_drift_new_errors_and_unparseable():
    assert classify(['ok','A',3],['ok','A',3],['ok','A',4],True)=='inherited-only'
    assert classify(['ok','A',5],['ok','A',3],['ok','A',4],True)=='new-local-error-with-drift'
    assert classify(None,['ok','A',3],['ok','A',4],False)=='extraction-budget'


def test_development_campaign_keeps_oracles_out_of_model_and_propagates_errors():
    spec=manifest();seen=[]
    def infer(job):
        assert set(job)=={'id','prompt','prompt_ids','output_tokens'}
        seen.append(job)
        return dict(generated_text='["ok","A",999]',terminal_eos=True)
    rows=campaign(spec,lambda t:[1]*100,infer,lambda r:None)
    assert len(rows)==spec['maximum_inferences']==88
    chain=[r for r in rows if r['suite']=='chain' and r['case_id']=='dev-chain-1' and r['policy']=='clarified']
    assert chain[1]['state_before']['A'][0]==999
    controls=[r for r in rows if r['suite']=='snapshot' and r['step']==2]
    assert all(r['state_before']['A'][0]!=999 for r in controls)
    assert spec['split']=='development-only'
    assert all(c['id'].startswith('dev-') for c in spec['cases']+spec['probes'])


def test_snapshot_and_trajectory_share_template_without_answer_leakage():
    spec=manifest();c=spec['cases'][0];state=copy.deepcopy(c['initial'])
    text=make_prompt(state,c['steps'][1],'clarified')
    assert 'ONE result' in text and 'If count <= 50' in text
    assert str(reference(state,c['steps'][1])[2]) not in text


def test_reference_rejects_unknown_operation():
    with pytest.raises(ValueError):reference({'A':[1,'ok']},dict(entity='A',op='oops',number=1))


def test_primitive_copy_is_never_an_accidental_noop():
    for c in manifest()['probes']:
        step=c['steps'][0];e=step['entity'];other='B' if e=='A' else 'A'
        assert c['initial'][e][0]!=c['initial'][other][0]
        if step['op']=='copy':assert reference(c['initial'],step)[2]!=c['initial'][e][0]
