"""After the baseline finishes: deploy calibrated R5 and measure paired held-out cases."""
from pathlib import Path
import fcntl,hashlib,importlib.util,json,os,subprocess,sys
import numpy as np
HERE=Path(__file__).resolve().parent;REPO=Path('/home/ubuntu/system-one-fpga')
CONTROL=Path('/sys/class/misc/sysone_r5_smoke')
BASELINE=Path('/var/lib/sysone/r5-evaluation/remaining-test-v1')
OLD_MODULE=Path('/var/lib/sysone/r5-inference/deploy-v2/sysone_r5_smoke.ko')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(name,data):(HERE/name).write_text(json.dumps(data,indent=2)+'\n')
def status():return (CONTROL/'status').read_text()
def idle():
    fields=dict(s.split('=',1) for s in status().split())
    return all(fields[k]=='0' for k in ['pinned','reserved','lease_pending','mapped','may_run','loaded','quarantine','error','recovery_error'])
def command(args,timeout=180):subprocess.run(args,check=True,timeout=timeout)

def main():
    assert os.geteuid()==0 and os.environ.get('INVOCATION_ID')
    config=json.loads((HERE/'config.json').read_text())
    baseline=json.loads((BASELINE/'summary.json').read_text())
    assert baseline['complete'] and baseline['requests']==55261 and baseline['errors']==0
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==config['boot_id']
    assert sha(OLD_MODULE)==config['old_module_sha256']
    for name,digest in config['source_sha256'].items():assert sha(HERE/name)==digest,name
    assert sha(Path('/var/lib/sysone/r5-inference/deploy-v2/r5_inference_client.py'))==config['client_sha256']
    # Compilation happens after baseline measurement, avoiding CPU load in its timings.
    command(['make','-C','/lib/modules/'+os.uname().release+'/build','M='+str(HERE/'source'),'CC=aarch64-linux-gnu-gcc-13','modules','-j2'])
    module=HERE/'source/sysone_r5_smoke.ko';new_module_sha=sha(module)
    sys.path.insert(0,str(REPO/'src'))
    from sysone.v2 import ddr_image,eval_suite
    spec=importlib.util.spec_from_file_location('client','/var/lib/sysone/r5-inference/deploy-v2/r5_inference_client.py')
    client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)
    manifest=json.loads((REPO/'export/v2/image/minilm-l12-v1-kr260/manifest.json').read_text())
    wp=client.WordPiece.from_file(REPO/'export/v2/chain/minilm-l12-v1/tokenizer.json')
    machine=ddr_image.ImageMachine((REPO/'export/v2/image/minilm-l12-v1-kr260/minilm-l12-v1-kr260.img').read_bytes())
    old_elf='e5dcdf1c863c917bb4c591b9820216c5beea81883a70af60044b735eee2492f4'
    swapped=False
    try:
        with Path('/run/lock/sysone-inference.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            assert idle() and old_elf in status()
            command(['/usr/sbin/rmmod','sysone_r5_smoke'])
            swapped=True
            command(['/usr/sbin/insmod',str(module)])
            assert config['elf_sha256'] in status()
            suite=json.loads((REPO/'build/v2/eval/minilm-l12-v1-matched.json').read_text())
            cases=[];logits_checked=0;changed=0
            for row in suite['cases']:
                original=eval_suite.chain(row);ch=client.build_chain(wp,[s.words for s in original.segments],original.task,128)
                jobs=client.jobs_for(ch,original.dataset);answer=client.execute(ch,jobs,manifest);hidden=eval_suite.reference(row)
                assert idle() and answer['trace'].startswith('R5: INFERENCE PASS')
                for actual,(name,rows,meta) in zip(answer['predictions'],jobs):
                    lg,sc=machine.head_logits(hidden,name,np.asarray(rows));lg=np.asarray(lg).reshape(-1);scores=lg*sc;label=int(np.argmax(scores));old_label=label
                    if name=='intent.clinc' and 1.0/np.exp(scores-scores.max()).sum()<config['tau']:label=150
                    assert actual['logits']==lg.tolist() and actual['label_index']==label,(row['id'],name)
                    logits_checked+=len(lg);changed+=label!=old_label
                cases.append(dict(id=row['id'],dataset=original.dataset,head_jobs=len(jobs)))
                if len(cases)%50==0:print('Calibrated hardware reference '+str(len(cases))+'/350',flush=True)
            write('hardware-validation.json',dict(passed=True,cases=cases,integer_logits=logits_checked,changed_clinc_jobs=changed,elf_sha256=config['elf_sha256'],module_sha256=new_module_sha))
        # The paired benchmark uses the identical deployed client and collector.
        command(['/home/ubuntu/sysone-venv/bin/python',str(HERE/'collector.py')],timeout=2400)
        # Score the two frozen decisions on identical inputs. No threshold fitting here.
        old={}
        for path in [Path('/var/lib/sysone/r5-evaluation/fresh-test-v1/requests.jsonl'),BASELINE/'requests.jsonl']:
            with path.open() as stream:
                for line in stream:
                    row=json.loads(line)
                    if row['dataset'] in ['clinc','multi_clinc']:old[row['ids_sha256']]=row
        paired={};seen=set()
        with (HERE/'requests.jsonl').open() as stream:
            for line in stream:
                row=json.loads(line);before=old[row['ids_sha256']];seen.add(row['ids_sha256'])
                assert row['id']==before['id'] and row['passed'] and before['passed']
                assert row['scores']['classification_n']==before['scores']['classification_n']
                d=paired.setdefault(row['dataset'],dict(requests=0,n=0,before_correct=0,after_correct=0))
                d['requests']+=1;d['n']+=row['scores']['classification_n'];d['before_correct']+=before['scores']['classification_correct'];d['after_correct']+=row['scores']['classification_correct']
        assert len(seen)==len(old)==6580
        for d in paired.values():
            d['before_accuracy']=d['before_correct']/d['n'];d['after_accuracy']=d['after_correct']/d['n']
        accepted=all(d['after_correct']>=d['before_correct'] for d in paired.values()) and sum(d['after_correct']-d['before_correct'] for d in paired.values())>0
        with Path('/run/lock/sysone-inference.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX);assert idle()
            if not accepted:
                command(['/usr/sbin/rmmod','sysone_r5_smoke']);command(['/usr/sbin/insmod',str(OLD_MODULE)]);swapped=False
            final=status()
        write('promotion.json',dict(completed=True,accepted=accepted,paired=paired,tau=config['tau'],model_weights_changed=False,r5_inference=True,linux_running=True,jtag_used=False,current_elf_sha256=config['elf_sha256'] if accepted else old_elf,module_sha256=new_module_sha,final_status=final,baseline_preserved=True))
        print('R5_CALIBRATION_COMPLETE accepted='+str(accepted),flush=True)
    except Exception as exc:
        # Roll back only when the R5 lifetime is conclusively idle. Otherwise retain
        # the existing kernel watchdog/quarantine and PL for diagnosis.
        rolled_back=False
        if swapped and (not CONTROL.exists() or idle()):
            if CONTROL.exists():command(['/usr/sbin/rmmod','sysone_r5_smoke'])
            command(['/usr/sbin/insmod',str(OLD_MODULE)]);rolled_back=True
        write('failure.json',dict(error=type(exc).__name__+': '+str(exc),rolled_back=rolled_back,status=status() if CONTROL.exists() else 'module absent',pl_retained=True))
        raise

if __name__=='__main__':main()
