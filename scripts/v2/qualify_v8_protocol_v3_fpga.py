"""Small v3 protocol qualification on the existing v8 image. No deployment writes."""
import argparse,hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True
from sysone.v2.v8_benchmark_protocol_v3 import parse_output,OUTPUT_BUDGET
from run_v8_benchmark import Session,fixture,package_identity,dump


def infer(session,job):
    e,v=session.engine,session.vocab
    tick=time.monotonic();ids=v.encode_text(job['prompt'])
    if ids!=job['prompt_ids']:raise RuntimeError('Pinned tokenizer differs from frozen CPU input IDs')
    if len(ids)+OUTPUT_BUDGET>e.context:raise RuntimeError('Qualification prompt outside context')
    e.begin_prefix(ids,enabled=False)
    for pos in range(0,len(ids),e.prefill_batch_size):
        group=ids[pos:pos+e.prefill_batch_size]
        token=e.prefill_batch(group,pos,logits=pos+len(group)==len(ids))
    prefill=time.monotonic()-tick;raw=b'';generated=[];parsed=None;terminal=False;decode=time.monotonic()
    for index in range(OUTPUT_BUDGET):
        generated.append(token);raw+=v.piece(token);terminal=token in e.manifest['eos_ids']
        try:parsed=list(parse_output(raw.decode('utf-8'),job['wire'],terminal=terminal,candidate=job['candidate']))
        except (ValueError,UnicodeDecodeError):parsed=None
        if parsed is not None or terminal:break
        if index+1<OUTPUT_BUDGET:token=e.step(token,len(ids)+index,logits=True)
    return dict(id=job['id'],case_id=job['case_id'],context=job['context'],wire=job['wire'],
        prompt_ids=ids,generated_ids=generated,generated_text=raw.decode('utf-8',errors='replace'),
        terminal_eos=terminal,observed=parsed,expected=job['expected'],format_valid=parsed is not None,
        correct=parsed==job['expected'],prefill_seconds=prefill,decode_seconds=time.monotonic()-decode,
        seconds=time.monotonic()-tick,prefix_tokens_reused=0,
        backend='FPGA v8 Q8 weights/block32 INT8 inputs; CPU does no model arithmetic')


def main():
    import fcntl
    ap=argparse.ArgumentParser();ap.add_argument('--package',type=Path,required=True)
    ap.add_argument('--manifest',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    frozen=json.loads((ROOT/'source-sha256.json').read_text())
    for name,digest in frozen.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('Frozen qualification file changed: '+name)
    manifest=json.loads(args.manifest.read_text());lock=Path('/run/lock/sysone-inference.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    before=package_identity(args.package);dump(args.out/'deployment-before.json',before)
    session=None;rows=[]
    try:
        session=Session(args.package);session.package=args.package
        dump(args.out/'fixture-before.json',fixture(session))
        dump(args.out/'status.json',dict(stage='running',completed=0))
        for job in manifest['jobs']:
            dump(args.out/'intent.json',job)
            row=infer(session,job);rows.append(row)
            with (args.out/'requests.jsonl').open('a') as f:f.write(json.dumps(row)+'\n');f.flush()
            dump(args.out/'status.json',dict(stage='running',completed=len(rows),last_id=row['id']))
            print(json.dumps({k:row[k] for k in ('id','format_valid','correct','generated_text')}),flush=True)
        dump(args.out/'fixture-after.json',fixture(session))
        after=package_identity(args.package);dump(args.out/'deployment-after.json',after)
        if before!=after:raise RuntimeError('Deployment identity changed')
        groups={}
        for context,wire in manifest['arms']:
            rs=[r for r in rows if (r['context'],r['wire'])==(context,wire)]
            groups[context+wire]=dict(cases=len(rs),format_valid=sum(r['format_valid'] for r in rs),correct=sum(r['correct'] for r in rs))
        gate=manifest['gates']
        passed=all(g['cases']==gate['per_arm_cases'] and g['format_valid']>=gate['per_arm_min_format_valid']
            and g['correct']>=gate['per_arm_min_semantic_correct'] for g in groups.values())
        result=dict(passed=passed,groups=groups,deployment_unchanged=True,
                    full_sweep_started=False,manifest_sha256=hashlib.sha256(args.manifest.read_bytes()).hexdigest())
        dump(args.out/'qualification.json',result)
        dump(args.out/'status.json',dict(stage='complete',completed=len(rows),qualification_passed=passed))
        print(json.dumps(result),flush=True)
    except Exception as exc:
        dump(args.out/'status.json',dict(stage='attention',completed=len(rows),error_type=type(exc).__name__,error=str(exc)))
        raise
    finally:
        if session is not None:session.close()
        lock.close()


if __name__=='__main__':main()
