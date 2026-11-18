"""Portable frozen test chains and their integer-reference hidden states."""
from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
import random

import numpy as np

from .chain_data import Chain, Segment


def digest(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def select(chains, per_dataset: int, seed: int):
    if per_dataset <= 0:
        raise ValueError("per_dataset must be positive")
    groups = {}
    for index, chain in enumerate(chains):
        groups.setdefault(chain.dataset, []).append((index, chain))
    rng = random.Random(seed)
    return [(f"{dataset}:{index}", chain)
            for dataset, rows in sorted(groups.items())
            for index, chain in rng.sample(rows, min(per_dataset, len(rows)))]


def case(case_id: str, chain: Chain, ids, hidden) -> dict:
    x = np.asarray(hidden)
    if x.shape[0] != len(ids) or np.any(x < -128) or np.any(x > 127):
        raise ValueError("Reference hidden states must be token-aligned INT8")
    raw = x.astype(np.int8).tobytes()
    return {"id": case_id, "chain": asdict(chain), "ids": list(map(int, ids)),
            "hidden_shape": list(x.shape), "hidden_b64": base64.b64encode(raw).decode(),
            "hidden_sha256": hashlib.sha256(raw).hexdigest()}


def reference(row: dict) -> np.ndarray:
    raw = base64.b64decode(row["hidden_b64"], validate=True)
    if hashlib.sha256(raw).hexdigest() != row["hidden_sha256"]:
        raise ValueError(f"Corrupt reference for {row['id']}")
    return np.frombuffer(raw, dtype=np.int8).reshape(row["hidden_shape"])


def chain(row: dict) -> Chain:
    values = dict(row["chain"])
    values["segments"] = [Segment(**segment) for segment in values["segments"]]
    return Chain(**values)


def save(path: Path, payload: dict) -> dict:
    result = {**payload, "suite_sha256": digest(payload)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def load(path: Path, image_sha: str, tokenizer_sha: str, head_labels: dict) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    claimed = payload.pop("suite_sha256")
    if claimed != digest(payload) or payload.get("format") != 1:
        raise ValueError("Invalid evaluation suite or content hash")
    if image_sha not in payload["image_sha256"].values():
        raise ValueError("Image is not one of the suite's validated board variants")
    if tokenizer_sha != payload["tokenizer_sha256"] or head_labels != payload["head_labels"]:
        raise ValueError("Tokenizer or head labels differ from the frozen suite")
    identifiers = [row["id"] for row in payload["cases"]]
    if not identifiers or len(set(identifiers)) != len(identifiers):
        raise ValueError("Suite must contain distinct cases")
    for row in payload["cases"]:
        reference(row)
    payload["suite_sha256"] = claimed
    return payload
