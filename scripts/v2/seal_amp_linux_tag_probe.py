"""Seal observation/recovery evidence without claiming target admission passed."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-linux-tag-probe-v1'
REPORT='docs/research/2026-10-17-typed200-amp-linux-tag-probe.md'

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    before=json.loads((BASE/'preservation-before.json').read_text())
    prior=json.loads((BASE/'prior-validation.json').read_text())
    preserved={}
    for group in ['preserved_sha256','candidate_sha256']:
        for name,digest in prior[group].items():
            assert name not in preserved or preserved[name]==digest
            preserved[name]=digest
    assert len(preserved)==before['files']==10700
    assert sha(ROOT/before['anchor'])==before['anchor_sha256']
    preserved[before['anchor']]=before['anchor_sha256']
    def check(item):
        name,digest=item;assert sha(ROOT/name)==digest,name
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(check,preserved.items()))
    for name in ['firmware-check-v1','adapter-check-v2','policy-check-v3',
                 'rtl-replay-v1','module-build-v1/target-build','observation-review-v1']:
        assert json.loads((BASE/name/'receipt.json').read_text())['passed'],name
    review=json.loads((BASE/'observation-review-v1/receipt.json').read_text())
    assert not review['original_trial_passed'] and not review['filter_admission_qualified']
    assert review['measured_metadata_rejections']==5 and review['recovery']['passed']
    assert '# Passive capture end' in (BASE/'target-trial-v2/uart.txt').read_text()
    assert sha(BASE/'firmware-build-v1/probe.elf')=='bacf61240bffa66a168bf5416aafcf4c1270f0056fbcd44c916ab934d65cc6d0'
    files=[p for p in BASE.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files+=list((ROOT/'firmware/typed200_amp_linux_tag_probe').glob('*'))
    names=['prepare_amp_linux_tag_probe.py','build_amp_linux_tag_probe.py',
           'check_amp_linux_tag_firmware.py','check_amp_linux_tag_adapter.py',
           'package_amp_linux_tag_module.py','check_amp_linux_tag_rtl.py',
           'amp_linux_tag_policy.py','check_amp_linux_tag_policy.py',
           'amp_linux_tag_target.py','stage_amp_linux_tag_trial.py',
           'prepare_amp_linux_tag_reviewed_recovery.py','audit_amp_linux_tag_sideband.py',
           'review_amp_linux_tag_observations.py','seal_amp_linux_tag_probe.py']
    files+=[ROOT/'scripts/v2'/n for n in names]+[ROOT/REPORT]
    candidate={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(files)) if p.is_file()}
    target=ROOT/'docs/research/2026-10-17-typed200-amp-linux-tag-probe-validation.json'
    assert not target.exists()
    target.write_text(json.dumps(dict(passed=True,scope='Evidence integrity and recovery; target admission remains failed/unqualified',
        observed_utc=datetime.now(timezone.utc).isoformat(),preserved_unique_files=len(preserved),
        preserved_sha256=preserved,candidate_files=len(candidate),candidate_sha256=candidate,
        r5_markers_observed=True,original_trial_passed=False,stock_recovery_passed=True,
        filter_admission_qualified=False,full_inference_ready=False,
        jtag_used=False,raw_linux_ps_rpu_mmio_used=False,handoff_mutable_unsealed=True),indent=2)+'\n')
    print(f'PASS evidence seal: {len(preserved)} prior and {len(candidate)} new files; admission remains closed')

if __name__=='__main__':main()
