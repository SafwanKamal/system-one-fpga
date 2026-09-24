"""Export an integer model as the artefact Phase 2 consumes.

The contract with the RTL is only as good as the guarantee that both sides loaded
the same numbers. So export writes three things together:

  * ``model.npz``   -- the integer tensors, exactly as the golden model holds them
  * ``*.mem``       -- Vivado-loadable hex, one word per line, for BRAM/DDR2 init
  * ``manifest.json`` -- SHA-256 of every tensor and every .mem file, plus the
                         arithmetic constants and the measured accumulator widths

The hashes are the point. A weight file that is silently truncated, byte-swapped,
or regenerated from a different training run is the single most common way a
bit-exact comparison turns into a week of debugging RTL that was never wrong. If
the hardware build and the golden model agree on the manifest hash, any
disagreement in their outputs is a real arithmetic difference.

The .mem writer emits two's-complement hex at the tensor's natural width. Sub-byte
widths (4-bit, ternary) are written one value per line rather than packed, because
the packing order is an RTL decision and baking a guess into the export is how you
get a transposed table that still loads cleanly.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from .model import ModelConfig
from .quant import MULT_SHIFT, RECIP_SHIFT, QuantModel


def _sha256_array(a: np.ndarray) -> str:
    """Hash canonicalised bytes: C-order, fixed dtype, so the digest depends on
    the values and shape rather than on how NumPy happened to lay them out."""
    h = hashlib.sha256()
    h.update(str(a.shape).encode())
    h.update(str(a.dtype.str).encode())
    h.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_mem(a: np.ndarray, path: Path, bits: int) -> None:
    """Two's-complement hex, row-major, one value per line."""
    width = max(bits, 2)
    nybbles = (width + 3) // 4
    mod = 1 << width
    flat = np.ascontiguousarray(a).reshape(-1).astype(np.int64)
    with open(path, "w") as f:
        for v in flat:
            f.write(f"{int(v) % mod:0{nybbles}x}\n")


def export(
    qm: QuantModel,
    mcfg: ModelConfig,
    out_dir: Path | str,
    metrics: dict | None = None,
    widths: dict | None = None,
    notes: str | None = None,
) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    tensors = {
        "Eq": qm.Eq.astype(np.int32), "W1q": qm.W1q.astype(np.int32),
        "W2q": qm.W2q.astype(np.int32), "M1": qm.M1.astype(np.int64),
        "B1": qm.B1.astype(np.int64), "M2": qm.M2.astype(np.int64),
        "B2": qm.B2.astype(np.int64), "recip": qm.recip.astype(np.int64),
    }
    np.savez_compressed(out / "model.npz", **tensors)

    mem_bits = {"Eq": qm.cfg.emb_bits, "W1q": qm.cfg.w1_bits, "W2q": qm.cfg.w2_bits,
                "M1": 32, "B1": 32, "M2": 32, "B2": 32, "recip": 32}
    mem_files = {}
    for name, arr in tensors.items():
        p = out / f"{name}.mem"
        write_mem(arr, p, mem_bits[name])
        mem_files[name] = {"file": p.name, "sha256": _sha256_file(p),
                           "bits": mem_bits[name], "n_words": int(arr.size)}

    manifest = {
        "format_version": 1,
        "model": asdict(mcfg),
        "quant": asdict(qm.cfg),
        "arithmetic": {
            "rounding": "round-half-up: (x*m + 2^(s-1)) >> s, arithmetic shift",
            "recip_shift": RECIP_SHIFT,
            "pool_gain": qm.pool_gain,
            "pool_rule": "pooled = (sum * recip[n] + 2^(16-g-1)) >> (16 - g), g = pool_gain",
            "mult_shift": MULT_SHIFT,
            "act_qmax": qm.act_qmax,
            "logit_qmax": qm.logit_qmax,
            "max_tokens": qm.max_tokens,
            "s_out": qm.s_out,
            "int4_range": "[-7, 7] (symmetric, -8 unused)",
            "ternary_range": "{-1, 0, +1}",
        },
        "hashing": {
            "algorithm": "FNV-1a/32",
            "offset_basis": "0x811C9DC5",
            "prime": "0x01000193",
            "index": "hash & (n_buckets - 1)",
            "normalisation": "ASCII case fold; token = maximal run of [a-z0-9]",
            "bigrams": mcfg.use_bigrams,
            "bigram_salt": "0x9E3779B9",
        },
        "tensors": {n: {"shape": list(a.shape), "dtype": str(a.dtype),
                        "sha256": _sha256_array(a)} for n, a in tensors.items()},
        "mem_files": mem_files,
        "npz_sha256": _sha256_file(out / "model.npz"),
        "storage": qm.storage_bits(),
    }
    if widths:
        manifest["measured_accumulator_widths"] = widths
    if metrics:
        manifest["golden_metrics"] = metrics
    if notes:
        manifest["notes"] = notes

    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def verify(out_dir: Path | str) -> tuple[bool, list[str]]:
    """Re-hash everything on disk against the manifest.

    Run this in CI and at the start of any hardware comparison. It is the cheap
    check that makes a later expensive check meaningful.
    """
    out = Path(out_dir)
    manifest = json.loads((out / "manifest.json").read_text())
    problems: list[str] = []

    if _sha256_file(out / "model.npz") != manifest["npz_sha256"]:
        problems.append("model.npz hash mismatch")

    with np.load(out / "model.npz") as z:
        for name, spec in manifest["tensors"].items():
            if name not in z:
                problems.append(f"{name}: missing from npz")
                continue
            a = z[name]
            if list(a.shape) != spec["shape"]:
                problems.append(f"{name}: shape {list(a.shape)} != {spec['shape']}")
            if _sha256_array(a) != spec["sha256"]:
                problems.append(f"{name}: tensor hash mismatch")

    for name, spec in manifest["mem_files"].items():
        p = out / spec["file"]
        if not p.exists():
            problems.append(f"{spec['file']}: missing")
        elif _sha256_file(p) != spec["sha256"]:
            problems.append(f"{spec['file']}: hash mismatch")

    return (not problems), problems
