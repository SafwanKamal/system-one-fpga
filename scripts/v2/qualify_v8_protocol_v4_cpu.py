"""V4 development-only format selection followed by fresh frozen qualification."""
import argparse,hashlib,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.v8_benchmark_protocol_v4 import (ARMS,CANDIDATES,OUTPUT_BUDGET,cases,prompt,
    parse_output,qualification_manifest,evaluate,response_prefix)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--development-only',action='store_true');ap.add_argument('--manifest',type=Path)
    args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    import tokenizers
    from sysone.v2.qwen_tokenizer_v1 import Vocabulary
    vocab=Vocabulary(ROOT/'build/v2/qwen-fpga-decoder-v8/deployment')
    model=ROOT/'models/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q8_0.gguf'
    digest=sha(model)
    if digest!='9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031':raise RuntimeError('Pinned model differs')
    source_names=['src/sysone/v2/v8_benchmark_protocol_v4.py','scripts/v2/qualify_v8_protocol_v4_cpu.py']
    sources={name:sha(ROOT/name) for name in source_names}
    (args.out/'source-provenance.json').write_text(json.dumps(sources,indent=2)+'\n')

    def run(job,split,candidate):
        name=f'{split}-{candidate}-{job["id"]}'
        path=args.out/(name+'.prompt.txt');path.write_text(job['prompt'],encoding='utf-8')
        if len(job['prompt_ids'])+OUTPUT_BUDGET>256:raise RuntimeError('Context limit exceeded')
        command=[str(ROOT/'build/v2/generation/windows/llama-completion.exe'),'-m',str(model),
            '-f',str(path),'-n',str(OUTPUT_BUDGET),'-c','256','-ngl','0','--temp','0','--seed','0',
            '--repeat-penalty','1','--no-conversation','--no-display-prompt','--no-escape','--no-warmup']
        tick=time.monotonic();proc=subprocess.run(command,capture_output=True,timeout=120)
        (args.out/(name+'.stdout')).write_bytes(proc.stdout);(args.out/(name+'.stderr')).write_bytes(proc.stderr)
        if proc.returncode:raise RuntimeError('CPU diagnostic failed: '+name)
        raw=proc.stdout.decode('utf-8').replace('\r\n','\n');terminal=' [end of text]' in raw
        suffix=raw.split(' [end of text]',1)[0] if terminal else raw.rstrip('\n')
        text=job['response_prefix']+suffix
        parsed=None
        try:parsed=list(parse_output(text,job['wire'],terminal=terminal,candidate=candidate))
        except ValueError:pass
        row=dict(job,split=split,variant=candidate,generated_text=text,generated_suffix_text=suffix,terminal_eos=terminal,
            observed=parsed,format_valid=parsed is not None,correct=parsed==job['expected'],
            seconds=time.monotonic()-tick,model_sha256=digest,backend='CPU llama.cpp Q8, not FPGA activation arithmetic')
        with (args.out/'requests.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        print(json.dumps({k:row[k] for k in ('id','split','variant','format_valid','correct','generated_text')}),flush=True)
        return row

    def jobs(items,candidate):
        result=[]
        for case in items:
            for context,wire in ARMS:
                text,_=prompt(case['state'],case['step'],context,wire,candidate)
                result.append(dict(id=f'{case["id"]}-{context}-{wire}',case_id=case['id'],context=context,
                    wire=wire,candidate=candidate,prompt=text,prompt_ids=vocab.encode_text(text),expected=case['expected'],
                    response_prefix=response_prefix(case['step'],candidate)))
        return result

    def finish(manifest,qualification,manifest_path):
        groups,operations,passed=evaluate(qualification,manifest['gates'])
        result=dict(backend='CPU llama.cpp Q8, not v8 activation arithmetic',variant=manifest['variant'],groups=groups,
                    passed=passed,operations=operations,manifest_sha256=sha(manifest_path),full_sweep_started=False)
        (args.out/'qualification.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2),flush=True)

    if args.manifest:
        manifest=json.loads(args.manifest.read_text())
        if any(sha(ROOT/n)!=h for n,h in manifest['source_sha256'].items()):raise RuntimeError('Frozen sources changed')
        manifest_path=args.out/'qualification-manifest.json'
        manifest_path.write_bytes(args.manifest.read_bytes())
        qualification=[run(job,'qualification',manifest['variant']) for job in manifest['jobs']]
        finish(manifest,qualification,manifest_path)
        return

    development=[]
    for candidate in CANDIDATES:
        for job in jobs(cases('development'),candidate):development.append(run(job,'development',candidate))
    scores={}
    for candidate in CANDIDATES:
        rs=[r for r in development if r['variant']==candidate]
        arms={c+w:[r for r in rs if (r['context'],r['wire'])==(c,w)] for c,w in ARMS}
        scores[candidate]=dict(min_arm_correct=min(sum(r['correct'] for r in rs if f'-{op}-' in r['case_id'])/sum(f'-{op}-' in r['case_id'] for r in rs) for op in ('set','add','copy','conditional','missing','error')),
            min_arm_format=min(sum(r['format_valid'] for r in v) for v in arms.values()),
            total_correct=sum(r['correct'] for r in rs),total_format=sum(r['format_valid'] for r in rs),
            mean_prompt_tokens=sum(len(r['prompt_ids']) for r in rs)/len(rs),
            arms={a:dict(correct=sum(r['correct'] for r in v),format_valid=sum(r['format_valid'] for r in v)) for a,v in arms.items()})
    def rank(candidate):
        s=scores[candidate]
        return s['min_arm_correct'],s['min_arm_format'],s['total_correct'],s['total_format'],-s['mean_prompt_tokens']
    selected=max(CANDIDATES,key=rank)
    manifest=qualification_manifest(selected)
    manifest['selection']=dict(policy='max worst-operation semantic fraction, format count, total correct, then fewer prompt tokens; ties keep first candidate',
                               development_scores=scores,selected_before_qualification=True)
    manifest['source_sha256']=sources
    manifest['jobs']=jobs(manifest['cases'],selected)
    for index in (12,14,20,24):
        original=manifest['jobs'][index]
        manifest['jobs'].append(dict(original,id=original['id']+'-repeat',repeat_of=original['id']))
    for job in manifest['jobs']:
        if len(job['prompt_ids'])+OUTPUT_BUDGET>256:raise RuntimeError('Frozen qualification context exceeds limit')
    manifest_path=args.out/'qualification-manifest.json'
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    (args.out/'selection.json').write_text(json.dumps(manifest['selection'],indent=2)+'\n')
    if any(sha(ROOT/n)!=h for n,h in sources.items()):raise RuntimeError('Protocol changed during selection')
    if args.development_only:
        print(json.dumps(dict(selected=selected,development_scores=scores,qualification_run=False)),flush=True)
        return
    qualification=[run(job,'qualification',selected) for job in manifest['jobs']]
    finish(manifest,qualification,manifest_path)


if __name__=='__main__':main()
