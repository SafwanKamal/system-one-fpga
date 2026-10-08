"""Test vectors for the v2 encoder RTL (bring-up step 4), from the DDR image itself.

    ../mlenv/bin/python scripts/v2/encoder_vectors.py --name bert-mini-slots4 --layer 0
    ../mlenv/bin/python scripts/v2/encoder_vectors.py --name bert-mini-slots4 --full
    cd simulation/v2 && make encoder

--full covers the whole program (EMBED, the embedding LayerNorm, every layer): the
X buffer before the run then holds the token ids as INT16 elements, as the host
will write them.

--heads tests the heads on the FPGA: X before the run is the encoder's final hidden
state, and the program is a per-chain head program (ddr_image.head_program: POOL per
segment, raw INT32 LINEAR per head, all seven heads), stored after the image in
8 KiB slots, one per case. Segments are the token runs between [SEP]s.

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


def words(arr: np.ndarray, wide: bool, dtype: str | None = None) -> list[str]:
    a = np.asarray(arr, dtype=np.int64)
    raw = a.astype(dtype or ("<i2" if wide else "i1")).tobytes()
    out = []
    for o in range(0, len(raw), 16):
        out.append(raw[o:o + 16][::-1].hex())
    return out


def model_name(name: str) -> str:
    """The trained model behind an image name (images of other tile shapes / boards
    carry a suffix: bert-mini-slots4-t24, bert-mini-slots4-kr260)."""
    for suffix in ("-t24", "-kr260"):
        if name.endswith(suffix):
            return name[:-len(suffix)]
    return name


def real_chains(name: str, rng: random.Random, max_tokens: int) -> list[np.ndarray]:
    name = model_name(name)
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
    ap.add_argument("--full", action="store_true", help="the whole program from EMBED")
    ap.add_argument("--heads", action="store_true", help="head programs (heads on the FPGA)")
    ap.add_argument("--no-corpus", action="store_true")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    img = (ROOT / "export" / "v2" / "image" / a.name / f"{a.name}.img").read_bytes()
    m = di.ImageMachine(img)
    h = m.h
    H, T = h["hidden"], h["max_tokens"]
    prog_addr = next(s["address"] for s in h["section_table"] if s["name"] == "program")
    heads = di.decode_heads(img)
    head_base = (len(img) + 1023) // 1024 * 1024        # offset in the image's memory
    SLOT = 8192
    if a.heads:
        first = 0
        count = None                      # per case
    elif a.full:
        first = 0
        count = next(k for k, ins in enumerate(m.program) if ins["op"] == di.END)
    else:
        first = 2 + 11 * a.layer
        count = 11
    rng = random.Random(a.seed)
    chains = [] if a.no_corpus else real_chains(a.name, rng, T)
    nrng = np.random.default_rng(a.seed)
    chains += [np.array([101]), nrng.integers(1000, h["vocab"], T)]

    OUT.mkdir(parents=True, exist_ok=True)
    memory = bytearray(img)
    if a.heads:
        memory += bytes(head_base - len(img) + SLOT * len(chains))
    for k, ids in enumerate(chains):
        steps = {}
        if a.heads:
            n = len(ids)
            x = m.hidden(ids)
            seps = [i for i, t in enumerate(ids) if int(t) == 102] + [n]
            segments, start = [], 1 if n > 1 and int(ids[0]) == 101 else 0
            for e in seps:
                if e > start:
                    segments.append((start, e))
                start = e + 1
            segments = segments or [(0, n)]
            blob, what = di.head_program(heads, sorted(heads), n, segments, h["tile_in"], h["tile_out"])
            assert len(blob) <= SLOT
            offset = head_base + SLOT * k
            prog_addr = h["base"] + offset
            memory[offset:offset + len(blob)] = blob
            program = di.decode_instructions(blob)
            count = len(program) - 1
            steps["x0"] = x
            dtypes = {}

            def on_step(i, ins, buf):
                d = ins["dst"]
                arr = buf[d].copy()
                if ins["op"] == di.LINEAR:
                    pad = (-arr.shape[1]) % 4
                    arr = np.pad(arr, ((0, 0), (0, pad)))
                    dtypes[i] = "<i4"
                else:
                    dtypes[i] = "i1"
                steps[i] = (d, arr)

            m.run(program, {di.BUF_X: x}, on_step=on_step)
            # the same logits as heads on the host
            for i, wt in enumerate(what):
                if wt["kind"] != "logits":
                    continue
                hd = heads[wt["head"]]
                if hd["kind"] == di.HEAD_TOKEN:
                    want = m.head_logits(x, wt["head"], np.arange(n))[0]
                elif hd["kind"] == di.HEAD_ALL:
                    want = m.head_logits(x, wt["head"])[0][None]
                else:
                    want = np.stack([m.head_logits(x, wt["head"], np.arange(s0, s1))[0]
                                     for s0, s1 in segments])
                assert np.array_equal(steps[i][1][:, :want.shape[1]], want), wt
            lines = [f"{n} {first} {count} {H} {prog_addr}"]
            lines += words(steps["x0"], False)
            for i in range(first, first + count):
                d, arr = steps[i]
                w = words(arr, False, dtypes[i])
                lines.append(f"{i} {d} {len(w)}")
                lines += w
            (OUT / f"case_{k}.txt").write_text("\n".join(lines) + "\n")
            print(f"case {k}: {n} tokens, {len(segments)} segments, {count} head instructions")
            continue

        if a.full:
            raw = np.zeros(len(ids) * H, dtype=np.int8)
            raw[:2 * len(ids)] = np.asarray(ids, dtype="<i2").view(np.int8)
            steps["x0"] = raw.reshape(len(ids), H)

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
    with open(OUT / "image.hex", "w") as f:
        for o in range(0, len(memory), 16):
            f.write(memory[o:o + 16][::-1].hex() + "\n")
    (OUT / "cases.txt").write_text(f"{len(chains)}\n")
    what = "head programs" if a.heads else "whole program" if a.full else f"layer {a.layer}"
    print(f"wrote {OUT} ({len(memory) // 16:,} memory words, {what}, instructions "
          f"{first}..{first + count - 1})")


if __name__ == "__main__":
    main()
