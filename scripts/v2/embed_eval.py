"""Few-shot intent classification on intents a model never saw (Banking77, SNIPS).

    ../mlenv/bin/python scripts/v2/embed_eval.py --teacher models/all-MiniLM-L6-v2
    ../mlenv/bin/python scripts/v2/embed_eval.py --chain minilm-l6        # float chain model
    ../mlenv/bin/python scripts/v2/embed_eval.py --image minilm-l6-v3     # integer image = the board

k example sentences per intent (k = 1, 5, 10; 5 draws each) form the intent's centroid;
every test sentence goes to the nearest centroid (cosine). Embeddings:
  --teacher  a sentence-transformers model: mean of all token states, normalised
  --chain    a chain model in float: its embedding head if it has one, else the mean of
             the sentence's token states (what the intent heads pool)
  --image    the compiled image through ImageMachine, bit-exact with the board: the
             "intent.embed" head (integer logits x scale)
Writes results/v2/chain/fewshot_<what>.json.
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
sys.path.insert(0, str(ROOT / "scripts" / "v2"))

from sysone.v2 import fewshot                                     # noqa: E402
from sysone.v2.chain_data import load_banking77, load_snips       # noqa: E402


def teacher_embed(path: str):
    import torch
    from transformers import AutoModel, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModel.from_pretrained(path).eval()

    @torch.no_grad()
    def f(texts):
        out = []
        for b in range(0, len(texts), 64):
            enc = tok(texts[b:b + 64], padding=True, truncation=True, max_length=128,
                      return_tensors="pt")
            h = model(**enc).last_hidden_state
            m = enc["attention_mask"].unsqueeze(-1).float()
            out.append(((h * m).sum(1) / m.sum(1)).numpy())
        return np.concatenate(out)
    return f


def chain_embed(name: str):
    import torch
    from transformers import AutoConfig, AutoModel, AutoTokenizer
    from train_chain import ChainModel, Encoder, collate
    from sysone.v2.chain_data import Chain, Segment
    d = ROOT / "export" / "v2" / "chain" / name
    labels = json.loads((d / "labels.json").read_text())
    tok = AutoTokenizer.from_pretrained(d)
    dim = len(labels["intent"].get("embed", []))
    intents = {k: len(v) for k, v in labels["intent"].items() if k != "embed"}
    model = ChainModel(AutoModel.from_config(AutoConfig.from_pretrained(d)), intents,
                       {k: len(v) for k, v in labels["tags"].items()},
                       {k: len(v) for k, v in labels["pair"].items()}, embed_dim=dim)
    model.load_state_dict(torch.load(d / "chain_model.pt"), strict=False)
    model.eval()
    enc = Encoder(tok, 128)

    @torch.no_grad()
    def f(texts):
        out = []
        for b in range(0, len(texts), 64):
            items = [enc.encode(Chain("intent", "x", [Segment(t.split(), intent=0)]))
                     for t in texts[b:b + 64]]
            batch = collate(items, enc.pad)
            h = model.encoder(input_ids=batch["ids"], attention_mask=batch["att"]).last_hidden_state
            for i in range(len(items)):
                v = h[i][batch["seg"][i] == 0].mean(0)
                out.append((model.intent["embed"](v) if dim else v).numpy())
        return np.stack(out)
    return f


def image_embed(name: str):
    from sysone.v2 import ddr_image as di
    from sysone.v2.host_heads import build_chain
    from sysone.v2.wordpiece import WordPiece
    d = ROOT / "export" / "v2" / "image" / name
    m = di.ImageMachine((d / f"{name}.img").read_bytes())
    model = name.split("-t24")[0].split("-kr260")[0]
    wp = WordPiece.from_file(ROOT / "export" / "v2" / "chain" / model / "tokenizer.json")

    def f(texts):
        out = []
        for t in texts:
            ch = build_chain(wp, [t.split()], "intent", m.h["max_tokens"])
            rows = np.array([r for r, s in enumerate(ch.seg) if s == 0])
            lg, sc = m.head_logits(m.hidden(np.asarray(ch.ids)), "intent.embed", rows)
            out.append(np.asarray(lg, dtype=np.float64).ravel() * sc)
        return np.stack(out)
    return f


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--teacher")
    g.add_argument("--chain")
    g.add_argument("--image")
    ap.add_argument("--ks", type=int, nargs="+", default=[1, 5, 10])
    ap.add_argument("--draws", type=int, default=5)
    a = ap.parse_args()
    t0 = time.time()
    if a.teacher:
        what, f = "teacher_" + Path(a.teacher).name, teacher_embed(a.teacher)
    elif a.chain:
        what, f = "chain_" + a.chain, chain_embed(a.chain)
    else:
        what, f = "image_" + a.image, image_embed(a.image)
    res = {"what": what}
    for nm, data in (("snips", load_snips()), ("banking77", load_banking77())):
        res[nm] = fewshot.evaluate(f, data, ks=a.ks, seeds=range(a.draws))
        print(nm, json.dumps({k: (round(v["accuracy"], 4) if isinstance(v, dict) else v)
                              for k, v in res[nm].items()}), f"({time.time() - t0:.0f} s)", flush=True)
    out = ROOT / "results" / "v2" / "chain" / f"fewshot_{what}.json"
    out.write_text(json.dumps(res, indent=1))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
