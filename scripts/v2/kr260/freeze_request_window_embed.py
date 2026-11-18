"""Freeze the fresh parameterized paired window/DSP-address candidate after proof."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return re.findall(r'case (\d+):\s+(\d+) tokens, status (\d+), stopped at (\d+), (\d+) mismatching words; clocks: encoder (\d+), request (\d+)', path.read_text())


def main():
    tested = ROOT / 'build/v2/rtl-request-window-embed-parameter-check'
    prototype = ROOT / 'build/v2/rtl-request-window-embed-dsp-check'
    assert json.loads((tested / 'completion-status.json').read_text()) == {'exit_code': 0, 'complete': True}
    proto = json.loads((prototype / 'review.json').read_text())
    assert proto['numerical_cases'] == 36 and proto['partial_tile_cases'] == 6 and proto['nexys_default_cases'] == 2
    previous = ROOT / 'build/v2/kr260-opt-attention16-distance-large'
    base = json.loads((previous / 'regression.json').read_text())
    checks = {}
    for name, count in {'wide': 8, 'l12': 8, 'one-word': 5, 'boundary': 3, 'h1024': 8, 'head32': 4, 'partial': 6}.items():
        actual = rows(tested / f'{name}.log')
        assert len(actual) == count and actual == rows(prototype / f'{name}.log'), name
        assert all(row[2] == '0' and row[4] == '0' for row in actual)
        if name in base['checks']:
            evidence = dict(base['checks'][name])
            evidence.update(log_sha256=sha(tested / f'{name}.log'), prototype_cycles_identical=True,
                            encoder_clocks=[int(r[5]) for r in actual], request_clocks=[int(r[6]) for r in actual])
            checks[name] = evidence
        assert 'FEATURES 5363ffff ' in (tested / f'{name}.log').read_text(), name
    pattern = r'case (\d+):\s+(\d+) tokens, (\d+) mismatching words; clocks per instruction ([0-9 ]+); whole layer (\d+)'
    default = re.findall(pattern, (tested / 'nexys-default.log').read_text())
    assert len(default) == 2 and default == re.findall(pattern, (prototype / 'nexys-default.log').read_text())
    assert all(row[2] == '0' for row in default)
    for group, directory in {
        'wide': 'build/v2/rtl-wide-check/vectors', 'l12': 'simulation/v2/vectors/kr260',
        'one-word': 'build/v2/rtl-batch3-check/one-word-vectors',
        'boundary': 'build/v2/rtl-batch-check/boundary-vectors',
        'h1024': 'build/v2/kr260-dot7-h1024-eight-vectors',
    }.items():
        for name, digest in base['checks'][group]['vectors_sha256'].items():
            assert sha(ROOT / directory / name) == digest
    for name, digest in base['query_group_vectors_sha256'].items():
        assert sha(ROOT / 'build/v2/attention16-head32-vectors' / name) == digest
    window = json.loads((ROOT / 'build/v2/linear-request-window-ooc/review.json').read_text())
    address = json.loads((ROOT / 'build/v2/embed-dsp-ooc/review.json').read_text())
    assert window['estimated_slack_gain_ns'] > 0 and address['accepted_for_parameterized_integration']
    assert address['estimated_slack_gain_ns'] > 0
    for name, digest in address['source_sha256'].items():
        assert sha(ROOT / name) == digest
    mapping = (ROOT / 'build/v2/embed-dsp-ooc/dsp-complete.txt').read_text().splitlines()
    assert len(mapping) == 2 and all('AREG=1 BREG=1 CREG=1 MREG=0 PREG=1' in line for line in mapping)
    assert json.loads((ROOT / 'build/v2/embed-dsp-engine/summary.json').read_text())['passed']
    primitive = ROOT / 'rtl/v2/common/embed_row_address_dsp.sv'
    arithmetic = json.loads((ROOT / 'build/v2/embed-row-dsp-arithmetic/summary.json').read_text())
    assert arithmetic['passed'] and sha(primitive) == arithmetic['kernel_sha256']
    digests = {name: digest for digest, name in
               (line.split(maxsplit=1) for line in (tested / 'source-sha256.txt').read_text().splitlines())}
    sources = [*base['rtl_sha256'], 'rtl/v2/common/embed_row_address_dsp.sv']
    assert len(sources) == len(set(sources)) == 23
    for name in sources:
        assert sha(ROOT / name) == digests[name], 'Edit under test: ' + name
    output = ROOT / 'build/v2/kr260-opt-request-window-embed-large'
    assert not output.exists(), 'Preserve existing frozen candidate'
    if sys.argv[1:] == ['--validate-only']:
        print('PASS:36KR+6partial+2Nexys exact prototype/default cycles,23sources,fixtures,DSP/register/timing proofs')
        return
    assert not sys.argv[1:], 'Unknown option'
    for name in sources:
        target = output / 'rtl-snapshot' / name.removeprefix('rtl/v2/')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    result = {**base, 'candidate': 'request-window-embed-large', 'checks': checks,
              'profile': {**base['profile'], 'cached_request_window': 1, 'dsp_embed_row_address': 1},
              'capability_word': '0x5363ffff', 'rtl_sha256': {name: digests[name] for name in sources},
              'component_proofs_sha256': {name: sha(ROOT / name) for name in [
                  'build/v2/linear-request-window-ooc/review.json', 'build/v2/embed-dsp-ooc/review.json',
                  'build/v2/embed-dsp-ooc/dsp-complete.txt', 'build/v2/embed-row-dsp-arithmetic/summary.json',
                  'build/v2/rtl-request-window-embed-dsp-check/review.json']},
              'routed': False, 'hardware_qualified': False}
    (output / 'regression.json').write_text(json.dumps(result, indent=2) + '\n')
    (output / 'completion-status.json').write_text(json.dumps({'state': 'numerical_ready', 'updated_utc': datetime.now(timezone.utc).isoformat()}) + '\n')
    print('PASS:23 sources frozen for paired200MHz synthesis; routing disabled')


if __name__ == '__main__':
    main()
