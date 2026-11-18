"""Review the private source-address recurrence; no production/build admission."""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def main(grouped=False):
    folder = ROOT / ('build/v2/rtl-source-row-bram-check' if grouped else 'build/v2/rtl-source-row-check')
    baseline = ROOT / 'build/v2/rtl-operand-capture-check'
    assert json.loads((folder / 'completion-status.json').read_text()) == {'exit_code': 0, 'complete': True}
    pattern = r'case (\d+):\s+(\d+) tokens, status (\d+), stopped at (\d+), (\d+) mismatching words; clocks: encoder (\d+), request (\d+)'
    checks = {}
    for name, count in {'wide': 8, 'l12': 8, 'one-word': 5, 'boundary': 3, 'h1024': 8, 'partial': 6}.items():
        log = folder / f'{name}.log'
        rows = re.findall(pattern, log.read_text())
        assert len(rows) == count and rows == re.findall(pattern, (baseline / log.name).read_text()), name
        assert all(row[2] == '0' and row[4] == '0' for row in rows)
        checks[name] = {'cases': count, 'exact_outputs_and_cycles': True,
                       'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest()}
    pattern = r'case (\d+):\s+(\d+) tokens, (\d+) mismatching words; clocks per instruction ([0-9 ]+); whole layer (\d+)'
    actual = re.findall(pattern, (folder / 'nexys-default.log').read_text())
    assert len(actual) == 2 and actual == re.findall(pattern, (baseline / 'nexys-default.log').read_text())
    hashes = {name: digest for digest, name in (line.split(maxsplit=1) for line in (folder / 'source-sha256.txt').read_text().splitlines())}
    prototype = ROOT / ('build/v2/linear-source-row-bram/engine-sources/linear_engine.sv' if grouped else
                        'build/v2/linear-source-row/engine-sources/linear_engine.sv')
    assert hashlib.sha256(prototype.read_bytes()).hexdigest() == hashes['rtl/v2/encoder/linear_engine.sv']
    result = {'complete': True, 'grouped_bram': grouped, 'numerical_cases': 32, 'partial_cases': 6, 'nexys_cases': 2,
              'checks': checks, 'nexys_outputs_and_cycles_unchanged': True,
              'prototype_sha256': hashes['rtl/v2/encoder/linear_engine.sv'],
              'production_parameter_admitted': False, 'routed': False, 'hardware_qualified': False}
    (folder / 'review.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS source-row: 32 KR260, six partial tiles, two Nexys; exact outputs/cycles')


if __name__ == '__main__':
    assert sys.argv[1:] in ([], ['--bram']), 'Use --bram for the separate grouped prototype'
    main(sys.argv[1:] == ['--bram'])
