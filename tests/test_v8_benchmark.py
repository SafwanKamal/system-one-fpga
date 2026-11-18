import json
import pytest
from sysone.v2.v8_benchmark import (encode_record, parse_record, complete_record, chains,
    reduce_observed, transition, prepare_manifest, chain_prompt, state_record)


@pytest.mark.parametrize('wire', ['A', 'E'])
def test_codec_is_lossless_and_rejects_bad_records(wire):
    for status in ('ok', 'missing', 'error'):
        for entity in ('A', 'B'):
            for value in (-9999, -1, 0, 9999):
                record = status, entity, value
                assert parse_record(encode_record(record, wire), wire) == record
    invalid = ['["ok","A",true]', '["ok","A",1.0]', '["ok","A",1,2]', '["bad","A",1]',
               '3 A 1\n', '0 A 1', '0 A 01\n', '0 A 1\njunk', '0 C 1\n']
    for value in invalid:
        with pytest.raises(ValueError): parse_record(value, wire)
    assert complete_record(b'\xff', wire) is None


def test_observed_reducer_does_not_inject_gold_or_repair_mistakes():
    initial = {'A': [10, 'ok'], 'B': [20, 'ok']}
    step = dict(entity='A', op='add', number=3)
    assert transition(initial, step) == ('ok', 'A', 13)
    assert reduce_observed(initial, ('ok', 'A', 99))['A'] == [99, 'ok']
    assert reduce_observed(initial, None) == initial
    assert initial['A'] == [10, 'ok']


def test_state_encodings_preserve_values_status_and_units():
    state = {'A': [-1, 'missing'], 'B': [20, 'error']}
    assert json.loads(state_record(state, 'J'))['A'] == dict(value=-1, status='missing', unit='count')
    assert state_record(state, 'C') == 'A=-1/1 B=20/2'
    for context in ('J', 'C'):
        prompt, _ = chain_prompt(chains('heldout', 1)[0], 1, state, context, 'A', [('assistant', 'SECRET_HISTORY')])
        assert 'SECRET_HISTORY' not in prompt


def test_manifest_is_deterministic_balanced_and_split_disjoint():
    manifest = prepare_manifest()
    assert manifest == prepare_manifest()
    assert len(manifest['fixed']) == 360
    assert len(manifest['historical']) == 30
    assert len(manifest['application']) == 100
    assert len(manifest['chains']) == 12*6+24*6
    ids = [row['id'] for key in ('fixed', 'historical', 'application', 'chains') for row in manifest[key]]
    assert len(set(ids)) == len(ids)
    assert all(row['input_tokens']+row['output_tokens'] <= 256 for row in manifest['fixed'])
    assert chains('development', 1)[0]['initial'] != chains('heldout', 1)[0]['initial']


def load_runner():
    import importlib.util
    from pathlib import Path
    spec=importlib.util.spec_from_file_location('v8_runner',Path(__file__).parents[1]/'scripts/v2/run_v8_benchmark.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class FakeEngine:
    context=256
    prefill_batch_size=8
    manifest={'eos_ids':[99]}
    commands=0;layers=0;head_rows=0;layer_weight_passes=0
    def __init__(self): self.starts=[];self.prefills=[];self.steps=[]
    def begin_prefix(self, ids, enabled):
        assert not enabled
        self.starts.append(ids);self.prefills=[];self.steps=[]
    def prefill_batch(self, group, pos, logits):
        self.prefills.append((pos,len(group)));self.commands+=1
        return 1
    def step(self, token, pos, logits):
        self.steps.append(pos);self.commands+=1
        return 1


class FakeVocab:
    def piece(self, token): return b'x'
    def encode_text(self, text): return [1]*10


def test_inference_counts_first_token_under_prefill_and_resets_each_request():
    runner=load_runner();session=runner.Session.__new__(runner.Session)
    session.engine=FakeEngine();session.vocab=FakeVocab()
    row=session.infer(dict(id='one',prompt_ids=[1]*10,output_tokens=4))
    assert session.engine.prefills==[(0,8),(8,2)]
    assert session.engine.steps==[10,11,12]
    assert row['output_tokens']==4 and row['subsequent_decode_steps']==3
    assert len(row['per_token_seconds'])==3
    session.infer(dict(id='two',prompt_ids=[1]*3,output_tokens=1))
    assert session.engine.prefills==[(0,3)] and not session.engine.steps
    assert len(session.engine.starts)==2


def test_context_overflow_never_issues_hardware_commands():
    runner=load_runner();session=runner.Session.__new__(runner.Session)
    session.engine=FakeEngine();session.vocab=FakeVocab()
    row=session.infer(dict(id='overflow',prompt_ids=[1]*240,output_tokens=24))
    assert row['status']=='context_exhausted'
    assert session.engine.commands==0 and not session.engine.starts


def test_summary_keeps_failures_in_chain_survival_denominator():
    runner=load_runner()
    rows=[dict(id='a',suite='chain',mode='resident',split='heldout',context='H',wire='A',
               chain_id='one',step=1,correct=True,status='completed',request_seconds=1),
          dict(id='b',suite='chain',mode='resident',split='heldout',context='H',wire='A',
               chain_id='one',step=2,correct=False,status='context_exhausted')]
    result=runner.summarize(rows)
    assert result['chain_survival']['heldout/H/A']['2']['correct_through_k']==0
    assert result['total_recorded']==2
