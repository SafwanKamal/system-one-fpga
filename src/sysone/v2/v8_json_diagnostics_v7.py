"""CPU development diagnostics. V6 sources and evidence remain frozen."""
import copy
import json
import random
from collections import Counter
from .v8_benchmark import chat, transition, reduce_observed
from .v8_chain_pilot_v5 import request
from .v8_state_pilot_v6 import normalize, render, SYSTEMS

VERSION = 'v8-json-diagnostics-v7-r2'
SYSTEM = ('Apply the current operation to the supplied state. Return ONE result for the target only, '
          'as a JSON object with status, entity, count. Do not return both counters. '
          'Use the resulting integer count, not the old target count. '
          'Successful operations set status ok; missing/error keep the target count. No explanation.')


def instruction(step):
    e, op, n = step['entity'], step['op'], step['number']
    other = 'B' if e == 'A' else 'A'
    if op == 'copy':
        return f'Target {e}: replace its count with the count from source {other}. Set status ok.'
    if op == 'conditional':
        return (f'Target {e}: compare its count with 50. If count > 50, new count = count - {n}. '
                f'If count <= 50, new count = count + {n}. Set status ok.')
    if op == 'add':
        return f'Target {e}: new count = its current count + {n}. Set status ok.'
    if op == 'subtract':
        return f'Target {e}: new count = its current count - {n}. Set status ok.'
    if op == 'set':
        return f'Target {e}: replace its count with {n}. Set status ok.'
    return f'Target {e}: keep its current count and set status {op}.'


def make_prompt(state, step, policy):
    if policy not in ('original', 'clarified'):
        raise ValueError('Unknown prompt policy')
    old = request(step) if step['op'] != 'subtract' else f'Subtract {step["number"]} from {step["entity"]}. Report target {step["entity"]}.'
    return chat(SYSTEMS['closed-loop'] if policy == 'original' else SYSTEM,
                'State '+render(state, 'J')+'\n'+(old if policy == 'original' else instruction(step)))


def reference(state, step):
    """Separate explicit task oracle, scorer only; unknown operations fail closed."""
    e, op, n = step['entity'], step['op'], step['number']
    value = state[e][0]
    if op == 'set': value = n
    elif op == 'add': value = value + n
    elif op == 'subtract': value = value - n
    elif op == 'copy': value = state['B' if e == 'A' else 'A'][0]
    elif op == 'conditional': value = value - n if value > 50 else value + n
    elif op not in ('missing', 'error'): raise ValueError('Unknown operation')
    return [op if op in ('missing', 'error') else 'ok', e, value]


def admission(state, step, record):
    """Application contract only. No expected answer or arithmetic oracle access."""
    if record is None: return False, 'extraction'
    if record[1] != step['entity']: return False, 'wrong-target'
    if step['op'] in ('missing', 'error') and record[2] != state[step['entity']][0]:
        return False, 'preserve-count-contract'
    return True, None


def classify(observed, local, gold, terminal):
    if observed is None: return 'extraction-eos' if terminal else 'extraction-budget'
    if observed == gold: return 'correct'
    if observed == local: return 'inherited-only'
    return 'new-local-error-with-drift' if local != gold else 'new-local-error'


def audit_v6(rows, spec):
    cases = {c['id']: c for c in spec['cases']}
    oracle_steps={}
    for c in spec['cases']:
        if c['mode']!='closed-loop': continue
        gold=copy.deepcopy(c['initial'])
        for i,step in enumerate(c['steps'],1):
            oracle_steps[c['id'],i]=reference(gold,step)
            gold=reduce_observed(gold,oracle_steps[c['id'],i])
    audited = []
    for r in rows:
        if r['suite'] != 'dependent' or r['mode'] != 'closed-loop' or r['status'] != 'completed': continue
        step = cases[r['case_id']]['steps'][r['step']-1]
        local = reference(r['state_before'], step)
        if local != r['local_expected']: raise RuntimeError('V6 local oracle mismatch')
        if oracle_steps[r['case_id'],r['step']] != r['expected']: raise RuntimeError('V6 global oracle mismatch')
        actual = reduce_observed(r['state_before'], r['observed'])
        if actual != r['state_after']: raise RuntimeError('V6 reducer mismatch')
        category = classify(r['observed'], local, r['expected'], r['terminal_eos'])
        audited.append(dict(id=r['id'], arm=r['arm'], split=r['split'], op=step['op'],
                            category=category, mechanism=mechanism(r['state_before'],step,r['observed'],local), observed=r['observed'], local_expected=local,
                            global_expected=r['expected'], input_state_drift=r['state_matches_snapshot_control'] is False,
                            target_answer_affected_by_drift=local != r['expected'],
                            generated_text=r['generated_text']))
    return dict(rows=audited, by_arm={a: dict(Counter(r['category'] for r in audited if r['arm']==a)) for a in ('H','J','C')},
                oracle_and_reducer_mismatches=0,
                caveat='Categories are observational, not a causal fraction. Extraction can hide semantic errors; drift may coexist with a new local error.')


def mechanism(state, step, observed, local):
    """Descriptive output patterns; does not establish the model's internal cause."""
    if observed is None: return 'unparseable'
    if observed==local: return 'locally-correct'
    e=step['entity'];op=step['op'];n=step['number']
    if observed[1]!=e: return 'wrong-entity'
    if observed[2]==local[2] and observed[0]!=local[0]: return 'wrong-status'
    if observed[2]==state[e][0]: return 'old-target-count'
    if op=='conditional':
        opposite=state[e][0]+n if state[e][0]>50 else state[e][0]-n
        if observed[2]==opposite: return 'opposite-conditional-branch'
    return 'other-wrong-count'


def manifest():
    rng = random.Random(20261021702)
    def s(e, op, n=1): return dict(entity=e, op=op, number=n)
    cases = []
    for i, (e, f) in enumerate((('A','B'), ('B','A'))):
        cases.append(dict(id=f'dev-chain-{i+1}', initial={'A':[rng.randint(151,179),'ok'],'B':[rng.randint(271,299),'error']},
            steps=[s(e,'add',rng.randint(3,7)), s(f,'conditional',rng.randint(3,7)), s(e,'copy'),
                   s(e,'missing'), s(f,'set',50-i), s(f,'conditional',rng.randint(3,7)), s(e,'error'), s(e,'copy')]))
    probes=[]
    for i,value in enumerate((49,50,51)):
        for op in ('add','subtract','conditional','copy'):
            e='A' if i%2==0 else 'B'
            other='B' if e=='A' else 'A'
            state={e:[value,'missing'],other:[value+93,'error']}
            probes.append(dict(id=f'dev-r2-probe-{i}-{op}', initial=state, steps=[s(e,op,6+i)]))
    return dict(version=VERSION, split='development-only', cases=cases, probes=probes,
                policies=['original','clarified'], context_limit=256, output_budget=48,
                maximum_inferences=88, full_sweep_started=False, board_access=False,
                commit_policy='target match and missing/error count-preservation contract; no arithmetic validation or repair',
                scope='Prompt development, not heldout qualification; no improvement/generalization claim')


def campaign(spec, encode, infer, commit):
    rows=[]
    def run(case, i, state, gold, policy, suite):
        step=case['steps'][i];text=make_prompt(state, step, policy);ids=encode(text)
        base=dict(id=f'{suite}-{case["id"]}-{policy}-{i+1:02d}', case_id=case['id'], step=i+1,
                  suite=suite, policy=policy, op=step['op'], prompt=text, prompt_ids=ids,
                  input_tokens=len(ids), state_before=copy.deepcopy(state))
        if len(ids)+spec['output_budget']>spec['context_limit']: raise RuntimeError('Development prompt exceeds budget')
        # Gold and state objects are never passed to inference.
        out=infer(dict(id=base['id'],prompt=text,prompt_ids=ids,output_tokens=spec['output_budget']))
        try: parsed=normalize(out['generated_text'],terminal=out['terminal_eos'])
        except ValueError: parsed=None
        observed=parsed['record'] if parsed else None
        accepted, reason=admission(state,step,observed)
        local=reference(state,step);target=reference(gold,step)
        after=reduce_observed(state,observed) if accepted else copy.deepcopy(state)
        row=dict(base,**out,observed=observed,parsed=parsed is not None,committed=accepted,rejection_reason=reason,
                 expected=target,local_expected=local,correct=observed==target,local_correct=observed==local,
                 state_after=after,category=classify(observed,local,target,out['terminal_eos']),
                 state_exact=after==reduce_observed(gold,target),
                 state_drift_before=state!=gold,target_answer_affected_by_drift=local!=target)
        rows.append(row);commit(row);return row
    for case in spec['cases']:
        for policy in spec['policies']:
            gold=copy.deepcopy(case['initial']);state=copy.deepcopy(gold)
            for i, step in enumerate(case['steps']):
                # Ideal-state controls are separate from measured trajectory, never repairs.
                run(case,i,gold,gold,policy,'snapshot')
                r=run(case,i,state,gold,policy,'chain');state=r['state_after']
                gold=reduce_observed(gold,reference(gold,step))
    for case in spec['probes']:
        for policy in spec['policies']:run(case,0,case['initial'],case['initial'],policy,'primitive')
    return rows


def summarize(rows):
    groups={}
    for policy in ('original','clarified'):
        for suite in ('chain','snapshot','primitive'):
            rs=[r for r in rows if r['policy']==policy and r['suite']==suite]
            groups[policy+'/'+suite]=dict(n=len(rs),correct=sum(r['correct'] for r in rs),
                locally_correct=sum(r['local_correct'] for r in rs),parsed=sum(r['parsed'] for r in rs),
                committed=sum(r['committed'] for r in rs),categories=dict(Counter(r['category'] for r in rs)),
                by_operation={op:dict(n=len(sub),correct=sum(r['correct'] for r in sub))
                    for op in sorted({r['op'] for r in rs}) for sub in [[r for r in rs if r['op']==op]]})
    return dict(version=VERSION,groups=groups,board_access=False,full_sweep_started=False,
                interpretation='Development-only paired diagnostics, not new heldout evidence. Arithmetic/copy errors remain model errors; never host-repaired.')
