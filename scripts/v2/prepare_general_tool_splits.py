"""Keep identical prompts and full schema sets together, preserving the old split."""
import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import shutil


def prompt_hash(text):
    return hashlib.sha256(' '.join(text.casefold().split()).encode()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    rows=[]
    for split in ('train','dev','schema-heldout-diagnostic'):
        rows.extend(json.loads(line) for line in (args.source/f'{split}.jsonl').read_text(encoding='utf-8').splitlines())
    if len({r['id'] for r in rows})!=len(rows):
        raise ValueError('duplicate source IDs')
    parent={r['schema_group']:r['schema_group'] for r in rows}
    def find(key):
        while parent[key]!=key:
            parent[key]=parent[parent[key]]
            key=parent[key]
        return key
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b:
            parent[max(a,b)]=min(a,b)
    first={}
    for row in rows:
        h=prompt_hash(row['query'])
        if h in first:
            union(row['schema_group'],first[h])
        else:
            first[h]=row['schema_group']
    splits={'train':[],'dev':[],'schema-heldout-diagnostic':[]}
    for row in rows:
        component=find(row['schema_group'])
        bucket=int(component[:8],16)%10
        split='dev' if bucket==0 else 'schema-heldout-diagnostic' if bucket==1 else 'train'
        splits[split].append({**row,'split_component':component,'prompt_hash':prompt_hash(row['query'])})
    prompts={k:{r['prompt_hash'] for r in v} for k,v in splits.items()}
    schemas={k:{r['schema_group'] for r in v} for k,v in splits.items()}
    overlaps={a+' / '+b:dict(exact_normalized_prompts=len(prompts[a]&prompts[b]),full_schema_sets=len(schemas[a]&schemas[b])) for a,b in itertools.combinations(splits,2)}
    if any(any(v.values()) for v in overlaps.values()):
        raise ValueError('split leakage remains')
    hashes={}
    for split,values in splits.items():
        path=args.out/f'{split}.jsonl'
        with path.open('w',encoding='utf-8') as stream:
            for row in sorted(values,key=lambda r:r['id']):
                stream.write(json.dumps(row,sort_keys=True)+'\n')
        hashes[split]=hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ('external-evaluation.jsonl','bfcl-answer-registry.json','training-overlap-exclusions.json','source-requests.json','xlam-access-receipt.json'):
        shutil.copyfile(args.source/name,args.out/name)
    shutil.copytree(args.source/'bfcl-python-checker',args.out/'bfcl-python-checker',ignore=shutil.ignore_patterns('__pycache__'))
    original=json.loads((args.source/'manifest.json').read_text())
    original.update(split_version=1,split_rule='Connected components of shared normalized prompts OR identical complete tool-schema sets',
        source_split_directory=str(args.source.resolve()),split_counts={k:len(v) for k,v in splits.items()},
        split_sha256=hashes,split_overlap_audit=overlaps,components=len({find(k) for k in parent}),
        largest_component_records=max(Counter(find(r['schema_group']) for r in rows).values()),
        limitations=['Individual tool identities and semantic paraphrases may still overlap across splits',
                     'Public BFCL/pretraining overlap remains unknown; no independent human blind test',
                     'Prior v0 pilot remains recorded against its original immutable data hashes'])
    original['training']['split_counts']=original['split_counts']
    original['training']['limitation']=original['limitations'][0]
    (args.out/'manifest.json').write_text(json.dumps(original,indent=2)+'\n')
    print(json.dumps(dict(out=str(args.out),splits=original['split_counts'],overlaps=overlaps,components=original['components']),indent=2))


if __name__=='__main__':
    main()
