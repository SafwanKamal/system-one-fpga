"""Require matching protocol evidence before building registered-request RTL."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def main():
    evidence = ROOT / 'build/v2/eval/axi-request-registers'
    report = json.loads((evidence / 'summary.json').read_text())
    if set(report['checks']) != {'direct-low', 'registered-low', 'registered-high'}:
        raise ValueError('Missing AXI mode/address coverage')
    for profile, result in report['checks'].items():
        if not result['passed'] or hashlib.sha256((evidence / f'{profile}.log').read_bytes()).hexdigest() != result['sha256']:
            raise ValueError(f'Invalid AXI protocol evidence: {profile}')
    for check in ('simultaneous_read_write_test', 'reset_cancellation', 'valid_to_ready_dependency_test'):
        if report.get(check) is not True:
            raise ValueError(f'Missing request-register check: {check}')
    for source, digest in report['source_sha256'].items():
        if hashlib.sha256((ROOT / source).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Protocol-tested source changed: {source}')
    if 'PASS: simultaneous32reads/32writes' not in (evidence / 'queue-result.log').read_text():
        raise ValueError('Missing simultaneous/reset test completion')
    ooc = ROOT / 'build/v2/axi-request-register-ooc'
    paths = json.loads((ooc / 'result.json').read_text())
    if [(r['registered_requests'], r['combinational_valid_to_write_ready_paths']) for r in paths] != [(0, 1), (1, 0)]:
        raise ValueError('Synthesized valid-to-ready dependency gate failed')
    for source in ('rtl/v2/common/sync_fifo.sv', 'rtl/v2/platform/kr260/axi_memory_port.sv'):
        frozen = ooc / 'rtl-snapshot' / Path(source).name
        if hashlib.sha256(frozen.read_bytes()).digest() != hashlib.sha256((ROOT / source).read_bytes()).digest():
            raise ValueError(f'OOC-tested source changed: {source}')
    print('PASS: request-register protocol evidence and source hashes')


if __name__ == '__main__':
    main()
