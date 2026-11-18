# Agent command gate RTL v3 — 2026-11-08

Implements in fabric what the closed-loop experiments (`2026-11-08-agent-gate-closed-loop.md`) showed to matter:
acceptance tracking, checksum verification, the risk-reducing exemption, a level interval that widens with the age of
the reading, and a session-preserving way to refuse a request. **Verified in simulation and by out-of-context
implementation only. It is not in a board bitstream and has not run on the KR260.** The board still runs the v1 bridge.

## What is built

| File | Role |
|---|---|
| `rtl/v2/gate/gate_csum.sv` | Streaming IPv4-header and TCP checksum verifier (VLAN-aware, odd-length padding, pseudo-header) |
| `rtl/v2/gate/gate_core_v3.sv` | Frame parser (v1's, unchanged semantics) + checksum check + acceptance-tracking decision core + byte-mutation descriptor |
| `rtl/v2/gate/bridge/gate_bridge_core_v3.sv` | Store-and-forward bridge around the v3 core; generated from `gate_bridge_core.sv` by `scripts/v2/gate/make_bridge_v3.py`; patches mutated frames and regenerates their Ethernet FCS |
| `src/sysone/v2/agent_gate/gate_v3.py` | Hardware-exact decision-core specification (the RTL's contract) |
| `src/sysone/v2/agent_gate/frames_v3.py` | Frame-level model of the core, including mutation; produces every expected value below |
| `scripts/v2/gate_v3_vectors.py`, `gate_v3_bridge_vectors.py` | Vector generators |
| `simulation/v2/gate/gate_core_v3_tb.sv`, `gate_bridge_core_v3_tb.sv` | Testbenches (`run_gate_sims.sh corev3 | bridgev3`) |

State kept by the core: an 8-entry pending-write table (conn, txid, address, values, time), an 8-entry read-transaction
table, for each of the four registers two possible values plus a "wild" flag, the observed level with its timestamp, the
last four pump-start times, an 8-entry table of refused requests awaiting the PLC's reply, and the active connection.

Decision flow for a write: expire pending writes older than 2 s (they become uncertain), build the set of possible
actuator values (committed values plus pending ones, two per register, a third makes the register wild), allow at once
if the write can only lower inlet, pump or heater, refuse if the pending table is full or any register is wild,
otherwise compute the level interval and evaluate the rule set sequentially for every possible actuator state at both
interval ends; the first failing rule is the answer. Echoes commit, exceptions discard, timeouts and lost connections make
registers uncertain, FC3/FC4 read-backs resolve them. Rule codes are now 5 bits (16 checksum_bad, 18 pending_table_full,
19 state_unknown).

## Refusal by byte mutation (replaces the planned TCP splice)

A refused request is forwarded with its Modbus function code replaced by 0x7F, same length, TCP checksum corrected by
RFC 1624 incremental update, Ethernet FCS regenerated in the transmit path. The PLC answers "illegal function". When that
reply comes back (matched by connection and transaction id, 9 bytes, function 0xFF) the gate restores function code
(original | 0x80) and exception code 0x03, again with an incremental checksum and a fresh FCS. No sequence or
acknowledgement number is ever changed and no frame is injected. Closed-loop experiment 6 found it equivalent to a spliced
exception on every measured outcome. **Open risks:** a real PLC must be shown to answer an unknown function code with
exception 01 and without closing the session or raising an alarm; the exception reaches the client after a PLC round trip.

## Verification

Reference model: `frames_v3.GateV3Model` (parser identical to the v1 model verified earlier, plus the v3 core).
Every vector line checks the decision (forward, rule, class), a 17-field state signature, and the byte-mutation
descriptor (kind, new function code, new exception code, new TCP checksum, three byte offsets).

| Test | Frames | Result |
|---|---|---|
| Core, traffic recorded from closed-loop episodes (all six scenarios: polls, echoes, exceptions, retransmits, bad checksums, reconnects) | 49,701 | 0 decision / 0 state / 0 patch mismatches |
| Core, directed fuzz (table edges, timeout boundary 1999/2000/2001 ms, 32-bit time wrap, pending-full bursts, wild registers, VLAN, malformed, bad FCS/checksums, PLC replies to mutated requests, connection changes) | 74,022 | 0 / 0 / 0 |
| Core, level-interval boundary probes (writes 1-2 ms either side of the exact age at which the interval crosses a rule threshold, plus the 60 s clamp) | 5,028 | 0 / 0 / 0 |
| Bridge core, bytes in with preamble and FCS, frames out compared byte for byte including FCS (recorded + fuzz) | 15,321 | 0 mismatches; hardware counters equal the model's (3,018 mutated requests, 202 restored replies) |

Coverage across these: 21,503 request mutations and 1,112 response restorations at core level; every rule code 0-19 except
the unused 17 and R6 (hit once).

**Mutation testing of the testbenches** (perturb one constant in a scratch copy of the RTL, confirm a mismatch appears).
The first round exposed that random traffic never lands on the level-interval thresholds, so the fall-rate constant (53→54)
and the 60 s age clamp were *not* detected; the boundary probe set was added and all now are:

| Perturbation | Caught by |
|---|---|
| ack timeout 2000→2001 ms | fuzz (118 decision mismatches) |
| fall constant 53→54 | probes (388), recorded (1) |
| rise constant 315→316 | probes (115) |
| age clamp 60000→59999 | probes (6) |
| exemption `>`→`>=` | recorded (219), fuzz (6,663) |
| illegal function 0x7F→0x7E | recorded, fuzz, probes |
| restored exception code 3→4 | fuzz (1,112) |
| second incremental checksum word | fuzz (1,112) |
| refused-table expiry 10000→10001 ms | fuzz (**3 state mismatches only**; thin) |
| refused-table ring step | recorded, fuzz, probes |
| 9-byte response condition | fuzz |
| transmit: FCS boundary, CRC not updated, checksum bytes swapped, code byte patch | bridge fuzz (3,194 / 3,194 / 3,173 / 202) |

## Timing and area (out-of-context, XCK26, 125 MHz)

| Block | LUTs | Flip-flops | BRAM | DSP | WNS | WHS |
|---|---|---|---|---|---|---|
| v1 core (earlier) | 3,456 | – | 0 | 0 | +1.676 | +0.075 |
| **v3 core, first run** | 6,930 | 4,367 | 0 | 3 | **-0.067** | +0.055 |
| **v3 core, multiply retimed into three stages** | 5,923 (5.1 %) | 4,361 | 0 | 3 | **+1.063** | +0.046 |
| **v3 bridge core** | 8,078 (6.9 %) | 6,797 | 4 | 3 | **+0.667** | +0.064 |

The first run missed by 0.067 ns on the four-way product pump x sqrt(outlet) x age x 53. Splitting it into registered stages
changed no result (the full simulation was re-run, still 0 mismatches) and added two cycles.

Decision latency after the last byte of a frame (core, 125 MHz): up to 113 cycles (0.90 µs) for writes, fewer for reads
and responses. A v1 decision took 11 cycles. At 100 Mb/s a minimum frame lasts 6.7 µs, so this fits.

## What is not done

- The v3 bridge is not instantiated in `gate_bridge_io.sv` / `gate_bridge_top.v`, there is no v3 bitstream, and nothing
  of v3 has run on the board. The synthesis above is out-of-context, not a full implementation with pins and the MMCM.
- 1 Gb/s receive still needs the deskew clock (unchanged from the v1 bridge).
- The closed-loop experiments used the Python shell (`MutateShell` + `V3Core`), not the frame-level model that the RTL
  matches; the two parse frames slightly differently (the frame model is v1's stricter parser). Their agreement on policy
  behaviour was not directly tested.
- Refused-request table (8 entries, round-robin) and pending table (8 entries) are bounded; behaviour past those limits is
  specified and tested but only evaluated in the closed loop at the loads it generated.
- The level-rate constants and the rule set are tuned to the simulated plant.
- An LLM agent has been run against the *Python* gate in the closed loop (experiment 7 in the closed-loop write-up), not against the RTL.

## Reproduce

```sh
python scripts/v2/gate_v3_vectors.py --fuzz 40000
python scripts/v2/gate_v3_bridge_vectors.py
wsl bash simulation/v2/gate/run_gate_sims.sh corev3
wsl bash simulation/v2/gate/run_gate_sims.sh bridgev3
vivado -mode batch -source scripts/v2/gate/synth_gate_v3_ooc.tcl -tclargs <out> core|bridge 8.0
```

Evidence and sources of the timing runs: `build/v2/agent-gate-v3-synth/` (`core` is the failed first run, kept;
`core-r2` and `bridge-r2` are the retimed runs; `rtl.sha256` pins the RTL they came from; `code_snapshot/` has the sources).
