# Agent-gate board bridge: overnight report, 2026-11-08

Continues `2026-11-08-agent-gate-hardware-step1.md`. Goal: get the gate onto the KR260's two fabric Ethernet ports, as far as possible without the board password.

The board was **not accessed**. Board access needs the password through the established local dialog, so that step waits for you; see `build/v2/agent-gate-board-20261108/MORNING.md`.

## What exists now

| Item | Status |
|---|---|
| Bridge RTL | Done (`rtl/v2/gate/bridge/`): RGMII RX/TX, 10/100/1000 byte framing, dual-clock FIFOs, FCS check, store-and-forward with the original FCS kept, MDIO PHY bring-up, read-only AXI status window, test-only PHY-loopback injector |
| Simulation (Verilator) | All pass: rules 57,562 vectors / 0 mismatches; core 26,961 frames / 0; bridge at 1 Gb/s 3,000 frames / 0 errors; at 100 Mb/s 601 frames / 0 errors (forwarded frames byte-identical incl. FCS); loopback build at 100 Mb/s matches the Python prediction on all 30 counters plus final plant state |
| KR260 bitstreams | **Attempt 4 passes** at 10/100 Mb/s. Production WNS +1.161 / WHS +0.012 ns; loopback-test WNS +1.435 / WHS +0.010 ns; 0 critical warnings. 6,342 LUTs (5.4%), 4 BRAM, 1 MMCM. Pins generated from AMD's KR260 board files. |
| Packaging | `build/v2/agent-gate-bridge/deploy.tar` (sha256 `50e79933728c4ae6d59f49acb72ee6df2cc99789bcd4cb0b277914a1bb3994c1`): two dfx-mgr apps (`sysone-gate-bridge-prod`, `sysone-gate-bridge-loop`), board tool `gate_board.py`, loopback expectations, bench tools |
| Board session | Queue of 15 jobs prepared: inventory → loopback test → production + link watch → restore RC1 + RC1 smoke → close |
| Host tools | `scripts/v2/gate_host/gate_bench.py`: Modbus/TCP plant server (simulated physics), agent replay client, software gate proxy (Linux baseline). Localhost rehearsal: 150 agent writes, 97 passed and applied, 53 blocked, all logs consistent. Software decision ≈ 9.5 µs median in Python, vs 88 ns in fabric. |
| Tests | `tests/test_agent_gate.py`, `tests/test_agent_gate_models.py`: the software gate and the RTL reference model agree decision-for-decision (4 pass) |

## Timing closure history (all evidence kept in `build/v2/agent-gate-bridge/builds/`)

| Attempt | RX configuration | Result |
|---|---|---|
| 1 | 1 Gb/s, PHY RX delay on, center-aligned constraints | Hold fails on RGMII inputs (−2.31 ns): clock-buffer insertion up to 3.6 ns |
| 2 | 1 Gb/s, PHY RX delay off, Xilinx edge-aligned template | Hold fixed; port A setup −0.283 ns |
| 3 | 2 + 1.1 ns calibrated IDELAYE3 on data | Worse (−0.911 ns) and an IDELAYCTRL reset DRC. The BUFG insertion spread across corners (≈0.8 → 3.6 ns) nearly fills the 4 ns half-period, so no fixed delay can close both checks. |
| **4** | **10/100 Mb/s only**, PHY RX delay on, SDR constraints | **Pass** with wide margin |

**Known limitation.** 1 Gb/s receive needs a deskewed RX clock (an MMCM per port in zero-delay mode). The 1 Gb/s RTL path is simulated but disabled (`ADV_1000=0`) until then.

For the current bench this costs nothing: the laptop's USB adapter is a Realtek *Fast* Ethernet part (100 Mb/s max), and 100 Mb/s is typical for Modbus/OT links.

## Bench facts found

- KR260 jacks (AMD Kria notes):
  - J10A = PL GEM3 (port B, plant side)
  - J10B = PL GEM2 (port A, agent side)
  - J10C = PS GEM1
  - J10D = PS GEM0
- The laptop adapter shows **Disconnected** while RC1 is loaded. That is expected if it is on a fabric jack, since RC1 does not drive those PHYs. Job 08 will show link and speed on whichever fabric port has it.
- For the full gate test, port B also needs a link (a short cable from J10A to the free PS jack, with the plant simulator on the board's Linux). Until then the loopback build covers both PHYs and the gate path without cables.

## Next

1. **Morning board session (needs your password).** Loopback test, production link check, RC1 restore.
2. With the second cable:
   - plant server on the board's PS port;
   - replay agent episodes from the laptop through the gate;
   - in-fabric latency counters against the software-gate baseline.
3. Deskew-MMCM RX path for 1 Gb/s.
4. Isolation and approval work (H1/H3): the R5 decision log and bypass attempts from root on the A53.

## Board session 1 (2026-11-08, afternoon)

Evidence: `build/v2/agent-gate-board-20261108/results/` and `SESSION_NOTES.md`.

- **Queue corrected before the board was touched.** The overnight queue would have swapped the PL under the running RC1 service. It now drains `sysone-rc1.service`, checks owner 0 / vmas 0 / sealed 1, and restores through RC1's own initializer.
- **Gate on silicon.** Both gate images loaded (`operating`), status ID `6a7e0001`, MMCM locked.
- **Loopback test.** Every status word that could be read matched the simulation prediction exactly:

  | Counter | Value |
  |---|---|
  | A→B frames received through the PHY loopback | 444 |
  | B→A frames received | 317 |
  | Passed | 308 |
  | Blocked by R3 | 5 |
  | Malformed, FCS-bad, overflow | 0 |

  That needs working 100 Mb/s RGMII TX and RX on both PHYs, plus PHY loopback configured over MDIO.
- **Readout bug: 3 of every 4 status words read 0.** The RC1 overlay leaves the PS-side HPM0 width (AFI_FS, config-afi index 14) at 128-bit (0xA00); the gate's port is 32-bit. The link/PHY words are among the masked ones, so the production link check is inconclusive. Fix: the gate overlays now set index 14 to 0 (32-bit). No bitstream change.
- **RC1 restored.**
  - Starter image, then initializer re-run: "verified existing sealed model", full SHA in 1.74 s.
  - Service READY.
  - The launcher returned the correct live boot ID.
  - `BOARD_STATUS.json` recorded (rev 60) and released.
- **Next.** Session r2 (`build/v2/agent-gate-board-20261108-r2/`) installs the fixed overlay and re-runs the full loopback comparison and the link check.

## Board session r2 (2026-11-08): overlay fix confirmed

Evidence: `build/v2/agent-gate-board-20261108-r2/results/`.

- **AFI width fix works.** All 64 status words read correctly.
- **Loopback test: 30 / 30 counters match the simulation prediction, zero mismatches.**
  - The final simulated plant state also matches: lvl10 = 611, actuators [30, 78, 80, 100].
  - The injector sent 453 frames: 444 came back on A and 317 on B.
  - 9 deliberately corrupted frames were rejected as FCS-bad.
  - 187 frames were forwarded A→B and 121 B→A.
  - Gate latency was 79–94 cycles (0.63–0.75 µs at 125 MHz, store-and-forward).
  - Both PHYs were found over MDIO (DP83867, ID 2000a231, addresses 2 and 3) and configured.
- **Production bridge with live traffic.**
  - Port B (J10A, plant side) has link at 100 Mb/s.
  - In 20 s it received 121 real frames from the attached device: 116 dropped as non-Modbus, 5 passed, 0 bad.
  - Port A (J10B, agent side) has no link (nothing plugged in).
  - So the laptop cable is in **J10A**. For the agent→plant test it belongs in **J10B**, with the plant on J10A.
- **RC1 restored.** The initializer verified the existing sealed model. The service is READY (PID 31590) and a launcher query returned the correct boot ID. `BOARD_STATUS.json` rev 63, released.
