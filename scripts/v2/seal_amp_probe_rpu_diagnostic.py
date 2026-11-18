"""Preserve both previous maps and seal the separate RPU diagnostic milestone."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'build/v2/typed200-amp-rpu-diagnostic-v1'
PRIOR = ROOT / 'docs/research/2026-10-16-typed200-amp-target-probe-validation.json'
OUTPUT = ROOT / 'docs/research/2026-10-16-typed200-amp-rpu-diagnostic-validation.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if OUTPUT.exists():
        raise RuntimeError('milestone already sealed; do not overwrite')
    before = json.loads((BASE / 'preservation-before.json').read_text())
    assert sha(PRIOR) == before['anchor_sha256']
    assert (BASE / 'prior-validation.json').read_bytes() == PRIOR.read_bytes()
    previous = json.loads(PRIOR.read_text())
    preserved = {}
    for name in ['preserved_sha256', 'candidate_sha256']:
        for path, digest in previous[name].items():
            if path in preserved:
                assert preserved[path] == digest
            preserved[path] = digest
    preserved[PRIOR.relative_to(ROOT).as_posix()] = sha(PRIOR)
    bad = [path for path, digest in preserved.items() if not (ROOT / path).is_file() or sha(ROOT / path) != digest]
    if bad:
        raise RuntimeError('prior evidence changed: ' + repr(bad))
    sources = [ROOT / 'scripts/v2' / name for name in [
        'amp_probe_guard_policy.py', 'amp_probe_guarded_target.py', 'check_amp_probe_guarded.py',
        'amp_probe_rpu_inventory.py', 'seal_amp_probe_rpu_diagnostic.py']]
    sources += [ROOT / 'docs/research/2026-10-16-typed200-amp-rpu-diagnostic.md']
    sources += [p for p in BASE.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    candidate = {p.relative_to(ROOT).as_posix(): sha(p) for p in sources}
    check = json.loads((BASE / 'controller-check-v2/receipt.json').read_text())
    assert check['passed'] and check['cases'] == 72
    for path, digest in check['source_sha256'].items():
        assert sha(ROOT / path) == digest
    result = dict(passed=True, preserved_unique_files=len(preserved), preserved_sha256=preserved,
                  candidate_sha256=candidate, controller_software_checks=72,
                  target_programmed=False, r5_executed=False, live_controller_qualified=False,
                  typed_output_deployment_ready=False)
    with OUTPUT.open('x') as f:
        f.write(json.dumps(result, indent=2) + '\n')
    print(f'PASS preserve {len(preserved)} prior files/anchors; seal {len(candidate)} new artifacts')


if __name__ == '__main__':
    main()
