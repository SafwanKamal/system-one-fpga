"""Versioned v8 benchmark protocol; no hardware imports or production mutations."""
import json
import random
import re

VERSION = 'v8-baseline-v1'
SEED = 20261021
STATUSES = ('ok', 'missing', 'error')
OUTPUT_RESERVE = 24


def chat(system, user, history=()):
    text = '<|im_start|>system\n'+system+'<|im_end|>\n'
    for role, content in history:
        text += '<|im_start|>'+role+'\n'+content+'<|im_end|>\n'
    return text+'<|im_start|>user\n'+user+'<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'


def encode_record(action, wire):
    status, entity, value = action
    if status not in STATUSES or entity not in ('A', 'B') or type(value) is not int or not -9999 <= value <= 9999:
        raise ValueError('Invalid semantic record')
    if wire == 'A': return json.dumps([status, entity, value], separators=(',', ':'))
    if wire == 'E': return f'{STATUSES.index(status)} {entity} {value}\n'
    raise ValueError('Unknown wire format')


def parse_record(text, wire):
    # Accept one exact record; no Markdown repair or argument correction.
    if wire == 'A':
        value = json.loads(text)
        if type(value) is not list or len(value) != 3: raise ValueError('Record shape')
        status, entity, number = value
        if type(status) is not str or type(entity) is not str: raise ValueError('Record types')
    elif wire == 'E':
        match = re.fullmatch(r'([012]) ([AB]) (-?(?:0|[1-9][0-9]{0,3}))\n', text)
        if not match: raise ValueError('Incomplete or malformed enum record')
        status, entity, number = STATUSES[int(match[1])], match[2], int(match[3])
    else: raise ValueError('Unknown wire format')
    result = (status, entity, number)
    encode_record(result, wire)  # bool/float/out-of-range rejected, not coerced
    return result


def complete_record(raw, wire):
    try: return parse_record(raw.decode('utf-8'), wire)
    except (ValueError, UnicodeDecodeError): return None


def state_record(state, context):
    # Same semantic values, including status and unit, in both state arms.
    if context == 'J':
        return json.dumps({entity: {'value': row[0], 'status': row[1], 'unit': 'count'}
                          for entity, row in sorted(state.items())}, separators=(',', ':'))
    if context == 'C':
        return ' '.join(f'{entity}={value}/{STATUSES.index(status)}'
                        for entity, (value, status) in sorted(state.items()))
    raise ValueError('No standalone state in full history')


def instruction(wire, context):
    base = 'Track counts for A and B. Apply only the current request. Reply with the affected entity and resulting value/status. On missing/error preserve its value.'
    if wire == 'A': base += ' Output only ["status","entity",integer]; status is ok,missing,error.'
    else: base += ' Output only: statusID entity integer then newline. IDs:0=ok,1=missing,2=error. Example:0 A 12\n'
    if context == 'C': base += ' State: A=value/statusID B=value/statusID; units=count;0=ok,1=missing,2=error.'
    return base


def request_text(step):
    entity, op, number = step['entity'], step['op'], step['number']
    if op == 'set': return f'Set {entity} to {number} counts.'
    if op == 'add': return f'Add {number} counts to {entity}.'
    if op == 'copy': return f'Copy the count of {"B" if entity == "A" else "A"} to {entity}.'
    if op == 'conditional': return f'If {entity} exceeds 50 counts subtract {number}; otherwise add {number}.'
    return f'The latest read of {entity} returned {op}. Report {op} and preserve its count.'


def transition(state, step):
    """Gold task semantics, NEVER used to update the measured rolling state."""
    entity, op, n = step['entity'], step['op'], step['number']
    value = state[entity][0]
    status = op if op in ('missing', 'error') else 'ok'
    if op == 'set': value = n
    elif op == 'add': value += n
    elif op == 'copy': value = state['B' if entity == 'A' else 'A'][0]
    elif op == 'conditional': value += -n if value > 50 else n
    return status, entity, value


def reduce_observed(state, record):
    """Simulator commits the model proposal verbatim, even when it is wrong."""
    result = {k: list(v) for k, v in state.items()}
    if record is not None:
        status, entity, value = record
        result[entity] = [value, status]
    return result


def chains(split, count, steps=16):
    rng = random.Random(SEED + (1 if split == 'development' else 2))
    result = []
    for index in range(count):
        initial = {'A': [rng.randint(10, 40), 'ok'], 'B': [rng.randint(55, 85), 'ok']}
        sequence = []
        for pos in range(steps):
            # Balanced deterministic families with delayed references and corrections.
            op = ('add', 'set', 'copy', 'conditional', 'missing', 'error')[(pos+index)%6]
            sequence.append(dict(entity='AB'[rng.randrange(2)], op=op, number=rng.randint(1, 9)))
        result.append(dict(id=f'{split}-{index:02d}', initial=initial, steps=sequence))
    return result


def chain_prompt(chain, step_index, state, context, wire, history):
    initial = json.dumps(chain['initial'], separators=(',', ':'))
    user = request_text(chain['steps'][step_index])
    if context == 'H':
        if step_index == 0: user = 'Initial '+initial+'\n'+user
    else: user = 'State '+state_record(state, context)+'\n'+user
    return chat(instruction(wire, context), user, history if context == 'H' else ()), user


def prepare_manifest():
    rng = random.Random(SEED)
    fixed = [dict(id=f'fixed-{mode}-{n}-{out}-{variant}-{repeat}', suite='fixed', mode=mode,
                  input_tokens=n, output_tokens=out, variant=variant, repeat=repeat)
             for mode in ('cold', 'resident') for n in (32, 64, 128, 192)
             for out in (16, 32, 64) for variant in range(3) for repeat in range(5)]
    rng.shuffle(fixed)
    historic = [dict(id=f'historic-{i:02d}', suite='historic', mode='cold', output_tokens=64,
                     query="Read the Linux boot ID from '/proc/sys/kernel/random/boot_id'.",
                     expected_path='/proc/sys/kernel/random/boot_id') for i in range(30)]
    paths = ['/proc/sys/kernel/random/boot_id', '/proc/uptime', '/proc/version', '/etc/shadow', '/tmp/unknown']
    templates = ["Read '{p}'.", "Return the contents of '{p}'.", "Please read Linux file '{p}'.",
        "Fetch the text stored at '{p}'.", "Show the contents of '{p}'.",
        "Read path '{p}' exactly.", "Open '{p}' and return its text.",
        "I need the contents of '{p}'.", "Get the Linux file '{p}'.",
        "Please retrieve '{p}'.", "Can you read '{p}'?", "Use read_linux_file on '{p}'.",
        "Read this file: '{p}'.", "File requested: '{p}'. Read it.",
        "Return text from path '{p}'.", "Please show me '{p}'.",
        "Fetch this exact path: '{p}'.", "Read only '{p}'.",
        "Give me the contents of Linux path '{p}'.", "Read '{p}' without changing the path."]
    application = [dict(id=f'application-{i:03d}', suite='application', mode='resident', output_tokens=64,
                        query=templates[i//5].format(p=paths[i%5]),
                        expected_path=paths[i%5] if i%5 < 3 else None) for i in range(100)]
    arms = [(c, w) for c in ('H', 'J', 'C') for w in ('A', 'E')]
    jobs = []
    for split, count, length in [('development', 12, 4), ('heldout', 24, 16)]:
        for chain in chains(split, count, length):
            order = arms.copy(); rng.shuffle(order)
            for context, wire in order:
                jobs.append(dict(id=f'{chain["id"]}-{context}-{wire}', suite='chain',
                                 split=split, context=context, wire=wire, chain=chain))
    # Qualification/development precede measurement. No automatic prompt tuning.
    return dict(version=VERSION, seed=SEED, context_limit=256, output_reserve=OUTPUT_RESERVE,
                warmups=0, policy='No warmups; all attempts retained. No tuning after freeze.',
                fixed=fixed, historical=historic, application=application, chains=jobs)
