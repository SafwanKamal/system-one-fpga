"""Train and score the v2 multi-task "chain" encoder.

    ../mlenv/bin/python scripts/v2/train_chain.py --model models/bert-mini --epochs 3 --lr 1e-4
    ../mlenv/bin/python scripts/v2/train_chain.py --model models/all-MiniLM-L6-v2 --name minilm-l6 --lr 5e-5

One encoder pass over up to ``--max-len`` (128) WordPiece tokens holding several
segments ([CLS] seg_1 [SEP] seg_2 [SEP] ...), with small heads on top:

  intent  mean of each target segment's token states -> Linear, one head per label
          set (clinc 151, atis 18, sgd 37)
  slots   each word's first sub-word state -> Linear, one head per tag set
          (atis 127, sgd 108 BIO tags)
  pair    mean of all token states -> Linear (sick 3, msrp 2)

Heads are tiny next to the encoder and on hardware they are a few extra rows of the
same matrix work, so adding tasks costs almost nothing per inference. The encoder
cost per board and length is in scripts/v2/chain_hw_estimate.py.

Scores (test split): CLINC150 in-scope accuracy / OOS recall, ATIS intent accuracy
and slot F1, SGD (multi-turn) intent accuracy and slot F1 on turns whose intent
occurs in training, with and without the dialogue context, multi-sentence per-segment
accuracy, SICK and MSRP accuracy. Also re-scored with INT8 weights and activations.

Writes results/v2/chain/<name>.json and export/v2/chain/<name>/.
"""

from __future__ import annotations

import argparse
import json
import math
import random
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

from sysone.v2.chain_data import IGNORE, Chain, Segment, intent_head, load_all   # noqa: E402


# ------------------------------------------------------------------------ encoding

class Encoder:
    """Chains -> padded tensors. Truncates from the oldest segment first."""

    def __init__(self, tok, max_len: int):
        self.tok, self.max_len = tok, max_len
        self.cls, self.sep, self.pad = tok.cls_token_id, tok.sep_token_id, tok.pad_token_id
        self.cache: dict[tuple, list[list[int]]] = {}

    def word_pieces(self, words: list[str]) -> list[list[int]]:
        key = tuple(words)
        if key not in self.cache:
            if not words:
                self.cache[key] = []
            else:
                enc = self.tok(words, is_split_into_words=True, add_special_tokens=False)
                pieces: list[list[int]] = [[] for _ in words]
                for i, w in zip(enc["input_ids"], enc.word_ids()):
                    if w is not None:
                        pieces[w].append(i)
                self.cache[key] = [p if p else [self.tok.unk_token_id] for p in pieces]
        return self.cache[key]

    def encode(self, chain: Chain) -> dict:
        segs = chain.segments
        pieces = [self.word_pieces(s.words) for s in segs]
        budget = self.max_len - 1                      # [CLS]
        lens = [sum(len(p) for p in ps) + 1 for ps in pieces]   # + [SEP]
        keep_from = 0
        if chain.task == "dialogue":                   # drop oldest context turns
            while sum(lens[keep_from:]) > budget and keep_from < len(segs) - 1:
                keep_from += 1
        ids, seg_of, first, tags = [self.cls], [-1], [False], [IGNORE]
        seg_map = {}
        for si in range(keep_from, len(segs)):
            s, ps = segs[si], pieces[si]
            seg_map[si] = len(seg_map)
            for wi, p in enumerate(ps):
                for k, piece in enumerate(p):
                    if len(ids) >= self.max_len - 1:
                        break
                    ids.append(piece)
                    seg_of.append(seg_map[si])
                    first.append(k == 0)
                    tags.append(s.tags[wi] if (s.tags is not None and k == 0) else IGNORE)
            if len(ids) >= self.max_len:
                break
            ids.append(self.sep)
            seg_of.append(-1)
            first.append(False)
            tags.append(IGNORE)
        ids, seg_of, tags = ids[:self.max_len], seg_of[:self.max_len], tags[:self.max_len]
        targets = [(seg_map[si], intent_head(chain), s.intent) for si, s in enumerate(segs)
                   if si in seg_map and s.intent != IGNORE]
        slot_head = chain.dataset if any(s.tags is not None for s in segs) else None
        return {"ids": ids, "seg": seg_of, "tags": tags, "targets": targets,
                "slot_head": slot_head, "pair": (chain.dataset, chain.pair_label)
                if chain.task == "pair" else None}


def collate(items: list[dict], pad: int) -> dict:
    L = max(len(x["ids"]) for x in items)
    n = len(items)
    ids = torch.full((n, L), pad, dtype=torch.long)
    att = torch.zeros((n, L), dtype=torch.long)
    seg = torch.full((n, L), -1, dtype=torch.long)
    tags = torch.full((n, L), IGNORE, dtype=torch.long)
    for i, x in enumerate(items):
        k = len(x["ids"])
        ids[i, :k] = torch.as_tensor(x["ids"])
        att[i, :k] = 1
        seg[i, :k] = torch.as_tensor(x["seg"])
        tags[i, :k] = torch.as_tensor(x["tags"])
    return {"ids": ids, "att": att, "seg": seg, "tags": tags, "items": items}


# --------------------------------------------------------------------------- model

class ChainModel(nn.Module):
    def __init__(self, encoder, intent_sizes: dict, tag_sizes: dict, pair_sizes: dict,
                 dropout: float = 0.1):
        super().__init__()
        self.encoder = encoder
        H = encoder.config.hidden_size
        self.drop = nn.Dropout(dropout)
        self.intent = nn.ModuleDict({k: nn.Linear(H, v) for k, v in intent_sizes.items()})
        self.slots = nn.ModuleDict({k: nn.Linear(H, v) for k, v in tag_sizes.items()})
        self.pair = nn.ModuleDict({k: nn.Linear(H, v) for k, v in pair_sizes.items()})

    def forward(self, batch: dict) -> dict:
        h = self.encoder(input_ids=batch["ids"], attention_mask=batch["att"]).last_hidden_state
        h = self.drop(h)
        out = {"intent": [], "slots": [], "pair": []}
        seg = batch["seg"]
        for i, x in enumerate(batch["items"]):
            for s, head, y in x["targets"]:
                m = (seg[i] == s)
                v = h[i][m].mean(0) if m.any() else h[i, 0]
                out["intent"].append((head, self.intent[head](v), y, i, s))
            if x["slot_head"] is not None:
                m = batch["tags"][i] != IGNORE
                if m.any():
                    out["slots"].append((x["slot_head"], self.slots[x["slot_head"]](h[i][m]),
                                         batch["tags"][i][m], i))
            if x["pair"] is not None:
                m = batch["att"][i].bool()
                out["pair"].append((x["pair"][0], self.pair[x["pair"][0]](h[i][m].mean(0)),
                                    x["pair"][1], i))
        return out


def loss_of(out: dict, slot_weight: float = 1.0) -> torch.Tensor:
    terms = []
    for head, logit, y, *_ in out["intent"]:
        terms.append(F.cross_entropy(logit[None], torch.as_tensor([y])))
    for head, logit, y, *_ in out["slots"]:
        terms.append(slot_weight * F.cross_entropy(logit, y))
    for head, logit, y, *_ in out["pair"]:
        terms.append(F.cross_entropy(logit[None], torch.as_tensor([y])))
    return torch.stack(terms).mean() if terms else torch.zeros(())


# ------------------------------------------------------------------------- scoring

def spans(tags: list[str]) -> set:
    out, start, name = set(), None, None
    for i, t in enumerate(tags + ["O"]):
        if t.startswith("B-") or t == "O" or (t.startswith("I-") and t[2:] != name):
            if name is not None:
                out.add((start, i, name))
            start, name = (i, t[2:]) if t != "O" else (None, None)
    return out


@torch.no_grad()
def evaluate(model, enc, chains: list[Chain], corpus, batch: int = 64) -> dict:
    model.eval()
    res: dict = {}
    by = {}
    for c in chains:
        by.setdefault(c.dataset, []).append(c)
    stats = {}
    for name, cs in by.items():
        st = stats.setdefault(name, {"intent_ok": 0, "intent_n": 0, "oos_ok": 0, "oos_n": 0,
                                     "ins_ok": 0, "ins_n": 0, "tp": 0, "fp": 0, "fn": 0,
                                     "pair_ok": 0, "pair_n": 0})
        order = sorted(range(len(cs)), key=lambda i: sum(len(s.words) for s in cs[i].segments))
        for b in range(0, len(order), batch):
            items = [enc.encode(cs[i]) for i in order[b:b + batch]]
            out = model(collate(items, enc.pad))
            for head, logit, y, *_ in out["intent"]:
                p = int(logit.argmax())
                st["intent_ok"] += int(p == y)
                st["intent_n"] += 1
                if head == "clinc":
                    oos = len(corpus.intent_labels["clinc"]) - 1
                    if y == oos:
                        st["oos_ok"] += int(p == oos)
                        st["oos_n"] += 1
                    else:
                        st["ins_ok"] += int(p == y)
                        st["ins_n"] += 1
            for head, logit, y, *_ in out["slots"]:
                names = corpus.tag_labels[head]
                pt = [names[int(t)] for t in logit.argmax(-1)]
                gt = [names[int(t)] for t in y]
                ps, gs = spans(pt), spans(gt)
                st["tp"] += len(ps & gs)
                st["fp"] += len(ps - gs)
                st["fn"] += len(gs - ps)
            for head, logit, y, *_ in out["pair"]:
                st["pair_ok"] += int(int(logit.argmax()) == y)
                st["pair_n"] += 1
    for name, st in stats.items():
        r = {}
        if st["intent_n"]:
            r["intent_accuracy"] = st["intent_ok"] / st["intent_n"]
        if st["ins_n"]:
            r["in_scope_accuracy"] = st["ins_ok"] / st["ins_n"]
            r["oos_recall"] = st["oos_ok"] / max(st["oos_n"], 1)
        if st["tp"] + st["fp"] + st["fn"]:
            p = st["tp"] / max(st["tp"] + st["fp"], 1)
            rc = st["tp"] / max(st["tp"] + st["fn"], 1)
            r["slot_f1"] = 2 * p * rc / max(p + rc, 1e-9)
        if st["pair_n"]:
            r["pair_accuracy"] = st["pair_ok"] / st["pair_n"]
        r["n"] = len(by[name])
        res[name] = r
    return res


def without_context(chains: list[Chain]) -> list[Chain]:
    return [Chain(c.task, c.dataset, [c.segments[-1]], c.pair_label, c.meta) for c in chains]


def eval_sets(corpus, split: str, sgd_n: int, seed: int = 0) -> list[Chain]:
    cs = getattr(corpus, split)
    sgd = [c for c in cs if c.dataset == "sgd" and c.meta["intent_seen"]]
    random.Random(seed).shuffle(sgd)
    return [c for c in cs if c.dataset != "sgd"] + sgd[:sgd_n]


# ---------------------------------------------------------------------- quantising

def fake_quant_int8(model: nn.Module, enc, calib: list[Chain]) -> None:
    from quantize_transformer import ActQuant, quantize_weights
    quantize_weights(model, 8, 8)
    aq = ActQuant(model, 8)
    model.eval()
    with torch.no_grad():
        for b in range(0, len(calib), 32):
            model(collate([enc.encode(c) for c in calib[b:b + 32]], enc.pad))
    aq.finish()


# ---------------------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--name", default=None)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--max-len", type=int, default=128)
    ap.add_argument("--sgd-dialogues", type=int, default=4000)
    ap.add_argument("--eval-sgd", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0, help="smoke test: use N chains per split")
    ap.add_argument("--slot-weight", type=float, default=1.0,
                    help="weight of each utterance's slot-tagging loss against an intent/pair loss")
    args = ap.parse_args()

    from transformers import AutoModel, AutoTokenizer

    torch.manual_seed(args.seed)
    torch.set_num_threads(args.threads)
    random.seed(args.seed)
    name = args.name or Path(args.model).name
    t0 = time.time()
    corpus = load_all(sgd_train_dialogues=args.sgd_dialogues, seed=args.seed)
    if args.limit:
        for sp in ("train", "dev", "test"):
            cs = getattr(corpus, sp)
            random.Random(1).shuffle(cs)
            setattr(corpus, sp, cs[:args.limit])
    tok = AutoTokenizer.from_pretrained(args.model)
    enc = Encoder(tok, args.max_len)
    model = ChainModel(AutoModel.from_pretrained(args.model),
                       {k: len(v) for k, v in corpus.intent_labels.items()},
                       {k: len(v) for k, v in corpus.tag_labels.items()},
                       {k: len(v) for k, v in corpus.pair_labels.items()})
    n_enc = sum(p.numel() for p in model.encoder.parameters())
    n_heads = sum(p.numel() for p in model.parameters()) - n_enc
    print(f"{name}: encoder {n_enc / 1e6:.2f}M, heads {n_heads / 1e3:.0f}K; "
          f"{len(corpus.train)} training chains (data {time.time() - t0:.0f}s)", flush=True)

    train = corpus.train
    lengths = [sum(len(s.words) for s in c.segments) for c in train]
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    steps = args.epochs * math.ceil(len(train) / args.batch)
    warm = int(0.06 * steps)
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min(1.0, (s + 1) / max(warm, 1)) * max(0.0, (steps - s) / max(steps - warm, 1)))
    dev = eval_sets(corpus, "dev", 2000, args.seed)
    history = []
    best, best_state = -1.0, None
    rng = random.Random(args.seed)
    for ep in range(args.epochs):
        model.train()
        # length-bucketed shuffle: sort within random chunks of 50 batches
        idx = list(range(len(train)))
        rng.shuffle(idx)
        chunk = args.batch * 50
        batches = []
        for c in range(0, len(idx), chunk):
            part = sorted(idx[c:c + chunk], key=lambda i: lengths[i])
            batches += [part[b:b + args.batch] for b in range(0, len(part), args.batch)]
        rng.shuffle(batches)
        te = time.time()
        for k, b in enumerate(batches):
            out = model(collate([enc.encode(train[i]) for i in b], enc.pad))
            loss = loss_of(out, args.slot_weight)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            opt.zero_grad()
            if k % 200 == 0:
                print(f"  epoch {ep} batch {k}/{len(batches)} loss {float(loss.detach()):.4f} "
                      f"({(time.time() - te) / 60:.1f} min)", flush=True)
        r = evaluate(model, enc, dev, corpus)
        score = float(np.mean([v.get("intent_accuracy", v.get("pair_accuracy", 0.0))
                               for v in r.values()]))
        history.append({"epoch": ep, "dev": r, "dev_mean": score,
                        "minutes": (time.time() - t0) / 60})
        print(f"  epoch {ep}: dev {json.dumps({k: {m: round(x, 4) for m, x in v.items()} for k, v in r.items()})}",
              flush=True)
        if score > best:
            best = score
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    test = eval_sets(corpus, "test", args.eval_sgd, args.seed)
    res = {"name": name, "model": args.model, "encoder_params": n_enc, "head_params": n_heads,
           "args": vars(args), "history": history}
    res["test"] = evaluate(model, enc, test, corpus)
    sgd_test = [c for c in test if c.dataset == "sgd"]
    res["test_sgd_without_context"] = evaluate(model, enc, without_context(sgd_test), corpus)["sgd"]
    ctx = [c for c in sgd_test if c.meta["context_turns"] > 0]
    res["test_sgd_context_turns_only"] = {
        "with_context": evaluate(model, enc, ctx, corpus)["sgd"],
        "without_context": evaluate(model, enc, without_context(ctx), corpus)["sgd"]}
    print(f"{name} test: {json.dumps(res['test'], indent=1)}", flush=True)
    print(f"{name} SGD without context: {res['test_sgd_without_context']}", flush=True)

    out_dir = ROOT / "export" / "v2" / "chain" / name
    out_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out_dir / "chain_model.pt")
    tok.save_pretrained(out_dir)
    model.encoder.config.save_pretrained(out_dir)
    (out_dir / "labels.json").write_text(json.dumps(
        {"intent": corpus.intent_labels, "tags": corpus.tag_labels, "pair": corpus.pair_labels}))

    calib, seen = [], {}
    for c in corpus.train:                      # ~64 chains from every dataset
        if seen.get(c.dataset, 0) < 64:
            calib.append(c)
            seen[c.dataset] = seen.get(c.dataset, 0) + 1
    fake_quant_int8(model, enc, calib)
    res["test_int8"] = evaluate(model, enc, test, corpus)
    print(f"{name} INT8 test: {json.dumps(res['test_int8'])}", flush=True)
    res["minutes"] = (time.time() - t0) / 60
    rd = ROOT / "results" / "v2" / "chain"
    rd.mkdir(parents=True, exist_ok=True)
    (rd / f"{name}.json").write_text(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
