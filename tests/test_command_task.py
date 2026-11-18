import copy
import json
import pytest
from sysone.v2.command_task import canonical, evaluate, parse, validate


def plan():
    return {"outcome": "Accepted", "actions": [{"api": "set_speed", "asset": "M1", "args": {"rpm": 1000}}], "condition": None}


@pytest.mark.parametrize("rpm", [True, 1000.0, "1000", 999, None])
def test_numbers_have_exact_type_and_range(rpm):
    p = plan()
    p["actions"][0]["args"]["rpm"] = rpm
    with pytest.raises(ValueError):
        validate(p)


def test_duplicate_keys_and_extra_payload_on_failure():
    with pytest.raises(ValueError):
        parse('{"outcome":"Reject","outcome":"Clarify","reason":"missing_asset"}')
    with pytest.raises(ValueError):
        validate({"outcome": "Deadline", "reason": "budget_exhausted", "actions": []})


def test_order_and_missing_predictions_count_as_errors():
    gold = plan()
    gold["actions"].append({"api": "stop_asset", "asset": "M2", "args": {}})
    reversed_plan = copy.deepcopy(gold)
    reversed_plan["actions"].reverse()
    cases = [{"id": str(i), "category": "composition", "gold": gold} for i in range(3)]
    rows = [{"id": "0", "output": canonical(gold), "latency_ms": 1},
            {"id": "1", "output": canonical(reversed_plan), "latency_ms": 3}]
    result = evaluate(cases, rows)
    assert result["full_command_accuracy"] == 1/3
    assert result["accepted_error"] == .5
    assert result["counts"]["missing"] == 1
    assert result["latency_ms"]["p50"] == 2
    with pytest.raises(ValueError):
        evaluate(cases, rows + [rows[0]])


def test_structural_validity_is_separate_from_correctness():
    result = evaluate([{"id": "a", "category": "single", "gold": plan()}],
                      [{"id": "a", "output": json.dumps({"outcome": "Reject", "reason": "unknown_asset"})}])
    assert result["structural_validity"] == 1
    assert result["full_command_accuracy"] == 0
    assert result["accepted_error"] is None
