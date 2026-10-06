"""Put pretrained word knowledge into the hashed embedding table.

The board's table is 16384 rows of 64 INT4 values, indexed by FNV hashes of words,
word n-grams and character 3-5 grams. Trained only on CLINC150 (about 100
sentences per intent), every row learns from a handful of examples, and a word the
training set never used gets a row that is noise or, at best, assembled from
character fragments of other words.

This module fills the table from pretrained word vectors before any CLINC150
training, fastText style: for each word w in a large vocabulary, the mean of the
rows w maps to (its unigram row plus its character n-gram rows, exactly as
``hash_features`` produces them for a one-word input) is regressed onto a 64-d
projection of w's pretrained vector. Afterwards

  * a word seen in pretraining has a meaningful row whether or not CLINC150 uses it,
  * the character n-gram rows encode sub-word meaning, so an unseen or misspelled
    word is assembled from fragments that mean something, and
  * the table, the hashing, the RTL and the bitstream structure are unchanged.
    Only the contents of embedding_low.mem / embedding_high.mem change.

Word bigram and trigram rows get no pretraining signal (there is no phrase
vocabulary in the source vectors) and keep their small random init.

The source vectors here are GloVe / fastText from the gensim-data GitHub releases,
because that is what this environment can reach; the code takes any word2vec-format
text file.
"""

from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np

from .hashing import encode_corpus, tokenize


def load_word2vec_text(path: Path | str, max_words: int,
                       keep: set[str] | None = None) -> tuple[list[str], np.ndarray]:
    """First ``max_words`` usable words of a word2vec-format text file (.gz ok).

    Files are frequency ordered, so the head of the file is the common vocabulary.
    A word is usable if the board's tokenizer would see it as exactly one token
    (lower-case ASCII letters and digits); anything else could never be looked up.
    Words in ``keep`` are taken even past ``max_words`` so that every word the
    task uses gets its vector when the file has one.
    """
    opener = gzip.open if str(path).endswith(".gz") else open
    words, vecs = [], []
    seen = set()
    with opener(path, "rt", encoding="utf-8", errors="ignore") as f:
        header = f.readline().split()
        dim = int(header[1])
        for line in f:
            w, _, rest = line.partition(" ")
            if len(words) >= max_words and (keep is None or w not in keep):
                continue
            if w in seen:
                continue
            if tokenize(w) != [w.encode()]:
                continue
            v = np.asarray(rest.split(), dtype=np.float32)
            if v.shape[0] != dim:
                continue
            words.append(w)
            vecs.append(v)
            seen.add(w)
            if keep is not None and len(words) >= max_words and keep <= seen:
                break
    return words, np.stack(vecs)


def project(vecs: np.ndarray, dim: int, scale: float) -> tuple[np.ndarray, dict]:
    """Centre, PCA to ``dim``, and scale so the targets have RMS ``scale``.

    PCA keeps the directions with the most variance in the pretrained space; the
    first component of raw GloVe is mostly word frequency, which is why centring
    comes first.
    """
    mu = vecs.mean(0)
    X = vecs - mu
    _, s, Vt = np.linalg.svd(X, full_matrices=False)
    P = Vt[:dim].T
    Y = X @ P
    rms = float(np.sqrt((Y ** 2).mean()))
    Y *= scale / rms
    kept = float((s[:dim] ** 2).sum() / (s ** 2).sum())
    return Y.astype(np.float32), {"variance_kept": kept}


def pretrain_table(words: list[str], targets: np.ndarray, n_buckets: int,
                   use_trigrams: bool, char_ngrams: tuple[int, int] | None,
                   max_tokens: int, seed: int = 0, epochs: int = 8,
                   batch: int = 1024, lr: float = 5e-3,
                   weights: np.ndarray | None = None,
                   init_scale: float = 0.05, verbose: bool = True) -> tuple[np.ndarray, dict]:
    """Regress mean(E[features(w)]) onto targets[w] with sparse Adam.

    Features of a one-word input are its unigram row and its character n-gram
    rows; bigrams and trigrams need two words, so they do not occur. Returns the
    table and the final fit (cosine between reconstruction and target).
    """
    rng = np.random.default_rng(seed)
    dim = targets.shape[1]
    E = (rng.standard_normal((n_buckets, dim)) * init_scale).astype(np.float32)
    flat, offs = encode_corpus(words, n_buckets, True, max_tokens, use_trigrams, char_ngrams)
    lens = np.diff(offs).astype(np.int64)
    w = np.ones(len(words), np.float32) if weights is None else weights.astype(np.float32)
    w = w / w.mean()
    mE = np.zeros_like(E)
    vE = np.zeros_like(E)
    t = 0
    b1, b2, eps = 0.9, 0.999, 1e-8
    n = len(words)

    def fit_cos() -> float:
        pred = np.add.reduceat(E[flat], offs[:-1], axis=0) / lens[:, None]
        num = (pred * targets).sum(1)
        den = np.linalg.norm(pred, axis=1) * np.linalg.norm(targets, axis=1) + 1e-9
        return float(np.average(num / den, weights=w))

    for ep in range(epochs):
        order = rng.permutation(n)
        for s in range(0, n, batch):
            idx = order[s:s + batch]
            take = np.concatenate([np.arange(offs[i], offs[i + 1]) for i in idx])
            bl = lens[idx]
            bo = np.zeros(len(idx) + 1, np.int64)
            np.cumsum(bl, out=bo[1:])
            rows = flat[take]
            pred = np.add.reduceat(E[rows], bo[:-1], axis=0) / bl[:, None]
            g = 2.0 * (pred - targets[idx]) * (w[idx] / len(idx))[:, None]
            per = np.repeat(g / bl[:, None], bl, axis=0)
            uniq, inv = np.unique(rows, return_inverse=True)
            acc = np.zeros((len(uniq), dim), np.float32)
            np.add.at(acc, inv, per)
            t += 1
            m = b1 * mE[uniq] + (1 - b1) * acc
            v = b2 * vE[uniq] + (1 - b2) * acc * acc
            mE[uniq], vE[uniq] = m, v
            E[uniq] -= lr * (m / (1 - b1 ** t)) / (np.sqrt(v / (1 - b2 ** t)) + eps)
        if verbose:
            print(f"  pretrain epoch {ep}: weighted cosine fit {fit_cos():.4f}", flush=True)
    return E, {"cosine_fit": fit_cos(), "n_words": n,
               "rows_touched": int(len(np.unique(flat)))}
