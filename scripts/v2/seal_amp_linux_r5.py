"""Seal this offline startup audit and reverify every prior preserved artifact."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'build/v2/typed200-amp-linux-r5-v1'
ANCHOR = 'docs/research/2026-10-17-kr260-debug-coexistence-validation.json'
REPORT = 'docs/research/2026-10-17-typed200-amp-linux-r5.md'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, data):
    assert not path.exists(), path
    path.write_text(json.dumps(data, indent=2)+'\n')


def main():
    prior = json.loads((ROOT / ANCHOR).read_text())
    preserved = {}
    for group in ['preserved_sha256', 'candidate_sha256']:
        for name, digest in prior[group].items():
            assert name not in preserved or preserved[name] == digest, name
            preserved[name] = digest
    expected = json.loads((BASE/'preservation-before.json').read_text())['anchor_sha256']
    assert sha(ROOT/ANCHOR) == expected
    preserved[ANCHOR] = expected
    def check(item):
        name, digest = item
        return name if not (ROOT/name).is_file() or sha(ROOT/name) != digest else None
    with ThreadPoolExecutor(max_workers=4) as pool:
        failures = [name for name in pool.map(check, preserved.items()) if name]
    assert not failures, failures
    print(f'Prior preservation PASS: {len(preserved)} unique files including anchor', flush=True)
    def receipt(attempt):
        data = json.loads((BASE/attempt/'receipt.json').read_text())
        assert data['passed'], attempt
        return data
    for attempt in ['kernel-source-v3', 'smoke-build-v2', 'smoke-emulation-v2',
                    'driver-host-check-v1', 'cleanup-host-check-v1', 'kernel-fixes-v1',
                    'overlay-check-v1', 'post-audit-health-v2']:
        receipt(attempt)
    readiness = dict(
        offline_audit_passed=True, diagnostic_firmware_built=True,
        smoke_cpu_scenarios=164, driver_callback_scenarios=226, cleanup_scenarios=7,
        narrow_kernel_fixes_staged=True, target_kernel_fixed=False,
        target_overlay_applied=False, r5_executed=False,
        live_smoke_admitted=False, typed_inference_deployment_ready=False,
        jtag_used=False, raw_ps_rpu_mmio_used=False,
        gates_open=[
            'Correct mode-query interface built and qualified for installed ABI',
            'Lease/mapping cleanup on prepare, allocation and parse failure',
            'Retain containment and resource ownership after ambiguous start or failed stop',
            'Independent board-local recovery armed before mutating driver bind',
            'Powered-down RPU entry, exact PMU/ATF ownership and TCM ECC qualification',
            'Target fresh smoke trace and verified stopped/recovered state',
            'Typed path tags, firmware/firewall/filter/output composition and full qualification'])
    write(BASE/'readiness.json', readiness)
    write(BASE/'failed-attempt-ledger.json', dict(attempts=[
        dict(path='source-download-v1', issue='Timed out partial archive; Unicode diff export failure', superseded_by='source-download-v2'),
        dict(path='added-source-v1', issue='Empty extraction receipt from initial parser; not PASS', superseded_by='kernel-source-v3'),
        dict(path='kernel-source-v1', issue='Empty initial attempt', superseded_by='kernel-source-v3'),
        dict(path='post-audit-health-v1', issue='Health exit0; read-only xmutil exit1 without root', superseded_by='post-audit-health-v2')],
        originals_retained=True, target_mutations=False))
    files = [p for p in BASE.rglob('*') if p.is_file()
             and not {'emulator-deps', '__pycache__'}.intersection(p.relative_to(BASE).parts)]
    files += list((ROOT/'firmware/typed200_amp_linux_r5').glob('*'))
    names = ['prepare_amp_linux_r5_sources.py', 'resume_amp_linux_source.py',
             'build_amp_linux_r5_smoke.py', 'check_amp_linux_r5_smoke.py',
             'check_amp_linux_r5_driver.py', 'check_amp_linux_r5_cleanup.py',
             'prepare_amp_linux_r5_fixes.py', 'check_amp_linux_r5_overlay.py', 'seal_amp_linux_r5.py']
    files += [ROOT/'scripts/v2'/name for name in names]
    files += [ROOT/REPORT]
    candidate = {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(set(files))}
    write(ROOT/'docs/research/2026-10-17-typed200-amp-linux-r5-validation.json', dict(
        passed=True, observed_utc=datetime.now(timezone.utc).isoformat(),
        preserved_unique_files=len(preserved), preserved_sha256=preserved,
        candidate_sha256=candidate, candidate_files=len(candidate),
        live_startup_admitted=False, target_r5_executed=False,
        software_checks_passed=True, dependencies_excluded_from_seal=['emulator-deps', '__pycache__'],
        handoff_mutable_unsealed=True))
    print(f'New audit sealed: {len(candidate)} files; live startup remains gated', flush=True)


if __name__ == '__main__':
    main()
