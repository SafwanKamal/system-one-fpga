"""Score the RTL's own output, independently of the golden model.

The testbench writes every logit the RTL emits to ``simulation/rtl_logits.hex``. This
script turns those back into probabilities (host-side softmax of logit * s_out,
exactly what a host on the other end of the Ethernet link would do) and runs the
Phase 1 metrics on them. If the RTL is bit-exact the numbers equal the manifest's
integer golden metrics; printing both side by side makes that visible rather than
implied by a PASS line.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from rtl_pack import EDGE_CASES                                 # noqa: E402
from sysone.deployed import DEPLOYED_EXPORT  # noqa: E402
from sysone.data import load_clinc150, majority_floor           # noqa: E402
from sysone.metrics import evaluate                             # noqa: E402
from sysone.model import softmax                                # noqa: E402

KEYS = ["in_scope_accuracy", "oos_recall", "combined_accuracy", "brier",
        "ece_equal_width", "ece_equal_mass", "oos_auroc_by_maxprob"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--logits", default=str(ROOT / "simulation/rtl_logits.hex"))
    ap.add_argument("--export", default=str(DEPLOYED_EXPORT))
    ap.add_argument("--out", default=str(ROOT / "results/rtl_sim.json"))
    args = ap.parse_args()

    man = json.loads((Path(args.export) / "manifest.json").read_text())
    K = man["model"]["n_classes"]
    raw = np.array([int(x, 16) for x in Path(args.logits).read_text().split()], dtype=np.int64)
    raw = np.where(raw >= 1 << 15, raw - (1 << 16), raw).reshape(-1, K)
    logits = raw[len(EDGE_CASES):]

    ds = load_clinc150()
    if len(logits) != len(ds.test.texts):
        raise SystemExit(f"expected {len(ds.test.texts)} test rows, got {len(logits)}")
    probs = softmax(logits.astype(np.float64) * man["arithmetic"]["s_out"])
    floor, _ = majority_floor(ds.test, ds.n_classes)
    rep = evaluate(probs, ds.test.y, ds.test.is_oos, ds.oos_id, floor)

    gold = man["golden_metrics"]["integer"]
    print(f"{'metric':24s} {'RTL sim':>10s} {'golden int':>11s}")
    for k in KEYS:
        print(f"{k:24s} {rep[k]:10.4f} {gold[k]:11.4f}")
    same = all(abs(rep[k] - gold[k]) < 1e-9 for k in KEYS)
    print("identical to golden integer metrics" if same else "DIFFERS from golden")

    out = {"source": "Verilator simulation of rtl/ (dense_engine head, pipelined), CLINC150 test set",
           "n": int(len(logits)), "identical_to_golden": bool(same),
           "metrics": {k: rep[k] for k in KEYS}}
    Path(args.out).write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
