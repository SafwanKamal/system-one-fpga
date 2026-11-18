"""Review private loader-window output/cycle equivalence before isolated synthesis."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[3]


def main():
    folder = ROOT / 'build/v2/rtl-request-window-check'
    baseline = ROOT / 'build/v2/rtl-attention16-distance-parameter-check'
    assert json.loads((folder / 'completion-status.json').read_text()) == {'exit_code': 0, 'complete': True}
    pattern = r'case (\d+):\s+(\d+) tokens, status (\d+), stopped at (\d+), (\d+) mismatching words; clocks: encoder (\d+), request (\d+)'
    checks = {}
    for name, count in {'wide': 8, 'l12': 8, 'one-word': 5, 'boundary': 3, 'h1024': 8, 'head32': 4, 'partial': 6}.items():
        text = (folder / f'{name}.log').read_text()
        rows = re.findall(pattern, text)
        assert len(rows) == count and rows == re.findall(pattern, (baseline / f'{name}.log').read_text()), name
        assert all(row[2] == '0' and row[4] == '0' for row in rows)
        checks[name] = {'cases': count, 'exact_outputs_and_cycles': True,
                        'log_sha256': hashlib.sha256(text.encode()).hexdigest()}
    pattern = r'case (\d+):\s+(\d+) tokens, (\d+) mismatching words; clocks per instruction ([0-9 ]+); whole layer (\d+)'
    rows = re.findall(pattern, (folder / 'nexys-default.log').read_text())
    assert len(rows) == 2 and rows == re.findall(pattern, (baseline / 'nexys-default.log').read_text())
    assert all(row[2] == '0' for row in rows)
    proto = ROOT / 'build/v2/linear-request-window/engine-sources/linear_engine.sv'
    digest = hashlib.sha256(proto.read_bytes()).hexdigest()
    recorded = (folder / 'source-sha256.txt').read_text()
    assert f'{digest}  rtl/v2/encoder/linear_engine.sv' in recorded
    frozen = ROOT / 'build/v2/kr260-opt-attention16-distance-large'
    regression = json.loads((frozen / 'regression.json').read_text())
    for name, expected in regression['rtl_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    result = {'checks': checks, 'numerical_cases': 36, 'partial_tile_cases': 6,
              'nexys_default_cases': 2, 'prototype_sha256': digest,
              'production_22_sources_unchanged': True,
              'stage': 'private numerical/cycle proof only; isolated inference/timing pending'}
    (folder / 'review.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS:36 KR260 plus6 partial and2 Nexys exact output/cycles; production22 unchanged')


if __name__ == '__main__':
    main()
