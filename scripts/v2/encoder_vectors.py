"""Test vectors for the v2 encoder RTL (bring-up step 4), from the DDR image itself.

    ../mlenv/bin/python scripts/v2/encoder_vectors.py --name bert-mini-slots4 --layer 0
    cd simulation/v2 && make encoder

Runs `ImageMachine` (src/sysone/v2/ddr_image.py) on a few chains and records every
buffer an instruction writes, so the testbench can single-step the RTL through one
encoder layer and compare after every instruction. Writes
simulation/v2/vectors/encoder/:

    image.hex        the DDR image, one 128-bit word per line (word 0 = address 0)
    cases.txt        number of cases
    case_<k>.txt     "tokens first count hidden program_address", then the X buffer
                     before the layer (tokens x hidden/16 words), then for every
                     instruction "index dst words" and the dst buffer's words

Words are written most significant byte first, so `$fscanf("%h")` reads them as
the RTL's 128-bit words (lowest address = bits [7:0]).

Cases: one real test chain per dataset (tokenised as the host will), the longest
test chain that fits, plus two synthetic ones (a single token and 128 random ids)
for the edges. --no-corpus uses synthetic chains only (no corpora or tokenizer).
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "v2"))

from sysone.v2 import ddr_image as di          # noqa: E402

OUT = ROOT / "simulation" / "v2" / "vectors" / "encoder"


def words(arr: np.ndarray, wide: bool) -> list[str]:
    a = np.asarray(arr, dtype=np.int64)
    raw = a.astype("<i2" if wide else "i1").tobytes()
    out = []
    for o in range(0, len(raw), 16):
        out.append(raw[o:o + 16][::-1].hex())
    return out


def real_chains(name: str, rng: random.Random, max_tokens: int) -> list[np.ndarray]:
    from transformers import AutoTokenizer
    from sysone.v2.chain_data import load_all
    from train_chain import Encoder
    tok = AutoTokenizer.from_pretrained(ROOT / "export" / "v2" / "chain" / name)
    enc = Encoder(tok, max_tokens)
    corpus = load_all()
    by: dict[str, list] = {}
    for c in corpus.test:
        by.setdefault(c.dataset, []).append(c)
    out = []
    for ds in sorted(by):
        out.append(np.asarray(enc.encode(rng.choice(by[ds]))["ids"]))
    longest = max((enc.encode(c) for c in rng.sample(corpus.test, 3000)), key=lambda it: len(it["ids"]))
    out.append(np.asarray(longest["ids"]))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="bert-mini-slots4")
    ap.add_argument("--layer", type=int, default=0)
    ap.add_argument("--no-corpus", action="store_true")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    img = (ROOT / "export" / "v2" / "image" / a.name / f"{a.name}.img").read_bytes()
    m = di.ImageMachine(img)
    h = m.h
    H, T = h["hidden"], h["max_tokens"]
    prog_addr = next(s["address"] for s in h["section_table"] if s["name"] == "program")
    first = 2 + 11 * a.layer
    count = 11
    rng = random.Random(a.seed)
    chains = [] if a.no_corpus else real_chains(a.name, rng, T)
    nrng = np.random.default_rng(a.seed)
    chains += [np.array([101]), nrng.integers(1000, h["vocab"], T)]

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "image.hex", "w") as f:
        for o in range(0, len(img), 16):
            f.write(img[o:o + 16][::-1].hex() + "\n")
    for k, ids in enumerate(chains):
        steps = {}

        def on_step(i, ins, buf):
            if i == first - 1:
                steps["x0"] = buf[di.BUF_X].copy()
            if first <= i < first + count:
                d = ins["dst"]
                steps[i] = (d, buf[d].copy())

        m.hidden(ids, on_step=on_step)
        lines = [f"{len(ids)} {first} {count} {H} {prog_addr}"]
        lines += words(steps["x0"], False)
        for i in range(first, first + count):
            d, arr = steps[i]
            w = words(arr, d in (di.BUF_R, di.BUF_A))
            lines.append(f"{i} {d} {len(w)}")
            lines += w
        (OUT / f"case_{k}.txt").write_text("\n".join(lines) + "\n")
        print(f"case {k}: {len(ids)} tokens")
    (OUT / "cases.txt").write_text(f"{len(chains)}\n")
    print(f"wrote {OUT} ({len(img) // 16:,} image words, layer {a.layer}, instructions "
          f"{first}..{first + count - 1})")


if __name__ == "__main__":
    main()
