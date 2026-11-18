"""Candidate EOS-aware framing. Not used to rewrite frozen v1 results."""
import re
import json
import random
from .v8_benchmark import STATUSES, encode_record, parse_record, transition

VERSION = 'v8-protocol-v2'
OUTPUT_BUDGET = 32
ARMS = [(context, wire) for context in ('H', 'J', 'C') for wire in ('A', 'E')]


def parse_enum_record(text, *, terminal=False):
    """EOS may delimit a complete record; a partial number never terminates it.

    Streaming callers pass terminal=True only after an actual EOS token or an
    independently framed end-of-record, never because a prefix looks parseable.
    """
    boundary = r'\n' if not terminal else r'\n?'
    match = re.fullmatch(r'([012]) ([AB]) (-?(?:0|[1-9][0-9]{0,3}))'+boundary, text)
    if not match: raise ValueError('Incomplete or malformed enum record')
    result=(STATUSES[int(match[1])],match[2],int(match[3]))
    encode_record(result,'E')
    return result


def parse_output(text, wire, *, terminal=False):
    if wire == 'A': return parse_record(text, 'A')
    if wire == 'E': return parse_enum_record(text, terminal=terminal)
    raise ValueError('Unknown wire')


def system_prompt(wire, context):
    text = ('Update counters A and B from the supplied state. Change only the counter named in the request. '
            'A successful update has status ok. For missing or error, keep the old count and report that status. ')
    if wire == 'A':
        text += ('Return only a valid JSON array with three elements: a status string, '
                 'a counter name string, and the resulting integer. Status is "ok", "missing", or "error". '
                 'Use double quotes and square brackets. No field labels or explanation.')
    else:
        text += ('Return only three space-separated fields: status digit, counter letter, resulting integer. '
                 'Status digits: 0 means ok, 1 means missing, 2 means error. No field labels or explanation.')
    if context == 'C':
        text += ' State entries are counter=count/statusDigit; all counts use unit count. Status digits:0=ok,1=missing,2=error.'
    return text


def render_state(state, context):
    if context == 'C':
        return ' '.join(f'{entity}={value}/{STATUSES.index(status)}' for entity,(value,status) in sorted(state.items()))
    return json.dumps({entity:dict(count=value,status=status) for entity,(value,status) in sorted(state.items())},separators=(',',':'))


def step_text(step):
    e,op,n=step['entity'],step['op'],step['number']
    if op=='add':return f'Add {n} to counter {e}.'
    if op=='set':return f'Set counter {e} to {n}.'
    if op=='copy':return f'Set counter {e} to the current count of counter {"B" if e=="A" else "A"}.'
    if op=='conditional':return f'For counter {e}: if its count is greater than 50, subtract {n}; otherwise add {n}.'
    return f'Counter {e} has a {op} result. Report status {op} without changing its count.'


def messages(system, user, history=()):
    text='<|im_start|>system\n'+system+'<|im_end|>\n'
    for role,body in history:
        text+='<|im_start|>'+role+'\n'+body+'<|im_end|>\n'
    return text+'<|im_start|>user\n'+user+'<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'


def prompt(state, step, context, wire, variant, history=()):
    demos=[]
    if variant=='demonstration':
        demos=[('user','State {"A":{"count":2,"status":"ok"},"B":{"count":8,"status":"ok"}}\nSet counter A to 5.'),
               ('assistant',encode_record(('ok','A',5),wire).rstrip('\n'))]
    elif variant!='plain':raise ValueError('Unknown prompt variant')
    user=step_text(step)
    if context!='H' or not history:user='State '+render_state(state,context)+'\n'+user
    return messages(system_prompt(wire,context),user,demos+list(history) if context=='H' else demos),user


def cases(split):
    rng=random.Random(20261022 if split=='development' else 20261023)
    count=1 if split=='development' else 2
    result=[]
    for op in ('set','add','copy','conditional','missing','error'):
        for i in range(count):
            state={'A':[rng.randint(15,39),'ok'],'B':[rng.randint(55,79),'ok']}
            step=dict(entity='A' if i==0 else 'B',op=op,number=rng.randint(2,4) if op!='set' else rng.randint(15,39))
            result.append(dict(id=f'{split}-{op}-{i}',state=state,step=step,expected=list(transition(state,step))))
    return result


def qualification_manifest(variant):
    # Gate declared before unseen qualification responses. This gate admits an
    # experimental benchmark, not deployment of a reliable autonomous controller.
    return dict(version=VERSION,variant=variant,output_budget=OUTPUT_BUDGET,
        gates=dict(per_arm_min_format_valid=11,per_arm_min_semantic_correct=9,per_arm_cases=12,
                   all_contexts_fit=True,fixture_before_after=True,deployment_unchanged=True),
        interpretation='Protocol admission only; no production reliability guarantee',
        cases=cases('qualification'),arms=ARMS)
