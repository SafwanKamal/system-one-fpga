"""Strict bounded AST and reversible JSON-array wire format."""
import copy
import json
import re

VERSION = 'maintenance-pilot-v1'
TOOLS = ('read_metric', 'read_history', 'list_alarms', 'read_status',
         'read_metadata', 'draft_report', 'request_inspection', 'lookup_procedure')
METRICS = ('temperature', 'vibration', 'current')
UNITS = {'temperature': 'C', 'vibration': 'mm_per_s', 'current': 'A'}
SCALES = {'temperature': 1, 'vibration': 1000, 'current': 1000}
OPS = ('gt', 'ge', 'lt', 'le')
REASONS = {
    'clarify': {'ambiguous_asset': 'asset', 'missing_reference': 'asset',
                'missing_asset': 'asset', 'contradiction': 'request'},
    'reject': {'unsupported_operation': None, 'unknown_asset': None,
               'unsupported_unit': None, 'unsupported_value': None, 'plan_capacity': None},
}


def keys(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise ValueError('Expected exactly ' + str(tuple(expected)))


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('Integer outside declared domain')


def validate(ast, catalog=None):
    if type(ast) is not dict or type(ast.get('outcome')) is not str:
        raise ValueError('Missing outcome')
    kind = ast['outcome']
    if kind in REASONS:
        expected = ('outcome', 'reason', 'field') if kind == 'clarify' else ('outcome', 'reason')
        keys(ast, expected)
        if ast['reason'] not in REASONS[kind]:
            raise ValueError('Unknown reason')
        if kind == 'clarify' and ast['field'] != REASONS[kind][ast['reason']]:
            raise ValueError('Incorrect clarification field')
        return copy.deepcopy(ast)
    if kind != 'plan':
        raise ValueError('Unknown outcome')
    keys(ast, ('outcome', 'steps', 'predicate'))
    steps, pred = ast['steps'], ast['predicate']
    if type(steps) is not list or not 1 <= len(steps) <= 3:
        raise ValueError('One to three steps required')
    if pred is not None:
        keys(pred, ('source', 'op', 'rhs'))
        integer(pred['source'], 0, len(steps)-2)
        if pred['op'] not in OPS:
            raise ValueError('Unknown comparison')
        if pred['rhs'] != 'limit':
            integer(pred['rhs'], -1000000, 1000000)
    assets, guarded = set(), False
    for i, step in enumerate(steps):
        if type(step) is not dict or step.get('tool') not in TOOLS:
            raise ValueError('Unknown tool')
        tool = step['tool']
        args = {'read_metric': ('metric',), 'read_history': ('metric', 'count'),
                'list_alarms': (), 'read_status': (), 'read_metadata': ('field',),
                'draft_report': ('priority', 'evidence'),
                'request_inspection': ('priority', 'evidence'),
                'lookup_procedure': ('topic',)}[tool]
        keys(step, ('tool', 'asset', 'guard') + args)
        asset = step['asset']
        if type(asset) is not str or not re.fullmatch(r'[PMF][1-9][0-9]?', asset):
            raise ValueError('Malformed asset')
        if catalog is not None and asset not in catalog:
            raise ValueError('Asset not in public catalog')
        assets.add(asset)
        if type(step['guard']) is not bool:
            raise ValueError('Guard must be boolean')
        if step['guard']:
            if pred is None or pred['source'] >= i:
                raise ValueError('Guard depends on earlier predicate source')
            guarded = True
        if 'metric' in args and step['metric'] not in METRICS:
            raise ValueError('Unknown metric')
        if 'count' in args:
            integer(step['count'], 1, 5)
        if 'field' in args and step['field'] not in ('manufacturer', 'inspection_date'):
            raise ValueError('Unknown metadata field')
        if 'topic' in args and step['topic'] not in ('inspection', 'lubrication'):
            raise ValueError('Unknown procedure')
        if 'priority' in args:
            if step['priority'] not in ('normal', 'high'):
                raise ValueError('Unknown priority')
            refs = step['evidence']
            if type(refs) is not list or not refs or len(refs) != len(set(refs)):
                raise ValueError('Nonempty unique evidence required')
            for ref in refs:
                integer(ref, 0, i-1)
                if steps[ref]['tool'] in ('draft_report', 'request_inspection'):
                    raise ValueError('Evidence must be a read result')
                if steps[ref]['guard'] and not step['guard']:
                    raise ValueError('Unconditional action cites conditional evidence')
    if len(assets) != 1:
        raise ValueError('One asset per plan')
    if pred is not None:
        source = steps[pred['source']]
        if source['tool'] != 'read_metric' or source['guard'] or not guarded:
            raise ValueError('Predicate requires unguarded metric source and guarded consumer')
    return copy.deepcopy(ast)


def canonical(ast):
    return json.dumps(validate(ast), sort_keys=True, separators=(',', ':'), allow_nan=False)


def encode(ast):
    """Tool names stay readable; no hidden ID mapping or semantic defaults."""
    ast = validate(ast)
    if ast['outcome'] == 'clarify':
        value = ['clarify', ast['reason'], ast['field']]
    elif ast['outcome'] == 'reject':
        value = ['reject', ast['reason']]
    else:
        nodes = []
        for step in ast['steps']:
            args = {k: v for k, v in step.items() if k not in ('tool', 'asset', 'guard')}
            nodes.append([step['tool'], step['asset'], args, step['guard']])
        p = ast['predicate']
        value = ['plan', nodes, None if p is None else [p['source'], p['op'], p['rhs']]]
    return json.dumps(value, separators=(',', ':'), allow_nan=False)


def _unique(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError('Duplicate JSON key')
        result[k] = v
    return result


def parse(raw, catalog=None):
    if type(raw) is not str or len(raw.encode('utf-8')) > 8192:
        raise ValueError('Output must be bounded text')
    value = json.loads(raw, object_pairs_hook=_unique,
                       parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    if type(value) is not list or not value or type(value[0]) is not str:
        raise ValueError('Expected one wire array')
    if value[0] == 'clarify' and len(value) == 3:
        ast = dict(outcome=value[0], reason=value[1], field=value[2])
    elif value[0] == 'reject' and len(value) == 2:
        ast = dict(outcome=value[0], reason=value[1])
    elif value[0] == 'plan' and len(value) == 3:
        nodes, pred = value[1:]
        if type(nodes) is not list:
            raise ValueError('Steps must be a list')
        steps = []
        for node in nodes:
            if type(node) is not list or len(node) != 4 or type(node[2]) is not dict:
                raise ValueError('Node must be [tool,asset,args,guard]')
            if set(node[2]) & {'tool', 'asset', 'guard'}:
                raise ValueError('Reserved argument')
            steps.append(dict(tool=node[0], asset=node[1], guard=node[3], **node[2]))
        if pred is not None and (type(pred) is not list or len(pred) != 3):
            raise ValueError('Malformed predicate')
        ast = dict(outcome='plan', steps=steps,
                   predicate=None if pred is None else dict(zip(('source', 'op', 'rhs'), pred)))
    else:
        raise ValueError('Unknown wire variant')
    return validate(ast, catalog)


def node(tool, asset, guard=False, **args):
    return dict(tool=tool, asset=asset, guard=guard, **args)


def plan(*steps, predicate=None):
    return validate(dict(outcome='plan', steps=list(steps), predicate=predicate))


def terminal(kind, reason):
    value = dict(outcome=kind, reason=reason)
    if kind == 'clarify':
        value['field'] = REASONS[kind][reason]
    return validate(value)
