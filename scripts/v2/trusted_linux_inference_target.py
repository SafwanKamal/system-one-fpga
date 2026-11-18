"""Root-local deployment of the qualified Linux-driven PL inference backend."""
import fcntl,hashlib,json,os,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
REPO=Path('/home/ubuntu/system-one-fpga')
PY='/home/ubuntu/sysone-venv/bin/python'
APP='sysone-v2-attention-context-capture'
DASH='snap.kria-dashboard.service.service'
CLIENT=[PY,str(REPO/'scripts/v2/sysone_v2_client.py'),'--kr260','--image','minilm-l12-v1-kr260','--timeout','15']

def require(ok,message):
    if not ok:raise RuntimeError(message)

def save(name,data):
    temp=HERE/(name+'.tmp');temp.write_text(json.dumps(data,indent=2)+'\n');os.replace(temp,HERE/name)

def run(args,name,timeout=60):
    print('START '+name,flush=True)
    with (HERE/(name+'.log')).open('xb') as out:
        p=subprocess.run(args,cwd=REPO,stdout=out,stderr=subprocess.STDOUT,timeout=timeout)
    require(p.returncode==0,name+' failed: '+str(p.returncode))
    print('PASS '+name,flush=True)

def verify(expected):
    for name,digest in expected.items():
        require(hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest,'Changed file: '+name)

def recover():
    if not (HERE/'state.json').exists():return
    state=json.loads((HERE/'state.json').read_text())
    if state.get('success'):return
    if state.get('run_attempted'):
        # A process timeout cannot cancel an in-flight AXI transaction.
        # Retain the loaded PL for diagnosis; never unload a potentially busy master.
        save('failure-retention.json',dict(pl_retained=True,reason='RUN attempted; quiescence requires inspection'))
        return
    if state.get('pl_changed'):
        run(['xmutil','unloadapp'],'recovery-unload')
        run(['xmutil','loadapp','k26-starter-kits'],'recovery-stock')
    if state.get('dashboard_active'):run(['systemctl','start',DASH],'recovery-dashboard')
    save('recovery.json',dict(passed=True,stock_restored=True))

def deploy(config):
    require(os.geteuid()==0 and os.environ.get('INVOCATION_ID'),'Root systemd service required')
    require(HERE.parent==Path('/var/lib/sysone/trusted-inference'),'Unexpected stage')
    require(not (HERE/'state.json').exists(),'Attempt already exists')
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==config['boot_id'],'Boot changed')
    require(int(Path('/proc/sys/kernel/tainted').read_text()) & ~12288==0,'Unexpected taint')
    require(not Path('/sys/module/sysone_r5_smoke').exists(),'R5 module present')
    require(not list(Path('/sys/class/remoteproc').iterdir()),'Remoteproc active')
    require(Path('/sys/class/fpga_manager/fpga0/state').read_text().strip()=='operating','PL unavailable')
    fw=Path('/sys/firmware/devicetree/base/fpga-region/firmware-name').read_bytes().rstrip(b'\0')
    require(fw==b'k26-starter-kits.bit.bin','Stock starting app required')
    verify(config['sha256'])
    active=subprocess.run(['systemctl','is-active','--quiet',DASH]).returncode==0
    state=dict(success=False,run_attempted=False,pl_changed=False,dashboard_active=active)
    save('state.json',state)
    run(['systemctl','stop',DASH],'dashboard-stop')
    for maps in Path('/proc').glob('[0-9]*/maps'):
        try:
            for line in maps.read_text().splitlines():
                parts=line.split()
                require(not (len(parts)>=6 and parts[-1]=='/dev/mem' and 0xa0000000<=int(parts[2],16)<0xb0000000),'Existing PL mapping')
        except (FileNotFoundError,ProcessLookupError):pass
    state['pl_changed']=True;save('state.json',state)
    run(['xmutil','unloadapp'],'stock-unload')
    run(['xmutil','loadapp',APP],'encoder-load')
    # The existing client confirms DT, no-map DDR reservation, clock/AFI driver
    # bindings and ID/build/capabilities before accessing DDR or issuing RUN.
    run(CLIENT+['load'],'model-load',120)
    state['run_attempted']=True;save('state.json',state)
    run(CLIENT+['run','--dataset','atis','show me flights from denver to boston tomorrow'],'text-inference',60)
    run(CLIENT+['eval','--suite',str(REPO/'build/v2/eval/minilm-l12-v1-matched.json'),
                '--verify','--report',str(HERE/'eval.json')],'frozen-evaluation',480)
    evaluation=json.loads((HERE/'eval.json').read_text())
    require(evaluation['backend']=='kr260' and evaluation['complete'],'Incomplete hardware evaluation')
    require(evaluation['verification']==dict(exact=350,total=350),'Golden hidden states differ')
    require(len(evaluation['cases'])==350,'Incomplete case count')
    verify(config['sha256'])
    # Install a serialized, usable entry point; no source/model replacement.
    entry=Path('/usr/local/bin/sysone-infer')
    require(not entry.exists(),'Existing inference entry point; do not overwrite')
    entry.write_text('#!/bin/sh\nexec sudo /usr/bin/flock -w 30 /run/lock/sysone-inference.lock '+PY+' '+str(REPO/'scripts/v2/sysone_v2_client.py')+' --kr260 --image minilm-l12-v1-kr260 --timeout 15 run --dataset atis "$@"\n')
    entry.chmod(0o755)
    run([str(entry),'what is the cheapest flight from dallas to boston'],'installed-entrypoint',60)
    state['success']=True;save('state.json',state)
    save('result.json',dict(passed=True,backend='PL encoder + on-board Linux A53 heads',
        app=APP,image_sha256=evaluation['image_sha256'],clock_hz=evaluation['clock_hz'],
        verification=evaluation['verification'],inference_cases=350,linux_trusted=True,
        r5_inference=False,exclusive_owner_enforced=False,entrypoint=str(entry),
        left_loaded=True,dashboard_stopped=True,jtag_used=False))
    print('FULL_INFERENCE_DEPLOYMENT_PASS: encoder/model left loaded; sysone-infer ready',flush=True)

def main():
    with (HERE/'controller.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if sys.argv[1]=='recover':recover()
        else:
            try:deploy(json.loads((HERE/'config.json').read_text()))
            finally:recover()

if __name__=='__main__':main()
