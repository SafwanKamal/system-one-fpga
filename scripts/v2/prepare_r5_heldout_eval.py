"""Select fresh held-out requests without training or altering the model."""
from pathlib import Path
from dataclasses import asdict
from collections import Counter,defaultdict
import hashlib,importlib.util,json,os,random,struct,sys
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'build/v2/typed200-r5-heldout-eval-v1'
SEED=20261017;PER_DATASET=100

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def ids_digest(ids):return hashlib.sha256(struct.pack('<'+'H'*len(ids),*ids)).hexdigest()

def main():
    BASE.mkdir(exist_ok=False);os.environ['SYSONE_REPO']=str(ROOT)
    sys.path.insert(0,str(ROOT/'src'))
    from sysone.v2.chain_data import load_all
    from sysone.v2.host_heads import build_chain
    from sysone.v2.wordpiece import WordPiece
    anchor=ROOT/'docs/research/2026-10-17-typed200-linux-r5-inference-validation.json'
    (BASE/'prior-validation.json').write_bytes(anchor.read_bytes())
    (BASE/'preservation-before.json').write_text(json.dumps(dict(anchor=anchor.relative_to(ROOT).as_posix(),anchor_sha256=sha(anchor)),indent=2)+'\n')
    model=ROOT/'export/v2/image/minilm-l12-v1-kr260';manifest=json.loads((model/'manifest.json').read_text())
    tok=ROOT/'export/v2/chain/minilm-l12-v1/tokenizer.json';wp=WordPiece.from_file(tok)
    print('Loading existing dataset splits',flush=True);corpus=load_all(hwu=True)
    labels={h['kind']+'.'+h['name']:h['labels'] for h in manifest['heads']}
    for prefix,mapping in [('intent',corpus.intent_labels),('slots',corpus.tag_labels),('pair',corpus.pair_labels)]:
        for name,names in mapping.items():assert labels[prefix+'.'+name]==names,(prefix,name)
    old=json.loads((ROOT/'build/v2/eval/minilm-l12-v1-matched.json').read_text())
    blocked_ids={ids_digest(row['ids']) for row in old['cases']}
    normalize=lambda words:' '.join(wp.normalize(' '.join(words)).split())
    old_segments={normalize(s['words']) for row in old['cases'] for s in row['chain']['segments']}
    print('Excluding encoded inputs from training/development and the prior350',flush=True)
    for index,c in enumerate(corpus.train+corpus.dev):
        chain=build_chain(wp,[s.words for s in c.segments],c.task,128)
        blocked_ids.add(ids_digest(chain.ids))
    spec=importlib.util.spec_from_file_location('r5client',ROOT/'scripts/v2/r5_inference_client.py');client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)
    groups=defaultdict(list)
    for index,c in enumerate(corpus.test):groups[c.dataset].append((index,c))
    cases=[];selection={};selected_ids=set();rng=random.Random(SEED)
    for dataset,rows in sorted(groups.items()):
        rng.shuffle(rows);counts=Counter();chosen=0
        for index,c in rows:
            if any(normalize(s.words) in old_segments for s in c.segments):counts['previous_segment_overlap']+=1;continue
            chain=build_chain(wp,[s.words for s in c.segments],c.task,128);digest=ids_digest(chain.ids)
            if digest in blocked_ids:counts['train_dev_or_previous_input_overlap']+=1;continue
            if digest in selected_ids:counts['duplicate_selected_input']+=1;continue
            try:client.pack_request(chain,client.jobs_for(chain,c.dataset))
            except ValueError:counts['invalid_request_shape']+=1;continue
            cases.append(dict(id=f'{dataset}:test:{index}',dataset=dataset,chain=asdict(c),ids=chain.ids,ids_sha256=digest))
            selected_ids.add(digest);chosen+=1
            if chosen==PER_DATASET:break
        assert chosen==PER_DATASET,(dataset,chosen,len(rows),dict(counts))
        selection[dataset]=dict(test_pool=len(rows),selected=chosen,skipped_before_selection=dict(counts))
        print(dataset+': '+str(chosen)+' fresh cases',flush=True)
    random.Random(SEED+1).shuffle(cases)
    assert len(cases)==700 and len(selected_ids)==700 and not selected_ids & blocked_ids
    payload=dict(schema='r5-heldout-evaluation-v1',seed=SEED,per_dataset=PER_DATASET,split='test',
        model_sha256=manifest['sha256'],tokenizer_sha256=sha(tok),head_labels=labels,cases=cases)
    suite=BASE/'cases.json';suite.write_text(json.dumps(payload,ensure_ascii=True,separators=(',',':'))+'\n')
    receipt=dict(passed=True,cases=len(cases),seed=SEED,per_dataset=PER_DATASET,
        selection=selection,train_cases=len(corpus.train),dev_cases=len(corpus.dev),
        encoded_train_dev_previous_inputs_excluded=True,previous_reference_segments_excluded=True,
        duplicate_selected_inputs_excluded=True,previous_reference_cases=len(old['cases']),
        cases_sha256=sha(suite),model_unchanged=True,labels_match_model=True,
        interpretation='Fresh relative to the frozen350; existing held-out test splits, not a newly sourced dataset')
    (BASE/'selection.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS selected700 unique held-out cases; no train/dev/previous encoded-input overlap',flush=True)

if __name__=='__main__':main()
