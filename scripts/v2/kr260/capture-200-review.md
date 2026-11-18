# 200 MHz activation capture candidate

## Resumed: prioritize 200 MHz capture candidate (October 13, 10:30 PM Chicago)

User continued work and then explicitly requested a 200 MHz candidate. That is
now the next deployment target; 300 MHz remains longer term. Automation confirmed
ACTIVE with the updated milestone. Preserve deployed dot7-large at 125 MHz.

New optional LOCAL_READ_CAPTURE defaults0 across encoder layer/system/KR260
wrapper. Enabled adds one aligned read cycle (4 -> 5), local per-physical-buffer
capture before the shared mux, delayed physical selector, and capability bit6.
Both engine reads and result-streamer/host wait latency were updated together.
Production option is experimental until full regression and route/hardware gates.
No deployed firmware or frozen dot7 sources changed.

Focused results: 32768 port comparisons; seven actual activation memories with
240000 independent reference comparisons including masked writes, read-first
collisions, 4K cascade boundaries, selector collisions/invalid7. Result streamer
passed96 chunks at latency3/4/5 under initial prolonged and random backpressure.
First standalone streamer run lacked sync_fifo dependency; failed log preserved,
runner dependency corrected and retest passed. No data-path fix was needed.

Focused synthesis: baseline36URAM /641FF /1036LUT primitives, capture36URAM /
1525FF /1036LUT primitives; all896 local capture FF preserved. Baseline native
wall77.872s, capture53.933s. Synthesized URAM path estimated data2.657 ->2.367ns
and final output fanout4 ->1 in the isolated probe. These are not placed/routed
full-system improvements. The deployed net had fanout24 after replication and
5.167ns routing; full placement/congestion remains critical with CLB98.18%.

Integrated frozen regression session39947: build/v2/rtl-capture-check and its
snapshot.txt. H1024 maximum capacity, feature5359017f, wide/L12/one-word/boundary/
eight-H1024 fixtures, then unchanged Nexys defaults. Planned32KR260 cases +2Nexys.
Compiler consumed one core for several minutes; actual numerical cases started
passing, so do not kill/recompile merely for quiet compiler output.

Hidden follow-through controller PID12592: run_capture_after_regressions.ps1,
status build/v2/capture-controller-status.json, log/err alongside. It waits for
completion, independently gates32cases, current/frozen source hashes, memory and
latency5 streamer evidence and OOC inference, freezes18RTL sources in
build/v2/kr260-opt-capture-large, then launches one full synthesis at200MHz.
No automatic placement/route. Inspect completion and actual child process ancestry
before launching jobs; preserve failed attempts. Do not edit RTL while frozen
regression or synthesis runs. Next action after synthesis: review capture count,
resource/URAM/control/pipeline gates and measured critical paths, then placement
at200MHz and clock sweep; route only after review supports it.


## Firmware admission before eventual deployment

The capture option advertises feature word 0x5359017f, retains BUILD0x20804004
and requires activation_read_latency5/local_read_capture1. Existing frontier
runtime/deployer guards intentionally accept only the previously qualified
profiles and latency4. Update their explicit candidate table and capability
checks, with negative tests for mismatched latency/flag/mode, when adding
route-qualified capture packaging. Do not simply widen generic feature masks
or disable guards. No new candidate is packaged/deployed by the current controller.
The inference cut preserves 36URAM, but DONT_TOUCH alone does not prove physical
locality or 200 MHz timing. Review full-system placed/routed paths before making
frequency or throughput claims.

## Offline deployment admission prepared (10:37 PM Chicago)

Runtime and deployer now have explicit capture-large / sysone-v2-capture guards,
latency5 / local_capture1 / accumulator controls3 and feature0x5359017f. The
separate app directory will preserve the installed qualified frontier package.
Legacy frontier candidates continue requiring latency4 and capture0. Both still
require finite positive setup/hold and matching enabled PL0/PL1 live clocks.
55 runtime/deployment tests passed in2.04s, including capture positive admission
and rejecting old latency, missing capture, wrong control mode, swapped candidate
and unqualified/zero-slack profiles. This is mocked host validation, not board
or200MHz evidence. No firmware was uploaded. Package/export integration remains
pending actual routed qualification. Evidence: build/v2/capture-admission-tests.json.
