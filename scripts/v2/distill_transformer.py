"""Distil the fine-tuned teacher into a small pretrained transformer.

    ../mlenv/bin/python scripts/v2/distill_transformer.py --student models/bert-mini --epochs 3

Student starts from its pretrained weights (not from its own fine-tuned version)
and trains on export/transformers/distill_<teacher>.npz (augment_and_label.py):

    loss = KD_T^2 * KL(teacher_T || student_T)            on every sentence
         + alpha  * cross-entropy(gold)                    on the original sentences

with the teacher's logits softened by ``--kd-temp``. Scored and saved exactly
like finetune_transformer.py, under the name <student>-kd.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "v2"))

from finetune_transformer import Classifier, batches, predict, score   # noqa: E402
from sysone.data import load_clinc150                                   # noqa: E402
from sysone.train import fit_temperature                                # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--student", required=True)
    ap.add_argument("--teacher", default="roberta-base")
    ap.add_argument("--name", default=None)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--kd-temp", type=float, default=2.0)
    ap.add_argument("--alpha", type=float, default=0.5)
    ap.add_argument("--max-len", type=int, default=48)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--threads", type=int, default=2)
    args = ap.parse_args()

    from transformers import AutoModel, AutoTokenizer

    torch.manual_seed(args.seed)
    torch.set_num_threads(args.threads)
    rng = np.random.default_rng(args.seed)
    name = args.name or Path(args.student).name + "-kd"
    ds = load_clinc150()
    data = np.load(ROOT / "export" / "v2" / "transformers" / f"distill_{args.teacher}.npz", allow_pickle=True)
    texts = list(data["texts"])
    tlog = torch.as_tensor(data["logits"])
    hard = torch.as_tensor(data["hard"], dtype=torch.long)
    print(f"{name}: {len(texts)} distillation sentences ({int(data['is_original'].sum())} original)",
          flush=True)

    tok = AutoTokenizer.from_pretrained(args.student)
    model = Classifier(AutoModel.from_pretrained(args.student), ds.n_classes)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    steps = args.epochs * math.ceil(len(texts) / args.batch)
    warm = int(0.06 * steps)
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min(1.0, (s + 1) / max(warm, 1)) * max(0.0, (steps - s) / max(steps - warm, 1)))
    Tk = args.kd_temp

    best, best_state, history, t0 = (-1.0, -1), None, [], time.time()
    for ep in range(args.epochs):
        model.train()
        for k, idx in enumerate(batches(len(texts), args.batch, rng)):
            x = tok([texts[i] for i in idx], padding=True, truncation=True,
                    max_length=args.max_len, return_tensors="pt")
            s = model(**x)
            kd = F.kl_div(F.log_softmax(s / Tk, -1), F.softmax(tlog[idx] / Tk, -1),
                          reduction="batchmean") * Tk * Tk
            h = hard[idx]
            ce = F.cross_entropy(s[h >= 0], h[h >= 0]) if (h >= 0).any() else s.sum() * 0
            loss = kd + args.alpha * ce
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            opt.zero_grad()
            if k % 500 == 0:
                print(f"  epoch {ep} step {k}: kd {float(kd):.4f} ce {float(ce):.4f} "
                      f"({(time.time() - t0) / 60:.1f} min)", flush=True)
        lv = predict(model, tok, ds.val.texts, args.max_len)
        acc = float((lv.argmax(1) == ds.val.y).mean())
        history.append({"epoch": ep, "val_acc": acc, "minutes": (time.time() - t0) / 60})
        print(f"  epoch {ep}: val acc {acc:.4f}", flush=True)
        if acc > best[0]:
            best = (acc, ep)
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    lv = predict(model, tok, ds.val.texts, args.max_len)
    lt = predict(model, tok, ds.test.texts, args.max_len)
    T = fit_temperature(lv, ds.val.y)
    res = score(lv, lt, ds, T)
    res.update({"name": name, "student": args.student, "teacher": args.teacher,
                "params": sum(p.numel() for p in model.parameters()),
                "best_epoch": best[1], "history": history, "args": vars(args),
                "train_minutes": (time.time() - t0) / 60})
    out = ROOT / "results" / "v2" / "transformers"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.json").write_text(json.dumps(res, indent=2))
    d = ROOT / "export" / "v2" / "transformers" / name
    d.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), d / "classifier.pt")
    tok.save_pretrained(d)
    model.encoder.config.save_pretrained(d)
    np.savez_compressed(ROOT / "export" / "v2" / "transformers" / f"{name}_logits.npz", val=lv, test=lt,
                        temperature=T)
    a, t = res["argmax"], res["tau_rule"]
    print(f"{name}: in-scope {a['in_scope_accuracy']:.4f}  OOS {a['oos_recall']:.4f}  "
          f"ECE {a['ece_equal_width']:.4f} | tau: in-scope {t['in_scope_accuracy']:.4f} "
          f"OOS {t['oos_recall']:.4f} combined {t['combined_accuracy']:.4f} | unseen-word "
          f"{res['unseen_word_subset']['accuracy']:.4f}", flush=True)


if __name__ == "__main__":
    main()
