# Value review context (2026-11-08) — read repo_context.md and corrections.md too

## Current default candidate: Consolidated RC1 (deployed on KR260 2026-11-08)
v9e hardware (Qwen3-0.6B Q8_0, INT8 block32 activations, BF16 KV, FP32 attention, 2048 ctx, B8 prefill, 125/250 MHz) + v16 sealed persistent ARM service (startup SHA of all weights, exclusive lease, exact prefix reuse).
- Warm short tool call: 3.86 s (no cache), 3.11 s (prefix reuse); 5.56 s with per-request SHA.
- 1,454-token prompt: 76.5 s cold (prefill ≈ 20 tok/s), 5.4 s on exact-prefix repeat.
- 8,224 causal fixtures worst error 0; 18/18 exact parity.
- Decode ≈ 6 tok/s (125 ms layers + 44 ms LM head per token), single 128-bit HP port ≈ 4 GB/s of the K26's ~19 GB/s DDR4. CLB 92–96% full, DSP 41%.

## Critical baseline already in the repo
llama.cpp on the KR260's OWN quad Cortex-A53 CPU (Oct 2026, small Qwen-class model, likely Qwen3-0.6B): Q8 decode 5.78 tok/s, Q4 5.29 tok/s, first word ~5 s on short prompts. => On decode, the FPGA fabric decoder is roughly at PARITY with the ARM cores of the same board. Fabric wins on prefill and frees the CPU; no substantial decode upgrade.

## Other on-board assets
- v1: tiny classifier in fabric, 13 µs compute, ~75 µs wire-to-wire over raw Ethernet in simulation, 0.58 ms host round trip on Nexys; bit-exact; calibrated integer logits; OOS abstention.
- v2: transformer encoder (MiniLM-L6 class) RTL on KR260 at up to 200 MHz; INT8 encoder + R5 integer heads; p50 8.54 ms PL-only, 208.9 ms end to end (Linux overhead); typed outputs; R5 real-time core ownership (AMP), AXI-Lite staging, deadline/epoch/quarantine logic, formal proofs.
- KR260 board: K26 SOM (Zynq UltraScale+ XCK26: 4x A53, 2x R5F, ~256K LUT, 1248 DSP, 144 BRAM, 64 URAM), 4 GB DDR4, 4x GbE (2 with TSN-capable PL paths), SFP+ 10G, USB, PMOD, Raspberry Pi header, industrial-grade SOM, AMD markets it for robotics/industrial (ROS 2, TSN, machine vision, motor control).
