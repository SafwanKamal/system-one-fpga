"""Generate synthetic H=768/FFN=3072 encoder goldens; no model-quality claim."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import argparse

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests"), str(ROOT / "scripts/v2")]
from test_ddr_image import _tiny
from kr260_vectors import hexwords
from sysone.v2 import ddr_image as di
from sysone.v2.encoder_client import RequestLayout, ids_bytes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hidden", type=int, choices=(768, 1024), default=768)
    parser.add_argument("--head-dim", type=int, choices=(16, 32, 64), default=64)
    parser.add_argument("--lengths", type=int, nargs="+", default=(1, 2, 3, 4, 5, 12, 64, 128))
    parser.add_argument("--output", type=Path, default=ROOT / "build/v2/rtl-wide-check/vectors")
    args = parser.parse_args()
    H = args.hidden
    if any(n < 1 or n > 128 for n in args.lengths):
        raise ValueError("token lengths must be 1..128")
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    encoder, rng = _tiny(H=H, A=H//args.head_dim, L=1, F=4*H, V=2048, P=128, seed=H)
    image, manifest = di.compile_image(encoder, f"synthetic-wide-{H}", base=0x60000000,
                                      tile_in=16, tile_out=32, max_tokens=128)
    di.verify_image(image)
    machine = di.ImageMachine(image)
    layout = RequestLayout.for_image(machine.h, len(image))
    (output / "image.hex").write_text("\n".join(hexwords(image)) + "\n")
    lengths = args.lengths
    for case, n in enumerate(lengths):
        ids = rng.integers(0, 2048, n)
        ids[0] = 101
        expected = encoder.hidden(ids)
        actual = machine.hidden(ids)
        if not np.array_equal(expected, actual):
            raise ValueError(f"IntEncoder/ImageMachine disagreement at {n} tokens")
        lines = [f"{n} {H} {layout.program} {layout.ids} {layout.result}"]
        lines += hexwords(ids_bytes(ids)) + hexwords(actual.astype(np.int8).tobytes())
        (output / f"case_{case}.txt").write_text("\n".join(lines) + "\n")
        print(f"H{H}, F{4*H}: {n} tokens reference exact", flush=True)
    (output / "cases.txt").write_text(f"{len(lengths)} {machine.h['base']}\n")
    manifest.update(synthetic=True, reference_verified=True, token_lengths=lengths)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Synthetic wide image {len(image):,} bytes, SHA256 {hashlib.sha256(image).hexdigest()}")


if __name__ == "__main__":
    main()
