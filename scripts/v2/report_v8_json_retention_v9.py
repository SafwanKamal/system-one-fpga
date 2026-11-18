"""Verify completed raw retention evidence and create a separate sealed analysis."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    raw=ROOT/'build/v2/v8-json-retention-v9'
    hashes=json.loads((raw/'seal.json').read_text())['files_sha256']
    for n,h in hashes.items():
        if sha(raw/n)!=h:raise RuntimeError('Raw evidence changed: '+n)
    status=json.loads((raw/'status.json').read_text())
    if status['stage']!='complete' or not status['source_integrity_passed']:raise RuntimeError('Run incomplete')
    spec=json.loads((raw/'manifest.json').read_text());jobs=json.loads((raw/'frozen-jobs.json').read_text())
    rows=[json.loads(x) for x in (raw/'cpu/requests.jsonl').read_text().splitlines()]
    if len(rows)!=spec['maximum_inferences'] or len(rows)!=len(jobs):raise RuntimeError('Missing rows')
    for row,job in zip(rows,jobs):
        if any(row.get(k)!=v for k,v in job.items()):raise RuntimeError('Frozen job mismatch')
        if row['correct']!=(row['observed']==row['expected']):raise RuntimeError('Score mismatch')
    primary=[r for r in rows if r['suite']=='primary']
    index={r['id']:r for r in primary}
    # Independent replay; never substitutes expected records for observed replies.
    for case in spec['cases']:
        state={e:list(v) for e,v in case['initial'].items()}
        for i,step in enumerate(case['steps'],1):
            event=step['observation']
            if event:
                e=event['entity']
                if event['status']=='ok':state[e][0]=event['count']
                state[e][1]=event['status']
            e=step['entity'];r=index[f'{case["id"]}-{i:03d}']
            if r['state']!=state or r['expected']!=[state[e][1],e,state[e][0]]:raise RuntimeError('Oracle/state mismatch')
    summary=json.loads((raw/'summary.json').read_text())
    if summary['primary']['n']!=len(primary) or summary['primary']['correct']!=sum(r['correct'] for r in primary):
        raise RuntimeError('Summary mismatch')
    duplicate={}
    for r in rows:duplicate.setdefault(tuple(r['prompt_ids']),[]).append(r)
    analysis=dict(raw_seal_sha256=sha(raw/'seal.json'),raw_sealed_files_verified=len(hashes),
        independently_replayed_primary_requests=len(primary),summary=summary,
        wrong_fields=dict(Counter(f for r in primary for f in r['wrong_fields'])),
        field_correct_all_requests={f:sum(r['observed'] is not None and r['observed'][i]==r['expected'][i] for r in primary)
                                   for i,f in enumerate(('status','entity','count'))},
        repeated_input_groups=sum(len(rs)>1 for rs in duplicate.values()),
        repeated_input_text_disagreements=sum(len({r['generated_text'] for r in rs})>1 for rs in duplicate.values()),
        by_step_window={f'{lo}-{lo+15}':dict(n=len(rs),correct=sum(r['correct'] for r in rs))
                       for lo in (1,17,33,49) for rs in [[r for r in primary if lo<=r['step']<lo+16]]},
        board_access=False,full_sweep_started=False,closed_loop_included=False)
    out=ROOT/'build/v2/v8-json-retention-v9-report';out.mkdir(parents=True,exist_ok=False)
    (out/'analysis.json').write_text(json.dumps(analysis,indent=2)+'\n')
    columns=['id','case_id','family','chain_length','suite','step','entity','query_age','event_relation',
             'input_tokens','parsed','correct','category','wrong_fields','expected','observed','generated_text']
    with (out/'requests.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    table=['| Chain | Correct | First failure | Longest correct run |','|---|---:|---:|---:|']
    for name,c in summary['chains'].items():
        table.append(f'| {name} | {c["correct"]}/{c["n"]} | {c["first_failure"]} | {c["longest_correct_run"]} |')
    (out/'README.md').write_text('# CPU JSON retention v9\n\n'+'\n'.join(table)+'\n\n'
        +'Read-only model replies; host observations carry state. Closed-loop excluded. '
        +'See analysis.json for per-status, distinct-input and duplicate checks. '
        +'Raw evidence remains separately sealed. V8 unchanged; full sweep stopped.\n')
    (out/'report-source.py').write_bytes(Path(__file__).read_bytes())
    files={p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file()}
    (out/'seal.json').write_text(json.dumps(dict(files_sha256=files),indent=2)+'\n')
    print(json.dumps(analysis,indent=2))


if __name__=='__main__':main()
