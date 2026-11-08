"""Versioned RC1 defaults installation with original-launcher rollback."""
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

BUNDLE=Path('/var/lib/sysone/rc1-default-v1')
OUT=Path('/var/lib/sysone/qualifications/rc1-default-20261108')
PACKAGE=Path('/var/lib/sysone/hardware-consolidated-rc1-20261108')
UNITS=Path('/etc/systemd/system')
LAUNCHER=Path('/usr/local/bin/sysone-qwen-fpga')


def run(args):
    r=subprocess.run(args,capture_output=True,text=True,timeout=360)
    print(json.dumps(dict(command=args,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr)),flush=True)
    r.check_returncode()
    return r.stdout


def rollback():
    run(['systemctl','stop','sysone-rc1.service'])
    run(['systemctl','disable','sysone-rc1.service'])
    run(['systemctl','stop','sysone-rc1-init.service'])
    shutil.copy2(OUT/'rollback/sysone-qwen-fpga.original',LAUNCHER)
    for name in ('sysone-rc1.service','sysone-rc1-init.service'):
        path=UNITS/name
        if path.exists():
            path.rename(OUT/'rollback'/(name+'.installed'))
    run(['systemctl','daemon-reload'])


def main():
    OUT.mkdir(parents=True,exist_ok=False)
    state=dict(passed=False,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    def save():(OUT/'installation.json').write_text(json.dumps(state,indent=2)+'\n')
    with Path('/run/lock/sysone-inference.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if BUNDLE.exists() or any((UNITS/n).exists() for n in ('sysone-rc1.service','sysone-rc1-init.service')):
            raise RuntimeError('RC1 defaults already exist; preserve and review them')
        if hashlib.sha256(LAUNCHER.read_bytes()).hexdigest()!='97e1d2bb60df803f6c5ac327647b6911ddb7040a8cb85185449c7ff59aed7792':
            raise RuntimeError('Original launcher differs from preflight')
        (OUT/'rollback').mkdir()
        shutil.copy2(LAUNCHER,OUT/'rollback/sysone-qwen-fpga.original')
        state['original_launcher_sha256']=hashlib.sha256(LAUNCHER.read_bytes()).hexdigest()
        state['original_cpu_service']=run(['systemctl','show','sysone-qwen06b-mvp.service','-p','ActiveState','-p','UnitFileState'])
        BUNDLE.mkdir()
        files=json.loads(Path(sys.argv[1]).read_text())
        for name,data in files.items():
            if Path(name).name!=name:raise RuntimeError('Invalid bundle filename')
            (BUNDLE/name).write_bytes(base64.b64decode(data))
        original=Path('/var/lib/sysone/benchmarks/persistent-arm-service-v16/bundle-r2/firmware/qwen_dma_v2/sysone_qwen_dma_v2.ko')
        shutil.copyfile(original,BUNDLE/'sysone_qwen_dma_v2.ko')
        hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in BUNDLE.iterdir() if p.is_file()}
        (BUNDLE/'bundle-sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
        state['bundle_sha256']=hashes;save()
        run(['systemd-analyze','verify',str(BUNDLE/'sysone-rc1-init.service'),str(BUNDLE/'sysone-rc1.service')])
        for name in ('sysone-rc1-init.service','sysone-rc1.service'):
            shutil.copyfile(BUNDLE/name,UNITS/name)
            (UNITS/name).chmod(0o644)
        (BUNDLE/'launcher.py').chmod(0o755)
    try:
        run(['systemctl','daemon-reload'])
        run(['systemctl','start','sysone-rc1.service'])
        # Only publish the launcher and enable boot after actual startup readiness.
        run(['/usr/bin/python3',str(BUNDLE/'control.py'),'wait-ready'])
        temp=LAUNCHER.with_name('sysone-qwen-fpga.rc1-new')
        if temp.exists():raise RuntimeError('Launcher staging path already exists')
        shutil.copyfile(BUNDLE/'launcher.py',temp);temp.chmod(0o755);temp.replace(LAUNCHER)
        run(['systemctl','enable','sysone-rc1.service'])
        state['default_health']=json.loads(run([str(LAUNCHER),'--health']))
        state['launcher_sha256']=hashlib.sha256(LAUNCHER.read_bytes()).hexdigest()
        state['service_state']=run(['systemctl','show','sysone-rc1.service','-p','ActiveState','-p','SubState','-p','UnitFileState','-p','MainPID'])
        state['init_state']=json.loads(Path('/run/sysone-rc1-init/state.json').read_text())
        state['passed']=True;save()
    except BaseException as exc:
        state['error']=type(exc).__name__+': '+str(exc);save()
        try:
            rollback();state['rolled_back']=True;save()
        except BaseException as recovery:
            state['rollback_error']=type(recovery).__name__+': '+str(recovery);save()
        raise
    print(json.dumps(state),flush=True)


if __name__=='__main__':main()
