# Dot5-large placement review — October 12, 2026

Frozen H1024 candidate; routing failed, so replacement deployment is blocked. No RTL changes
were made while this design was being synthesized, placed or routed.

Placement: optimization 118.148 s, placement 1138.261 s. Frequency diagnostics
are estimates from the placed design, not routed qualifications:

| Clock MHz | Setup slack ns |
|---:|---:|
| 125 | 2.952 |
| 150 | 1.619 |
| 200 | -0.048 |
| 250 | -1.048 |
| 300 | -1.715 |

Selected 150 MHz for one routing attempt; require final setup and hold plus
complete routing. A qualified 125 MHz fallback may reuse the same routing.
Congestion remains level 5, with attention, shared dot and linear logic in the
busiest DSP regions. Initial routing explicitly warned that congestion forces
connection completion ahead of timing optimization.

The placed worst path at 150 MHz is add_skip_inst/rounded_reg[0][6] to
out_data_reg[10]/S: 4.849 ns data delay, 14 logic levels, 10 CARRY8 stages,
1.859 ns logic and 2.990 ns estimated routing. This is a different path from
the request-arbitration path fixed by dot5.

Next candidate after deployment review: residual arithmetic width reduction.
Current add_skip_engine uses generic signed 64-bit clamp/add/clamp operations.
A clamped skip fits signed 16 bits, with range [-32767,32767]. Adding a signed
16-bit residual requires only signed 17 bits: [-65535,65534]. The rounded
input is signed 26 bits, so its first clamp can compare at that width and
narrow before the sum. This provides a mathematical basis for eliminating
unnecessary wide carry chains. It is not an implemented optimization yet.

If an additional register stage is needed, preserve valid/address and residual
operand alignment and update the flush depth. Keep the legacy Nexys path.
Require saturation boundary, randomized arithmetic, full numerical and
backpressure regressions before any new synthesis. Do not modify dot5 sources
or rerun expensive placement simply to test a speculative change.

Evidence: build/v2/kr260-opt-dot5-large/placement/{frequency-diagnostics.json,
placement-result.json,critical-150mhz.rpt,congestion.rpt}; active routing
build/v2/kr260-opt-dot5-large/route-150mhz. Final route failed after 3h19m32s
with 6236 node overlaps and 8262 unrouted signals (south congestion level 6).
The 125 MHz fallback was never reached. Dot6 width/RAM follow-up is documented
in dot6_review.md; no qualified new FPGA app was uploaded.

## Additional width audit (read-only during routing)

Do not narrow the linear accumulator based on an assumed 48-bit datapath:
linear_engine.sv stores 32-bit accumulator words already, and its modular
addition semantics must be preserved.

The shared dot16_pipeline accepts signed 17-bit products. Sixteen arbitrary
such products sum within [-1048576,1048560], so the full mathematical result
fits signed 21 bits. Pair/quad/octet sums fit 18/19/20 bits respectively.
Current source declares all stages at WIDTH=24. The synthesis audit reports
4608 pair FFs, 2560 quad FFs and 1536 octet FFs: the pair stage was already
trimmed to 18 bits, while later stages retain more bits than their mathematical
bounds need. Explicit per-stage widths could help; actual savings require a
fresh synthesis gate, so do not count an estimated reduction as achieved.

Preserve the module's WIDTH-bit modular-sum contract, including WIDTH<21,
by proving truncation/sign extension at every stage and retaining four-cycle
latency and initiation interval one. Check full signed 17-bit inputs, not only
INT8 products: the generic dot testbench is permitted to exercise that range.
Keep the output ABI unchanged. Batch this with residual clamp narrowing only
after the current frozen candidate is reviewed; never change RTL under build.
