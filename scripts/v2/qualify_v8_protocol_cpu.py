"""Finite CPU development selection and disjoint qualification, no board writes."""
import argparse,hashlib,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.v8_benchmark_protocol_v2 import (ARMS,OUTPUT_BUDGET,cases,prompt,parse_output,qualification_manifest)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    import tokenizers
    from sysone.v2.qwen_tokenizer_v1 import Vocabulary
    v=Vocabulary(ROOT/'build/v2/qwen-fpga-decoder-v8/deployment')
    model=ROOT/'models/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q8_0.gguf'
    modelhash=sha(model)
    if modelhash!='9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031':raise RuntimeError('Model hash mismatch')
    rows=[]
    def evaluate(split,variant,items):
        phase=[]
        for case in items:
            for context,wire in ARMS:
                name=f'{split}-{variant}-{case["id"]}-{context}-{wire}'
                text,_=prompt(case['state'],case['step'],context,wire,variant)
                ids=v.encode_text(text)
                if len(ids)+OUTPUT_BUDGET>256:raise ValueError('Qualification input exceeds v8 context')
                path=args.out/(name+'.prompt.txt');path.write_text(text,encoding='utf-8')
                command=[str(ROOT/'build/v2/generation/windows/llama-completion.exe'),'-m',str(model),
                    '-f',str(path),'-n',str(OUTPUT_BUDGET),'-c','256','-ngl','0','--temp','0','--seed','0',
                    '--repeat-penalty','1','--no-conversation','--no-display-prompt','--no-escape','--no-warmup']
                started=time.monotonic();proc=subprocess.run(command,capture_output=True,timeout=120)
                (args.out/(name+'.stdout')).write_bytes(proc.stdout);(args.out/(name+'.stderr')).write_bytes(proc.stderr)
                if proc.returncode:raise RuntimeError('CPU generation failed: '+name)
                raw=proc.stdout.decode('utf-8').replace('\r\n','\n')
                terminal=' [end of text]' in raw
                # CLI presentation delimiter is retained in raw artifacts and
                # removed only to recover model text, not repair a model record.
                generated=raw.split(' [end of text]',1)[0] if terminal else raw.rstrip('\n')
                observed=None
                try:observed=list(parse_output(generated,wire,terminal=terminal))
                except ValueError:pass
                row=dict(id=name,case_id=case['id'],split=split,variant=variant,context=context,wire=wire,
                    prompt=text,prompt_ids=ids,generated_text=generated,terminal_eos=terminal,
                    observed=observed,expected=case['expected'],format_valid=observed is not None,
                    correct=observed==case['expected'],seconds=time.monotonic()-started,model_sha256=modelhash)
                rows.append(row);phase.append(row)
                with (args.out/'requests.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
                print(json.dumps({k:row[k] for k in ('id','format_valid','correct','generated_text')}),flush=True)
        return phase
    development=[]
    for variant in ('plain','demonstration'):development+=evaluate('development',variant,cases('development'))
    scores={variant:(sum(r['correct'] for r in development if r['variant']==variant),
                     sum(r['format_valid'] for r in development if r['variant']==variant)) for variant in ('plain','demonstration')}
    # Ties retain plain; select only on development responses.
    variant=max(('plain','demonstration'),key=lambda variant:scores[variant])
    manifest=qualification_manifest(variant)
    manifest['selection']=dict(development_scores=scores,selected_before_qualification=True)
    jobs=[]
    for case in manifest['cases']:
        for context,wire in ARMS:
            text,_=prompt(case['state'],case['step'],context,wire,variant)
            jobs.append(dict(id=f'{case["id"]}-{context}-{wire}',case_id=case['id'],context=context,wire=wire,
                prompt=text,prompt_ids=v.encode_text(text),expected=case['expected']))
    manifest['jobs']=jobs
    (args.out/'qualification-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    qualification=evaluate('qualification',variant,manifest['cases'])
    groups={}
    for context,wire in ARMS:
        rs=[r for r in qualification if (r['context'],r['wire'])==(context,wire)]
        groups[context+wire]=dict(cases=len(rs),format_valid=sum(r['format_valid'] for r in rs),
                                correct=sum(r['correct'] for r in rs))
    passed=all(g['format_valid']>=11 and g['correct']>=9 for g in groups.values())
    result=dict(backend='CPU llama.cpp Q8, not v8 activation arithmetic',variant=variant,
                groups=groups,passed=passed,manifest_sha256=sha(args.out/'qualification-manifest.json'))
    (args.out/'qualification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':main()
