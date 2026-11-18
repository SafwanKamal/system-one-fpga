# Typed row-range validation narrowing

Status: COMPLETE; functionally equivalent, timing probe rejected. No full build,
hardware qualification or deployment.

The parent is sealed `typed200_predecode`, whose 200 MHz placement had
+0.449 ns setup and -0.154 ns hold. Its actual worst path ran from the stored
first-row field through typed shape/admission logic to encoder state enable.
That checkpoint remains rejected for routing under the +0.500 ns setup gate.

## Architecture and scope

Only `contracts/typed_intent_axil.sv` changes in the new
`rtl/v2/candidates/typed200_row_range`. No register, cache, state transition,
deadline rule, clock, ABI, numerical operator or observable cycle is added.

The old predicate requires tokens 1..128, reserved count bits zero, positive
count, first<tokens and a 17-bit first+count<=tokens. Thus an accepted frame
necessarily has first<=127 and count<=128. The candidate explicitly rejects
tokens[15:8], first[15:7], and count_word[31:8]; tests tokens 1..128 and positive
low count; and compares a nine-bit sum of first[6:0]+count[7:0] against tokens.
This sum represents every possible remaining low-field combination up to382.
It cannot wrap. Positive count plus sum<=tokens implies first<tokens, removing
the second wide comparator without weakening invalid-input rejection.

No live ownership, error, quiet, identity or deadline permission is cached.

## Proofs

`build/v2/typed200-row-range-arithmetic-v2/receipt.json` records SAT proof of the
actual extracted old/new predicates for **all 2^64 raw encodings**: 16-bit tokens,
16-bit first, 16-bit count, 16-bit reserved. No legal-input or bounded-value
assumptions. This covers zero, invalid high bits, reserved bits and sums beyond
the token boundary. Two-state finite-width SystemVerilog semantics apply.

The first attempt, arithmetic-v1, is retained. Yosys rejected its unlowered
`$check` cell before solving; v2 adds `chformal -lower`. No RTL counterexample
was found and the RTL did not change between attempts.

`build/v2/typed200-row-range-endpoint-formal-v1/receipt.json` records full endpoint
sequential correspondence, proved by temporal induction in two steps. Both
actual AXIL/guard/publication-gate source sets are copied and renamed separately;
proof-only observation ports expose the stored bank, written byte masks, captured
bus state, guard recurrence state, profile equality flags and shape predicate.
All external endpoint outputs and observation state match at every sampled edge
after reset. Address/data valid, addresses, byte strobes, backpressure, commands,
core completion/identity/success, quiet, readiness and counters are arbitrary.
Split writes, partial masks, invalid commands/frames and later resets are covered.
Only first sampled reset, single sampled clock and two-state semantics are assumed.

The numerical pipeline and predecode sources are byte-identical to the sealed
parent; the candidate manifest checks this boundary.

Full independent regression COMPLETE PASS: **5400 golden words / 14 paired
completions / 14 launches**, normal T1/2/3/4/5/12/64/128 and delayed B, early
proposal, B/R error, timeout/late response, stale session/shape scenarios. Every
sampled output, AXI transaction, busy/done and raw counter cycle matches the
independent reference, which separately renames frozen profile-cache ADD_SKIP
and encoder_layer. T128 encoder/request cycles remain 7961537/7966029 and
emulated publication age7966096. Simulation walltime404.197 s is host runtime,
not target ARM timing or inference WCET.

The functional seal rehashed the actual WSL staged inputs and preserved all
previously sealed paths. The final seal binds this report, candidate/helper
sources, proof/probe/regression evidence, rejected-build pipeline receipts and
the failed first proof-tool attempt. Both handoffs remain editable.

## Timing and physical admission

The matched probe uses actual full endpoint sources with the same registered
input/output shell for both variants. It reports all-endpoint worst timing and
paths from actual stored shape banks5/28. The shell models timing boundaries,
not extra cycles in the candidate. Full encoder fanout, actual placement and
board timing remain outside this probe.

Completed matched probe (`typed200-row-range-ooc-v1`):

| Metric | Sealed predecode control | Direct narrow sum |
|---|---:|---:|
| Overall and shape-source worst slack, ns | +1.595 | +1.292 |
| Shape-path data delay, ns | 3.279 | 3.582 |
| Logic delay, ns | 1.404 | 1.210 |
| Estimated wire delay, ns | 1.875 | 2.372 |
| Path logic levels | 11 | 10 |
| Carry cells on worst path | 4 | 1 |
| Total endpoint carry cells | 64 | 59 |
| Endpoint probe LUTs | 1026 | 1014 |
| Endpoint probe FFs, including common shell | 1815 | 1815 |

Both worst paths end at owned-count register enables. The source changes from
count bit0 to count bit2. The candidate's lower logic delay is outweighed by
0.497 ns higher estimated wire delay. Overall slack **regresses 0.303 ns**.
No full synthesis/placement is admitted for this variant; its regression passed
the requested exact-output/cycle check. These are synthesis
mapping estimates, not a placed or routed speed measurement.

A separately preserved carry-save refinement targets the add-then-compare
dependency; see [carry-save experiment](2026-10-16-typed200-row-range-csa.md).
It does not replace this attempt or its proof/timing evidence.

Decision: preserve and reject the direct-sum candidate for promotion/full build.
Pipeline session33014 exited0 with physical_build_admitted=false. No native job,
physical project, route, bitstream/package or board action was started for this
variant. `2026-10-16-typed200-row-range-validation.json` is its final immutable
record; the carry-save refinement is a separately authorized implementation of
the same requested narrowing, not a modification of this completed attempt.

Full synthesis/placement requires successful proofs, exact independent regression
and evidence of matched timing improvement. No constraints may be relaxed. The
existing +0.500 ns full placed setup gate precedes timing-only routing; placed
negative hold is not routed closure. No bitstream/package or board action is
authorized by this experiment.

## Typed timing guarantees

This optimization preserves rejection and admission semantics. It does not
establish successful-inference WCET, ARM startup, reset/clock/master ownership,
bounded DDR/MMIO service, useful-success coverage or external result delivery.
Those product gates remain explicit in the existing deployment inventory. A
local terminal deadline under stated assumptions and useful inference by that
deadline are separate claims. ARM A53/R5 supervision can support ownership and
protocol handling only after the target execution and interference bounds are
measured or enforced; using a core alone supplies no timing guarantee.
