# Synchronous result-FIFO clear candidate

This continuation addresses the LUTAR-1 derived asynchronous-reset warning in
the [first typed200 physical candidate](2026-10-15-typed200-physical-r5.md).
It also records read-only confirmation that the KR260 is reachable again. The
qualified 200 MHz baseline, its package/recovery and all earlier sealed sources
remain unchanged. No FPGA design or firmware was deployed to the board.

## Board state after reachability returned

SSH authenticated against the previously saved host key. Linux reports hostname
kria, kernel 6.8.0-1036-xilinx and boot ID
`26b8c4ae-d5b6-4311-b8ef-d986df3156f4`, with about 25 minutes uptime at inspection.
eth1 is up at 192.168.0.239, the heartbeat LED trigger is selected, and systemd
lists no failed services. The FPGA manager reports operating, but configfs shows
the **stock k26-starter-kits_image_1 overlay**, not System One. We did not read
System One MMIO through an unverified address mapping.

The installed System One context-capture package's four files match the original
hardware-qualified archive exactly. The archive SHA-256 remains
`ecd320163baa3c289c64e069186497974d4703039df4a455bc8620d357d7ec99`.
Its package metadata predates board qualification and still says hardware_qualified
false; the later qualification receipt is the authority for the qualified baseline.
An initial comparison with the preservation file_checks list was insufficient:
that list is not an index of unpacked package files. Comparison against members
of the hash-verified qualification archive establishes the actual package match.
Diagnostics and the comparison receipt are retained in
`build/v2/board-readonly-recovery-20261015-v1`. No credentials are saved there.
The outage cause remains unknown; no reset, remoteproc action, reconfiguration,
software installation or other remote write was performed in this continuation.

## Implementation and boundary

[`create_typed200_flush_candidate.py`](../../scripts/v2/kr260/create_typed200_flush_candidate.py)
creates the isolated, sealed `rtl/v2/candidates/typed200_flush` successor.
Relative to its sealed parent, exactly one existing source changes:
[`result_streamer.sv`](../../rtl/v2/candidates/typed200_flush/encoder/result_streamer.sv).
One source is added:
[`stream_fifo_sync_clear.sv`](../../rtl/v2/candidates/typed200_flush/common/stream_fifo_sync_clear.sv).
All arithmetic, memory-port, epoch, deadline, numerical-profile and ABI sources
remain identical to the parent. The qualified and parent FIFO implementations
are preserved for the other consumers and the independent reference.
The frozen [contract specification](../../firmware/typed_intent/generated/contract.json)
explicitly separates semantic contract identity from a deployment certificate
binding contract, firmware, bitstream, environment and fresh boot session. Its
unchanged hash is not authorization to reuse a parent's physical qualification
or deployment certificate for this new candidate.

The old streamer drove FIFO asynchronous pointer resets with `reset || start`.
The successor's dedicated result FIFO samples reset and per-descriptor clear
at the rising clock edge, with clear/reset priority over reads and writes. Its
streamer suppresses valid during START/reset. This matches externally meaningful
clocked behavior while removing the path from a potentially glitching START LUT
to asynchronous reset pins. It deliberately does not preserve the old asynchronous
response to a START/clear pulse entirely between clock edges.

**Reset contract:** reset must span at least one sampled clock edge and release
synchronously. All consumers use the same PL clock. A subcycle global reset
cannot be silently treated as equivalent to the parent's asynchronous reset.
Reset/clock ownership and interruptions remain deployment assumptions. This
change does not make an interrupted PL clock satisfy a wall-time deadline.

## Verification

| Evidence | Observed result | Scope |
|---|---|---|
| Boundary simulation, unit-v3 | 65,673 compared cycles, 54 abort/reset cases across READ_LATENCY 3/4/5 | Actual FIFO DEPTH8/WIDTH128; independent frozen parent streamer; ordered outputs, identical valid/address/data cycles under backpressure, replacement and reset |
| Subcycle clear test | State and buffered word retained when clear never reaches a sampling edge; sampled clear dominates read/write | Direct FIFO stimulus tests the physical-risk mechanism removed by synchronous state updates |
| Induction, live-formal-v3 | PASS at actual DEPTH8/WIDTH128 | Arbitrary sampled data/read/write/clear: live pointers, count/flags, occupied memory and output equivalence to parent; occupancy bounded |
| Module-only Vivado synthesis | No asynchronous-reset/preset flip-flops; no LUTAR-1 | Structural mapping of the complete streamer, not full-system physical signoff |
| Full native encoder comparison, integration-v2 | PASS: 5,400 golden words, 14 paired completions and launches; exact AXI cycles and raw core/request counts | T1/2/3/4/5/12/64/128 and delayed/error/late B/R, early proposal, deadline/quarantine, stale session, invalid shapes; frozen reference system/streamer explicitly separate |

Formal uses pinned yowasp-yosys 0.70.0.0.post1259. The miter mechanically copies
both FIFO bodies and assumes reset at the first sampled edge. Reads and writes
remain arbitrary even during reset/clear. It compares live state and live
memory; inactive data and raw asynchronous-reset state are intentionally outside
the equivalence claim. This is a scoped FIFO proof, not a whole-encoder proof,
analog glitch simulation, placement result or target timing/WCET proof.

Preserved attempts: unit-v1 failed because GNU Make cannot build in paths with
spaces; unit-v2 stages into a separate Linux temporary directory. Unit-v3 additionally
covers READ_LATENCY5, the actual composed profile, alongside3/4. Integration-v1
failed at compilation because the multiline parent module declaration was not
renamed; integration-v2 uses an explicit independent reference system/streamer.
An initial generic equivalence attempt compared raw reset/internal pointer and
inactive data signals that intentionally differ and did not prove. The live-state
miter makes the intended clocked observation boundary explicit and proves its
invariants at the actual FIFO size. The stronger v3 proof removes v2's exclusion
of reads/writes during reset/clear. None of the earlier attempts is overwritten.

The OOC report contains expected TIMING-18 missing top I/O-delay warnings. It is
used only to verify reset mapping, not to claim standalone or composed 200 MHz
timing closure. The full physical runner explicitly adds the new FIFO source
before freezing its compilation snapshot, and requires full integration PASS
and actual-size formal PASS before synthesis.

## Full physical experiment

Independent `build/v2/typed200-flush-physical-v1` synthesis completed successfully.
At the actual 5 ns PL0 constraint, the synthesized estimate is WNS -0.612 ns,
WHS -0.087 ns, with no unconstrained internal endpoints or multiple-clock pins.
Eight synthesis no-clock warnings require checking after physical optimization,
as in the parent run. The critical synthesized path is inherited linear request
state to system status enable: 17 levels, 5.259 ns estimated data delay, of which
3.826 ns is estimated interconnect. This is not a routed timing result.

Synthesis uses 69,524 LUTs, 53,651 registers, 579 DSPs, 50 BRAM tiles and 36 URAMs.
The parent typed200 synthesis had three more LUTs and the same remaining totals;
this descriptive comparison is not a frequency/performance claim. Placement is
complete, with full methodology and explicit result-FIFO async-pin checks included.
No new bitstream, package or deployment is part of this experiment.

The original placed result is **WNS -0.066 ns**, TNS -0.263 ns across four setup
endpoints; WHS -0.074 ns, THS -1.657 ns across 105 hold endpoints. Its setup limit
is inherited linear out_tiles[1] through completion/ready logic to request_clocks[24]
synchronous reset: 16 levels, 4.810 ns estimated data delay (1.427 ns logic,
3.383 ns interconnect). All 12 check_timing categories are zero; CDC reports
all defined-clock paths safely timed. The placed design uses 64,340 LUTs,
52,184 registers, 579 DSPs, 50 BRAM tiles and 36 URAMs.

**The safety fix is confirmed in the composed netlist:** 202 FIFO cells retained,
zero asynchronous-reset/preset FIFO flip-flops, and no LUTAR-1 methodology warning.
The remaining 64 methodology warnings are inherited asynchronous DSP drivers.
That does not make the candidate timing-qualified: the original placed setup
result fails, and its route review rejects routing. The checkpoint/reports remain
preserved. A separate physical-only `phys_opt_design -directive Explore` pass in
postplace-opt-v1 improves setup to **+0.067 ns**, TNS 0, with hold **-0.117 ns**.
RTL, 5 ns period and timing exceptions remain unchanged. Its full methodology,
FIFO-reset mapping, CDC and clock checks pass. A separate hash-bound postplace
review admits the optimized checkpoint to a timing-only route experiment;
the original negative placed result remains rejected and preserved. Routing is
complete, with no package or deployment approval. One admission attempt was
blocked by a parser counting duplicated summary/detail categories; the corrected
review requires all 12 unique categories zero, and the failed attempt is retained.

**Final routed result:** Vivado reports all 200 MHz constraints met at its printed
precision: **WNS 0.000 ns, WHS +0.010 ns, TNS/THS 0**, with zero failing setup/hold
endpoints, zero unrouted nets and zero node overlaps. All 12 check_timing categories
are zero and CDC remains safely timed. The full routed FIFO still has 202 cells,
zero asynchronous-reset/preset flip-flops and no LUTAR-1 warning. Default DRC has
no errors or critical warnings; it retains DSP pipeline advisories and RTSTAT-10
no-routable-load warnings. Final resources: 64,346 LUTs, 52,185 registers, 579 DSPs,
50 BRAM tiles, 36 URAMs.

This is a **zero reported setup-margin pass**, not a hardware qualification or
evidence of 300 MHz headroom. The qualified baseline remains the only qualified
system. See the [route review](../../build/v2/typed200-flush-physical-v1/route-review.json),
[final timing](../../build/v2/typed200-flush-physical-v1/route/timing.rpt) and
[reset mapping](../../build/v2/typed200-flush-physical-v1/route/fifo-reset-mapping.txt).

The final limiting path moves to the AXI response/load boundary: SmartConnect
read-state flop to linear LUT data, **3 logic levels, 4.769 ns data delay**, with
4.330 ns interconnect (90.8%). A single m_axi_rdata[11] net has fanout 166 and
3.289 ns routed delay. The next path has +0.001 ns slack from inherited request
state into encoder-clock telemetry, 15 levels. These are concrete locality,
response-staging and observation-control targets; they do not establish that
additional MAC/DSP arithmetic pipelining is the first useful change.

| Matched evidence | Frozen parent | Synchronous-clear candidate | Interpretation |
|---|---:|---:|---|
| T1 core/request cycles | 1,845,556 / 1,845,641 | 1,845,556 / 1,845,641 | Same native fixture and bus response stream |
| T128 core/request cycles | 7,961,537 / 7,966,029 | 7,961,537 / 7,966,029 | No extra encoder/request cycles in the compared implementation |
| DSP / BRAM tiles / URAM, synthesis | 579 / 50 / 36 | 579 / 50 / 36 | Same arithmetic/storage profile |
| Registers, synthesis | 53,651 | 53,651 | Same total before physical optimization |
| LUTs, synthesis | 69,527 | 69,524 | Descriptive mapped count, not a performance claim |
| Derived asynchronous result-FIFO reset | Present; LUTAR-1 | Absent in both module and full placed mapping | Fix targets reset correctness rather than compute throughput |

These are encoder-request observations. Testbench-controlled proposal ages are
not R5 execution times, certified successful-inference bounds, decoder prefill
times or generated-token rates.

## Newly checked synthesis-clock boundary

A native Vivado audit of the actual custom-encoder OOC checkpoint reports
**Stored OOC clocks: 0**. The generated encoder synthesis Tcl has no explicit
create_clock/read_xdc command; its log reports no constraint files, and the OOC
checkpoint contains only a 93-byte in-context XDC without a clock definition.
See the [native clock query](../../build/v2/typed200-flush-physical-v1/encoder-ooc-clock-audit/clocks.txt)
and [audit script](../../scripts/v2/kr260/audit_typed200_flush_ooc_clocks.tcl).

The **composed** design does have its real 5 ns PL0 timing constraint and complete
clock coverage. This observation does not invalidate the qualified baseline's
routed STA and does not prove that missing OOC clocks cause every frequency limit.
It motivates a controlled **explicit OOC-clock synthesis experiment on identical
RTL**, checking that the constraint is active during synthesis and comparing
mapped critical paths, resources and final physical timing. Frequency metadata
on an interface is not sufficient evidence of an active synthesis clock object.
Possible benefit remains unmeasured; no clock relaxation or exception bypass
has been applied to the current candidate.

## Assurance implications and remaining work

This candidate removes one concrete reset-risk mechanism without changing the
typed contract or taking clock cycles away from the independent deadline. The
native equivalence comparison passes, and full synthesis/place/route checks confirm
the warning's removal. A clean FIFO mapping does not establish whole
system reset correctness or certify successful inference by deadline D.

Keep the 200 MHz timing-margin work separate: the previous route's 8 ps setup
margin is small, with the worst path from inherited completion logic into epoch
status. Registered read-only completion/quiescence observation and staged profile
validation remain evidence-led timing experiments. A registered hint must never
replace a current live-traffic/fault veto or allow a stale quiet indication to
authorize publication. Added observation latency must be explicit while the
independent deadline continues counting.

| Priority | Next controlled experiment | Evidence and acceptance condition | Effort / risk |
|---|---|---|---|
| 1 | Explicit clock-constrained encoder OOC synthesis on identical RTL | Native OOC audit currently finds zero clocks; prove the clock is active during synthesis, then compare mapped and full physical timing without changing RTL or exceptions | Low/medium; low semantic risk, benefit unmeasured |
| 2 | AXI response capture/register-slice and local load-data replication | Final critical path is 90.8% interconnect with fanout166. Preserve burst data/order, errors and complete live-drain accounting; quantify any added request cycles and recompute the successful-inference budget | Medium; protocol/ownership risk requires negative cases and a declared latency change |
| 3 | Retime telemetry and conservative completion observation | Near-critical inherited request-to-counter path; preserve exact raw counts and core output/AXI behavior for a purely observational change. Keep immediate traffic/error vetoes and epoch identity | Medium; off-by-one and stale-status risks |
| 4 | Reviewed R5 loader/ownership profile and target timing evidence | Bind new FPGA artifact, R5 ELF, clocks, memory ownership and fresh session; then exact target golden vectors, PMU/PL traces and justified DDR/ARM service bounds | High; prerequisites for a deployed timing guarantee remain unmet |

An incremental-layout experiment seeded from a hash-verified parent checkpoint
is another reversible flow control for this small RTL delta; it must preserve
the parent and report actual matched cells and routed results. Neither clock
constraints nor layout reuse should be credited with a benefit before measurement.

The R5 v8 executable and frozen numerical head are unchanged. Target startup,
golden outputs, buffer/master exclusion, bounded DDR/AXI service, real transfer/
head/commit WCET and independently bounded delivery remain required. The board
is currently running its stock overlay; reachability and an installed qualified
package do not establish a deployed typed service.
