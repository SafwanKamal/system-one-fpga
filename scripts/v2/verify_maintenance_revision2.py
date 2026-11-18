"""Recompute every recorded verdict, prompt budget and SFT mask without inference."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from maintenance_revision2 import verify,verify_parent,read_rows,dump
from sysone.v2.maintenance.schema import parse
from sysone.v2.maintenance.dataset import score


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--work',type=Path,required=True);a=ap.parse_args()
    verify(a.work);parent=verify_parent()
    data={s:{c['id']:c for c in read_rows(a.work/(s+'.jsonl'))} for s in ('train','tuning','audit')}
    jobs={(r['id'],r['mode']):r for r in read_rows(a.work/'frozen-jobs.jsonl')}
    total=0;actual_ids=0;counts={}
    for name,split in (('rules','audit'),('tfidf','audit'),('minilm','audit'),
                       ('qwen-tuning-zero','tuning'),('qwen-tuning-examples','tuning'),('qwen-audit','audit')):
        folder=a.work/name
        rows=read_rows(folder/('predictions.jsonl' if name.startswith('qwen') else 'audit-predictions.jsonl'))
        expected=list(data[split]) if split=='audit' else json.loads((a.work/'tuning-selection-ids.json').read_text())
        if [r['id'] for r in rows]!=expected:raise RuntimeError('Attempt lineage/order mismatch: '+name)
        for row in rows:
            case=data[split][row['id']]
            try:
                ast=parse(row['raw_output'],case['catalog']);r=score(case,ast)
                correct,accepted,valid=r['correct'],r['accepted'],True
            except (ValueError,TypeError,KeyError,IndexError):correct,accepted,valid=False,False,False
            if (correct,accepted,valid)!=(row['correct'],row['accepted'],row['valid']):
                raise RuntimeError('Verdict mismatch: '+row['id'])
            if name.startswith('qwen'):
                job=jobs[(row['id'],row['mode'])]
                if row['actual_prompt_ids']!=job['prompt_ids'] or len(job['prompt_ids'])+256>1024:
                    raise RuntimeError('Prompt lineage/budget mismatch')
                if row['generated_tokens']>256:raise RuntimeError('Generation exceeds reservation')
                actual_ids+=1
            total+=1
        counts[name]=len(rows)
    selection=json.loads((a.work/'selection.json').read_text())
    stats=selection['tuning_stats']
    selected=max(('zero','examples'),key=lambda m:(stats[m]['correct'],stats[m]['valid']))
    if selected!=selection['selected']:raise RuntimeError('Prompt-selection mismatch')
    demos=json.loads((a.work/'demonstrations.json').read_text())
    if any(d['id'] not in data['train'] for d in demos):raise RuntimeError('Nontraining demonstration')
    sft=0
    for split in ('train','tuning'):
        rows=read_rows(a.work/'sft-export'/(split+'.jsonl'))
        if [r['id'] for r in rows]!=list(data[split]):raise RuntimeError('SFT split mismatch')
        for row in rows:
            n=row['prompt_tokens'];ids=row['input_ids'];labels=row['labels']
            if len(ids)!=len(labels) or len(ids)>1024 or labels[:n]!=[-100]*n or labels[n:]!=ids[n:] or ids[-1]!=151645:
                raise RuntimeError('SFT label mask/boundary mismatch')
            sft+=1
    result=dict(recorded_verdicts_reproduced=total,counts=counts,
        actual_qwen_prompt_ids_and_budgets_verified=actual_ids,sft_records_and_masks_verified=sft,
        training_only_demonstrations_verified=True,prompt_selection_reproduced=True,
        parent_seal_verified_files=parent['verified_files'],board_access=False,energy_measured=False)
    path=a.work/'verification.json'
    if path.exists():
        if json.loads(path.read_text())!=result:raise RuntimeError('Existing verification differs')
    else:dump(path,result)
    print(json.dumps(result))


if __name__=='__main__':main()
