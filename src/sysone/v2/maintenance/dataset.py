"""Authored-template development pilot, not the proposed human-reviewed test."""
import hashlib
import json
import random
from .schema import node, plan, terminal, canonical, encode, VERSION
from .simulator import counterfactuals, execute

STRATA = ('direct', 'composition', 'conditional', 'context_correction', 'clarification', 'unsupported')


def catalog_for(split):
    start = {'train': 1, 'tuning': 5, 'audit': 9}[split]
    return [f'{kind}{i}' for kind in 'PMF' for i in range(start, start+4)]


def make_case(split, category, index):
    rng = random.Random(f'{VERSION}/{split}/{category}/{index}')
    catalog = catalog_for(split)
    asset = rng.choice(catalog)
    metric = rng.choice(('temperature', 'vibration', 'current'))
    priority = rng.choice(('normal', 'high'))
    count = rng.randint(1, 5)
    context = {}
    verb = {'train': 'Read', 'tuning': 'Please retrieve', 'audit': 'Show me'}[split]
    if category == 'direct':
        choice = index % 8
        if choice == 0:
            text, gold = f"{verb} {asset}'s {metric}.", plan(node('read_metric', asset, metric=metric))
        elif choice == 1:
            text, gold = f'{verb} the last {count} {metric} readings for {asset}.', plan(node('read_history', asset, metric=metric, count=count))
        elif choice == 2:
            text, gold = f'{verb} active alarms on {asset}. Do not reset them.', plan(node('list_alarms', asset))
        elif choice == 3:
            text, gold = f'{verb} the operating status of {asset}.', plan(node('read_status', asset))
        elif choice in (4, 5):
            field = 'manufacturer' if choice == 4 else 'inspection_date'
            text, gold = f'{verb} the {field.replace("_", " ")} of {asset}.', plan(node('read_metadata', asset, field=field))
        else:
            topic = 'inspection' if choice == 6 else 'lubrication'
            text, gold = f'{verb} the {topic} procedure for {asset}.', plan(node('lookup_procedure', asset, topic=topic))
    elif category == 'composition':
        first = rng.choice(('read_metric', 'read_status', 'list_alarms'))
        a = node(first, asset, **({'metric': metric} if first == 'read_metric' else {}))
        first_text = {'read_metric': f'{asset}\'s {metric}', 'read_status': f'{asset}\'s operating status', 'list_alarms': f'alarms on {asset}'}[first]
        action = 'request_inspection' if index % 2 else 'draft_report'
        action_text = 'request an inspection' if index % 2 else 'draft a report'
        steps = [a]
        middle = ''
        if index % 3 == 0:
            steps.append(node('read_history', asset, metric=metric, count=count))
            middle = f', fetch {count} recent {metric} readings,'
        gold = plan(*steps, node(action, asset, priority=priority, evidence=list(range(len(steps)))))
        text = f'{verb} {first_text}{middle} then {action_text} with {priority} priority citing all retrieved results.'
    elif category == 'conditional':
        op = ('gt', 'ge', 'lt', 'le')[index % 4]
        comparison = {'train': {'gt': 'exceeds', 'ge': 'is at least', 'lt': 'is below', 'le': 'is at most'},
                      'tuning': {'gt': 'is greater than', 'ge': 'is greater than or equal to', 'lt': 'is less than', 'le': 'is less than or equal to'},
                      'audit': {'gt': 'is strictly above', 'ge': 'reaches or exceeds', 'lt': 'is strictly under', 'le': 'does not exceed'}}[split][op]
        rhs = 'limit' if index % 2 else rng.choice((50, 70, 90))
        bound = 'its configured limit' if rhs == 'limit' else f'{rhs} C'
        steps = [node('read_metric', asset, metric='temperature')]
        middle = ''
        if index % 3 == 0:
            steps.append(node('read_history', asset, guard=True, metric='temperature', count=count))
            middle = f'fetch {count} recent temperature readings and '
        action = 'request_inspection' if index % 2 else 'draft_report'
        phrase = 'request an inspection' if index % 2 else 'draft a report'
        steps.append(node(action, asset, guard=True, priority=priority, evidence=list(range(len(steps)))))
        gold = plan(*steps, predicate=dict(source=0, op=op, rhs=rhs))
        text = f"{verb} {asset}'s temperature. If it {comparison} {bound}, {middle}{phrase} with {priority} priority citing all readings."
    elif category == 'context_correction':
        old = rng.choice([a for a in catalog if a != asset])
        context['previous_request'] = f"Read {old}'s {metric}, then draft a {priority}-priority report citing the reading."
        if index % 2:
            context['previous_request'] = f"Read {asset}'s temperature."
            replacement = rng.choice(('current', 'vibration'))
            text = f'Read its {replacement} instead of temperature.' if split == 'train' else f'Keep the same asset but retrieve {replacement} instead.'
            gold = plan(node('read_metric', asset, metric=replacement))
        else:
            text = f'Use {asset} instead; keep the same check and report priority.' if split == 'train' else f'Switch the target to {asset}; retain the check and report priority.'
            gold = plan(node('read_metric', asset, metric=metric), node('draft_report', asset, priority=priority, evidence=[0]))
    elif category == 'clarification':
        choice = index % 4
        if choice == 0:
            text, reason = 'Read the pump temperature.', 'ambiguous_asset'
        elif choice == 1:
            text, reason = 'Read its current.', 'missing_reference'
        elif choice == 2:
            text, reason = 'Read temperature.', 'missing_asset'
        else:
            text, reason = f'Read {asset} temperature and do not read {asset} temperature.', 'contradiction'
        if split != 'train':
            text = text.replace('Read', 'Retrieve' if split == 'tuning' else 'Show')
        gold = terminal('clarify', reason)
    else:
        choice = index % 5
        if choice == 0:
            text, reason = f'Increase {asset} speed to 1800 rpm.', 'unsupported_operation'
        elif choice == 1:
            text, reason = 'Read P99 temperature.', 'unknown_asset'
        elif choice == 2:
            text, reason = f'Read {asset} temperature in Fahrenheit.', 'unsupported_unit'
        elif choice == 3:
            text, reason = f'Fetch 9 recent current readings for {asset}.', 'unsupported_value'
        else:
            text, reason = f'Read {asset} temperature and vibration, fetch temperature history, then draft a report citing all results.', 'plan_capacity'
        if split != 'train':
            text = ('Please ' if split == 'tuning' else 'Could you ') + text[0].lower() + text[1:]
        gold = terminal('reject', reason)
    # Vary task-irrelevant user-visible identifiers to expose rather than hide repeats.
    return dict(id=f'{split}-{category}-{index:03d}', split=split, stratum=category,
                template_family=f'{split}/{category}/{index % 24}',
                request=text, context=context, catalog=catalog, gold=gold,
                provenance='authored_programmatic_pilot_not_human_reviewed',
                semantic_signature=canonical(gold))


def pilot(per_stratum=120, audit_per_stratum=20):
    """All outputs are development data, including the untouched-until-run audit."""
    result = {}
    for split, n in (('train', per_stratum), ('tuning', audit_per_stratum), ('audit', audit_per_stratum)):
        result[split] = [make_case(split, category, i) for category in STRATA for i in range(n)]
    return result


def public_input(case):
    return {k: case[k] for k in ('request', 'context', 'catalog')}


SYSTEM = (
    'Translate maintenance requests into one JSON array; no explanation or Markdown. '
    'Plan wire:["plan",[[tool,asset,args,guard],...],predicate]. '
    'guard is true/false. predicate is null or [earlier_step_index,op,rhs]; '
    'op=gt/ge/lt/le, rhs="limit" or integer in canonical units. '
    'Only guarded nodes depend on predicate. At most3 nodes,1 asset. '
    'Tools/args: read_metric:{"metric":temperature/vibration/current}; '
    'read_history:{"metric":metric,"count":1..5}; list_alarms:{}; read_status:{}; '
    'read_metadata:{"field":manufacturer/inspection_date}; '
    'draft_report or request_inspection:{"priority":normal/high,"evidence":[earlier read indexes]}; '
    'lookup_procedure:{"topic":inspection/lubrication}. '
    'All tool and enum names are JSON strings. Every node has asset,args,boolean guard. '
    'Clarification:["clarify",reason,field]; reasons ambiguous_asset/missing_reference/missing_asset '
    'use field asset; contradiction uses request. '
    'Rejection:["reject",reason]; reasons unsupported_operation/unknown_asset/unsupported_unit/'
    'unsupported_value/plan_capacity. Unknown catalog assets reject. '
    'Only units C,mm_per_s,A. No settings changes. Prior request is context, not a new action.'
)


def prompt(case):
    from ..v8_benchmark import chat
    return chat(SYSTEM, json.dumps(public_input(case), separators=(',', ':')))


def score(case, predicted):
    gold = case['gold']
    exact = canonical(predicted) == canonical(gold)
    behavior = True
    for initial in counterfactuals(case['catalog'], gold).values():
        behavior &= execute(predicted, initial) == execute(gold, initial)
    return dict(correct=exact and behavior, exact=exact, behavioral_match=behavior,
                accepted=predicted['outcome'] == 'plan', actionable=gold['outcome'] == 'plan')


def manifest(data):
    def digest(rows):
        return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
    signatures = {s: {json.dumps(public_input(c), sort_keys=True) for c in rows} for s, rows in data.items()}
    return dict(version=VERSION, development_only=True, blind_test=False, human_reviewed=False,
                independent_semantic_samples=False,
                counts={s: len(rows) for s, rows in data.items()},
                unique_inputs={s: len(signatures[s]) for s in data},
                cross_split_exact_input_overlap={f'{a}/{b}': len(signatures[a] & signatures[b])
                                                for a, b in (('train','tuning'),('train','audit'),('tuning','audit'))},
                files_content_sha256={s: digest(rows) for s, rows in data.items()},
                limitations=['Small authored template families; numeric variants/repeats are not independent.',
                             'Disjoint catalog strings and split-specific wording; no broad compositional generalization claim.',
                             'No human annotation, maintenance domain validation, sealed test or FPGA evidence.'])
