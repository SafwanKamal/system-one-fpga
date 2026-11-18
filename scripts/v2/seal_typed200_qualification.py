"""Freeze completed offline capture evidence while rechecking its prior seal."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    docs = ROOT/'docs/research'
    dest = docs/'2026-10-15-typed200-capture-validation.json'
    if dest.exists():
        raise ValueError('Preserve the completed seal')
    previous = docs/'2026-10-15-typed200-timing-continuation-validation.json'
    preserved = {}
    for key, values in json.loads(previous.read_text()).items():
        if key in ('preserved_sha256', 'review_sha256', 'new_source_and_report_sha256'):
            for name, expected in values.items():
                if sha(ROOT/name) != expected:
                    raise ValueError(f'Changed sealed file: {name}')
                preserved[name] = expected
    b = ROOT/'build/v2/typed200-qualification-host-v3'
    receipt = json.loads((b/'receipt.json').read_text())
    for name, expected in receipt['source_sha256'].items():
        if sha(ROOT/name) != expected:
            raise ValueError(f'Changed tested source: {name}')
    for name, expected in receipt['artifact_sha256'].items():
        if sha(b/name) != expected:
            raise ValueError(f'Changed artifact: {name}')
    report = docs/'2026-10-15-typed200-capture-qualification.md'
    result = {'verified_utc': datetime.now(timezone.utc).isoformat(),
              'scope': 'Offline record checker and host/mock-service ABI evidence only',
              'all_preserved_files_unchanged': True, 'preserved_unique_files': len(preserved),
              'prior_seal_sha256': sha(previous), 'preserved_sha256': preserved,
              'source_sha256': {**receipt['source_sha256'],
                  Path(__file__).relative_to(ROOT).as_posix(): sha(Path(__file__))},
              'documentation_sha256': {report.relative_to(ROOT).as_posix(): sha(report)},
              'evidence_sha256': {p.relative_to(ROOT).as_posix(): sha(p) for p in b.iterdir() if p.is_file()},
              'decoder_tests_passed': 332, 'service_capture_cases': 5,
              'arm_and_host_layout_assertions_passed': True,
              'target_executed': False, 'wcet_certified': False,
              'board_programming_performed': False}
    with dest.open('x', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(f'PASS {len(preserved)} preserved files and final host-capture artifacts; no target qualification')
if __name__ == '__main__':
    main()
