"""Fine-tune a pretrained transformer encoder on CLINC150 and score it like the board model.

    # separate environment: torch + transformers are not in the board flow's uv.lock
    uv venv ../mlenv && uv pip install --python ../mlenv torch transformers safetensors tokenizers
    ../mlenv/bin/python scripts/v2/finetune_transformer.py --model models/bert-mini --epochs 12 --lr 1e-4

Encoder -> mean pool over real tokens -> dropout -> linear over 151 classes,
plain cross-entropy (the out-of-scope class is just class 150), AdamW with linear
warm-up and decay. The checkpoint with the best validation accuracy is kept.

Scoring is the Phase 1 protocol so the numbers line up with the board model:
temperature fitted on validation, then in-scope accuracy, OOS recall (argmax and
with the max-probability rule tuned on validation for <= 1 point of in-scope
cost), ECE, Brier, and accuracy on in-scope test utterances that contain a word
the training split never uses.

Writes results/transformers/<name>.json and the logits for train / val / test to
export/transformers/<name>_logits.npz (the train logits are the distillation
targets for the smaller models). With --save the fine-tuned weights go to
export/transformers/<name>/.
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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sysone.data import load_clinc150, majority_floor      # noqa: E402
from sysone.hashing import tokenize as board_tokenize      # noqa: E402
from sysone.metrics import evaluate                        # noqa: E402
from sysone.model import softmax                           # noqa: E402
from sysone.train import fit_temperature                   # noqa: E402

KEYS = ["in_scope_accuracy", "oos_recall", "combined_accuracy", "ece_equal_width",
        "brier", "nll", "oos_auroc_by_maxprob"]


class Classifier(nn.Module):
    def __init__(self, encoder, n_classes: int, dropout: float = 0.1):
        super().__init__()
        self.encoder = encoder
        self.drop = nn.Dropout(dropout)
        self.head = nn.Linear(encoder.config.hidden_size, n_classes)

    def forward(self, input_ids, attention_mask, **_):
        h = self.encoder(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        m = attention_mask.unsqueeze(-1).to(h.dtype)
        pooled = (h * m).sum(1) / m.sum(1).clamp(min=1.0)
        return self.head(self.drop(pooled))


def batches(n: int, size: int, rng: np.random.Generator | None):
    order = rng.permutation(n) if rng is not None else np.arange(n)
    for s in range(0, n, size):
        yield order[s:s + size]


@torch.no_grad()
def predict(model, tok, texts, max_len: int, batch: int = 128) -> np.ndarray:
    model.eval()
    out = []
    for idx in batches(len(texts), batch, None):
        x = tok([texts[i] for i in idx], padding=True, truncation=True,
                max_length=max_len, return_tensors="pt")
        out.append(model(**x).float().numpy())
    return np.concatenate(out)


def score(logits_val, logits_test, ds, T: float) -> dict:
    floor, _ = majority_floor(ds.test, ds.n_classes)
    oos = ds.oos_id
    pv = softmax(logits_val.astype(np.float64) / T)
    pt = softmax(logits_test.astype(np.float64) / T)
    r = evaluate(pt, ds.test.y, ds.test.is_oos, oos, floor)
    out = {"temperature": T, "argmax": {k: r[k] for k in KEYS}}

    ins_v = ~ds.val.is_oos
    base = float((pv.argmax(1)[ins_v] == ds.val.y[ins_v]).mean())
    best = (-1.0, 0.0)
    for tau in np.linspace(0, 0.95, 191):
        pred = np.where(pv.max(1) < tau, oos, pv.argmax(1))
        vin = float((pred[ins_v] == ds.val.y[ins_v]).mean())
        vrec = float((pred[ds.val.is_oos] == oos).mean())
        if base - vin <= 0.01 and vrec > best[0]:
            best = (vrec, float(tau))
    tau = best[1]
    pred = np.where(pt.max(1) < tau, oos, pt.argmax(1))
    ins = ~ds.test.is_oos
    out["tau_rule"] = {"threshold": tau,
                       "in_scope_accuracy": float((pred[ins] == ds.test.y[ins]).mean()),
                       "oos_recall": float((pred[ds.test.is_oos] == oos).mean()),
                       "combined_accuracy": float((pred == ds.test.y).mean())}
    train_vocab = {w for t in ds.train.texts for w in board_tokenize(t)}
    has_new = np.array([any(w not in train_vocab for w in board_tokenize(t))
                        for t in ds.test.texts])
    sel = ins & has_new
    out["unseen_word_subset"] = {"n": int(sel.sum()),
                                 "accuracy": float((pt.argmax(1)[sel] == ds.test.y[sel]).mean())}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="local directory with config, weights, tokenizer")
    ap.add_argument("--name", default=None)
    ap.add_argument("--variant", default="full")
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--lr", type=float, default=5e-5)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--max-len", type=int, default=48)
    ap.add_argument("--warmup", type=float, default=0.06)
    ap.add_argument("--weight-decay", type=float, default=0.01)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--oos-weight", type=float, default=1.0,
                    help="class weight of out-of-scope in the loss (the board model uses 10)")
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()

    from transformers import AutoModel, AutoTokenizer

    torch.manual_seed(args.seed)
    torch.set_num_threads(args.threads)
    rng = np.random.default_rng(args.seed)
    name = args.name or Path(args.model).name
    ds = load_clinc150(variant=args.variant)

    tok = AutoTokenizer.from_pretrained(args.model)
    model = Classifier(AutoModel.from_pretrained(args.model), ds.n_classes)
    n_params = sum(p.numel() for p in model.parameters())
    emb_params = sum(p.numel() for n, p in model.named_parameters() if "embeddings" in n)
    print(f"{name}: {n_params / 1e6:.2f}M parameters ({emb_params / 1e6:.2f}M in embeddings)", flush=True)

    no_decay = ("bias", "LayerNorm.weight", "layer_norm.weight")
    groups = [
        {"params": [p for n, p in model.named_parameters() if not n.endswith(no_decay)],
         "weight_decay": args.weight_decay},
        {"params": [p for n, p in model.named_parameters() if n.endswith(no_decay)],
         "weight_decay": 0.0},
    ]
    opt = torch.optim.AdamW(groups, lr=args.lr)
    steps = args.epochs * math.ceil(len(ds.train.texts) / args.batch)
    warm = int(args.warmup * steps)
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min(1.0, (s + 1) / max(warm, 1)) * max(0.0, (steps - s) / max(steps - warm, 1)))
    cw = torch.ones(ds.n_classes)
    cw[ds.oos_id] = args.oos_weight
    loss_fn = nn.CrossEntropyLoss(weight=cw)
    y = torch.as_tensor(ds.train.y, dtype=torch.long)

    best = (-1.0, -1)
    best_state = None
    history = []
    t0 = time.time()
    for ep in range(args.epochs):
        model.train()
        tot = 0.0
        for idx in batches(len(ds.train.texts), args.batch, rng):
            x = tok([ds.train.texts[i] for i in idx], padding=True, truncation=True,
                    max_length=args.max_len, return_tensors="pt")
            loss = loss_fn(model(**x), y[idx])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            opt.zero_grad()
            tot += float(loss.detach()) * len(idx)
        lv = predict(model, tok, ds.val.texts, args.max_len)
        acc = float((lv.argmax(1) == ds.val.y).mean())
        history.append({"epoch": ep, "train_loss": tot / len(ds.train.texts), "val_acc": acc,
                        "minutes": (time.time() - t0) / 60})
        print(f"  epoch {ep}: loss {history[-1]['train_loss']:.4f}  val acc {acc:.4f}  "
              f"({history[-1]['minutes']:.1f} min)", flush=True)
        if acc > best[0]:
            best = (acc, ep)
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    lv = predict(model, tok, ds.val.texts, args.max_len)
    lt = predict(model, tok, ds.test.texts, args.max_len)
    ltr = predict(model, tok, ds.train.texts, args.max_len)
    T = fit_temperature(lv, ds.val.y)
    res = score(lv, lt, ds, T)
    res.update({"name": name, "model_dir": str(args.model), "variant": args.variant,
                "params": n_params, "embedding_params": emb_params,
                "best_epoch": best[1], "best_val_acc": best[0], "history": history,
                "args": vars(args), "train_minutes": (time.time() - t0) / 60})

    out_dir = ROOT / "results" / "v2" / "transformers"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.json").write_text(json.dumps(res, indent=2))
    exp = ROOT / "export" / "v2" / "transformers"
    exp.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(exp / f"{name}_logits.npz", train=ltr, val=lv, test=lt, temperature=T)
    if args.save:
        d = exp / name
        d.mkdir(exist_ok=True)
        torch.save(model.state_dict(), d / "classifier.pt")
        tok.save_pretrained(d)
        model.encoder.config.save_pretrained(d)

    a, t = res["argmax"], res["tau_rule"]
    print(f"{name}: in-scope {a['in_scope_accuracy']:.4f}  OOS {a['oos_recall']:.4f}  "
          f"ECE {a['ece_equal_width']:.4f} | tau {t['threshold']:.2f}: in-scope "
          f"{t['in_scope_accuracy']:.4f} OOS {t['oos_recall']:.4f} combined "
          f"{t['combined_accuracy']:.4f} | unseen-word {res['unseen_word_subset']['accuracy']:.4f}",
          flush=True)


if __name__ == "__main__":
    main()
