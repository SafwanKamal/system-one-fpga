"""Typed complete-call matching without lossy integer-to-float conversion."""
from collections import Counter
import json
from .general_tools import normalize_tool, validate_calls


def calls_key(calls, tools):
    validate_calls(calls, tools)
    specs = {t['name']:normalize_tool(t)['parameters'] for t in tools}
    def normalize(value, spec):
        if spec.get('type')=='number' and type(value) is float and value.is_integer():
            return int(value)
        if type(value) is list:
            return [normalize(v,spec.get('items',{})) for v in value]
        if type(value) is dict:
            return {k:normalize(v,spec.get('properties',{}).get(k,{})) for k,v in value.items()}
        return value
    return Counter(json.dumps(dict(name=c['name'],arguments=normalize(c['arguments'],specs[c['name']])),
        sort_keys=True,separators=(',',':'),allow_nan=False) for c in calls)


def exact_calls(calls, gold, tools):
    return calls_key(calls,tools)==calls_key(gold,tools)
