import copy
import json

import numpy as np
import pytest

from sysone.v2 import eval_suite as suite
from sysone.v2.chain_data import Chain, Segment
from scripts.v2.compare_eval import compare


def test_frozen_goldens_roundtrip_and_variant_guard(tmp_path):
    chain = Chain("intent", "clinc", [Segment(["hello"], intent=0)])
    row = suite.case("clinc:7", chain, [101, 5, 102], np.array([[-128, 127], [0, 4], [7, -8]]))
    path = tmp_path / "suite.json"
    suite.save(path, {"format": 1, "image_sha256": {"nexys": "a", "kr": "b"},
                     "tokenizer_sha256": "t", "head_labels": {"intent.clinc": ["hello"]}, "cases": [row]})
    loaded = suite.load(path, "b", "t", {"intent.clinc": ["hello"]})
    assert suite.chain(loaded["cases"][0]) == chain
    assert suite.reference(row).tolist() == [[-128, 127], [0, 4], [7, -8]]
    with pytest.raises(ValueError, match="validated board variants"):
        suite.load(path, "unknown", "t", {"intent.clinc": ["hello"]})
    changed = json.loads(path.read_text())
    changed["cases"][0]["ids"][1] = 6
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="content hash"):
        suite.load(path, "a", "t", {})


def test_selection_repeats_exact_test_subset():
    examples = [Chain("intent", ds, [Segment([str(i)])])
                for ds in ("clinc", "atis") for i in range(20)]
    assert suite.select(examples, 5, 0) == suite.select(examples, 5, 0)
    assert suite.select(examples, 5, 0) != suite.select(examples, 5, 1)
    assert len(suite.select(examples, 5, 0)) == 10


def reports():
    row = {"id": "clinc:1", "dataset": "clinc", "tokens": 12, "ids_sha256": "ids",
           "hidden_sha256": "x", "predictions": [], "bit_exact": True,
           "encoder_clocks": 1500, "request_clocks": 1600, "host_round_trip_ms": 8, "heads_ms": 2}
    a = {"backend": "nexys4ddr", "complete": True, "suite_sha256": "suite",
         "clock_hz": 75000000, "cases": [row], "verification": {"exact": 1, "total": 1},
         "stats": {"clinc": {"ok": 1, "n": 1, "tp": 0, "fp": 0, "fn": 0}}}
    b = copy.deepcopy(a)
    b["backend"] = "kr260"
    b["clock_hz"] = 75000000
    b["cases"][0]["encoder_clocks"] = 750
    b["cases"][0]["request_clocks"] = 800
    return a, b


def test_compare_uses_board_counters_not_host_latency():
    a, b = reports()
    b["cases"][0]["host_round_trip_ms"] = 1000
    result = compare(a, b)
    assert result["datasets"]["clinc"]["encoder_speedup"] == 2
    assert result["datasets"]["clinc"]["accuracy"] == 1


@pytest.mark.parametrize("change,match", [
    (lambda b: b.update(complete=False), "Partial"),
    (lambda b: b.update(suite_sha256="other"), "different or unfrozen"),
    (lambda b: b["cases"][0].update(hidden_sha256="wrong"), "hidden_sha256"),
    (lambda b: b["cases"][0].update(bit_exact=False), "integer reference"),
])
def test_comparison_refuses_invalid_evidence(change, match):
    a, b = reports()
    change(b)
    with pytest.raises(ValueError, match=match):
        compare(a, b)


@pytest.mark.parametrize("dataset", ["atis", "sgd", "hwu"])
def test_client_scores_slot_labels_from_the_selected_head(tmp_path, monkeypatch, dataset):
    from types import SimpleNamespace as NS
    from scripts.v2 import sysone_v2_client as client

    gold = Chain("slots", dataset, [Segment(["Boston"], intent=0, tags=[1])])
    x = np.array([[5, -2]], dtype=np.int8)
    row = suite.case(f"{dataset}:0", gold, [101], x)
    frozen = {"suite_sha256": "frozen", "seed": 0, "cases": [row]}
    monkeypatch.setattr(suite, "load", lambda *args: frozen)
    built = NS(ids=[101], kept={0: 0})
    monkeypatch.setattr(client, "build_chain", lambda *args: built)
    predictions = [NS(head=f"intent.{dataset}", segment=0, labels=["travel"],
                      integer_logits=np.array([[4]])),
                   NS(head=f"slots.{dataset}", segment=0, labels=["B-city"],
                      integer_logits=np.array([[0, 4]]))]
    monkeypatch.setattr(client, "predict", lambda *args: predictions)
    heads = NS(labels={f"intent.{dataset}": ["travel"],
                       f"slots.{dataset}": ["O", "B-city"]})
    enc = NS(local=True, layout=NS(max_tokens=128),
             encode=lambda *args: NS(x=x, run=NS(encoder_clocks=0, total_clocks=0)))
    args = NS(suite=tmp_path / "suite.json", image_sha256="image", tokenizer_sha256="tok",
              seed=0, kr260=False, report=tmp_path / "report.json", timeout=5, verify=True)
    assert client.cmd_eval(enc, heads, None, args) == 0
    report = json.loads(args.report.read_text())
    assert report["complete"] is True
    assert report["stats"][dataset] == {"ok": 1, "n": 1, "tp": 1, "fp": 0, "fn": 0}
    assert report["verification"] == {"exact": 1, "total": 1}
