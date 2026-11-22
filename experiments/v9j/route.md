# v9j route: skipped (2026-11-22)

**Not routed.** This step's gate was a routed decoder estimate of about 96k LUT or less. Codex's
csynth puts v9j at **133,338 LUT** for the decoder alone, above the whole K26 (117,120 LUT, about
5k of which is shell). Routing it would spend about an hour of Vivado on a design that cannot fit.
See [csynth.md](csynth.md).

| Decoder | Source | LUT |
|---|---|---:|
| v9h | routed (whole design 101,844) | n/a (no hierarchy report) |
| v9i (D3 + P=2) | routed, `../v9i/route.md` | 87,772 |
| D3 (P=4) | HLS 157,308 × 0.63 | ≈ 99,104 |
| **v9j (D3 + P=4 + mul_xb)** | D3 estimate + 0.69 × 49,614 attention HLS increase | **≈ 133,338** |
| Gate for routing | | ≤ ~96,000 |

## Why v9j grew instead of shrinking

v9j was meant to keep P=4 and pay for it by swapping attention's fp32×bf16 multiplies for a
narrow 24×8 integer product. In synthesis the swap added area:

- **Attention HLS LUT:** 46,586 → 96,200 (+49,614). DSP: 295 → 423 (+128). Matvec unchanged.
- **The FP32 multipliers were not removed.** Attention still instantiates 56 FP32 `fmul` cores in
  both designs; in v9j they sit in the carried-accumulator rescale pipeline. So the integer
  multipliers were added on top of a bank of the same size, not in place of it.
- **The fabric cost is in the wrapper, not the product.** The +128 DSP matches 2 sites × 64 lanes,
  one DSP each for the 24×8 mantissa product. The LUT increase works out to about 390 LUT per lane
  (49,614 ÷ 128). That pays for unpacking, exponent add, normalization, RNE rounding and FTZ
  handling, replicated in all 128 lanes.
- **Schedule:** score and value loops stayed at II=1 (depth 27 → 25 and 10 → 8). Exactness is as
  expected: stock probe 75,776/75,776 exact; differences are only subnormal products flushed to
  zero (FTZ), and IEEE mode matches D3 exactly (`probe.md`).

## What routing v9j would need

v9j would have to drop by about 37k routed LUT (≈ 54k HLS LUT in attention) to reach the gate:

1. **Fold the rescale multiplies back into the shared bank.** If the 56 `fmul` cores were reused
   rather than duplicated, the design would recover most of the fp32 cost. That needs a
   scheduling change in attention, not just a substitution.
2. **Share the post-product logic across lanes.** Do normalization and rounding once per
   reduction instead of once per product, for example by accumulating unrounded products in a
   wider fixed-point sum. That changes rounding order, so exactness against v9h would have to be
   shown again; it would no longer be bit-identical by construction.
3. **Or fewer lanes per site.** That lowers throughput, which defeats the point of keeping P=4.

None of these is a small patch. v9i already fits with 24k LUT of headroom (92,728 of 117,120) and
is bit-exact with v9h in prefill C-sim, so v9i is the image to pilot.

## Ready if needed

`build_v9j.py` is `experiments/v9i/build_v9i.py` retargeted to `build/v2/v9j` (v9h's exact flow,
plus the hierarchical utilization report). It has **not been run**: use it only after a revised
v9j's csynth estimate clears the gate.
