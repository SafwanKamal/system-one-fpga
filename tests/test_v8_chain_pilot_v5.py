import json
import pytest
from sysone.v2.v8_chain_pilot_v5 import normalize,manifest,campaign,summarize
from sysone.v2.v8_benchmark import transition,reduce_observed


@pytest.mark.parametrize('text,route',[
    (' ["ok","A",35] ','array'),
    ('```json\n["ok","A",35]\n```','fence'),
    ('{"status":"OK","target":"a","value":"35"}','object+integer-string'),
    ('ok A 35','text'),
    ('status=ok;entity=A;count=35','text')])
def test_predeclared_equivalent_formats(text,route):
    r=normalize(text,terminal=True)
    assert r['record']==['ok','A',35] and r['route']==route


@pytest.mark.parametrize('text',[
    '["ok","A",true]','["ok","A",35.0]','["ok","A",35] ["ok","A",36]',
    '{"status":"ok","entity":"A","count":35,"value":36}',
    '{"status":"ok","entity":"A","count":35,"count":36}',
    'The answer is ["ok","A",35].','```json\n["ok","A",35]',
    '{"status":"ok","count":35}','["success","A",35]'])
def test_ambiguous_unknown_or_partial_answers_are_not_repaired(text):
    with pytest.raises(ValueError):normalize(text,terminal=True)


def test_plain_number_requires_actual_terminal_boundary():
    with pytest.raises(ValueError):normalize('ok A 3',terminal=False)
    assert normalize('ok A 35',terminal=True)['record'][2]==35
    assert normalize('["ok","A",3]',terminal=False)['record'][2]==3


def responses(spec):
    result={}
    for chain in spec['chains']:
        state=chain['initial']
        for i,step in enumerate(chain['steps'],1):
            row=list(transition(state,step));state=reduce_observed(state,row)
            for ident in [f'control-{chain["id"]}-{i:02d}']+[f'chain-{chain["id"]}-{arm}-{i:02d}' for arm in ('H','C')]:
                result[ident]=row
    return result


def test_wrong_proposals_propagate_controls_never_correct_rolling_state_and_recovery_is_measured():
    spec=manifest();answer=responses(spec)
    answer['chain-simple-C-01']=['ok','A',99]
    answer['chain-simple-C-02']=['ok','B',99]
    answer['chain-simple-C-03']=['missing','B',99]
    answer['chain-simple-C-04']=['error','A',99]
    def infer(job):
        assert 'expected' not in job and 'local_expected' not in job
        return dict(generated_text=json.dumps(answer[job['id']]),terminal_eos=True,seconds=1)
    rows=campaign(spec,lambda text:[0]*10,infer,lambda r:None)
    lookup={r['id']:r for r in rows};r=lookup['chain-simple-C-02']
    assert r['state_before']['A'][0]==99 and r['expected']==['ok','B',43]
    assert r['local_correct'] and not r['correct']
    assert 'State A:99,ok;' in r['prompt'] and '99' not in lookup['control-simple-02']['prompt']
    s=summarize(rows)['chains']['simple/C']
    assert s['first_semantic_failure']==1 and s['consecutive_correct_steps']==0
    assert s['exact_state_recovery_steps']==[6]
    assert len(rows)==48


def test_full_history_keeps_raw_replies_and_context_stops_are_censored():
    spec=manifest();answer=responses(spec);seen=[]
    def infer(job):
        seen.append(job['id'])
        return dict(generated_text='```json\n'+json.dumps(answer[job['id']])+'\n```',terminal_eos=True,seconds=1)
    def encode(text):return [0]*(500 if text.count('<|im_start|>assistant')>=3 else 10)
    rows=campaign(spec,encode,infer,lambda r:None);lookup={r['id']:r for r in rows}
    stopped=lookup['chain-simple-H-03']
    assert stopped['status']=='context_exhausted' and stopped['correct'] is None
    assert 'chain-simple-H-03' not in seen and '```json' in stopped['prompt']
    assert lookup['chain-simple-C-08']['correct']
    s=summarize(rows)['chains']['simple/H']
    assert s['survival']['4'] is None and s['first_semantic_failure'] is None


def test_new_initial_states_do_not_repeat_previous_qualified_tasks():
    from sysone.v2.v8_benchmark_protocol_v2 import cases as v2
    from sysone.v2.v8_benchmark_protocol_v3 import cases as v3
    from sysone.v2.v8_benchmark_protocol_v4 import cases as v4
    sig=lambda s,t:json.dumps([s,t],sort_keys=True)
    previous={sig(c['state'],c['step']) for source in (v2,v3,v4)
              for split in ('development','qualification') for c in source(split)}
    for chain in manifest()['chains']:
        state=chain['initial']
        for step in chain['steps']:
            assert sig(state,step) not in previous
            state=reduce_observed(state,transition(state,step))


def test_capacity_does_not_hide_a_known_prior_failure():
    rows=[]
    for step,correct in [(1,True),(2,False),(3,None)]:
        rows.append(dict(id=str(step),suite='dependent',chain_id='test',arm='H',family='arithmetic',
            status='completed' if correct is not None else 'context_exhausted',step=step,
            correct=correct,accepted=True,native_format=True,local_correct=correct,state_exact=correct,input_tokens=100))
    s=summarize(rows)['chains']['test/H']
    assert s['first_semantic_failure']==2 and s['context_exhausted_at']==3
    assert s['survival']['8'] is False


def test_complete_fpga_response_is_consumed_before_normalization():
    import importlib.util,sys
    from pathlib import Path
    root=Path(__file__).parents[1];sys.path.insert(0,str(root/'scripts/v2'))
    spec=importlib.util.spec_from_file_location('v5_runner',root/'scripts/v2/run_v8_chain_pilot_v5.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    class Engine:
        context=256;prefill_batch_size=8;manifest={'eos_ids':[99]}
        def begin_prefix(self,ids,enabled):assert enabled is False
        def prefill_batch(self,group,pos,logits):return 1
        def step(self,token,position,logits):return {1:2,2:99}[token]
    class Vocab:
        def encode_text(self,text):return [3]*8
        def piece(self,token):return {1:b'["ok","A",35]',2:b' ["ok","A",36]',99:b''}[token]
    class Session:pass
    backend=m.FPGA.__new__(m.FPGA);backend.session=Session();backend.session.engine=Engine()
    backend.session.vocab=backend.vocab=Vocab()
    output=backend.infer(dict(prompt='test',prompt_ids=[3]*8,output_tokens=48))
    assert output['generated_ids']==[1,2,99] and output['terminal_eos']
    with pytest.raises(ValueError):normalize(output['generated_text'],terminal=True)
