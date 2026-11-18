"""Stage a calibrated R5 build and a paired 6,580-request hardware evaluation."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,io,json,random,shlex,tarfile
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'build/v2/typed200-linux-r5-calibrated-v1'
STAGE='/var/lib/sysone/r5-inference/calibrated-v1'

def sha(data):return hashlib.sha256(data).hexdigest()

def main():
    checks=['firmware-build-v2','head-check-v2','elf-check-v2','policy-check-v2']
    for name in checks:assert json.loads((BASE/name/'receipt.json').read_text())['passed']
    anchor=ROOT/'docs/research/2026-10-17-typed200-r5-remaining-results-validation.json'
    prior=json.loads(anchor.read_text());assert prior['passed'] and prior['hardware_requests']==55261
    (BASE/'prior-validation.json').write_bytes(anchor.read_bytes())
    (BASE/'preservation-before.json').write_text(json.dumps(dict(anchor=anchor.relative_to(ROOT).as_posix(),anchor_sha256=sha(anchor.read_bytes())),indent=2)+'\n')
    before=ROOT/'build/v2/typed200-r5-heldout-eval-v1/cases.json'
    remaining=ROOT/'build/v2/typed200-r5-heldout-remaining-v1/cases.json'
    suite=json.loads(remaining.read_text());first=json.loads(before.read_text())
    cases=[row for row in first['cases']+suite['cases'] if row['dataset'] in ['clinc','multi_clinc']]
    assert len(cases)==len({r['ids_sha256'] for r in cases})==6580
    random.Random(2026101836).shuffle(cases);suite['cases']=cases;suite['seed']=2026101836;suite['per_dataset']=None
    raw=(json.dumps(suite,separators=(',',':'))+'\n').encode();(BASE/'cases.json').write_bytes(raw)
    fit=json.loads((BASE/'calibration-dev-fit.json').read_text());tau=fit['selected']['tau'];assert tau==.36
    config=dict(boot_id='6c80ec1a-e7ae-473f-b169-d54f129615d1',cases_sha256=sha(raw),
        client_sha256=sha((ROOT/'scripts/v2/r5_inference_client.py').read_bytes()),
        elf_sha256=json.loads((BASE/'firmware-build-v2/receipt.json').read_text())['elf_sha256'],
        old_module_sha256='e6f834a35a9c73c1bf768aa2ff05b049b52b418e9b1eb0c204f4e1db338965a0',tau=tau)
    files={'cases.json':raw,'collector.py':(ROOT/'scripts/v2/collect_r5_remaining.py').read_bytes(),
        'deploy.py':(ROOT/'scripts/v2/deploy_r5_calibration_target.py').read_bytes()}
    original=ROOT/'firmware/typed200_linux_r5_inference'
    for name in ['linux.c','session.c','session.h','Makefile']:files['source/'+name]=(original/name).read_bytes()
    files['source/smoke_image.h']=(BASE/'firmware-build-v2/smoke_image.h').read_bytes()
    config['source_sha256']={name:sha(data) for name,data in files.items()}
    files['config.json']=(json.dumps(config,indent=2)+'\n').encode()
    (BASE/'config.json').write_bytes(files['config.json'])
    with tarfile.open(BASE/'deploy.tar.gz','w:gz') as archive:
        for name,data in files.items():
            info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o600;archive.addfile(info,io.BytesIO(data))
    upload='/home/ubuntu/sysone-r5-calibrated-v1-upload.tar.gz'
    unpack=f'''from pathlib import Path
import hashlib,io,tarfile
s=Path({STAGE!r});assert s.parent.stat().st_uid==0 and not s.parent.stat().st_mode & 0o022
s.mkdir(mode=0o700);(s/'source').mkdir(mode=0o700)
data=Path({upload!r}).read_bytes();assert hashlib.sha256(data).hexdigest()=={sha((BASE/'deploy.tar.gz').read_bytes())!r}
with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
 for member in archive:
  assert member.name in {list(files)!r} and member.isfile() and member.size<12000000
  with (s/member.name).open('xb') as out:out.write(archive.extractfile(member).read())
  (s/member.name).chmod(0o600)
print('Verified calibration deployment and paired test staged')
'''
    health='cat /proc/sys/kernel/random/boot_id; cat /proc/sys/kernel/tainted; cat /sys/devices/system/cpu/online; cat /sys/class/misc/sysone_r5_smoke/status; cat /sys/class/fpga_manager/fpga0/state; grep -w -e pl0_ref -e pl1_ref /sys/kernel/debug/clk/clk_summary; if ps -eo comm | grep -E "^(hw_server|cs_server|xsdb|xsct)$"; then exit 1; fi'
    tail=[dict(name='health',root=True,command=health),dict(name='collect',root=True,timeout=180,
        command=f'tar -C {STAGE} -czf - hardware-validation.json promotion.json metadata.json summary.json requests.jsonl progress.log source/sysone_r5_smoke.ko')]
    commands=[dict(name='upload',upload=str(BASE/'deploy.tar.gz'),remote=upload),
        dict(name='stage',root=True,command='python3 -c '+shlex.quote(unpack)),
        dict(name='run',root=True,timeout=3900,command=f'systemd-run --unit=sysone-r5-calibrated-v1 --wait --property=Type=oneshot --property=TimeoutStartSec=3600 --property=TimeoutStopSec=30 --property=StandardOutput=append:{STAGE}/progress.log --property=StandardError=append:{STAGE}/progress.log /home/ubuntu/sysone-venv/bin/python {STAGE}/deploy.py')]+tail
    (BASE/'deploy-plan.json').write_text(json.dumps(dict(commands=commands),indent=2)+'\n')
    (BASE/'collection-plan.json').write_text(json.dumps(dict(commands=tail),indent=2)+'\n')
    progress=f'date -u; systemctl show sysone-r5-calibrated-v1 -p ActiveState -p SubState -p ExecMainStatus; tail -4 {STAGE}/progress.log; if test -f {STAGE}/summary.json; then cat {STAGE}/summary.json; fi; cat /sys/class/misc/sysone_r5_smoke/status'
    (BASE/'progress-plan.json').write_text(json.dumps(dict(commands=[dict(name='progress',root=True,command=progress)]),indent=2)+'\n')
    (BASE/'deployment-prepared.json').write_text(json.dumps(dict(prepared_utc=datetime.now(timezone.utc).isoformat(),passed=True,baseline_completed=True,planned_paired_requests=6580,tau=tau,source_sha256=config['source_sha256'],current_status='PREPARED'),indent=2)+'\n')
    print('Ready: improved R5 deployment plus6580 paired requests; baseline already complete')

if __name__=='__main__':main()
