"""Collect the finite v4 run, verify controls and seal separate evidence."""
import csv,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    w=ROOT/'build/v2/v8-protocol-v4'
    def receipt(name):
        p=w/'board/results'/name
        if json.loads((p/'receipt.json').read_text())['exit']!=0:raise RuntimeError(name+' failed')
        return json.loads((p/'stdout').read_text())
    raw=receipt('04-collect')
    allowed={'qualification.json','requests.jsonl','fixture-before.json','fixture-after.json',
             'deployment-before.json','deployment-after.json','status.json'}
    if set(raw)!=allowed:raise RuntimeError('Unexpected collection')
    out=w/'fpga';out.mkdir(exist_ok=False)
    for n,s in raw.items():(out/n).write_text(s)
    cpu=json.loads((w/'cpu-qualification/qualification.json').read_text())
    fpga=json.loads((out/'qualification.json').read_text())
    if cpu['manifest_sha256']!=fpga['manifest_sha256']:raise RuntimeError('Different manifests')
    rows={b:[json.loads(x) for x in (p/'requests.jsonl').read_text().splitlines()]
          for b,p in [('cpu',w/'cpu-qualification'),('fpga',out)]}
    indexed={b:{r['id']:r for r in rs} for b,rs in rows.items()}
    if set(indexed['cpu'])!=set(indexed['fpga']):raise RuntimeError('Different jobs')
    measured={b:[r for r in rs if not r.get('repeat_of')] for b,rs in rows.items()}
    paired=[]
    for ident,f in indexed['fpga'].items():
        c=indexed['cpu'][ident]
        paired.append(dict(id=ident,repeat_of=f.get('repeat_of'),input_ids_match=c['prompt_ids']==f['prompt_ids'],
            cpu_valid=c['format_valid'],fpga_valid=f['format_valid'],cpu_correct=c['correct'],fpga_correct=f['correct'],
            parsed_agreement=c['observed']==f['observed']))
    if not all(r['input_ids_match'] for r in paired):raise RuntimeError('Input IDs mismatch')
    repeats=[dict(id=r['id'],original=r['repeat_of'],
        ids_match=r['generated_ids']==indexed['fpga'][r['repeat_of']]['generated_ids'])
        for r in rows['fpga'] if r.get('repeat_of')]
    control=receipt('05-mvp-control');old=json.loads((ROOT/'build/v2/v8-protocol-v3/mvp-control.json').read_text())
    audit=receipt('06-final-audit')
    if audit['benchmark_processes'] or 'ActiveState=active' in audit['baseline_unit']:raise RuntimeError('Sweep active')
    if not (w/'board/session-closed.json').exists():raise RuntimeError('Authenticated session still open')
    seals={}
    for name,base,file in [('v8',ROOT,'build/v2/qwen-fpga-decoder-v8/seal.json'),
                           ('v2',ROOT/'build/v2/v8-protocol-v2','build/v2/v8-protocol-v2/qualification-seal.json'),
                           ('v3',ROOT/'build/v2/v8-protocol-v3','build/v2/v8-protocol-v3/qualification-seal.json')]:
        s=json.loads((ROOT/file).read_text())['files_sha256']
        bad=[n for n,h in s.items() if sha(base/n)!=h]
        if bad:raise RuntimeError(name+' seal mismatch: '+str(bad))
        seals[name]=len(s)
    fixture_ok=all(json.loads((out/n).read_text())['passed'] for n in ('fixture-before.json','fixture-after.json'))
    mvp_ok=control['correct'] and all(control[k]==old[k] for k in ('prompt_ids','generated_ids'))
    identity=json.loads((out/'deployment-after.json').read_text())
    previous_identity=json.loads((ROOT/'build/v2/v8-protocol-v3/fpga/deployment-after.json').read_text())
    identity_matches_previous=identity==previous_identity
    integrity=fixture_ok and mvp_ok and len(repeats)==4 and all(r['ids_match'] for r in repeats) and fpga['deployment_unchanged'] and identity_matches_previous
    total=lambda rs:dict(cases=len(rs),format_valid=sum(r['format_valid'] for r in rs),correct=sum(r['correct'] for r in rs))
    result=dict(version='v8-protocol-v4',variant=cpu['variant'],cpu=total(measured['cpu']),fpga=total(measured['fpga']),
        cpu_operations=cpu['operations'],fpga_operations=fpga['operations'],cpu_gate_passed=cpu['passed'],
        fpga_gate_passed=fpga['passed'],protocol_gate_passed=bool(cpu['passed'] and fpga['passed'] and integrity),
        full_sweep_started=False,full_sweep_restart_authorized=False,integrity_checks_passed=integrity,
        fixture_before_after_passed=fixture_ok,unchanged_mvp_exact_ids=mvp_ok,sealed_files_verified=seals,
        repeated_input_checks=repeats,identical_input_ids=True,paired_jobs=len(paired),
        deployment_unchanged=fpga['deployment_unchanged'],deployment_matches_previous=identity_matches_previous,final_sweep_audit=audit,
        semantic_error_fields={b:{field:sum(r['format_valid'] and r['observed'][i]!=r['expected'][i] for r in rs)
            for i,field in enumerate(('status','entity','count'))} for b,rs in measured.items()},
        manifest_sha256=cpu['manifest_sha256'])
    failures=[dict(backend=b,id=r['id'],expected=r['expected'],observed=r['observed'],generated_text=r['generated_text'],
                   format_valid=r['format_valid']) for b,rs in measured.items() for r in rs if not r['correct']]
    for n,data in [('qualification-summary.json',result),('semantic-failures.json',failures),('comparisons.json',paired),('mvp-control.json',control)]:
        (w/n).write_text(json.dumps(data,indent=2)+'\n')
    with (w/'comparisons.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(paired[0]));writer.writeheader();writer.writerows(paired)
    (w/'README.md').write_text('# v8 protocol v4 qualification\n\nCompact state/string-status output only.\n\n'
        +f'CPU: {result["cpu"]}. FPGA: {result["fpga"]}.\n\n'
        +f'Protocol gate passed: {result["protocol_gate_passed"]}. Full sweep remains stopped.\n\n'
        +'28 fresh single-step cases plus four determinism repeats per backend; repeats excluded from accuracy.\n'
        +'See qualification-summary.json and semantic-failures.json. Raw development and qualification traces are preserved.\n')
    frozen={p.relative_to(w).as_posix():sha(p) for p in w.rglob('*') if p.is_file() and p.name!='qualification-seal.json'}
    (w/'qualification-seal.json').write_text(json.dumps(dict(files_sha256=frozen),indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
