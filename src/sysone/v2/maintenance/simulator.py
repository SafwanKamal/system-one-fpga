"""Deterministic finite plant. Never reads the user request or gold labels."""
import copy
from .schema import validate, METRICS, UNITS, SCALES


def world(catalog, value=75, status='ok', epoch=1):
    if status not in ('ok', 'missing', 'error'):
        raise ValueError('Unknown reading status')
    assets = {}
    for asset in catalog:
        assets[asset] = dict(
            metrics={m: dict(value=value * SCALES[m], limit=70 * SCALES[m],
                            scale=SCALES[m], unit=UNITS[m], status=status,
                            sample_id=f'{asset}/{m}/{epoch}') for m in METRICS},
            history={m: [dict(value=(value-i)*SCALES[m], scale=SCALES[m], unit=UNITS[m],
                             sample_id=f'{asset}/{m}/{epoch-i}') for i in range(5)] for m in METRICS},
            alarms=['A1'], operating_state='running',
            metadata={'manufacturer': 'ExampleCo', 'inspection_date': '2026-10-01'})
    return dict(epoch=epoch, assets=assets, reports=[], inspections=[])


def execute(ast, initial):
    """Deep-copy world; failures stop path, no semantic repair or gold access."""
    state = copy.deepcopy(initial)
    ast = validate(ast, state['assets'])
    if ast['outcome'] != 'plan':
        return dict(outcome=ast['outcome'], trace=[], state=state)
    trace, pred_value = [], None
    for i, step in enumerate(ast['steps']):
        if step['guard'] and pred_value is not True:
            trace.append(dict(step=i, tool=step['tool'], status='skipped'))
            continue
        tool, asset = step['tool'], step['asset']
        item = state['assets'][asset]
        result = dict(epoch=state['epoch'], asset=asset)
        if tool == 'read_metric':
            result.update(copy.deepcopy(item['metrics'][step['metric']]))
        elif tool == 'read_history':
            reading = item['metrics'][step['metric']]
            result.update(status=reading['status'], samples=copy.deepcopy(item['history'][step['metric']][:step['count']]))
        elif tool == 'list_alarms':
            result.update(status='ok', alarms=copy.deepcopy(item['alarms']))
        elif tool == 'read_status':
            result.update(status='ok', operating_state=item['operating_state'])
        elif tool == 'read_metadata':
            result.update(status='ok', field=step['field'], value=item['metadata'][step['field']])
        elif tool == 'lookup_procedure':
            result.update(status='ok', procedure_id=f'{asset}-{step["topic"]}-v1')
        else:
            evidence = []
            for ref in step['evidence']:
                record = trace[ref]
                if record['status'] != 'ok' or record['result']['epoch'] != state['epoch']:
                    raise ValueError('Unusable evidence')
                evidence.append(copy.deepcopy(record['result']))
            result.update(status='ok', priority=step['priority'], evidence=evidence)
            key = 'reports' if tool == 'draft_report' else 'inspections'
            state[key].append(copy.deepcopy(result))
        trace.append(dict(step=i, tool=tool, status=result['status'], result=result))
        if result['status'] != 'ok':
            return dict(outcome='tool_error', trace=trace, state=state)
        pred = ast['predicate']
        if pred is not None and i == pred['source']:
            lhs = result['value']
            rhs = result['limit'] if pred['rhs'] == 'limit' else pred['rhs'] * result['scale']
            pred_value = {'gt': lhs > rhs, 'ge': lhs >= rhs, 'lt': lhs < rhs, 'le': lhs <= rhs}[pred['op']]
    return dict(outcome='complete', trace=trace, state=state)


def counterfactuals(catalog, ast):
    pred = ast.get('predicate')
    threshold = 70 if pred is None or pred['rhs'] == 'limit' else pred['rhs']
    return {name: world(catalog, value=value, status=status)
            for name, value, status in (
                ('below', threshold-1, 'ok'), ('equal', threshold, 'ok'),
                ('above', threshold+1, 'ok'), ('read_error', threshold+1, 'error'))}
