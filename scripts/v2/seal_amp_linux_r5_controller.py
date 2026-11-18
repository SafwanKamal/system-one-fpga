"""Reverify prior evidence and seal the narrow target smoke/recovery milestone."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-linux-r5-controller-v1'
ANCHOR='docs/research/2026-10-17-typed200-amp-linux-r5-validation.json'
REPORT='docs/research/2026-10-17-typed200-amp-linux-r5-controller.md'


def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def write(path,data):
    assert not path.exists(),path
    path.write_text(json.dumps(data,indent=2)+'\n')


def main():
    prior=json.loads((ROOT/ANCHOR).read_text());preserved={}
    for group in ['preserved_sha256','candidate_sha256']:
        for name,digest in prior[group].items():
            assert name not in preserved or preserved[name]==digest
            preserved[name]=digest
    expected=json.loads((BASE/'preservation-before.json').read_text())['anchor_sha256']
    assert sha(ROOT/ANCHOR)==expected
    preserved[ANCHOR]=expected
    def check(item):
        name,digest=item
        assert sha(ROOT/name)==digest,name
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(check,preserved.items()))
    print(f'Prior preservation PASS {len(preserved)} unique files including original anchor',flush=True)
    def passed(path):
        data=json.loads((BASE/path/'receipt.json').read_text());assert data['passed'],path
        return data
    for name in ['session-check-v3','adapter-check-v6','smoke-emulation-v1',
                 'module-build-v7/target-build','prepare-trial-v1/target-trial',
                 'smoke-trial-v2/target-trial','smoke-failure-health-v1']:
        passed(name)
    success=(BASE/'smoke-trial-v2/target-trial/smoke-service.stdout').read_text()
    failure=(BASE/'smoke-trial-v1/target-trial/prepare-only-service.stdout').read_text()
    assert 'SMOKE_AND_RECOVERY_PASS' in success and 'watchdog_released_both_leases' in success
    assert 'ERROR=00000001' in failure and '"exit": 0' in failure
    trace='R5: PASS\nSCTLR=00e50878\nCPSR=000001d3\nMIDR=411fc153\n'
    assert json.dumps(trace) in success
    (BASE/'target-pass-trace.txt').write_text(trace)
    # New gate macros differ; exact functions tested in host live branch must
    # still match those compiled into the successful target module.
    from check_amp_linux_r5_adapter import extract
    module=(BASE/'module-build-v7/linux.c').read_text()
    tested=(BASE/'adapter-check-v6/adapter_functions.inc').read_text()
    for name in ['smoke_pm_event','correct_mode','inspect','request','lease','release',
                 'stop','off','map','unmap','load','wake','recover_workfn','command_store']:
        assert extract(module,name) in tested,name
    assert sha(BASE/'module-build-v7/target-build/module-binary.stdout')=='9edf6bd825660bb65d7774d57c94ce175bd5a6c4cfc35e448ae42289ea63aeba'
    write(BASE/'readiness.json',dict(
        diagnostic_smoke_deployed_and_passed=True,target_recovered_and_module_unloaded=True,
        preparation_watchdog_target_passed=True,firmware_exception_recovery_target_passed=True,
        failed_stop_resource_retention_host_tested=True,failed_stop_hardware_fault_induced=False,
        session_trajectories=10465,adapter_scenarios=[25,26,35],firmware_emulation_cases=164,
        actual_target_trace=trace,current_kernel_taint=12288,expected_taint_flags=['O','E'],
        jtag_used=False,raw_linux_ps_rpu_mmio_used=False,rpu_mode_changed=False,
        corrected_elf_sha256='65033cebee9df86b202f0b86206302eb639768bd389884f22be3c891eaf23b53',
        old_vbar_images_cpu_startup_admitted=False,hardened_replay_plan_executed=False,
        full_typed_inference_deployment_ready=False,hard_wcet_claim=False,
        remaining='Separate corrected startup/tag firmware, trusted firmware/session/firewall/filter/output composition and full numerical/physical/target qualification'))
    write(BASE/'failed-attempt-ledger.json',dict(originals_retained=True,attempts=[
        dict(path='module-build-v1',issue='Kernel node_state helper name collision',superseded_by='module-build-v3'),
        dict(path='module-build-v2',issue='Non-exported OF all-node iterator',superseded_by='module-build-v3'),
        dict(path='adapter-check-v1',issue='Host extraction matched forward prototype; signedness warning',superseded_by='adapter-check-v2'),
        dict(path='passive-audit-v1',issue='Literal newline escape in initial generated query; plan not executed',superseded_by='passive-audit-v3'),
        dict(path='passive-audit-v2',issue='Generated Python SyntaxError before any module action',superseded_by='passive-audit-v3'),
        dict(path='smoke-trial-v1',issue='Real R5 undefined instruction from unsupported VBAR; recovered and unloaded',superseded_by='smoke-trial-v2')],
        superseded_checks=[dict(path='session-check-v1',issue='Wide fault-mask conversion strengthened in v2; two-bank coverage added in v3')]))
    files=[p for p in BASE.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files+=list((ROOT/'firmware/typed200_amp_linux_r5_controller').glob('*'))
    script_names=['prepare_amp_linux_r5_controller.py','check_amp_linux_r5_session.py',
        'check_amp_linux_r5_adapter.py','package_amp_linux_r5_controller.py',
        'prepare_amp_linux_r5_passive_audit.py','prepare_amp_linux_r5_field_trial.py',
        'capture_amp_uart_passive.ps1','prepare_amp_linux_r5_reset_fix.py',
        'build_amp_linux_r5_reset_smoke.py','check_amp_linux_r5_reset_smoke.py',
        'seal_amp_linux_r5_controller.py']
    files+=[ROOT/'scripts/v2'/name for name in script_names]+[ROOT/REPORT]
    candidate={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(files)) if p.is_file()}
    write(ROOT/'docs/research/2026-10-17-typed200-amp-linux-r5-controller-validation.json',dict(
        passed=True,observed_utc=datetime.now(timezone.utc).isoformat(),
        preserved_unique_files=len(preserved),preserved_sha256=preserved,
        candidate_files=len(candidate),candidate_sha256=candidate,
        diagnostic_smoke_passed=True,full_inference_ready=False,handoff_mutable_unsealed=True))
    print(f'PASS target smoke/recovery evidence sealed: {len(candidate)} new files',flush=True)


if __name__=='__main__':main()
