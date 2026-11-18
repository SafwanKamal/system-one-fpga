"""Status-copy development and fresh retention evaluation; no closed-loop changes."""
import copy
import random
from .v8_benchmark import chat
from .v8_state_pilot_v6 import render,SYSTEMS
from .v8_json_retention_v9 import manifest as v9_manifest,prepare as v9_prepare,execute,summarize as v9_summarize

VERSION='v8-json-retention-v10-r3'
SYSTEM=('Read the supplied JSON state as authoritative. Copy the requested entity\'s stored status exactly: '
        'missing stays missing, error stays error, ok stays ok. Never replace missing or error with ok. '
        'Status is not the success of answering. Copy its stored integer count unchanged. '
        'Return one JSON object with status, entity, count. No explanation.')


def prompt(state,entity,policy):
    if policy=='original':
        return chat(SYSTEMS['retention'],'State '+render(state,'J')+'\n'+f'Report the latest status and count of {entity}.')
    if policy!='status-copy':raise ValueError('Unknown prompt policy')
    return chat(SYSTEM,'State '+render(state,'J')+'\n'+f'For {entity}, return status from State.{entity}.status, entity {entity}, and count from State.{entity}.count.')


def development(encode,include_original=True):
    rng=random.Random(202610211001);jobs=[]
    for repeat in range(2):
        for a in ('ok','missing','error'):
            for b in ('ok','missing','error'):
                for entity in ('A','B'):
                    state={'A':[rng.randrange(301,650),a],'B':[rng.randrange(651,950),b]}
                    case=f'dev-{repeat}-{a}-{b}-{entity}'
                    for policy in (('original','status-copy') if include_original else ('status-copy',)):
                        text=prompt(state,entity,policy);ids=encode(text)
                        if len(ids)+48>256:raise ValueError('Development input exceeds context')
                        jobs.append(dict(id=case+'-'+policy,case_id=case,suite='development',policy=policy,
                            entity=entity,state=copy.deepcopy(state),expected=[state[entity][1],entity,state[entity][0]],
                            prompt=text,prompt_ids=ids,input_tokens=len(ids),output_tokens=48))
    return dict(version=VERSION,phase='development',seed=202610211001,unique_cases=36,
                maximum_inferences=len(jobs),context_limit=256,output_budget=48,
                gate='status-copy must score 36/36 full records; no parser changes or gold repair',
                comparison='Same development cases as first attempt; original baseline is sealed at v8-json-retention-v10/development',
                closed_loop_included=False,board_access=False,full_sweep_started=False),jobs


def evaluation_manifest():
    spec=copy.deepcopy(v9_manifest());spec.update(version=VERSION,phase='evaluation',
        prompt_policy='frozen status-copy instruction selected using fresh development only',
        evaluation_seed_base=202610211100,
        parser_policy='unchanged v6-r2 parser and v9 scorer, no domain-value normalization/repair',
        comparison='fresh evaluation of selected prompt; raw v9 and v10 evaluation scores are not paired')
    for index,c in enumerate(spec['cases']):
        seed=202610211100+index;rng=random.Random(seed);swap=bool(rng.getrandbits(1))
        c.update(id='eval-'+c['id'],split='fresh-evaluation',seed=seed,swap_entities=swap)
        c['initial']={'A':[rng.randrange(301,650),'ok'],'B':[rng.randrange(651,950),'ok']}
        for step in c['steps']:
            if step['observation'] and step['observation']['status']=='ok':
                step['observation']['count']=rng.randrange(301,950)
        if c['family']=='long-gap' and len(c['steps'])==32:
            c['steps'][0]['observation']['status']='error'
        if swap:
            other=lambda e:'B' if e=='A' else 'A'
            c['initial']={other(e):v for e,v in c['initial'].items()}
            for step in c['steps']:
                step['entity']=other(step['entity'])
                if step['observation']:step['observation']['entity']=other(step['observation']['entity'])
    return spec


def evaluation(encode):
    spec=evaluation_manifest();jobs=v9_prepare(spec,encode)
    for row in jobs:
        row['policy']='status-copy';row['prompt']=prompt(row['state'],row['entity'],'status-copy')
        row['prompt_ids']=encode(row['prompt']);row['input_tokens']=len(row['prompt_ids'])
        if row['input_tokens']+48>256:raise ValueError('Evaluation input exceeds context')
    return spec,jobs


def development_summary(rows):
    groups={}
    for policy in ('original','status-copy'):
        rs=[r for r in rows if r['policy']==policy]
        groups[policy]=dict(n=len(rs),correct=sum(r['correct'] for r in rs),parsed=sum(r['parsed'] for r in rs),
            by_status={s:dict(n=len(sub),correct=sum(r['correct'] for r in sub)) for s in ('ok','missing','error')
                       for sub in [[r for r in rs if r['expected'][0]==s]]})
    passed=groups['status-copy']['n']==36 and groups['status-copy']['correct']==36
    return dict(version=VERSION,groups=groups,gate_passed=passed,selected_policy='status-copy' if passed else None,
                closed_loop_included=False,board_access=False,full_sweep_started=False)


def summarize(rows):
    result=v9_summarize(rows);result['version']=VERSION
    result['comparison']='Fresh evaluation, not paired with v9. Development original/status-copy is paired.'
    return result
