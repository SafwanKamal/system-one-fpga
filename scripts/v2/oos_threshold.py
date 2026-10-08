"""Out-of-scope rule for the v2 CLINC head, as v1's: "oos" when the top probability is
below tau, tau tuned on validation.

    ../mlenv/bin/python scripts/v2/oos_threshold.py --name bert-mini-slots4

The v2 CLINC head was trained with "oos" as a 151st class; plain argmax finds only a
quarter to a third of the out-of-scope queries. This applies v1's host-side rule
(scripts/oos_tradeoff.py) to the integer model the board runs: every CLINC validation
and test utterance goes through the image (ImageMachine, bit-exact with the board),
the head's float probabilities are softmax(logit * scale), and tau is the value with
the largest out-of-scope recall on validation that costs at most --budget of
in-scope accuracy there. Test numbers are reported at that tau.

Writes export/v2/image/<name>/decision.json (read by sysone_v2_client.py) and
results/v2/chain/<name>_oos.json. NumPy only; needs the CLINC data (data/clinc150).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sysone.v2 import ddr_image as di                     # noqa: E402
from sysone.v2.chain_data import load_clinc               # noqa: E402
from sysone.v2.host_heads import build_chain              # noqa: E402
from sysone.v2.wordpiece import WordPiece                 # noqa: E402


def probabilities(m, wp, chains, max_len, cache: Path | None = None, heads=("intent.clinc",)):
    """Probabilities per chain (the heads' softmaxes side by side, from one encoder pass);
    with `cache`, saved every 250 chains and resumed from there (runs survive a restart)."""
    out, t0 = [], time.perf_counter()
    if cache is not None and cache.exists():
        out = list(np.load(cache))
        print(f"  resumed at {len(out)}", flush=True)
    for k, c in enumerate(chains):
        if k < len(out):
            continue
        ch = build_chain(wp, [s.words for s in c.segments], "intent", max_len)
        x = m.hidden(np.asarray(ch.ids))
        rows = np.array([r for r, s in enumerate(ch.seg) if s == 0])
        ps = []
        for h in heads:
            lg, sc = m.head_logits(x, h, rows)
            z = lg * sc
            e = np.exp(z - z.max())
            ps.append(e / e.sum())
        out.append(np.concatenate(ps))
        if cache is not None and k % 250 == 249:
            np.save(cache.with_suffix(".tmp.npy"), np.array(out))
            cache.with_suffix(".tmp.npy").replace(cache)
        if k % 1000 == 999:
            print(f"  {k + 1}/{len(chains)} ({time.perf_counter() - t0:.0f} s)", flush=True)
    return np.array(out)


def rates(p, y, oos, tau):
    pred = np.where(p.max(1) < tau, oos, p.argmax(1))
    ins = y != oos
    return (float((pred[ins] == y[ins]).mean()), float((pred[~ins] == oos).mean()),
            float((pred == y).mean()))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="bert-mini-slots4")
    ap.add_argument("--budget", type=float, default=0.01, help="in-scope accuracy to give up")
    ap.add_argument("--limit", type=int, default=0, help="smoke test: first N per split")
    ap.add_argument("--extra", choices=["hwu"], default=None,
                    help="v3: also tune the HWU head's acceptance threshold (it has no oos class) "
                         "against CLINC's out-of-scope utterances, for the router")
    ap.add_argument("--extra-budget", type=float, default=0.03,
                    help="share of HWU in-scope requests the router may reject")
    a = ap.parse_args()

    d = ROOT / "export" / "v2" / "image" / a.name
    m = di.ImageMachine((d / f"{a.name}.img").read_bytes())
    wp = WordPiece.from_file(ROOT / "export" / "v2" / "chain" / a.name / "tokenizer.json")
    splits, labels = load_clinc()
    oos = labels.index("oos")
    res = {"name": a.name, "budget": a.budget}
    probs = {}
    for split in ("dev", "test"):
        chains = splits[split][:a.limit] if a.limit else splits[split]
        print(f"{split}: {len(chains)} utterances", flush=True)
        cache = None
        if not a.limit:
            (ROOT / "logs" / "oos_cache").mkdir(parents=True, exist_ok=True)
            cache = ROOT / "logs" / "oos_cache" / f"{a.name}_{split}.npy"
        probs[split] = (probabilities(m, wp, chains, m.h["max_tokens"], cache),
                        np.array([c.segments[0].intent for c in chains]))
    pv, yv = probs["dev"]
    pt, yt = probs["test"]
    in0, _, _ = rates(pv, yv, oos, 0.0)
    best = (0.0, -1.0)
    for tau in np.arange(0.0, 1.0001, 0.005):
        vin, vrec, _ = rates(pv, yv, oos, tau)
        if in0 - vin <= a.budget and vrec > best[1]:
            best = (float(tau), vrec)
    tau = best[0]
    for nm, t in (("argmax", 0.0), ("threshold", tau)):
        tin, trec, comb = rates(pt, yt, oos, t)
        res[nm] = {"tau": t, "in_scope_accuracy": tin, "oos_recall": trec, "combined_accuracy": comb}
        print(f"{nm:9s} tau {t:.3f}: test in-scope {tin:.4f}, OOS recall {trec:.4f}, combined {comb:.4f}")
    decision = {"head": "intent.clinc", "rule": "max_prob", "oos_label": "oos", "tau": tau,
                "budget": a.budget}
    if a.extra:
        decision["thresholds"] = {"intent.hwu": extra_hwu(a, m, wp, labels, oos, tau, res)}
    if a.limit:                                   # smoke test: write nothing
        return 0
    (d / "decision.json").write_text(json.dumps(decision, indent=1))
    out = ROOT / "results" / "v2" / "chain" / f"{a.name}_oos.json"
    out.write_text(json.dumps(res, indent=1))
    print(f"wrote {d / 'decision.json'} and {out}")
    return 0


def extra_hwu(a, m, wp, clinc_labels, oos, tau_c, res) -> float:
    """The router (host_heads.route) accepts a request if CLINC is in scope (top
    probability >= tau_c) or HWU's top probability >= tau_h. tau_h: the largest value
    that keeps at least 1 - extra_budget of HWU's validation requests accepted, which
    maximises the router's rejection of CLINC's out-of-scope validation utterances."""
    from sysone.v2.chain_data import load_hwu
    hs, hwu_labels, _ = load_hwu()
    cs, _ = load_clinc()
    nc = len(clinc_labels)
    sets = {}
    for split in ("dev", "test"):
        for nm, chains in (("clinc", cs[split]), ("hwu", hs[split])):
            chains = chains[:a.limit] if a.limit else chains
            cache = None
            if not a.limit:
                cache = ROOT / "logs" / "oos_cache" / f"{a.name}_{nm}_{split}_clinc+hwu.npy"
            print(f"{nm} {split}: {len(chains)} utterances (CLINC and HWU heads)", flush=True)
            p = probabilities(m, wp, chains, m.h["max_tokens"], cache, ("intent.clinc", "intent.hwu"))
            y = np.array([c.segments[0].intent for c in chains])
            sets[(nm, split)] = (p[:, :nc], p[:, nc:], y)

    def router(split, tau_h):
        pc, ph, yc = sets[("clinc", split)]
        qc, qh, yh = sets[("hwu", split)]
        # exactly host_heads.route: CLINC accepts when its top label is not "oos" and its
        # top probability clears tau_c (the argmax can itself be the oos class)
        c_in = (pc.max(1) >= tau_c) & (pc.argmax(1) != oos)
        h_ok = ph.max(1) >= tau_h
        is_oos = yc == oos
        hc_in = (qc.max(1) >= tau_c) & (qc.argmax(1) != oos)
        hh_ok = qh.max(1) >= tau_h
        return {"oos_rejected": float((~c_in[is_oos] & ~h_ok[is_oos]).mean()),
                "clinc_in_scope_accepted": float((c_in[~is_oos] | h_ok[~is_oos]).mean()),
                "hwu_accepted": float((hc_in | hh_ok).mean()),
                "hwu_intent_accuracy": float((qh.argmax(1) == yh).mean()),
                "hwu_accepted_and_correct": float(((hc_in | hh_ok) & (qh.argmax(1) == yh)).mean())}

    best = 0.0
    for t in np.arange(0.0, 1.0001, 0.005):
        if router("dev", t)["hwu_accepted"] >= 1 - a.extra_budget:
            best = float(t)
    res["hwu_router"] = {"tau_hwu": best, "extra_budget": a.extra_budget,
                         "test_without_hwu_threshold": router("test", 0.0) | {"note": "HWU always accepts"},
                         "test": router("test", best),
                         "test_clinc_only": router("test", 1.01)}
    for k in ("test_clinc_only", "test"):
        print(f"router {k}: {json.dumps({x: round(v, 4) for x, v in res['hwu_router'][k].items()})}")
    print(f"tau_hwu {best:.3f}")
    return best


if __name__ == "__main__":
    sys.exit(main())
