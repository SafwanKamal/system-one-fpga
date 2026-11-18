"""Verify the selected retention prompt, paired development and fresh evaluation."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(base):
    hashes=json.loads((base/'seal.json').read_text())['files_sha256']
    for n,h in hashes.items():
        if sha(base/n)!=h:raise RuntimeError('Sealed artifact changed: '+str(base/n))
    return len(hashes)


def read_rows(base):return [json.loads(x) for x in (base/'cpu/requests.jsonl').read_text().splitlines()]


def main():
    folders={'first-development':'v8-json-retention-v10/development',
             'second-development':'v8-json-retention-v10-r2/development',
             'selected-development':'v8-json-retention-v10-r3/development',
             'evaluation':'v8-json-retention-v10-r3/evaluation'}
    bases={k:ROOT/'build/v2'/n for k,n in folders.items()}
    verified={label:verify(base) for label,base in bases.items()}
    dev=bases['selected-development'];raw=bases['evaluation']
    ds=json.loads((dev/'summary.json').read_text())
    if not ds['gate_passed']:raise RuntimeError('Selected prompt failed development')
    frozen_dev=json.loads((dev/'source-sha256.json').read_text())
    frozen_eval=json.loads((raw/'source-sha256.json').read_text())
    for name,h in frozen_dev.items():
        if name.startswith(('src/','scripts/','tests/')) and frozen_eval.get(name)!=h:
            raise RuntimeError('Source changed between selected development and evaluation')
    selection=json.loads((raw/'selection.json').read_text())
    if selection['development_seal_sha256']!=sha(dev/'seal.json'):raise RuntimeError('Selection provenance mismatch')
    baseline={r['case_id']:r for r in read_rows(bases['first-development']) if r['policy']=='original'}
    revised=read_rows(dev)
    if len(revised)!=36 or len(baseline)!=36:raise RuntimeError('Development pairing incomplete')
    for r in revised:
        old=baseline[r['case_id']]
        if any(r[k]!=old[k] for k in ('state','entity','expected')):raise RuntimeError('Development case mismatch')
    spec=json.loads((raw/'manifest.json').read_text());jobs=json.loads((raw/'frozen-jobs.json').read_text())
    rows=read_rows(raw);status=json.loads((raw/'status.json').read_text())
    if status['stage']!='complete' or not status['source_integrity_passed']:raise RuntimeError('Evaluation incomplete')
    if len(rows)!=spec['maximum_inferences'] or len(rows)!=len(jobs):raise RuntimeError('Missing evaluation rows')
    for r,j in zip(rows,jobs):
        if any(r.get(k)!=v for k,v in j.items()):raise RuntimeError('Frozen evaluation job mismatch')
        if r['correct']!=(r['observed']==r['expected']):raise RuntimeError('Score mismatch')
    primary=[r for r in rows if r['suite']=='primary'];index={r['id']:r for r in primary}
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
    if summary['primary']['correct']!=sum(r['correct'] for r in primary):raise RuntimeError('Summary mismatch')
    groups={}
    for r in rows:groups.setdefault(tuple(r['prompt_ids']),[]).append(r)
    analysis=dict(evaluation_summary=summary,verified_sealed_files=verified,
        phase_seal_sha256={label:sha(base/'seal.json') for label,base in bases.items()},
        development=dict(paired_cases=36,original_correct=sum(r['correct'] for r in baseline.values()),
                         selected_correct=sum(r['correct'] for r in revised),
                         second_revision_correct=json.loads((bases['second-development']/'summary.json').read_text())['groups']['status-copy']['correct']),
        selected_source_matches_evaluation=True,independently_replayed_requests=len(primary),
        wrong_fields=dict(Counter(f for r in primary for f in r['wrong_fields'])),
        repeated_input_groups=sum(len(rs)>1 for rs in groups.values()),
        repeated_input_text_disagreements=sum(len({r['generated_text'] for r in rs})>1 for rs in groups.values()),
        board_access=False,full_sweep_started=False,closed_loop_included=False,
        comparison='Original/selected development is paired; v9 and v10 fresh evaluations are not paired.')
    out=ROOT/'build/v2/v8-json-retention-v10-report';out.mkdir(parents=True,exist_ok=False)
    (out/'analysis.json').write_text(json.dumps(analysis,indent=2)+'\n')
    columns=['id','case_id','family','chain_length','suite','step','entity','query_age','event_relation',
             'input_tokens','parsed','correct','category','wrong_fields','expected','observed','generated_text']
    with (out/'requests.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    table=['| Chain | Correct | First failure | Longest correct run |','|---|---:|---:|---:|']
    for name,c in summary['chains'].items():
        table.append(f'| {name} | {c["correct"]}/{c["n"]} | {c["first_failure"]} | {c["longest_correct_run"]} |')
    (out/'README.md').write_text('# CPU JSON retention v10\n\n'+'\n'.join(table)+'\n\n'
         +'Development selected the prompt before fresh evaluation. Parser/scoring unchanged; no status repair. '
         +'Read-only replies and bounded host state; closed-loop excluded. V8 unchanged; full sweep stopped.\n')
    (out/'report-source.py').write_bytes(Path(__file__).read_bytes())
    hashes={p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file()}
    (out/'seal.json').write_text(json.dumps(dict(files_sha256=hashes),indent=2)+'\n')
    print(json.dumps(analysis,indent=2))


if __name__=='__main__':main()
