"""Byte-level FNV-1a feature hashing.

This module is the software half of a contract with RTL. Every operation here is
chosen so that it can be reproduced exactly by a small state machine on the FPGA
that consumes UTF-8 bytes from the link:

  * normalisation is a byte-wise map (ASCII upper -> lower), no Unicode tables;
  * a token boundary is "byte is not in [a-z0-9]", testable with two comparators;
  * the hash is FNV-1a/32, which is one XOR and one 32-bit multiply per byte;
  * the table index is ``hash & (V - 1)`` with V a power of two, so no divider.

Nothing here allocates per-token strings on the hardware side: the RTL updates a
32-bit register per byte and emits an index at each boundary. The Python below
does allocate, because it is the reference, not the implementation.
"""

from __future__ import annotations

import numpy as np

FNV_OFFSET_32 = 0x811C9DC5
FNV_PRIME_32 = 0x01000193
MASK32 = 0xFFFFFFFF

# Marker mixed into a bigram hash so that the bigram ("book", "flight") cannot
# collide systematically with a unigram that happens to hash the same way.
BIGRAM_SALT = 0x9E3779B9
TRIGRAM_SALT = 0x85EBCA6B
CHAR_SALT = 0xC2B2AE35

# Word-boundary markers, fastText convention. Without them "ban" as a whole word
# and "ban" inside "banking" hash to the same feature, which is exactly the
# distinction character n-grams exist to make.
WORD_START = 0x3C   # '<'
WORD_END = 0x3E     # '>'


def fnv1a32(data: bytes) -> int:
    """FNV-1a, 32-bit. One XOR + one multiply per byte."""
    h = FNV_OFFSET_32
    for b in data:
        h ^= b
        h = (h * FNV_PRIME_32) & MASK32
    return h


def _is_word_byte(b: int) -> bool:
    return (0x61 <= b <= 0x7A) or (0x30 <= b <= 0x39)


def _fold_case(b: int) -> int:
    """ASCII upper -> lower. Bytes >= 0x80 pass through unchanged."""
    return b + 32 if 0x41 <= b <= 0x5A else b


def tokenize(text: str) -> list[bytes]:
    """Split into byte tokens exactly the way the RTL boundary detector will.

    Case-folded ASCII alphanumeric runs. Everything else -- spaces, punctuation,
    and any byte of a multi-byte UTF-8 sequence -- is a separator. Dropping
    non-ASCII is a real limitation and is recorded as such: CLINC150 is English
    and effectively pure ASCII, but a multilingual port would need the boundary
    rule widened to "byte >= 0x80 continues the current token".
    """
    tokens: list[bytes] = []
    cur = bytearray()
    for raw in text.encode("utf-8", errors="ignore"):
        b = _fold_case(raw)
        if _is_word_byte(b):
            cur.append(b)
        elif cur:
            tokens.append(bytes(cur))
            cur = bytearray()
    if cur:
        tokens.append(bytes(cur))
    return tokens


def _mix(a: int, b: int, salt: int) -> int:
    """Combine two hashes into one. Two multiplies, two XORs -- RTL-cheap."""
    m = ((a ^ salt) * FNV_PRIME_32) & MASK32
    return ((m ^ b) * FNV_PRIME_32) & MASK32


def char_ngram_hashes(word: bytes, lo: int, hi: int) -> list[int]:
    """Hashes of the character n-grams of one word, with boundary markers.

    On hardware this is cheaper than it looks: the n-grams of a word are a sliding
    window over the same byte stream the word hash already walks, so an RTL unit
    can maintain (hi - lo + 1) rolling FNV registers alongside the word register
    and emit them at each step. No extra memory traffic, only extra lanes.

    The reason to want them at all is out-of-vocabulary words. 39.8% of the
    distinct words in the CLINC150 test set never appear in training, and a word
    hash gives those a randomly-initialised row -- pure noise. Character n-grams
    give them a representation assembled from fragments the model has seen, so
    "rescheduling" can borrow from "schedule".
    """
    padded = bytes([WORD_START]) + word + bytes([WORD_END])
    out: list[int] = []
    for n in range(lo, hi + 1):
        if len(padded) < n:
            continue
        for i in range(len(padded) - n + 1):
            out.append(_mix(fnv1a32(padded[i:i + n]), n, CHAR_SALT))
    return out


def hash_features(
    text: str,
    n_buckets: int,
    use_bigrams: bool = True,
    max_tokens: int = 64,
    use_trigrams: bool = False,
    char_ngrams: tuple[int, int] | None = None,
) -> np.ndarray:
    """Return the embedding-table row indices for one input.

    ``n_buckets`` must be a power of two so the index is a bit-mask on hardware.
    Duplicate indices are kept, not deduplicated: the pooling stage averages over
    occurrences, so a word repeated twice should count twice, and dedup would cost
    the RTL a set membership test it cannot afford.

    ``max_tokens`` bounds the DDR2 read burst per input. It is a hardware budget,
    not a modelling choice, so truncation is silent and deterministic (keep the
    first ``max_tokens`` features) rather than random.
    """
    if n_buckets & (n_buckets - 1):
        raise ValueError(f"n_buckets must be a power of two, got {n_buckets}")
    mask = n_buckets - 1

    words = tokenize(text)
    hashes = [fnv1a32(w) for w in words]
    idx = [h & mask for h in hashes]

    if use_bigrams:
        for a, b in zip(hashes, hashes[1:]):
            idx.append(_mix(a, b, BIGRAM_SALT) & mask)

    if use_trigrams:
        for a, b, c in zip(hashes, hashes[1:], hashes[2:]):
            idx.append(_mix(_mix(a, b, TRIGRAM_SALT), c, TRIGRAM_SALT) & mask)

    if char_ngrams is not None:
        lo, hi = char_ngrams
        for w in words:
            idx.extend(h & mask for h in char_ngram_hashes(w, lo, hi))

    if len(idx) > max_tokens:
        idx = idx[:max_tokens]
    return np.asarray(idx, dtype=np.int32)


def encode_corpus(
    texts: list[str],
    n_buckets: int,
    use_bigrams: bool = True,
    max_tokens: int = 64,
    use_trigrams: bool = False,
    char_ngrams: tuple[int, int] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Encode a corpus into CSR-style (flat_indices, offsets).

    ``offsets`` has length ``len(texts) + 1``; row i occupies
    ``flat[offsets[i]:offsets[i + 1]]``. This is the same shape the RTL sees:
    a contiguous index stream plus per-input lengths.

    An input that produces no features at all (empty string, punctuation only)
    gets a single index 0 so that downstream pooling never divides by zero. That
    is a deliberate, documented degenerate case rather than an exception, because
    the hardware path has no way to signal an error mid-stream.
    """
    flat: list[int] = []
    offsets = np.zeros(len(texts) + 1, dtype=np.int64)
    for i, t in enumerate(texts):
        idx = hash_features(t, n_buckets, use_bigrams, max_tokens,
                            use_trigrams, char_ngrams)
        if idx.size == 0:
            idx = np.zeros(1, dtype=np.int32)
        flat.extend(int(x) for x in idx)
        offsets[i + 1] = len(flat)
    return np.asarray(flat, dtype=np.int32), offsets


def collision_stats(texts: list[str], n_buckets: int, use_bigrams: bool = True) -> dict:
    """How badly the table is overloaded at this size.

    Reported because hashing collisions, not quantisation, are the first thing to
    blame when a small table loses accuracy, and the two are easy to confuse.
    """
    distinct: dict[int, set[bytes]] = {}
    total = 0
    for t in texts:
        words = tokenize(t)
        for w in words:
            b = fnv1a32(w) & (n_buckets - 1)
            distinct.setdefault(b, set()).add(w)
            total += 1
    n_types = sum(len(v) for v in distinct.values())
    colliding = sum(len(v) for v in distinct.values() if len(v) > 1)
    return {
        "n_buckets": n_buckets,
        "distinct_word_types": n_types,
        "buckets_used": len(distinct),
        "load_factor": n_types / n_buckets,
        "types_in_colliding_buckets": colliding,
        "collision_rate": colliding / max(n_types, 1),
        "token_occurrences": total,
    }
