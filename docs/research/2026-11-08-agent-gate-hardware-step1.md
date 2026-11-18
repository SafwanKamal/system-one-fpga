# Agent command gate: hardware step 1 (offline RTL) — 2026-11-08

Plan: `2026-11-08-agent-gate-hardware-plan.md`. This step is offline only: no board access, programming or bitstream.

## Results

| Item | Result |
|---|---|
| Integer specification (`intspec.py`) vs frozen float `stateful_rules` | **7,562 / 7,562** allow/deny agreement (both go/no-go runs) |
| `gate_rules.sv` vs integer spec (Verilator 5.020) | **57,562 vectors, 0 mismatches**, including which rule fired. Vectors: 7,562 recorded + 50,000 threshold-biased random. |
| `gate_core.sv` vs Python frame model `frames.GateModel` | **26,961 frames, 0 mismatches** in forward/drop, rule and frame class |
| Decision latency | **11 cycles = 88 ns at 125 MHz** after the frame's last byte (plus store-and-forward of the frame itself) |
| K26 (`xck26-sfvc784-2LV-c`), OOC routed, 125 MHz | **3,456 LUTs (2.95%)**, 3,025 registers, 0 BRAM / DSP / URAM. **WNS +1.676 ns**, WHS +0.075 ns, 0 critical warnings. |
| Artix-7 100T (Nexys 4 DDR part), OOC routed, 125 MHz | 3,484 LUTs (5.5%), 3,024 registers. **WNS −1.037 ns**: closes at about 110 MHz. The critical path is the payload-length checks in `S_DEC` (15 logic levels), so one more pipeline stage would fix it. A 100 Mb/s OT link needs only a 12.5 MB/s byte rate. |
| RTL size | 412 lines of SystemVerilog (`gate_rules.sv` + `gate_core.sv`) |

What the frame traffic covers:
- Replayed operator and LLM episodes from both go/no-go runs, each write preceded by an FC4 poll and its response, so the plant level is learned from the wire.
- 10% of frames with VLAN tags.
- Edge cases:
  - ARP in both directions, pure TCP ACKs;
  - bad FCS, IP fragments;
  - MBAP length mismatch, two ADUs in one frame;
  - FC16 byte-count mismatch, FC16 with more than 4 registers;
  - TCP to port 503, UDP, FC5 coil writes, FC8 diagnostics;
  - unsolicited responses, non-502 traffic from the plant side.

Totals: 19,661 frames forwarded; 6,791 writes, of which 1,810 were denied.

## What this establishes, and what it does not

- **Established.** The frozen policy, Modbus/TCP parsing and plant-state tracking run in a small, fixed-function block. Its decisions are bit-identical to the reference, which is the basis of exact replay (H4). The block is far below 1% of the K26's resources beyond the MACs, and it also fits the Artix boards.
  - **Fabric scale is not the constraint.** Ports and isolation are.
- **Not yet established:**
  - H1 (unbypassable);
  - H2 (bounded latency on real links under flood);
  - H3 (TCB comparison);
  - anything on real PHYs.

  The core sees ideal byte streams. RGMII, the PHYs, clock-domain crossings and frame buffers are phase 2.
- **Same author.** The Python reference and the RTL were written by the same author. A second, independent Modbus parser, for example from Scapy or a pymodbus decoder, would strengthen the parsing claim.

## Next: phase 2, board bridge

1. **RGMII at 1 Gb/s** on both PL PHYs (`pl_gem2`, `pl_gem3`):
   - IDDR/ODDR;
   - RX clocks from the PHYs, TX clock from an MMCM with a 90° shift if the PHY adds no TX delay;
   - per-port preamble/SFD strip and insertion, FCS check and regeneration (reusing the v1 CRC32 logic).
2. **DP83867 setup over MDIO:** reset pins (`PL_GEM2_RESET_B`, `PL_GEM3_RESET_B`), RGMII internal delays, forced or auto-negotiated 1000BASE-T. Done once by a small fabric FSM, so no PS path is needed at runtime.
3. **Dual-clock store-and-forward buffers.** Two frames per direction in BRAM, with one gate_core arbitrated between directions (gaps of 12+ bytes between frames are guaranteed).
4. **Pass-through bring-up:** ping, iperf and byte-identical frame capture before enabling the gate.
5. **Board session under the canonical `BOARD_STATUS.json` protocol.** It displaces RC1, which is restored afterwards.

Bench needs: a second Ethernet interface on the laptop (or a second machine), two cables, and a decision on where the plant simulator runs.

## Files

- RTL: `rtl/v2/gate/gate_rules.sv`, `rtl/v2/gate/gate_core.sv`
- Specification and reference model: `src/sysone/v2/agent_gate/intspec.py`, `src/sysone/v2/agent_gate/frames.py`
- Vectors: `scripts/v2/gate_vectors.py`, which writes `simulation/v2/gate/vectors/` (11 MB, regenerable)
- Testbenches: `simulation/v2/gate/gate_rules_tb.sv`, `simulation/v2/gate/gate_core_tb.sv`, `simulation/v2/gate/run_gate_sims.sh` (WSL)
- Synthesis: `scripts/v2/gate/synth_gate_ooc.tcl`
- Evidence: `build/v2/agent-gate-hw-step1-20261108/` (OOC reports for both parts, Vivado logs, simulation output, source hashes)
