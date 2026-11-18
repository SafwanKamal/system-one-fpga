# Persona 1: senior FPGA / reconfigurable-computing architect (FCCM/FPGA/FPL/TRETS reviewer)

Round 1. Inputs: repo_context.md, corrections.md (these take precedence), lit A–F. I also ran four novelty searches on 2026-11-08 (listed at the end).

## How a hardware PC will read this project

At an FPGA venue, two kinds of claim will be dismissed immediately:
- **"Fast LLM decode on a Kria."** A01, A02, A04–A07 already report 85–94% DDR bandwidth utilisation and 5–27 tok/s on the same K26 SOM. Our ~6 tok/s comes from one HP port (~4 GB/s of ~19 GB/s), so it is at parity at best.
- **"Determinism by construction."** Reviewers will say a fixed-order datapath is trivially deterministic. A33/DetLLM already shows bit-identical Qwen3-0.6B, the same model, across five GPU/CPU vendors.

What *is* hardware-novel here is narrower: an operating point where **CLB is 92–96% packed, DSP is 41% used, decode is bound by weight bandwidth, and the output must be bit-exact.** So a strong paper has to do one of two things. It can cut the bytes streamed per *useful* token without changing any output bit. Or it can add a property (integrity) using resources that are still free (DSPs, BRAM headroom, ARM time), not LUTs. My three niches follow from that.

### Baseline numbers (derived from corrections.md; please verify on the board)

- **Per decoded token:** ~125 ms layer stream + ~44 ms LM head ≈ 169 ms, which is ~6 tok/s.
- **16-token tool call:** decode ≈ 2.7 s.
- **Cold v9e call (6.9 s):** ≈ 2.7 s startup SHA + ~1.5 s prefill (62 tokens, so ~24 ms/token, about 1.5 weight passes per B8 group) + 2.7 s decode.
- **Warm call** (v15/v16 persistent service plus prefix cache, prefill −65%): ≈ 0.5 s prefill + 2.7 s decode. **Decode is about 85% of a warm tool call.** Anything that does not touch decode bytes is second-order.

---

## Niche 1: Schema-co-designed *exact* decoding (grammar jump-forward, allowed-subset LM head, lossless state-lookup speculation)

**(a) Claim.** On a bandwidth-bound edge-FPGA decoder, using the tool schema to skip, batch or verify tokens cuts weight passes per tool call by 2–3x and leaves the output token IDs bit-identical to plain greedy decoding (N/N exact-match against non-speculative controls). No new arithmetic is needed: the existing B8 prefill engine is reused and an LM-head row-gather mode is added.

**(b) Why it is not already done.**
- Grammar engines (XGrammar F10/B22, SGLang compressed-FSM F11, SynCode B23, DOMINO F12) run only on GPU or host CPU. My search for "grammar-constrained decoding FPGA LLM accelerator vocabulary pruned LM head" returned no hardware design. TensorRT-LLM still runs grammar backends on the CPU, and NanoSpec (arXiv 2605.26444) prunes only the *draft* vocabulary on GPU.
- Speculation on FPGA exists only on datacenter FlightLLM (F08, DATE'26) and for Mamba (A22/F09). Neither claims bit-exactness. My search for "speculative decoding embedded FPGA Zynq KV260 lossless prompt lookup" found nothing on an edge SoC; DFVG uses the FPGA only as the drafter, beside a GPU.
- GPU speculation cannot be bit-identical to non-speculative decode, because verify batch shapes change the logits (C12, C14, and our own llama-server divergences). On our datapath, greedy verification is exactly lossless. That is the paper's "only possible here" property.

**(c) Minimal experiments and metrics.**
1. **Offline gate, about 1 week, no hardware.** Replay the Qwen3 tool-call template over BFCL/200, the maintenance fresh/120 and the conditional/64 sets using the C reference's greedy traces. Measure:
   - the fraction of tokens that are grammar-forced (expect 40–60%);
   - the allowed-set size per constrained step (expect under 1k of 151,936 rows);
   - mean accepted length τ for a prompt/JSON-state suffix-match drafter (REST-style, F06);
   - from these, the projected weight passes per call.
2. **Hardware.** Add three features:
   - an LM-head *index-list* mode that gathers allowed rows (1,088 B each, 34 beats on the 256-bit bus);
   - forced-token injection into the B8 prefill path;
   - a verify mode that returns argmax for up to 8 positions.
3. **Metrics.**
   - Weight bytes per output token, and weight passes per call.
   - Decode-phase and end-to-end warm-call latency (p50/p90).
   - τ distribution.
   - LM-head time on constrained steps. Projection: 44 ms → under 1 ms for 1k rows, which removes about 26% of each constrained decode step.
   - **Exact-match rate against plain greedy decoding (must be 100%)**.
   - BFCL/maintenance task accuracy, which is unchanged by construction for pure verification. For forced-token jump-forward, report it separately, because DOMINO/B24 token-alignment effects apply.
4. **Back-of-envelope target (16-token call).** About 8 forced tokens go through 1–2 B8 passes (~0.3 s). About 8 free tokens, with τ≈2.5, take ~3–4 verify passes of ~190 ms layer stream plus the LM head (~0.8 s). Decode falls from 2.7 s to ~1.1 s (2.4x), and a warm call from ~3.2 s to ~1.6 s (2x).

**(d) Reused assets.** B8 prefill engine and 2-token attention scoring; bit-exact C-sim and board causal fixtures (they become the exactness oracle); ARM JSON validator (it becomes the grammar FSM and drafter); v16 prefix cache; the 328/328 exact-match harness; BFCL/maintenance benchmarks.

**(e) Engineering cost and main risk.**
- About 6–9 person-weeks. Most of it is ARM-side work (grammar FSM, drafter, scheduling). The PL changes are an address generator for row-gather, a mode bit and an argmax over ≤8 positions: about 1–3k LUTs.
- **Risk 1, CLB:** with 92–96% packing, even 2k LUTs can break 125 MHz closure.
- **Risk 2, free-text verify cost:** verifying free-text drafts needs a full-vocabulary LM head at k positions. If the LM-head engine is single-position, that costs k×44 ms and eats the gain. Mitigation: run the LM head through the B8 linear engine (one 165 MB pass for 8 positions), or verify only under grammar-restricted rows.
- **Risk 3, DDR efficiency on gathers:** gathered 1 KB rows may drop DDR efficiency to about 60–70% from 95%. That is irrelevant at under 1k rows.

**(f) Venue.** FPL 2027 (deadline around late March/April; fits a 4–5 month plan) or FCCM 2027 if a workshop or short version is ready by January. A full version goes to TRETS. A systems variant could go to MLSys/EuroMLSys.

**(g) Kill criterion.** Kill if the offline gate projects **under a 1.5x reduction in decode-phase weight passes** on BFCL/200 plus maintenance (forced fraction under 25% and τ under 1.6). Also kill if adding the PL modes cannot close timing at 125 MHz within two P&R iterations *and* the ARM-only subset (forced tokens via prefill, gathered LM head done by the A53) gives under 1.3x.

---

## Niche 2: Line-rate, lossless weight-stream authentication from spare DSPs (closing the TOCTOU gap with zero throughput cost)

**(a) Claim.** A Wegman–Carter MAC (NH/UMAC-style universal hash on DSP48E2 slices plus a per-tensor tag) on the 256-bit weight stream authenticates every weight byte on every token at the full ~4 GB/s. It uses about 32–64 DSPs and under 1k LUTs. It closes the post-load tampering gap (Rowhammer/PrisonBreak-style flips, C32), needs no model change (no perplexity cost), and removes the ~2.4 s startup SHA from the cold path.

**(b) Why it is not already done.**
- SILK (C30, arXiv 2608.26402; details checked by search) is the closest work. It uses an Ascon-PRF checker on a ZCU102. Its N=16 pipelined checker reaches **756 MB/s**, and its prototype ran at 725 MB/s, below the 800 MB/s its own 16×16 array needs. It also reports an INT8 cost of up to 0.17 perplexity.
- We need **~4 GB/s, about 5.3x SILK's throughput**, on a device with almost no LUTs free. Scaling a LUT-based Ascon pipeline 5x is not viable at 92–96% CLB. Moving the hash into DSPs is the architectural contribution.
- My search for "DSP-based universal hash MAC FPGA line-rate memory integrity neural network weights" found only NH-UMAC on Virtex-II slices (Yang/Karri/McGrew, ePrint 2003/215) and DSP48 used for CRC/SHA-3 XORs. I found no DSP-mapped MAC for accelerator weight streams.
- ShEF (C29) roots integrity in the boot chain but checks at load time. Startup-only SHA (our v16) has exactly the gap SILK names.

**(c) Minimal experiments and metrics.**
1. **NH datapath.** Per 125 MHz cycle the datapath takes 256 bits = 8×32-bit words, which gives 4 NH products of (a+k)·(b+k') in 32×32 → 64 bits, at about 4 DSP48E2 each. That is ~16 DSPs per 32-bit-ε lane. Use 2–4 Toeplitz lanes for ε ≈ 2^-64 to 2^-128 (32–64 DSPs).
2. **Tag check.** The per-tensor tag is finalised by AES/PRF in the CSU or on the A53 and compared with sealed tags. Tags are created at provisioning with a device key that is PUF/eFUSE-wrapped by the Zynq RoT.
3. **Release gating.** Policy is verify-before-release: the typed output/R5 path withholds a token if any tensor tag in that token's pass fails.
4. **Metrics.**
   - Added resources (DSP/LUT/FF/BRAM) and Fmax impact.
   - Decode slowdown, with a target of 0% (the hash sits off the critical path).
   - Detection rate for injected faults: 10^4 random single-bit flips, PrisonBreak-selected 5–25 flips, and flips in scales versus INT8 values (C33). All are injected in DDR after startup.
   - Detection latency, with a target of ≤ one token.
   - Cold-call time with startup SHA replaced by first-pass verification. Projection: 6.9 s → ~4.5 s.
   - A false-positive count over ≥10^6 tensor passes (must be 0).
5. **Contrast experiment.** Show that output-level checks miss small corruptions (SILK observed this too). With our bit-exact references we can count exactly how many flips produce identical outputs, which turns a known claim into a quantified one.

**(d) Reused assets.** Sealed read-only weight mapping and evidence seals; the existing SHA digests (as the provisioning reference); the 256-bit weight stream; R5/typed-output release gate (v2 assurance work); bit-exact fixtures for fault attribution.

**(e) Engineering cost and main risk.**
- About 7–10 person-weeks: RTL hash core about 2, integration and timing about 3, provisioning, key handling and CSU about 2–3, attack and fault campaign about 2.
- **Main risk:** tapping a 256-bit bus in a congested region. Mitigations: tap at the HP-port side before width conversion and constrain the core to a pblock over DSP columns.
- **Secondary risk:** security reviewers will check the MAC construction. Use a textbook UMAC/NH plus PRF construction with nonce = (tensor id, epoch) so we invent no crypto.
- **Fallback if the PL tap fails:** do periodic re-hashing on the A53 or R5. This is weaker and a worse paper.

**(f) Venue.** FPT 2027 (deadline around mid-year) or HOST 2027. A FPL 2027 short paper is possible if done early. A dependability angle (fault attribution) could go to DSN 2028.

**(g) Kill criterion.** Kill if (i) the core cannot close at 125 MHz without lowering the existing Fmax, *or* it needs more than 2k LUTs after two placement attempts, or (ii) measured decode slowdown is over 3%. Also check SILK's full text first. If it already reports a GB/s-class DSP or universal-hash variant, kill or re-scope to the fault-attribution study alone.

---

## Niche 3: Phase-resolved, calibrated energy of a verified edge-FPGA LLM, and when energy is just latency

**(a) Claim.** This would be the first calibrated, rail-level energy breakdown of an unmodified pretrained INT8 LLM on Zynq UltraScale+ fabric. It covers startup verification, prefill, the layer stream, the LM head and idle. It reports joules per *validated* tool call with and without exact prefix reuse and schema decoding, against TeLLMe v2 (same SOM) and Pi 5 / Orin Nano / on-board A53 running the same Qwen3-0.6B Q8_0.

**(b) Why it is not already done.**
- Edge-FPGA LLM papers report board envelopes or vendor estimates (E22–E24, A05/A06; TeLLMe's method is unverified).
- Nobody calibrates K26 telemetry against an external meter the way E06/E11 do for Jetson and Pi.
- Energy of exact cache reuse is unmeasured (E26–E30 measure latency or cost only).
- J per successful goal (E32/E33) has never been measured on FPGA.

**(c) Minimal experiments and metrics.**
1. Calibrate SOM_5V0 (and other INA rails) against an external DC power analyser at ≥1 kHz. Report MAPE and sampling coverage per E05.
2. Measure at three boundaries (SOM, carrier, wall) with idle subtraction (E10).
3. Report J/token by phase, J per warm and cold call, and J per *validated* call at coverage c, over BFCL/200 plus maintenance.
4. Report the energy saved by prefix reuse (70.7% fewer evaluated tokens) and by Niches 1 and 2 if available.
5. Report run-to-run variance. Determinism gives identical token sequences, so all variance is physical.
6. Baselines use llama.cpp at Q8_0 on Pi 5 and Orin Nano (15 W mode), with the same prompts and meter.

**(d) Reused assets.** The existing energy-methods study (MLPerf-Power boundaries), the persistent service, the prefix-cache harness, evidence seals and the benchmarks. New spend: a DC power analyser or Otii-class meter (about $0.5–3k) and Pi 5 and Orin Nano boards (about $0.6k).

**(e) Engineering cost and main risk.** About 4–6 person-weeks and no RTL. The main risk is scientific, not technical. FPGA power is nearly flat (static plus DDR dominate), so J ≈ P̄ × t, and the "breakdown" collapses to the latency breakdown. Expect about 0.6–1.9 J/token (E table), which loses on raw J/token to Hailo-10H (~0.27) and TeLLMe v2 (~0.007, author figure). The paper has to win on the boundary method and on J per validated call, not on efficiency.

**(f) Venue.** IEEE Embedded Systems Letters or an FPT 2027 short paper. ISLPED 2027 is better if the calibration methodology is the headline. Otherwise fold it into Niche 1 or 2 as their energy section (my preference).

**(g) Kill criterion.** As a standalone paper, kill if (i) phase-to-phase dynamic power differs by less than 10% of total board power, so energy carries no information beyond latency, or (ii) on-board telemetry cannot be calibrated within 5% MAPE. In either case, keep the measurement only as a section of Niche 1 or 2.

---

## Strongest niche and the trap

**Strongest: Niche 1 (schema-co-designed exact decoding).** It targets the term that dominates a warm tool call (decode, about 85%). It can be gated in one week offline, from traces we already have, before any RTL is touched. Most of the work is ARM-side, so the CLB risk is bounded. Its headline property, *lossless speedup with bit-identical output IDs proven N/N*, is genuinely impossible on batch-variant GPU stacks and unclaimed by the FPGA speculation papers (F08, A22). A credible result of 2–2.5x decode and 2x warm-call latency at 100% exact match, on a $350 board, is a solid FPL or TRETS paper. It also makes every other paper (energy, assurance) better.

Niche 2 is the cleanest *hardware-architecture* contribution: about 5x SILK's throughput using DSPs on a LUT-starved device. It is my second choice, and it should start in parallel once SILK's full text is checked.

**Trap: racing tok/s.** That means multi-HP-port bandwidth scaling, Q4/ternary, or DPR prefill/decode swapping to "catch" TeLLMe v2 and PD-Swap (25–27 tok/s on the same SOM).
- Each lever is already published (A02 for full-DDR utilisation, A05–A07 for ternary and DPR).
- Multi-port needs extra AXI datamovers and interconnect in exactly the CLB we lack. At 92–96% this is likely a multi-month timing-closure fight.
- The best case (about 2–4x, so 12–24 tok/s) still only reaches parity with prior work, and the reviewer verdict would be "incremental".

A secondary trap is a standalone "determinism on FPGA" paper. It is pre-empted by A33/DetLLM and C12–C14, and reviewers will call it trivial unless it is tied to something determinism *enables* (exact speculation in Niche 1, exact fault attribution in Niche 2).

---

## Searches run (2026-11-08)

1. "grammar-constrained decoding FPGA LLM accelerator vocabulary pruned LM head". No hardware grammar decoding found. Related: NanoSpec arXiv 2605.26444 (draft-vocabulary pruning on GPU), TeLLMe (runs the LM head on shared hardware, no constraints), TensorRT-LLM guided decoding on CPU.
2. "SILK TOCTOU ... Ascon streaming weight checker FPGA". SILK arXiv 2608.26402: the Ascon-PRF checker reaches 756 MB/s (N=16 pipelined), the prototype 725 MB/s, against an 800 MB/s requirement.
3. "speculative decoding embedded FPGA Zynq KV260 LLM lossless prompt lookup". No edge-SoC speculation found. DFVG puts the drafter on an FPGA with a GPU verifier; A01/A02 are bandwidth baselines only.
4. "DSP-based universal hash MAC FPGA line-rate memory integrity neural network weights". Found only NH-UMAC on Virtex-II slices (ePrint 2003/215) and DSP48 used for CRC/SHA-3. No DSP-mapped weight-stream MAC.
