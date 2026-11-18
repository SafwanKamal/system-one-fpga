"""Pin general tool-calling sources. Raw BFCL is evaluation-only, never training.

All source rows remain available, including out-of-profile cases. Dataset terms
must be accepted through the publisher; access failures are retained, not bypassed.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
BFCL_REV='6ea57973c7a6097fd7c5915698c54c17c5b1b6c8'
XLAM_REV='26d14ebfe18b1f7b524bd39b404b50af5dc97866'
CATEGORIES=('simple_python','multiple','parallel','parallel_multiple','irrelevance')


def dump(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def question_text(row):
    return '\n'.join(message.get('content','') for turn in row['question'] for message in turn if message['role']=='user')


def prompt_identity(text):
    return hashlib.sha256(' '.join(text.casefold().split()).encode()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    raw=args.out/'raw'
    raw.mkdir()
    requests=[]
    def fetch(path):
        url=f'https://raw.githubusercontent.com/ShishirPatil/gorilla/{BFCL_REV}/{path}'
        receipt=dict(source='official BFCL repository',url=url)
        requests.append(receipt)
        try:
            with urllib.request.urlopen(url,timeout=40) as response:
                content=response.read()
            target=raw/path
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(content)
            receipt.update(status='ok',bytes=len(content),sha256=hashlib.sha256(content).hexdigest())
            return content.decode('utf-8')
        except Exception as exc:
            receipt.update(status='failed',error_type=type(exc).__name__,http_status=getattr(exc,'code',None))
            raise
        finally:
            dump(args.out/'source-requests.json',requests)
    fetch('LICENSE')
    fetch('berkeley-function-call-leaderboard/README.md')
    cases=[]
    schemas=Counter()
    base='berkeley-function-call-leaderboard/bfcl_eval/data/'
    answer_registry={}
    for category in CATEGORIES:
        filename=f'BFCL_v4_{category}.json'
        content=fetch(base+filename)
        rows=[json.loads(x) for x in content.splitlines() if x.strip()]
        # BFCL irrelevance means no appropriate tool, not a new inferred reason.
        if category!='irrelevance':
            answers=[json.loads(x) for x in fetch(base+'possible_answer/'+filename).splitlines() if x.strip()]
            by_id={x['id']:x['ground_truth'] for x in answers}
            if len(by_id)!=len(answers) or set(by_id)!={x['id'] for x in rows}:
                raise ValueError('question/answer IDs differ')
        else:
            by_id={x['id']:[] for x in rows}
        for row in rows:
            text=question_text(row)
            cases.append(dict(id=row['id'],category=category,query=text,tools=row['function'],
                source='BFCL_v4',source_revision=BFCL_REV,raw_question=row['question'],
                prompt_hash=prompt_identity(text),scope='external_evaluation_only'))
            answer_registry[row['id']]=by_id[row['id']]
            for f in row['function']:
                for spec in f.get('parameters',{}).get('properties',{}).values():
                    schemas[str(spec.get('type','missing'))]+=1
    if len({c['id'] for c in cases})!=len(cases):
        raise ValueError('duplicate evaluation IDs')
    with (args.out/'external-evaluation.jsonl').open('w',encoding='utf-8') as stream:
        for case in cases:
            stream.write(json.dumps(case,sort_keys=True)+'\n')
    dump(args.out/'bfcl-answer-registry.json',answer_registry)
    # Keep gold alternatives separate. Do not mistake all allowed alternatives
    # for one canonical answer, or execute arbitrary generated Python calls.
    manifest=dict(domain='general tool/function calling, explicitly selected by user',
        bfcl_revision=BFCL_REV,cases=len(cases),categories=dict(Counter(c['category'] for c in cases)),
        parameter_type_occurrences=dict(schemas),training=[],
        evaluator_status='official BFCL matching required; answers contain allowed value alternatives',
        cold_model_overlap_unknown=True,independent_human_blind_test=False,
        maintenance_pilot='diagnostic only; not evidence selecting a general tool caller',
        profile_policy='Keep every request; publish exclusions/profile failures separately; no silent truncation')
    dump(args.out/'manifest.json',manifest)
    from huggingface_hub import hf_hub_download
    receipt=dict(repo='Salesforce/xlam-function-calling-60k',revision=XLAM_REV,
                 filename='xlam_function_calling_60k.json',repo_type='dataset')
    try:
        path=Path(hf_hub_download(receipt['repo'],receipt['filename'],repo_type='dataset',revision=XLAM_REV))
        receipt.update(status='ok',path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        data=json.loads(path.read_text(encoding='utf-8'))
        eval_hashes={c['prompt_hash'] for c in cases}
        excluded=[]
        groups={}
        for record in data:
            query=record['query']
            if not isinstance(query,str):
                raise ValueError('expected query string')
            if prompt_identity(query) in eval_hashes:
                excluded.append(dict(id=record['id'],reason='exact_normalized_prompt_overlap_with_external_eval'))
                continue
            tools=json.loads(record['tools']) if isinstance(record['tools'],str) else record['tools']
            answers=json.loads(record['answers']) if isinstance(record['answers'],str) else record['answers']
            key=hashlib.sha256(json.dumps(tools,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            groups.setdefault(key,[]).append(dict(id='xlam_'+str(record['id']),query=query,tools=tools,answers=answers,
                schema_group=key,scope='task_training_or_development',source_revision=XLAM_REV))
        splits={'train':[],'dev':[],'schema-heldout-diagnostic':[]}
        # Entire identical tool-schema groups are assigned together; train
        # duplicates can never cross splits by sharing the same full schema.
        for key,values in groups.items():
            bucket=int(key[:8],16)%10
            split='dev' if bucket==0 else 'schema-heldout-diagnostic' if bucket==1 else 'train'
            splits[split].extend(values)
        for split,values in splits.items():
            with (args.out/f'{split}.jsonl').open('w',encoding='utf-8') as stream:
                for value in values:
                    stream.write(json.dumps(value,sort_keys=True)+'\n')
        dump(args.out/'training-overlap-exclusions.json',excluded)
        manifest['training']=dict(source=receipt,split_counts={k:len(v) for k,v in splits.items()},
            schema_groups=len(groups),excluded_prompt_overlaps=len(excluded),
            limitation='Full schema-set grouping is not disjoint individual-tool identity or semantic paraphrase grouping; stronger overlap audit remains required')
        dump(args.out/'manifest.json',manifest)
    except Exception as exc:
        receipt.update(status='failed',error_type=type(exc).__name__,http_status=getattr(getattr(exc,'response',None),'status_code',None))
    dump(args.out/'xlam-access-receipt.json',receipt)
    print(json.dumps(dict(out=str(args.out),cases=len(cases),xlam_status=receipt['status']),indent=2))


if __name__=='__main__':
    main()
