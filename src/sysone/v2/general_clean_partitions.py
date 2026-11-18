"""Successor development audit excludes previously inspected components."""
import json
import random
from .general_training_v2 import partition_records


def partition_checked_records(data, train_count, audit_offset=144):
    if audit_offset<16:
        raise ValueError('audit overlaps selection')
    train,selection,_=partition_records(data,train_count)
    with (data/'dev.jsonl').open(encoding='utf-8') as stream:
        dev=[json.loads(line) for line in stream]
    random.Random(2026101702).shuffle(dev)
    blocked={r['split_component'] for r in dev[:audit_offset]}
    audit=[r for r in dev[audit_offset:] if r['split_component'] not in blocked][:64]
    if len(audit)!=64:
        raise ValueError('not enough untouched audit components')
    audit += [{**r,'id':r['id']+':deny','answers':[],
        'query':'Return no function calls. Leave every listed tool unused.',
        'provenance':'synthetic_explicit_no_action_instruction'} for r in audit[::8]]
    return train,selection,audit
