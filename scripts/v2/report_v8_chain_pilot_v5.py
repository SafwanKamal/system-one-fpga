"""Collect, compare and seal a completed finite chain pilot."""
import csv,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    w=ROOT/'build/v2/v8-chain-pilot-v5'
    def receipt(name):
        p=w/'board/results'/name
        if json.loads((p/'receipt.json').read_text())['exit']!=0:raise RuntimeError(name+' failed')
        return json.loads((p/'stdout').read_text())
    raw=receipt('04-collect')
    allowed={'summary.json','requests.jsonl','fixture-before.json','fixture-after.json',
             'deployment-before.json','deployment-after.json','status.json','run-config.json'}
    if set(raw)!=allowed:raise RuntimeError('Unexpected collected names')
    out=w/'fpga';out.mkdir(exist_ok=True)
    for n,s in raw.items():
        destination=out/n
        if destination.exists() and destination.read_text()!=s:raise RuntimeError('Collected evidence differs: '+n)
        if not destination.exists():destination.write_text(s)
    paths={'cpu':w/'cpu','fpga':out}
    summaries={b:json.loads((p/'summary.json').read_text()) for b,p in paths.items()}
    configs={b:json.loads((p/'run-config.json').read_text()) for b,p in paths.items()}
    if configs['cpu']['manifest_sha256']!=configs['fpga']['manifest_sha256']:raise RuntimeError('Manifest mismatch')
    rows={b:[json.loads(x) for x in (p/'requests.jsonl').read_text().splitlines()] for b,p in paths.items()}
    indexed={b:{r['id']:r for r in rs} for b,rs in rows.items()}
    paired=[]
    for ident in sorted(set(indexed['cpu'])|set(indexed['fpga'])):
        c=indexed['cpu'].get(ident);f=indexed['fpga'].get(ident)
        paired.append(dict(id=ident,cpu_present=c is not None,fpga_present=f is not None,
            input_ids_match=c['prompt_ids']==f['prompt_ids'] if c and f else None,
            state_before_match=c['state_before']==f['state_before'] if c and f else None,
            status_match=c['status']==f['status'] if c and f else None,
            observed_match=c['observed']==f['observed'] if c and f else None))
    controls=[r for r in paired if r['id'].startswith('control-')]
    if len(controls)!=16 or not all(r['input_ids_match'] for r in controls):raise RuntimeError('Control inputs differ')
    # Dynamic inputs may legitimately diverge after backend output differences.
    # Never replay the CPU's state to make the hardware input artificially match.
    repeated=[];first={}
    for r in rows['fpga']:
        if r['status']!='completed':continue
        key=tuple(r['prompt_ids'])
        if key in first:
            old=first[key];repeated.append(dict(id=r['id'],original=old['id'],output_ids_match=r['generated_ids']==old['generated_ids']))
        else:first[key]=r
    control=receipt('05-mvp-control');previous=json.loads((ROOT/'build/v2/v8-protocol-v4/mvp-control.json').read_text())
    mvp=control['correct'] and all(control[k]==previous[k] for k in ('prompt_ids','generated_ids'))
    audit=receipt('06-final-audit')
    if audit['benchmark_processes'] or 'ActiveState=active' in audit['baseline_unit']:raise RuntimeError('Sweep process active')
    if not (w/'board/session-closed.json').exists():raise RuntimeError('Authenticated session not closed')
    before=json.loads((out/'deployment-before.json').read_text());after=json.loads((out/'deployment-after.json').read_text())
    old=json.loads((ROOT/'build/v2/v8-protocol-v4/fpga/deployment-after.json').read_text())
    identity=before==after==old
    fixtures=all(json.loads((out/n).read_text())['passed'] for n in ('fixture-before.json','fixture-after.json'))
    verified={}
    specs=[('v8',ROOT,ROOT/'build/v2/qwen-fpga-decoder-v8/seal.json')]
    for version in (2,3,4):
        base=ROOT/f'build/v2/v8-protocol-v{version}';specs.append((f'v{version}',base,base/'qualification-seal.json'))
    for name,base,p in specs:
        hashes=json.loads(p.read_text())['files_sha256'];bad=[n for n,h in hashes.items() if sha(base/n)!=h]
        if bad:raise RuntimeError('Previous sealed evidence changed: '+name+str(bad))
        verified[name]=len(hashes)
    integrity=identity and fixtures and mvp and len(repeated)>=4 and all(r['output_ids_match'] for r in repeated)
    result=dict(version='v8-chain-pilot-v5',backends=summaries,paired_records=len(paired),
        matching_input_sequences=sum(r['input_ids_match'] is True for r in paired),
        matching_valid_parsed_outputs_on_matching_inputs=sum(r['input_ids_match'] and r['observed_match']
            and indexed['fpga'][r['id']]['status']=='completed' and indexed['fpga'][r['id']]['accepted']
            for r in paired if r['cpu_present'] and r['fpga_present']),
        both_unparseable_on_matching_completed_inputs=sum(r['input_ids_match']
            and indexed['fpga'][r['id']]['status']=='completed' and not indexed['fpga'][r['id']]['accepted']
            and not indexed['cpu'][r['id']]['accepted'] for r in paired if r['cpu_present'] and r['fpga_present']),
        fixed_control_inputs_match=True,repeated_input_checks=repeated,integrity_checks_passed=integrity,
        deployment_unchanged=identity,causal_fixtures_passed=fixtures,original_mvp_exact_ids=mvp,
        sealed_files_verified=verified,final_sweep_audit=audit,full_sweep_started=False,
        full_sweep_restart_authorized=False,manifest_sha256=configs['cpu']['manifest_sha256'],
        limitations=['One chain per task family, one model, no statistical reliability or cross-model scaling claim',
            'Representation and acknowledgement phrasing can affect quality; controls omit prior-reply feedback and are not an identical-prompt causal ablation',
            'Deployment context256 with fixed output reservation48; no history truncation or prefix reuse',
            'CPU timing includes process/model load; FPGA timing is resident inference only',
            'Host normalization/reducer overhead and energy unmeasured; no throughput/speedup claim'])
    failures=[dict(backend=b,id=r['id'],observed=r['observed'],expected=r['expected'],local_expected=r['local_expected'],
        generated_text=r['generated_text'],accepted=r['accepted'],local_correct=r['local_correct'],state_exact=r['state_exact'])
        for b,rs in rows.items() for r in rs if r['status']=='completed' and not r['correct']]
    for n,v in [('pilot-summary.json',result),('comparisons.json',paired),('semantic-failures.json',failures),('mvp-control.json',control)]:
        (w/n).write_text(json.dumps(v,indent=2)+'\n')
    with (w/'comparisons.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(paired[0]));writer.writeheader();writer.writerows(paired)
    table=['| Backend | Chain/arm | Generated | Correct | First failure | Capacity stop |',
           '|---|---|---:|---:|---:|---:|']
    for b,s in summaries.items():
        for name,c in s['chains'].items():
            table.append(f'| {b} | {name} | {c["generated_steps"]} | {c["correct_steps"]} | '
                f'{c["first_semantic_failure"]} | {c["context_exhausted_at"]} |')
    (w/'README.md').write_text('# v8 dependent-chain pilot v5\n\n'+'\n'.join(table)+'\n\n'
        +'H=full raw history; C=lossless named compact observed state. First failure includes unparseable output.\n'
        +'Capacity stops are observed under context256/output-reserve48, not general Qwen context limits.\n'
        +'One-step oracle-input controls are diagnostics and never correct measured rolling state.\n'
        +'See pilot-summary.json for acceptance, native format, controls, recovery, timings and limitations.\n'
        +'V8 is unchanged; full sweep remains stopped. No model-specific prompt tuning was performed.\n')
    files={p.relative_to(w).as_posix():sha(p) for p in w.rglob('*') if p.is_file() and p.name!='pilot-seal.json'}
    (w/'pilot-seal.json').write_text(json.dumps(dict(files_sha256=files),indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
