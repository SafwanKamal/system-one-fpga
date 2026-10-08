"""Chains in, labels out, on the host (heads-on-the-host version of the v2 board).

    build_chain(wp, segments, task, max_len)   token ids + which rows belong to what,
                                                exactly as scripts/v2/train_chain.py's
                                                Encoder.encode builds them for training
    Heads(manifest, machine).predict(x, chain, ...)
                                                the image's heads on the board's X:
                                                integer logits (ImageMachine.head_logits,
                                                bit-exact with the integer reference),
                                                float logits = logit * per-class scale,
                                                labels and probabilities

Row rules (as in training and in scripts/v2/int_reference.py):
  intent  the mean of the rows of one segment (its word pieces, not [CLS]/[SEP])
  slots   the first piece of every word of the segment(s) asked for
  pair    the mean of every row of the chain
Dialogue chains (task "dialogue") drop their oldest turns first when too long; other
chains are cut at max_len.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import ddr_image as di


@dataclass
class BuiltChain:
    ids: list[int]
    seg: list[int]                       # segment index per row (-1: [CLS] / [SEP])
    word_rows: dict[int, list[int]]      # kept segment -> row of each word's first piece
    kept: dict[int, int]                 # original segment index -> kept index
    words: dict[int, list[str]] = field(default_factory=dict)


def build_chain(wp, segments: list[list[str]], task: str = "intent", max_len: int = 128) -> BuiltChain:
    pieces = [wp.word_pieces(words) for words in segments]
    budget = max_len - 1
    lens = [sum(len(p) for p in ps) + 1 for ps in pieces]
    keep_from = 0
    if task == "dialogue":
        while sum(lens[keep_from:]) > budget and keep_from < len(segments) - 1:
            keep_from += 1
    ids, seg = [wp.cls_id], [-1]
    word_rows: dict[int, list[int]] = {}
    kept: dict[int, int] = {}
    words: dict[int, list[str]] = {}
    for si in range(keep_from, len(segments)):
        k = kept.setdefault(si, len(kept))
        word_rows[k] = []
        words[k] = []
        for wi, p in enumerate(pieces[si]):
            for j, piece in enumerate(p):
                if len(ids) >= max_len - 1:
                    break
                if j == 0:
                    word_rows[k].append(len(ids))
                    words[k].append(segments[si][wi])
                ids.append(piece)
                seg.append(k)
        if len(ids) >= max_len:
            break
        ids.append(wp.sep_id)
        seg.append(-1)
    return BuiltChain(ids[:max_len], seg[:max_len], word_rows, kept, words)


def spans(tags: list[str]) -> set:
    """BIO tags -> {(start, end, slot)} (as scripts/v2/train_chain.py, for slot F1)."""
    out, start, name = set(), None, None
    for i, t in enumerate(tags + ["O"]):
        if t.startswith("B-") or t == "O" or (t.startswith("I-") and t[2:] != name):
            if name is not None:
                out.add((start, i, name))
            start, name = (i, t[2:]) if t != "O" else (None, None)
    return out


def _softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(-1, keepdims=True)


@dataclass
class Prediction:
    head: str                            # e.g. "intent.atis"
    segment: int | None                  # kept segment index (intent, slots)
    labels: list[str]                    # one per segment / word / pair
    probability: list[float]
    logits: np.ndarray                   # float logits (rows x classes)
    integer_logits: np.ndarray           # what ImageMachine / the integer reference gives
    words: list[str] | None = None


class Heads:
    """`decision` (export/v2/image/<name>/decision.json, scripts/v2/oos_threshold.py):
    the out-of-scope rule of one intent head, "oos" when the top probability < tau."""

    def __init__(self, manifest: dict, machine: di.ImageMachine, decision: dict | None = None):
        self.machine = machine
        self.labels = {f"{h['kind']}.{h['name']}": h["labels"] for h in manifest["heads"]}
        self.decision = decision

    def _run(self, x, name, rows):
        lg, sc = self.machine.head_logits(x, name, np.asarray(rows))
        lg = np.atleast_2d(lg)
        return lg, lg * sc

    def intent(self, x, chain: BuiltChain, head: str, segment: int) -> Prediction:
        name = f"intent.{head}"
        rows = [r for r, s in enumerate(chain.seg) if s == segment]
        lg, fl = self._run(x, name, rows)
        p = _softmax(fl)
        k = int(np.argmax(fl[0]))
        label = self.labels[name][k]
        dec = self.decision
        if dec and dec.get("head") == name and p[0, k] < dec["tau"]:
            label = dec["oos_label"]
        return Prediction(name, segment, [label], [float(p[0, k])], fl, lg)

    def slots(self, x, chain: BuiltChain, head: str, segment: int) -> Prediction:
        name = f"slots.{head}"
        rows = chain.word_rows[segment]
        if not rows:
            return Prediction(name, segment, [], [], np.zeros((0, 0)), np.zeros((0, 0)), [])
        lg, fl = self._run(x, name, rows)
        p = _softmax(fl)
        k = np.argmax(fl, -1)
        return Prediction(name, segment, [self.labels[name][i] for i in k],
                          [float(p[j, i]) for j, i in enumerate(k)], fl, lg, chain.words[segment])

    def tau(self, head: str) -> float | None:
        """The acceptance threshold of an intent head without an oos class (v3: HWU),
        decision.json "thresholds" (scripts/v2/oos_threshold.py --name ... --extra hwu)."""
        return (self.decision or {}).get("thresholds", {}).get(f"intent.{head}")

    @property
    def has_embedding(self) -> bool:
        return "intent.embed" in self.labels

    def embedding(self, x, chain: BuiltChain, segment: int) -> np.ndarray:
        """The v3 sentence embedding of one segment, unit length (float64)."""
        rows = [r for r, s in enumerate(chain.seg) if s == segment]
        lg, fl = self._run(x, "intent.embed", rows)
        v = np.asarray(fl[0], dtype=np.float64)
        return v / max(float(np.linalg.norm(v)), 1e-12)

    def pair(self, x, chain: BuiltChain, head: str) -> Prediction:
        name = f"pair.{head}"
        lg, fl = self._run(x, name, np.arange(len(chain.ids)))
        p = _softmax(fl)
        k = int(np.argmax(fl[0]))
        return Prediction(name, None, [self.labels[name][k]], [float(p[0, k])], fl, lg)


# which heads a dataset uses (the chain models' training tasks)
DATASETS = {
    "clinc": {"task": "intent", "intent": "clinc"},
    "multi": {"task": "multi", "intent": "clinc"},
    "atis": {"task": "slots", "intent": "atis", "slots": "atis"},
    "sgd": {"task": "dialogue", "intent": "sgd", "slots": "sgd"},
    "sick": {"task": "pair", "pair": "sick"},
    "msrp": {"task": "pair", "pair": "msrp"},
    "hwu": {"task": "slots", "intent": "hwu", "slots": "hwu"},      # v3 images
}


# "auto": one encoder pass, the CLINC head (with its out-of-scope rule) decides whether
# the request is in scope and which specialist heads apply. CLINC intents that ATIS
# (flight information) or SGD (services: restaurants, hotels, cars, rides, music,
# weather, banking, events) cover in more detail, with slots.
ROUTE_ATIS = {"book_flight", "flight_status"}
ROUTE_SGD = {"restaurant_reservation", "restaurant_suggestion", "book_hotel", "car_rental",
             "uber", "play_music", "weather", "transfer", "balance", "calendar_update",
             "travel_suggestion"}


@dataclass
class Routed:
    decision: str            # "out_of_scope" | "clinc" | "atis" | "sgd" | "hwu" | "custom"
    predictions: list[Prediction]
    custom: tuple[str, float] | None = None     # (user intent, cosine similarity)
    embedding: np.ndarray | None = None


@dataclass
class CustomIntents:
    """User-defined intents for the v3 embedding head: a few example sentences each.
    A request matches the nearest centroid if its cosine similarity is >= threshold."""
    names: list[str]
    centroids: np.ndarray                # (intents, D), unit rows
    threshold: float = 0.6


def route(heads: Heads, x, chain: BuiltChain, segment: int | None = None,
          custom: CustomIntents | None = None) -> Routed:
    """One encoder pass serves every head. In order:
    1. custom intents (v3 embedding head): nearest centroid above its threshold wins;
    2. CLINC with its out-of-scope rule decides whether the request is in scope; HWU
       (v3), which has no oos class, can still accept it when its own top probability
       clears its threshold (decision.json "thresholds");
    3. in scope: a flight intent -> ATIS intent and slots; a service intent -> SGD
       intent and slots unless SGD says NONE; otherwise HWU intent and slots when HWU
       is confident (v3), else the CLINC intent alone.
    The ATIS, SGD and HWU heads cannot say "none of these", so they are only used after
    CLINC (or HWU's threshold) has accepted the request."""
    seg = segment if segment is not None else (max(chain.word_rows) if chain.word_rows else 0)
    emb = heads.embedding(x, chain, seg) if heads.has_embedding else None
    if custom is not None and emb is not None and len(custom.names):
        sims = custom.centroids @ emb
        k = int(np.argmax(sims))
        if sims[k] >= custom.threshold:
            return Routed("custom", [], (custom.names[k], float(sims[k])), emb)
    clinc = heads.intent(x, chain, "clinc", seg)
    label = clinc.labels[0]
    oos = heads.decision["oos_label"] if heads.decision else "oos"
    hwu = None
    if "intent.hwu" in heads.labels:
        hwu = heads.intent(x, chain, "hwu", seg)
        t = heads.tau("hwu")
        hwu_ok = t is not None and hwu.probability[0] >= t
    if label == oos:
        if hwu is not None and hwu_ok:
            return Routed("hwu", [clinc, hwu, heads.slots(x, chain, "hwu", seg)], None, emb)
        return Routed("out_of_scope", [clinc], None, emb)
    if label in ROUTE_ATIS:
        return Routed("atis", [clinc, heads.intent(x, chain, "atis", seg),
                               heads.slots(x, chain, "atis", seg)], None, emb)
    if label in ROUTE_SGD:
        sgd = heads.intent(x, chain, "sgd", seg)
        if sgd.labels[0] != "NONE":
            return Routed("sgd", [clinc, sgd, heads.slots(x, chain, "sgd", seg)], None, emb)
    if hwu is not None and hwu_ok:
        return Routed("hwu", [clinc, hwu, heads.slots(x, chain, "hwu", seg)], None, emb)
    return Routed("clinc", [clinc], None, emb)


# ------------------------------------------------------------------- long inputs

_SENT = None


def sentences(text: str) -> list[str]:
    """Split running text into sentences (., !, ? followed by space; blank lines)."""
    import re
    global _SENT
    if _SENT is None:
        _SENT = re.compile(r"(?<=[.!?])\s+(?=[\"'(\[]?[A-Z0-9])|\n\s*\n")
    return [s.strip() for s in _SENT.split(text.strip()) if s.strip()]


def pack(wp, sents: list[str], max_len: int = 128,
         max_segments: int | None = None) -> list[list[list[str]]]:
    """Sentences -> chains of whole sentences that fit max_len tokens ([CLS] + each
    sentence's pieces + [SEP]); a sentence longer than one chain is cut into word runs
    that fit. Each chain is one board request ("multi": one result per sentence).
    `max_segments` caps the sentences per chain (training used 2-4; see
    scripts/v2/longtext_eval.py for what packing more costs in accuracy)."""
    budget = max_len - 1
    units: list[list[str]] = []
    for s in sents:
        words = s.split()
        run, n = [], 0
        for w in words:
            k = len(wp.word_pieces([w])[0]) if w else 1
            if n + k + 1 > budget and run:
                units.append(run)
                run, n = [], 0
            run.append(w)
            n += k
        if run:
            units.append(run)
    chains, cur, n = [], [], 1
    for u in units:
        k = sum(len(p) for p in wp.word_pieces(u)) + 1
        if cur and (n + k > max_len or (max_segments and len(cur) >= max_segments)):
            chains.append(cur)
            cur, n = [], 1
        cur.append(u)
        n += k
    if cur:
        chains.append(cur)
    return chains


def predict(heads: Heads, x, chain: BuiltChain, dataset: str) -> list[Prediction]:
    """Every head the dataset uses: intent for every segment (multi) or the last one,
    slots for the last segment, the pair label."""
    d = DATASETS[dataset]
    out = []
    last = max(chain.word_rows) if chain.word_rows else 0
    if "intent" in d:
        segs = sorted(chain.word_rows) if d["task"] == "multi" else [last]
        out += [heads.intent(x, chain, d["intent"], s) for s in segs]
    if "slots" in d:
        out.append(heads.slots(x, chain, d["slots"], last))
    if "pair" in d:
        out.append(heads.pair(x, chain, d["pair"]))
    return out
