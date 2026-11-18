"""Collect completed qualification receipts and publish the admission decision."""
import csv,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def main():
    work=ROOT/'build/v2/v8-protocol-v2'
    receipt=json.loads((work/'board/results/04-collect/receipt.json').read_text())
    if receipt['exit']!=0:raise RuntimeError('Board result collection failed')
    raw=json.loads((work/'board/results/04-collect/stdout').read_text())
    out=work/'fpga';out.mkdir(exist_ok=False)
    allowed={'qualification.json','requests.jsonl','fixture-before.json','fixture-after.json',
             'deployment-before.json','deployment-after.json','status.json'}
    if set(raw)!=allowed:raise ValueError('Unexpected collected artifact names')
    for name,text in raw.items():(out/name).write_text(text)
    cpu=json.loads((work/'cpu/qualification.json').read_text())
    fpga=json.loads((out/'qualification.json').read_text())
    if cpu['manifest_sha256']!=fpga['manifest_sha256']:raise RuntimeError('Qualification manifests differ')
    cpu_rows=[json.loads(l) for l in (work/'cpu/requests.jsonl').read_text().splitlines() if json.loads(l)['split']=='qualification']
    fpga_rows=[json.loads(l) for l in (out/'requests.jsonl').read_text().splitlines()]
    lookup={(r['case_id'],r['context'],r['wire']):r for r in cpu_rows}
    comparisons=[]
    for row in fpga_rows:
        c=lookup[(row['case_id'],row['context'],row['wire'])]
        comparisons.append(dict(id=row['id'],context=row['context'],wire=row['wire'],
            cpu_valid=c['format_valid'],fpga_valid=row['format_valid'],cpu_correct=c['correct'],fpga_correct=row['correct'],
            parsed_agreement=c['observed']==row['observed'],
            both_valid=c['format_valid'] and row['format_valid'],
            both_invalid=not c['format_valid'] and not row['format_valid'],
            input_ids_match=c['prompt_ids']==row['prompt_ids']))
    if not all(r['input_ids_match'] for r in comparisons):raise RuntimeError('Input IDs mismatch')
    total=lambda rows:dict(cases=len(rows),format_valid=sum(r['format_valid'] for r in rows),correct=sum(r['correct'] for r in rows))
    result=dict(version='v8-protocol-v2',cpu=total(cpu_rows),fpga=total(fpga_rows),
        cpu_groups=cpu['groups'],fpga_groups=fpga['groups'],cpu_gate_passed=cpu['passed'],
        fpga_gate_passed=fpga['passed'],full_sweep_admitted=cpu['passed'] and fpga['passed'],
        full_sweep_started=False,selected_prompt_variant=cpu['variant'],
        parsed_output_agreement=sum(r['parsed_agreement'] for r in comparisons),
        valid_output_agreement=sum(r['parsed_agreement'] and r['both_valid'] for r in comparisons),
        both_valid_cases=sum(r['both_valid'] for r in comparisons),
        both_invalid_cases=sum(r['both_invalid'] for r in comparisons),
        identical_input_ids=all(r['input_ids_match'] for r in comparisons),
        deployment_unchanged=fpga['deployment_unchanged'],
        qualification_manifest_sha256=cpu['manifest_sha256'])
    fpga_lookup={(r['case_id'],r['context'],r['wire']):r for r in fpga_rows}
    determinism=[]
    for row in fpga_rows:
        if row['context']!='H':continue
        other=fpga_lookup[(row['case_id'],'J',row['wire'])]
        if row['prompt_ids']==other['prompt_ids']:
            determinism.append(dict(case_id=row['case_id'],wire=row['wire'],
                generated_ids_equal=row['generated_ids']==other['generated_ids']))
    result['repeat_input_checks']=len(determinism)
    result['repeat_input_output_mismatches']=sum(not r['generated_ids_equal'] for r in determinism)
    if result['repeat_input_output_mismatches']:result['full_sweep_admitted']=False
    (work/'determinism-checks.json').write_text(json.dumps(determinism,indent=2)+'\n')
    control_receipt=json.loads((work/'board/results/05-mvp-control/receipt.json').read_text())
    if control_receipt['exit']!=0:raise RuntimeError('MVP control did not complete')
    control=json.loads((work/'board/results/05-mvp-control/stdout').read_text())
    (work/'mvp-control.json').write_text(json.dumps(control,indent=2)+'\n')
    result['unchanged_mvp_control_correct']=control['correct']
    (work/'qualification-summary.json').write_text(json.dumps(result,indent=2)+'\n')
    (work/'comparisons.json').write_text(json.dumps(comparisons,indent=2)+'\n')
    with (work/'comparisons.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(comparisons[0]));writer.writeheader();writer.writerows(comparisons)
    table=['| Arm | CPU format | CPU correct | FPGA format | FPGA correct |',
           '|---|---:|---:|---:|---:|']
    for arm,c in cpu['groups'].items():
        g=fpga['groups'][arm]
        table.append(f'| {arm} | {c["format_valid"]}/{c["cases"]} | {c["correct"]}/{c["cases"]} | '
                     f'{g["format_valid"]}/{g["cases"]} | {g["correct"]}/{g["cases"]} |')
    (work/'README.md').write_text('# v8 protocol v2 qualification\n\n'
        'Completed finite CPU and FPGA qualification. This package does not change deployed v8.\n\n'
        +'\n'.join(table)+'\n\n'
        +'H=initial history, J=JSON state, C=compact state; A=JSON array, E=enum record.\n'
        +'These are single-step protocol controls, not sustainable-chain results. H/J initial prompts coincide.\n\n'
        +f'Full sweep admitted: {result["full_sweep_admitted"]}. Full sweep started: False.\n'
        +f'Parsed CPU/FPGA agreement: {result["parsed_output_agreement"]}/{len(comparisons)}.\n'
        +f'Original MVP command-generation control correct: {control["correct"]}; no tool executed.\n\n'
        +'See qualification-summary.json, comparisons.csv, cpu/requests.jsonl and fpga/requests.jsonl.\n'
        +'All raw outputs and failures are retained. Gates were frozen before qualification.\n')
    files={p.relative_to(work).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
           for p in work.rglob('*') if p.is_file() and p.name!='qualification-seal.json'
           and 'snapshot-preflight' not in p.parts}
    (work/'qualification-seal.json').write_text(json.dumps(dict(files_sha256=files),indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
