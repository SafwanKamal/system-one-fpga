# Carry-save typed row-range validation

Status: COMPLETE. Proofs, matched probe, independent full regression, full
synthesis, source/clock review, placement and native checkpoint audit PASS.
The setup routing gate is met narrowly; no routing or deployment was started.

The direct nine-bit sum variant reduced logic/carry resources but regressed the
matched full endpoint timing from +1.595 to +1.292 ns. Its path had 0.194 ns less
logic delay and 0.497 ns more estimated wire delay; fewer carry cells alone do not
establish an improvement. That separate attempt and all evidence are retained.

Documentation correction to the sealed direct-sum report: its closing sentence
"No native job ... was started" means **no full native implementation job**.
Native endpoint probes and the Verilator regression were run and are preserved;
the direct pipeline had exited before this refinement began. No full physical
project, routing, bitstream/package or board action occurred. The sealed report
is preserved unchanged; this clarification supersedes that ambiguous sentence.

This new candidate, `rtl/v2/candidates/typed200_row_range_csa`, independently
descends from the sealed predecode parent. Only `contracts/typed_intent_axil.sv`
changes. It retains explicit rejection of all high raw bits and tokens 1..128
and positive count. It replaces add-then-compare with a carry-save comparison.

For A=first[6:0] zero-extended to8 bits, B=count[7:0] and T=tokens[7:0],
A+B+~T=A+B-T+255. Thus A+B<=T precisely when this sum has no bit above bit7.
Three-input XOR and majority form its carry-save representation. The candidate
retains **both** possible high carries: majority bit7 and bit8 of the final
nine-bit sum of XOR plus shifted majority[6:0]. No bit is discarded to assume
a legal input. Positive count and bounded total imply first<tokens.

The architecture has one carry-propagating addition after local XOR/majority
logic. It adds no state, cache, live permission or cycle. Exact all-raw-input
proof and full arbitrary-input endpoint induction must precede the same matched
endpoint probe. Full exact regression and strictly positive matched overall and
shape gain are required before full synthesis/placement.

## Completed proof evidence

`build/v2/typed200-row-range-csa-arithmetic-v1/receipt.json`: actual-source
combinational equivalence for every one of the 2^64 raw shape/count encodings,
without assumptions on valid range, reserved/high bits, positivity or overflow.
Two-state unsigned finite-width SystemVerilog semantics apply.

`build/v2/typed200-row-range-csa-endpoint-formal-v1/receipt.json`: full actual
AXIL/guard/publication gate sequential correspondence, proved by two-step
temporal induction. All external outputs, stored bank/written masks/bus state,
guard recurrence state, profile flags and shape predicate match after reset.
Only first sampled reset, single sampled clock and two-state semantics are
assumed. AXI addresses/data/byte strobes/valid/backpressure, split writes,
commands, core result signals, readiness, quiet, counters and later resets
remain arbitrary. No valid-input assumption weakens fail-closed behavior.

All encoder/numerical/predecode sources remain byte-identical to the sealed
predecode parent; manifest verification permits only the endpoint file change.
The endpoint proof therefore preserves launch and owned-shape timing for the
unchanged core, including invalid frames and fault decisions. Independent full
encoder output/cycle regression is additionally discharged below.

## Full independent regression

COMPLETE PASS: 5400 golden words / 14 paired completions / 14 launches. Normal
T1/2/3/4/5/12/64/128 plus delayed B, early proposal, B/R errors, timeout/late
response, stale session/shape checks preserve every sampled output, AXI,
busy/done and raw counter cycle. Reference encoder_layer and ADD_SKIP are
separately renamed frozen profile-cache sources, not shared candidate arithmetic.
T128 encoder/request counts7961537/7966029 and emulated publication age7966096
remain unchanged. Host simulation walltime444.320 s is not ARM timing or WCET.

The functional seal rehashed the actual WSL staging directory and checks every
prior sealed path (2604 unique files), including the completed direct-sum rejection. It freezes the
candidate, proofs, regression and matched probe before physical implementation.
The physical builder binds its own source, exact staged RTL, wrapper, board
setup, clock XDC/hooks and prerequisite receipts in input-proof.json. Do not
edit bound sources after this point.

## Matched endpoint timing

`build/v2/typed200-row-range-csa-ooc-v1/receipt.json` binds the actual source,
proofs, identical registered-input/output shell and native mapped checkpoints.
The independently repeated control produces exactly the prior probe metrics.

| Metric | Sealed predecode control | Carry-save narrowing |
|---|---:|---:|
| Overall worst slack, ns | +1.595 | +1.743 |
| Worst slack from actual stored shape banks5/28, ns | +1.595 | +2.313 |
| Shape-path data delay, ns | 3.279 | 2.561 |
| Shape-path logic delay, ns | 1.404 | 1.051 |
| Shape-path estimated wire delay, ns | 1.875 | 1.510 |
| Shape-path logic levels | 11 | 7 |
| Total endpoint carry cells | 64 | 58 |
| Endpoint probe LUTs | 1026 | 1009 |
| Endpoint probe FFs, including common shell | 1815 | 1815 |

The shape-source improvement is +0.718 ns and the stricter overall improvement
is +0.148 ns. The overall bottleneck moves outside the selected shape-source
path: profile-equality flag21 to last-request register enable, 3.131 ns data,
16 levels including10 CARRY8. The selected shape-source path is first-row bit1
to last-request enable, with seven LUT levels and no CARRY8 on that worst path;
the arithmetic expression does not imply a specific final primitive mapping.
These matched mapping results justify the requested full physical
experiment only after exact full regression passes. They are not full-design
placed/routed timing, 300 MHz evidence or a deadline guarantee.

## Full synthesis and source/clock review

COMPLETE: 30 staged / 28 compiled RTL files match the candidate and wrapper
hashes. The explicit 5 ns OOC clock was applied before encoder optimization;
encoder synthesis finished with zero errors and critical warnings. Full linked
clocks remain 5 ns and 10 ns, with no OOC clock leakage.

| Full synthesized design | Predecode parent | Carry-save row-range |
|---|---:|---:|
| LUT | 68499 | 68296 |
| FF | 53387 | 53376 |
| DSP | 579 | 579 |
| BRAM tiles | 50 | 50 |
| URAM | 36 | 36 |
| Estimated setup slack, ns | +0.628 | +0.624 |
| Estimated hold slack, ns | -0.087 | -0.087 |

Area is lower by203 LUTs and11 FFs in this full synthesis, while estimated global
setup is slightly worse by0.004 ns. This is not a full-design synthesis timing
speedup. The positive matched endpoint probe, unchanged functional behavior and
exact source/clock review admit the requested placement experiment; no physical
conclusion follows from resource reduction alone. All constraints remain intact.
Receipt: `build/v2/typed200-row-range-csa-physical-v1/synthesis-review.json` and
its bound full/OOC clock, timing, utilization, compiled-source and checkpoint evidence.

## Full placement

Placed reports and independent native reopened-checkpoint review agree on
**+0.506 ns setup / -0.073 ns hold** at unchanged 5 ns/10 ns clocks.

| Full placed design | Predecode parent | Carry-save row-range |
|---|---:|---:|
| LUT | 63383 | 63192 |
| FF | 52812 | 52748 |
| DSP / BRAM tiles / URAM | 579 / 50 / 36 | 579 / 50 / 36 |
| Setup slack, ns | +0.449 | +0.506 |
| Hold slack, ns | -0.154 | -0.073 |

Setup gains0.057 ns; hold improves0.081 ns but remains negative and unresolved.
Placed LUT/FF counts fall191/64. The setup report clears the preserved +0.500 ns
gate by only0.006 ns, a narrow single-run result, not robust closure. No routing
is started by this synthesis/placement request. No routed timing, target
qualification, 300 MHz capability or deadline guarantee is established.

The global worst path moves from typed row-range admission to instruction bit130,
softmax_shift[2], through attention exponent-index generation to lane11
e_index[24]. It has4.285 ns data delay (1.147 logic /3.138 estimated wire,
73.232% wire),9 levels including4 CARRY8, -0.124 ns clock skew and0.129 ns
uncertainty. The source code computes `((index >> (shift-1)) + 1) >> 1` when shift
is nonzero, retaining the original expression and finite-width semantics.
This identifies a new path for investigation, not a newly implemented change.

## Native checkpoint audit and decision

COMPLETE: all12 check-timing categories report zero issues; defined-clock CDC
paths are safely timed. All39 false-path exceptions remain vendor XPM
reset/synchronizer exceptions. No LUT asynchronous-reset or result-FIFO
asynchronous-reset mapping issue is present. Epoch/publication/permit structure
and GPIO driver are retained, along with32 profile-equality registers,
128 clamped-skip registers, captured instruction bias and product registers.
Placed DRC retains the expected unrouted-net condition and DSP pipeline
advisories; it does not establish routed closure.

| Native selected path scope | Worst slack, ns |
|---|---:|
| From actual shape banks5/28 | +1.010 |
| To predecode bias registers | +1.996 |
| To ADD_SKIP product registers | +0.965 |
| To clamped-skip registers | +0.819 |
| From clamped-skip registers toward output | +0.916 |
| From profile byte-equality registers | +1.080 |

The output query is source-restricted, not the minimum from every residual or
control input. The full-design global timing report covers all timed paths.
The parent had its global worst at a shape-bank source, +0.449 ns; the new
shape-source minimum is +1.010 ns, an improvement0.561 ns, while the global
improvement is only0.057 ns because attention softmax becomes the bottleneck.
This is a single physical run, not a repeatability or Fmax study. No throughput
or request-latency gain is claimed: clock target and observable cycles are unchanged.

Retain the carry-save candidate as the best characterized descendant for this
experiment. Reject the direct-sum attempt for full implementation and preserve
both. Pipeline session52782 exited0; all seven commands completed successfully.
No native job remains. The setup gate's `route_approved=true` records eligibility
for a timing-only route under the existing policy; **routed=false**. Routing was
not part of this completed synthesis/placement run. Negative placed hold must
be repaired and rechecked in any later routing experiment.

Priorities after this completed request:

1. Characterize timing-only routing of the exact reviewed checkpoint, retaining
   the +0.500 ns setup gate, all constraints and exception audit. It passes by
   only6 ps, so routing or repeated placement may erase the apparent margin.
   Require routed setup/hold, zero unrouted/overlap nets and DRC/CDC checks before
   any closure claim. No bitstream or deployment follows automatically.
2. Prioritize target startup, reset/clock/master ownership and bounded DDR/MMIO
   service for a typed-output MVP. The existing13 deployment gates remain
   unresolved; no ARM target, useful-success WCET or external-delivery evidence
   is supplied here. A53/R5 supervision requires enforced ownership and measured
   or justified interference bounds, not simply moving code onto an ARM core.
3. Investigate the measured attention softmax shift/rounding path only as another
   isolated experiment. Instruction-local predecode or local fanout reduction
   has direct critical-path evidence, but benefit/effort are unmeasured and
   73.232% estimated wire delay warns against assuming arithmetic simplification
   alone will help. Shift bits128..133 are in instruction word1, unlike ADD_SKIP's
   word0: require actual word1 freshness/history/alignment proof and exact
   finite-width rounding, then all-stage probes and independent full regression.
   This is not implemented or scheduled by the present request.

Final immutable `2026-10-16-typed200-row-range-csa-validation.json` binds this
report, candidate/helper sources, whole-domain and endpoint proofs, matched
probe, independent regression and actual WSL staged rehash, full physical
checkpoints/reviews/audit and all2604 prior preserved paths. The earlier failed
direct proof-tool attempt and its rejected timing result remain sealed. Both
handoffs remain editable. The completed overnight heartbeat remains PAUSED.

The +0.500 ns placed setup routing gate and 5 ns/10 ns clocks remain unchanged.
This request performs synthesis and placement only; it creates no bitstream,
package or board deployment. Qualified 200 MHz sources/package/recovery/numerical
baselines and the rejected direct variant remain preserved. Timing estimates
do not establish successful-inference WCET, target ARM execution, master
ownership, bounded DDR/MMIO service or external-delivery deadlines.
