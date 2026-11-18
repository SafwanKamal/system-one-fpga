# Grouped batch review before another implementation

The independent memory candidate combines registered MAC operands, BRAM
exponent tables, H768 activation capacity and pipelined UltraRAM. It passes
125 MHz routed timing, with +0.001 ns setup margin. Board qualification is
still required. Its immutable RTL snapshot is the deployment source.

The first additional batch combines streaming result reads, query-data
distribution and ten performance counters. It passed simulation but its
125 MHz implementation failed at -4.477 ns. The critical path is the shared
query word-index decode to thousands of query-register clock enables.
95.5% of that path delay is routing. It took about 5 h 42 min to implement
and report clocks. Do not repeat that run unchanged.

## Changes and review gates

1. Predecode query lane and word at the same clock as the local query data.
   Register eight enables per static lane/word, each feeding only sixteen
   query bits. Use static destinations; remove the late dynamic write index.
   This retains the existing extra query stage and drain clock.
2. Keep the credit-reserved result FIFO and diagnostics. They already passed
   prolonged/random AXI stalls and independent bus-counter checks. Full
   corrected regression includes H768, L12, H1024/F4096 boundaries and Nexys.
3. Review reset/enable fanout and the query read-select path alongside data
   fanout before routing. Attribute requests alone do not prove localization:
   synthesis may merge equivalent enable registers. Inspect synthesized
   register fanout and paths; if it merges them, revise replication or use a
   targeted constraint after measuring the actual netlist.
4. Preserve old evidence. Corrected source and simulation logs belong under
   `build/v2/rtl-batch2-check`; old `kr260-opt-batch` remains immutable.
5. Run synthesis-only qualification in a new project after simulations pass.
   Capture high-fanout reports, query-control timing, primitive inference and
   resource fit, not only total LUT/BRAM counts. Require removal of the late
   global write-control cone before spending hours routing again.

## Memory/computation audit

- Existing LINEAR already overlaps two weight banks and accumulator drain.
  The AXI reader already permits eight outstanding bursts, splits at 4 KiB,
  and supports 256 beats. Increasing these blindly can increase congestion.
- Behavioral counters show weight delivery dominates short inputs; compute
  and read backpressure become relevant for longer inputs. Gather real board
  counters once the corrected batch is deployed before selecting deeper
  prefetch/FIFO changes. The memory candidate does not include these counters.
- Streaming removes much of output-only overhead but changes whole inference
  by far less than its 76.8% reduction of simulated transfer overhead.
- H1024/F4096 simulation covers the row-counter boundary; it does not establish
  device fit. Larger trained models still need separate qualification.
- Do not claim a completion guarantee from observed maximum latency or a
  passing FPGA clock. Model/input limits and DDR/host arbitration bounds must
  also be specified.

No second full implementation is authorized by this review workflow alone.
Finish the inexpensive gates and review their evidence first.

## Turnaround priority (2026-10-11)

Corrected batch simulation passed all 27 requests, the FIFO stall tests and
Nexys intermediate/final comparisons. A synthesis-only check is running in
`kr260-opt-batch2`. Gate query-enable loads at sixteen per register; if synthesis
merges the intended local copies, stop and correct that before implementation.

After the gates pass, `prepare_batch2_incremental.ps1` configures the completed
UltraRAM routed checkpoint as an incremental implementation reference. It
validates the gate again, records the reference hash and does not launch a run.
Reference reuse is a supported Vivado mechanism; actual matching/reuse and
turnaround improvement are not established until implementation runs.

Keep one heavy job at a time on this laptop. Do not increase thread count or
overlap full Vivado runs with simulation compilation without checking memory
headroom. Implementation already uses four threads. Preserve all frozen RTL,
checkpoints and reports; rebuilding the project discards opportunities for reuse.

Measured old batch times: placement 20m49s, routing 5h10m48s. Independent memory
candidate: placement 21m50s, routing 1h15m04s. These distinguish the structural
congestion problem from normal placement/synthesis overhead on this machine.
