# Placed linear drain path review — October 13, 2026

The completed dot7 placement's 125 MHz worst setup path runs from linear
accumulator bank 1 RAMB18E2 CLKARDCLK to d3_product DSP B[12]. Slack is 2.921ns,
data delay 4.344ns: logic 1.742ns, estimated routing 2.602ns, four logic levels
(LUT3, two LUT6 and MUXF7). This is a placed estimate, not routed closure.
The synthesized embedding shift-control bottleneck is therefore not the only
constraint. The completed 300MHz report confirms this same path is worst,
with estimated slack -1.746ns; no 300MHz closure is established.

The drain currently reads a whole accumulator row, selects a bank/channel with
a variable part-select into d2_selected, then multiplies by a 17-bit unsigned
requantizer. Synthesis absorbs the selected operand register into DSP B input
registering. The measured path includes RAM clock-to-out, bank/channel muxes
and long interconnect to that DSP input. Optimizing the downstream multiplier
arithmetic alone will not remove that RAM-to-selection path.

A candidate cut should be tested as a default-off drain option: capture an
intermediate selected bank or channel group before final lane selection/DSP
input. Preserve complete signed INT32 accumulators and UINT17 multipliers;
keep tags, lane validity, multiplier, final issue and flush latency aligned.
Avoid adding a full 1024-bit register per bank without measuring packing:
placed dot7 already uses 14374/14640 CLBs (98.18%) despite only 77.08% LUT use.
Changing the compute accumulator read latency affects old-sum hazard spacing;
a drain-only stage avoids that compute-path change but still requires correct
bank/parameter release timing until the last row/multiplier has been captured.

Before heavy builds: isolated drain/control equivalence with signed INT32
boundaries, all six-bit shifts, partial output tiles, drain lanes 1/2/4,
alternating banks, one-token cases, overlapping next-tile compute, destination
stalls where supported and reset/restart; synthesis register/DSP/BRAM inference
inspection; then numerical/default regressions. No production RTL change or
timing benefit from this proposal has been established. Frozen dot7 remains
untouched while its placement reports complete and routing is reviewed.

## Standalone two-stage selector verified October 13

linear_drain_select.sv prototypes a drain-only cut: select channels separately
from each bank into local registers, then select the bank in the following
stage before the DSP operand/product path. For four lanes its first-stage row
data is 2*4*32 = 256 bits, rather than duplicating two full 1024-bit rows.
That is an architectural storage count, not measured synthesized FF/LUT use.
Mask, UINT17 multipliers and packet tags traverse the same stages. Invalid
lanes are zeroed and masked; advance stalls the complete tuple; reset cancels
valid entries. It is separate from the frozen dot7 engine and not integrated.

24576 packet comparisons passed over ROW_CHANNELS=12/32 and LANES=1/2/4.
Coverage includes both banks at all columns, every mask pattern, outside-row
columns/partial groups, full INT32 edge/random row data, UINT17 zero/max/random
metadata, consecutive inputs, clock-enable stalls and reset cancellation.
The strengthened bank/mask pass supersedes a first pass whose one-lane mask
was correlated with bank selection; the earlier result log is preserved.
Evidence/source hashes and native build/simulation elapsed are recorded in
build/v2/linear-drain-select/summary.json. No synthesis/timing gain is proven.

Integration should feed the returned RAM row plus existing d1 bank/column,
multiplier and lane metadata into the selector. Per-bank capture replaces the
old d2 selection; next-stage bank selection delays the product by one cycle.
The full drain depth becomes seven instead of six, with final/token/column/lane
tags and rounded/clamped/table output shifted consistently. Preserve compute
accumulator read latency and its pass-gap hazard spacing. Bank/parameter release
must be proven safe after the last row and multiplier are captured, including
next-tile overlap; the standalone module does not verify that controller policy.
Require full-engine equivalence and isolated inference/resource/timing checks
before any grouped full build. No production RTL was edited under active routing.
