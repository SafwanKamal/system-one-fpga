"""Public-input-only rules and factorized typed targets for software baselines."""
import json
import re
from .schema import plan, node, terminal, validate

ASSET_RE = re.compile(r'\b[PMF][1-9][0-9]?\b', re.I)


def rules(public):
    text = public['request'].lower()
    previous = public['context'].get('previous_request', '').lower()
    explicit = [m.upper() for m in ASSET_RE.findall(text)]
    if any(a not in public['catalog'] for a in explicit):
        return terminal('reject', 'unknown_asset')
    if any(w in text for w in ('increase', 'shutdown', 'start motor', 'set speed')):
        return terminal('reject', 'unsupported_operation')
    if 'fahrenheit' in text:
        return terminal('reject', 'unsupported_unit')
    if re.search(r'\b[6-9]\s+(?:recent|last)', text):
        return terminal('reject', 'unsupported_value')
    if 'temperature and vibration' in text and 'history' in text and 'report' in text:
        return terminal('reject', 'plan_capacity')
    if 'and do not read' in text:
        return terminal('clarify', 'contradiction')
    references = [m.upper() for m in ASSET_RE.findall(previous)]
    if not explicit and not references:
        reason = 'missing_reference' if re.search(r'\b(?:its|it|same asset)\b', text) else ('ambiguous_asset' if 'pump' in text else 'missing_asset')
        return terminal('clarify', reason)
    asset = (explicit or references)[0]
    correction = bool(previous) and any(w in text for w in ('same check', 'retain the check', 'instead', 'same asset'))
    working = previous if correction and explicit else text
    if correction and explicit:
        # Preserve previous instruction; substitute only the newly named asset.
        working = ASSET_RE.sub(asset, previous)
    metric_matches = re.findall(r'\b(?:temperature|vibration|current)\b', working)
    metric = metric_matches[0] if metric_matches else 'temperature'
    priority = 'high' if 'high' in working else 'normal'
    nmatch = re.search(r'\b([1-5])\s+(?:recent|temperature|vibration|current)', working)
    count = int(nmatch[1]) if nmatch else 3
    if 'procedure' in working:
        return plan(node('lookup_procedure', asset, topic='lubrication' if 'lubrication' in working else 'inspection'))
    if 'manufacturer' in working or 'inspection date' in working:
        return plan(node('read_metadata', asset, field='manufacturer' if 'manufacturer' in working else 'inspection_date'))
    conditional = 'if ' in working
    pred = None
    if conditional:
        if any(w in working for w in ('at least', 'greater than or equal', 'reaches or exceeds')):
            op = 'ge'
        elif any(w in working for w in ('at most', 'less than or equal', 'does not exceed')):
            op = 'le'
        elif any(w in working for w in ('below', 'less than', 'strictly under')):
            op = 'lt'
        else:
            op = 'gt'
        threshold = re.search(r'\b(-?[0-9]+) C\b', working, re.I)
        rhs = 'limit' if 'configured limit' in working else int(threshold[1])
        pred = dict(source=0, op=op, rhs=rhs)
    action = 'draft_report' if 'report' in working else ('request_inspection' if 'inspection' in working else None)
    history = any(w in working for w in ('recent', 'last ', 'history'))
    if 'alarm' in working:
        first = node('list_alarms', asset)
    elif 'operating status' in working:
        first = node('read_status', asset)
    elif history and action is None:
        first = node('read_history', asset, metric=metric, count=count)
    else:
        first = node('read_metric', asset, metric=metric)
    steps = [first]
    if history and action is not None:
        steps.append(node('read_history', asset, guard=conditional, metric=metric, count=count))
    if action is not None:
        steps.append(node(action, asset, guard=conditional, priority=priority, evidence=list(range(len(steps)))))
    return plan(*steps, predicate=pred)


def features(public):
    """Catalog-index names permit pointer-style prediction of new identifiers."""
    text = json.dumps(public, sort_keys=True)
    catalog = public['catalog']
    return ASSET_RE.sub(lambda m: 'entity'+str(catalog.index(m[0])) if m[0] in catalog else 'unknown_entity', text)


def flatten(ast, catalog):
    values = dict(outcome=ast['outcome'], reason=ast.get('reason', '_'), field=ast.get('field', '_'),
                  asset='_', length='0', pred_source='_', pred_op='_', pred_rhs='_')
    for i in range(3):
        for name in ('tool', 'guard', 'metric', 'count', 'field', 'topic', 'priority', 'evidence'):
            values[f'{i}.{name}'] = '_'
    if ast['outcome'] == 'plan':
        values['asset'] = str(catalog.index(ast['steps'][0]['asset']))
        values['length'] = str(len(ast['steps']))
        for i, step in enumerate(ast['steps']):
            for name in ('tool', 'guard', 'metric', 'count', 'field', 'topic', 'priority', 'evidence'):
                if name in step:
                    values[f'{i}.{name}'] = json.dumps(step[name], separators=(',', ':'))
        if ast['predicate'] is not None:
            for name in ('source', 'op', 'rhs'):
                values['pred_'+name] = json.dumps(ast['predicate'][name])
    return values


def unflatten(values, catalog):
    kind = values['outcome']
    if kind != 'plan':
        ast = dict(outcome=kind, reason=values['reason'])
        if kind == 'clarify':
            ast['field'] = values['field']
        return validate(ast, catalog)
    asset = catalog[int(values['asset'])]
    steps = []
    for i in range(int(values['length'])):
        tool = json.loads(values[f'{i}.tool'])
        args = {'read_metric': ('metric',), 'read_history': ('metric', 'count'),
                'list_alarms': (), 'read_status': (), 'read_metadata': ('field',),
                'draft_report': ('priority', 'evidence'), 'request_inspection': ('priority', 'evidence'),
                'lookup_procedure': ('topic',)}[tool]
        step = node(tool, asset, guard=json.loads(values[f'{i}.guard']),
                    **{n: json.loads(values[f'{i}.{n}']) for n in args})
        steps.append(step)
    pred = None if values['pred_source'] == '_' else {
        n: json.loads(values['pred_'+n]) for n in ('source', 'op', 'rhs')}
    return validate(dict(outcome='plan', steps=steps, predicate=pred), catalog)
