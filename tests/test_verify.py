"""Cross-checks against independent implementations and published constants.

The metrics module and the hash are both places where a plausible-looking wrong
answer is easy to produce and hard to notice: an AUROC that mishandles ties, a
Brier score that silently became the top-label variant, an FNV implementation that
is really FNV-1 rather than FNV-1a. Each of those would quietly change a headline
number, so each is checked here against something that was not written for this
project.

sklearn is used only as a witness. It is not a dependency of the library, so these
checks skip rather than fail where it is unavailable (the device VM has no sklearn).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sysone.hashing import encode_corpus, fnv1a32, tokenize   # noqa: E402
from sysone.manifest import write_mem                         # noqa: E402
from sysone.metrics import auroc, brier, ece_equal_width, nll  # noqa: E402
from sysone.quant import RECIP_SHIFT, make_reciprocal_table    # noqa: E402

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'OK ' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAILURES.append(name)


def test_fnv_vectors() -> None:
    """Canonical FNV-1a/32 test vectors.

    The empty string pins the offset basis. The single characters pin the operation
    order: FNV-1 multiplies then XORs and FNV-1a XORs then multiplies, and the two
    differ from the very first byte, so "a", "b" and "c" alone are enough to
    distinguish them. "foobar" and the mixed-case pair pin multi-byte carry
    behaviour and confirm the hash is byte-sensitive, not case-folded, which
    matters because case folding happens in the tokenizer instead.
    """
    vectors = {b"": 0x811C9DC5, b"a": 0xE40C292C, b"b": 0xE70C2DE5,
               b"c": 0xE60C2C52, b"foobar": 0xBF9CF968,
               b"hello": 0x4F9F2CAB, b"Hello": 0xF55C314B}
    bad = [(k, hex(fnv1a32(k)), hex(v)) for k, v in vectors.items() if fnv1a32(k) != v]
    check("FNV-1a/32 matches published test vectors", not bad, str(bad) if bad else
          f"{len(vectors)} vectors, incl. FNV-1 vs FNV-1a discrimination")

    # Guard the whole reason this hash was chosen: it must be computable one byte
    # at a time, because the RTL sees a byte stream and has nowhere to buffer a
    # word. Incremental and whole-string hashing must agree.
    def incremental(data: bytes) -> int:
        h = 0x811C9DC5
        for b in data:
            h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
        return h
    probes = [b"balance", b"transfer_money", b"x" * 64, bytes(range(1, 200))]
    check("hash is computable byte-at-a-time (RTL streaming property)",
          all(incremental(p) == fnv1a32(p) for p in probes), f"{len(probes)} probes")


def test_tokenizer() -> None:
    cases = [
        ("Book me a FLIGHT to Paris!", [b"book", b"me", b"a", b"flight", b"to", b"paris"]),
        ("what's my 401k balance?", [b"what", b"s", b"my", b"401k", b"balance"]),
        ("   ", []),
        ("a,b;c", [b"a", b"b", b"c"]),
    ]
    bad = [(t, tokenize(t)) for t, want in cases if tokenize(t) != want]
    check("tokenizer: case fold, alnum runs, empty input", not bad, str(bad) if bad else "")

    # An input with no features must still yield exactly one row, or pooling
    # divides by zero on hardware with no way to signal it.
    flat, off = encode_corpus(["", "!!!", "ok"], 1024)
    check("degenerate inputs get exactly one feature",
          list(np.diff(off))[:2] == [1, 1], f"lengths={list(np.diff(off))}")


def test_reciprocal_table() -> None:
    t = make_reciprocal_table(64)
    worst, worst_n = 0.0, 0
    for n in range(1, 65):
        for s in (-8191, -137, -1, 0, 1, 137, 8191):
            exact = s / n
            got = (int(s) * int(t[n]) + (1 << (RECIP_SHIFT - 1))) >> RECIP_SHIFT
            if abs(got - exact) > worst:
                worst, worst_n = abs(got - exact), n
    check("Q16 reciprocal pooling within 1 LSB of true division",
          worst <= 1.0, f"max error {worst:.3f} LSB at n={worst_n}")


def test_metrics_vs_sklearn() -> None:
    try:
        from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
    except ImportError:
        print("[SKIP] sklearn not installed; metric cross-check skipped")
        return

    rng = np.random.default_rng(7)
    n, k = 4000, 12
    logits = rng.standard_normal((n, k)) * 2.0
    p = np.exp(logits - logits.max(1, keepdims=True))
    p /= p.sum(1, keepdims=True)
    y = rng.integers(0, k, n)

    check("NLL matches sklearn.log_loss",
          abs(nll(p, y) - log_loss(y, p, labels=list(range(k)))) < 1e-9,
          f"{nll(p, y):.10f}")

    onehot = np.zeros_like(p)
    onehot[np.arange(n), y] = 1.0
    sk_brier = sum(brier_score_loss((y == c).astype(int), p[:, c]) for c in range(k))
    check("Brier matches sum of per-class sklearn Brier",
          abs(brier(p, y) - sk_brier) < 1e-9, f"{brier(p, y):.10f} vs {sk_brier:.10f}")

    pos = rng.random(n) < 0.3
    scores = rng.standard_normal(n)
    check("AUROC matches sklearn.roc_auc_score",
          abs(auroc(scores, pos) - roc_auc_score(pos, scores)) < 1e-9,
          f"{auroc(scores, pos):.10f}")

    # Ties are the case a naive rank implementation gets wrong, so force many.
    tied = np.round(rng.standard_normal(n))
    check("AUROC matches sklearn with heavy ties",
          abs(auroc(tied, pos) - roc_auc_score(pos, tied)) < 1e-9,
          f"{int(len(np.unique(tied)))} distinct values over {n} points")


def test_ece_known_answer() -> None:
    """A hand-computable case, so the binning logic is checked against arithmetic
    rather than against itself."""
    # 100 points at confidence 0.9 that are 70% correct -> gap 0.20 in one bin.
    p = np.zeros((100, 2))
    p[:, 0] = 0.9
    p[:, 1] = 0.1
    y = np.zeros(100, dtype=int)
    y[70:] = 1                       # 70 correct, 30 wrong
    check("ECE on a hand-computed case", abs(ece_equal_width(p, y) - 0.20) < 1e-12,
          f"got {ece_equal_width(p, y):.6f}, expected 0.200000")

    # Perfectly calibrated two-bin case must give exactly 0.
    p2 = np.concatenate([np.full((100, 1), 1.0), np.zeros((100, 1))], axis=1)
    y2 = np.zeros(100, dtype=int)
    check("ECE is 0 for a perfectly calibrated set", ece_equal_width(p2, y2) == 0.0)


def test_mem_roundtrip() -> None:
    """Exported hex must read back as the same signed integers."""
    import tempfile
    rng = np.random.default_rng(1)
    for bits, lo, hi in ((8, -127, 127), (4, -7, 7), (2, -1, 1), (32, -2**20, 2**20)):
        a = rng.integers(lo, hi + 1, size=(37, 11)).astype(np.int64)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.mem"
            write_mem(a, p, bits)
            width = max(bits, 2)
            vals = [int(line, 16) for line in p.read_text().split()]
            signed = np.array([v - (1 << width) if v >= (1 << (width - 1)) else v
                               for v in vals]).reshape(a.shape)
        check(f".mem round-trip at {bits}-bit", np.array_equal(signed, a))


def test_export_manifest_detects_tampering() -> None:
    """A manifest that does not notice a changed byte is worse than no manifest."""
    from sysone.manifest import verify
    d = ROOT / "export" / "student_bram_int4"
    if not (d / "manifest.json").exists():
        print("[SKIP] no export found; run scripts/train_student.py first")
        return
    ok, problems = verify(d)
    check("exported manifest verifies clean", ok, str(problems) if problems else "")

    import shutil, tempfile
    with tempfile.TemporaryDirectory() as tmp:
        c = Path(tmp) / "e"
        shutil.copytree(d, c)
        text = (c / "W1q.mem").read_text().split("\n")
        text[0] = "7f" if text[0] != "7f" else "01"     # flip one word
        (c / "W1q.mem").write_text("\n".join(text))
        ok2, problems2 = verify(c)
        check("manifest catches a single flipped .mem word", not ok2,
              f"reported: {problems2}")


def main() -> int:
    test_fnv_vectors()
    test_tokenizer()
    test_reciprocal_table()
    test_metrics_vs_sklearn()
    test_ece_known_answer()
    test_mem_roundtrip()
    test_export_manifest_detects_tampering()
    print("\nRESULT:", "all checks passed" if not FAILURES else f"FAILED: {FAILURES}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
