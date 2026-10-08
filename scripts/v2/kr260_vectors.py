"""Vectors for simulation/v2/kr260_encoder_tb.sv: the KR260 PL block (kr260_encoder.sv)
driven through its AXI4-Lite registers, memory = an AXI4 slave model preloaded with a
KR260 image (16 x 32 tiles, built at its PS DDR base address):

    ../mlenv/bin/python scripts/v2/compile_image.py build --name bert-mini-slots4 \\
        --board kr260 --base 0x60000000 --reuse-calibration --suffix=-kr260
    ../mlenv/bin/python scripts/v2/kr260_vectors.py --name bert-mini-slots4-kr260
    cd simulation/v2 && make kr260

Writes simulation/v2/vectors/kr260/: image.hex (word 0 = the image base), cases.txt
("count base"), case_<k>.txt ("n H program ids result", the ids words, then X as
ImageMachine computes it). The testbench writes the ids into memory the way the ARM
would, starts the run through the registers, waits for DONE and compares X.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sysone.v2 import ddr_image as di                    # noqa: E402
from sysone.v2.encoder_client import RequestLayout, ids_bytes   # noqa: E402

OUT = ROOT / "simulation" / "v2" / "vectors" / "kr260"


def hexwords(raw: bytes) -> list[str]:
    raw = raw + bytes(-len(raw) % 16)
    return [raw[o:o + 16][::-1].hex() for o in range(0, len(raw), 16)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="bert-mini-slots4-kr260")
    ap.add_argument("--tokens", type=int, nargs="*", default=[12, 1, 128])
    ap.add_argument("--seed", type=int, default=5)
    a = ap.parse_args()
    img = (ROOT / "export" / "v2" / "image" / a.name / f"{a.name}.img").read_bytes()
    m = di.ImageMachine(img)
    lay = RequestLayout.for_image(m.h, len(img))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "image.hex").write_text("\n".join(hexwords(img)) + "\n")
    rng = np.random.default_rng(a.seed)
    for k, n in enumerate(a.tokens):
        ids = rng.integers(1000, m.h["vocab"], n)
        ids[0] = 101
        x = m.hidden(ids)
        lines = [f"{n} {lay.hidden} {lay.program} {lay.ids} {lay.result}"]
        lines += hexwords(ids_bytes(ids))
        lines += hexwords(x.astype(np.int8).tobytes())
        (OUT / f"case_{k}.txt").write_text("\n".join(lines) + "\n")
    (OUT / "cases.txt").write_text(f"{len(a.tokens)} {m.h['base']}\n")
    print(f"{len(a.tokens)} cases, image {len(img):,} bytes at {m.h['base']:#x}, ids {lay.ids:#x}, "
          f"X {lay.result:#x} -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
