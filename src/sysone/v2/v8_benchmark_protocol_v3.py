"""Development-selected v3 state/record protocols; sealed v1/v2 untouched."""
import json
import random
from .v8_benchmark import STATUSES, encode_record, parse_record, transition
from .v8_benchmark_protocol_v2 import messages, parse_enum_record

VERSION='v8-protocol-v3'
OUTPUT_BUDGET=32
ARMS=[(c,w) for c in ('H','J','C') for w in ('A','E')]
CANDIDATES=('named-line','named-array','tuple-array')


def encode_output(record,wire,candidate):
    encode_record(record,'A')
    if wire=='A':return encode_record(record,'A')
    if wire!='E' or candidate not in CANDIDATES:raise ValueError('Unknown protocol')
    status,entity,value=record
    if candidate=='named-line':return encode_record(record,'E')
    return json.dumps([STATUSES.index(status),entity,value],separators=(',',':'))


def parse_output(text,wire,*,terminal=False,candidate):
    if wire=='A':return parse_record(text,'A')
    if wire!='E' or candidate not in CANDIDATES:raise ValueError('Unknown protocol')
    if candidate=='named-line':return parse_enum_record(text,terminal=terminal)
    row=json.loads(text)
    if type(row) is not list or len(row)!=3 or type(row[0]) is not int or not 0<=row[0]<3:
        raise ValueError('Invalid numeric-status record')
    result=(STATUSES[row[0]],row[1],row[2]);encode_record(result,'A')
    return result


def render_state(state,context,candidate):
    if context in ('H','J'):
        return json.dumps({k:dict(count=v[0],status=v[1]) for k,v in sorted(state.items())},separators=(',',':'))
    if context!='C' or candidate not in CANDIDATES:raise ValueError('Unknown state protocol')
    if candidate=='tuple-array':
        return json.dumps([state['A'][0],state['A'][1],state['B'][0],state['B'][1]],separators=(',',':'))
    return ';'.join(f'{k}:{v[0]},{v[1]}' for k,v in sorted(state.items()))


def decode_compact(text,candidate):
    if candidate=='tuple-array':
        row=json.loads(text)
        if type(row) is not list or len(row)!=4:raise ValueError('State shape')
        result={'A':[row[0],row[1]],'B':[row[2],row[3]]}
    elif candidate in ('named-line','named-array'):
        import re
        match=re.fullmatch(r'A:(-?(?:0|[1-9][0-9]{0,3})),(ok|missing|error);B:(-?(?:0|[1-9][0-9]{0,3})),(ok|missing|error)',text)
        if not match:raise ValueError('Malformed named state')
        result={'A':[int(match[1]),match[2]],'B':[int(match[3]),match[4]]}
    else:raise ValueError('Unknown state protocol')
    for entity,(count,status) in result.items():encode_record((status,entity,count),'A')
    return result


def system_prompt(context,wire,candidate):
    text='Apply the request to the two counters. Output the requested target counter, not the source. '
    if wire=='A':text+='Reply only with a JSON array: status string, target string, new count integer. '
    elif candidate=='named-line':text+='Reply only with three space-separated fields: status digit, target letter, new count integer. '
    else:text+='Reply only with a JSON array: status digit, target string, new count integer. '
    if wire=='E':text+='Digits:0=ok,1=missing,2=error. '
    else:text+='Statuses:ok,missing,error. '
    if context=='C':
        text+=('State array order:A count,A status,B count,B status. ' if candidate=='tuple-array'
               else 'State rows are name:count,status. ')
    return text+'Counts use unit count. No labels or explanation.'


def step_text(step):
    e,op,n=step['entity'],step['op'],step['number'];other='B' if e=='A' else 'A'
    if op=='set':text=f'Set {e} to {n}.'
    elif op=='add':text=f'Add {n} to {e}.'
    elif op=='copy':text=f'Output target {e} using the count stored under {other}.'
    elif op=='conditional':text=f'Update {e}: if its count > 50, subtract {n}; otherwise add {n}.'
    else:text=f'Result for {e}: {op}. Retain its existing count.'
    return text+f' Return target {e}.'


def demonstrations(op):
    # Retrieval depends ONLY on request family, never actual values, predicate,
    # expected answer or qualification responses. Same examples for all arms.
    initial={'A':[2,'ok'],'B':[8,'ok']}
    if op=='conditional':return [(initial,dict(entity='A',op=op,number=1))]
    return [(initial,dict(entity='A',op=op,number=3 if op in ('set','add') else 1))]


def prompt(state,step,context,wire,candidate,history=()):
    if candidate not in CANDIDATES:raise ValueError('Unknown candidate')
    demos=[]
    for initial,example in demonstrations(step['op']):
        demos.extend([('user','State '+render_state(initial,context,candidate)+'\n'+step_text(example)),
                      ('assistant',encode_output(transition(initial,example),wire,candidate).rstrip('\n'))])
    user=step_text(step)
    if context!='H' or not history:user='State '+render_state(state,context,candidate)+'\n'+user
    system=system_prompt(context,wire,candidate)
    status=step['op'] if step['op'] in ('missing','error') else 'ok'
    # The current event explicitly supplies this status in the task definition;
    # no target count, arithmetic result or branch predicate is supplied here.
    if wire=='E':system+=f' Use status digit {STATUSES.index(status)} for both targets.'
    else:system+=f' Use status "{status}".'
    if step['op'] in ('missing','error'):system+=' Copy target count from state, not the example.'
    if step['op']=='conditional':system+=' Compute the changed count. Branch examples:120>50 subtract;2<50 add.'
    return messages(system,user,demos+list(history) if context=='H' else demos),user


def cases(split):
    if split not in ('development','qualification'):raise ValueError('Split')
    rng=random.Random(2026103101 if split=='development' else 2026110101)
    result=[]
    for op in ('set','add','copy','conditional','missing','error'):
        for i in range(2):
            state={'A':[rng.randint(16,44),'ok'],'B':[rng.randint(56,94),'ok']}
            step=dict(entity='AB'[i],op=op,number=rng.randint(1,5) if op!='set' else rng.randint(16,44))
            result.append(dict(id=f'v3-{split}-{op}-{i}',state=state,step=step,expected=list(transition(state,step))))
    return result


def qualification_manifest(candidate):
    return dict(version=VERSION,variant=candidate,output_budget=OUTPUT_BUDGET,cases=cases('qualification'),arms=ARMS,
        gates=dict(per_arm_cases=12,per_arm_min_format_valid=11,per_arm_min_semantic_correct=9,
                   all_contexts_fit=True,fixture_before_after=True,deployment_unchanged=True),
        interpretation='Single-step research protocol admission, not production reliability or chain-depth proof',
        output_E=('space-separated status digit/target/count' if candidate=='named-line'
                  else 'JSON array [status digit,target string,count integer]'),
        full_sweep_must_remain_stopped=True)
