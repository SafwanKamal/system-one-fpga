# Overnight KR260 work â€” October12,2026

## Morning handoff — October 12, 2026, 08:49 America/Chicago

Overnight work is stopping near the requested 09:00 cutoff. No synthesis,
implementation or regression job remains active. No new build is queued.
The overnight automation is being paused; retain all frozen evidence.

- The deployed `sysone-v2-memory` remains the validated 125 MHz baseline:
  eight input lengths and 350/350 frozen L12 requests bit-exact, 32 UltraRAM
  blocks and 59 BRAM tiles. No board or boot-memory changes this morning.
- Dot2 shared reduction synthesis reduced LUT use from 114,832 to 104,606.
  Incremental placement failed after 29m03s of placement plus checkpoint/import
  overhead. Full placement from the same optimized checkpoint succeeded in
  18m42s, avoiding repeated synthesis. Reuse was counterproductive for this
  particular candidate; this does not establish a general incremental result.
- Full placement estimates setup margin +2.642 ns at 125 MHz, +1.309 at 150,
  -0.358 at 200, -1.358 at 250 and -2.025 at 300 MHz. No routing was launched.
  Congestion remains level 5. The worst 300 MHz path shifted to LayerNorm's
  gamma BRAM through its wide multiplier, with 4.006 ns of logic delay.
- Dot3 addresses that path with registered operands, two partial products,
  and a registered combine. Scale/gamma alignment was adjusted together.
  All 32 KR260 cases, two Nexys cases and 64 stalled-output chunks passed;
  all 17 current RTL hashes match the frozen tested sources. The independent
  multiplier test passed 1,025 cycles across four lanes and both operand widths.
  Dot3 has NOT been synthesized, placed, routed or deployed.
- The simulated 128-token L12 encoder count increased from 7,509,558 to
  7,547,855 clocks (+0.510%). These runs include randomized stalls, so this
  comparison is diagnostic rather than a measured hardware performance claim.
- Independent high-address AXI tests and relative-image/address-window contracts
  passed, as did integer decoder primitives and empirical timing-policy checks.
  High-DDR executor/PS integration and a complete FPGA decoder remain open.

Next work session: run `scripts/v2/kr260/preflight_dot3_candidate.ps1` once.
It rechecks frozen regression hashes, uses isolated `kr260-opt-dot3`, and runs
synthesis only. Review LUT/DSP fit, retained split-product stages, local control
fanout, all 32 registered UltraRAM outputs and timing before placement. Routing
requires useful placement evidence. Keep the validated app until routed setup,
hold and hardware numerical checks pass; 300 MHz is not achieved.

Evidence: `build/v2/rtl-dot3-check/summary.json`,
`build/v2/eval/split-product-simulation/summary.json`,
`build/v2/kr260-opt-dot2/cold-placement/`, and the preserved failed incremental
run. Dot3 launcher PowerShell parsing and Python checker compilation passed;
the updated resource checker still passes the existing dot2 synthesis evidence.
The Tcl dot3 selector is prepared but has not been exercised by Vivado.


Overnight08:14 continuation (review through08:26Chicago): full dot2 cold
placement completed08:11 in1122.151s (18m42s), without incremental placement
or repeated synthesis. Legal placement succeeds where incremental failed.
Placed estimates:125MHz +2.642ns,150 +1.309,200 -0.358,250 -1.358,
300 -2.025. These are UNROUTED estimates; no hold/board qualification.
Placed104240LUTs (89.00%),113372FF,59BRAM32URAM607DSP; congestionlevel5
around attention/shared dot/MAC. Worst300MHz path now LayerNorm gamma BRAM
through multiplier:5.212ns data,4.006ns logic,1.206ns estimated routing.
No routing queued; preserve cold-placement checkpoint and failed incremental.

New dot3 source adds split_product_pipeline: input register, parallel signed
upper/unsigned lower products, registered signed combine (three clocks).
PIPELINED_DOT enables PIPELINED_AFFINE in LayerNorm: scale and gamma each
add two clocks, with gamma/beta/output tags adjusted. Default0 retains old
schedule. Four-lane21x32/18x30 isolated test passes1025 checked cycles with
signed extremes/random operands; build/v2/eval/split-product-simulation has
logs and hashes. Full regression frozen in /var/tmp/sysone-batch-regression.mpJExQ,
unifiedexec50528, outputbuild/v2/rtl-dot3-check. At08:27 all eight wide cases pass exact (10512 words compared); remaining
L12/one-word/control/Nexys/H1024 checks still ACTIVE.
Do not edit the17 RTL sources under this regression. No dot3 synthesis or
routing is queued. Finish numerical gates first, then review synthesis before
placement. Do not launch new heavyjobs near09:00cutoff; leave active tests
intact and pause overnight automation with a morning report. Board remains
validated sysone-v2-memory125MHz;300MHz is not achieved.


## Continuation at07:44Chicago

Incremental dot2 placement failed07:26: more than5% of movable cells could
not be legally placed. Placement29m03s; wrapperwait44m32s. Reuse percentages
did not produce success. No routing or board change. Preserved all evidence.
Started full placement from the same optimized checkpoint at07:46, session51013,
without reusing placement or rerunning synthesis. Independent cold-placement
directory records source hash and will contain frequency/timing/congestion
reports if successful. Do not duplicate/reset it. Next wake reviews this retry.

Diagnostic tool nowlabels failed stages explicitly;4testsPASS. Decoder
configuration type/range rejection tests also pass. No hardwareclock or
high-DDR integration claim. Active125MHz board baseline remains validated.

## Continuation at07:14Chicago

Low-address compatibility simulation also passed. Both high/low logs and
source SHA256 hashes are recorded in high-ddr-simulation/summary.json.

Dot2 placement remains active. Incremental matching83.34%,placementreuse82.20%
now works; no routing reused from the placed reference. Import alone8m40s, so
reuse does not automatically imply a net runtime improvement. Current Windows
paging observed (67pageReads/s,829pagesIn/s),~1.4GiB free; preserved userapps
and global settings. No routed timing or300MHz qualification yet.

High-DDR generic AXI simulation passed at0x800000ff0 over240000bytes using
300beatrequests, randomized bus stalls, 4KiB/256beat split checks and deliberate
one-beat corruption. Full40bit physical-window assertions prevent a misleading
pass if read/write both truncate highbits. Default low-address compatibility
run is also being checked. Logs saved build/v2/eval/high-ddr-simulation.
Actual PS mapping/relative-executor integration and high-DDR board use remain
unimplemented. No board change during this continuation.

## Continuation at06:44Chicago

Dot2 synthesis:104606LUTs (89.31%),112999registers,59BRAM,32registeredURAM,
607DSP. Compared first dot:10226fewerLUTs,9247fewerregisters,onefewerDSP.
Shared sum stages and query/accumulator fanout gates pass. Estimated300MHz
setup-2.084ns now traverses request arbitration into result-streamer controls.
Placement-only job launched06:45, session69176, using closerbatch3 placed
reference. No routing queued. Next continuation must review actual placed
timing/congestion and reuse before selecting more RTL work or routing.

Added independent integer RMSNorm and calibrated-table gated multiplication
references;37 decoder/memory/policy/profile tests pass, including float/scalar
oracles and wide/extreme input checks. Caller must supply model-specific
epsilon/scales/tables. This does not constitute a calibrated or deployed decoder.

## Continuation at06:14Chicago

Dot2 full frozen32KR260 cases plus Nexys/FIFO checks passed. Synthesis began
06:03, encoder IP finished06:17 and top-level reports remain active. Prepared
placement-only scripts referencing the closer batch3 placed checkpoint; do
not launch until actual dot2 resource/timing gates are reviewed. This reference
has no qualified routing to reuse; record measured matching and runtime.

Decoder integer reference gained grouped-query attention with compact KV-head
storage and half-split fixed-point RoPE using caller-supplied calibratedtables.
Grouped result matches explicitly expanded KV and streaming decode. RoPE
identity/quarterturn/clamp tests pass;12 decoder/INT4/relative bundle tests
passed. These remain primitive references, not a complete model or FPGA decoder.

## Continuation at05:44Chicago

First dot synthesis passed structural gates but uses114832LUTs (98.05%).
Estimated300MHz setup-2.216ns now points to LINEAR's combinational tile-address
multiplier; no routing launched. Revised dot2 shares a single four-stage dot
tree across mutuallyexclusive engines and replaces tile-index multiplication
with an accepted-request stream pointer. Regression session89002/evidence
rtl-dot2-check is active, wideeightcasesPASS, L12running; qualifier89043 starts
isolated dot2 synthesis only after all tests. Old dot project stays frozen.

Independent model_address_window.sv standalone RTL test passes high physical
addresses, end-of-region/40bit overflow, alignment, stalls and reset. It is an
experimental status-bearing translator, not connected to AXI/current executor.
relative_model.py supplies a zero-based payload plus SYS3 physical descriptor,
checks image/request scratch fit and rejects current executor capabilities.
16 relative/windowPython tests pass; inner numerical output matches IntEncoder.
No high-DDR board memory/configuration change or new app deployment performed.

Owner authorized scheduled continuation of all frontier work. Thread automation
`kr260-overnight-optimization` returns every30minutes, with a morning cutoff
of09:00America/Chicago onOctober12 (14:00UTC). Pause near the cutoff and leave
a report; do not kill builds already running. Notify only for significant
results, completion, failures or necessary user action.

## Starting evidence

- Board sysone-v2-memory deployed,125MHz,256MiB reservation, eight input lengths
  bit-exact and350/350 frozenL12 cases exact. Reports/comparison are in
  build/v2/eval/kr260-memory-hardware. Mean17.1877ms,baseline17.1598ms;
  observed+0.163%, not a speedup or hard timing bound.
- PIPELINED_DOT uses four balanced registered reduction levels and aligned
  score/LINEAR tags. Isolated signed/latency test512cycles passes.
- Frozen full regression session7197, staging
  /var/tmp/sysone-batch-regression.RTORjV, evidencebuild/v2/rtl-dot-check.
  Wideeight/L12eight/short-headfive/controlL12/Nexys passed; H1024 boundary
  compiling at setup time. Check log and source hashes rather than assume.
- Qualifier session11647 waits full completion, then starts isolated
  synthesis-only kr260-opt-dot at300MHz. No routing queued.
-47 relevant Python tests pass for high-DDR address planning, causal KV-cache
  reference, signedINT4 packing/matvec, timing policy, event profiling and
  existing link/evaluation behavior. These are foundations, not full hardware
  high-DDR/decoder implementation.

## Execution order

Setup milestone: H1024 boundary regression completed successfully; the
qualification summary accepted all32 KR260 cases plus Nexys/FIFO checks and
frozen17-source hashes. Synthesis started05:13Chicago in kr260-opt-dot;
completion-status.json is synthesizing. Do not rerun the regression or create
another synthesis job. Inspect this candidate's results next.

1. Inspect active processes/status/logs; do not duplicate or reset jobs. Finish
   the current regression. Repair functional failures before synthesis.
2. Inspect actual synthesized dot stage retention, resource fit, control fanout,
   UltraRAM output registers and timing paths. Use evidence to select the next
   pipeline or layout change. Keep defaults compatible with Nexys.
3. Use placement as an intermediate gate. Commit to at most one meaningful
   routing experiment after review; record timing, congestion and elapsed time.
   A nominal300MHz setting or unplaced estimate is not timing closure.
4. While heavy work runs, continue independent compiler/runtime/RTL relative
   address contracts, decoder primitives/reference, profiling support and
   timing-policy validation. Do not broaden training or paid compute.
5. Preserve board baseline. Only deploy a replacement with routed setup/hold,
   image/source provenance and exactness evidence. Use existing chat-authorized
   authentication transiently; never store credentials. Avoid concurrent RUNs.
6. Update this report and HANDOFF.md after each milestone. Morning report must
   distinguish completed work, active jobs, measured performance and remaining
   requirements. Pause automation near cutoff or when genuinely blocked/done.
