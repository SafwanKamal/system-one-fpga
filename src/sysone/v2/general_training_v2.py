"""Successor training helpers. Previous sealed pilot sources remain unchanged."""
from collections import Counter
import json
import random
import re
from .general_tools import normalize_tool, validate_calls
from .general_tool_encoder import KINDS, job_text


def partition_records(data, train_count, selection_count=16, audit_count=64):
    def read(name):
        with (data / (name + '.jsonl')).open(encoding='utf-8') as stream:
            rows = [json.loads(line) for line in stream]
        random.Random(2026101702).shuffle(rows)
        return rows
    train = read('train')[:train_count]
    dev = read('dev')
    selection = dev[:selection_count]
    audit = dev[selection_count:selection_count + audit_count]
    if {r['id'] for r in selection} & {r['id'] for r in audit}:
        raise ValueError('selection/audit overlap')
    def augment(rows, every, phrases):
        result = list(rows)
        for index, row in enumerate(rows[::every]):
            result.append({**row, 'id': row['id'] + ':deny',
                'query': phrases[index % len(phrases)], 'answers': [],
                'provenance': 'synthetic_explicit_no_action_instruction'})
        return result
    return (augment(train, 8, ['Do not call any function. Return no tool calls.', 'Make no function calls for this request.']),
            augment(selection, 4, ['Use none of these functions; make no calls.']),
            augment(audit, 8, ['Do not use any tools or call any functions.']))


def encoder_text(tool, argument=None, slot=0):
    question = job_text(tool, argument, slot, 4)
    if argument is None:
        return question, len(question)
    spec = normalize_tool(tool)['parameters']['properties'][argument]
    if 'default' in spec:
        question += ' Default: ' + json.dumps(spec['default'])
    # Only metadata after the argument header is eligible for copying. Control
    # text such as "Call 1" must never become a numeric argument source.
    marker = f' Argument {argument} ('
    header = question.rfind(marker)
    start = question.index('): ', header) + 3
    return question, start


def source_tokens(encoding, schema_start):
    return [i for i, seq in enumerate(encoding.sequence_ids())
            if seq is not None and encoding['offset_mapping'][i][1] > encoding['offset_mapping'][i][0]
            and (seq == 1 or encoding['offset_mapping'][i][0] >= schema_start)]


def value_label(value, query, question, schema_start, encoding):
    for candidate, kind in ((True, 'true'), (False, 'false'), (None, 'null'),
                            ('', 'empty_string'), ([], 'empty_array'), ({}, 'empty_object')):
        if type(value) is type(candidate) and value == candidate:
            return KINDS.index(kind), 0, 0
    forms = [value] if isinstance(value, str) else [json.dumps(value), json.dumps(value, separators=(',', ':'))]
    if type(value) is float and value.is_integer():
        forms.append(str(int(value)))
    offsets = encoding['offset_mapping']
    seqs = encoding.sequence_ids()
    for text, seq, lower in ((query, 1, 0), (question, 0, schema_start)):
        for form in forms:
            for match in re.finditer(re.escape(form), text, re.IGNORECASE):
                if match.start() < lower:
                    continue
                a = [i for i, (x, y) in enumerate(offsets) if seqs[i] == seq and x == match.start() and y > x]
                b = [i for i, (x, y) in enumerate(offsets) if seqs[i] == seq and y == match.end() and y > x]
                if a and b:
                    return KINDS.index('span'), a[0], b[-1]
    return KINDS.index('unrepresentable'), 0, 0


def prepare_jobs(rows, tok, cap):
    jobs, failures, kinds = [], [], Counter()
    missing = object()
    for row in rows:
        try:
            validate_calls(row['answers'], row['tools'])
            if len(row['tools']) > 8:
                raise ValueError('more than eight tools')
        except (ValueError, TypeError, KeyError) as exc:
            failures.append(dict(id=row['id'], reason='training_record_profile_or_gold', detail=str(exc)))
            continue
        for tool in row['tools']:
            props = normalize_tool(tool)['parameters']['properties']
            answers = [a for a in row['answers'] if a['name'] == tool['name']]
            descriptions = [(None, 0, missing)]
            descriptions += [(key, slot, answer['arguments'].get(key, missing))
                             for slot, answer in enumerate(answers) for key in props]
            for key, slot, value in descriptions:
                question, lower = encoder_text(tool, key, slot)
                enc = tok(question, row['query'], truncation=False, return_offsets_mapping=True)
                identity = f"{row['id']}:{tool['name']}:{key}:{slot}"
                if len(enc['input_ids']) > cap:
                    failures.append(dict(id=identity, reason='input_profile', tokens=len(enc['input_ids'])))
                    continue
                kind, a, b = (0, 0, 0) if value is missing else value_label(value, row['query'], question, lower, enc)
                if key is not None:
                    kinds[KINDS[kind]] += 1
                jobs.append(dict(id=identity, record_id=row['id'], task='count' if key is None else 'argument',
                    tokens={k: v for k, v in enc.items() if k != 'offset_mapping'},
                    count=min(len(answers), 5), kind=kind, start=a, end=b))
    return jobs, failures, dict(kinds)


def calls_key(calls, tools):
    validate_calls(calls, tools)
    specs = {t['name']: normalize_tool(t)['parameters'] for t in tools}
    def normalize(value, spec):
        if spec.get('type') == 'number' and type(value) in (int, float):
            return float(value)
        if type(value) is list:
            return [normalize(v, spec.get('items', {})) for v in value]
        if type(value) is dict:
            return {k: normalize(v, spec.get('properties', {}).get(k, {})) for k, v in value.items()}
        return value
    return Counter(json.dumps(dict(name=c['name'], arguments=normalize(c['arguments'], specs[c['name']])),
                              sort_keys=True, separators=(',', ':'), allow_nan=False) for c in calls)


def exact_calls(calls, gold, tools):
    return calls_key(calls, tools) == calls_key(gold, tools)
