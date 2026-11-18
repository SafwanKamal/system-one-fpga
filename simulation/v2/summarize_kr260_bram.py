"""Record completed LUT/BRAM regressions with the exact staged RTL hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def read_cases(path):
    text = path.read_text()
    rows = [dict(zip(('case', 'tokens', 'status', 'stopped_at', 'mismatches',
                      'encoder_clocks', 'request_clocks'), map(int, match)))
            for match in re.findall(
                r'case (\d+):\s+(\d+) tokens, status (\d+), stopped at (\d+), '
                r'(\d+) mismatching words; clocks: encoder (\d+), request (\d+)', text)]
    passed = re.search(r'PASS: KR260 block bit-exact, (\d+) cases, (\d+) words compared', text)
    if not passed or len(rows) != int(passed[1]) or [r['tokens'] for r in rows] != [1, 2, 3, 4, 5, 12, 64, 128]:
        raise ValueError(f'Incomplete regression: {path}')
    if any(r['status'] or r['mismatches'] or not 0 < r['encoder_clocks'] <= r['request_clocks'] for r in rows):
        raise ValueError(f'Failed regression: {path}')
    return {'cases': rows, 'words': int(passed[2]),
            'log_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=ROOT / 'build/v2/rtl-bram-check')
    args = parser.parse_args()
    output = args.directory
    checks = {}
    for model, names in (('minilm-l12', ('kr260-pipe', 'kr260-bram')),
                         ('bert-mini', ('bert-pipe', 'bert-bram'))):
        lut, bram = (read_cases(output / f'{name}.log') for name in names)
        if lut['cases'] != bram['cases'] or lut['words'] != bram['words']:
            raise ValueError(f'LUT/BRAM simulation behavior differs for {model}')
        checks[model] = {'lut': lut, 'bram': bram, 'simulation_cycles_identical': True}
    nexys = (output / 'encoder.log').read_text()
    if 'PASS: encoder layer bit-exact, 2 cases, 39216 words compared' not in nexys:
        raise ValueError('Default Nexys layer regression incomplete')
    checks['nexys_default'] = {'cases': 2, 'words': 39216,
                             'log_sha256': hashlib.sha256((output / 'encoder.log').read_bytes()).hexdigest()}
    staged = dict(line.split(maxsplit=1)[::-1] for line in
                  (output / 'source-sha256.txt').read_text().splitlines())
    previous = json.loads((ROOT / 'build/v2/rtl-pipeline-check/summary.json').read_text())
    rtl_hashes = {name: staged[name] for name in previous['rtl_sha256']}
    summary = {'candidate': 'MAC_INPUT_REGISTERS=1, EXP_TABLE_IN_BRAM=1',
               'hardware_clock_verified': False, 'checks': checks, 'rtl_sha256': rtl_hashes,
               'note': 'Equal cycles refer to the same simulated AXI stall sequence; hardware timing and latency still require measurement.'}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print('PASS: two models, eight lengths, LUT/BRAM cycle equality and default Nexys; source hashes recorded')


if __name__ == '__main__':
    main()
