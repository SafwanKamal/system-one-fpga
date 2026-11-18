"""Finite field representation shared by learned encoder heads and tool caller."""
from .command_task import API_ARGS, ASSETS, REASONS, validate

NONE = "none"
FIELDS = {
    "outcome": ("Accepted", "Clarify", "Reject"),
    "reason": (NONE,) + tuple(r for k in ("Clarify", "Reject") for r in REASONS[k]),
    "count": ("0", "1", "2"),
}
ARGUMENTS = (NONE,) + tuple(dict.fromkeys(str(v) for spec in API_ARGS.values() for choices in spec.values() for v in choices))
for i in range(2):
    FIELDS.update({f"api{i}": (NONE,) + tuple(API_ARGS), f"asset{i}": (NONE,) + ASSETS,
                   f"arg{i}": ARGUMENTS})
FIELDS.update(condition_asset=(NONE,) + ASSETS, condition_op=(NONE, "gt", "lt"),
              condition_value=(NONE, "50", "70", "90"))


def allowed_values(partial, key):
    """Canonical grammar, in sorted field order, independent of gold labels."""
    if key == 'api0':
        return FIELDS[key]
    active = partial['api0'] != NONE
    if key == 'api1':
        return FIELDS[key] if active else (NONE,)
    if key in ('arg0', 'arg1'):
        api = partial['api' + key[-1]]
        spec = API_ARGS.get(api, {})
        return tuple(str(v) for v in next(iter(spec.values()))) if spec else (NONE,)
    if key in ('asset0', 'asset1'):
        return ASSETS if partial['api' + key[-1]] != NONE else (NONE,)
    if key == 'condition_asset':
        return FIELDS[key] if active else (NONE,)
    if key in ('condition_op', 'condition_value'):
        return FIELDS[key][1:] if partial['condition_asset'] != NONE else (NONE,)
    if key == 'count':
        return ('0' if not active else '2' if partial['api1'] != NONE else '1',)
    if key == 'outcome':
        return ('Accepted',) if active else ('Clarify', 'Reject')
    if key == 'reason':
        return (NONE,) if active else REASONS[partial['outcome']]
    raise ValueError('unknown field')


def constrained_fields(scores):
    """Greedy categorical encoder decoding under the same grammar as generator."""
    result = {}
    for key in sorted(FIELDS):
        choices = allowed_values(result, key)
        result[key] = max(choices, key=lambda v: scores[key][FIELDS[key].index(v)])
    return result


def encode(plan):
    validate(plan)
    fields = {k: NONE for k in FIELDS}
    fields.update(outcome=plan["outcome"], count="0")
    if plan["outcome"] != "Accepted":
        if plan["outcome"] not in ("Clarify", "Reject"):
            raise ValueError("runtime outcomes are supplied by runtime, not model")
        fields["reason"] = plan["reason"]
        return fields
    fields["count"] = str(len(plan["actions"]))
    for i, a in enumerate(plan["actions"]):
        fields.update({f"api{i}": a["api"], f"asset{i}": a["asset"],
                       f"arg{i}": str(next(iter(a["args"].values()), NONE))})
    c = plan["condition"]
    if c:
        fields.update(condition_asset=c["asset"], condition_op=c["op"], condition_value=str(c["value"]))
    return fields


def decode(fields):
    if set(fields) != set(FIELDS):
        raise ValueError("incorrect field set")
    if any(type(fields[k]) is not str or fields[k] not in choices for k, choices in FIELDS.items()):
        raise ValueError("invalid field value")
    if fields["outcome"] != "Accepted":
        plan = dict(outcome=fields["outcome"], reason=fields["reason"])
    else:
        actions = []
        for i in range(int(fields["count"])):
            api = fields[f"api{i}"]
            if api not in API_ARGS:
                raise ValueError("missing API")
            arg = fields[f"arg{i}"]
            args = {}
            for key in API_ARGS[api]:
                args[key] = int(arg) if key == "rpm" else arg
            actions.append(dict(api=api, asset=fields[f"asset{i}"], args=args))
        c = None
        if fields["condition_asset"] != NONE:
            c = dict(asset=fields["condition_asset"], sensor="temperature", unit="C",
                     op=fields["condition_op"], value=int(fields["condition_value"]))
        plan = dict(outcome="Accepted", actions=actions, condition=c)
    validate(plan)
    # Do not silently discard inconsistent or stale unused arguments/fields.
    if encode(plan) != fields:
        raise ValueError("noncanonical unused fields")
    return plan


def tool():
    return {"type": "function", "function": {
        "name": "publish_command",
        "description": "Propose a maintenance plan, never execute it. Assets M1-M8 only. "
            "Ordered actions api0 then api1; count 0 for Clarify or Reject. "
            "Use none for every unused field. condition_asset,condition_op,condition_value "
            "apply temperature in C to the entire plan. "
            "API arguments: set_mode=auto/manual/maintenance; set_speed=500/1000/1500 rpm; "
            "create_work_order,schedule_inspection=low/normal/high priority; "
            "enable_monitor=temperature/vibration; all others=none. "
            "Negated actions are excluded; latest explicit correction wins. "
            "Missing asset, ambiguity or contradiction needs Clarify; unknown assets, "
            "unsupported operations or values need Reject.",
        "parameters": {"type": "object", "properties": {
            k: {"type": "string", "enum": list(v), "description": k} for k,v in FIELDS.items()
        }, "required": list(FIELDS)},
    }}
