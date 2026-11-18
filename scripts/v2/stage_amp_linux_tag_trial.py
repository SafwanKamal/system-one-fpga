"""Create a reviewable root-private fixed tag trial and collection plans."""
from pathlib import Path
import argparse
import base64
import hashlib
import json

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-linux-tag-probe-v1'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);args=ap.parse_args()
    out=BASE/args.attempt;out.mkdir(exist_ok=False)
    for name in ['inventory-v1','firmware-check-v1','adapter-check-v2','policy-check-v3','rtl-replay-v1','module-build-v1/target-build']:
        assert json.loads((BASE/name/'receipt.json').read_text())['passed'],name
    build=BASE/'module-build-v1';remote=json.loads((build/'receipt.json').read_text())['remote_directory']
    binaries={'sysone_r5_smoke.ko':'module','apu_probe':'apu-probe','pl_snapshot':'pl-snapshot'}
    hashes={}
    for name,record in binaries.items():
        data=(build/'target-build'/(record+'.stdout')).read_bytes();digest=hashlib.sha256(data).hexdigest()
        assert digest+'  '+remote+'/'+name in (build/'target-build/hashes.stdout').read_text()
        (out/name).write_bytes(data);hashes[name]=digest
    payload={}
    for name in ['amp_linux_tag_target.py','amp_linux_tag_policy.py']:
        data=(ROOT/'scripts/v2'/name).read_bytes();compile(data.decode(),name,'exec')
        payload[name]=data;hashes[name]=hashlib.sha256(data).hexdigest();(out/name).write_bytes(data)
    stock={};probe={}
    for line in (BASE/'inventory-v1/package-hashes.stdout').read_text().splitlines():
        digest,path=line.split(None,1);path=path.strip()
        if '/k26-starter-kits/' in path:stock[path]=digest
        else:probe[path]=digest
    assert len(stock)==3 and len(probe)==4
    package=ROOT/'build/v2/typed200-amp-deployment-v1/probe-package-v1/sysone-amp-origin-probe'
    for path,digest in probe.items():assert hashlib.sha256((package/Path(path).name).read_bytes()).hexdigest()==digest,path
    stage='/var/lib/sysone/linux-tag-probe/'+args.attempt;unit='sysone-linux-tag-'+args.attempt
    config=dict(unit=unit,boot_id=(BASE/'inventory-v1/health.stdout').read_text().splitlines()[2],
        elf_sha256=json.loads((BASE/'firmware-build-v1/receipt.json').read_text())['elf_sha256'],
        local_sha256=hashes,stock_sha256=stock,probe_sha256=probe)
    # Locate boot ID by schema rather than relying on uptime formatting.
    import re
    config['boot_id']=next(x for x in (BASE/'inventory-v1/health.stdout').read_text().splitlines() if re.fullmatch(r'[0-9a-f-]{36}',x))
    payload['config.json']=(json.dumps(config,indent=2)+'\n').encode()
    (out/'config.json').write_bytes(payload['config.json'])
    entries={name:base64.b64encode(data).decode() for name,data in payload.items()}
    stage_script=f'''import base64,hashlib,json,os,pathlib
stage=pathlib.Path({stage!r});stage.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
assert stage.parent.stat().st_uid==0 and not stage.parent.stat().st_mode & 0o022
stage.mkdir(mode=0o700)
assert not os.statvfs(stage).f_flag & os.ST_NOEXEC
payload=json.loads({json.dumps(entries)!r})
for name,encoded in payload.items():
 with (stage/name).open('xb') as stream: stream.write(base64.b64decode(encoded))
 (stage/name).chmod(0o700 if name.endswith('.py') else 0o600)
config=json.loads((stage/'config.json').read_text())
for name in {list(binaries)!r}:
 data=(pathlib.Path({remote!r})/name).read_bytes()
 assert hashlib.sha256(data).hexdigest()==config['local_sha256'][name]
 with (stage/name).open('xb') as stream:stream.write(data)
 (stage/name).chmod(0o600 if name.endswith('.ko') else 0o700)
for name,digest in config['local_sha256'].items():
 assert hashlib.sha256((stage/name).read_bytes()).hexdigest()==digest
 assert (stage/name).stat().st_uid==0
print('PASS root-private module/helpers/controller staging')
'''
    compile(stage_script,'stage.py','exec');(out/'stage.py').write_text(stage_script)
    invocation=f"systemd-run --unit={unit} --wait --pipe --property=Type=oneshot --property=TimeoutStartSec=120 --property=RuntimeMaxSec=120 --property=TimeoutStopSec=120 --property=KillMode=control-group '--property=ExecStopPost=/usr/bin/python3 {stage}/amp_linux_tag_target.py recover' /usr/bin/python3 '{stage}/amp_linux_tag_target.py' trial"
    collect=f'''import json,pathlib
stage=pathlib.Path({stage!r})
print(json.dumps({{p.name:p.read_text() for p in stage.iterdir() if p.suffix in ['.json','.txt','.log'] and p.name!='config.json'}},indent=2))
'''
    collection=dict(name='collect',root=True,command="python3 - <<'COLLECT_TAG'\n"+collect+'\nCOLLECT_TAG',timeout=30)
    health=dict(name='health',root=True,command='uptime; cat /proc/sys/kernel/random/boot_id; cat /proc/sys/kernel/tainted; cat /sys/devices/system/cpu/online; xmutil listapps; cat /sys/class/fpga_manager/fpga0/state; grep -w pl0_ref /sys/kernel/debug/clk/clk_summary; test ! -d /sys/module/sysone_r5_smoke; systemctl is-active snap.kria-dashboard.service.service; dmesg --ctime | tail -15')
    plan=dict(commands=[dict(name='stage',root=True,command="umask 077; python3 - <<'STAGE_TAG'\n"+stage_script+'\nSTAGE_TAG'),
        dict(name='trial',root=True,command=invocation,timeout=300),collection,health])
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    (out/'collection-plan.json').write_text(json.dumps(dict(commands=[collection,health]),indent=2)+'\n')
    (out/'preflight.json').write_text(json.dumps(dict(passed=True,root_stage=stage,unit=unit,
        qualified_pl_package_reused=True,ps_register_mmio=False,unknown_axi_drain_retains_pl=True,
        expected_module_sha256=hashes['sysone_r5_smoke.ko'],firmware_sha256=config['elf_sha256']),indent=2)+'\n')
    print('PASS root-private tag trial; fixed image/package and independent recovery plans')


if __name__=='__main__':main()
