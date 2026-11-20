# Dual weight port on v9g: exact design, measured cost, and why it does not fit yet (2026-11-19)

## Summary

- **Decode is bandwidth-bound.** Streaming the 28 layers and the vocabulary head takes
  158 ms of every 174 ms decode step. A second weight port is the largest remaining lossless
  lever. It is modelled to take speculative decode with the new drafter
  (`2026-11-19-cost-aware-drafting.md`) from 2.58x to **3.58x** plain v9g, before prefill
  gains.
- **The design is bit-exact by construction and synthesizes at II=1.** HLS reports the same
  four II warnings as v9g, all in pre-existing loops.
- **It does not fit next to P=4.** It adds about 27k LUT routed. v9g already sits at 83.5% LUT
  and 99.3% CLB, so roughly 20k LUT must be reclaimed first.
- **Two reclaim techniques were measured:**
  - an exact slot-pair DSP packing of the INT8 products;
  - a single shared RMS-norm instance.

  Together they recover about 12k LUT (HLS), not enough on their own. Attention, at 36.5k
  LUT routed, is the remaining large target.

## Where the LUTs go in v9g (routed, `build/v2/dual-port-study/v9g-hier-util.rpt`)

| Block | LUT | DSP |
|---|---|---|
| attention (P=4) | 36.5k | 302 |
| matrix path | 27.7k | 285 |
| — accumulator | 18.5k | 275 |
| — reducer / unpacker / FIFOs / loader | 3.9k / 1.9k / 2.1k / 0.9k | |
| RMS norm, three copies | 8.2k | 84 |
| rope, quantize, top, control, state AXI | 11.1k | |
| memory + control interconnect | 4.3k | |
| **decoder total** | **93.3k** (of 117k) | 749 |

## Design (exact by construction)

`experiments/dual_port/matrix_dual.hpp`, applied to the decoder by `make_dual.py`.

1. **Row split.** Rows [0, R/2) stream on the existing `weights` master and rows [R/2, R) on
   a new `weights_b` master (for HP1). Each half goes through its own page-table loader and
   unpacker. This needs R even and cols % 512 == 0, so that the rows of each half are whole
   32-byte words. That holds for every Qwen3-0.6B matrix (1024, 2048, 3072 columns) and both
   head chunk sizes the host issues (8192, 4480).
2. **Lockstep core.** One II=1 pipeline takes block j of row i and block j of row i+R/2 every
   cycle. Both rows need the same activation block, so the activation buffer is read once
   and is not duplicated. That avoids about 32 BRAM36, and only 35 are spare. Each row's
   arithmetic is the single-port code: products, integer tree, two FP scalings, and the
   eight-register rotation.
3. **Shared reducer.** Row pairs alternate through the existing II=16 reducer, which keeps up
   because each row takes at least 32 blocks. The vocabulary argmax rule (larger value; on
   equality, the smaller index) does not depend on visiting order, so its result equals the
   single-port scan.
4. **Static reorder.** cols % 512 == 0 means the last block of every row lands in rotation
   slot 7, so the reorder is the identity and needs no multiplexer.

## Measured cost (HLS csynth, `build/v2/dual-port-study/hls-*/summary.json`)

| Variant | LUT | FF | DSP | BRAM18 | Matrix LUT |
|---|---|---|---|---|---|
| v9g | 125.9k | 169.7k | 701 | 223 | 28.5k |
| A1: one RMS call site for q/k norms | 123.0k | 167.1k | 673 | 223 | 28.5k |
| A2: A1 + static reorder (single port) | 123.0k | 169.9k | 673 | 223 | 28.5k |
| D1: A1 + dual port | 170.6k | 268.9k | 897 | 238 | 74.9k |
| D2: D1 + slot-pair DSP packing | 161.9k | 264.7k | 833 | 246 | 66.1k |
| D3: D2 + static reorder | **159.2k** | 264.6k | 833 | 246 | 63.4k |

HLS overestimates LUT: v9g is 125.9k in HLS and 93.3k routed, a ratio of about 0.74. FF
scales by about 0.58.

D3 is therefore about 118k LUT routed for the decoder, plus the interconnects and a second
HP clock converter: roughly 125k against a 117k device. FF (about 154k of 234k) and DSP
(about 880 of 1,248) fit.

## Slot-pair DSP packing (exact; `check_pair_dot.py`)

Token slots b and b+1 multiply the same weight, so (x_b·2¹⁹ + x_b+1)·w computes both products
in one 27×8 DSP multiply. Sixteen lanes are summed in one chain. |Σ x_b+1·w| ≤ 16·127·128 =
260,096 < 2¹⁸, so the low 19 bits, sign extended, are exactly that sum, and the rest is
exactly the x_b sum. Activations are clamped to ±127, so the packed operand always fits 27
signed bits.

An emulation with the exact ap_int widths matches direct sums on 200,255 cases, including all
sign and magnitude extremes and weights of -128. In HLS it removes the 96 LUT multipliers per
core and most of the integer adder tree (D1 → D2: -8.7k LUT, -64 DSP).

## Modelled gains (v9g cost model, replay logs of `2026-11-19-cost-aware-drafting.md`)

| Hardware | Plain decode | Speculative decode, RC1.1 policy | Speculative decode, new drafter |
|---|---|---|---|
| v9g | 1.00x | 2.28x | 2.58x |
| Second port used only for passes of ≤ 4 tokens (row-parallel use of idle slots) | 1.51x | 2.53x | 3.00x |
| Full dual port | 1.51x | 3.15x | **3.58x** |

All figures are relative to plain v9g decoding. Drafts are not re-tuned for the new costs, so
these are slight underestimates. The full dual port also speeds up prefill matrix work.

## Paths forward

1. **Reclaim in attention (36.5k LUT routed).** This is the only block large enough to make
   room for the full dual port next to P=4. It needs its own study of which P=4 lane
   structures can be shared without changing per-token operation order.
2. **Row-parallel small passes.** Single steps and passes of ≤ 4 tokens leave half the slot
   datapaths idle; let them take the second row half instead. This needs the second loader,
   unpacker and AXI path (about 7–10k LUT routed) and no new arithmetic. It is the cheaper
   route to most of the decode gain (3.00x vs 3.58x), but it still needs space at 99.3% CLB.
3. **Smaller fixes that add up:**
   - SRL FIFOs to BRAM (about 2–4k LUT, about 23 RAMB36 spare);
   - the last duplicate RMS instance (about 2k), which needs the outlined head loop removed.
4. **Dual port on v9f instead of v9g** (P=2 attention) would probably fit, but it gains only
   about 4% over v9g's P=4 in the model. Not recommended.

Nothing here has been routed or run on the board. Exactness is argued from construction and
the packing check; a C-sim audit would come before any board work.
