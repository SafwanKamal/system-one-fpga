"""Verify previous immutable evidence and seal the target-probe milestone."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[2]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    previous=ROOT/'docs/research/2026-10-16-typed200-amp-deployment-validation.json'
    target=ROOT/'docs/research/2026-10-16-typed200-amp-target-probe-validation.json'
    assert not target.exists()
    a=json.loads(previous.read_text())
    preserved={**a['preserved_sha256'],**a['candidate_sha256']}
    preserved[previous.relative_to(ROOT).as_posix()]=sha(previous)
    for name,h in preserved.items():assert sha(ROOT/name)==h,name
    base=ROOT/'build/v2/typed200-amp-deployment-v1'
    (base/'target-milestone-v1/source/seal_typed200_amp_target_probe.py').write_bytes(Path(__file__).read_bytes())
    selected=[]
    for name in ['board-readiness-v3','board-readiness-v4','probe-target-v1','apu-tag-replay-v1','apu-tag-replay-v2','target-milestone-v1']:
        selected.extend(p for p in (base/name).rglob('*') if p.is_file())
    selected.extend([base/'access-after-user-powercycle-v1.json',base/'apu-probe-v1.elf',
      ROOT/'docs/research/2026-10-16-typed200-amp-target-probe.md',ROOT/'docs/research/2026-10-16-typed200-amp-target-probe.csv'])
    candidate={p.relative_to(ROOT).as_posix():sha(p) for p in selected}
    assert not set(preserved)&set(candidate)
    result=dict(passed=True,preserved_unique_files=len(preserved),preserved_sha256=preserved,
      candidate_sealed_files=len(candidate),candidate_sha256=candidate,
      target_state='Stock restored; diagnostic app installed but inactive; SSH/dashboard available; R5 remains reset',
      diagnostic_trial_passed=True,original_service_recovery_assertion_passed=False,
      reviewed_recovery_passed=True,typed_inference_deployed=False,typed_output_mvp_ready=False)
    target.write_text(json.dumps(result,indent=2)+'\n')
    print('PASS preserved',len(preserved),'sealed',len(candidate),'diagnostic only; full MVP not ready')
if __name__=='__main__':main()
