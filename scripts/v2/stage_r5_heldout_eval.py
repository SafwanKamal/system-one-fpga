"""Stage a finite held-out batch using bounded SSH commands and no model changes."""
from pathlib import Path
import base64,hashlib,io,json,shlex,tarfile
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'build/v2/typed200-r5-heldout-eval-v1'

def sha(data):return hashlib.sha256(data).hexdigest()

def main():
    selection=json.loads((BASE/'selection.json').read_text());assert selection['passed']
    assert sha((BASE/'cases.json').read_bytes())==selection['cases_sha256']
    assert json.loads((BASE/'scoring-check.json').read_text())['passed']
    stage='/var/lib/sysone/r5-evaluation/fresh-test-v1'
    config=dict(boot_id='6c80ec1a-e7ae-473f-b169-d54f129615d1',cases_sha256=selection['cases_sha256'],
        client_sha256=sha((ROOT/'scripts/v2/r5_inference_client.py').read_bytes()),
        elf_sha256='e5dcdf1c863c917bb4c591b9820216c5beea81883a70af60044b735eee2492f4')
    files={'collector.py':(ROOT/'scripts/v2/collect_r5_heldout.py').read_bytes(),
        'cases.json':(BASE/'cases.json').read_bytes(),'selection.json':(BASE/'selection.json').read_bytes(),
        'config.json':(json.dumps(config,indent=2)+'\n').encode()}
    compile(files['collector.py'],'collector.py','exec')
    with tarfile.open(BASE/'batch.tar.gz','w:gz') as tf:
        for name,data in files.items():
            item=tarfile.TarInfo(name);item.size=len(data);item.mode=0o600;tf.addfile(item,io.BytesIO(data))
    archive=(BASE/'batch.tar.gz').read_bytes();encoded=base64.b64encode(archive).decode();parts=[encoded[i:i+24000] for i in range(0,len(encoded),24000)]
    init=f'''from pathlib import Path
s=Path({stage!r});s.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
assert s.parent.stat().st_uid==0 and not s.parent.stat().st_mode & 0o022
s.mkdir(mode=0o700);print('Fresh evaluation stage ready')
'''
    commands=[dict(name='stage',root=True,command='python3 -c '+shlex.quote(init))]
    for index,part in enumerate(parts):
        code=f"from pathlib import Path; Path({(stage+'/part-'+str(index))!r}).write_text({part!r})"
        commands.append(dict(name='upload-'+str(index),root=True,command='python3 -c '+shlex.quote(code)))
    unpack=f'''from pathlib import Path
import base64,hashlib,io,tarfile
s=Path({stage!r});data=base64.b64decode(''.join((s/('part-'+str(i))).read_text() for i in range({len(parts)})))
assert hashlib.sha256(data).hexdigest()=={sha(archive)!r}
with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as tf:
 for member in tf:
  assert member.name in {list(files)!r} and member.isfile() and member.size<4000000
  with (s/member.name).open('xb') as out:out.write(tf.extractfile(member).read())
  (s/member.name).chmod(0o600)
print('Verified held-out data and collector staged')
'''
    commands.append(dict(name='unpack',root=True,command='python3 -c '+shlex.quote(unpack)))
    commands.append(dict(name='run',root=True,timeout=1020,command=f'systemd-run --unit=sysone-r5-heldout-fresh-v1 --wait --pipe --property=Type=oneshot --property=TimeoutStartSec=900 --property=TimeoutStopSec=30 /home/ubuntu/sysone-venv/bin/python {stage}/collector.py'))
    collect=f'''from pathlib import Path
import json
s=Path({stage!r});print(json.dumps({{name:(s/name).read_text() for name in ['metadata.json','summary.json','requests.jsonl'] if (s/name).exists()}},indent=2))
'''
    tail=[dict(name='collect',root=True,timeout=60,command='python3 -c '+shlex.quote(collect)),
        dict(name='health',root=True,command='cat /proc/sys/kernel/random/boot_id; cat /proc/sys/kernel/tainted; cat /sys/devices/system/cpu/online; cat /sys/class/misc/sysone_r5_smoke/status; cat /sys/class/fpga_manager/fpga0/state; grep -w -e pl0_ref -e pl1_ref /sys/kernel/debug/clk/clk_summary; dmesg --ctime | tail -5')]
    commands+=tail
    assert max(len(c['command'].encode()) for c in commands)<40000
    (BASE/'run-plan.json').write_text(json.dumps(dict(commands=commands),indent=2)+'\n')
    (BASE/'collection-plan.json').write_text(json.dumps(dict(commands=tail),indent=2)+'\n')
    (BASE/'staging.json').write_text(json.dumps(dict(passed=True,root_stage=stage,archive_sha256=sha(archive),upload_chunks=len(parts),max_command_bytes=max(len(c['command'].encode()) for c in commands),no_pl_or_model_reconfiguration=True),indent=2)+'\n')
    print(f'Ready:700 R5 requests, {len(parts)} bounded upload chunks')

if __name__=='__main__':main()
