"""Seal the completed debug-coexistence investigation without rewriting history."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'build/v2/typed200-amp-rpu-recovery-v1'
PRIOR = ROOT / 'docs/research/2026-10-16-typed200-amp-rpu-diagnostic-validation.json'
OUTPUT = ROOT / 'docs/research/2026-10-17-kr260-debug-coexistence-validation.json'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    assert not OUTPUT.exists(), 'already sealed; preserve it'
    before = json.loads((BASE / 'preservation-before.json').read_text())
    assert sha(PRIOR) == before['anchor_sha256']
    assert PRIOR.read_bytes() == (BASE / 'prior-validation.json').read_bytes()
    old = json.loads(PRIOR.read_text())
    preserved = {}
    for key in ['preserved_sha256', 'candidate_sha256']:
        for name, digest in old[key].items():
            assert name not in preserved or preserved[name] == digest
            preserved[name] = digest
    preserved[PRIOR.relative_to(ROOT).as_posix()] = sha(PRIOR)
    bad = [n for n, h in preserved.items() if not (ROOT/n).is_file() or sha(ROOT/n) != h]
    assert not bad, bad
    for name in ['linux-diagnosis-v1', 'linux-stability-v1', 'post-isolation-v1']:
        assert json.loads((BASE / name / 'receipt.json').read_text())['passed']
    diagnosis = json.loads((BASE/'diagnosis.json').read_text())
    assert diagnosis['software_observation_passed'] and diagnosis['samples'] == 25
    sources = [p for p in BASE.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    sources += list((ROOT/'build/v2/typed200-amp-rpu-diagnostic-v1/inventory-v3').glob('*'))
    sources += [ROOT/'scripts/v2/amp_probe_saved_ssh.py', Path(__file__),
                ROOT/'docs/research/2026-10-16-typed200-amp-rpu-recovery.md',
                ROOT/'docs/research/2026-10-17-kr260-debug-coexistence.md']
    candidate = {p.relative_to(ROOT).as_posix(): sha(p) for p in sources if p.is_file()}
    result = dict(passed=True, preserved_unique_files=len(preserved), preserved_sha256=preserved,
                  candidate_sha256=candidate, diagnosis=diagnosis,
                  no_target_image_load=True, no_explicit_ps_writes=True,
                  no_boot_flash_changes=True, no_commit_or_push=True)
    with OUTPUT.open('x') as f:
        f.write(json.dumps(result, indent=2)+'\n')
    print(f'PASS preserve {len(preserved)} files/anchors; seal {len(candidate)} artifacts')


if __name__ == '__main__':
    main()
