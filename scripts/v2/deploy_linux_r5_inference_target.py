"""Deploy R5 control/heads while preserving the active encoder and model."""
from pathlib import Path
import fcntl,hashlib,importlib.util,json,os,subprocess,sys,time
HERE=Path(__file__).resolve().parent;REPO=Path('/home/ubuntu/system-one-fpga')
def require(ok,reason):
    if not ok:raise RuntimeError(reason)
def write(name,data):(HERE/name).write_text(json.dumps(data,indent=2)+'\n')
def cmd(value):Path('/sys/class/misc/sysone_r5_smoke/command').write_text(value+'\n')
def status():return Path('/sys/class/misc/sysone_r5_smoke/status').read_text()
def main():
    require(os.geteuid()==0 and os.environ.get('INVOCATION_ID'),'Root-local service required')
    with Path('/run/lock/sysone-inference.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        config=json.loads((HERE/'config.json').read_text())
        require(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==config['boot_id'],'Boot changed')
        require(not Path('/sys/module/sysone_r5_smoke').exists(),'R5 module already loaded')
        require(not list(Path('/sys/class/remoteproc').iterdir()),'Remoteproc owner exists')
        for name,digest in config['sha256'].items():require(hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest,'Changed '+name)
        sys.path.insert(0,str(REPO/'src'))
        from sysone.v2.kr260_link import Kr260Link
        from sysone.v2.kr260_runtime import discover_memory
        from sysone.v2 import ddr_image,eval_suite
        import numpy as np
        image=REPO/'export/v2/image/minilm-l12-v1-kr260'
        raw=(image/'minilm-l12-v1-kr260.img').read_bytes();machine=ddr_image.ImageMachine(raw)
        link=Kr260Link(memory=discover_memory())
        try:
            require(not link._r(0)&1,'PL is busy');link.verify_loaded_image(0x60000000,raw)
            initial_clock=link.clock_hz
        finally:link.close()
        spec=importlib.util.spec_from_file_location('r5client',HERE/'r5_inference_client.py');client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)
        manifest=json.loads((image/'manifest.json').read_text());wp=client.WordPiece.from_file(REPO/'export/v2/chain/minilm-l12-v1/tokenizer.json')
        subprocess.run(['/usr/sbin/insmod',str(HERE/'sysone_r5_smoke.ko')],check=True)
        module_loaded=True;successful=[]
        try:
            chain=client.build_chain(wp,['show me flights from denver to boston tomorrow'.split()],'slots',128)
            jobs=client.jobs_for(chain,'atis');print('Running first R5-controlled inference',flush=True)
            first=client.execute(chain,jobs,manifest);write('first-inference.json',first)
            require(first['predictions'][0]['label']=='atis_flight','Unexpected first intent')
            suite=json.loads((REPO/'build/v2/eval/minilm-l12-v1-matched.json').read_text())
            # A representative case from each dataset, plus longest ATIS slot
            # request, exercises every classifier head with real R5/PL traffic.
            selected=[];seen=set()
            for row in suite['cases']:
                dataset=row['chain']['dataset']
                if dataset not in seen:selected.append(row);seen.add(dataset)
            atis=[r for r in suite['cases'] if r['chain']['dataset']=='atis']
            selected.append(max(atis,key=lambda r:len(r['ids'])))
            for row in selected:
                c=eval_suite.chain(row);chain=client.build_chain(wp,[s.words for s in c.segments],c.task,128)
                jobs=client.jobs_for(chain,c.dataset);result=client.execute(chain,jobs,manifest)
                hidden=eval_suite.reference(row)
                for prediction,(name,rows,meta) in zip(result['predictions'],jobs):
                    logits,scales=machine.head_logits(hidden,name,np.asarray(rows));logits=np.asarray(logits).reshape(-1)
                    require(prediction['logits']==logits.tolist(),'R5 logits differ: '+row['id']+' '+name)
                    require(prediction['label_index']==int(np.argmax(logits*scales)),'R5 label differs')
                successful.append(dict(id=row['id'],dataset=c.dataset,tokens=len(chain.ids),head_jobs=len(jobs),encoder_clocks=result['encoder_clocks']))
                write('hardware-validation.json',dict(passed=True,cases=successful))
                print('PASS R5 '+row['id']+' '+str(len(jobs))+' head jobs',flush=True)
            # Replace only the CLI entry point after validation; preserve its
            # exact A53 predecessor for an immediate manual rollback.
            entry=Path('/usr/local/bin/sysone-infer');before=entry.read_bytes();(HERE/'sysone-infer-a53.before').write_bytes(before)
            entry.write_text('#!/bin/sh\nexec sudo /home/ubuntu/sysone-venv/bin/python '+str(HERE/'r5_inference_client.py')+' "$@"\n');entry.chmod(0o755)
            write('result.json',dict(passed=True,linux_running=True,r5_controls_pl=True,r5_computes_heads=True,
                app_reloaded=False,model_reloaded=False,pl_clock_hz=initial_clock,first_prediction=first['predictions'][0]['label'],
                hardware_cases=len(successful),all_reference_logits_and_labels_match=True,entrypoint=str(entry),
                module_loaded=True,r5_idle_between_requests=True,status=status(),jtag_used=False))
            print('R5_INFERENCE_DEPLOYMENT_PASS',flush=True)
        except Exception:
            # Never reset or unload the working PL on an uncertain DMA request.
            write('failure-state.json',dict(module_status=status(),pl_retained=True))
            raise
if __name__=='__main__':main()
