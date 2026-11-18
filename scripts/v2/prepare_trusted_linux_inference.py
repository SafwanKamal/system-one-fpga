"""Stage an isolated, repeatable deployment attempt using installed assets."""
from pathlib import Path
import argparse,base64,json,shlex
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-trusted-linux-inference-v1'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);args=ap.parse_args()
    assert args.attempt in ['deploy-v2','deploy-v3']
    attempt=args.attempt;stage='/var/lib/sysone/trusted-inference/'+attempt
    unit='sysone-trusted-inference-'+attempt
    config=(BASE/'config.json').read_bytes()
    expected=json.loads(config)['sha256']
    assert all(name.startswith('/') and '\\' not in name for name in expected),'Linux paths required'
    source=(ROOT/'scripts/v2/trusted_linux_inference_target.py').read_bytes();compile(source,'controller','exec')
    (BASE/(attempt+'-controller.py')).write_bytes(source)
    payload={n:base64.b64encode(d).decode() for n,d in [('controller.py',source),('config.json',config)]}
    code=f'''import pathlib,base64,json
s=pathlib.Path({stage!r});s.parent.mkdir(mode=0o700,parents=True,exist_ok=True);s.mkdir(mode=0o700)
assert s.parent.stat().st_uid==0 and not s.parent.stat().st_mode & 0o022
for n,v in json.loads({json.dumps(payload)!r}).items():
 (s/n).write_bytes(base64.b64decode(v));(s/n).chmod(0o600)
assert not pathlib.Path('/usr/local/bin/sysone-infer').exists()
print('Root-private inference controller staged')
'''
    collect=f'''import pathlib,json
s=pathlib.Path({stage!r});print(json.dumps({{p.name:p.read_text() for p in s.iterdir() if p.suffix in ('.json','.log') and p.name!='config.json'}},indent=2))
'''
    health="cat /proc/sys/kernel/random/boot_id; cat /proc/sys/kernel/tainted; cat /sys/devices/system/cpu/online; xmutil listapps; cat /sys/class/fpga_manager/fpga0/state; grep -w -e pl0_ref -e pl1_ref /sys/kernel/debug/clk/clk_summary; test ! -d /sys/module/sysone_r5_smoke"
    commands=[dict(name='stage',root=True,command='python3 -c '+shlex.quote(code)),
        dict(name='deploy',root=True,timeout=700,command=f"systemd-run --unit={unit} --wait --pipe --property=Type=oneshot --property=TimeoutStartSec=600 --property=TimeoutStopSec=90 --property=KillMode=control-group '--property=ExecStopPost=/usr/bin/python3 {stage}/controller.py recover' /usr/bin/python3 {stage}/controller.py deploy"),
        dict(name='collect',root=True,timeout=45,command='python3 -c '+shlex.quote(collect)),
        dict(name='health',root=True,command=health)]
    for suffix,cmds in [('-plan.json',commands),('-collection-plan.json',commands[2:])]:
        p=BASE/(attempt+suffix);assert not p.exists();p.write_text(json.dumps(dict(commands=cmds),indent=2)+'\n')
    print('Ready: '+attempt)

if __name__=='__main__':main()
