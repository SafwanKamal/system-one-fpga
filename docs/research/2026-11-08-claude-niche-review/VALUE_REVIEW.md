# Second review: FPGA/SoC relevance × real-world value: Claude, 2026-11-08

This review answers one question. **Where does a Zynq UltraScale+ (KR260) ARM+FPGA SoC excel, *and* where could we give a notable, substantial upgrade over what already exists?** It takes into account the consolidated **RC1** default candidate, qualified on the board on 2026-11-08.

Inputs:
- the earlier review (`README.md`, `COMPARISON.md`);
- three new agent reports:
  - `value_A_landscape.md`: competing edge hardware, and where FPGAs win in industry;
  - `value_B_applications.md`: scouting for applications native to an FPGA;
  - `value_C_redteam.md`: an attempt to kill each candidate against today's commercial practice;
- a direct check of the repo's own ARM-CPU baseline.

Sources are tagged [V]/[S]/[U] in those files. Many are search-summary level, so verify before citing.

## 1. The fact that reorders everything

| Qwen3-0.6B Q8_0, batch 1 | Decode | Prefill | Source |
|---|---|---|---|
| **KR260 fabric decoder (RC1 / v9e)** | **≈169 ms/token (≈6 tok/s)** | ≈45 tok/s short prompts; ≈20 tok/s at 1,454 tokens | RC1 `BOARD_QUALIFICATION.md`, hardware recommendation |
| **KR260's own 4× Cortex-A53, llama.cpp** | **171 ms/token (5.85 tok/s)** | ≈10 tok/s | `build/v2/eval/kr260-generation-q8.json` (Oct 2026) |
| Raspberry Pi 5 CPU | ≈21.5 tok/s | — | value_A [S], informal |
| Jetson Orin Nano (INT4, TensorRT Edge-LLM) | ≈77 tok/s | ≈4,600 tok/s | value_A [V] |
| KR260 theoretical ceiling at all ~19 GB/s DDR4, Q8 | ≈21–26 tok/s realistic | compute-bound on DSPs | value_A [D] |

**The fabric LLM decoder gives no decode speedup over the CPU on the same board.** Prefill is 2–4.5x faster. Even a perfect rebuild using all of the DDR bandwidth reaches only Pi-5 class, against a ~$250 Orin Nano at ~13x and ~200x on prefill. Grammar forcing and a restricted LM head (earlier T1) speed up the A53, a Pi or an Orin just as much.

**Conclusion:** running the LLM on this fabric is research infrastructure, not a product advantage. Any target whose value depends on the LLM running *in fabric* fails the real-world-value test:
- T1 grammar-aware decoding as a speed paper;
- T3 auditing of fabric LLM outputs;
- T4 inline authentication of LLM weights;
- any tok/s or J/token work.

The red team reached the same verdict independently.

## 2. Where this hardware actually wins in deployed practice

From value_A, with evidence:
- **In-path, line-rate processing with deterministic latency:**
  - physics triggers at 50–200 ns;
  - HFT tick-to-trade at ~14 ns;
  - Azure SmartNICs on >1M hosts;
  - in-network ML adding ~221 ns;
  - TSN timing under 20 ns.
- **Direct high-rate I/O.** Multi-axis motor control loops at ~120 ns (vendor claim); RFSoC at 5 GS/s.
- **Assurance and longevity.**
  - Zynq US+ assessed for SIL 3, and up to ASIL C on automotive parts.
  - Supply through 2045.
  - Flight-qualified variants.
  - Hardware isolation between the PS, the PL and the R5 cores.

None of these wins is "model throughput per dollar". Every one is about **being physically in the I/O path, deterministic, independent of the main OS, and long-lived.**

Two cautions from the red team:
- **The OT loops we would guard run on millisecond budgets:** PLC scans, safe-torque-off at 2–30 ms, and a GOOSE trip at 3 ms with ~600 µs for the network. So "µs vs ms latency" is rarely the selling point by itself. FPGA network classifiers at nanoseconds are already published, so our 13 µs classifier does not set us apart on speed either.
- **"Survives compromise of the AI host" is not exclusive.** Any second device does it: an OT firewall, PLC limits, an MCU, or NVIDIA IGX Thor's SIL 3-capable safety island, which is on a TÜV path. **The KR260 itself is not SIL-certified.**

## 3. What survives both filters

### V1 (recommended): an inline gate for AI-agent commands to industrial controllers

**Problem, with real demand:**
- **LLM agents are being wired straight to PLCs.** Several open-source MCP servers already expose Modbus coil and register *writes* to LLM agents: [modbus-mcp](https://pypi.org/project/modbus-mcp/0.4.0/), [alejoseb/modbusmcp](https://lobehub.com/es/mcp/alejoseb-modbusmcp), [kukapay/modbus-mcp](https://enterprisedna.co/directories/mcp/kukapay-modbus-mcp), [iot-edge-mcp-server](https://github.com/poly-mcp/iot-edge-mcp-server).
- **The agents are unreliable.**
  - LLMs proposed unsafe OT actions in 10–70% of runs (Schall 2026).
  - On PLCBench (arXiv 2608.26882), agents sustained physical objectives in only 31.3% of 240 real-PLC episodes.
- **Regulators are paying attention.** CISA/NSA issued AI-in-OT guidance (Dec 2025).
- **Attacks use legitimate traffic.** FrostyGoop disrupted heating with valid Modbus commands.
- **Current guardrails share the agent's host.** RoboGuard, SafeGate and Schall's validator are software on the same host as the planner.
- **Commercial OT firewalls do not see plant dynamics.** Tofino-, Claroty- and Nozomi-class products allow-list function codes and register ranges per packet, so a write that is in range but unsafe for the current plant state passes.

**Design.** The KR260 sits as a transparent bump-in-the-wire between the IT/AI side and the OT side, on its own Ethernet ports, with no IP stack on the enforcement path.
1. **Fabric:** parses Modbus/TCP (later DNP3 and the GOOSE status bit) at line rate, then forwards, holds or drops each frame.
2. **Bare-metal R5:** keeps a live plant-state model from the read traffic it observes, and enforces a stateful policy: envelope, rate-of-change, interlocks, sequence rules.
3. **Human approval bound to the command:** an approved command is released only if it is byte-identical to what the human approved, within a deadline.
4. **Abstention:** a small calibrated model (the v1/v2 lineage) may only *hold or escalate*, never permit by itself.
5. **Replay:** every decision is sealed and bit-exactly replayable.

The LLM runs wherever is cheapest: an Orin, a PC, or the KR260's A53. It is untrusted by design.

**Why this hardware specifically.** Each property is a structural fit, not a speed claim:
- **Transparent multi-port inline forwarding** with deterministic worst-case latency under attack load. An MCU cannot do 1G inline transparently; a Linux box has jitter and a large attack surface.
- **A small trusted computing base (RTL + R5), isolated from Linux by hardware.** It is ~10–100x smaller than a Linux-hosted validator, and it can be replayed exactly.
- **Low cost:** about $350 for the KR260, against several thousand dollars for an IGX-class box (to verify). Supply runs to 2045.

**Substantial-upgrade claims (each falsifiable):**

| Claim | Against | Falsifier |
|---|---|---|
| Blocks ≥95% of *in-range but unsafe* write sequences in PLCBench- and Schall-style episodes at ≤1% false blocks | Static allow-list (Tofino-equivalent) | Gate beats the allow-list by <10 points |
| Gate holds/forwards with ≤10 µs worst-case added latency at line rate under flood | Suricata or DPDK inline IPS on x86 (p99.99) | Software stays <100 µs at p99.99. Then the latency claim is dropped, but the TCB/isolation claim remains. |
| Root on the A53 (or on the agent host) cannot cause an unapproved write | Software validator on the same host | Any bypass found by a fault-injection or red-team campaign |
| Trusted code base 10–100x smaller, and every decision replayable | Linux-hosted gateway or IPS | — (a measurement) |
| Same policy on an STM32 cannot forward 1G transparently on two ports with bounded latency | MCU gate | An MCU does it. Then the board is not the contribution. Report that honestly; the policy and benchmark remain the contribution. |

**What we already have:**
- typed-output path, R5 ownership with deadline/epoch/quarantine logic, AXI-Lite staging and formal proofs (typed200 line);
- raw-Ethernet RTL path (v1);
- µs classifier with calibrated abstention (v1);
- evidence and seal tooling;
- prefix-exact replay methodology (v14/v16).

The fabric LLM is not needed. If used, it is only the untrusted proposer in the demo.

**Novelty boundary:**
- Lanotte et al. (CSF 2020, arXiv 2105.10668) enforce PLC commands with an FPGA proxy, but against compromised PLCs, not AI proposers. They have no human-approval binding and no replay.
- CIGRE 2026 "SRIM" describes an inline FPGA IPS for GOOSE/SV. **Read the full text before committing.**
- There is no standard benchmark for unsafe AI-to-PLC commands, so building one is part of the contribution.

**Venues:** ACSAC/ICSS, CPSIoTSec, DSN, SAFECOMP, IEEE TII. Workshop first is realistic.

**Risks:**
- Reviewers may call it "a firewall with a schema". The answer is the stateful in-range results, the isolation evidence and the replay.
- The plant-state model's fidelity limits the policy.
- No SIL certification. State plainly that it is a *security* layer above the certified safety systems, not a safety function.

**First experiment (2–3 weeks, mostly software):**
1. Replay PLCBench's released pipeline, or a Modbus water-tank simulator, under three conditions: no filter, a static allow-list, and the stateful policy (in Python first).
2. Measure the in-range-unsafe catch rate and false blocks.
3. **Go** only if the stateful policy beats the allow-list by ≥10 points. Port to R5 + fabric only after that.

### V2 (conditional): bounded-latency inline protection for time-critical substation traffic

The KR260 gates IEC 61850 GOOSE status changes and Modbus setpoint writes inline. Fixed rules block; the model may only hold or escalate. The claim is that the worst-case added latency stays inside GOOSE's network share (~600 µs) under attack load, where software IPS cannot guarantee that.

- **Kill:** if DPDK/Suricata on cheap x86 stays <100 µs at p99.99, or if SRIM already does semantic gating.
- The red team marks inline ML blocking of trip traffic as dead (OT prefers passive monitoring, and GOOSE authentication exists). So V2 is a fallback or an extension of V1, not a lead.

### What to keep from the earlier review, re-scoped

- **Exactness and replay (earlier T1 identity proof, T3 commit format):** keep as V1's sealed decision log and replay checker, not as LLM work.
- **Fault attribution (earlier T2):** apply it to the *gate's* own model and state, not the LLM. It is workshop-level by itself.
- **Inline weight authentication (earlier T4):** only if the gate's encoder streams weights from DDR. Low priority.
- **The fabric LLM:** a stable research artifact (RC1) and the demo's untrusted proposer. Stop optimising it for speed.

## 4. Do not pursue (value filter)

1. LLM tok/s, TTFT or J/token on the KR260, including multi-HP-port rebuilds. The best case is Pi-5 class, against an Orin at ~13x.
2. Grammar-aware or speculative decoding framed as an FPGA contribution. It is portable to any CPU/GPU.
3. "Deterministic LLM on FPGA" (DetLLM covers it on GPUs). Auditing fabric LLM outputs (the LLM should not be on fabric).
4. µs-latency classification as the headline. Nanosecond FPGA classifiers exist, and OT budgets are milliseconds.
5. Claiming "safety" or SIL. The KR260 is not certified, and IGX Thor owns that position.
6. Condition monitoring at MHz rates. The KR260 has no fast ADC, so it needs extra hardware. Voice/command interfaces: no documented demand.

## 5. Bottom line

The KR260 is the right hardware for the **trusted, transparent, deterministic enforcement point in the I/O path**, not for the AI compute. The notable, substantial upgrade is a capability, not a speed-up. Today, LLM agents can write directly to PLCs, and existing protection is either per-packet allow-lists with no plant state, or software guardrails on the agent's own host. A hardware-isolated, stateful, human-approval-binding, replayable gate on a ~$350 board would close that gap.

The first experiment is software-only and decides go/no-go in about 2–3 weeks.
