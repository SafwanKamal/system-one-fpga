"""Offline audit of frozen outputs plus finite pinned Q8 CPU prompt controls."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.v8_benchmark import parse_record,chat,chain_prompt,chains


def main():
    out=ROOT/'build/v2/v8-diagnosis-v1';out.mkdir(parents=True,exist_ok=True)
    rows=[json.loads(line) for line in (ROOT/'build/v2/v8-baseline-v1/progress-check-01/requests.jsonl').read_text().splitlines()]
    audit=[]
    for row in rows:
        decoded=None
        try:decoded=parse_record(row['generated_text']+('\n' if row['wire']=='E' else ''),row['wire'])
        except ValueError:pass
        audit.append(dict(id=row['id'],wire=row['wire'],raw=row['generated_text'],
            expected=row['expected'],terminal_eos=bool(row['eos_positions']),
            valid_if_eos_frames_record=decoded is not None,
            correct_if_eos_frames_record=list(decoded)==row['expected'] if decoded else False))
    (out/'offline-format-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    c=chains('development',1,4)[0]
    cases=[]
    for context in ('H','J','C'):
        for wire in ('A','E'):
            prompt,_=chain_prompt(c,0,c['initial'],context,wire,[])
            cases.append(dict(id=f'original-{context}-{wire}',prompt=prompt,wire=wire))
    cases.extend([
        dict(id='literal-json',prompt=chat('Return exactly ["ok","A",4]. Do not add text.','Return the specified array.'),wire='A'),
        dict(id='clear-json',prompt=chat('Reply with one JSON array. Example format: ["ok","A",7]. No labels or Markdown.','A has 31 counts and B has 66 counts. Add 3 to B. Return [status,entity,new_count].'),wire='A'),
        dict(id='clear-enum',prompt=chat('Reply with three fields separated by spaces: statusID entity value. 0 means ok. No other text.','A=31 B=66. Add 3 to B.'),wire='E')])
    (out/'cpu-cases.json').write_text(json.dumps(cases,indent=2)+'\n')
    model=ROOT/'models/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q8_0.gguf'
    digest=hashlib.sha256(model.read_bytes()).hexdigest()
    assert digest=='9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031'
    results=[]
    for case in cases:
        path=out/(case['id']+'.prompt.txt');path.write_text(case['prompt'],encoding='utf-8')
        command=[str(ROOT/'build/v2/generation/windows/llama-completion.exe'),'-m',str(model),
            '-f',str(path),'-n','24','-c','256','-ngl','0','--temp','0','--seed','0',
            '--repeat-penalty','1','--no-conversation','--no-display-prompt','--no-escape','--no-warmup']
        proc=subprocess.run(command,capture_output=True,timeout=120)
        (out/(case['id']+'.stdout')).write_bytes(proc.stdout)
        (out/(case['id']+'.stderr')).write_bytes(proc.stderr)
        results.append(dict(id=case['id'],exit=proc.returncode,stdout=proc.stdout.decode('utf-8',errors='replace'),
            command=command,model_sha256=digest,backend='CPU llama.cpp Q8 weights; not v8 block32 activation arithmetic'))
        (out/'cpu-results.json').write_text(json.dumps(results,indent=2)+'\n')
        print(json.dumps(results[-1]),flush=True)
        if proc.returncode:raise RuntimeError('CPU diagnostic failed')


if __name__=='__main__':main()
