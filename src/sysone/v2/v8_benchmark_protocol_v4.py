"""Compact state/string status prompt development; no deployment dependencies."""
import json
import random
from .v8_benchmark import encode_record, parse_record, transition
from .v8_benchmark_protocol_v2 import messages
from .v8_benchmark_protocol_v3 import render_state as render_v3, decode_compact, prompt as v3_prompt

VERSION='v8-protocol-v4'
OUTPUT_BUDGET=32
ARMS=[('C','A')]
CANDIDATES=('v3-control','two-tuple','two-named','prefilled-contrastive')
OPS=('set','add','copy','conditional','missing','error')


def render_state(state,candidate=None):
    return render_v3(state,'C','named-line' if candidate=='two-named' else 'tuple-array')


def parse_output(text,wire,*,terminal=False,candidate):
    if wire!='A' or candidate not in CANDIDATES:raise ValueError('Unsupported protocol')
    return parse_record(text,'A')


def instruction(step,candidate):
    e,op,n=step['entity'],step['op'],step['number']
    other='B' if e=='A' else 'A'
    if candidate=='prefilled-expression':
        expr={'set':str(n),'add':f'{e} + {n}','copy':other,
              'conditional':f'({e} - {n}) if ({e} > 50) else ({e} + {n})',
              'missing':e,'error':e}[op]
        return f'Target {e}. Evaluate new_count = {expr} using the current state. Return the integer result, not code.'
    if op=='set':return f'Set the count of {e} to {n}. Return the new count of {e}.'
    if op=='add':return f'Increase the current count of {e} by {n}. Return the new count of {e}.'
    if op=='copy':return f'Copy the current count of {other} into {e}. Return target {e} with that copied count.'
    if op=='conditional' and candidate=='prefilled-contrastive':
        return f'If {e}>50, return {e}-{n}; otherwise return {e}+{n}. Calculate the integer.'
    if op=='conditional':return (f'Look up the current count of {e}. If that number is greater than 50, '
        f'subtract {n} from it. If it is 50 or less, add {n} to it. Return the calculated count of {e}.')
    return f'Report {op} for {e}. Return the CURRENT count of {e} unchanged.'


def response_prefix(step,candidate):
    if candidate not in CANDIDATES:raise ValueError('Unsupported candidate')
    if not candidate.startswith('prefilled'):return ''
    status=step['op'] if step['op'] in ('missing','error') else 'ok'
    return json.dumps([status,step['entity']],separators=(',',':'))[:-1]+','


def prompt(state,step,context,wire,candidate,history=()):
    if context!='C' or wire!='A' or candidate not in CANDIDATES or history:
        raise ValueError('Only single-step compact state/string status is qualified')
    if candidate=='v3-control':return v3_prompt(state,step,context,wire,'tuple-array')
    if candidate in ('two-tuple','two-named'):
        system=('State rows are name:count,status. ' if candidate=='two-named'
                else 'State order: A count,A status,B count,B status. ')
        system+=('Apply the request to CURRENT state. Successful updates use ok. '
                 'Reply only with a JSON array: status string, target string, resulting integer. No Markdown.')
        demos=[]
        for s,e,n in [({'A':[64,'missing'],'B':[17,'error']},'A',7),
                      ({'A':[72,'error'],'B':[19,'missing']},'B',4)]:
            t=dict(entity=e,op=step['op'],number=n)
            demos.extend([('user','CURRENT state '+render_state(s,candidate)+'\n'+instruction(t,'prefilled-contrastive')),
                          ('assistant',encode_record(transition(s,t),'A'))])
        user='CURRENT state '+render_state(state,candidate)+'\n'+instruction(step,'prefilled-contrastive')
        return messages(system,user,demos),user
    system=('State order: A count,A status,B count,B status. '
        'Calculate the requested resulting count using the CURRENT state. '
        'Continue the assistant JSON array with only the resulting integer and closing bracket. '
        'No objects, Markdown or explanation.')
    demos=[]
    if candidate=='prefilled-contrastive' and step['op']=='conditional':
        # Fixed examples cover opposite branches and targets, independent of
        # the actual state, amount, predicate and qualification answers.
        for s,t in [({'A':[64,'ok'],'B':[17,'ok']},dict(entity='A',op='conditional',number=7)),
                    ({'A':[72,'ok'],'B':[19,'ok']},dict(entity='B',op='conditional',number=4))]:
            demos.extend([('user','CURRENT state '+render_state(s)+'\n'+instruction(t,candidate)),
                          ('assistant',encode_record(transition(s,t),'A'))])
    user='CURRENT state '+render_state(state)+'\n'+instruction(step,candidate)
    return messages(system,user,demos)+response_prefix(step,candidate),user


def cases(split):
    if split not in ('development','qualification'):raise ValueError('Unknown split')
    rng=random.Random(2026120101 if split=='development' else 2026120201)
    rows=[]
    for op in OPS:
        for i in range(8 if op=='conditional' else 4):
            entity='AB'[i%2]
            low=rng.randint(16,43);high=rng.randint(62,96)
            counts=[low,high] if (i//2)%2==0 else [high,low]
            if op=='conditional' and i>=4:counts['AB'.index(entity)]=50 if i<6 else 51
            state={e:[counts[j],('ok','missing','error')[(i+j)%3]] for j,e in enumerate('AB')}
            step=dict(entity=entity,op=op,number=rng.randint(2,9) if op!='set' else rng.randint(16,96))
            rows.append(dict(id=f'v4-{split}-{op}-{i}',state=state,step=step,expected=list(transition(state,step))))
    return rows


def qualification_manifest(candidate):
    return dict(version=VERSION,variant=candidate,output_budget=OUTPUT_BUDGET,arms=ARMS,
        cases=cases('qualification'),full_sweep_must_remain_stopped=True,
        gates=dict(per_arm_cases=28,per_arm_min_format_valid=26,per_arm_min_semantic_correct=21,
                   per_operation_min_semantic_correct={op:6 if op=='conditional' else 3 for op in OPS},
                   repeat_output_mismatches=0,all_contexts_fit=True,fixture_before_after=True,deployment_unchanged=True),
        interpretation='Single-step compact state/string status only; not chain-depth or production reliability')


def evaluate(rows,gates):
    measured=[r for r in rows if not r.get('repeat_of')]
    groups={'CA':dict(cases=len(measured),format_valid=sum(r['format_valid'] for r in measured),
                      correct=sum(r['correct'] for r in measured))}
    operations={op:dict(cases=sum(f'-{op}-' in r['case_id'] for r in measured),
        correct=sum(f'-{op}-' in r['case_id'] and r['correct'] for r in measured)) for op in OPS}
    g=groups['CA']
    passed=(g['cases']==gates['per_arm_cases'] and g['format_valid']>=gates['per_arm_min_format_valid']
        and g['correct']>=gates['per_arm_min_semantic_correct']
        and all(operations[op]['correct']>=n for op,n in gates['per_operation_min_semantic_correct'].items()))
    repeats=[r for r in rows if r.get('repeat_of')]
    originals={r['id']:r for r in measured}
    if repeats:
        passed=passed and len(repeats)==4 and all(r['generated_text']==originals[r['repeat_of']]['generated_text']
            and r.get('generated_ids')==originals[r['repeat_of']].get('generated_ids') for r in repeats)
    return groups,operations,passed
