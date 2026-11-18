"""Collect held-out accuracy and latency using the installed R5 inference path."""
from pathlib import Path
from collections import defaultdict
import hashlib,importlib.util,json,os,platform,struct,sys,time
if os.name=='posix':import fcntl
import numpy as np
HERE=Path(__file__).resolve().parent;REPO=Path('/home/ubuntu/system-one-fpga')
CLIENT=Path('/var/lib/sysone/r5-inference/deploy-v2/r5_inference_client.py')

def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def quantiles(values):
    a=np.asarray(values,dtype=np.float64)
    return dict(n=len(values),mean=float(a.mean()),p50=float(np.percentile(a,50)),
                p95=float(np.percentile(a,95)),p99=float(np.percentile(a,99)),min=float(a.min()),max=float(a.max())) if len(a) else None

def metrics(records,complete):
    groups=defaultdict(list)
    for row in records:groups[row['dataset']].append(row)
    output={}
    for dataset,rows in sorted(groups.items()):
        success=[r for r in rows if r['passed']]
        totals={k:sum(r['scores'][k] for r in success) for k in ['classification_n','classification_correct','slot_tokens','slot_tokens_correct','slot_tp','slot_fp','slot_fn','unscored_classification']}
        n=totals['classification_n'];den=2*totals['slot_tp']+totals['slot_fp']+totals['slot_fn']
        output[dataset]=dict(requests=len(rows),successful=len(success),errors=len(rows)-len(success),**totals,
            classification_accuracy=totals['classification_correct']/n if n else None,
            slot_span_f1=2*totals['slot_tp']/den if den else (1.0 if totals['slot_tokens'] else None),
            slot_token_accuracy=totals['slot_tokens_correct']/totals['slot_tokens'] if totals['slot_tokens'] else None,
            latency_ms={k:quantiles([r['latency_ms'][k] for r in success]) for k in ['end_to_end','service','ingress','pl_encoder','pl_request']})
    good=[r for r in records if r['passed']]
    return dict(complete=complete,requests=len(records),successful=len(good),errors=len(records)-len(good),
        backend='R5 controls PL and computes heads; Linux ingress and I/O',datasets=output,
        latency_ms={k:quantiles([r['latency_ms'][k] for r in good]) for k in ['end_to_end','service','ingress','pl_encoder','pl_request']},
        timing_scope='On-board perf_counter_ns; end-to-end starts before tokenization and ends after R5 completion/cleanup. Includes runtime checks, TCM preparation, firmware PM, PL, R5 heads, result copy and stop. Excludes lock wait, initial loading, SSH, scoring and log writes. PL cycles separately measured; no isolated R5-head timer or WCET claim.',
        percentile_method='NumPy linear interpolation',model_changed=False,r5_inference=True,jtag_used=False)

def save_summary(records,complete=False):
    temp=HERE/'summary.tmp';temp.write_text(json.dumps(metrics(records,complete),indent=2)+'\n');os.replace(temp,HERE/'summary.json')

def score(predictions,jobs,chain,original,labels,spans):
    inv={v:k for k,v in chain.kept.items()};totals=dict.fromkeys(['classification_n','classification_correct','slot_tokens','slot_tokens_correct','slot_tp','slot_fp','slot_fn','unscored_classification'],0)
    slot_groups=defaultdict(list);details=[]
    for p,(name,rows,meta) in zip(predictions,jobs):
        record={k:v for k,v in p.items() if k!='logits'}
        record['logits_sha256']=hashlib.sha256(struct.pack('<'+'i'*len(p['logits']),*p['logits'])).hexdigest()
        if name.startswith('intent.'):
            gold=original.segments[inv[p['segment']]].intent
        elif name.startswith('pair.'):gold=original.pair_label
        else:
            slot_groups[(name,p['segment'])].append(p['label']);details.append(record);continue
        if gold==-100:totals['unscored_classification']+=1;record['expected']=None;record['correct']=None
        else:
            record['expected']=labels[name][gold];record['correct']=p['label_index']==gold
            totals['classification_n']+=1;totals['classification_correct']+=int(record['correct'])
        details.append(record)
    for (name,segment),predicted in slot_groups.items():
        tags=original.segments[inv[segment]].tags
        if tags is None:continue
        gold=[labels[name][tag] for tag in tags[:len(predicted)]]
        if len(gold)!=len(predicted):raise RuntimeError('Slot annotation alignment mismatch')
        ps=spans(predicted);gs=spans(gold)
        totals['slot_tokens']+=len(gold);totals['slot_tokens_correct']+=sum(a==b for a,b in zip(predicted,gold))
        totals['slot_tp']+=len(ps&gs);totals['slot_fp']+=len(ps-gs);totals['slot_fn']+=len(gs-ps)
        # Preserve word-level gold labels alongside the actual R5 predictions.
        matches=[p for p in details if p['head']==name and p['segment']==segment]
        for p,expected in zip(matches,gold):p['expected']=expected;p['correct']=p['label']==expected
    return totals,details

def main():
    if os.geteuid()!=0:raise RuntimeError('Root required')
    config=json.loads((HERE/'config.json').read_text())
    if digest(HERE/'cases.json')!=config['cases_sha256'] or digest(CLIENT)!=config['client_sha256']:raise RuntimeError('Evaluation/client changed')
    require_boot=config['boot_id'];boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if boot!=require_boot:raise RuntimeError('Boot changed')
    if config['elf_sha256'] not in Path('/sys/class/misc/sysone_r5_smoke/status').read_text():raise RuntimeError('Wrong R5 firmware')
    suite=json.loads((HERE/'cases.json').read_text());sys.path.insert(0,str(REPO/'src'))
    from sysone.v2 import eval_suite
    from sysone.v2.host_heads import spans
    from sysone.v2.kr260_link import Kr260Link
    from sysone.v2.kr260_runtime import discover_memory
    spec=importlib.util.spec_from_file_location('r5client',CLIENT);client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)
    image=REPO/'export/v2/image/minilm-l12-v1-kr260';manifest=json.loads((image/'manifest.json').read_text())
    labels={h['kind']+'.'+h['name']:h['labels'] for h in manifest['heads']}
    if labels!=suite['head_labels'] or digest(image/'minilm-l12-v1-kr260.img')!=suite['model_sha256']:raise RuntimeError('Model or labels changed')
    tokenizer=REPO/'export/v2/chain/minilm-l12-v1/tokenizer.json'
    if digest(tokenizer)!=suite['tokenizer_sha256']:raise RuntimeError('Tokenizer changed')
    wp=client.WordPiece.from_file(tokenizer);records=[]
    with Path('/run/lock/sysone-inference.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        # Read-only verification; operational RUN remains exclusively in R5.
        link=Kr260Link(memory=discover_memory())
        try:link.verify_loaded_image(0x60000000,(image/'minilm-l12-v1-kr260.img').read_bytes());clock=link.clock_hz
        finally:link.close()
        (HERE/'metadata.json').write_text(json.dumps(dict(boot_id=boot,kernel=platform.release(),model_sha256=suite['model_sha256'],cases_sha256=config['cases_sha256'],seed=suite['seed'],split=suite['split'],clock_hz=clock,planned_requests=len(suite['cases']),r5_firmware_sha256=config['elf_sha256'],linux_running=True,pl_reloaded=False,model_reloaded=False),indent=2)+'\n')
        with (HERE/'requests.jsonl').open('x') as journal:
            for row in suite['cases']:
                start=time.perf_counter_ns();original=eval_suite.chain(row)
                chain=client.build_chain(wp,[s.words for s in original.segments],original.task,128)
                if chain.ids!=row['ids']:raise RuntimeError('Tokenization mismatch '+row['id'])
                jobs=client.jobs_for(chain,row['dataset']);ready=time.perf_counter_ns()
                try:
                    result=client.execute(chain,jobs,manifest);finish=time.perf_counter_ns()
                    totals,predictions=score(result['predictions'],jobs,chain,original,labels,spans)
                    record=dict(id=row['id'],dataset=row['dataset'],passed=True,tokens=len(chain.ids),head_jobs=len(jobs),
                        ids_sha256=row['ids_sha256'],clock_hz=result['clock_hz'],encoder_clocks=result['encoder_clocks'],request_clocks=result['request_clocks'],
                        latency_ms=dict(end_to_end=(finish-start)/1e6,service=(finish-ready)/1e6,ingress=(ready-start)/1e6,pl_encoder=result['encoder_clocks']/result['clock_hz']*1000,pl_request=result['request_clocks']/result['clock_hz']*1000),
                        scores=totals,predictions=predictions,r5_trace=result['trace'],r5_cleanup_status=result['r5_cleanup_status'])
                except Exception as exc:
                    record=dict(id=row['id'],dataset=row['dataset'],passed=False,error=type(exc).__name__+': '+str(exc))
                    records.append(record);journal.write(json.dumps(record)+'\n');journal.flush();save_summary(records);raise
                records.append(record);journal.write(json.dumps(record)+'\n');journal.flush()
                if len(records)%25==0:
                    os.fsync(journal.fileno());save_summary(records);print(f'Collected {len(records)}/{len(suite["cases"])} fresh R5 requests',flush=True)
            os.fsync(journal.fileno())
    save_summary(records,complete=True)
    print('R5_HELDOUT_COLLECTION_PASS '+str(len(records)),flush=True)

if __name__=='__main__':main()
