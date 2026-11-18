import pytest
import hashlib
import json
from scripts.v2.kr260.package_app import frontier_profile, capture_fixture

def test_shared_read_candidate_preserves_all_other_pipeline_requirements():
    old=frontier_profile('dot5-large');new=frontier_profile('dot7-large')
    assert old['local_accumulator_controls']==1 and new['local_accumulator_controls']==3
    assert new['max_hidden']==1024 and new['pipelined_uram']==1 and new['pipelined_dot']==1
    assert {k:v for k,v in old.items() if k!='local_accumulator_controls'}=={
        k:v for k,v in new.items() if k!='local_accumulator_controls'}
    with pytest.raises(ValueError):frontier_profile('dot6')


def test_capture_adds_only_local_memory_cut_to_dot7_profile():
    previous=frontier_profile('dot7-large')
    capture=frontier_profile('capture-large')
    assert capture.pop('local_read_capture') == 1
    assert capture == previous


def test_grouped_flags_adds_only_fifo_status_cut_to_capture():
    previous=frontier_profile('capture-large')
    grouped=frontier_profile('capture-flags-large')
    assert grouped.pop('registered_fifo_flags') == 1
    assert grouped == previous


def test_capture_fixture_requires_all_frozen_case_bytes(tmp_path):
    vectors=tmp_path/'build/v2/kr260-dot7-h1024-eight-vectors'
    vectors.mkdir(parents=True)
    manifest={'reference_verified':True,'dims':{'hidden':1024,'ffn':4096},
              'token_lengths':[1,2,3,4,5,12,64,128]}
    (vectors/'manifest.json').write_text(json.dumps(manifest))
    (vectors/'image.hex').write_text('00'*16+'\n')
    (vectors/'cases.txt').write_text('8\n')
    for i in range(8): (vectors/f'case_{i}.txt').write_text(str(i)+'\n')
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in vectors.iterdir()}
    checks={'checks':{'h1024':{'vectors_sha256':hashes}}}
    assert capture_fixture(checks,tmp_path) == (vectors,manifest)
    (vectors/'case_7.txt').write_text('tampered\n')
    with pytest.raises(SystemExit,match='differs from regression'):
        capture_fixture(checks,tmp_path)
    hashes.pop('case_7.txt')
    with pytest.raises(SystemExit,match='Incomplete frozen'):
        capture_fixture(checks,tmp_path)


def test_new_pipeline_profile_requires_both_arithmetic_cuts():
    old=frontier_profile('capture-flags-large');new=frontier_profile('pipeline-cuts-large')
    assert new.pop('probability_pipeline')==1
    assert new.pop('pipelined_drain_select')==1
    assert new==old


def test_operand_package_profile_requires_both_new_cuts():
    old = frontier_profile('pipeline-cuts-large')
    new = frontier_profile('operand-capture-large')
    assert new.pop('probability_input_capture') == 1
    assert new.pop('local_embed_controls') == 1
    assert new == old


def test_source_row_bram_profile_retains_operand_stages():
    old = frontier_profile('operand-capture-large')
    new = frontier_profile('source-row-bram-large')
    assert new.pop('incremental_source_row') == 1
    assert new.pop('linear_accumulators_in_bram') == 1
    assert new == old


def test_attention_distance_package_fixture_hash_and_scheduling_guard():
    from pathlib import Path
    from scripts.v2.kr260.package_app import attention_distance_evidence
    root=Path(__file__).resolve().parents[1]
    path=root/'build/v2/kr260-opt-attention16-distance-large/regression.json'
    if not path.exists():
        pytest.skip('Frozen regression not available')
    checks=json.loads(path.read_text())
    assert frontier_profile('attention16-distance-large')['attention_lanes']==16
    attention_distance_evidence(checks,root)
    for update in ({'query_group_cases':0},{'capability_word':'0x535a7fff'},
                   {'encoder_cycle_change_vs_32query_range_percent':[0,float('nan')]},
                   {'query_group_vectors_sha256':{}}):
        bad=dict(checks,**update)
        with pytest.raises(SystemExit):
            attention_distance_evidence(bad,root)
    bad=dict(checks,query_group_vectors_sha256=dict(checks['query_group_vectors_sha256'],case_3__txt='bad'))
    bad['query_group_vectors_sha256']['case_3.txt']='bad'
    with pytest.raises(SystemExit,match='differs'):
        attention_distance_evidence(bad,root)


def test_paired_profile_keeps_16query_and_all_earlier_stages():
    new=frontier_profile('request-window-embed-large');old=frontier_profile('attention16-distance-large')
    assert new.pop('cached_request_window')==1 and new.pop('dsp_embed_row_address')==1
    assert new==old


def test_context_profile_retains_paired_stages():
    old=frontier_profile('request-window-embed-large')
    new=frontier_profile('attention-context-capture-large')
    assert new.pop('fabric_context_capture')==1
    assert new==old
