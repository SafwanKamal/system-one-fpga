"""Reuse qualified hardware and recovery for a trusted-Linux diagnostic run."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-trusted-r5-smoke-v1'

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    anchor=ROOT/'docs/research/2026-10-17-typed200-amp-r5-profile-filter-validation.json'
    prior=json.loads(anchor.read_text());records={**prior['preserved_sha256'],**prior['candidate_sha256']}
    records[anchor.relative_to(ROOT).as_posix()]=sha(anchor)
    def check(item):
        path,digest=item;assert sha(ROOT/path)==digest,path
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(check,records.items()))
    BASE.mkdir(exist_ok=False)
    (BASE/'prior-validation.json').write_bytes(anchor.read_bytes())
    (BASE/'preservation-before.json').write_text(json.dumps(dict(passed=True,files=len(records),
        anchor=anchor.relative_to(ROOT).as_posix(),anchor_sha256=sha(anchor)),indent=2)+'\n')
    controller=(ROOT/'scripts/v2/amp_linux_tag_target.py').read_text()
    old='from amp_linux_tag_policy import require,idle,restore_allowed,parse_trace,check_apu,check_r5'
    assert controller.count(old)==1
    controller=controller.replace(old,'from amp_linux_tag_policy import require,idle,restore_allowed,parse_trace,check_apu\nfrom amp_r5_profile_policy import review as check_r5')
    controller=controller.replace("Path('/var/lib/sysone/linux-tag-probe')","Path('/var/lib/sysone/trusted-r5-smoke')")
    controller=controller.replace('passed=True,diagnostic_only=True,measured=result,inference_deployed=False,',
        'passed=True,diagnostic_only=True,linux_trusted=True,exclusive_owner_enforced=False,measured=result,inference_deployed=False,')
    controller=controller.replace('PASS R5/APU AXI identities measured; watchdog released clock/TCM leases',
        'PASS trusted-Linux R5 smoke workload; watchdog released clock/TCM leases; no exclusive-owner claim')
    (BASE/'amp_linux_tag_target.py').write_text(controller)
    for name in ['amp_linux_tag_policy.py','amp_r5_profile_policy.py']:
        (BASE/name).write_bytes((ROOT/'scripts/v2'/name).read_bytes())
    stage=(ROOT/'scripts/v2/stage_amp_linux_tag_trial.py').read_text()
    stage=stage.replace("BASE=ROOT/'build/v2/typed200-amp-linux-tag-probe-v1'",
        "BASE=ROOT/'build/v2/typed200-amp-trusted-r5-smoke-v1'\nPRIOR=ROOT/'build/v2/typed200-amp-linux-tag-probe-v1'")
    stage=stage.replace("(BASE/name/'receipt.json')","(PRIOR/name/'receipt.json')")
    stage=stage.replace("build=BASE/'module-build-v1'","build=PRIOR/'module-build-v1'")
    stage=stage.replace("BASE/'inventory-v1/","PRIOR/'inventory-v1/")
    stage=stage.replace("BASE/'firmware-build-v1/","PRIOR/'firmware-build-v1/")
    stage=stage.replace("['amp_linux_tag_target.py','amp_linux_tag_policy.py']",
        "['amp_linux_tag_target.py','amp_linux_tag_policy.py','amp_r5_profile_policy.py']")
    stage=stage.replace("(ROOT/'scripts/v2'/name).read_bytes()","(BASE/name).read_bytes()")
    stage=stage.replace('/var/lib/sysone/linux-tag-probe/','/var/lib/sysone/trusted-r5-smoke/')
    stage=stage.replace("unit='sysone-linux-tag-'","unit='sysone-trusted-r5-'")
    stage=stage.replace('qualified_pl_package_reused=True,ps_register_mmio=False,',
        'qualified_pl_package_reused=True,linux_trusted=True,exclusive_owner_enforced=False,ps_register_mmio=False,')
    for name,text in [('amp_linux_tag_target.py',controller),('stage.py',stage)]:compile(text,name,'exec')
    (BASE/'stage.py').write_text(stage)
    sys.argv=['stage.py','--attempt','smoke-trial-v1']
    exec(compile(stage,str(BASE/'stage.py'),'exec'),dict(__file__=str(ROOT/'scripts/v2/stage_amp_linux_tag_trial.py'),__name__='__main__'))
    print('PASS preserved prior evidence; prepared fixed trusted-Linux diagnostic deployment')

if __name__=='__main__':main()
