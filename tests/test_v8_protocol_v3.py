import json
import pytest
from sysone.v2.v8_benchmark_protocol_v3 import (CANDIDATES,encode_output,parse_output,
    render_state,decode_compact,cases,prompt,demonstrations,qualification_manifest)


@pytest.mark.parametrize('candidate',CANDIDATES)
def test_states_lossless_and_examples_use_evaluated_representation(candidate):
    for state in ({'A':[-3,'missing'],'B':[92,'error']},{'A':[16,'ok'],'B':[84,'ok']}):
        assert decode_compact(render_state(state,'C',candidate),candidate)==state
    c=cases('development')[0];text,_=prompt(c['state'],c['step'],'C','A',candidate)
    initial,_=demonstrations(c['step']['op'])[0]
    assert render_state(initial,'C',candidate) in text
    assert 'count/statusDigit' not in text


@pytest.mark.parametrize('candidate',CANDIDATES)
@pytest.mark.parametrize('wire',['A','E'])
def test_output_semantics_roundtrip_and_reject_repair(candidate,wire):
    for status in ('ok','missing','error'):
        record=status,'B',67
        assert parse_output(encode_output(record,wire,candidate),wire,terminal=True,candidate=candidate)==record
    for bad in ('[true,"A",3]','[3,"A",3]','[0,"A",true]','0 missing A 3','[0,"Z",3]'):
        with pytest.raises(ValueError):parse_output(bad,wire,terminal=True,candidate=candidate)


def test_splits_are_new_and_demos_do_not_depend_on_test_values():
    dev=cases('development');qual=cases('qualification')
    signature=lambda c:json.dumps([c['state'],c['step']],sort_keys=True)
    assert not set(map(signature,dev)) & set(map(signature,qual))
    from sysone.v2.v8_benchmark_protocol_v2 import cases as old
    previous={signature(c) for split in ('development','qualification') for c in old(split)}
    assert not previous & set(map(signature,dev+qual))
    assert demonstrations('conditional')==demonstrations('conditional')
    for candidate in CANDIDATES:
        assert qualification_manifest(candidate)['full_sweep_must_remain_stopped']


def test_fpga_numeric_array_waits_for_closing_bracket():
    import importlib.util,sys
    from pathlib import Path
    root=Path(__file__).parents[1];sys.path.insert(0,str(root/'scripts/v2'))
    spec=importlib.util.spec_from_file_location('v3_fpga',root/'scripts/v2/qualify_v8_protocol_v3_fpga.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    class Engine:
        context=256;prefill_batch_size=8;manifest={'eos_ids':[99]}
        def __init__(self):self.calls=[]
        def begin_prefix(self,ids,enabled):assert enabled is False
        def prefill_batch(self,group,pos,logits):return 1
        def step(self,token,position,logits):self.calls.append(position);return 2
    class Vocab:
        def encode_text(self,prompt):return [3]*8
        def piece(self,token):return {1:b'[0,"A",4',2:b'2]'}[token]
    class Session:pass
    s=Session();s.engine=Engine();s.vocab=Vocab()
    row=module.infer(s,dict(id='test',case_id='test',prompt='test',prompt_ids=[3]*8,
        context='C',wire='E',candidate='named-array',expected=['ok','A',42]))
    assert row['correct'] and s.engine.calls==[8]
