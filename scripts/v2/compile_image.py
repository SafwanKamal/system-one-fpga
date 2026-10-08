"""Bring-up step 3: compile a trained chain model into one DDR image for the board.

    ../mlenv/bin/python scripts/v2/compile_image.py build --name bert-mini
    ../mlenv/bin/python scripts/v2/compile_image.py check --name bert-mini --chains 300
    ../mlenv/bin/python scripts/v2/compile_image.py show  --name bert-mini

build   calibrates the integer reference exactly as scripts/v2/int_reference.py does
        (or reuses the calibration stored in an earlier manifest with --reuse-calibration,
        which needs no corpora), then writes
            export/v2/image/<name>/<name>.img       the memory image
            export/v2/image/<name>/manifest.json    addresses, CRCs, SHA-256, scales, labels
            export/v2/image/<name>/program.txt      the decoded layer program
check   runs the image with `ImageMachine` (only the image's bytes) against
        `IntEncoder` on test chains of every dataset: final hidden codes and every head's
        logits must be identical. Also prints the widest intermediates (RTL widths).
show    verifies CRCs and prints the section map and program.

Load it on the board (laptop, Realtek adapter) at the base it was built for:

    uv run python scripts/v2/memory_link_client.py -i "Realtek USB FE Family Controller" \
        verify export/v2/image/bert-mini/bert-mini.img --address 0

(verify = write + read back + compare). The link's MB/s is the host path only.
The format is documented in src/sysone/v2/ddr_image.py.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "v2"))

from sysone.v2 import ddr_image as di                                   # noqa: E402
from sysone.v2.int_encoder import FloatEncoder, IntEncoder              # noqa: E402

# tile in x out; the encoder RTL's tile input is fixed at 16 (one 128-bit word), its
# output width is TILE_OUT (12 on the Nexys 4 DDR, 32 planned for the KR260's K26)
BOARDS = {"nexys4ddr": (16, 12), "kr260": (16, 32)}


def out_dir(name: str) -> Path:
    return ROOT / "export" / "v2" / "image" / name


def load_model(name: str):
    import torch
    from transformers import AutoConfig, AutoTokenizer
    d = ROOT / "export" / "v2" / "chain" / name
    labels = json.loads((d / "labels.json").read_text())
    cfg = AutoConfig.from_pretrained(d)
    tok = AutoTokenizer.from_pretrained(d)
    state = torch.load(d / "chain_model.pt")
    fe = FloatEncoder(state, cfg, {"intent": labels["intent"], "slots": labels["tags"],
                                   "pair": labels["pair"]})
    return fe, tok, labels


def calibrate(fe, tok, per_dataset: int, stat: str = "max", hwu: bool = False) -> dict[str, float]:
    """Same procedure and order as int_reference.py: first N training chains per dataset;
    each tensor's range is the max (or median) over chains of its 99.99th percentile."""
    from sysone.v2.chain_data import load_all
    from train_chain import Encoder
    enc = Encoder(tok, 128)
    corpus = load_all(hwu=hwu)
    fe.trace, seen = {}, {}
    for c in corpus.train:
        if seen.get(c.dataset, 0) < per_dataset:
            fe.hidden(np.asarray(enc.encode(c)["ids"]))
            seen[c.dataset] = seen.get(c.dataset, 0) + 1
    trace, fe.trace = fe.trace, None
    reduce = {"max": np.max, "median": np.median}[stat]
    return {k: float(reduce(v)) for k, v in trace.items()}


def build_int(name: str, calibration: int, reuse: bool, stat: str = "max"):
    fe, tok, labels = load_model(name)
    if reuse:
        m = json.loads((out_dir(name) / "manifest.json").read_text())
        cal = m.get("calibration_range", m.get("calibration_max"))
    else:
        cal = calibrate(fe, tok, calibration, stat, hwu="hwu" in labels["intent"])
    return IntEncoder(fe, {k: [v] for k, v in cal.items()}), cal, tok, labels


def cmd_build(a) -> None:
    t0 = time.time()
    ti, to = BOARDS[a.board] if a.tile is None else map(int, a.tile.split("x"))
    ie, cal, _, labels = build_int(a.name, a.calibration, a.reuse_calibration, a.range)
    head_labels = {"intent": labels["intent"], "slots": labels["tags"], "pair": labels["pair"]}
    img, man = di.compile_image(ie, a.name, head_labels, base=a.base, tile_in=ti, tile_out=to,
                                max_tokens=a.max_tokens)
    man["calibration_range"] = cal
    man["calibration_stat"] = a.range
    man["calibration_chains_per_dataset"] = a.calibration
    if a.reuse_calibration:                   # keep what the calibrated build recorded
        old = json.loads((out_dir(a.name) / "manifest.json").read_text())
        man["calibration_stat"] = old.get("calibration_stat", "max")
        man["calibration_chains_per_dataset"] = old.get("calibration_chains_per_dataset")
    man["board_profile"] = a.board
    out = a.name + a.suffix
    d = out_dir(out)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{out}.img").write_bytes(img)
    (d / "manifest.json").write_text(json.dumps(man, indent=1))
    (d / "program.txt").write_text(di.describe(img) + "\n")
    print(di.describe(img).split("\n  ", 1)[0])
    print(f"wrote {d / (out + '.img')} ({len(img):,} bytes, sha256 {man['sha256'][:16]}…) "
          f"in {time.time() - t0:.0f}s")


def cmd_show(a) -> None:
    print(di.describe((out_dir(a.name) / f"{a.name}.img").read_bytes()))


def cmd_check(a) -> None:
    from sysone.v2.chain_data import IGNORE, load_all
    from train_chain import Encoder, eval_sets
    img = (out_dir(a.name) / f"{a.name}.img").read_bytes()
    ie, _, tok, labels = build_int(a.name, 0, True)
    mach = di.ImageMachine(img)
    enc = Encoder(tok, 128)
    test = eval_sets(load_all(hwu="hwu" in labels["intent"]), "test", a.chains, 0)
    by: dict[str, list] = {}
    for c in test:
        by.setdefault(c.dataset, []).append(c)
    rng = random.Random(1)
    n_chain = n_hidden_bad = n_logit_bad = n_logits = n_tok = 0
    t0 = time.time()
    for ds, cs in sorted(by.items()):
        rng.shuffle(cs)
        for c in cs[:a.chains]:
            it = enc.encode(c)
            ids = np.asarray(it["ids"])
            seg = np.asarray(it["seg"])
            xr = ie.hidden(ids)
            xm = mach.hidden(ids)
            n_chain += 1
            n_tok += len(ids)
            if not np.array_equal(xr, xm):
                n_hidden_bad += 1
                continue
            probes = [("intent", h, np.where(seg == s)[0]) for s, h, *_ in it["targets"]]
            if "embed" in labels["intent"]:            # v3: the embedding head on every target
                probes += [("intent", "embed", np.where(seg == s)[0]) for s, *_ in it["targets"]]
            if it["slot_head"] is not None:
                probes.append(("slots", it["slot_head"], np.where(np.asarray(it["tags"]) != IGNORE)[0]))
            if it["pair"] is not None:
                probes.append(("pair", it["pair"][0], np.arange(len(ids))))
            for kind, h, rows in probes:
                if not len(rows):
                    continue
                lr, sr = ie.head_logits(xr, kind, h, rows)
                lm, sm = mach.head_logits(xm, f"{kind}.{h}", rows)
                n_logits += lr.size
                if not (np.array_equal(lr, lm) and np.allclose(sr, sm, rtol=1e-6)):
                    n_logit_bad += 1
        print(f"  {ds}: {min(len(cs), a.chains)} chains ({time.time() - t0:.0f}s)", flush=True)
    res = {"name": a.name, "chains": n_chain, "tokens": n_tok, "hidden_mismatch_chains": n_hidden_bad,
           "head_mismatches": n_logit_bad, "logits_compared": n_logits,
           "max_abs": mach.stats,
           "bits_signed": {k: int(v).bit_length() + 1 for k, v in mach.stats.items()},
           "clamped_fraction": {k: mach.clipped[k] / max(mach.counted[k], 1) for k in mach.clipped}}
    print(json.dumps(res, indent=1))
    (out_dir(a.name) / "check.json").write_text(json.dumps(res, indent=1))
    if n_hidden_bad or n_logit_bad:
        sys.exit(1)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--name", default="bert-mini")
    b.add_argument("--board", choices=sorted(BOARDS), default="nexys4ddr")
    b.add_argument("--tile", default=None, help="override tile, e.g. 16x12 (in x out)")
    b.add_argument("--base", type=lambda s: int(s, 0), default=0)
    b.add_argument("--suffix", default="", help="write export/v2/image/<name><suffix>/ "
                   "(e.g. -kr260), keeping the model's own image")
    b.add_argument("--max-tokens", type=int, default=128)
    b.add_argument("--calibration", type=int, default=64, help="chains per dataset")
    b.add_argument("--range", choices=["max", "median"], default="max",
                   help="activation range over calibration chains (see int_encoder.IntEncoder)")
    b.add_argument("--reuse-calibration", action="store_true",
                   help="take the activation ranges from the existing manifest (no corpora needed)")
    s = sub.add_parser("show")
    s.add_argument("--name", default="bert-mini")
    c = sub.add_parser("check")
    c.add_argument("--name", default="bert-mini")
    c.add_argument("--chains", type=int, default=200, help="test chains per dataset")
    a = ap.parse_args()
    {"build": cmd_build, "show": cmd_show, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    main()
