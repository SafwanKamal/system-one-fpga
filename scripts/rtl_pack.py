"""Pack an exported model for the RTL and write bit-exact test vectors.

Phase 1 exported one value per line and deliberately left packing order to the
RTL. This script is where that decision is made, and it is the only place.
Memories go to memory/, named the way Genome-Classifier names its files:

  * ``embedding_low.mem``   4096 x 1008 bits -- dims 0..62 of rows r, r+4096,
      r+8192, r+12288 on line r, row r in the MSBs; within a row dim d is in
      bits [4d+3:4d]. 4096 deep so Vivado maps it onto 112 RAMB36; 16384 x 252
      went to 16K x 2 mode and 126.
  * ``embedding_high.mem``  16384 x 4 bits   -- dim 63 (2 RAMB36, 114 in total)
  * ``dense_hidden_weights.mem``  256 x 512 bits -- dense_engine layout: word
      (group * 64 + input), lane 0 in the MSBs (export_fpga.pack_lanes order)
  * ``dense_output_weights.mem``  768 x 512 bits -- same layout, lanes past class
      150 are zero
  * ``dense_hidden_biases.mem`` / ``dense_output_biases.mem`` -- all zero: this
      model adds its bias after the requant multiplier, not in the accumulator
  * ``requant_{hidden,output}_{multipliers,biases}.mem``, ``pool_reciprocals.mem``
      -- 32-bit two's complement, one per line

It also writes ``rtl/model_parameters.svh`` (MODEL_* localparams, the same
convention as Genome-Classifier's export_fpga), which the testbench includes and
passes to sysone_core.

Vectors (``--vectors``) go to simulation/vectors/: the CLINC150 test set plus edge
cases chosen to hit every branch of the feature generator: empty input,
punctuation only, upper case, non-ASCII bytes, one-letter words, feature-count
truncation at 256, more than 256 words, and a single word longer than any in the
corpus.

Every logit is recomputed here from ``model.npz`` with ``QuantModel.forward_int``,
the same code path Phase 1 validated against the scalar reference, and the
in-scope accuracy is checked against the manifest before anything is written.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sysone.deployed import DEPLOYED_EXPORT  # noqa: E402
from sysone.data import load_clinc150                         # noqa: E402
from sysone.hashing import encode_corpus                       # noqa: E402
from sysone.manifest import verify                             # noqa: E402
from sysone.quant import MULT_SHIFT, RECIP_SHIFT, QuantConfig, QuantModel  # noqa: E402

LANES = 64
MSG_BYTES = 2048          # RTL message buffer; must match sysone_core.MSG_BYTES
EOM = 0x100               # end-of-message marker in the byte-stream vector file

EDGE_CASES = [
    "",
    "?!... ,,, --",
    "WHAT IS MY Credit Score",
    "café crème brûlée naïve",
    "a b c d e f g",
    "x",
    "I",
    "12 34 567 8",
    "supercalifragilisticexpialidociousantidisestablishmentarianism",
    " ".join(["transfer money from checking to savings please"] * 12),   # > 256 feats
    " ".join(f"w{i}" for i in range(300)),                               # > 256 words
    " ".join(f"tok{i}" for i in range(90)),                              # tri spills
    "a" * 400,                                                           # one long word
    "  leading and trailing spaces   ",
    "tab\tand\nnewline\rseparators",
]


def load_qm(export_dir: Path) -> tuple[QuantModel, dict]:
    man = json.loads((export_dir / "manifest.json").read_text())
    z = np.load(export_dir / "model.npz")
    q = man["quant"]
    a = man["arithmetic"]
    assert a["recip_shift"] == RECIP_SHIFT and a["mult_shift"] == MULT_SHIFT
    cfg = QuantConfig(**q)
    qm = QuantModel(cfg=cfg, Eq=z["Eq"], W1q=z["W1q"], W2q=z["W2q"],
                    M1=z["M1"], B1=z["B1"], M2=z["M2"], B2=z["B2"], recip=z["recip"],
                    pool_gain=a["pool_gain"], s_out=a["s_out"], act_qmax=a["act_qmax"],
                    logit_qmax=a["logit_qmax"], max_tokens=a["max_tokens"])
    return qm, man


def hexw(v: int, bits: int) -> str:
    return f"{int(v) % (1 << bits):0{(bits + 3) // 4}x}"


def pack_lanes(vals: np.ndarray, bits: int) -> str:
    """vals[0] in the least significant bits."""
    acc = 0
    for j, v in enumerate(vals):
        acc |= (int(v) % (1 << bits)) << (bits * j)
    return hexw(acc, bits * len(vals))


def check_widths(qm: QuantModel) -> dict:
    """The RTL has fixed register widths. Refuse to pack a model that does not fit."""
    D, H = qm.W1q.shape
    K = qm.W2q.shape[1]
    lim = {
        "Eq in [-7,7]": int(np.abs(qm.Eq).max()) <= 7,
        "W1q, W2q in [-127,127]": max(int(np.abs(qm.W1q).max()), int(np.abs(qm.W2q).max())) <= 127,
        "M1 < 2^17": 0 <= int(qm.M1.min()) and int(qm.M1.max()) < (1 << 17),
        "M2 < 2^17": 0 <= int(qm.M2.min()) and int(qm.M2.max()) < (1 << 17),
        "|B1| < 2^31": int(np.abs(qm.B1).max()) < (1 << 31),
        "|B2| < 2^31": int(np.abs(qm.B2).max()) < (1 << 31),
        "max_tokens == 256": qm.max_tokens == 256,
        # embedding_bag's 10-bit pooled output holds 7 * 2^POOL_GAIN + 1
        "pool_gain <= 6": qm.pool_gain <= 6,
        "shape 16384x64x256x151": (qm.Eq.shape[0], D, H, K) == (16384, 64, 256, 151),
        "act_qmax 127, logit_qmax 32767": (qm.act_qmax, qm.logit_qmax) == (127, 32767),
    }
    bad = [k for k, ok in lim.items() if not ok]
    if bad:
        raise SystemExit(f"model does not fit the RTL widths: {bad}")
    return lim


ACC_WIDTH = 25   # dense_engine accumulator width used by classifier_head


def write_mems(qm: QuantModel, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    Eq = qm.Eq.astype(np.int64)
    with open(out / "embedding_low.mem", "w") as flo, open(out / "embedding_high.mem", "w") as fhi:
        banks = 4
        bank_rows = Eq.shape[0] // banks
        for r in range(bank_rows):
            flo.write("".join(pack_lanes(Eq[b * bank_rows + r, :63], 4)
                              for b in range(banks)) + "\n")
        for r in range(Eq.shape[0]):
            fhi.write(hexw(Eq[r, 63], 4) + "\n")

    def pack_msb_first(vals, bits):
        return pack_lanes(np.asarray(vals)[::-1], bits)

    D, H = qm.W1q.shape
    K = qm.W2q.shape[1]
    groups1 = H // LANES
    groups2 = -(-K // LANES)
    W2p = np.zeros((H, groups2 * LANES), dtype=np.int64)
    W2p[:, :K] = qm.W2q

    with open(out / "dense_hidden_weights.mem", "w") as f:
        for g in range(groups1):
            for d in range(D):
                f.write(pack_msb_first(qm.W1q[d, g * LANES:(g + 1) * LANES], 8) + "\n")
    with open(out / "dense_output_weights.mem", "w") as f:
        for g in range(groups2):
            for i in range(H):
                f.write(pack_msb_first(W2p[i, g * LANES:(g + 1) * LANES], 8) + "\n")

    zero_word = "0" * (LANES * ACC_WIDTH // 4)
    (out / "dense_hidden_biases.mem").write_text((zero_word + "\n") * groups1)
    (out / "dense_output_biases.mem").write_text((zero_word + "\n") * groups2)

    names = {"M1": "requant_hidden_multipliers", "B1": "requant_hidden_biases",
             "M2": "requant_output_multipliers", "B2": "requant_output_biases",
             "recip": "pool_reciprocals"}
    for attr, name in names.items():
        with open(out / f"{name}.mem", "w") as f:
            for v in getattr(qm, attr):
                f.write(hexw(v, 32) + "\n")


def write_parameters(qm: QuantModel, path: Path, npz_sha: str) -> None:
    """MODEL_* constants for the testbench and board top, taken from the model."""
    D, H = qm.W1q.shape
    path.write_text(
        "// Generated by scripts/rtl_pack.py from the export manifest; do not edit manually.\n"
        f"// model.npz sha256 {npz_sha}\n"
        "`ifndef SYSONE_MODEL_PARAMETERS_SVH\n"
        "`define SYSONE_MODEL_PARAMETERS_SVH\n\n"
        f"localparam integer MODEL_ROW_NUMBER       = {qm.Eq.shape[0]};\n"
        f"localparam integer MODEL_DIMENSION        = {D};\n"
        f"localparam integer MODEL_HIDDEN           = {H};\n"
        f"localparam integer MODEL_CLASS_NUMBER     = {qm.W2q.shape[1]};\n"
        f"localparam integer MODEL_MAXIMUM_FEATURES = {qm.max_tokens};\n"
        f"localparam integer MODEL_POOL_GAIN        = {qm.pool_gain};\n"
        f"localparam integer MODEL_MULTIPLIER_SHIFT = {MULT_SHIFT};\n\n"
        "`endif\n")


def write_vectors(qm: QuantModel, man: dict, texts: list[str], out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    m = man["model"]
    flat, offs = encode_corpus(texts, m["n_buckets"], m["use_bigrams"], m["max_tokens"],
                               m["use_trigrams"], tuple(m["char_ngrams"]))
    logits = qm.forward_int(flat, offs)

    n_bytes = 0
    with open(out / "bytes.hex", "w") as f:
        for t in texts:
            b = t.encode("utf-8")
            assert len(b) <= MSG_BYTES, "vector longer than the RTL message buffer"
            for x in b:
                f.write(f"{x:03x}\n")
            f.write(f"{EOM:03x}\n")
            n_bytes += len(b) + 1
    with open(out / "idx.hex", "w") as f:
        for i in range(len(texts)):
            seg = flat[offs[i]:offs[i + 1]]
            f.write(f"{len(seg):04x}\n")
            for v in seg:
                f.write(f"{int(v):04x}\n")
    with open(out / "logits.hex", "w") as f:
        for row in logits:
            for v in row:
                f.write(hexw(v, 16) + "\n")
    with open(out / "argmax.hex", "w") as f:
        for row in logits:
            f.write(f"{int(np.argmax(row)):02x}\n")
    info = {"n_msgs": len(texts), "n_byte_words": n_bytes, "n_idx_words": int(len(flat) + len(texts)),
            "n_logits": int(logits.size), "n_classes": int(logits.shape[1])}
    (out / "vectors.json").write_text(json.dumps(info, indent=2))
    return {"info": info, "logits": logits}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", default=str(DEPLOYED_EXPORT))
    ap.add_argument("--mem-out", default=str(ROOT / "memory"))
    ap.add_argument("--vec-out", default=str(ROOT / "simulation/vectors"))
    ap.add_argument("--vectors", action="store_true", help="also write test vectors")
    ap.add_argument("--limit", type=int, default=0, help="only the first N test messages")
    args = ap.parse_args()

    exp = Path(args.export)
    ok, problems = verify(exp)
    if not ok:
        raise SystemExit(f"manifest verification failed: {problems}")
    qm, man = load_qm(exp)
    check_widths(qm)
    write_mems(qm, Path(args.mem_out))
    write_parameters(qm, ROOT / "rtl" / "model_parameters.svh", man["npz_sha256"])
    print(f"packed memories -> {args.mem_out}")

    if args.vectors:
        ds = load_clinc150()
        m = man["model"]
        flat, offs = encode_corpus(ds.test.texts, m["n_buckets"], m["use_bigrams"],
                                   m["max_tokens"], m["use_trigrams"], tuple(m["char_ngrams"]))
        pred = qm.forward_int(flat, offs).argmax(1)
        ins = ~ds.test.is_oos
        acc = float((pred[ins] == ds.test.y[ins]).mean())
        want = man["golden_metrics"]["integer"]["in_scope_accuracy"]
        print(f"golden in-scope accuracy {acc:.4f} (manifest {want:.4f})")
        if abs(acc - want) > 1e-9:
            raise SystemExit("golden model does not reproduce the manifest metrics")
        texts = list(ds.test.texts)
        if args.limit:
            texts = texts[:args.limit]
        texts = EDGE_CASES + texts
        r = write_vectors(qm, man, texts, Path(args.vec_out))
        np.save(Path(args.vec_out) / "labels.npy",
                np.concatenate([np.full(len(EDGE_CASES), -1), ds.test.y[:len(texts) - len(EDGE_CASES)]]))
        print(f"vectors -> {args.vec_out}: {r['info']}")


if __name__ == "__main__":
    main()
