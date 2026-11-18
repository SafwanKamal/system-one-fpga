import json
from sysone.v2.v8_benchmark_protocol_v2 import cases,prompt,qualification_manifest,parse_output


def test_missing_and_error_preserve_real_values_and_change_only_status():
    for case in cases('qualification'):
        op=case['step']['op'];entity=case['step']['entity']
        if op in ('missing','error'):
            assert case['expected']==[op,entity,case['state'][entity][0]]


def test_prompts_use_same_state_across_contexts_and_no_answer_substitution():
    case=cases('development')[0]
    for context in ('H','J','C'):
        text,user=prompt(case['state'],case['step'],context,'A','plain')
        assert str(case['state']['A'][0]) in text and str(case['state']['B'][0]) in text
        assert 'Set counter' in user
        assert '0 A 12' not in text


def test_frozen_manifest_gates_apply_to_each_arm_not_aggregate():
    manifest=qualification_manifest('demonstration')
    assert len(manifest['cases'])==12 and len(manifest['arms'])==6
    assert manifest['gates']['per_arm_min_format_valid']==11
    assert manifest['gates']['per_arm_min_semantic_correct']==9
    development=json.dumps(cases('development'),sort_keys=True)
    qualification=json.dumps(cases('qualification'),sort_keys=True)
    assert development!=qualification


def test_json_remains_strict_and_enum_waits_for_a_real_boundary():
    assert parse_output('["ok","A",33]','A')==('ok','A',33)
    assert parse_output('0 A 33','E',terminal=True)==('ok','A',33)
    import pytest
    with pytest.raises(ValueError):parse_output('0 A 3','E')
    with pytest.raises(ValueError):parse_output('status: ok, entity: A, value: 33','A',terminal=True)


def test_fpga_stream_does_not_truncate_a_number_before_eos():
    import importlib.util,sys
    from pathlib import Path
    root=Path(__file__).parents[1]
    sys.path.insert(0,str(root/'scripts/v2'))
    spec=importlib.util.spec_from_file_location('qualification_fpga',root/'scripts/v2/qualify_v8_protocol_fpga.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    class Engine:
        context=256;prefill_batch_size=8;manifest={'eos_ids':[99]}
        def __init__(self):self.calls=[];self.next=iter([2,99])
        def begin_prefix(self,ids,enabled):assert enabled is False
        def prefill_batch(self,group,pos,logits):return 1
        def step(self,token,position,logits):self.calls.append(position);return next(self.next)
    class Vocab:
        def encode_text(self,prompt):return [3]*8
        def piece(self,token):return {1:b'0 A 4',2:b'2',99:b''}[token]
    class Session:pass
    s=Session();s.engine=Engine();s.vocab=Vocab()
    result=module.infer(s,dict(id='test',case_id='test',prompt='test',prompt_ids=[3]*8,
                             wire='E',context='J',expected=['ok','A',42]))
    assert result['correct'] and result['observed']==['ok','A',42]
    assert s.engine.calls==[8,9] and result['terminal_eos']
