"""Latency of one v2 encoder pass, per board, per model, per chained length.

    python scripts/v2/chain_hw_estimate.py

The v2 design streams INT8 weights from external memory once per pass and applies
each weight tile to every token of the chain while it is on chip. So a pass costs

    max(weight bytes / memory bandwidth,  MACs / (DSPs * efficiency * clock))

and the MAC count grows linearly with the number of tokens (plus a small quadratic
attention term), while the weight traffic does not grow at all.

What that means differs by board. With only ~200 usable DSPs, the Nexys 4 DDR is
compute-bound at every length: one chained pass costs about what the same sentences
cost one pass each, so there the gain from chaining is accuracy (context), not time.
On the KR260 and larger parts, short passes are memory-bound, so up to the
crossover (~32-64 tokens) extra chained segments are nearly free.

Board numbers are first-order and stated so they can be argued with:
  nexys4ddr  XC7A100T: 240 DSP48E1; MIG DDR2 16-bit 600 MT/s = 1.2 GB/s peak, 80%
             sustained in simulation of mig_memory_port with 20% random stalls; the
             MAC array is assumed to run at 100 MHz with 200 DSPs, 75% efficient
  kr260      K26 (XCK26): 1,248 DSP48E2; PS DDR4 64-bit 2400 MT/s = 19.2 GB/s, ~10 GB/s
             through the PL HP ports; 1,000 DSPs at 250 MHz, 75%; INT8 packing (two
             MACs per DSP48E2) is NOT assumed
  zu9eg      ZCU102-class: 2,520 DSP48E2, same PS DDR4; 2,000 DSPs at 300 MHz
Softmax, GELU, LayerNorm and the heads are O(tokens x hidden) and assumed to overlap
with the matrix work on small dedicated units.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

MODELS = {            # layers, hidden, ffn
    "bert-mini (4x256)":   (4, 256, 1024),
    "minilm-l6 (6x384)":   (6, 384, 1536),
    "bert-small (4x512)":  (4, 512, 2048),
    "bert-medium (8x512)": (8, 512, 2048),
    "bert-base (12x768)":  (12, 768, 3072),
}
BOARDS = {           # bandwidth B/s, DSPs used, clock Hz, efficiency
    "nexys4ddr": (1.2e9 * 0.8, 200, 100e6, 0.75),
    "kr260":     (10e9, 1000, 250e6, 0.75),
    "zu9eg":     (10e9, 2000, 300e6, 0.75),
}
LENGTHS = (16, 64, 128, 256)


def cost(model: tuple, tokens: int) -> tuple[float, float]:
    L, H, F = model
    weights = L * (4 * H * H + 2 * H * F)                 # INT8 bytes
    macs = tokens * weights + L * 2 * tokens * tokens * H
    return weights, macs


def main() -> None:
    rows = []
    print(f"{'model':22s} {'board':10s} " + " ".join(f"{'L=' + str(n):>16s}" for n in LENGTHS))
    for mname, m in MODELS.items():
        for bname, (bw, dsp, clk, eff) in BOARDS.items():
            cells = []
            for n in LENGTHS:
                w, macs = cost(m, n)
                t_mem = w / bw
                t_cmp = macs / (dsp * clk * eff)
                t = max(t_mem, t_cmp)
                rows.append({"model": mname, "board": bname, "tokens": n, "weight_bytes": w,
                             "macs": macs, "memory_ms": t_mem * 1e3, "compute_ms": t_cmp * 1e3,
                             "ms": t * 1e3, "bound": "memory" if t_mem > t_cmp else "compute"})
                cells.append(f"{t * 1e3:8.1f}ms {'mem' if t_mem > t_cmp else 'cmp'}")
            print(f"{mname:22s} {bname:10s} " + " ".join(f"{c:>16s}" for c in cells))
    out = ROOT / "results" / "v2" / "chain_hw_estimate.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2))

    print("\nchaining: 8 sentences of 16 tokens, one pass of 128 vs eight passes of 16")
    for mname in ("bert-mini (4x256)", "minilm-l6 (6x384)"):
        for bname, (bw, dsp, clk, eff) in BOARDS.items():
            def t(n):
                w, macs = cost(MODELS[mname], n)
                return max(w / bw, macs / (dsp * clk * eff))
            print(f"  {mname:20s} {bname:10s} chained {t(128) * 1e3:7.1f} ms   "
                  f"separate {8 * t(16) * 1e3:7.1f} ms")


if __name__ == "__main__":
    main()
