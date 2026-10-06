"""Make distillation data: MLM-augmented CLINC150 sentences labelled by the teacher.

    ../mlenv/bin/python scripts/v2/augment_and_label.py --teacher roberta-base --variants 8

A student only learns the teacher's knowledge from inputs it is shown, and the
labelled training split is small (~15k sentences). TinyBERT-style augmentation
gives it many more, close to the task distribution: for each training sentence,
``--variants`` copies are made in which ~``--rate`` of the words are masked
together and refilled by sampling from pretrained RoBERTa's masked-LM head (top-k
among whole-word, alphabetic candidates). The fine-tuned teacher then labels
every sentence, original and augmented, with its full probability vector.

Outputs export/transformers/distill_<teacher>.npz with ``texts`` (originals
first), ``is_original``, ``hard`` (gold label, -1 for augmented) and ``logits``
(teacher logits, temperature not applied) plus the teacher's temperature.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "v2"))

from finetune_transformer import Classifier, predict     # noqa: E402
from sysone.data import load_clinc150                    # noqa: E402

WORD = re.compile(r"^[a-z]+$")


@torch.no_grad()
def augment(texts: list[str], mlm, tok, variants: int, rate: float, topk: int,
            rng: np.random.Generator, batch: int = 64) -> list[str]:
    # candidate vocabulary: tokens that start a word (leading space marker) and are lowercase letters
    vocab = tok.convert_ids_to_tokens(list(range(len(tok))))
    ok = torch.zeros(len(tok), dtype=torch.bool)
    for i, t in enumerate(vocab):
        if t.startswith("Ġ") and WORD.match(t[1:]):
            ok[i] = True
    jobs = [(i, v) for i in range(len(texts)) for v in range(variants)]
    out = [None] * len(jobs)
    t0 = time.time()
    for s in range(0, len(jobs), batch):
        chunk = jobs[s:s + batch]
        masked, slots = [], []
        for i, _ in chunk:
            words = texts[i].split()
            pos = [j for j, w in enumerate(words) if w.isalpha()]
            k = max(1, int(round(rate * len(pos)))) if pos else 0
            pick = set(rng.choice(pos, size=min(k, len(pos)), replace=False).tolist()) if k else set()
            masked.append(" ".join(tok.mask_token if j in pick else w for j, w in enumerate(words)))
            slots.append((words, sorted(pick)))
        x = tok(masked, padding=True, return_tensors="pt")
        logits = mlm(**x).logits
        logits[:, :, ~ok] = -1e9
        for b, (words, pick) in enumerate(slots):
            mpos = (x["input_ids"][b] == tok.mask_token_id).nonzero().flatten().tolist()
            new = list(words)
            for j, p in zip(pick, mpos):
                top = logits[b, p].topk(topk)
                probs = torch.softmax(top.values, 0).numpy().astype(np.float64)
                choice = int(top.indices[rng.choice(topk, p=probs / probs.sum())])
                new[j] = tok.convert_ids_to_tokens(choice)[1:]
            out[s + b] = " ".join(new)
        if (s // batch) % 50 == 0:
            done = s + len(chunk)
            print(f"  augmented {done}/{len(jobs)}  ({(time.time() - t0) / 60:.1f} min)", flush=True)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--teacher", default="roberta-base", help="export/transformers/<name>/")
    ap.add_argument("--mlm", default=str(ROOT / "models" / "roberta-base"))
    ap.add_argument("--variants", type=int, default=8)
    ap.add_argument("--rate", type=float, default=0.3)
    ap.add_argument("--topk", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--tag", default="", help="suffix for the output file name")
    ap.add_argument("--no-originals", action="store_true",
                    help="write only the augmented sentences (to merge with an earlier run)")
    args = ap.parse_args()

    from transformers import AutoConfig, AutoModel, AutoTokenizer, RobertaForMaskedLM

    torch.set_num_threads(args.threads)
    rng = np.random.default_rng(args.seed)
    ds = load_clinc150()

    tok = AutoTokenizer.from_pretrained(args.mlm)
    mlm = RobertaForMaskedLM.from_pretrained(args.mlm).eval()
    aug = augment(ds.train.texts, mlm, tok, args.variants, args.rate, args.topk, rng)
    del mlm

    d = ROOT / "export" / "v2" / "transformers" / args.teacher
    ttok = AutoTokenizer.from_pretrained(d)
    teacher = Classifier(AutoModel.from_config(AutoConfig.from_pretrained(d)), ds.n_classes)
    teacher.load_state_dict(torch.load(d / "classifier.pt"))
    T = float(np.load(ROOT / "export" / "v2" / "transformers" / f"{args.teacher}_logits.npz")["temperature"])

    texts = ([] if args.no_originals else list(ds.train.texts)) + aug
    t0 = time.time()
    logits = predict(teacher, ttok, texts, 48, batch=128)
    print(f"  teacher labelled {len(texts)} sentences in {(time.time() - t0) / 60:.1f} min", flush=True)
    n = 0 if args.no_originals else len(ds.train.texts)
    hard = np.concatenate([ds.train.y[:n], -np.ones(len(aug), dtype=np.int64)])
    is_orig = np.arange(len(texts)) < n
    if n:
        agree = float((logits[:n].argmax(1) == ds.train.y).mean())
        print(f"  teacher agrees with gold on {agree:.4f} of the original training sentences")
    np.savez_compressed(ROOT / "export" / "v2" / "transformers" / f"distill_{args.teacher}{args.tag}.npz",
                        texts=np.array(texts, dtype=object), is_original=is_orig, hard=hard,
                        logits=logits.astype(np.float32), temperature=T)
    for s in rng.choice(len(aug), 8, replace=False):
        print("   ", ds.train.texts[s // args.variants], "->", aug[s])


if __name__ == "__main__":
    main()
