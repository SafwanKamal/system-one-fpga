import json
import pytest
from sysone.v2.v8_benchmark_protocol_v4 import (CANDIDATES,cases,prompt,render_state,
    decode_compact,parse_output,qualification_manifest,evaluate,response_prefix)


def signature(case):return json.dumps([case['state'],case['step']],sort_keys=True)


def test_new_cases_do_not_overlap_previous_development_or_qualification():
    from sysone.v2.v8_benchmark_protocol_v2 import cases as v2
    from sysone.v2.v8_benchmark_protocol_v3 import cases as v3
    old={signature(c) for source in (v2,v3) for split in ('development','qualification') for c in source(split)}
    dev={signature(c) for c in cases('development')};qual={signature(c) for c in cases('qualification')}
    assert not dev & qual and not (dev|qual) & old


@pytest.mark.parametrize('split',['development','qualification'])
def test_conditionals_cross_targets_branches_and_threshold_boundary(split):
    cs=[c for c in cases(split) if c['step']['op']=='conditional']
    for entity in 'AB':
        values=[c['state'][entity][0] for c in cs if c['step']['entity']==entity]
        assert any(x<50 for x in values) and any(x>51 for x in values)
        assert 50 in values and 51 in values
    assert len(cases(split))==28


@pytest.mark.parametrize('variant',CANDIDATES)
def test_only_compact_string_records_and_no_answer_computation_in_actual_prompt(variant):
    state={'A':[37,'missing'],'B':[81,'error']}
    step=dict(entity='A',op='conditional',number=9)
    text,user=prompt(state,step,'C','A',variant)
    assert render_state(state,variant) in user
    assert '46' not in text
    assert decode_compact(render_state(state,variant),'named-line' if variant=='two-named' else 'tuple-array')==state
    assert parse_output('["ok","A",46]','A',candidate=variant)==('ok','A',46)
    for bad in ('[0,"A",46]','["ok","A",true]','```json\n["ok","A",46]\n```'):
        with pytest.raises(ValueError):parse_output(bad,'A',candidate=variant)


def test_conditional_failure_cannot_hide_behind_other_operation_scores():
    rows=[dict(id=c['id'],case_id=c['id'],format_valid=True,correct=c['step']['op']!='conditional')
          for c in cases('qualification')]
    gates=qualification_manifest(CANDIDATES[0])['gates']
    gates=dict(gates,per_arm_min_semantic_correct=20)
    _,operations,passed=evaluate(rows,gates)
    assert operations['conditional']==dict(cases=8,correct=0)
    assert passed is False


def test_prefill_contains_only_known_metadata_and_waits_for_complete_count():
    import importlib.util,sys
    from pathlib import Path
    for variant in CANDIDATES:
        step=dict(entity='B',op='conditional',number=9)
        assert response_prefix(step,variant)==('["ok","B",' if variant.startswith('prefilled') else '')
        text,_=prompt({'A':[18,'ok'],'B':[51,'error']},step,'C','A',variant)
        if variant.startswith('prefilled'):assert text.endswith('["ok","B",')
        assert '42' not in text
    root=Path(__file__).parents[1];sys.path.insert(0,str(root/'scripts/v2'))
    spec=importlib.util.spec_from_file_location('v4_fpga',root/'scripts/v2/qualify_v8_protocol_v4_fpga.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    class Engine:
        context=256;prefill_batch_size=8;manifest={'eos_ids':[99]}
        def __init__(self):self.calls=[]
        def begin_prefix(self,ids,enabled):assert enabled is False
        def prefill_batch(self,group,pos,logits):return 1
        def step(self,token,position,logits):self.calls.append(position);return 2
    class Vocab:
        def encode_text(self,prompt):return [3]*8
        def piece(self,token):return {1:b'4',2:b'2]'}[token]
    class Session:pass
    s=Session();s.engine=Engine();s.vocab=Vocab()
    row=m.infer(s,dict(id='test',case_id='test',prompt='test',prompt_ids=[3]*8,
        context='C',wire='A',candidate='prefilled-contrastive',expected=['ok','B',42],response_prefix='["ok","B",'))
    assert row['correct'] and row['generated_suffix_text']=='42]' and row['generated_ids']==[1,2]
    assert s.engine.calls==[8]
