"""Analyze and seal a completed CPU-only three-arm pilot."""
import csv,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    w=ROOT/'build/v2/v8-state-pilot-v6-r2';out=w/'cpu'
    status=json.loads((out/'status.json').read_text())
    if status['stage']!='complete' or not status['source_integrity_passed']:raise RuntimeError('Pilot not complete')
    spec=json.loads((w/'pilot-manifest.json').read_text());summary=json.loads((out/'summary.json').read_text())
    rows=[json.loads(x) for x in (out/'requests.jsonl').read_text().splitlines()];index={r['id']:r for r in rows}
    if len(index)!=len(rows):raise RuntimeError('Duplicate IDs')
    frozen=json.loads((w/'source-sha256.json').read_text())
    for name,h in frozen.items():
        if sha(ROOT/name)!=h:raise RuntimeError('Frozen source changed: '+name)
    expected_prompts={(r['case_id'],r['arm'],r['step']):r['prompt']
        for r in json.loads((w/'frozen-control-prompts.json').read_text())}
    controls=[r for r in rows if r['suite']=='snapshot-control']
    if len(controls)!=64 or any(r['prompt']!=expected_prompts[(r['case_id'],r['arm'],r['step'])] for r in controls):
        raise RuntimeError('Frozen control inputs changed')
    done=[r for r in rows if r['status']=='completed'];paired=[]
    for r in rows:
        if r['suite']!='dependent' or r['arm'] not in ('J','C'):continue
        c=index[r['control_id']]
        paired.append(dict(id=r['id'],control_id=c['id'],mode=r['mode'],split=r['split'],arm=r['arm'],
            state_match=r['state_before']==c['state_before'],input_ids_match=r['prompt_ids']==c['prompt_ids'],
            output_text_match=r.get('generated_text')==c.get('generated_text'),
            correct=r['correct'],control_correct=c['correct']))
    if any(p['state_match'] and not p['input_ids_match'] for p in paired):raise RuntimeError('Control alignment failure')
    first={};repeats=[]
    for r in done:
        key=tuple(r['prompt_ids'])
        if key in first:
            old=first[key];repeats.append(dict(id=r['id'],original=old['id'],
                output_text_match=r['generated_text']==old['generated_text']))
        else:first[key]=r
    grouped={}
    for key,g in summary['groups'].items():
        suite,split,mode,arm=key.split('/')
        rs=[r for r in done if (r['suite'],r['split'],r['mode'],r['arm'])==(suite,split,mode,arm)]
        grouped[key]=dict(g,unparseable=sum(not r['accepted'] for r in rs),
            parsed_wrong=sum(r['accepted'] and not r['correct'] for r in rs),
            accepted_correct=sum(r['accepted'] and r['correct'] for r in rs),
            mean_input_tokens=sum(r['input_tokens'] for r in rs)/len(rs) if rs else None)
    chains={}
    for key,g in summary['chains'].items():
        rs=[r for r in done if r['suite']=='dependent' and r['case_id']+'/'+r['arm']==key]
        chains[key]=dict(g,first_end_to_end_failure=g['first_semantic_failure'],
            first_parsed_semantic_error=next((r['step'] for r in rs if r['accepted'] and not r['correct']),None))
    comparisons=[]
    for case in spec['cases']:
        arms={a:[r for r in done if r['suite']=='dependent' and r['case_id']==case['id'] and r['arm']==a] for a in ('H','J','C')}
        common=min(len(rs) for rs in arms.values())
        comparisons.append(dict(case_id=case['id'],mode=case['mode'],split=case['split'],common_steps=common,
            correct_on_common_steps={a:sum(r['correct'] for r in rs[:common]) for a,rs in arms.items()},
            whole_chain={a:dict(generated=len(rs),correct=sum(r['correct'] for r in rs)) for a,rs in arms.items()}))
    verified={}
    checks=[('v8',ROOT,ROOT/'build/v2/qwen-fpga-decoder-v8/seal.json')]
    for v in (2,3,4):
        base=ROOT/f'build/v2/v8-protocol-v{v}';checks.append((f'v{v}',base,base/'qualification-seal.json'))
    base=ROOT/'build/v2/v8-chain-pilot-v5';checks.append(('v5',base,base/'pilot-seal.json'))
    base=ROOT/'build/v2/v8-state-pilot-v6';checks.append(('parser-development',base,base/'development-seal.json'))
    for label,base,p in checks:
        hashes=json.loads(p.read_text())['files_sha256'];bad=[n for n,h in hashes.items() if sha(base/n)!=h]
        if bad:raise RuntimeError('Preserved seal changed: '+label+str(bad))
        verified[label]=len(hashes)
    result=dict(version=spec['version'],overall=summary['overall'],groups=grouped,chains=chains,
        common_prefix_comparisons=comparisons,aligned_state_control_pairs=len(paired),
        matching_state_control_inputs=sum(p['input_ids_match'] for p in paired),
        repeated_input_checks=len(repeats),repeat_output_text_mismatches=sum(not p['output_text_match'] for p in repeats),
        frozen_control_prompts_verified=True,source_integrity_passed=True,sealed_files_verified=verified,
        board_access=False,board_status_file_modified=False,full_sweep_started=False,
        model='Pinned Qwen3-0.6B Q8_0, CPU greedy llama.cpp ngl0',
        limitations=['One sequence per mode/split, shared templates, no statistical or cross-model reliability claim',
            'Context256 and output reservation48; H retains complete raw responses and stops without truncation',
            'H snapshot controls are diagnostic, not identical-history controls; J/C controls use identical templates',
            'Retention reducers summarize actual tool facts; this is task-sufficient current state, not lossless full history',
            'Closed-loop state comes only from model proposals; controls/gold never repair it',
            'Parser r2 uses development-only structural normalization; heldout never informed prompt or parser changes',
            'CPU time includes process/model loading and is not a latency/throughput baseline for FPGA',
            'Preferred-array conformance is distinct from accepted equivalent formats; extraction failure is not proof of wrong semantic content'])
    failures=[{k:r.get(k) for k in ('id','suite','split','mode','arm','step','generated_text','observed','expected',
        'local_expected','accepted','local_correct','inherited_only_error','state_before','state_after','state_exact')}
        for r in done if not r['correct']]
    for name,data in [('pilot-summary.json',result),('control-alignment.json',paired),('repeat-checks.json',repeats),
                      ('semantic-failures.json',failures),('common-prefix-comparisons.json',comparisons)]:
        (w/name).write_text(json.dumps(data,indent=2)+'\n')
    columns=['id','suite','split','mode','arm','step','status','input_tokens','output_tokens_estimate','seconds',
             'accepted','native_format','correct','local_correct','inherited_only_error','state_exact','normalization_route']
    with (w/'requests.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    table=['| Split | Mode | Arm | Generated | Accepted | Correct | Capacity stop |',
           '|---|---|---|---:|---:|---:|---:|']
    for key,g in chains.items():
        rs=[r for r in rows if r['suite']=='dependent' and r['case_id']+'/'+r['arm']==key]
        table.append(f'| {rs[0]["split"]} | {rs[0]["mode"]} | {rs[0]["arm"]} | {g["inferences"]} | '
            f'{g["accepted"]} | {g["correct"]} | {g["context_exhausted_at"]} |')
    (w/'README.md').write_text('# CPU state pilot v6-r2\n\n'+'\n'.join(table)+'\n\n'
        +'H=full raw history; J=readable JSON state; C=named compact state.\n'
        +'Retention state is updated only by simulated tool observations; closed-loop state by actual model proposals.\n'
        +'Controls, dependent requests, extraction, semantic errors and capacity censoring are reported separately.\n'
        +'See pilot-summary.json and common-prefix-comparisons.json; no full sweep or board access.\n')
    files={p.relative_to(w).as_posix():sha(p) for p in w.rglob('*') if p.is_file() and p.name!='pilot-seal.json'}
    (w/'pilot-seal.json').write_text(json.dumps(dict(files_sha256=files),indent=2)+'\n')
    print(json.dumps(dict(version=result['version'],overall=result['overall'],chains=chains,
        aligned_control_pairs=len(paired),repeat_mismatches=result['repeat_output_text_mismatches'],
        sealed_files_verified=verified,board_access=False,full_sweep_started=False),indent=2))


if __name__=='__main__':main()
