"""Audit paired token-level inputs, semantic outputs, hardware identity and release."""
import csv
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.v8_json_fpga_qualification_v11 import VERSION
from run_v8_json_retention_v10 import preserved,seal_check


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    work=ROOT/'build/v2'/VERSION
    if (work/'seal.json').exists():raise RuntimeError('Qualification already sealed')
    bundle=work/'bundle';hashes=json.loads((bundle/'source-sha256.json').read_text())
    for n,h in hashes.items():
        if sha(bundle/n)!=h:raise RuntimeError('Frozen bundle changed: '+n)
    checks=preserved()
    for n in ('development','evaluation'):
        checks['v10-r3-'+n]=seal_check(ROOT/'build/v2/v8-json-retention-v10-r3'/n)
    checks['v10-report']=seal_check(ROOT/'build/v2/v8-json-retention-v10-report')
    checks['v11-framing-diagnostic']=seal_check(ROOT/'build/v2/v8-json-retention-v11')
    jobs=json.loads((bundle/'frozen-jobs.json').read_text());rows={};statuses={}
    for backend in ('cpu','fpga'):
        statuses[backend]=json.loads((work/backend/'status.json').read_text())
        if statuses[backend]['stage']!='complete' or not statuses[backend]['source_integrity_passed']:
            raise RuntimeError(backend+' incomplete')
        data=[json.loads(x) for x in (work/backend/'requests.jsonl').read_text().splitlines()]
        if [r['id'] for r in data]!=[j['id'] for j in jobs]:raise RuntimeError('Request sequence differs')
        for r,j in zip(data,jobs):
            if any(r.get(k)!=v for k,v in j.items()):raise RuntimeError('Frozen request metadata differs')
        rows[backend]={r['id']:r for r in data}
    paired=[]
    for j in jobs:
        a,b=rows['cpu'][j['id']],rows['fpga'][j['id']]
        paired.append(dict(id=j['id'],suite=j['suite'],expected=j['expected'],
             actual_input_ids_match=a['actual_cpu_prompt_ids']==j['prompt_ids']==b['backend_input_ids'],
             cpu_correct=a['correct'],fpga_correct=b['correct'],semantic_agreement=a['observed']==b['observed'],
             text_agreement=a['generated_text']==b['generated_text'],cpu_text=a['generated_text'],fpga_text=b['generated_text']))
    repeats=[]
    for j in jobs:
        if j['suite']=='repeat':
            a=rows['fpga'][j['id']];b=rows['fpga'][j['repeat_of']]
            repeats.append(dict(id=j['id'],original=j['repeat_of'],
                exact_fpga_ids=a['generated_ids']==b['generated_ids'],
                exact_cpu_text=rows['cpu'][j['id']]['generated_text']==rows['cpu'][j['repeat_of']]['generated_text']))
    fixtures={n:json.loads((work/'fpga'/f'fixture-{n}.json').read_text()) for n in ('before','after')}
    before=json.loads((work/'fpga/deployment-before.json').read_text())
    after=json.loads((work/'fpga/deployment-after.json').read_text())
    live_before=json.loads((work/'board/live-before.json').read_text());live_after=json.loads((work/'board/live-after.json').read_text())
    closed=json.loads((work/'board/session-closed.json').read_text())['closed']
    released=json.loads((work/'board/released.json').read_text())['released']
    gates=dict(all20_correct_each=all(r['cpu_correct'] and r['fpga_correct'] for r in paired),
        all20_parsed_each=all(r['parsed'] for rs in rows.values() for r in rs.values()),
        all20_actual_input_ids_match=all(r['actual_input_ids_match'] for r in paired),
        all20_semantic_agreement=all(r['semantic_agreement'] for r in paired),
        four_fpga_repeats_exact=all(r['exact_fpga_ids'] for r in repeats) and len(repeats)==4,
        causal_fixtures_passed=all(f['passed'] for f in fixtures.values()),
        deployment_identity_unchanged=before==after,live_identity_unchanged=live_before==live_after,
        reservation_released=released,ssh_closed=closed)
    summary=dict(version=VERSION,passed=all(gates.values()),gates=gates,
        backend_results={backend:dict(total=20,primary=16,repeats=4,
            correct=sum(r['correct'] for r in rs.values()),parsed=sum(r['parsed'] for r in rs.values()),
            primary_correct=sum(r['correct'] for r in rs.values() if r['suite']=='primary'),
            by_status={s:dict(n=len(sub),correct=sum(r['correct'] for r in sub))
                for s in ('ok','missing','error') for sub in [[r for r in rs.values() if r['expected'][0]==s]]}) for backend,rs in rows.items()},
        raw_text_matches=sum(r['text_agreement'] for r in paired),input_ids_verified_from_actual_cli=True,
        fixture_cases_per_check={n:len(f['cases']) for n,f in fixtures.items()},
        fixture_worst_abs=max(c['max_absolute_error'] for f in fixtures.values() for c in f['cases']),
        input_tokens=sorted({len(j['prompt_ids']) for j in jobs}),output_budget=48,
        model_startup=json.loads((work/'fpga/startup.json').read_text()),sealed_files_verified=checks,
        board_access=True,closed_loop_included=False,full_sweep_started=False,
        limitations=['Small qualification of two eight-step traces, not a full sweep or statistical reliability claim.',
                     'Actual CLI input parity now checked; earlier nominal CPU prompt IDs did not establish parity.',
                     'CPU process/loading timings and FPGA timings are not a speedup comparison.'])
    for name,value in [('qualification-summary.json',summary),('paired-comparisons.json',paired),('repeat-checks.json',repeats)]:
        (work/name).write_text(json.dumps(value,indent=2)+'\n')
    with (work/'paired-comparisons.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(paired[0]));writer.writeheader();writer.writerows(paired)
    (work/'report-source.py').write_bytes(Path(__file__).read_bytes())
    (work/'README.md').write_text('# Paired CPU/FPGA JSON retention qualification\n\n'
        +f'Passed: {summary["passed"]}. CPU correct: {summary["backend_results"]["cpu"]["correct"]}/20; '
        +f'FPGA correct: {summary["backend_results"]["fpga"]["correct"]}/20. Includes four repeats each.\n\n'
        +'See qualification-summary.json, paired-comparisons.csv, CPU verbose token logs and FPGA fixture/identity evidence. '
        +'V8 unchanged; full sweep stopped; shared board reservation released.\n')
    hashes={p.relative_to(work).as_posix():sha(p) for p in work.rglob('*') if p.is_file()}
    (work/'seal.json').write_text(json.dumps(dict(files_sha256=hashes),indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
