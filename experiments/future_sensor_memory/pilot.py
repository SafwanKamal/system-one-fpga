"""Reproducible, query-hidden retention pilot. See PROTOCOL.md for scope.

Run with --stage prepare, --stage validate, --stage test, or --stage summarize.
Only serialized, budget-checked archives cross into query evaluation.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import heapq
import io
import json
import math
from pathlib import Path
import pickle
import platform
import struct
import sys
import time
import zipfile
import zlib

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "build/research/future_sensor_memory"
OUT = ROOT / "results/research/future_sensor_memory/pilot_v2"
SEED = 20261108
CHUNK = 128
D = 12
BUDGETS = [8192, 16384, 32768, 65536]
LABELS = ["LYING_DOWN", "SITTING", "OR_standing", "FIX_walking",
          "FIX_running", "BICYCLING", "EATING", "COMPUTER_WORK"]
FEATURES = ["raw_acc:magnitude_stats:std", "watch_acceleration:magnitude_stats:std",
            "proc_gyro:magnitude_stats:std", "audio_properties:max_abs_value"]
URL = "https://extrasensory.ucsd.edu/data/primary_data_files/ExtraSensory.per_uuid_features_labels.zip"
ARCHIVE_SHA = "412d307bdf54a60dff81a705c2f25833889a46dca64a184e3b588ad99c69cb56"
SAMPLED = {"reservoir", "hybrid_reservoir", "hybrid_change", "hybrid_bundle"}
METHODS = ["ring", "reservoir", "change", "dyadic", "adaptive_segments",
           "codec8", "progressive_codec", "balanced_codec", "event1", "event2",
           "hybrid_reservoir", "hybrid_change", "hybrid_bundle"]
HEADER = struct.Struct("<4sIIIII")
INGEST_STATE_BYTES = 64  # PCG64 state, previous feature record, and padding/flags.


def dump(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def utc():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def quantize(x):
    return np.where(np.isfinite(x), np.rint(np.clip(np.nan_to_num(x), 0, 1) * 254), 255).astype(np.uint8)


def floats(q):
    return np.where(q == 255, np.nan, q.astype(np.float32) / 254)


def value_block(q, bits):
    """Lossy value precision; missingness is always exact. Delta filter is lossless."""
    missing = q == 255
    levels = (1 << bits) - 1
    v = np.floor(np.where(missing, 0, q).astype(float) * levels / 254 + .5).astype(np.uint8)
    if bits == 8:
        v = np.where(missing, 0, q).astype(np.uint8)
        delta = np.diff(v.astype(np.int16), axis=0, prepend=np.zeros((1, D), dtype=np.int16))
        packed = (delta % 256).astype(np.uint8).T.tobytes()
    else:
        flat = v.ravel()
        packed = np.packbits(((flat[:, None] >> np.arange(bits)) & 1).ravel(), bitorder="little").tobytes()
    mask = np.packbits(missing.ravel(), bitorder="little").tobytes() if missing.any() else b""
    body = bytes([int(bool(mask))]) + packed + mask
    return zlib.compress(body, 9)


def read_block(payload, count, bits):
    body = zlib.decompress(payload)
    missing_flag, body = body[0], body[1:]
    n = count * D
    if bits == 8:
        size = n
        delta = np.frombuffer(body[:size], dtype=np.uint8).reshape(D, count).T
        values = (np.cumsum(delta, axis=0) % 256).astype(np.float32)
    else:
        size = (n * bits + 7) // 8
        b = np.unpackbits(np.frombuffer(body[:size], dtype=np.uint8), bitorder="little")[:n * bits]
        values = (b.reshape(n, bits) * (1 << np.arange(bits))).sum(1).reshape(count, D).astype(np.float32)
    values /= 254 if bits == 8 else (1 << bits) - 1
    if missing_flag:
        mask = np.unpackbits(np.frombuffer(body[size:], dtype=np.uint8), bitorder="little")[:n].reshape(count, D)
        values[mask.astype(bool)] = np.nan
    return values


class Timeline:
    """Immutable compressed chunks; no uncharged copy of historical timestamps."""
    def __init__(self):
        self.chunks = []
        self.n = 0
        self.start = 0
        self.last = 0

    def add(self, t):
        t = np.asarray(t, dtype=np.uint32)
        if not self.n:
            self.start = int(t[0])
            self.last = self.start
        delta = np.diff(t.astype(np.int64), prepend=self.last).astype("<u4")
        b = zlib.compress(delta.tobytes(), 9)
        self.chunks.append(struct.pack("<HI", len(t), len(b)) + b)
        self.last = int(t[-1])
        self.n += len(t)

    def serialize(self):
        return b"".join(self.chunks)

    @property
    def size(self):
        return sum(map(len, self.chunks))


def read_timeline(blob, start):
    p, pieces = 0, []
    while p < len(blob):
        count, size = struct.unpack_from("<HI", blob, p)
        p += 6
        a = np.frombuffer(zlib.decompress(blob[p:p + size]), dtype="<u4")
        assert len(a) == count
        pieces.append(a)
        p += size
    return (np.cumsum(np.concatenate(pieces).astype(np.int64)) + start).astype(np.uint32)


def entry_payload(entries):
    # Scores are included because ingestion must retain them to update its heap.
    return b"".join(struct.pack("<Id", int(i), float(score)) + bytes(q) for score, i, q in sorted(entries, key=lambda a: a[1]))


def read_entries(blob):
    assert len(blob) % (12 + D) == 0
    ids, x = [], []
    for p in range(0, len(blob), 12 + D):
        i, _ = struct.unpack_from("<Id", blob, p)
        ids.append(i)
        x.append(np.frombuffer(blob[p + 12:p + 12 + D], dtype=np.uint8))
    return np.asarray(ids, dtype=int), floats(np.asarray(x, dtype=np.uint8).reshape(-1, D))


class Memory:
    def __init__(self, method, budget, seed=0, base_bits=1, mixing=0.5):
        self.method, self.budget = method, budget
        self.base_bits, self.mixing = base_bits, mixing
        self.rng = np.random.default_rng(seed)
        self.timeline = Timeline()
        self.blocks = []
        self.entries = []
        self.segments = []
        self.previous = None
        self.seen = 0
        self.peak = 0
        self.degraded = 0
        self.dropped = 0
        self.operations = 0

    def blocks_size(self):
        return sum(11 + len(b[3]) for b in self.blocks)

    def size(self):
        return HEADER.size + INGEST_STATE_BYTES + self.timeline.size + 2 + self.blocks_size() + len(self.entries) * (12 + D) + len(self.segments) * (8 + 2 * D)

    def shrink_entries(self):
        while self.entries and self.size() > self.budget:
            heapq.heappop(self.entries)

    def add_entry(self, i, q, score):
        heapq.heappush(self.entries, (float(score), int(i), q.copy()))
        self.shrink_entries()

    def ingest(self, t, q):
        """No labels, queries, total duration or future windows are arguments."""
        offset = self.seen
        self.timeline.add(t)
        self.seen += len(q)
        if HEADER.size + INGEST_STATE_BYTES + self.timeline.size + 2 > self.budget:
            raise ValueError("timeline alone exceeds budget")
        m = self.method
        if m in {"codec8", "progressive_codec", "balanced_codec", "event1", "event2"} or m.startswith("hybrid"):
            bits = self.base_bits if m.startswith("hybrid") else {"event1": 1, "event2": 2}.get(m, 8)
            self.blocks.append([offset, len(q), bits, value_block(q, bits)])
            # A compressed block can be refined only downwards; discarded precision
            # is not kept in an uncharged backing store.
            self.shrink_entries()
            while self.size() > self.budget and self.blocks:
                if m in {"progressive_codec", "balanced_codec"}:
                    choices = [k for k, b in enumerate(self.blocks) if b[2] > 1]
                    k = (max(choices, key=lambda k: self.blocks[k][2]) if m == "balanced_codec"
                         else choices[0]) if choices else None
                    if k is not None:
                        b = self.blocks[k]
                        old = read_block(b[3], b[1], b[2])
                        b[2] = {8: 4, 4: 2, 2: 1}[b[2]]
                        b[3] = value_block(quantize(old), b[2])
                        self.degraded += 1
                        continue
                self.blocks.pop(0)
                self.dropped += 1
        if m in {"dyadic", "adaptive_segments"}:
            for j, row in enumerate(q):
                # Missing is represented by a separate NaN value in each mean.
                self.segments.append([offset + j, offset + j + 1, floats(row).astype("<f2")])
                while self.size() > self.budget and len(self.segments) > 1:
                    widths = np.asarray([b - a for a, b, _ in self.segments])
                    if m == "dyadic":
                        costs = widths[:-1] + widths[1:]
                    else:
                        means = np.asarray([v for _, _, v in self.segments], dtype=np.float32)
                        diff = np.nan_to_num(means[:-1] - means[1:])
                        costs = np.sum(diff * diff, axis=1) * widths[:-1] * widths[1:] / (widths[:-1] + widths[1:])
                    k = int(np.argmin(costs))
                    a, b = self.segments[k:k + 2]
                    # Missing-only/mixed spans become unknown. This avoids inventing
                    # feature observations inside gaps in channel availability.
                    v = (a[2].astype(float) * (a[1] - a[0]) + b[2].astype(float) * (b[1] - b[0])) / (b[1] - a[0])
                    self.segments[k:k + 2] = [[a[0], b[1], v.astype("<f2")]]
                    self.operations += len(costs)
        if m in {"ring", "reservoir", "change"} or m.startswith("hybrid"):
            for j, row in enumerate(q):
                i = offset + j
                if m == "ring":
                    score = i
                elif m in {"reservoir", "hybrid_reservoir"}:
                    score = self.rng.random()
                else:
                    delta = np.zeros(D) if self.previous is None else np.abs(row.astype(float) - self.previous.astype(float)) / 254
                    delta[(row == 255) | (self.previous == 255 if self.previous is not None else False)] = 0
                    # Distinct channels jointly changing is the candidate's bundle cue.
                    top = np.sort(delta)[-2:]
                    change = float(delta.mean())
                    linked = float(np.sqrt(top[0] * top[1]))
                    score = ((1 - self.mixing) * change + self.mixing * linked) + 1e-8 * self.rng.random()
                    if m == "hybrid_bundle" and self.previous is not None:
                        # Keep the two endpoints together or evict the whole pair.
                        # Implemented separately from per-window priorities below.
                        pass
                if m == "hybrid_bundle":
                    if i % 2 == 1 and self.previous is not None:
                        self.add_entry(i - 1, self.previous, score)
                        self.add_entry(i, row, score)
                        # Remove any orphan after capacity shrink. Bundle context
                        # is charged as two full records, including two priorities.
                        ids = {e[1] for e in self.entries}
                        self.entries = [e for e in self.entries if (e[1] ^ 1) in ids]
                        heapq.heapify(self.entries)
                else:
                    self.add_entry(i, row, score)
                self.previous = row.copy()
        while self.segments and self.size() > self.budget:
            # At extremely small residual capacities even one mean record can
            # fail to fit. Preserve the timeline and answer from the prior.
            self.segments.pop(0)
            self.dropped += 1
        self.shrink_entries()
        assert self.size() <= self.budget, (m, self.size(), self.budget)
        self.peak = max(self.peak, self.size())

    def serialize(self):
        timeline = self.timeline.serialize()
        blocks = b"".join(struct.pack("<IHB I", a, n, bits, len(b)) + b for a, n, bits, b in self.blocks)
        entries = entry_payload(self.entries)
        segments = b"".join(struct.pack("<II", a, b) + v.astype("<f2").tobytes() for a, b, v in self.segments)
        kind = 2 if self.segments else (1 if self.method.startswith("hybrid") else 0)
        rng = self.rng.bit_generator.state
        state = int(rng["state"]["state"]).to_bytes(16, "little") + int(rng["state"]["inc"]).to_bytes(16, "little")
        state += struct.pack("<II", rng["has_uint32"], rng["uinteger"])
        state += bytes(self.previous) if self.previous is not None else bytes(D)
        state += bytes([self.previous is not None])
        state = state.ljust(INGEST_STATE_BYTES, b"\0")
        payload = HEADER.pack(b"FSM1", self.seen, self.timeline.start, len(timeline), len(blocks), len(entries))
        payload += bytes([kind, self.base_bits]) + state + timeline + blocks + entries + segments
        assert len(payload) == self.size()
        assert len(payload) <= self.budget
        return payload


def decode(blob, prior):
    magic, n, start, ts_size, block_size, entry_size = HEADER.unpack_from(blob)
    assert magic == b"FSM1"
    kind = blob[HEADER.size]
    p = HEADER.size + 2 + INGEST_STATE_BYTES
    times = read_timeline(blob[p:p + ts_size], start)
    assert len(times) == n
    p += ts_size
    end = p + block_size
    x = np.tile(np.asarray(prior, dtype=np.float32), (n, 1))
    covered = np.zeros(n, bool)
    while p < end:
        a, count, bits, size = struct.unpack_from("<IHB I", blob, p)
        p += 11
        x[a:a + count] = read_block(blob[p:p + size], count, bits)
        covered[a:a + count] = True
        p += size
    ids, samples = read_entries(blob[p:p + entry_size])
    p += entry_size
    if kind == 2:
        while p < len(blob):
            a, b = struct.unpack_from("<II", blob, p)
            p += 8
            x[a:b] = np.frombuffer(blob[p:p + D * 2], dtype="<f2").astype(np.float32)
            p += D * 2
            covered[a:b] = True
    if len(ids):
        if kind == 1:
            # The coarse table already preserves interval structure. Estimate
            # soft values from nearest retained sample in the SAME coarse bin.
            bits = blob[HEADER.size + 1]
            levels = (1 << bits) - 1
            for d in range(D):
                b = np.floor(x[:, d] * levels + .5)
                sb = np.floor(samples[:, d] * levels + .5)
                for k in range(levels + 1):
                    selected = np.flatnonzero(sb == k)
                    target = np.flatnonzero((b == k) & covered)
                    if len(selected) and len(target):
                        nearest = nearest_indices(times[ids[selected]], times[target])
                        x[target, d] = samples[selected[nearest], d]
            x[ids] = samples
        else:
            nearest = nearest_indices(times[ids], times)
            x = samples[nearest].copy()
            covered[:] = True
    return times, x, covered


def nearest_indices(t, target):
    right = np.minimum(np.searchsorted(t, target), len(t) - 1)
    left = np.maximum(right - 1, 0)
    dl = np.abs(target.astype(np.int64) - t[left].astype(np.int64))
    dr = np.abs(t[right].astype(np.int64) - target.astype(np.int64))
    return np.where(dl <= dr, left, right)


def queries(n, seed, validation=False):
    rng = np.random.default_rng(seed)
    result = []
    specs = [("duration", "familiar"), ("episodes", "familiar"), ("co_duration", "familiar"),
             ("follow", "composition"), ("co_episodes", "composition"),
             ("duration", "threshold_shift"), ("co_duration", "threshold_shift"),
             ("follow", "threshold_shift"), ("co_episodes", "sensor_shift"),
             ("duration", "continuous_shift"), ("co_duration", "continuous_shift"),
             ("follow", "continuous_shift")]
    for op, panel in specs:
        for j in range(48):
            d = int(rng.integers(8, D) if panel == "sensor_shift" else rng.integers(0, 8))
            e = int(rng.integers(0, D) if panel == "sensor_shift" else rng.integers(0, 8))
            if d == e:
                e = (e + 1) % (D if panel == "sensor_shift" else 8)
            a = 0 if j % 3 == 0 else int(rng.integers(0, max(1, n // 2)))
            b = n if j % 3 == 0 else int(rng.integers(max(a + 1, n // 2), n + 1))
            threshold = float(rng.choice([0.3, 0.7])) if panel == "threshold_shift" else 0.5
            if panel == "continuous_shift":
                threshold = float(rng.uniform(.2, .8))
                if j % 2 == 0:
                    d = int(rng.integers(8, D))
            result.append(dict(op=op, panel=panel, d=d, e=e, a=a, b=b, threshold=threshold))
    if validation:
        # Familiar operators only. Different threshold VALUES, not the held-out
        # composition operators, provide validation probes for useful uncertainty.
        result = [q for q in result if q["panel"] == "familiar"]
        for j, q in enumerate(result):
            q["threshold"] = [.25, .5, .75][j % 3]
            if j % 4 == 0:
                q["d"] = 8 + ((j // 4) % 4)
                q["e"] = j % 8
    return result


def starts(mask, t):
    previous = np.r_[False, mask[:-1]]
    continuous = np.r_[False, np.diff(t.astype(np.int64)) <= 90]
    return np.flatnonzero(mask & ~(previous & continuous))


def answer(x, t, q):
    a, b = q["a"], q["b"]
    tt = t
    m = x[:, q["d"]] >= q["threshold"]
    op = q["op"]
    if op == "duration":
        return int(m[a:b].sum())
    if op == "episodes":
        onsets = starts(m, tt)
        return int(((onsets >= a) & (onsets < b)).sum())
    other = x[:, q["e"]] >= q["threshold"]
    if op == "co_duration":
        return int((m & other)[a:b].sum())
    if op == "co_episodes":
        onsets = starts(m & other, tt)
        return int(((onsets >= a) & (onsets < b)).sum())
    if op == "follow":
        aa, bb = starts(m, tt), starts(other, tt)
        aa = aa[(aa >= a) & (aa < b)]
        bb = bb[(bb >= a) & (bb < b)]
        if not len(aa) or not len(bb):
            return 0
        k = np.searchsorted(tt[bb], tt[aa], side="right")
        ok = k < len(bb)
        dest = bb[np.minimum(k, len(bb) - 1)]
        breaks = np.cumsum(np.r_[0, np.diff(tt.astype(np.int64)) > 90])
        ok &= (tt[dest].astype(np.int64) - tt[aa].astype(np.int64) <= 1800)
        ok &= breaks[dest] == breaks[aa]
        return int(ok.sum())
    raise ValueError(op)


def answers(x, t, qq):
    return np.asarray([answer(x, t, q) for q in qq], dtype=np.int32)


def scores(pred, truth, qq):
    groups = {"all": np.ones(len(qq), bool)}
    for panel in sorted({q["panel"] for q in qq}):
        groups[panel] = np.asarray([q["panel"] == panel for q in qq])
    result = {}
    for group, mask in groups.items():
        error = np.abs(pred[mask] - truth[mask])
        positive = truth[mask] > 0
        result[group] = dict(n=int(mask.sum()), positive_n=int(positive.sum()),
                             exact=float(np.mean(error == 0)),
                             positive_exact=float(np.mean(error[positive] == 0)) if positive.any() else None,
                             nmae=float(np.mean(error / np.maximum(truth[mask], 1))),
                             zero_reference=float(np.mean(~positive)))
    return result


def prepare():
    from sklearn.ensemble import ExtraTreesClassifier
    from sklearn.metrics import average_precision_score, f1_score
    import sklearn
    import requests
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    archive = WORK / "data/ExtraSensory.per_uuid_features_labels.zip"
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        r = requests.get(URL, stream=True, timeout=(30, 180))
        r.raise_for_status()
        with archive.open("wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                f.write(chunk)
    assert sha(archive) == ARCHIVE_SHA
    z = zipfile.ZipFile(archive)
    names = sorted(n for n in z.namelist() if n.endswith(".csv.gz"))
    ids = [n.split(".")[0] for n in names]
    perm = np.random.default_rng(SEED).permutation(len(ids))
    split = {"train": [ids[i] for i in perm[:36]], "validation": [ids[i] for i in perm[36:48]], "test": [ids[i] for i in perm[48:]]}
    dump(OUT / "split.json", split)
    cache = WORK / "parsed"
    cache.mkdir(exist_ok=True)
    header = None
    for name, user in zip(names, ids):
        f = cache / f"{user}.npz"
        if f.exists():
            continue
        with gzip.GzipFile(fileobj=z.open(name)) as g:
            columns = g.readline().decode().strip().split(",")
            if header is None:
                header = columns
                dump(WORK / "columns.json", columns)
            a = np.loadtxt(g, delimiter=",", dtype=np.float32)
        # Epoch timestamps require integer precision; float32 would collapse nearby
        # observations, so read that column again with float64.
        with gzip.GzipFile(fileobj=z.open(name)) as g:
            t = np.loadtxt(g, delimiter=",", skiprows=1, usecols=[0], dtype=np.float64).astype(np.uint32)
        order = np.argsort(t, kind="stable")
        assert np.all(np.diff(t[order].astype(np.int64)) > 0), user
        indices = [columns.index("label:" + label) for label in LABELS]
        x = a[order, 1:columns.index("label:LYING_DOWN")]
        y = a[order][:, indices]
        known = np.isfinite(y).any(axis=1)
        np.savez_compressed(f, t=t[order], x=x, y=np.nan_to_num(y).astype(np.uint8), known=known)
        print("parsed", user, len(t), flush=True)
    columns = json.loads((WORK / "columns.json").read_text())
    data = {user: dict(np.load(cache / f"{user}.npz")) for user in ids}
    xtrain = np.concatenate([data[u]["x"][data[u]["known"]] for u in split["train"]])
    ytrain = np.concatenate([data[u]["y"][data[u]["known"]] for u in split["train"]])
    with np.errstate(all="ignore"):
        median = np.nanmedian(xtrain, axis=0)
    median = np.nan_to_num(median)
    # Median imputation is fitted on training people only.
    np.copyto(xtrain, np.broadcast_to(median, xtrain.shape), where=~np.isfinite(xtrain))
    model = ExtraTreesClassifier(n_estimators=96, max_depth=24, min_samples_leaf=12,
                                 max_features=0.7, n_jobs=4, random_state=SEED)
    print("training", xtrain.shape, flush=True)
    begin = time.perf_counter()
    model.fit(xtrain, ytrain)
    elapsed = time.perf_counter() - begin
    idx = [columns.index(f) - 1 for f in FEATURES]
    quantiles = [np.unique(np.quantile(xtrain[:, k], np.linspace(0, 1, 255))) for k in idx]
    model_file = WORK / "frontend.pkl"
    with model_file.open("wb") as f:
        pickle.dump(dict(model=model, median=median, quantiles=quantiles, indices=idx), f)
    streams = WORK / "streams"
    streams.mkdir(exist_ok=True)
    quality, inventory = {}, []
    for user in ids:
        a = data[user]
        x = a["x"].copy()
        np.copyto(x, np.broadcast_to(median, x.shape), where=~np.isfinite(x))
        prob = np.column_stack([p[:, 1] if p.shape[1] > 1 else np.zeros(len(x)) for p in model.predict_proba(x)])
        numeric = np.column_stack([np.where(np.isfinite(a["x"][:, k]),
                                           np.searchsorted(cuts, a["x"][:, k]) / len(cuts), np.nan)
                                   for k, cuts in zip(idx, quantiles)])
        full = np.column_stack([prob, numeric]).astype(np.float32)
        np.savez_compressed(streams / f"{user}.npz", t=a["t"], q=quantize(full), full=full,
                            y=a["y"], known=a["known"])
        group = next(g for g, users in split.items() if user in users)
        if group != "train":
            ok = a["known"]
            quality[user] = {LABELS[j]: dict(positive_n=int(a["y"][ok, j].sum()),
                                           f1=float(f1_score(a["y"][ok, j], prob[ok, j] >= .5, zero_division=0)),
                                           ap=float(average_precision_score(a["y"][ok, j], prob[ok, j])) if a["y"][ok, j].any() else None)
                             for j in range(len(LABELS))}
        inventory.append(dict(user=user, split=group, observations=len(a["t"]),
                              elapsed_hours=float((int(a["t"][-1]) - int(a["t"][0])) / 3600),
                              gap_fraction=float(np.mean(np.diff(a["t"].astype(np.int64)) > 90))))
    prior = np.nanmean(np.concatenate([floats(np.load(streams / f"{u}.npz")["q"]) for u in split["train"]]), axis=0)
    dump(OUT / "frontend_quality.json", quality)
    dump(OUT / "inventory.json", inventory)
    dump(OUT / "frontend.json", dict(prior=prior.tolist(), labels=LABELS, numeric_features=FEATURES,
                                     train_rows=len(xtrain), train_seconds=elapsed, model_bytes=model_file.stat().st_size,
                                     model_sha256=sha(model_file)))
    dump(OUT / "manifest.json", dict(created_utc=utc(), source_url=URL, source_sha256=sha(archive),
                                    code_sha256=sha(__file__), protocol_sha256=sha(Path(__file__).with_name("PROTOCOL.md")),
                                    python=sys.version, numpy=np.__version__, sklearn=sklearn.__version__,
                                    platform=platform.platform(), seed=SEED, chunk=CHUNK, budgets=BUDGETS,
                                    source_feature_bytes="upstream feature extraction excluded; memory input 12 bytes/observation",
                                    archive_scope="Serialized retained state; runtime, model weights and decode workspace excluded"))
    print("prepared", len(ids), "streams; model seconds", elapsed, flush=True)


def configurations(stage):
    base = [(m, 1, .5) for m in METHODS if not m.startswith("hybrid")]
    if stage == "validation":
        return base + [(m, b, mix) for m in ["hybrid_reservoir", "hybrid_change", "hybrid_bundle"]
                       for b in [1, 2] for mix in ([0, .5, 1] if m != "hybrid_reservoir" else [.5])]
    chosen = json.loads((OUT / "selection.json").read_text())
    return base + [(m, cfg["base_bits"], cfg["mixing"]) for m, cfg in chosen["hybrids"].items()]


def run(stage):
    split = json.loads((OUT / "split.json").read_text())
    prior = json.loads((OUT / "frontend.json").read_text())["prior"]
    configs = configurations(stage)
    records = []
    qa_path = OUT / f"{stage}_answers.jsonl.gz"
    qa_file = gzip.open(qa_path, "wt", encoding="utf-8")
    for user_index, user in enumerate(split[stage]):
        source = np.load(WORK / "streams" / f"{user}.npz")
        t, q = source["t"], source["q"]
        qq = queries(len(t), SEED + user_index + (0 if stage == "validation" else 1000), validation=stage == "validation")
        reference = answers(floats(q), t, qq)
        unquantized = answers(source["full"], t, qq)
        dump(OUT / "questions" / f"{stage}_{user}.json", dict(queries=qq, reference=reference.tolist()))
        records.append(dict(user=user, method="quantization_floor", budget=0, seed=0, base_bits=8, mixing=0,
                            scores=scores(reference, unquantized, qq), archive_bytes=0))
        # Evaluate upstream recognition separately with the SAME question engine
        # over observed annotated sessions; labels never enter memory ingestion.
        known = source["known"]
        labeled_q = queries(int(known.sum()), SEED + user_index + 2000)
        labeled_q = [a for a in labeled_q if a["panel"] != "sensor_shift"]
        labels = np.column_stack([source["y"][known], np.zeros((known.sum(), 4))])
        label_answers = answers(labels, t[known], labeled_q)
        pred_answers = answers(floats(q[known]), t[known], labeled_q)
        records.append(dict(user=user, method="recognition_floor", budget=0, seed=0, base_bits=8, mixing=0,
                            scores=scores(pred_answers, label_answers, labeled_q), archive_bytes=0))
        for budget in BUDGETS:
            for method, bits, mixing in configs:
                seeds = [11, 23, 47] if method in SAMPLED else [0]
                for seed in seeds:
                    mem = Memory(method, budget, seed, bits, mixing)
                    begin = time.perf_counter()
                    try:
                        for a in range(0, len(q), CHUNK):
                            mem.ingest(t[a:a + CHUNK], q[a:a + CHUNK])
                        blob = mem.serialize()
                    except ValueError as exc:
                        records.append(dict(user=user, method=method, budget=budget, seed=seed, base_bits=bits,
                                            mixing=mixing, infeasible=str(exc)))
                        continue
                    ingestion = time.perf_counter() - begin
                    begin = time.perf_counter()
                    restored_t, restored, covered = decode(blob, prior)
                    assert np.array_equal(restored_t, t)
                    pred = answers(restored, restored_t, qq)
                    query_seconds = time.perf_counter() - begin
                    record = dict(user=user, method=method, budget=budget, seed=seed, base_bits=bits, mixing=mixing,
                                  scores=scores(pred, reference, qq), archive_bytes=len(blob), peak_archive_bytes=mem.peak,
                                  timeline_bytes=mem.timeline.size, coverage=float(covered.mean()),
                                  retained_records=len(mem.entries), segments=len(mem.segments),
                                  degraded_blocks=mem.degraded, dropped_blocks=mem.dropped,
                                  ingestion_seconds=ingestion, decode_and_query_seconds=query_seconds,
                                  operation_proxy=mem.operations, archive_sha256=hashlib.sha256(blob).hexdigest())
                    records.append(record)
                    if stage == "test":
                        name = f"{user}_{method}_{budget}_{seed}.bin"
                        path = OUT / "archives" / name
                        path.parent.mkdir(exist_ok=True)
                        path.write_bytes(blob)
                    qa_file.write(json.dumps(dict(user=user, method=method, budget=budget, seed=seed,
                                                  base_bits=bits, mixing=mixing, answers=pred.tolist())) + "\n")
        dump(OUT / f"{stage}_records.json", records)
        print(stage, user_index + 1, "/", len(split[stage]), user, len(q), "records", len(records), flush=True)
    qa_file.close()
    if stage == "validation":
        select(records)


def select(records):
    from collections import defaultdict
    grouped = defaultdict(list)
    for r in records:
        if "scores" in r and r["method"] not in {"quantization_floor", "recognition_floor"}:
            grouped[(r["method"], r["base_bits"], r["mixing"])].append(r["scores"]["familiar"]["nmae"])
    means = {key: float(np.mean(v)) for key, v in grouped.items()}
    hybrids = {}
    for method in ["hybrid_reservoir", "hybrid_change", "hybrid_bundle"]:
        key = min((k for k in means if k[0] == method), key=lambda k: means[k])
        hybrids[method] = dict(base_bits=key[1], mixing=key[2], validation_familiar_nmae=means[key])
    simple = [k for k in means if k[0] not in {"hybrid_change", "hybrid_bundle"}]
    best = min(simple, key=lambda k: means[k])
    candidates = [k for k in means if k[0] in {"hybrid_change", "hybrid_bundle"}]
    candidate = min(candidates, key=lambda k: means[k])
    by_budget = {}
    for budget in BUDGETS:
        candidates_at_budget = {}
        for key in simple:
            rows = [r["scores"]["familiar"]["nmae"] for r in records
                    if r.get("budget") == budget and "scores" in r
                    and (r["method"], r["base_bits"], r["mixing"]) == key]
            if rows:
                candidates_at_budget[key] = float(np.mean(rows))
        by_budget[budget] = min(candidates_at_budget, key=candidates_at_budget.get)[0]
    dump(OUT / "selection.json", dict(frozen_utc=utc(), code_sha256=sha(__file__),
                                      criterion="mean participant/budget familiar normalized absolute error; seeds averaged",
                                      hybrids=hybrids, strongest_simple=best[0],
                                      strongest_simple_by_budget=by_budget,
                                      selected_candidate=candidate[0],
                                      validation_scores={str(k): v for k, v in means.items()}))


def summarize():
    from collections import defaultdict
    records = json.loads((OUT / "test_records.json").read_text())
    groups = defaultdict(list)
    for r in records:
        if "scores" not in r:
            continue
        for panel, s in r["scores"].items():
            groups[(r["method"], r["budget"], panel, r["user"])].append(s)
    users = {}
    for key, rows in groups.items():
        users[key] = {metric: float(np.mean([r[metric] for r in rows if r[metric] is not None]))
                      for metric in ["exact", "positive_exact", "nmae", "zero_reference"]
                      if any(r[metric] is not None for r in rows)}
    cells = defaultdict(list)
    for (method, budget, panel, user), s in users.items():
        cells[(method, budget, panel)].append(s)
    summary = [dict(method=k[0], budget=k[1], panel=k[2], participants=len(v),
                    **{metric: float(np.mean([r[metric] for r in v if metric in r]))
                       for metric in ["exact", "positive_exact", "nmae", "zero_reference"]}) for k, v in cells.items()]
    dump(OUT / "summary.json", summary)
    selection = json.loads((OUT / "selection.json").read_text())
    baseline, candidate = selection["strongest_simple"], selection["selected_candidate"]
    rng = np.random.default_rng(SEED)
    paired = []
    for budget in BUDGETS:
        baseline = selection["strongest_simple_by_budget"][str(budget)]
        for panel in ["all", "familiar", "composition", "threshold_shift", "sensor_shift", "continuous_shift"]:
            uid = sorted({k[3] for k in users if k[:3] == (candidate, budget, panel)})
            for metric in ["exact", "positive_exact", "nmae"]:
                differences = np.asarray([users[(candidate, budget, panel, u)][metric] - users[(baseline, budget, panel, u)][metric]
                                          for u in uid if metric in users[(candidate, budget, panel, u)] and metric in users[(baseline, budget, panel, u)]])
                boots = differences[rng.integers(0, len(differences), size=(10000, len(differences)))].mean(axis=1)
                paired.append(dict(baseline=baseline, candidate=candidate, budget=budget, panel=panel, metric=metric,
                                   delta=float(differences.mean()), ci95=np.quantile(boots, [.025, .975]).tolist(),
                                   participant_deltas=differences.tolist()))
    dump(OUT / "paired.json", paired)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(13, 4), layout="constrained")
    display = ["reservoir", "adaptive_segments", "balanced_codec", "event1", "event2", "hybrid_reservoir", candidate]
    for ax, panel in zip(axes, ["familiar", "composition", "continuous_shift"]):
        for method in display:
            rows = sorted([r for r in summary if r["method"] == method and r["panel"] == panel], key=lambda r: r["budget"])
            ax.plot([r["budget"] / 1024 for r in rows], [r["exact"] * 100 for r in rows], marker="o", label=method)
        ax.set(xscale="log", xlabel="Archive cap (KiB/person)", ylabel="Exact answer agreement (%)", title=panel)
        ax.set_xticks([8, 16, 32, 64], labels=[8, 16, 32, 64])
        ax.grid(alpha=.25)
    axes[-1].legend(fontsize=7)
    fig.suptitle("ExtraSensory: agreement with full feature history; 12 unseen participants")
    fig.savefig(OUT / "frontier.png", dpi=170)
    plt.close(fig)
    dump(OUT / "completed.json", dict(completed_utc=utc(), code_sha256=sha(__file__),
                                      records=len(records), test_answers_sha256=sha(OUT / "test_answers.jsonl.gz"),
                                      questions_hidden_during_ingestion=True,
                                      fixed_chunk_input_bytes=CHUNK * (D + 4),
                                      query_source="seeded structured queries, not original SensorQA questions"))
    for budget in BUDGETS:
        print("BUDGET", budget)
        for method in display:
            r = next(r for r in summary if r["method"] == method and r["panel"] == "all" and r["budget"] == budget)
            print(method, "exact", round(r["exact"], 4), "nmae", round(r["nmae"], 4), "positive", round(r["positive_exact"], 4))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["prepare", "validate", "test", "summarize"], required=True)
    args = parser.parse_args()
    if args.stage == "prepare":
        prepare()
    elif args.stage == "validate":
        run("validation")
    elif args.stage == "test":
        run("test")
    else:
        summarize()
