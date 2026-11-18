"""Audit fresh long-chain pairs, independent state replay and actual CLI tokens."""
import csv
import hashlib
import json
from pathlib import Path
import re
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.v8_json_retention_v12 import VERSION,summarize
from sysone.v2.v8_json_fpga_qualification_v11 import cpu_prompt_file_bytes
from run_v8_json_retention_v10 import preserved,seal_check


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    work=ROOT/'build/v2'/VERSION
    if (work/'seal.json').exists():raise RuntimeError('Completed evidence cannot be overwritten')
    bundle=work/'bundle';hashes=json.loads((bundle/'source-sha256.json').read_text())
    for n,h in hashes.items():
        if sha(bundle/n)!=h:raise RuntimeError('Frozen bundle differs: '+n)
    checks=preserved()
    checks['v12-cpu-phase']=seal_check(work/'cpu')
    for n in ('development','evaluation'):checks['v10-r3-'+n]=seal_check(ROOT/'build/v2/v8-json-retention-v10-r3'/n)
    for name in ('v8-json-retention-v10-report','v8-json-retention-v11','v8-json-retention-v11-r2'):
        checks[name]=seal_check(ROOT/'build/v2'/name)
    spec=json.loads((bundle/'manifest.json').read_text());jobs=json.loads((bundle/'frozen-jobs.json').read_text())
    total=len(jobs);primary=sum(j['suite']=='primary' for j in jobs);n_repeats=total-primary
    rows={};statuses={};metrics={}
    for backend in ('cpu','fpga'):
        folder=work/backend;statuses[backend]=json.loads((folder/'status.json').read_text())
        if statuses[backend]['stage']!='complete' or not statuses[backend]['source_integrity_passed']:raise RuntimeError(backend+' incomplete')
        data=[json.loads(x) for x in (folder/'requests.jsonl').read_text().splitlines()]
        if [r['id'] for r in data]!=[j['id'] for j in jobs]:raise RuntimeError('Request sequence mismatch')
        for r,j in zip(data,jobs):
            if any(r.get(k)!=v for k,v in j.items()):raise RuntimeError('Frozen input metadata changed')
            if r['correct']!=(r['observed']==r['expected']):raise RuntimeError('Score mismatch')
            expected_bytes=cpu_prompt_file_bytes(j['prompt']) if backend=='cpu' else j['prompt'].encode('utf-8')
            if (folder/(j['id']+'.prompt.txt')).read_bytes()!=expected_bytes:raise RuntimeError('Prompt-file framing differs')
            if backend=='cpu':
                logged=[int(n) for n in re.findall(r"\b(\d+)\s*->\s*'",(folder/(j['id']+'.stderr')).read_text())]
                if logged!=r['actual_cpu_prompt_ids'] or logged!=j['prompt_ids']:raise RuntimeError('Actual CLI input mismatch')
        rows[backend]={r['id']:r for r in data}
        # Generic retention metrics are recomputed from rows. Execution identity
        # comes from the chosen backend and live evidence, not legacy scorer flags.
        metrics[backend]=dict(summarize(data),backend=backend,board_access=backend=='fpga')
    index={j['id']:j for j in jobs}
    for case in spec['cases']:
        state={e:list(v) for e,v in case['initial'].items()}
        for i,step in enumerate(case['steps'],1):
            obs=step['observation']
            if obs:
                e=obs['entity']
                if obs['status']=='ok':state[e][0]=obs['count']
                state[e][1]=obs['status']
            e=step['entity'];j=index[f'{case["id"]}-{i:03d}']
            if j['state']!=state or j['expected']!=[state[e][1],e,state[e][0]]:raise RuntimeError('Independent state replay failed')
    pairs=[];repeats=[]
    for j in jobs:
        a,b=rows['cpu'][j['id']],rows['fpga'][j['id']]
        pairs.append(dict(id=j['id'],case_id=j['case_id'],suite=j['suite'],step=j['step'],expected=j['expected'],
            actual_input_ids_match=a['actual_cpu_prompt_ids']==j['prompt_ids']==b['backend_input_ids'],
            cpu_correct=a['correct'],fpga_correct=b['correct'],semantic_agreement=a['observed']==b['observed'],
            text_agreement=a['generated_text']==b['generated_text'],cpu_text=a['generated_text'],fpga_text=b['generated_text']))
        if j['suite']=='repeat':
            original=rows['fpga'][j['repeat_of']]
            repeats.append(dict(id=j['id'],original=j['repeat_of'],exact_fpga_ids=b['generated_ids']==original['generated_ids'],
                exact_cpu_text=a['generated_text']==rows['cpu'][j['repeat_of']]['generated_text']))
    fixture_names=['fixture-before.json','fixture-after.json']+[c['id']+'.fixture.json' for c in spec['cases']]
    fixtures={n:json.loads((work/'fpga'/n).read_text()) for n in fixture_names}
    identity_before=json.loads((work/'fpga/deployment-before.json').read_text());identity_after=json.loads((work/'fpga/deployment-after.json').read_text())
    live_before=json.loads((work/'board/live-before.json').read_text());live_after=json.loads((work/'board/live-after.json').read_text())
    gates=dict(all_correct_both=all(r['cpu_correct'] and r['fpga_correct'] for r in pairs),
        all_actual_inputs_match=all(r['actual_input_ids_match'] for r in pairs),
        all_semantic_outputs_agree=all(r['semantic_agreement'] for r in pairs),
        fpga_repeats_exact=len(repeats)==n_repeats and all(r['exact_fpga_ids'] for r in repeats),
        all_causal_checks_passed=all(f['passed'] for f in fixtures.values()),
        deployment_unchanged=identity_before==identity_after,live_identity_unchanged=live_before==live_after,
        reservation_released=json.loads((work/'board/released.json').read_text())['released'],
        ssh_closed=json.loads((work/'board/session-closed.json').read_text())['closed'])
    summary=dict(version=VERSION,passed=all(gates.values()),gates=gates,requests_per_backend=total,
        primary_per_backend=primary,repeats_per_backend=n_repeats,backend_results=metrics,
        paired_semantic_matches=sum(r['semantic_agreement'] for r in pairs),raw_text_matches=sum(r['text_agreement'] for r in pairs),
        replayed_primary_steps=primary,fixture_checks=len(fixtures),fixture_cases=sum(len(f['cases']) for f in fixtures.values()),
        fixture_worst_abs=max(c['max_absolute_error'] for f in fixtures.values() for c in f['cases']),
        input_tokens=sorted({j['input_tokens'] for j in jobs}),source_integrity_passed=True,sealed_files_verified=checks,
        board_access=True,closed_loop_included=False,full_sweep_started=False,
        limitations=['Two fixed workload sequences per length; duplicate snapshots are correlated.',
                     'Host carries sufficient state; no claim of long model context or closed-loop reasoning.',
                     'CPU process/loading timings are not comparable to warm FPGA request timing.'])
    for name,value in [('paired-summary.json',summary),('paired-comparisons.json',pairs),('repeat-checks.json',repeats)]:
        (work/name).write_text(json.dumps(value,indent=2)+'\n')
    with (work/'paired-comparisons.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(pairs[0]));writer.writeheader();writer.writerows(pairs)
    table=['| Chain | CPU correct | FPGA correct |','|---|---:|---:|']
    for name,c in metrics['cpu']['chains'].items():
        other=metrics['fpga']['chains'][name]
        table.append(f'| {name} | {c["correct"]}/{c["n"]} | {other["correct"]}/{other["n"]} |')
    (work/'README.md').write_text('# Fresh paired CPU/FPGA JSON retention v12\n\n'+'\n'.join(table)+'\n\n'
        +'Actual CLI tokens and FPGA input IDs checked; corrected prompt-file framing. '
        +'Closed-loop excluded, v8 unchanged, full sweep stopped. See paired-summary.json and board evidence.\n')
    (work/'report-source.py').write_bytes(Path(__file__).read_bytes())
    hashes={p.relative_to(work).as_posix():sha(p) for p in work.rglob('*') if p.is_file()}
    (work/'seal.json').write_text(json.dumps(dict(files_sha256=hashes),indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
