"""Require numerical evidence for the H1024 candidate before synthesis."""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    base_path = ROOT / (sys.argv[1] if len(sys.argv) > 1 else 'build/v2/rtl-dot4-check') / 'summary.json'
    base = json.loads(base_path.read_text())
    output = ROOT / (sys.argv[2] if len(sys.argv) > 2 else 'build/v2/rtl-dot4-large-check')
    checks = {}
    for profile, reference in (
        ('wide', 'batch-wide.log'), ('l12', 'batch-l12.log'),
        ('one-word', 'one-word-head.log'),
    ):
        raw = (output / f'{profile}.log').read_bytes()
        log = raw.decode()
        rows = re.findall(r'case (\d+):\s+(\d+) tokens, status (\d+), stopped at (\d+), (\d+) mismatching words; clocks: encoder (\d+), request (\d+)', log)
        lengths = [1, 2, 3, 4, 5, 12, 64, 128] if profile != 'one-word' else [1, 2, 3, 31, 33]
        words = base['checks'][reference]['words']
        if [int(r[1]) for r in rows] != lengths or any(int(r[2]) or int(r[4]) for r in rows):
            raise ValueError(f'Incomplete or incorrect large-profile results: {profile}')
        if f'PASS: KR260 block bit-exact, {len(lengths)} cases, {words} words compared' not in log:
            raise ValueError(f'Missing full golden comparison: {profile}')
        if 'BUILD register 20804004' not in log or 'FEATURES 5359013f' not in log:
            raise ValueError(f'Wrong capacity or pipeline profile: {profile}')
        checks[profile] = {'sha256': hashlib.sha256(raw).hexdigest(), 'words': words,
                           'tokens': lengths, 'encoder_clocks': [int(r[5]) for r in rows]}
    for source, digest in base['rtl_sha256'].items():
        if hashlib.sha256((ROOT / source).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Current RTL differs from frozen regression: {source}')
    profile = dict(base['profile'], max_hidden=1024)
    result = {'profile': profile, 'checks': checks, 'rtl_sha256': base['rtl_sha256'],
              'base_regression_sha256': hashlib.sha256(base_path.read_bytes()).hexdigest(),
              'hardware_qualified': False, 'synthesis_fit_verified': False}
    (output / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: H1024 profile, 21 additional frozen cases and unchanged tested RTL')


if __name__ == '__main__':
    main()
