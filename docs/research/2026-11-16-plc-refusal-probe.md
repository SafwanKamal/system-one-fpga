# Refusal by function-code mutation: software Modbus server probe (2026-11-16)

This is the first experiment in hardware direction 1 (`reports/Hardware directions for inline OT gate.md`). Before building a bitstream, it checks whether real Modbus/TCP server stacks handle the gate's refused write safely. The gate refuses a write by rewriting its function code to 0x7F. A safe server answers with exception 01, keeps the session open, and does not apply the write.

Pre-registration and code snapshot: `build/v2/plc-refusal/run1-<server>/prereg.json`, which records the probe's sha256. The probe is `scripts/v2/gate/plc_refusal_probe.py`. Server provenance, with exact commits, is in `build/v2/plc-refusal/server_provenance.txt`.

## Design

Each server got 10,000 rounds on one TCP session:

- 8,171 refused writes (FC6, or FC16 with 1 to 4 registers), with the function code rewritten to 0x7F.
- 1,829 rounds of the alternative mutation (FC3 with quantity 0, which should return exception 03).
- A control FC6 write every 5th round.
- A read-back after every round, compared with a shadow copy of the registers.

After the probe, 1,000 writes from a stock pymodbus 3.16.2 client went through a Modbus-level `GateRelay`. The relay rewrites each write to 0x7F and turns the `0xFF/01` reply back into `fc|0x80` with exception code 03.

Pass criteria:

- **R1:** at least 99.99 % of refusals answered `0xFF/01`.
- **R2:** zero register changes.
- **R3:** no closures, timeouts, control failures or transaction-id mismatches.
- **R4** (reported only): the alternative mutation is answered `0x83/03`.

## Results

| Server (unmodified code) | R1 0x7F → FF/01 | R2 no write | R3 session | R4 alt → 83/03 | Refusal latency | Client through relay |
|---|---|---|---|---|---|---|
| OpenPLC_v3 runtime Modbus core (b5d41356) | 8171/8171 ✔ | 0 changes ✔ | ✔ | ✘ normal `03 00` reply, 1829/1829 | ~0.6 ms | 1000/1000 exception 03, session kept |
| libmodbus 3.2.0 reference server (a9b025d1) | 8171/8171 ✔ | 0 ✔ | ✔ | ✔ | **~500 ms**, then the input buffer is flushed | 1000/1000, session kept |
| pymodbus 3.16.2 server | 8171/8171 ✔ | 0 ✔ | ✔ | ✔ | sub-ms | 1000/1000, session kept |
| pymodbus 3.7.4 server | ✘ 0/8171: replies `A8 01` with transaction id 0 | 0 ✔ | ✘ txid mismatch on every refusal | ✔ | sub-ms | client raises a transaction-id error on the first refusal |

**No server applied a refused write.** That is 0 register changes across 32,684 refusals. A refusal fails safe on every stack tested. What differs between stacks is how the refusal is answered, not whether the write happens.

## Findings that change the RTL

1. **Add a timeout fallback that builds the refusal reply in the gate.** pymodbus 3.7.4 answers a function code it doesn't recognise with transaction id 0 and a wrong exception function code (0xA8). Neither the gate nor the client can match that reply to the request. The gate's pending-refusal entry therefore needs its own timer. When the timer expires, the gate synthesizes `fc|0x80, 03` toward the agent and discards any late or unmatched reply from the PLC. The same path covers a PLC that never answers at all.
2. **Tolerate a 500 ms refusal reply.** libmodbus deliberately sleeps for its response timeout and then flushes its input before sending any exception (`modbus.c`, `response_exception(..., to_flush=TRUE)`). This applies to both exception 01 and exception 03, so the alternative mutation is no faster. A refused write from a libmodbus-based device holds the session for about 0.5 s. Any request pipelined behind it in that window is discarded silently. The gate should therefore:
   - not count a refusal as uncertain until at least about 1 s has passed;
   - hold later requests until the refusal reply arrives, or until the timeout fallback in finding 1 fires, rather than pipelining them behind it.
3. **Don't depend on the alternative mutation.** OpenPLC answers FC3 with quantity 0 as a normal read with byte count 0, not exception 03. That would look like a successful read to the agent. Keep 0x7F as the only mutation.
4. **Restoring the exception works with a stock client.** On every conforming server, a standard client saw an ordinary `exception 03` and kept its session for all 1000 writes. This was the end-to-end property the mechanism needed.

## Kill criterion status

The pre-registered kill criterion is that more than one of three PLC implementations fails R1 to R3. It is decided on PLC hardware, not on software stacks. On software stacks the result is 1 failure out of 4: pymodbus 3.7.4, a legacy library version whose reply bug is fixed in current releases. Its failure is handled safely by finding 1. The mechanism is not killed, so the experiment moves on to PLC hardware.

## What hardware is needed next

- **At least three physical PLCs or controllers**, with the KR260 gate (or the `GateRelay`) inline. Candidates:
  - OpenPLC on a Raspberry Pi;
  - CODESYS Control (Raspberry Pi or Linux SL);
  - a Siemens S7-1200 with Modbus/TCP server blocks;
  - a Schneider M221;
  - any WAGO or Phoenix controller that is available.
  Record each device's answer to 0x7F in both RUN and STOP mode. A stopped WAGO is documented to answer every request with exception 01, which would hide the gate's refusal.
- **Snort 3 inline on the same link.** Rule 144:3 fires on function code 0x7F, so an inline IPS would drop the rewritten request. That needs a measurement, and a documented allow rule if it happens.
- **Unchanged rerun:** `plc_refusal_probe.py --server name=host:502 --rounds 10000 --client-check`, against each device in a fresh `run2-<device>` directory with a new pre-registration.
