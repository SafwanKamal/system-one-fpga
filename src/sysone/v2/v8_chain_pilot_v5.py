"""Frozen, model-independent chain mechanics; Qwen-only exploratory pilot."""
import copy
import json
import re
from .v8_benchmark import chat,encode_record,parse_record,transition,reduce_observed

VERSION='v8-chain-pilot-v5'
OUTPUT_BUDGET=48
CONTEXT_LIMIT=256
SYSTEM=('Track counters A and B. State entries are name:count,status. Apply only the current request. '
    'Successful updates have status ok; missing/error preserve the count. '
    'Report status, target counter, and resulting integer count. Prefer a JSON array or an object '
    'with status,entity,count fields. Use accepted prior replies when no current state is supplied. '
    'No explanation.')


def strict_pairs(pairs):
    obj={}
    for key,value in pairs:
        if key in obj:raise ValueError('Duplicate JSON key')
        obj[key]=value
    return obj


def normalize(text,*,terminal):
    """Closed single JSON value, fenced value, or EOS-framed declared text form.

    No search for embedded answers, expected-value access, defaults or fuzzy
    matching. Aliases and lexical conversions are fixed before any pilot output.
    """
    native=False
    try:parse_record(text,'A');native=True
    except ValueError:pass
    body=text.strip();route=[]
    fence=re.fullmatch(r'```(?:json)?\s*\n(.*?)\n```',body,re.DOTALL|re.IGNORECASE)
    if fence:body=fence[1].strip();route.append('fence')
    try:row=json.loads(body,object_pairs_hook=strict_pairs)
    except ValueError:
        if not terminal:raise ValueError('Unframed or incomplete text record')
        m=re.fullmatch(r'(ok|missing|error)\s+([AB])\s+(-?(?:0|[1-9][0-9]{0,3}))',body,re.IGNORECASE)
        if not m:
            m=re.fullmatch(r'status\s*[:=]\s*(ok|missing|error)\s*[,;]\s*'
                r'(?:entity|target)\s*[:=]\s*([AB])\s*[,;]\s*'
                r'(?:count|value)\s*[:=]\s*(-?(?:0|[1-9][0-9]{0,3}))',body,re.IGNORECASE)
        if not m:raise ValueError('No single declared record')
        row=[m[1],m[2],int(m[3])];route.append('text')
    if type(row) is dict:
        keys=set(row)
        target_keys=keys & {'entity','target'};value_keys=keys & {'count','value','new_count'}
        if len(target_keys)!=1 or len(value_keys)!=1 or keys!={'status'}|target_keys|value_keys:
            raise ValueError('Unknown, missing or ambiguous fields')
        row=[row['status'],row[next(iter(target_keys))],row[next(iter(value_keys))]];route.append('object')
    if type(row) is not list or len(row)!=3:raise ValueError('Record shape')
    status,entity,number=row
    if type(status) is not str or type(entity) is not str:raise ValueError('Record types')
    if type(number) is str and re.fullmatch(r'-?(?:0|[1-9][0-9]{0,3})',number):
        number=int(number);route.append('integer-string')
    status,entity=status.lower(),entity.upper()
    record=(status,entity,number);encode_record(record,'A')
    return dict(record=list(record),native_format=native,route='+'.join(route) or 'array')


def compact(state):
    return ';'.join(f'{e}:{v},{s}' for e,(v,s) in sorted(state.items()))


def request(step):
    e,op,n=step['entity'],step['op'],step['number'];other='B' if e=='A' else 'A'
    if op=='set':text=f'Set {e} to {n}.'
    elif op=='copy':text=f'Copy the count of {other} into {e}.'
    elif op=='add':text=f'Add {n} to {e}.'
    elif op=='conditional':text=f'If {e} is greater than 50 subtract {n} from {e}; otherwise add {n} to {e}.'
    else:text=f'Report {op} for {e}, keeping its count unchanged.'
    return text+f' Report target {e}.'


def prompt(chain,index,state,arm,history,accepted=None):
    if arm not in ('H','C'):raise ValueError('Context arm')
    user=request(chain['steps'][index])
    if accepted is not None:user=('Previous reply accepted.\n' if accepted else 'Previous reply rejected; state unchanged.\n')+user
    if arm=='C' or index==0:user='State '+compact(state)+'\n'+user
    return chat(SYSTEM,user,history if arm=='H' else ()),user


def manifest():
    def s(e,op,n=1):return dict(entity=e,op=op,number=n)
    chains=[dict(id='simple',family='retrieval-status',initial={'A':[28,'ok'],'B':[74,'ok']},
        steps=[s('A','set',43),s('B','copy'),s('B','missing'),s('A','error'),
               s('A','set',36),s('B','copy'),s('A','missing'),s('B','error')],arms=['H','C']),
        dict(id='arithmetic',family='arithmetic',initial={'A':[32,'ok'],'B':[86,'ok']},
        steps=[s('A','add',4),s('B','conditional',7),s('A','copy'),s('A','conditional',6),
               s('A','missing'),s('B','set',26),s('B','conditional',5),s('A','copy')],arms=['C','H'])]
    return dict(version=VERSION,chains=chains,context_limit=CONTEXT_LIMIT,output_budget=OUTPUT_BUDGET,
        one_step_controls=True,normalization_policy='closed single record; fixed aliases/case/integer-string/fence handling',
        prompt_policy='One frozen generic prompt; no examples, model-specific codes, prompt selection or retries',
        full_sweep_started=False,full_sweep_restart_authorized=False,
        scope='Two eight-step exploratory chains. Qwen3-0.6B only; no scalable-compression or reliability claim.')


def campaign(spec,encode,infer,commit):
    """A backend owns its observed trajectory. Gold never updates that state."""
    rows=[]
    def run(job,state,gold,step):
        text=job['prompt'];ids=encode(text)
        expected=list(transition(gold,step));local=list(transition(state,step))
        base=dict(job,prompt_ids=ids,input_tokens=len(ids),state_before=copy.deepcopy(state),
            expected=expected,local_expected=local,output_budget=spec['output_budget'])
        if len(ids)+spec['output_budget']>spec['context_limit']:
            row=dict(base,status='context_exhausted',observed=None,correct=None,accepted=False,
                native_format=None,state_after=copy.deepcopy(state),state_exact=None,local_correct=None)
        else:
            output=infer(dict(job,prompt_ids=ids,output_tokens=spec['output_budget']))
            try:parsed=normalize(output['generated_text'],terminal=output['terminal_eos'])
            except ValueError:parsed=None
            observed=parsed['record'] if parsed else None
            actual=reduce_observed(state,observed)
            gold_after=reduce_observed(gold,expected)
            row=dict(base,**output,status='completed',observed=observed,accepted=parsed is not None,
                native_format=parsed['native_format'] if parsed else False,
                normalization_route=parsed['route'] if parsed else None,correct=observed==expected,
                local_correct=observed==local,state_after=actual,state_exact=actual==gold_after)
        rows.append(row);commit(row)
        return row
    # Explicit oracle-input controls isolate single-step competence. Their
    # states are NEVER fed back into either measured dependent trajectory.
    for chain in spec['chains']:
        gold=copy.deepcopy(chain['initial'])
        for i,step in enumerate(chain['steps']):
            control=dict(chain,steps=[step]);text,_=prompt(control,0,gold,'C',[])
            run(dict(id=f'control-{chain["id"]}-{i+1:02d}',suite='one-step-control',chain_id=chain['id'],
                family=chain['family'],arm='C',step=i+1,prompt=text),gold,gold,step)
            gold=reduce_observed(gold,transition(gold,step))
    for chain in spec['chains']:
        for arm in chain['arms']:
            state=copy.deepcopy(chain['initial']);gold=copy.deepcopy(chain['initial']);history=[];accepted=None
            for i,step in enumerate(chain['steps']):
                text,user=prompt(chain,i,state,arm,history,accepted)
                row=run(dict(id=f'chain-{chain["id"]}-{arm}-{i+1:02d}',suite='dependent',chain_id=chain['id'],
                    family=chain['family'],arm=arm,step=i+1,prompt=text),state,gold,step)
                if row['status']=='context_exhausted':break
                state=copy.deepcopy(row['state_after']);gold=reduce_observed(gold,transition(gold,step))
                accepted=row['accepted'];history.extend([('user',user),('assistant',row['generated_text'])])
    return rows


def summarize(rows):
    inferred=[r for r in rows if r['status']=='completed']
    chains={}
    for r in rows:
        if r['suite']=='dependent':chains.setdefault(r['chain_id']+'/'+r['arm'],[]).append(r)
    details={}
    for key,rs in chains.items():
        done=[r for r in rs if r['status']=='completed']
        first=lambda field:next((r['step'] for r in done if not r[field]),None)
        failed=first('correct')
        details[key]=dict(generated_steps=len(done),correct_steps=sum(r['correct'] for r in done),
            first_semantic_failure=failed,first_unparseable=first('accepted'),first_local_error=first('local_correct'),
            consecutive_correct_steps=(failed-1) if failed else len(done),
            context_exhausted_at=next((r['step'] for r in rs if r['status']=='context_exhausted'),None),
            exact_state_recovery_steps=[r['step'] for i,r in enumerate(done) if i and failed and r['step']>failed
                and r['state_exact'] and not done[i-1]['state_exact']],
            survival={str(k):(False if failed and failed<=k else
                all(r['correct'] for r in done[:k]) if len(done)>=k else None) for k in (1,2,4,8)},
            input_tokens=[r['input_tokens'] for r in rs],
            inference_seconds=sum(r.get('seconds',0) for r in done))
    return dict(version=VERSION,completed_inferences=len(inferred),native_format=sum(r['native_format'] for r in inferred),
        accepted=sum(r['accepted'] for r in inferred),correct=sum(r['correct'] for r in inferred),
        controls={family:dict(cases=sum(r['suite']=='one-step-control' and r['family']==family for r in inferred),
            correct=sum(r['suite']=='one-step-control' and r['family']==family and r['correct'] for r in inferred))
            for family in ('retrieval-status','arithmetic')},chains=details,full_sweep_started=False,
        note='Context stops are capacity observations, not semantic model failures; null survival is unobserved/censored.')
