"""Stage a root-controlled prepare-only service and independent stop handler."""
from pathlib import Path
import argparse
import base64
import hashlib
import json

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-linux-r5-controller-v1'


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--attempt',required=True)
    ap.add_argument('--package',required=True)
    ap.add_argument('--mode',choices=['prepare','smoke'],required=True)
    ap.add_argument('--adapter-check',required=True)
    args=ap.parse_args()
    out=BASE/args.attempt;out.mkdir(exist_ok=False)
    package=BASE/args.package
    assert json.loads((package/'target-build/receipt.json').read_text())['passed']
    assert json.loads((BASE/args.adapter_check/'receipt.json').read_text())['passed']
    code=(package/'linux.c').read_text()
    live=int(args.mode=='smoke')
    assert f'#define SYSONE_R5_LIVE_ADMITTED {live}' in code
    assert '#define SYSONE_R5_PREPARE_ADMITTED 1' in code
    if live:
        assert json.loads((BASE/'prepare-trial-v1/target-trial/receipt.json').read_text())['passed']
    binary=(package/'target-build/module-binary.stdout').read_bytes()
    digest=hashlib.sha256(binary).hexdigest()
    remote=json.loads((package/'receipt.json').read_text())['remote_build_directory']+'/sysone_r5_smoke.ko'
    assert digest+'  '+remote in (package/'target-build/module-info.stdout').read_text()
    stage='/run/sysone-r5-'+args.attempt
    unit='sysone-r5-'+args.attempt
    root_module=stage+'/sysone_r5_smoke.ko'
    script=f'''import hashlib,json,pathlib,re,subprocess,sys,time
BASE=pathlib.Path('/sys/class/misc/sysone_r5_smoke')
MODULE=pathlib.Path({root_module!r})
def log(label,data): print(label+' '+json.dumps(data),flush=True)
def run(args):
 r=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=10)
 log('COMMAND',dict(args=args,exit=r.returncode,output=r.stdout.decode(errors='replace')))
 assert r.returncode==0
def status():
 text=(BASE/'status').read_text().strip();log('STATUS',text)
 return dict(part.split('=',1) for part in text.split())
def command(text):
 log('SYSFS_COMMAND',text)
 (BASE/'command').write_text(text+chr(10))
def idle(s):
 return all(s[k]=='0' for k in ['pinned','reserved','lease_pending','mapped','may_run','loaded','quarantine'])
def cleanup():
 if not BASE.exists():return
 command('stop')
 s=status()
 assert idle(s),'Retain module, mappings and leases after uncertain recovery'
 run(['/usr/sbin/rmmod','sysone_r5_smoke'])
if sys.argv[1]=='stop':
 cleanup();sys.exit(0)
assert hashlib.sha256(MODULE.read_bytes()).hexdigest()=={digest!r}
assert MODULE.stat().st_uid==0 and MODULE.parent.stat().st_uid==0
assert MODULE.parent.stat().st_mode & 0o077 == 0
assert not pathlib.Path('/sys/module/sysone_r5_smoke').exists()
assert not list(pathlib.Path('/sys/class/remoteproc').iterdir())
assert not pathlib.Path('/sys/module/zynqmp_r5_remoteproc').exists()
taint=int(pathlib.Path('/proc/sys/kernel/tainted').read_text())
assert taint & ~((1<<12)|(1<<13)) == 0
run(['/usr/sbin/insmod',str(MODULE)])
try:
 s=status();assert idle(s) and s['live_enabled']=={str(live)!r} and s['prepare_enabled']=='1'
 command('audit');s=status();assert s['audit']=='0' and s['usage']=='0' and s['usage1']=='0'
 command('prepare');s=status()
 if not idle(s):
  assert s['pinned']=='1' and s['lease_pending']=='3' and s['mapped']=='1' and s['loaded']=='1'
  assert s['may_run']=='0' and s['quarantine']=='0'
 if {live}:
  assert (BASE/'trace').read_text().startswith('R5: WAIT')
  command('start')
  trace='';trace_deadline=time.monotonic()+2
  while time.monotonic()<trace_deadline:
   trace=(BASE/'trace').read_text()
   if 'PASS' in trace or 'FAIL' in trace:break
   time.sleep(0.02)
  log('FRESH_SMOKE_TRACE',trace)
  match=re.fullmatch('R5: PASS'+chr(10)+'SCTLR=([0-9a-f]{{8}})'+chr(10)+'CPSR=([0-9a-f]{{8}})'+chr(10)+'MIDR=([0-9a-f]{{8}})'+chr(10),trace)
  assert match,'Fresh complete PASS schema required'
  ctl,cpsr,midr=(int(x,16) for x in match.groups())
  assert ctl & 0x1005==0 and cpsr & 255==0xd3 and midr & 0xfff0==0xc150
  s=status();assert s['may_run']=='1' and s['loaded']=='0' and s['lease_pending']=='3'
 deadline=time.monotonic()+9
 while not idle(s) and time.monotonic()<deadline:
  time.sleep(0.2);s=status()
 assert idle(s),'Kernel watchdog must stop/release without an SSH stop command'
 trace=(BASE/'trace').read_text();log('TRACE',trace)
 assert trace.startswith('R5: PASS' if {live} else 'R5: WAIT')
 command('audit');s=status();assert idle(s) and s['audit']=='0'
 assert s['usage']=='0' and s['usage1']=='0' and s['r0']=='0' and s['r1']=='0'
 log('SMOKE_AND_RECOVERY_PASS' if {live} else 'PREPARE_ONLY_PASS',dict(r5_executed=bool({live}),watchdog_released_both_leases=True))
finally:
 cleanup()
'''
    compile(script,'trial.py','exec')
    (out/'trial.py').write_text(script)
    script_digest=hashlib.sha256(script.encode()).hexdigest()
    encoded=base64.b64encode(script.encode()).decode()
    stage_cmd=f"umask 077; mkdir '{stage}' && printf '%s' '{encoded}' | base64 -d > '{stage}/trial.py' && chmod 700 '{stage}/trial.py' && echo '{script_digest}  {stage}/trial.py' | sha256sum -c -"
    # Read once, hash those bytes, then install the same bytes into the new
    # root-private directory. Never insmod from a user-writable build path.
    copy=f'''import hashlib,pathlib
data=pathlib.Path({remote!r}).read_bytes()
assert hashlib.sha256(data).hexdigest()=={digest!r}
with pathlib.Path({root_module!r}).open('xb') as stream: stream.write(data)
assert pathlib.Path({root_module!r}).stat().st_uid==0
'''
    compile(copy,'stage-module.py','exec')
    stage_cmd+=" && python3 - <<'SYSONE_STAGE_MODULE'\n"+copy+'\nSYSONE_STAGE_MODULE'
    service=f"systemd-run --unit={unit} --wait --pipe --property=Type=oneshot --property=TimeoutStartSec=25 --property=RuntimeMaxSec=25 --property=TimeoutStopSec=10 --property=KillMode=control-group '--property=ExecStopPost=/usr/bin/python3 {stage}/trial.py stop' /usr/bin/python3 '{stage}/trial.py' prepare"
    plan=dict(commands=[dict(name='stage',root=True,command=stage_cmd),
        dict(name=args.mode+'-service',root=True,command=service,timeout=60),
        dict(name='post-health',command='uptime; cat /proc/sys/kernel/random/boot_id; cat /proc/sys/kernel/tainted; cat /sys/devices/system/cpu/online; ls -la /sys/class/remoteproc; test ! -d /sys/module/sysone_r5_smoke'),
        dict(name='kernel-log',root=True,command='dmesg --ctime | tail -30')])
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    (out/'preflight.json').write_text(json.dumps(dict(passed=True,prepare_only=not live,
        r5_start_compile_disabled=not live,module_sha256=digest,controller_sha256=script_digest,
        root_stage=stage,systemd_unit=unit,adapter_check=args.adapter_check,
        module_copied_and_hash_checked_in_root_private_stage=True,
        watchdog_armed_before_prepare=True),indent=2)+'\n')
    print(f'PASS {args.mode} plan, root stage and independent kernel/service recovery')


if __name__=='__main__':main()
