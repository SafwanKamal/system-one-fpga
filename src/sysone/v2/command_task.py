"""Provisional bounded command task shared by encoder and generator experiments.

This software schema does not change the deployed typed-result RTL ABI.
"""
from __future__ import annotations

from collections import Counter
import json
import math

ASSETS = tuple(f"M{i}" for i in range(1, 9))
API_ARGS = {
    "get_status": {}, "read_temperature": {}, "read_vibration": {},
    "list_alarms": {}, "start_asset": {}, "stop_asset": {}, "reset_alarm": {},
    "set_mode": {"mode": ("auto", "manual", "maintenance")},
    "set_speed": {"rpm": (500, 1000, 1500)},
    "create_work_order": {"priority": ("low", "normal", "high")},
    "schedule_inspection": {"priority": ("low", "normal", "high")},
    "enable_monitor": {"sensor": ("temperature", "vibration")},
}
REASONS = {
    "Clarify": ("missing_asset", "ambiguous_reference", "contradiction"),
    "Reject": ("unknown_asset", "unsupported_operation", "unsupported_value"),
    "Deadline": ("budget_exhausted",), "Fault": ("runtime_failure",),
}


def _keys(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise ValueError(f"expected exactly {tuple(expected)}")


def validate(value):
    """Reject extra fields, noncanonical numbers, malformed or unbounded plans."""
    if type(value) is not dict or type(value.get("outcome")) is not str:
        raise ValueError("missing outcome")
    outcome = value["outcome"]
    if outcome != "Accepted":
        _keys(value, ("outcome", "reason"))
        if outcome not in REASONS or value["reason"] not in REASONS[outcome]:
            raise ValueError("invalid terminal variant/reason")
        return value
    _keys(value, ("outcome", "actions", "condition"))
    actions = value["actions"]
    if type(actions) is not list or not 1 <= len(actions) <= 2:
        raise ValueError("one or two ordered actions required")
    for action in actions:
        _keys(action, ("api", "asset", "args"))
        if type(action["api"]) is not str or action["api"] not in API_ARGS:
            raise ValueError("unknown API")
        if action["asset"] not in ASSETS:
            raise ValueError("unknown asset")
        spec = API_ARGS[action["api"]]
        _keys(action["args"], spec)
        for name, choices in spec.items():
            v = action["args"][name]
            if not any(type(v) is type(c) and v == c for c in choices):
                raise ValueError("invalid argument")
    condition = value["condition"]
    if condition is not None:
        _keys(condition, ("asset", "sensor", "op", "value", "unit"))
        if (condition["asset"] not in ASSETS or condition["sensor"] != "temperature"
                or condition["op"] not in ("gt", "lt") or condition["unit"] != "C"
                or type(condition["value"]) is not int
                or condition["value"] not in (50, 70, 90)):
            raise ValueError("invalid condition")
    return value


def canonical(value):
    return json.dumps(validate(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def parse(raw):
    if type(raw) is not str:
        raise ValueError("output must be a JSON string")
    def unique(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ValueError("duplicate JSON key")
            out[k] = v
        return out
    if len(raw.encode("utf-8")) > 4096:
        raise ValueError("output exceeds bounded record")
    return validate(json.loads(raw, object_pairs_hook=unique))


def leaves(value, path=""):
    if isinstance(value, dict):
        return {kv for k, v in value.items() for kv in leaves(v, f"{path}/{k}")}
    if isinstance(value, list):
        return {kv for i, v in enumerate(value) for kv in leaves(v, f"{path}/{i}")}
    return {(path, json.dumps(value, allow_nan=False))}


def percentile(values, q):
    if not values:
        return None
    x = sorted(values)
    p = (len(x) - 1) * q
    lo, hi = math.floor(p), math.ceil(p)
    return x[lo] + (x[hi] - x[lo]) * (p - lo)


def evaluate(cases, predictions):
    """Every issued case stays in denominator, including missing/failed outputs."""
    ids = [x["id"] for x in cases]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate case ID")
    by_id = {}
    for row in predictions:
        if row["id"] in by_id or row["id"] not in ids:
            raise ValueError("duplicate or unexpected prediction ID")
        by_id[row["id"]] = row
    counts = Counter()
    groups = {}
    timings = []
    for case in cases:
        gold = validate(case["gold"])
        row = by_id.get(case["id"])
        counts["requests"] += 1
        counts["gold_accepted"] += gold["outcome"] == "Accepted"
        group = groups.setdefault(case["category"], Counter())
        group["requests"] += 1
        pred = None
        if row is None:
            counts["missing"] += 1
        elif row.get("error"):
            counts["runtime_errors"] += 1
        else:
            try:
                pred = parse(row["output"])
            except (ValueError, TypeError, KeyError):
                counts["invalid"] += 1
        correct = pred is not None and canonical(pred) == canonical(gold)
        counts["correct"] += correct
        group["correct"] += correct
        counts["structurally_valid"] += pred is not None
        if pred is not None and pred["outcome"] == "Accepted":
            counts["accepted"] += 1
            counts["accepted_errors"] += not correct
            counts["correct_accepted"] += correct
        # Positional leaf scoring includes action order, API and every argument.
        expected = leaves(gold)
        actual = leaves(pred) if pred is not None else set()
        counts["leaf_tp"] += len(expected & actual)
        counts["leaf_fp"] += len(actual - expected)
        counts["leaf_fn"] += len(expected - actual)
        def argument_leaves(items):
            return {x for x in items if '/args/' in x[0] or x[0].endswith('/asset')
                    or x[0].startswith('/condition/')}
        wanted_args, got_args = argument_leaves(expected), argument_leaves(actual)
        counts["argument_tp"] += len(wanted_args & got_args)
        counts["argument_fp"] += len(got_args - wanted_args)
        counts["argument_fn"] += len(wanted_args - got_args)
        if row is not None and row.get("latency_ms") is not None:
            t = row["latency_ms"]
            if type(t) not in (int, float) or not math.isfinite(t) or t < 0:
                raise ValueError("invalid timing")
            timings.append(t)
    n = counts["requests"]
    return {
        "counts": dict(counts),
        "full_command_accuracy": counts["correct"] / n if n else None,
        "structural_validity": counts["structurally_valid"] / n if n else None,
        "accepted_coverage": counts["accepted"] / n if n else None,
        "accepted_error": counts["accepted_errors"] / counts["accepted"] if counts["accepted"] else None,
        "supported_correct_coverage": counts["correct_accepted"] / counts["gold_accepted"] if counts["gold_accepted"] else None,
        "leaf_f1": 2 * counts["leaf_tp"] / max(1, 2 * counts["leaf_tp"] + counts["leaf_fp"] + counts["leaf_fn"]),
        "argument_slot_micro_f1": 2 * counts["argument_tp"] / max(1, 2 * counts["argument_tp"] + counts["argument_fp"] + counts["argument_fn"]),
        "latency_ms": {"timed_requests": len(timings), **{f"p{p}": percentile(timings, p/100) for p in (50, 95, 99)}},
        "categories": {k: dict(v) for k, v in groups.items()},
        "hard_deadline_claim": False,
    }
