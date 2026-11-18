"""Independently re-score saved model outputs and write auditable tables."""
import argparse
from collections import Counter
import importlib.util
import json
import math
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('runner',ROOT/'scripts/v2/capability_comparison_20261102.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

def audit_row(case,row,route,second=False):
    valid,correct,accepted=False,False,False
    if row['status']=='context_rejection':return valid,correct,accepted
    try:
        decoded=row.get('decoded_output',row['raw'])
        raw='<think>'+decoded if row.get('reasoning_prefix_in_prompt') else decoded
        if case['domain']=='maintenance':
            if route=='native':
                calls=runner.parse_calls(raw,[runner.SUBMIT],allow_text_no_calls=route=='native')
                if len(calls)!=1 or calls[0]['name']!='submit_maintenance_plan' or set(calls[0]['arguments'])!={'plan_json'}:raise ValueError('Bad native submission')
                text=calls[0]['arguments']['plan_json']
            else:text=runner.strip_format(raw)
            ast=runner.maintenance_parse(text,case['catalog'])
            scored=runner.maintenance_score(case,ast)
            valid,correct,accepted=True,scored['correct'],scored['accepted']
        else:
            calls=runner.parse_calls(raw,case['tools'],allow_text_no_calls=route=='native');valid=True;accepted=bool(calls)
            if case['domain']=='general':correct=bool(CHECKER.score(case,calls,case['gold'])['valid'])
            else:
                gold=case['followup']['gold'] if second else case['gold']
                correct=sorted(json.dumps(x,sort_keys=True) for x in calls)==sorted(json.dumps(x,sort_keys=True) for x in gold)
        if row.get('truncated'):correct=False
    except (ValueError,TypeError,SyntaxError,KeyError,IndexError):pass
    return bool(valid),bool(correct),bool(accepted)

CHECKER=None

def stats(items):
    walls=sorted(x['seconds'] for x in items)
    generated=sorted((x.get('generated_tokens') or 0)+(x.get('second_turn',{}).get('generated_tokens') or 0) for x in items)
    def percentile(values,q):return values[max(0,math.ceil(q*len(values))-1)] if values else None
    return dict(n=len(items),correct=sum(x['correct'] for x in items),valid=sum(x['valid'] and (not x.get('second_turn') or x['second_turn']['valid']) for x in items),
        accepted=sum(x['accepted'] for x in items),wrong_accepted=sum(x['accepted'] and not x['correct'] for x in items),
        maintenance_exact_canonical=sum(bool(x.get('exact')) for x in items),maintenance_simulator_equivalent=sum(bool(x.get('behavioral_match')) for x in items),
        overflows=sum(x['status']=='context_rejection' or x.get('second_turn',{}).get('status')=='context_rejection' for x in items),truncated=sum(x.get('truncated',False) or x.get('second_turn',{}).get('truncated',False) for x in items),
        median_wall=statistics.median(walls) if walls else None,p95_wall=percentile(walls,.95),max_wall=max(walls) if walls else None,
        max_prompt=max((max(x['input_tokens'],x.get('second_turn',{}).get('input_tokens',0)) for x in items),default=0),
        episode_first_turn_correct=sum(bool(x.get('first_turn_correct')) for x in items),episode_second_turn_correct=sum(bool(x.get('second_turn',{}).get('correct')) for x in items),
        median_generated_tokens=statistics.median(generated) if generated else None,p95_generated_tokens=percentile(generated,.95),max_generated_tokens=max(generated) if generated else None,
        output_budget_success_counts={str(b):sum(x['correct'] and (x.get('generated_tokens') or 0)<=b and
            (not x.get('second_turn') or (x['second_turn'].get('generated_tokens') or 0)<=b) for x in items) for b in [32,64,128,256,512,1024]},
        capacity_counts={str(c):sum(x['input_tokens']+x.get('output_budget',256)<=c and (not x.get('second_turn') or x['second_turn']['input_tokens']+x['second_turn'].get('output_budget',256)<=c) for x in items) for c in [512,1024,2048,4096]})

def report(work):
    global CHECKER
    protocol=runner.rows_json(work/'protocol.json')
    CHECKER=runner.BFCLPythonChecker(ROOT/'build/v2/general-tool-data-v1/bfcl-python-checker')
    cases={c['id']:c for c in runner.rows(work/'evaluation.jsonl')}
    screen_ids=set(runner.rows_json(work/'screen-ids.json'))
    all_reports=[];failures=[];verified=0
    for model in runner.rows_json(work/'models.json'):
        folder=work/'runs'/model['key']
        stages={}
        for phase in ['screen','confirm']:
            if not (folder/f'{phase}-complete.json').exists():continue
            data=sum([runner.rows(folder/f'{phase}-{d}.jsonl') for d in ['maintenance','general','episode']],[])
            for r in data:
                v,c,a=audit_row(cases[r['id']],r,r['route'])
                for label,value in [('valid',v),('accepted',a)]:
                    if bool(r[label])!=value:failures.append([model['key'],phase,r['id'],label])
                if r['domain']=='episode':
                    v2,c2,a2=audit_row(cases[r['id']],r['second_turn'],r['route'],True)
                    for label,value in [('valid',v2),('accepted',a2)]:
                        if bool(r['second_turn'][label])!=value:failures.append([model['key'],phase,r['id'],'second_turn_'+label])
                    if bool(r['first_turn_correct'])!=c:failures.append([model['key'],phase,r['id'],'first_turn_correct'])
                    if bool(r['second_turn']['correct'])!=c2:failures.append([model['key'],phase,r['id'],'second_turn'])
                    c=c and c2
                if bool(r['correct'])!=c:failures.append([model['key'],phase,r['id'],'correct'])
                verified+=1
            stages[phase]={s:stats([r for r in data if r['subset']==s]) for s in ['fresh','conditional','bfcl','two_turn']}
            stages[phase]['bfcl_categories']={cat:stats([r for r in data if r['domain']=='general' and cases[r['id']]['category']==cat]) for cat in ['simple_python','multiple','parallel','parallel_multiple','irrelevance']}
            stages[phase]['operator_breakdown']={op:stats([r for r in data if r['subset']=='conditional' and cases[r['id']]['gold']['predicate']['op']==op]) for op in ['gt','ge','lt','le']}
            stages[phase]['episode_operator_breakdown']={op:stats([r for r in data if r['domain']=='episode' and cases[r['id']]['operator']==op]) for op in ['gt','ge','lt','le']}
            stages[phase]['fresh_strata']={name:stats([r for r in data if r['subset']=='fresh' and cases[r['id']]['stratum']==name]) for name in sorted({cases[r['id']]['stratum'] for r in data if r['subset']=='fresh'})}
            stages[phase]['all']=stats(data)
            if phase=='confirm':
                extra=[r for r in data if r['id'] not in screen_ids]
                stages['confirm_additional']={s:stats([r for r in extra if r['subset']==s]) for s in ['fresh','conditional','bfcl','two_turn']}
                stages['confirm_additional']['all']=stats(extra)
        if stages:all_reports.append(dict(model=model['key'],file_bytes=model['bytes'],stages=stages,routes=runner.rows_json(folder/'routes.json')))
    result=dict(models=all_reports,verified_records=verified,rescore_failures=failures,
        limitations=['Software quantized-weight capability screen, not FPGA arithmetic or target latency.',
        'Public BFCL and previously inspected template-derived maintenance development evidence.',
        'Two fixed maintenance training demonstrations added after initial zero-shot codec failures; initial attempts retained.',
        'Prompt route selected on 22 development records; model selection uses screening data.',
        'Confirmation includes repeated screen cases; neither is an independent blinded test.',
        'Output/context sensitivity counts are retrospective capacity accounting, not separate inference at every setting.',
        'Software requests ran four-way concurrently; wall times include contention and are not FPGA performance estimates.'])
    runner.dump(work/'independent-rescore.json',result)
    sample=next((m['stages']['screen'] for m in all_reports),{})
    denominators=[sample.get(s,{}).get('n',0) for s in ['fresh','conditional','bfcl','two_turn']]
    adapted=any('adaptation' in m for m in protocol['candidates'])
    lines=['# Quantized model capability comparison','',
        f"Profile: {protocol['primary_context']:,} total tokens, {protocol['output_tokens']:,} output tokens including any reasoning, thinking {'enabled' if protocol.get('thinking',False) else 'disabled'}, greedy full-vocabulary decoding, no grammar/semantic repair. {'Existing task-adapted checkpoint controls; no new training.' if adapted else 'Pretrained checkpoints; no task fine-tuning.'} Maintenance uses two fixed training demonstrations. General tool use uses a balanced public BFCL sample plus simulator-only dependent-action episodes. This is software inference; no FPGA performance is measured.",
        '', 'Runtime: '+runner.rows_json(work/'protocol.json')['generation'],'',
        f'| Model | File GiB | Fresh screen /{denominators[0]} | Conditional screen /{denominators[1]} | BFCL screen /{denominators[2]} | Two-turn episodes /{denominators[3]} |',
        '|---|---:|---:|---:|---:|---:|']
    for m in all_reports:
        s=m['stages']['screen'];lines.append(f"| {m['model']} | {m['file_bytes']/2**30:.3f} | {s['fresh']['correct']} | {s['conditional']['correct']} | {s['bfcl']['correct']} | {s['two_turn']['correct']} |")
    lines+=['','## Finalist confirmation','',
        '| Model | Fresh /120 | Conditional /64 | BFCL /200 | Two-turn episodes /12 | Wrong accepted maintenance plans | Context rejections |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for m in all_reports:
        if 'confirm' not in m['stages']:continue
        s=m['stages']['confirm'];lines.append(f"| {m['model']} | {s['fresh']['correct']} | {s['conditional']['correct']} | {s['bfcl']['correct']} | {s['two_turn']['correct']} | {s['fresh']['wrong_accepted']+s['conditional']['wrong_accepted']} | {s['all']['overflows']} |")
    lines+=['','## Interpretation limits','']+['- '+x for x in result['limitations']]
    lines+=['',f"Re-scored {verified} saved task records; scorer discrepancies: {len(failures)}. Detailed category, operator, validity, capacity and latency counts are in independent-rescore.json.",'']
    (work/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(dict(models=len(all_reports),records=verified,failures=failures)))
    if failures:raise RuntimeError('Independent rescoring disagrees')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--work',type=Path,default=ROOT/'build/v2/model-capability-20261102-r2')
    report(ap.parse_args().work.resolve())
