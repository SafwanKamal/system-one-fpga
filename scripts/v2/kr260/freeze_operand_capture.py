"""Freeze the production operand profile after numerical and inference evidence."""
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return re.findall(r'case (\d+):\s+(\d+) tokens, status (\d+), stopped at (\d+), (\d+) mismatching words; clocks: encoder (\d+), request (\d+)', path.read_text())


def main():
    tested = ROOT / 'build/v2/rtl-operand-capture-check'
    assert json.loads((tested / 'completion-status.json').read_text()) == {'exit_code': 0, 'complete': True}
    prototype = ROOT / 'build/v2/rtl-input-embed-check'
    assert json.loads((prototype / 'review.json').read_text())['state'] == 'experimental_numerical_ready'
    base = json.loads((ROOT / 'build/v2/kr260-opt-pipeline-cuts-large/regression.json').read_text())
    directories = {'wide': 'build/v2/rtl-wide-check/vectors', 'l12': 'simulation/v2/vectors/kr260',
                   'one-word': 'build/v2/rtl-batch3-check/one-word-vectors',
                   'boundary': 'build/v2/rtl-batch-check/boundary-vectors',
                   'h1024': 'build/v2/kr260-dot7-h1024-eight-vectors'}
    checks = {}
    for name, expected in base['checks'].items():
        log = tested / f'{name}.log'
        actual = rows(log)
        assert len(actual) == len(expected['tokens'])
        assert actual == rows(prototype / log.name), f'Production parameter alignment changed: {name}'
        assert all(row[2] == '0' and row[4] == '0' for row in actual)
        assert 'FEATURES 53591fff' in log.read_text()
        for filename, digest in expected['vectors_sha256'].items():
            assert sha(ROOT / directories[name] / filename) == digest
        checks[name] = {'log_sha256': sha(log), 'tokens': [int(row[1]) for row in actual],
                        'encoder_clocks': [int(row[5]) for row in actual],
                        'request_clocks': [int(row[6]) for row in actual],
                        'prototype_cycles_identical': True,
                        'vectors_sha256': expected['vectors_sha256']}
    pattern = r'case (\d+):\s+(\d+) tokens, (\d+) mismatching words; clocks per instruction ([0-9 ]+); whole layer (\d+)'
    default = re.findall(pattern, (tested / 'nexys-default.log').read_text())
    assert len(default) == 2 and default == re.findall(pattern, (prototype / 'nexys-default.log').read_text())
    partial = rows(tested / 'partial.log')
    assert len(partial) == 6 and partial == rows(ROOT / 'build/v2/probability-input-partial-check/grouped.log')
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
    # Only the new kernel's descriptive comments differ from its proven prototype.
    def logic(path):
        return re.sub(r'\s+', '', re.sub(r'//[^\n]*', '', path.read_text()))
    assert logic(ROOT / 'rtl/v2/common/attention_probability_input.sv') == logic(ROOT / 'build/v2/probability-input-cut/engine-sources/attention_probability_input.sv')
    digests = {name: digest for digest, name in
               (line.split(maxsplit=1) for line in (tested / 'source-sha256.txt').read_text().splitlines())}
    sources = list(base['rtl_sha256']) + ['rtl/v2/common/attention_probability_input.sv']
    assert len(sources) == len(set(sources)) == 22
    for name in sources:
        assert sha(ROOT / name) == digests[name], f'Edit under production test: {name}'
    output = ROOT / 'build/v2/kr260-opt-operand-capture-large'
    assert not output.exists(), 'Preserve existing frozen candidate'
    for name in sources:
        target = output / 'rtl-snapshot' / name.removeprefix('rtl/v2/')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    profile = {**base['profile'], 'probability_input_capture': 1, 'local_embed_controls': 1}
    result = {'candidate': 'operand-capture-large', 'target_mhz': 200, 'read_latency': 5,
              'profile': profile, 'capability_word': '0x53591fff', 'numerical_cases': 32,
              'checks': checks, 'partial_tile_cases': 6, 'partial_tile_cycles_unchanged': True,
              'nexys_default_cycles_unchanged': True,
              'rtl_sha256': {name: digests[name] for name in sources},
              'routed': False, 'hardware_qualified': False}
    (output / 'regression.json').write_text(json.dumps(result, indent=2) + '\n')
    (output / 'completion-status.json').write_text(json.dumps({'state': 'numerical_ready', 'updated_utc': datetime.now(timezone.utc).isoformat()}, indent=2) + '\n')
    print('PASS: 32 production cases equal prototype, two Nexys defaults, six partial tiles; 22 sources frozen')


if __name__ == '__main__':
    main()
