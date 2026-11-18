"""Frozen three-arm state pilot: trusted-observation retention versus closed loop."""
import copy
import json
import random
from .v8_benchmark import chat,transition,reduce_observed,encode_record
from .v8_chain_pilot_v5 import normalize as normalize_v5,strict_pairs,compact,request

VERSION='v8-state-pilot-v6-r2'
ARMS=('H','J','C')
CONTEXT=256
OUTPUT=48
SYSTEMS={
 'retention':('Tool observations are authoritative; previous answers do not update state. '
    'Missing/error observations preserve the last count. State is JSON or name:count,status. '
    'Answer the current query with status, entity and integer count as a JSON array or object. No explanation.'),
 'closed-loop':('Update counts A and B using the current request. State is JSON or name:count,status. '
    'Successful changes use ok; missing/error preserve the count. Prior replies change state only if accepted. '
    'Return status, entity and integer count as a JSON array or object. No explanation.')}


def normalize(text,*,terminal):
    try:return normalize_v5(text,terminal=terminal)
    except ValueError:pass
    import re
    body=text.strip();routes=[]
    fence=re.fullmatch(r'```(?:json)?\s*\n(.*?)\n```',body,re.DOTALL|re.IGNORECASE)
    if fence:body=fence[1].strip();routes.append('fence')
    row=json.loads(body,object_pairs_hook=strict_pairs)
    if type(row) is list and len(row)==1 and type(row[0]) is dict:
        row=row[0];routes.append('singleton-object-list')
    if type(row) is dict and 'name' in row and not ({'entity','target'} & set(row)):
        row=dict(row);row['entity']=row.pop('name');routes.append('name-alias')
    if not routes:raise ValueError('No additional declared normalization')
    parsed=normalize_v5(json.dumps(row),terminal=terminal)
    return dict(parsed,native_format=False,route='+'.join(routes+[parsed['route']]))


def render(state,arm):
    if arm=='C':return compact(state)
    if arm not in ('H','J'):raise ValueError('Unknown arm')
    return json.dumps({e:dict(count=v[0],status=v[1]) for e,v in sorted(state.items())},separators=(',',':'))


def apply_observation(state,event):
    result=copy.deepcopy(state)
    if event is None:return result
    e,status=event['entity'],event['status']
    value=event['count'] if status=='ok' else state[e][0]
    encode_record((status,e,value),'A')
    if status!='ok' and 'count' in event:raise ValueError('Missing/error observations must not supply a new count')
    result[e]=[value,status]
    return result


def expected(case,state,step):
    if case['mode']=='retention':
        e=step['entity'];return [state[e][1],e,state[e][0]]
    return list(transition(state,step))


def prompt(case,index,state,arm,history=(),accepted=None):
    mode=case['mode'];step=case['steps'][index]
    if arm not in ARMS:raise ValueError('Unknown arm')
    if mode=='retention':
        user=f'Report the latest status and count of {step["entity"]}.'
        if arm=='H':
            event=step['observation']
            user=('Tool observation '+json.dumps(event,separators=(',',':')) if event else 'No new tool observation.')+'\n'+user
    else:
        user=request(step)
        if arm=='H' and accepted is not None:
            user=('Previous reply accepted.\n' if accepted else 'Previous reply rejected; state unchanged.\n')+user
    if arm in ('J','C'):user='State '+render(state,arm)+'\n'+user
    elif index==0:user='Initial state '+render(case['initial'],'J')+'\n'+user
    return chat(SYSTEMS[mode],user,history if arm=='H' else ()),user


def make_cases(split):
    if split not in ('development','heldout'):raise ValueError('Split')
    rng=random.Random(20261021601 if split=='development' else 20261021602)
    a,b=rng.randint(111,149),rng.randint(211,249)
    # Triple-digit states distinguish these tasks from v2-v5; new random values
    # are fixed before inference. Same templates across independently seeded splits.
    def obs(e,status='ok',count=None):
        return dict(entity=e,status=status,**({'count':count} if status=='ok' else {}))
    def q(e,event):return dict(entity=e,observation=event)
    retention=dict(id=split+'-retention',split=split,mode='retention',
        initial={'A':[a,'ok'],'B':[b,'ok']},steps=[
            q('A',obs('A',count=a+7)),q('A',obs('B',count=b+9)),
            q('A',obs('A','missing')),q('B',obs('B',count=b+13)),
            q('A',obs('B','error')),q('A',obs('A',count=a+11)),
            q('B',None),q('A',obs('B',count=b+17))])
    e,f=('A','B') if split=='development' else ('B','A')
    def s(entity,op,number=1):return dict(entity=entity,op=op,number=number)
    closed=dict(id=split+'-closed-loop',split=split,mode='closed-loop',
        initial={'A':[a+3,'ok'],'B':[b+5,'ok']},steps=[
            s(e,'add',rng.randint(2,6)),s(f,'conditional',rng.randint(2,6)),
            s(e,'copy'),s(e,'conditional',rng.randint(2,6)),s(e,'missing'),
            s(f,'set',rng.randint(27,39)),s(f,'conditional',rng.randint(2,6)),s(e,'copy')])
    return [retention,closed]


def manifest():
    cases=make_cases('development')+make_cases('heldout')
    for i,c in enumerate(cases):c['arms']=list(ARMS[i%3:]+ARMS[:i%3])
    return dict(version=VERSION,cases=cases,arms=ARMS,context_limit=CONTEXT,output_budget=OUTPUT,
        maximum_inferences=160,seed_development=20261021601,seed_heldout=20261021602,
        controls='J/C oracle-state snapshots with exact state-arm prompt policy; H references J as a snapshot diagnostic only',
        retention_state='actual simulated tool observations; model answers are read-only and never update world state',
        closed_loop_state='model proposals committed verbatim; rejected output leaves state unchanged; gold is scorer-only',
        frozen_parser='v5 plus singleton-object-list and name alias, fixed using development only before heldout',prompt_policy='one fixed prompt per mode, shared by all arms; no examples or selection',
        full_sweep_started=False,board_access=False,scope='CPU-only exploratory pilot; 1 sequence per mode/split, no general reliability claim')


def campaign(spec,encode,infer,commit):
    rows=[];controls={}
    def run(job,state,gold,case,step):
        ids=encode(job['prompt']);target=expected(case,gold,step);local=expected(case,state,step)
        linked=controls.get(job.get('control_id'))
        base=dict(job,prompt_ids=ids,input_tokens=len(ids),state_before=copy.deepcopy(state),
            expected=target,local_expected=local,output_budget=spec['output_budget'],
            matches_snapshot_control_input=ids==linked['prompt_ids'] if linked else None,
            state_matches_snapshot_control=state==linked['state_before'] if linked else None,
            control_relation='matched-state-template' if job['arm'] in ('J','C') else 'snapshot-diagnostic-only')
        if linked and job['arm'] in ('J','C') and state==linked['state_before'] and ids!=linked['prompt_ids']:
            raise RuntimeError('Snapshot control prompt mismatch')
        if len(ids)+spec['output_budget']>spec['context_limit']:
            row=dict(base,status='context_exhausted',observed=None,accepted=False,native_format=None,
                correct=None,local_correct=None,state_after=copy.deepcopy(state),state_exact=None)
        else:
            # The inference interface never receives expected values or state objects.
            output=infer(dict(id=job['id'],prompt=job['prompt'],prompt_ids=ids,output_tokens=spec['output_budget']))
            try:parsed=normalize(output['generated_text'],terminal=output['terminal_eos'])
            except ValueError:parsed=None
            observed=parsed['record'] if parsed else None
            actual=copy.deepcopy(state) if case['mode']=='retention' else reduce_observed(state,observed)
            ideal=copy.deepcopy(gold) if case['mode']=='retention' else reduce_observed(gold,target)
            row=dict(base,**output,status='completed',observed=observed,accepted=parsed is not None,
                native_format=parsed['native_format'] if parsed else False,
                normalization_route=parsed['route'] if parsed else None,correct=observed==target,
                local_correct=observed==local,state_after=actual,state_exact=actual==ideal,
                inherited_only_error=bool(observed==local and observed!=target))
        rows.append(row);commit(row);return row
    def job(case,arm,i,text,suite):
        prefix='control' if suite=='snapshot-control' else 'chain'
        data=dict(id=f'{prefix}-{case["id"]}-{arm}-{i+1:02d}',suite=suite,
            case_id=case['id'],mode=case['mode'],split=case['split'],arm=arm,step=i+1,prompt=text)
        if suite!='snapshot-control':data['control_id']=f'control-{case["id"]}-{arm if arm in ("J","C") else "J"}-{i+1:02d}'
        return data
    for split in ('development','heldout'):
        cases=[c for c in spec['cases'] if c['split']==split]
        for case in cases:
            oracle=copy.deepcopy(case['initial'])
            for i,step in enumerate(case['steps']):
                if case['mode']=='retention':oracle=apply_observation(oracle,step['observation'])
                for arm in ('J','C'):
                    text,_=prompt(case,i,oracle,arm)
                    r=run(job(case,arm,i,text,'snapshot-control'),oracle,oracle,case,step);controls[r['id']]=r
                if case['mode']=='closed-loop':oracle=reduce_observed(oracle,expected(case,oracle,step))
        for case in cases:
            for arm in case['arms']:
                state=copy.deepcopy(case['initial']);gold=copy.deepcopy(case['initial']);history=[];accepted=None
                for i,step in enumerate(case['steps']):
                    if case['mode']=='retention':
                        state=apply_observation(state,step['observation']);gold=copy.deepcopy(state)
                    text,user=prompt(case,i,state,arm,history,accepted)
                    row=run(job(case,arm,i,text,'dependent'),state,gold,case,step)
                    if row['status']=='context_exhausted':break
                    state=copy.deepcopy(row['state_after'])
                    if case['mode']=='closed-loop':gold=reduce_observed(gold,expected(case,gold,step))
                    accepted=row['accepted'];history.extend([('user',user),('assistant',row['generated_text'])])
    return rows


def totals(rows):
    rs=[r for r in rows if r['status']=='completed']
    return dict(inferences=len(rs),accepted=sum(r['accepted'] for r in rs),preferred_array=sum(r['native_format'] for r in rs),
        correct=sum(r['correct'] for r in rs),locally_correct=sum(r['local_correct'] for r in rs),
        inherited_only_errors=sum(r['inherited_only_error'] for r in rs),
        capacity_stops=sum(r['status']=='context_exhausted' for r in rows),
        input_tokens=[r['input_tokens'] for r in rs],process_seconds=sum(r.get('seconds',0) for r in rs))


def summarize(rows):
    chains={}
    for r in rows:
        if r['suite']=='dependent':chains.setdefault(r['case_id']+'/'+r['arm'],[]).append(r)
    details={}
    for key,rs in chains.items():
        done=[r for r in rs if r['status']=='completed']
        first=lambda field:next((r['step'] for r in done if not r[field]),None)
        failed=first('correct')
        details[key]=dict(totals(rs),first_semantic_failure=failed,first_unparseable=first('accepted'),
            first_local_error=first('local_correct'),consecutive_correct_steps=failed-1 if failed else len(done),
            context_exhausted_at=next((r['step'] for r in rs if r['status']=='context_exhausted'),None),
            survival={str(k):(False if failed and failed<=k else all(r['correct'] for r in done[:k])
                if len(done)>=k else None) for k in (1,2,4,8)},
            full_state_recovery_steps=[r['step'] for i,r in enumerate(done) if i and rs[0]['mode']=='closed-loop'
                and r['state_exact'] and not done[i-1]['state_exact']])
    groups={}
    for suite in ('snapshot-control','dependent'):
        for split in ('development','heldout'):
            for mode in ('retention','closed-loop'):
                for arm in ARMS:
                    rs=[r for r in rows if (r['suite'],r['split'],r['mode'],r['arm'])==(suite,split,mode,arm)]
                    if rs:groups['/'.join((suite,split,mode,arm))]=totals(rs)
    return dict(version=VERSION,overall=totals(rows),groups=groups,chains=details,
        full_sweep_started=False,board_access=False,
        interpretation='Retention answers never alter tool state. Closed-loop errors propagate. Capacity stops are not NN failures. No cross-model or statistical reliability claim.')
