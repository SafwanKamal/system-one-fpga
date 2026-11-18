"""Hash-check passive module, and stage a query-only load/audit/unload plan."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-linux-r5-controller-v1'


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--attempt',required=True)
    args=ap.parse_args()
    out=BASE/args.attempt
    out.mkdir(exist_ok=False)
    package=BASE/'module-build-v3'
    binary=package/'target-build/module-binary.stdout'
    expected='1146fa19b25e2af060dc1ff4f55d2014ca58f1b9d86acc82fc4e867244a3c80a'
    assert hashlib.sha256(binary.read_bytes()).hexdigest()==expected
    assert json.loads((package/'target-build/receipt.json').read_text())['passed']
    assert json.loads((BASE/'adapter-check-v2/receipt.json').read_text())['passed']
    assert '#define SYSONE_R5_LIVE_ADMITTED 0' in (package/'linux.c').read_text()
    (out/'sysone_r5_smoke.ko').write_bytes(binary.read_bytes())
    # Read-only disassembly archived independently from the build logs.
    command=['wsl.exe','-d','Ubuntu-24.04','--','/usr/bin/aarch64-linux-gnu-objdump','-dr',
             '/mnt/c/'+str((out/'sysone_r5_smoke.ko').resolve())[3:].replace('\\','/')]
    run=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
    (out/'disassembly-attempt.txt').write_bytes(run.stdout)
    # LLVM fallback is available on Windows; no install or target action needed.
    if run.returncode:
        import os
        tool=Path('C:/AMDDesignTools/2025.2/win64/tools/clang-16/bin')
        env=os.environ.copy()
        env['PATH']='C:/AMDDesignTools/2025.2/Vitis/lib/win64.o;'+str(tool)+';'+env['PATH']
        run=subprocess.run([str(tool/'llvm-objdump.exe'),'-dr',str(out/'sysone_r5_smoke.ko')],
                           stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30,env=env)
        assert not run.returncode
    (out/'disassembly.txt').write_bytes(run.stdout)
    remote='/home/ubuntu/sysone-r5-smoke-module-build-v3/sysone_r5_smoke.ko'
    script=f'''import errno, hashlib, json, pathlib, subprocess
module=pathlib.Path({remote!r})
assert hashlib.sha256(module.read_bytes()).hexdigest()=={expected!r}
assert pathlib.Path('/proc/sys/kernel/tainted').read_text().strip()=='0'
assert not list(pathlib.Path('/sys/class/remoteproc').iterdir())
assert not pathlib.Path('/sys/module/zynqmp_r5_remoteproc').exists()
assert not pathlib.Path('/sys/module/sysone_r5_smoke').exists()
def run(args):
 r=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=15)
 print(json.dumps(dict(command=args,exit=r.returncode,output=r.stdout.decode(errors='replace'))),flush=True)
 assert r.returncode==0
run(['/usr/sbin/insmod',str(module)])
try:
 base=pathlib.Path('/sys/class/misc/sysone_r5_smoke')
 print('STATUS_BEFORE '+(base/'status').read_text(),flush=True)
 try:
  (base/'command').write_text('audit'+chr(10))
  print('AUDIT_RESULT 0',flush=True)
 except OSError as e:
  print('AUDIT_RESULT '+str(e.errno),flush=True)
  assert e.errno in (errno.EBUSY,errno.EIO,errno.EPROTO)
 status=(base/'status').read_text()
 print('STATUS_AFTER '+status,flush=True)
 assert 'live_enabled=0' in status
 for flag in ['pinned','reserved','lease_pending','mapped','may_run','loaded','quarantine']:
  assert flag+'=0 ' in status
 assert (base/'trace').read_text()==''
finally:
 run(['/usr/sbin/rmmod','sysone_r5_smoke'])
assert not pathlib.Path('/sys/module/sysone_r5_smoke').exists()
taint=int(pathlib.Path('/proc/sys/kernel/tainted').read_text())
print('TAINT_AFTER '+str(taint),flush=True)
assert taint & ~((1<<12)|(1<<13)) == 0
'''
    compile(script, 'query-only.py', 'exec')
    (out/'query-only.py').write_text(script)
    plan=dict(commands=[dict(name='passive-module-audit',root=True,
        command="python3 - <<'SYSONE_PASSIVE_AUDIT'\n"+script+'\nSYSONE_PASSIVE_AUDIT',timeout=60),
        dict(name='health',command='uptime; cat /proc/sys/kernel/tainted; cat /proc/sys/kernel/random/boot_id; cat /sys/devices/system/cpu/online; ls -la /sys/class/remoteproc'),
        dict(name='kernel-log',root=True,command='dmesg --ctime | tail -50')])
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('PASS hash-checked query-only plan; no power request, TCM mapping or R5 execution')


if __name__=='__main__':main()
