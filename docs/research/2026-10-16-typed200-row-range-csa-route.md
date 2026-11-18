# Timing-only routing of reviewed carry-save checkpoint

Status: COMPLETE, routed static timing and verification PASS at200 MHz.
User authorized routing and setup/hold, DRC, CDC and exception verification, with
unchanged constraints, preserved baseline, no bitstream or deployment. This is
a separate continuation of the completed narrowing experiment.

## Admission and provenance

The sealed source is
`build/v2/typed200-row-range-csa-physical-v1/place/placed.dcp`, SHA256
`c5ebe28f029ba9490fb146bac93a9139fbee403c5b78a94ed9a76fbbf7f2eb5e`.
Its reviewed placement has +0.506 ns setup and -0.073 ns hold at the unchanged
200 MHz target. It clears the existing +0.500 ns setup gate by only0.006 ns.
That narrow single-run admission is not routed closure or hardware qualification.

All2770 entries in the prior final seal were verified before starting. The
checkpoint was copied byte-for-byte to
`build/v2/typed200-row-range-csa-route-v1/input/placed.dcp`. The native tool opens
that standalone checkpoint; it never opens or saves the sealed project.
All old sources, checkpoint, reports, helpers, package/recovery/numerical baselines
and seals remain frozen. New route evidence is written only in the new directory.

The input checkpoint contains exactly two explicit clock definitions (5 ns and
10 ns) and39 scoped vendor XPM reset/synchronizer false-path commands. Input
constraint records include the `current_instance` scope, command and source
provenance. The routed checkpoint passed exact scoped command multiset equality,
unchanged vendor exception sources and clock-period checks.

## Final routed result

| Check | Result |
|---|---|
| Target / secondary clock | 200 MHz /100 MHz, unchanged5 ns/10 ns |
| Final setup slack | **+0.048 ns** |
| Final hold slack | **+0.011 ns** |
| Routable nets / fully routed nets | 123430 /123430 |
| Unrouted nets / node overlaps / routing errors | 0 /0 /0 |
| Check-timing categories | All12 zero |
| CDC | All defined-clock paths safely timed |
| DRC errors / critical warnings | 0 /0 |
| Exceptions | Same39 scoped vendor XPM false paths |
| Scoped timing commands / timing properties | Exact input/output multiset equality |
| Prior preserved paths | All2770 unchanged |

The router's intermediate/final routing summary estimated +0.046 ns setup.
The subsequent full STA report and final get_timing_paths query both give
+0.048 ns; the latter is the recorded result. Hold is +0.011 ns in both.
Compared with placement, setup drops0.458 ns while hold improves0.084 ns.
The placement margin was not a prediction of routed slack. This is a passing
single route with **tight margins**, not a repeatability or Fmax study.

Routed resources remain63192 LUT /52748 FF /579 DSP /50 BRAM tiles /36 URAM.
No observable-cycle or throughput improvement is claimed: the source, numerical
contract and clock target are unchanged.

DRC is not warning-free. It reports1226 warning checks:644 DPIP-2 input pipeline,
6 DPOP-3 output pipeline,575 DPOP-4 multiplier pipeline and one RTSTAT-10 warning
covering197 nets with no routable loads. The text lists only the first15 net/bus
entries: control-interconnect reset-pipeline nets and unused captured-data bits.
All routable nets are fully routed with zero routing errors; no-load warnings
must not be mislabeled as remaining unrouted loads. Methodology retains64
DPIR-2 asynchronous-driver advisories on DSP inputs; no LUTAR-1 issue is present.
No reset/pipeline RTL was changed to silence these advisories. They remain
explicit evidence for any later device-qualification review.

The result FIFO still has zero asynchronous-reset/preset flip-flops. No new
clock, generated clock, unconstrained endpoint, combinational/latch loop,
partial I/O timing constraint or pulse-width timing issue is reported.

## Native flow and verification

The existing default `phys_opt_design` followed by `route_design` is applied
with maximum4 threads. No retiming option, source change, clock edit, new timing
exception, bitstream, package, project save or board command is issued.
The staged Tcl and Python helpers are bound in input-proof.json before launch.

The native run saves a routed DCP and reports route completion, setup and hold
critical paths, global timing, DRC, methodology, CDC, clock interaction, clocks,
exceptions and all12 check-timing categories. Result FIFO synchronous-reset
mapping is checked. The review distinguishes completed assessment from passing
closure: negative setup/hold or another failed check must remain a documented
rejection, without constraint relaxation or automatic promotion.

Parent functional evidence remains unchanged: actual-source equivalence for
all2^64 raw shape/count encodings, arbitrary-input full endpoint induction and
5400 golden words /14 paired cases with exact outputs/counters/cycles. Routing
does not add RTL or cycles; it does not replace target numerical qualification.

## Routed critical paths and next measurements

The final setup worst path is **memory SmartConnect read-state register[3] to
linear weight_reg[1][7][12][5]**. It has4.728 ns data delay, of which4.532 ns
(95.855%) is routed wire and0.196 ns is logic, with one LUT2 level, -0.139 ns
clock skew and0.129 ns uncertainty. The route traverses a142-load state net,
one read-data gate and the156-load `m_axi_rdata[101]` net; that last segment
alone is3.498 ns. The placement softmax-shift worst path is therefore not the
routed global worst. Optimizing only arithmetic depth would miss this limit.

The final hold worst path is attention query-distribution group2 data_reg[68]
to query_reg[11][1][8][4]. It has0.245 ns data delay (0.114 logic /0.131 wire),
zero logic levels and0.131 ns clock skew, leaving0.011 ns hold slack.

Evidence supports inspecting the AXI read-data distribution and weight-loading
fanout/locality before another300 MHz arithmetic change. Any local capture or
buffering experiment must explicitly determine whether it adds a cycle, preserve
AXI valid/ready alignment and exact outputs/counters, and revisit deadline budgets
if latency changes. Benefit and implementation effort remain unmeasured; this is
a recommendation, not another implemented experiment. A repeat physical run or
target qualification would be separate evidence; neither was started here.

For the typed-output MVP, prioritize enforced target startup/reset/clock/master
ownership and measured or justified memory/MMIO service bounds. Static routed
closure removes this candidate's negative hold result; it does not establish
useful inference by a deadline, ARM execution bounds or external result delivery.
The old deployment inventory remains a sealed historical draft rather than a
new qualified profile for this routed candidate.

## Completion and preservation

Native run and review session30266 exited0. All2770 prior preserved paths,
including the original placed DCP/project, qualified sources/package/recovery/
numerical baselines and all earlier seals, were verified again after routing.
Input and routed checkpoints have exactly the same scoped timing commands and
vendor exception source/scope records. No constraints were relaxed or waived.
No bitstream, package, board action, commit, push or automation restart occurred.

Final immutable `2026-10-16-typed200-row-range-csa-route-validation.json` binds
this report, route helpers, input receipt/copy, native routed DCP, reports,
constraint snapshots, review, completion and all prior preservation hashes.
Mapped files are frozen after sealing; both handoffs remain editable.

The first sealing attempt exposed a receipt bookkeeping error: the original
reviewer hashed its own redirected console before printing the last line.
All other evidence hashes matched. `sealing-attempt-v1/` preserves the failed
sealer snapshot and exact recorded/final log hashes. The original route-review
and its bound helper are unchanged. `route-review-final.json` corrects only that
log hash, binds the original receipt and states that no native result changed.
The final v2 sealer checks this completed receipt and preserves both attempts.
No route, timing, DRC, CDC, exception or constraint check was rerun or weakened.

## Scope of this result

Any pass is 200 MHz static timing evidence for the exact routed checkpoint.
It does not establish 300 MHz, a bitstream-qualified device, target ARM startup,
reset/clock/master ownership, bounded DDR/MMIO service, successful-inference WCET,
external delivery deadlines or measured power. The qualified 200 MHz baseline
remains the recovery path. No bitstream or deployment is authorized here.
