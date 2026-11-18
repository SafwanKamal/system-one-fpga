"""Package all remaining eligible held-out requests; leave deployed inference unchanged."""
from pathlib import Path
import hashlib,io,json,shlex,tarfile
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-r5-heldout-remaining-v1'
STAGE='/var/lib/sysone/r5-evaluation/remaining-test-v1'

def sha(data):return hashlib.sha256(data).hexdigest()

def main():
    selection=json.loads((BASE/'selection.json').read_text())
    assert selection['passed'] and selection['already_tested_cases_excluded']==700
    assert sha((BASE/'cases.json').read_bytes())==selection['cases_sha256']
    config=dict(boot_id='6c80ec1a-e7ae-473f-b169-d54f129615d1',cases_sha256=selection['cases_sha256'],
        client_sha256=sha((ROOT/'scripts/v2/r5_inference_client.py').read_bytes()),
        elf_sha256='e5dcdf1c863c917bb4c591b9820216c5beea81883a70af60044b735eee2492f4')
    files={'collector.py':(ROOT/'scripts/v2/collect_r5_remaining.py').read_bytes(),
        'cases.json':(BASE/'cases.json').read_bytes(),'selection.json':(BASE/'selection.json').read_bytes(),
        'config.json':(json.dumps(config,indent=2)+'\n').encode()}
    compile(files['collector.py'],'collector.py','exec')
    with tarfile.open(BASE/'batch.tar.gz','w:gz') as archive:
        for name,data in files.items():
            info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o600
            archive.addfile(info,io.BytesIO(data))
    upload='/home/ubuntu/sysone-heldout-remaining-v1-upload.tar.gz'
    unpack=f'''from pathlib import Path
import hashlib,io,tarfile
s=Path({STAGE!r});assert s.parent.stat().st_uid==0 and not s.parent.stat().st_mode & 0o022
s.mkdir(mode=0o700)
data=Path({upload!r}).read_bytes();assert hashlib.sha256(data).hexdigest()=={sha((BASE/'batch.tar.gz').read_bytes())!r}
with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
 for member in archive:
  assert member.name in {list(files)!r} and member.isfile() and member.size<128000000
  with (s/member.name).open('xb') as out:out.write(archive.extractfile(member).read())
  (s/member.name).chmod(0o600)
print('Remaining held-out batch verified and staged')
'''
    health='cat /proc/sys/kernel/random/boot_id; cat /proc/sys/kernel/tainted; cat /sys/devices/system/cpu/online; cat /sys/class/misc/sysone_r5_smoke/status; cat /sys/class/fpga_manager/fpga0/state; grep -w -e pl0_ref -e pl1_ref /sys/kernel/debug/clk/clk_summary; if ps -eo comm | grep -E "^(hw_server|cs_server|xsdb|xsct)$"; then exit 1; fi'
    tail=[dict(name='health',root=True,command=health),dict(name='collect',root=True,timeout=300,
        command=f'tar -C {STAGE} -czf - metadata.json summary.json requests.jsonl progress.log')]
    commands=[dict(name='upload',upload=str(BASE/'batch.tar.gz'),remote=upload),
        dict(name='stage',root=True,command='python3 -c '+shlex.quote(unpack)),
        dict(name='run',root=True,timeout=29100,command=f'systemd-run --unit=sysone-r5-heldout-remaining-v1 --wait --property=Type=oneshot --property=TimeoutStartSec=28800 --property=TimeoutStopSec=30 --property=StandardOutput=append:{STAGE}/progress.log --property=StandardError=append:{STAGE}/progress.log /home/ubuntu/sysone-venv/bin/python {STAGE}/collector.py')]+tail
    (BASE/'run-plan.json').write_text(json.dumps(dict(commands=commands),indent=2)+'\n')
    (BASE/'collection-plan.json').write_text(json.dumps(dict(commands=tail),indent=2)+'\n')
    (BASE/'staging.json').write_text(json.dumps(dict(passed=True,planned_requests=selection['cases'],root_stage=STAGE,archive_sha256=sha((BASE/'batch.tar.gz').read_bytes()),model_changed=False,client_changed=False,pl_changed=False),indent=2)+'\n')
    print(f"Ready: {selection['cases']} requests; archive {(BASE/'batch.tar.gz').stat().st_size} bytes")

if __name__=='__main__':main()
