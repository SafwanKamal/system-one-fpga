"""Check the integer-only reference of a trained chain model against its float self.

    ../mlenv/bin/python scripts/v2/int_reference.py --name bert-mini

1. NumPy float encoder vs PyTorch on a few chains (should agree to ~1e-5).
2. Calibrate activation scales on calibration chains (training split).
3. Integer encoder (src/sysone/v2/int_encoder.py) vs float on test subsets of
   every task: same metrics as train_chain.py, plus how often the integer model's
   decision equals the float model's.

This is the model the v2 RTL will have to match bit for bit, so the accuracy it
loses here is the accuracy the board loses.

Writes results/v2/chain/<name>_int.json.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "v2"))

from sysone.v2.chain_data import IGNORE, load_all, intent_head          # noqa: E402
from sysone.v2.int_encoder import FloatEncoder, IntEncoder, isqrt       # noqa: E402,F401
from train_chain import ChainModel, Encoder, collate, eval_sets, spans  # noqa: E402


def run_chain(model_hidden, item):
    ids = np.asarray(item["ids"])
    return model_hidden(ids)


def decisions(enc_obj, x, item, labels, integer: bool):
    """Head outputs for one encoded chain: list of (kind, head, pred, gold, extra)."""
    out = []
    seg = np.asarray(item["seg"])
    for s, head, y in item["targets"]:
        rows = np.where(seg == s)[0]
        if integer:
            lg, sc = enc_obj.head_logits(x, "intent", head, rows)
            out.append(("intent", head, int(np.argmax(lg * sc)), y))
        else:
            W, b = enc_obj.heads[("intent", head)]
            out.append(("intent", head, int(np.argmax(x[rows].mean(0) @ W + b)), y))
    if item["slot_head"] is not None:
        tags = np.asarray(item["tags"])
        rows = np.where(tags != IGNORE)[0]
        if len(rows):
            if integer:
                lg, sc = enc_obj.head_logits(x, "slots", item["slot_head"], rows)
                pred = np.argmax(lg * sc, -1)
            else:
                W, b = enc_obj.heads[("slots", item["slot_head"])]
                pred = np.argmax(x[rows] @ W + b, -1)
            out.append(("slots", item["slot_head"], pred.tolist(), tags[rows].tolist()))
    if item["pair"] is not None:
        rows = np.arange(len(item["ids"]))
        if integer:
            lg, sc = enc_obj.head_logits(x, "pair", item["pair"][0], rows)
            out.append(("pair", item["pair"][0], int(np.argmax(lg * sc)), item["pair"][1]))
        else:
            W, b = enc_obj.heads[("pair", item["pair"][0])]
            out.append(("pair", item["pair"][0], int(np.argmax(x.mean(0) @ W + b)), item["pair"][1]))
    return out


def score(rows, tag_labels, oos_id):
    st = {}
    for ds, outs in rows:
        d = st.setdefault(ds, {"ok": 0, "n": 0, "ins_ok": 0, "ins_n": 0, "tp": 0, "fp": 0,
                               "fn": 0, "pair_ok": 0, "pair_n": 0})
        for kind, head, pred, gold in outs:
            if kind == "intent":
                d["ok"] += int(pred == gold)
                d["n"] += 1
                if head == "clinc" and gold != oos_id:
                    d["ins_ok"] += int(pred == gold)
                    d["ins_n"] += 1
            elif kind == "slots":
                names = tag_labels[head]
                ps = spans([names[t] for t in pred])
                gs = spans([names[t] for t in gold])
                d["tp"] += len(ps & gs)
                d["fp"] += len(ps - gs)
                d["fn"] += len(gs - ps)
            else:
                d["pair_ok"] += int(pred == gold)
                d["pair_n"] += 1
    res = {}
    for ds, d in st.items():
        r = {}
        if d["n"]:
            r["intent_accuracy"] = d["ok"] / d["n"]
        if d["ins_n"]:
            r["in_scope_accuracy"] = d["ins_ok"] / d["ins_n"]
        if d["tp"] + d["fp"] + d["fn"]:
            p = d["tp"] / max(d["tp"] + d["fp"], 1)
            rc = d["tp"] / max(d["tp"] + d["fn"], 1)
            r["slot_f1"] = 2 * p * rc / max(p + rc, 1e-9)
        if d["pair_n"]:
            r["pair_accuracy"] = d["pair_ok"] / d["pair_n"]
        res[ds] = r
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="bert-mini")
    ap.add_argument("--per-dataset", type=int, default=400)
    ap.add_argument("--calibration", type=int, default=48, help="chains per dataset")
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--range", choices=["max", "median"], default="max",
                    help="activation range: max or median over calibration chains of the "
                         "per-chain 99.99th percentile")
    args = ap.parse_args()

    from transformers import AutoConfig, AutoModel, AutoTokenizer

    torch.set_num_threads(args.threads)
    d = ROOT / "export" / "v2" / "chain" / args.name
    labels = json.loads((d / "labels.json").read_text())
    cfg = AutoConfig.from_pretrained(d)
    tok = AutoTokenizer.from_pretrained(d)
    model = ChainModel(AutoModel.from_config(cfg),
                       {k: len(v) for k, v in labels["intent"].items()},
                       {k: len(v) for k, v in labels["tags"].items()},
                       {k: len(v) for k, v in labels["pair"].items()})
    state = torch.load(d / "chain_model.pt")
    model.load_state_dict(state)
    model.eval()
    corpus = load_all()
    enc = Encoder(tok, 128)
    fe = FloatEncoder(state, cfg, {"intent": labels["intent"], "slots": labels["tags"],
                                   "pair": labels["pair"]})

    # 1. float NumPy vs PyTorch
    probe = [enc.encode(c) for c in corpus.test[:: max(1, len(corpus.test) // 5)][:5]]
    worst = 0.0
    with torch.no_grad():
        for it in probe:
            b = collate([it], enc.pad)
            ht = model.encoder(input_ids=b["ids"], attention_mask=b["att"]).last_hidden_state[0].numpy()
            worst = max(worst, float(np.abs(ht - fe.hidden(np.asarray(it["ids"]))).max()))
    print(f"NumPy float encoder vs PyTorch: max |diff| {worst:.2e}", flush=True)

    # 2. calibration
    fe.trace = {}
    seen = {}
    for c in corpus.train:
        if seen.get(c.dataset, 0) < args.calibration:
            fe.hidden(np.asarray(enc.encode(c)["ids"]))
            seen[c.dataset] = seen.get(c.dataset, 0) + 1
    trace, fe.trace = fe.trace, None
    ie = IntEncoder(fe, trace, range_stat=args.range)

    # 3. integer vs float on test subsets
    test = eval_sets(corpus, "test", args.per_dataset, 0)
    by = {}
    for c in test:
        by.setdefault(c.dataset, []).append(c)
    rng = random.Random(0)
    f_rows, i_rows, agree, total = [], [], 0, 0
    t0 = time.time()
    for ds, cs in by.items():
        rng.shuffle(cs)
        for c in cs[:args.per_dataset]:
            it = enc.encode(c)
            ids = np.asarray(it["ids"])
            fo = decisions(fe, fe.hidden(ids), it, labels, integer=False)
            io = decisions(ie, ie.hidden(ids), it, labels, integer=True)
            f_rows.append((ds, fo))
            i_rows.append((ds, io))
            for a, b in zip(fo, io):
                total += 1
                agree += int(a[2] == b[2])
        print(f"  {ds}: done ({time.time() - t0:.0f}s)", flush=True)
    oos_id = len(labels["intent"]["clinc"]) - 1
    res = {"name": args.name, "numpy_vs_torch_max_abs": worst,
           "float": score(f_rows, labels["tags"], oos_id),
           "integer": score(i_rows, labels["tags"], oos_id),
           "decision_agreement": agree / max(total, 1), "per_dataset": args.per_dataset}
    for ds in res["float"]:
        print(f"{ds:12s} float {json.dumps({k: round(v, 4) for k, v in res['float'][ds].items()})}"
              f"\n{'':12s} int   {json.dumps({k: round(v, 4) for k, v in res['integer'][ds].items()})}")
    print(f"integer decisions equal to float: {res['decision_agreement']:.4f}")
    res["range"] = args.range
    res["calibration_per_dataset"] = args.calibration
    suffix = "" if args.range == "max" else f"_{args.range}"
    out = ROOT / "results" / "v2" / "chain" / f"{args.name}_int{suffix}.json"
    out.write_text(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
