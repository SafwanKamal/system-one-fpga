"""Few-shot intent classification with sentence embeddings (the v3 embedding head).

A new intent is a handful of example sentences: their embeddings' mean (normalised) is
the intent's centroid, and a query goes to the nearest centroid by cosine similarity.
`evaluate` measures that on intents the model never saw (Banking77, SNIPS): k examples
per intent drawn from the training split as the support set, every test sentence
classified, averaged over several draws.

`embed` is any function list[str] -> (n, d) array (rows need not be normalised), so the
same code scores the float model, a pretrained sentence encoder, and the integer image
(ImageMachine, i.e. what the board computes).
"""

from __future__ import annotations

import random
from typing import Callable

import numpy as np

Embed = Callable[[list[str]], np.ndarray]


def normalise(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float64)
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12)


def centroids(embed: Embed, examples: dict[str, list[str]]) -> tuple[list[str], np.ndarray]:
    names = sorted(examples)
    texts = [t for n in names for t in examples[n]]
    e = normalise(embed(texts))
    out, k = [], 0
    for n in names:
        m = len(examples[n])
        out.append(normalise(e[k:k + m].mean(0)))
        k += m
    return names, np.stack(out)


def classify(embed: Embed, names: list[str], cents: np.ndarray, texts: list[str]):
    """(best intent, its cosine similarity) per text."""
    sims = normalise(embed(texts)) @ cents.T
    k = sims.argmax(1)
    return [names[i] for i in k], sims[np.arange(len(texts)), k]


def evaluate(embed: Embed, data: dict, ks=(1, 5, 10), seeds=(0, 1, 2, 3, 4),
             cache: dict | None = None) -> dict:
    """data = {'train': [(text, intent)], 'test': [...]} -> {k: mean accuracy, ...}."""
    cache = {} if cache is None else cache

    def emb(texts):
        missing = [t for t in dict.fromkeys(texts) if t not in cache]
        if missing:
            for t, v in zip(missing, normalise(embed(missing))):
                cache[t] = v
        return np.stack([cache[t] for t in texts])

    pool: dict[str, list[str]] = {}
    for t, y in data["train"]:
        pool.setdefault(y, []).append(t)
    test_x = [t for t, _ in data["test"]]
    test_y = [y for _, y in data["test"]]
    emb(test_x)
    res = {}
    for k in ks:
        accs = []
        for s in seeds:
            rng = random.Random(1000 * k + s)
            support = {y: rng.sample(ts, min(k, len(ts))) for y, ts in pool.items()}
            names, c = centroids(emb, support)
            pred, _ = classify(emb, names, c, test_x)
            accs.append(float(np.mean([p == y for p, y in zip(pred, test_y)])))
        res[f"{k}-shot"] = {"accuracy": float(np.mean(accs)), "std": float(np.std(accs)),
                            "draws": len(seeds)}
    res["intents"] = len(pool)
    res["test"] = len(test_x)
    return res
