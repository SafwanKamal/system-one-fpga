"""Expanded JSON snapshot retention; observations, never model replies, update state."""
import copy
import json
import random
from collections import Counter
from .v8_state_pilot_v6 import apply_observation, normalize, render, SYSTEMS
from .v8_benchmark import chat

VERSION='v8-json-retention-v9'
CONTEXT=256
OUTPUT=48


def manifest():
    cases=[]
    for length in (16,32,64):
        for family in ('mixed','long-gap'):
            seed=20261021900+length+(1000 if family=='long-gap' else 0)
            rng=random.Random(seed)
            initial={'A':[rng.randrange(301,500),'ok'],'B':[rng.randrange(701,900),'ok']}
            steps=[]
            def event(e,status):
                return dict(entity=e,status=status,**({'count':rng.randrange(301,950)} if status=='ok' else {}))
            # All initial values and refreshes are new task data, not previous pilot cases.
            for i in range(length):
                if family=='mixed':
                    schedule=[('A','ok','A'),('B','ok','A'),('A','missing','A'),(None,None,'A'),
                              ('B','error','B'),(None,None,'B'),('A','ok','A'),('B','ok','B'),
                              ('B','missing','A'),(None,None,'B'),('A','error','A'),(None,None,'A'),
                              ('B','ok','A'),('A','ok','B'),(None,None,'B'),(None,None,'A')]
                    e,status,q=schedule[i%16]
                elif i==0:e,status,q='A','missing','A'
                elif i==length-1:e,status,q='A','ok','A'
                else:
                    e='B' if i%5 else None
                    status=('ok','missing','error')[i%3] if e else None
                    q='A' if i%3 else 'B'
                steps.append(dict(entity=q,observation=event(e,status) if e else None))
            cases.append(dict(id=f'{family}-{length}',split='fresh-evaluation',mode='retention',
                              family=family,seed=seed,initial=initial,steps=steps))
    return dict(version=VERSION,cases=cases,context_limit=CONTEXT,output_budget=OUTPUT,
                maximum_inferences=sum(len(c['steps'])+2 for c in cases),
                prompt_policy='unchanged frozen v6 retention system prompt and JSON snapshot query',
                parser_policy='unchanged v6-r2 tolerant parser; no missing-field or semantic repair',
                retention_policy='trusted simulated tool observations update reducer; model answers read-only',
                repeats='exact first and last input of each chain, separate from primary accuracy',
                board_access=False,full_sweep_started=False,closed_loop_included=False,
                scope='six fixed sequences, two workloads per length; exploratory, one pinned model, not a full sweep')


def prepare(spec,encode):
    jobs=[]
    for case in spec['cases']:
        state=copy.deepcopy(case['initial']);age={'A':0,'B':0};chain=[]
        for i,step in enumerate(case['steps'],1):
            state=apply_observation(state,step['observation'])
            age={e:n+1 for e,n in age.items()}
            if step['observation']:age[step['observation']['entity']]=0
            e=step['entity'];obs=step['observation']
            text=chat(SYSTEMS['retention'],'State '+render(state,'J')+'\n'+f'Report the latest status and count of {e}.')
            ids=encode(text)
            if len(ids)+spec['output_budget']>spec['context_limit']:raise ValueError('Input capacity exceeded')
            row=dict(id=f'{case["id"]}-{i:03d}',case_id=case['id'],family=case['family'],chain_length=len(case['steps']),
                     suite='primary',step=i,entity=e,observation=obs,state=copy.deepcopy(state),
                     expected=[state[e][1],e,state[e][0]],query_age=age[e],
                     event_relation='none' if obs is None else 'target' if obs['entity']==e else 'distractor',
                     prompt=text,prompt_ids=ids,input_tokens=len(ids),output_tokens=spec['output_budget'])
            chain.append(row)
        jobs.extend(chain)
        for index in (0,-1):
            r=copy.deepcopy(chain[index]);r.update(id='repeat-'+r['id'],suite='repeat',repeat_of=r['id']);jobs.append(r)
    if len(jobs)!=spec['maximum_inferences']:raise ValueError('Inference count mismatch')
    return jobs


def execute(job,infer):
    # The scorer's reference and reducer state are not passed to model inference.
    output=infer({k:job[k] for k in ('id','prompt','prompt_ids','output_tokens')})
    try:parsed=normalize(output['generated_text'],terminal=output['terminal_eos'])
    except ValueError:parsed=None
    record=parsed['record'] if parsed else None
    correct=record==job['expected']
    category=('correct' if correct else 'parsed-wrong' if parsed else
              'extraction-eos' if output['terminal_eos'] else 'extraction-budget')
    return dict(job,**output,observed=record,parsed=parsed is not None,correct=correct,category=category,
                wrong_fields=[name for i,name in enumerate(('status','entity','count'))
                              if record is not None and record[i]!=job['expected'][i]],
                normalization_route=parsed['route'] if parsed else None)


def summarize(rows):
    primary=[r for r in rows if r['suite']=='primary'];by_id={r['id']:r for r in primary}
    def totals(rs):
        return dict(n=len(rs),correct=sum(r['correct'] for r in rs),parsed=sum(r['parsed'] for r in rs),
                    categories=dict(Counter(r['category'] for r in rs)))
    chains={}
    for name in sorted({r['case_id'] for r in primary}):
        rs=[r for r in primary if r['case_id']==name]
        fail=next((r['step'] for r in rs if not r['correct']),None)
        chains[name]=dict(totals(rs),first_failure=fail,all_correct=fail is None,
             longest_correct_run=max((len(x) for x in ''.join('1' if r['correct'] else '0' for r in rs).split('0')),default=0),
             survival={str(k):all(r['correct'] for r in rs[:k]) if len(rs)>=k else None for k in (8,16,32,64)})
    unique={}
    for r in primary:unique.setdefault(tuple(r['prompt_ids']),r)
    repeats=[r for r in rows if r['suite']=='repeat']
    return dict(version=VERSION,primary=totals(primary),chains=chains,
        by_length={str(n):totals([r for r in primary if r['chain_length']==n]) for n in (16,32,64)},
        by_status={s:totals([r for r in primary if r['expected'][0]==s]) for s in ('ok','missing','error')},
        by_event_relation={s:totals([r for r in primary if r['event_relation']==s]) for s in ('target','distractor','none')},
        by_query_age={s:totals([r for r in primary if (r['query_age']>=8 if s=='8+' else r['query_age']<8)]) for s in ('0-7','8+')},
        unique_inputs=totals(list(unique.values())),repeat_count=len(repeats),
        repeat_text_mismatches=sum(r['generated_text']!=by_id[r['repeat_of']]['generated_text'] for r in repeats),
        input_token_range=[min(r['input_tokens'] for r in primary),max(r['input_tokens'] for r in primary)],
        board_access=False,full_sweep_started=False,closed_loop_included=False,
        limitations=['Host reducer supplies complete latest state each request; chain length is not model context width.',
                     'Read-only replies cannot cause model-driven drift. This is not closed-loop reasoning.',
                     'Two fixed workload sequences per length; repeated snapshots are correlated; unique-input results reported separately.',
                     'CPU includes per-request model loading; no FPGA performance or cross-model claims.'])
