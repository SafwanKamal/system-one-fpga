"""Freeze a matched test subset; verify both board images against common goldens."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import numpy as np

from sysone_v2_client import ROOT, load_files
from sysone.v2.chain_data import load_all
from sysone.v2.encoder_client import LocalEncoder
from sysone.v2.host_heads import Heads, build_chain
from sysone.v2 import eval_suite as suite


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="bert-mini-slots4")
    parser.add_argument("--peer-image", default="bert-mini-slots4-kr260")
    parser.add_argument("--per-dataset", type=int, default=50)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", type=Path, default=ROOT / "build/v2/eval/bert-mini-matched.json")
    args = parser.parse_args()
    image, manifest, wp, decision = load_files(args.image)
    peer_image, peer_manifest, _, peer_decision = load_files(args.peer_image)
    enc, peer = LocalEncoder(image), LocalEncoder(peer_image)
    heads = Heads(manifest, enc.machine, decision)
    peer_heads = Heads(peer_manifest, peer.machine, peer_decision)
    if manifest["dims"] != peer_manifest["dims"] or heads.labels != peer_heads.labels:
        raise SystemExit("Board variants differ in dimensions or head labels")
    model = manifest.get("model_name", args.image)
    tokenizer = ROOT / "export/v2/chain" / model / "tokenizer.json"
    peer_model = peer_manifest.get("model_name", args.peer_image.removesuffix("-kr260"))
    peer_tokenizer = ROOT / "export/v2/chain" / peer_model / "tokenizer.json"
    if tokenizer.read_bytes() != peer_tokenizer.read_bytes():
        raise SystemExit("Board tokenizers differ")
    corpus = load_all(hwu="intent.hwu" in heads.labels)
    for prefix, label_sets in (("intent", corpus.intent_labels), ("slots", corpus.tag_labels),
                               ("pair", corpus.pair_labels)):
        for dataset, labels in label_sets.items():
            if heads.labels.get(f"{prefix}.{dataset}") != labels:
                raise SystemExit(f"Corpus label ordering differs: {prefix}.{dataset}")
    selected = suite.select(corpus.test, args.per_dataset, args.seed)
    rows = []
    for index, (identifier, example) in enumerate(selected, 1):
        built = build_chain(wp, [s.words for s in example.segments], example.task, enc.layout.max_tokens)
        x = enc.encode(built.ids).x
        other = peer.encode(built.ids).x
        if not np.array_equal(x, other):
            raise SystemExit(f"Board-image integer references differ at {identifier}")
        # Task heads must also be identical, beyond their human-readable labels.
        from sysone.v2.host_heads import predict
        key = "multi" if example.dataset == "multi_clinc" else example.dataset
        a, b = predict(heads, x, built, key), predict(peer_heads, other, built, key)
        if len(a) != len(b) or any(p.labels != q.labels or
                not np.array_equal(p.integer_logits, q.integer_logits) or
                not np.array_equal(p.logits, q.logits) for p, q in zip(a, b)):
            raise SystemExit(f"Board-image task heads differ at {identifier}")
        rows.append(suite.case(identifier, example, built.ids, x))
        if index % 10 == 0 or index == len(selected):
            print(f"Validated both image variants: {index}/{len(selected)}", flush=True)
    result = suite.save(args.out, {"format": 1, "model_name": model, "seed": args.seed,
        "per_dataset": args.per_dataset, "split": "test", "head_labels": heads.labels,
        "tokenizer_sha256": hashlib.sha256(tokenizer.read_bytes()).hexdigest(),
        "image_sha256": {args.image: hashlib.sha256(image).hexdigest(),
                         args.peer_image: hashlib.sha256(peer_image).hexdigest()}, "cases": rows})
    print(f"Frozen {len(rows)} cases: {args.out}\nsuite_sha256={result['suite_sha256']}")


if __name__ == "__main__":
    main()
