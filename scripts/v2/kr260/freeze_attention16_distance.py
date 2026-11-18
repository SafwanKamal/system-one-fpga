"""Freeze the production attention-width/distance profile after numerical and inference evidence."""
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return re.findall(r'case (\d+):\s+(\d+) tokens, status (\d+), stopped at (\d+), (\d+) mismatching words; clocks: encoder (\d+), request (\d+)', path.read_text())


def main():
    tested = ROOT / 'build/v2/rtl-attention16-distance-parameter-check'
    assert json.loads((tested / 'completion-status.json').read_text()) == {'exit_code': 0, 'complete': True}
    prototype = ROOT / 'build/v2/rtl-attention16-check'
    proof = json.loads((prototype / 'review.json').read_text())
    assert proof['complete'] and proof['all_outputs_bit_exact'] and proof['numerical_cases'] == 32 and proof['partial_cases'] == 6
    base = json.loads((ROOT / 'build/v2/kr260-opt-source-row-bram-large/regression.json').read_text())
    directories = {'wide': 'build/v2/rtl-wide-check/vectors', 'l12': 'simulation/v2/vectors/kr260',
                   'one-word': 'build/v2/rtl-batch3-check/one-word-vectors',
                   'boundary': 'build/v2/rtl-batch-check/boundary-vectors',
                   'h1024': 'build/v2/kr260-dot7-h1024-eight-vectors'}
    checks = {}
    cycle_changes = []
    fresh_l12 = ROOT / 'build/v2/attention16-l12-cycle-reference'
    assert json.loads((fresh_l12 / 'completion-status.json').read_text()) == {'exit_code': 0, 'complete': True}
    for name, expected in base['checks'].items():
        log = tested / f'{name}.log'
        actual = rows(log)
        assert len(actual) == len(expected['tokens'])
        reference = fresh_l12 / log.name if name == 'l12' else prototype / log.name
        assert actual == rows(reference), f'Production parameter alignment changed: {name}'
        assert all(row[2] == '0' and row[4] == '0' for row in actual)
        assert 'FEATURES 535affff' in log.read_text()
        for filename, digest in expected['vectors_sha256'].items():
            assert sha(ROOT / directories[name] / filename) == digest
        checks[name] = {'log_sha256': sha(log), 'tokens': [int(row[1]) for row in actual],
                        'encoder_clocks': [int(row[5]) for row in actual],
                        'request_clocks': [int(row[6]) for row in actual],
                        'prototype_cycles_identical': True,
                        'vectors_sha256': expected['vectors_sha256']}
        old = rows(ROOT / 'build/v2/rtl-source-row-bram-parameter-check' / log.name)
        changes = [100*(int(row[5])/int(before[5])-1) for row,before in zip(actual,old)]
        checks[name]['encoder_cycle_change_vs_32query_percent'] = changes
        cycle_changes += changes
    pattern = r'case (\d+):\s+(\d+) tokens, (\d+) mismatching words; clocks per instruction ([0-9 ]+); whole layer (\d+)'
    default = re.findall(pattern, (tested / 'nexys-default.log').read_text())
    assert len(default) == 2 and default == re.findall(pattern, (prototype / 'nexys-default.log').read_text())
    partial = rows(tested / 'partial.log')
    assert len(partial) == 6 and partial == rows(prototype / 'partial.log')
    assert all(row[2] == '0' and row[4] == '0' for row in partial)
    embed = ROOT / 'build/v2/embed-controls-integrated'
    assert json.loads((embed / 'completion-status.json').read_text()) == {'complete': True, 'exit_code': 0}
    assert 'PASS embed controls: 4097 profiles,262096 writes' in (embed / 'result.log').read_text()
    embed_hashes = {name: digest for digest, name in
                    (line.split(maxsplit=1) for line in (embed / 'source-sha256.txt').read_text().splitlines())}
    assert embed_hashes['embed_engine.sv'] == sha(ROOT / 'rtl/v2/encoder/embed_engine.sv')
    for name in ('probability-input-ooc', 'embed-controls-ooc'):
        evidence = json.loads((ROOT / f'build/v2/{name}/summary.json').read_text())
        assert evidence['complete'] and evidence['estimated_slack_gain_ns'] > 0
        for path, digest in evidence['source_sha256'].items():
            assert sha(ROOT / path) == digest, f'Isolated proof source changed: {path}'
    for name in ('linear-source-row-ooc', 'linear-accumulator-ooc'):
        evidence = json.loads((ROOT / f'build/v2/{name}/summary.json').read_text())
        assert evidence['complete'], name
        for path, digest in evidence['source_sha256'].items():
            assert sha(ROOT / path) == digest, path
        if name == 'linear-accumulator-ooc':
            assert evidence['read_first'] and evidence['output_register_extra_latency'] == 0
            assert evidence['resources_new']['BRAM'] == 29
        else:
            assert evidence['estimated_slack_gain_ns'] > 0 and evidence['resources_new']['DSP'] == 0
    core = json.loads((ROOT / 'build/v2/attention16-distance-ooc/summary.json').read_text())
    assert core['complete'] and core['lut_reduction'] > 10000
    assert core['results'][1]['external_distance_ff'] == 352 and core['results'][1]['distance_dsps'] == 16
    for path, digest in core['source_sha256'].items():
        assert sha(ROOT / path) == digest, path
    head32 = rows(tested / 'head32.log')
    assert len(head32) == 4 and head32 == rows(ROOT / 'build/v2/attention16-head-groups/attention16.log')
    assert all(row[2] == '0' and row[4] == '0' for row in head32)
    group_dir = ROOT / 'build/v2/attention16-head32-vectors'
    group_hashes = {path.name: sha(path) for path in group_dir.iterdir() if path.is_file()}
    assert json.loads((group_dir / 'manifest.json').read_text())['reference_verified'] is True
    # Only the new kernel's descriptive comments differ from its proven prototype.
    def logic(path):
        return re.sub(r'\s+', '', re.sub(r'//[^\n]*', '', path.read_text()))
    assert logic(ROOT / 'rtl/v2/common/attention_probability_input.sv') == logic(ROOT / 'build/v2/probability-input-cut/engine-sources/attention_probability_input.sv')
    digests = {name: digest for digest, name in
               (line.split(maxsplit=1) for line in (tested / 'source-sha256.txt').read_text().splitlines())}
    sources = list(base['rtl_sha256'])
    assert len(sources) == len(set(sources)) == 22
    for name in sources:
        assert sha(ROOT / name) == digests[name], f'Edit under production test: {name}'
    output = ROOT / 'build/v2/kr260-opt-attention16-distance-large'
    assert not output.exists(), 'Preserve existing frozen candidate'
    if sys.argv[1:] == ['--validate-only']:
        print('PASS: production36 KR260+sixpartial, fresh twoNexys, prototype cycles,22sources,component/source/fixture gates')
        return
    assert not sys.argv[1:], 'Unknown freeze option'
    for name in sources:
        target = output / 'rtl-snapshot' / name.removeprefix('rtl/v2/')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    profile = {**base['profile'], 'attention_lanes': 16, 'fabric_score_distance': 1}
    result = {'candidate': 'attention16-distance-large', 'target_mhz': 200, 'read_latency': 5,
              'profile': profile, 'capability_word': '0x535affff', 'numerical_cases': 32,
              'checks': checks, 'partial_tile_cases': 6, 'partial_tile_cycles_unchanged': True,
              'nexys_default_cycles_unchanged': True,
              'query_group_cases': 4, 'query_group_vectors_sha256': group_hashes,
              'encoder_cycle_change_vs_32query_range_percent': [min(cycle_changes),max(cycle_changes)],
              'l12_cycle_reference_sha256': sha(fresh_l12 / 'l12.log'),
              'cycle_comparison_scope': 'identical to16queryprototype; scheduling tradeoff versus32querybaseline',
              'rtl_sha256': {name: digests[name] for name in sources},
              'routed': False, 'hardware_qualified': False}
    (output / 'regression.json').write_text(json.dumps(result, indent=2) + '\n')
    (output / 'completion-status.json').write_text(json.dumps({'state': 'numerical_ready', 'updated_utc': datetime.now(timezone.utc).isoformat()}, indent=2) + '\n')
    print('PASS: 32 production cases equal prototype, two Nexys defaults, six partial tiles; 22 sources frozen')


if __name__ == '__main__':
    main()
