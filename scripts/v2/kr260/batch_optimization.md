# KR260 grouped optimization candidate

The next candidate retains H768/T128/HD64/TO32 and the registered MAC,
BRAM softmax table and pipelined UltraRAM profile. It adds optional
`STREAM_RESULTS=1`, `LOCAL_QUERY_REGISTERS=1` and `PERF_COUNTERS=1`.
Defaults keep the established transfer and attention paths. LINEAR source and
destination row strides are widened from eight to sixteen bits for all profiles.

## Changes and checks

- Result reads reserve space in an eight-word FIFO before issuing fixed-latency
  activation reads. Pending reads count against capacity, so AXI write stalls
  cannot overflow storage. Results remain stable until accepted. Requests still
  use the existing burst/chunk and AXI 4 KiB boundary handling.
- Query data is registered near groups of four attention lanes with distinct
  write enables. A one-clock query drain state aligns the added distribution
  stage before the first score operation, including one-word heads.
- Sixteen-bit row strides represent 256 words for a 4096-element INT8 FFN row.
  H1024/F4096 synthetic vectors check this boundary in simulation only; the
  deployment candidate remains H768 and no H1024 fit or model quality is claimed.
- `simulation/v2/run_kr260_batch.sh` checks FIFO backpressure, full wide and L12
  requests, a matched control with streaming/local queries disabled, the Nexys
  default and the independent H1024/F4096 integer-reference boundary vectors.
  `summarize_kr260_batch.py` requires complete cases, counter checks and exact
  current source hashes before accepting evidence.

## Performance registers

0x1C contains versioned capabilities `0x53590100 | flags`: bit 0 counters,
bit 1 streaming results, bit 2 local query registers, bit 3 pipelined UltraRAM.
Older firmware returns zero; `Kr260Link.performance_counters()` returns None
when counters are unsupported and rejects reads while the encoder is busy.
Serialize RUN and readout through one owner. Counters reset for each accepted
RUN, freeze when idle and wrap at 2^32. Different event counts can overlap.

| Address | Counter | Meaning |
|---|---|---|
| 0x30 | axi_read_beats | Accepted AXI R beats |
| 0x34 | axi_read_service_wait | Outstanding R beats, consumer ready, RVALID absent |
| 0x38 | read_backpressure | RVALID present, consumer not ready |
| 0x3C | linear_mac_issues | LINEAR input tiles issued to the MAC pipeline |
| 0x40 | attention_mac_issues | Score or P.V inputs issued to the MAC pipeline |
| 0x44 | linear_weight_wait | Compute waiting on its weight bank |
| 0x48 | linear_drain_wait | Compute waiting on its accumulator bank to drain |
| 0x4C | axi_write_beats | Accepted AXI W beats |
| 0x50 | axi_read_bursts | Accepted AXI AR requests |
| 0x54 | result_source_wait | Result words due, memory writer ready, source absent |

Use these with encoder/request clock counts and the model/input shape. A high
weight-wait count alone does not distinguish unavoidable DDR bandwidth demand
from poor prefetch scheduling. Simulation uses synthetic AXI stalls; board
measurements remain necessary. None of these counters establishes a hard timing
bound under Linux/shared-DDR contention.

## Build gate

`preflight_batch_candidate.ps1` verifies simulation/source evidence, waits for
the existing memory-layout build to finish, then runs synthesis only in
`build/v2/kr260-opt-batch`. It records utilization and actual UltraRAM primitive
output-register properties. `check_batch_preflight.py` requires resource fit
and registered UltraRAM outputs. Review these reports before launching full
placement/routing; synthesized fit does not establish routability or frequency.
Preserve the completed wide build and the independent memory candidate.
Deployment packaging and board validation follow routed clock qualification.

## Verified simulation result (2026-10-10)

All 27 AXI requests pass: eight H768 synthetic, eight existing L12, eight
matched L12 control, three H1024/F4096 boundary cases. Counters match independent
AXI beat/burst monitors. FIFO unit tests pass 64 chunks at latency 3/4, and
the default Nexys regression passes 39,216 intermediate/final words. Evidence
and the 17 RTL source hashes are in `build/v2/rtl-batch-check/summary.json`.
At 128 tokens, matched L12 request overhead drops from 19,625 to 4,561 clocks
(76.759% reduction); encoder cycles increase 0.0068%. These use a behavioral
AXI model with random stalls and are not measured board timings.
