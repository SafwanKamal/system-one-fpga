# Agent command gate on the KR260: hardware plan (step 1), 2026-11-08

This plan follows the software go/no-go in `2026-11-08-agent-gate-gonogo.md`, which passed with both Qwen3-0.6B and Qwen3-4B agents. The open question now is whether the board itself contributes anything beyond the policy.

## Hypotheses the hardware must test

| ID | Claim | Falsified if |
|---|---|---|
| H1 | **Unbypassable from the AI side.** Root on the A53, or on the agent host, cannot get an unapproved write to the plant. | Any path from PS/Linux to the plant-side port that avoids the PL rule engine. This includes reprogramming the PL or the PHY at runtime, or DMA into the gate's state. |
| H2 | **Bounded latency.** Worst-case added latency is ≤10 µs per Modbus frame, and stays bounded under a flood at line rate. **Correction (2026-11-08, after review):** the built bridge shares one byte-per-cycle decision core between both directions (strict priority to port A), so it cannot sustain two simultaneously saturated 1 Gb/s inputs; at the 100 Mb/s the board runs today it has ample margin. The 1 Gb/s line-rate claim is withdrawn until a flood test and a second parser or wider datapath exist. | A Linux bridge with nftables, or a DPDK filter, matches it at p99.99 within 2x. |
| H3 | **Small trusted code base.** The enforcement TCB is ≥10x smaller than a Linux-hosted gateway. | — (a measurement: RTL lines + R5 firmware vs kernel + filter). |
| H4 | **Exact replay.** Every decision is logged and replays bit-exactly from the log against the integer specification. | Any replay mismatch. |

## Architecture

```
 agent / IT side                          KR260 PL (fabric)                              plant / OT side
 ┌──────────┐  RJ45 pl_gem2   ┌──────────────────────────────────────────────┐  RJ45 pl_gem3  ┌──────────┐
 │ LLM host │──RGMII PHY A────│ rx A ─ frame buf ─ PARSE ─ RULES ─ tx B      │──RGMII PHY B───│ PLC /    │
 │ (MCP)    │                 │                       │ state ↑               │                │ plant    │
 └──────────┘                 │ tx A ─ frame buf ─ PARSE(resp) ─ rx B        │                └──────────┘
                              │          decision log ─▶ R5 TCM (phase 2)    │
                              └──────────────────────────────────────────────┘
      PS GEM ports (other two RJ45): Linux management only, no path to pl_gem3
```

- **Store-and-forward L2 bridge** between the two fabric RGMII PHYs. There is no MAC address, IP stack or ARP on the enforcement path, so the gate is not addressable.
  - FCS is checked on receive. Unmodified frames are forwarded byte-identical.
  - Non-Modbus traffic is forwarded or dropped per a fixed allow rule: phase 1 forwards ARP and TCP/502 and drops everything else.
- **Parser.** Ethernet with optional 802.1Q, IPv4, TCP, MBAP, PDU.
  - **Agent → plant:**
    - FC3/FC4 reads are forwarded, and their transaction id and range are recorded.
    - FC6/FC16 writes go to the rule engine.
    - Other function codes, and malformed, fragmented or multi-ADU writes, are dropped (fail closed).
  - **Plant → agent:** FC4 responses update the observed level, temperature, pressure and flow through the matching transaction id.
- **Rule engine.** The frozen `stateful_rules` (R1–R7), in fixed-point integers:
  - inputs: observed readings (×10 for level and temperature, ×100 for pressure and flow); the actuator values the gate has forwarded itself; a ring of the last 4 pump-start times on a 1 ms counter;
  - the canonical specification is `src/sysone/v2/agent_gate/intspec.py`;
  - the RTL must be bit-exact to it.
- **Decision log.** Each write produces a record: time, transaction id, FC, address, values, allow/deny, rule id. Phase 1 exposes it on a FIFO; phase 2 sends it to R5 tightly-coupled memory, which the A53 cannot write.
- **Approval path (phase 2).** "Hold" instead of "drop". The R5 releases a held frame only when it matches, byte for byte, an approval hash delivered within a deadline.
- **Isolation (phase 2, for H1).** No AXI master or slave from the PS reaches the rule-engine state or the plant-side TX. Configuration is fixed at bitstream build, and the bitstream is authenticated at boot. The PS is denied PCAP/partial reconfiguration after boot. This needs checking against the K26 boot and dfx-mgr flow, since the current RC1 workflow loads overlays from Linux.

## Phases

1. **Offline (this step).**
   - Integer specification and its agreement with the frozen float policy.
   - RTL rule engine + parser + state tracker.
   - Verilator bit-exact check on every recorded go/no-go decision.
   - Frame-level parser test.
   - Out-of-context synthesis.
2. **Board bridge.** RGMII RX/TX with IDDR/ODDR at 1 Gb/s, DP83867 setup over MDIO (internal delays), dual-clock frame buffers, and pass-through validation (ping, iperf, byte-identical frames). This is the main bring-up risk.
3. **Inline gate on the bench.** Real Modbus/TCP traffic from the agent host through the KR260 to a plant simulator. Measure H2 under flood, and compare against a Linux bridge.
4. **Isolation and approval.** R5 log and approval, bypass attempts from root on the A53, TCB count.

## Bench needed for phase 2/3

At minimum:
- the laptop with a second Ethernet interface (a USB-Ethernet adapter is fine);
- two Cat5e/6 cables.

The laptop runs both the agent (port A side) and the Modbus plant simulator (port B side), in separate network namespaces or on separate interfaces. A Raspberry Pi or a second machine as the "PLC" would separate the two ends better.

Board programming follows the canonical `BOARD_STATUS.json` protocol. It displaces RC1 for the session, and RC1 is restored afterwards.
