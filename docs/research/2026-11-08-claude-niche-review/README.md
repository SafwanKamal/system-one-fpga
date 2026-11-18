# Literature review and research-niche selection: Claude, 2026-11-08

Independent review by Claude (Opus 5.5) with parallel sub-agents. It was written **before** reading the earlier ChatGPT/Codex niche review. Section 7 compares the two afterwards.

No board access, builds, training or paid compute were used. Sources are web literature plus a read of the repo state (`HANDOFF.md`, `BOARD_STATUS.json`, hardware handoff/recommendation docs, v9e HLS source). Several 2026 entries are unreviewed preprints, and some were checked only at abstract or snippet level; per-entry markers are in the appendix files. **Verify any number before it goes into a paper.**

## 1. Method

1. **Repo read.** Summarised in `repo_context.md`. Two coordinator corrections are recorded in `corrections.md`:
   - **Decode rate.** Real decode is about **6 tok/s**: ~125 ms of layer stream plus ~44 ms of LM head per token. The LM head is already at its bandwidth floor.
   - **LM-head interface.** In the v9e HLS, the LM-head command is batch-1. It accepts a vocabulary row range and returns argmax only.
2. **Six parallel literature agents**, 225 annotated entries, about 200 distinct works (186 unique arXiv IDs plus conference, journal and standards items). Each entry has a closeness score and a relation-to-us note.

   | File | Area | Entries |
   |---|---|---|
   | `lit_A_fpga_accel.md` | FPGA/edge LLM accelerators | 33 |
   | `lit_B_tool_slm.md` | Small-LM tool calling, structured output, agent memory | 39 |
   | `lit_C_numerics_trust.md` | Quantization, determinism, verifiable inference, integrity, faults | 35 |
   | `lit_D_maint_assurance.md` | Industrial maintenance LLMs, abstention, conformal, guardrails, cascades | 40 |
   | `lit_E_energy_bench.md` | Edge energy and benchmarking, prefix caching, cold start | 34 |
   | `lit_F_frontier.md` | Speculative/grammar decoding, ternary, sparsity, SSM/diffusion, KV compression | 44 |

3. **Agentic discussion, round 1.** Four personas each proposed three niches with kill criteria:
   - FPGA architect (`persona_1_fpga.md`)
   - verifiable-inference researcher (`persona_2_verifiable.md`)
   - industrial-assurance researcher (`persona_3_industrial.md`)
   - PC skeptic (`persona_4_skeptic.md`), who scored all 24 deduplicated gaps
4. **Round 2.** A moderator cross-examined the four, ran six targeted novelty searches, and produced a consensus ranking (`discussion_round2.md`).
5. **Coordinator synthesis.** This file adds my own judgement, the source check, and one target the moderator ranked differently.

## 2. Where the project actually stands against the literature

**What is no longer novel (do not lead with it):**

- **Fast LLM decode on a Kria/Zynq board.** Already published:
  - Li et al., DATE'25: LLaMA2-7B on a KV260 at ~85% of bandwidth.
  - Hummingbird, ICCAD'25.
  - TeLLMe v1/v2: ternary, 9.5 → 25 tok/s at ~5 W on the KV260, which uses the same K26 SOM as our board.
  - PD-Swap: 27 tok/s.
  - Qwen2.5-0.5B on the KV260 (arXiv 2504.17376).

  Our tok/s per GB/s is at parity, not beyond. On energy: TeLLMe v2's reported power and throughput imply roughly 0.19 J/token, but RC1 has no power measurement yet, so **no ratio can be stated** (the earlier "~100x" was an unmeasured estimate and is withdrawn).
- **Determinism / bit-exactness by itself.** Already covered:
  - *Eliminating Nondeterminism in LLM Inference via Integer-Only Arithmetic* (NeurIPS 2026) makes **the same model, Qwen3-0.6B**, bit-identical across GPU and CPU.
  - Thinking Machines' batch-invariant kernels, SGLang deterministic mode, LLM-42, cross-GPU bit-exact kernels (arXiv 2609.25624), and bit-exact verification via emulation (ICML 2026).
- **Small-model function calling as such.** TinyAgent, Octopus, FunctionGemma, xLAM, Hammer and ToolACE all exist. A Sept 2026 CPU benchmark of MCP-style tool calling in sub-2B models (arXiv 2609.07370) reaches our own conclusion: small models are bounded components, not trusted executors.
- **Maintenance LLM benchmarks.** IBM owns this area: AssetOpsBench, FailureSensorIQ, Condition Insight. Our template benchmark is circular, since the rules engine scores 120/120 because it generated the labels.
- **Load-time weight integrity.** SILK (arXiv 2608.26402) already demonstrates the TOCTOU gap on a Zynq/Caliptra prototype. It reaches ~0.7 GB/s with Ascon.

**What is genuinely distinctive about this project (the assets a niche must use):**

1. **A bit-exact, independently referenced, batch-shape-invariant generative decoder on a $350 SoC FPGA.** We have *already shown* that an optimization (exact prefix reuse) preserves outputs 328/328, where a CPU llama-server under caching did not (16 divergences). No FPGA LLM paper claims output identity under optimization.
2. **A decode path that is weight-bandwidth-bound but leaves DSP headroom.** DSPs are 41% used, though CLB is 92–96% packed. A row-addressable LM head (`token_base`, `rows` ≤ 8192) and a B8 prefill path already exist.
3. **A structured-output workload.** JSON tool calls are largely predictable tokens. JSON-state memory cut input tokens by 89.5%, and prefix reuse cut evaluated prompt tokens by 70.7%.
4. **An integrity and evidence culture.** Weight SHA, sealed read-only mappings, inference lease, seals on every experiment, and the R5-owned typed output path from the encoder line.
5. **A calibration and abstention lineage.** The v1 classifier folds temperature into the integer path; selective accuracy is 97.4% at 50% coverage.

**The niche is therefore in what exactness *enables*, not exactness itself.** The two directions with real headroom are (a) speedups that are provably output-preserving, and (b) third-party audit, fault attribution and replayable guarantees.

## 3. Viable targets (ranked)

The consensus from the discussion is reproduced in full in `discussion_round2.md` §2 (gate experiments, plans, kill criteria). This is the summary with my adjustments. "P" is the estimated probability of a publishable result.

| # | Target | One-line claim | Gate (≤2 weeks) | Venue | P |
|---|---|---|---|---|---|
| **T1** | **Exact schema-aware decoding** (flagship) | Token-level grammar forcing through B8 prefill, plus a grammar-range-restricted LM head, cuts decode for JSON tool calls by 1.5–2.3x on a KR260. Token IDs are N/N bit-identical to a masked-greedy reference. | Offline C-reference traces on BFCL/maintenance: forced fraction ≥ ~0.3, ≤16 contiguous ranges p95. Board test: B8-vs-sequential bitwise identity on ≥1,000 positions. | FPL'27 → TRETS | ~65% |
| **T2** | **Fault injection with exact attribution + TOCTOU demonstration** (student) | Each DDR bit flip in a Q8_0 tool-caller is classified as masked / caught / abstained / silent-wrong-valid with no ambiguity from nondeterminism. Startup-only SHA misses 100% of post-load tampering. | 500 random flips + 50 scale flips over 50 BFCL calls; 0 unexplained deviations, and ≥1% of flips not masked. | DSN-W / SELSE / SAFECOMP'27 | ~70% |
| **T3** | **Exact commit + cross-platform (FPGA↔GPU) replay audit** | Per-token hidden-state hash commitments from the board replay bit-exactly on x86 and GPUs. They detect small perturbations (single bit flips, Q8→Q4 swaps) that tolerance-based TOPLOC/SVIP accept by design. | CUDA port of the C reference (`--fmad=false`, hls::expf reproduced), bit-identical on 1k tokens; TOPLOC misses ≥1 of 3 attacks. | Verifiable-AI workshop'27 → MLSys'28 | ~50% |
| **T4** | **Line-rate weight authentication on spare DSPs** (conditional) | An NH/UMAC universal-hash MAC on DSP48E2s checks every weight byte on every token at ~3.5 GB/s, ≈5x SILK. It closes TOCTOU and removes the ~2.4 s startup SHA. | Read SILK in full; out-of-context synthesis + pblock placement into routed v9e: ≤2k LUT, no WNS loss. | FPT'27 / HOST'28, or a section of T2/T3 | ~40–50% |
| **T5** | **Calibrated energy per validated call** (required section) | Rail telemetry calibrated against an external meter. J per *validated* tool call, with the saving from each exact optimization itemised. | Calibrate SOM_5V0 against a meter; measure dynamic power per phase. | Section of T1/T2 (IEEE ESL only if phase power varies >10%) | high as a section |
| **T6** | **Replayable risk-controlled abstention** (conditional) | Conformal/LTT guarantees assume a fixed scorer. We measure decision flips under CPU/GPU batching and caching, versus a hash-replayable FPGA scorer. | Read RCP (arXiv 2608.23638) first; jitter census on FailureSensorIQ + BFCL relevance across llama.cpp/GPU configs; flip rate ≥0.1% somewhere. | SAFECOMP'27, or half of the T3 paper | ~40% |
| **T7** | **Typed extraction on real maintenance text** (workload) | A grammar-constrained on-fabric 0.6B extractor + rules verifier on MaintIE/MaintNorm gives fewer unsupported actions than 1.7–8B plan generation, with 0 unverified actions. | 200 MaintIE sentences: 0.6B within 5 F1 of MiniLM/CRF/1.7B. | Demo workload for T1; PHM Society'27 if strong | ~45% |
| **T8** | **(Horizon) Integer-spec decoder: same bits on FPGA and on DetLLM's GPU engine** | Port DetLLM's integer-only Qwen3-0.6B arithmetic to fabric, so a public GPU implementation reproduces the board's output hash. | Paper read + resource estimate of integer softmax/RMSNorm/RoPE in HLS against 92–96% CLB. | FPGA'28 / FCCM'28 | ~30% |

**Where I differ from the moderator:**

- **T8.** The moderator listed "DetLLM integer port" as *do not pursue now*. I agree it should not start before T1–T3 gates, but I keep it as a named horizon target. It is the only path to cross-vendor identity against an *external* reference. It also replaces our FP32 attention/softmax with integer logic, which is cheaper on fabric. If T3's FP32 replay hits trouble with hls::expf or denormals, T8 becomes the fix rather than a detour.
- **Speculative decoding.** With the current batch-1 LM head, verifying 8 draft tokens costs ~542 ms against ~169 ms per plain token. Speculation is net-negative until the LM head is batched. I agree it is a *stretch inside T1*, not a separate target. The batched head reuses the matvec batch-B path, so it is a bounded HLS change, but it must close timing at 92–96% CLB.
- **Exactness caveats to state up front in T1.**
  - A grammar-restricted head is exact against *masked* greedy decoding, not unconstrained greedy.
  - Only token-level forcing is lossless. Text-level jump-forward re-tokenizes and can change outputs, so report it separately.

## 4. How the targets compose

| Paper | Contents | Lead | Earliest submission |
|---|---|---|---|
| **A (flagship)** | T1 + output-identity invariant (prefix reuse ∘ forcing ∘ restricted head) + T5 energy section + T7 real-text workload | PI + agents | FPL 2027 (~Apr 2027) |
| **B (dependability)** | T2 + T4 (or a periodic re-hash fallback) + R5 typed-output gating + T5 numbers | student | DSN-W/SELSE (~Mar–Apr 2027); SAFECOMP if strong |
| **C (replayability)** | T3 + T6, later T8 | ML-side | workshop ~May 2027 → MLSys 2028 |

Infrastructure is shared across the papers:
- masked-greedy C reference and replayer (A, C);
- seal/Merkle format (B, C);
- BFCL + MaintIE + FailureSensorIQ harness (all);
- energy rig (A, B).

All the gates are mostly software and can run concurrently in weeks 1–2. Board time is needed for T1 gate 2, T2 and T4 placement. **Venue deadlines are typical-cycle estimates and have not been verified.**

## 5. Do not pursue

1. A raw tok/s or J/token race: more HP ports, Q4/ternary, partial reconfiguration. It is published, it only reaches parity, and it means a timing fight at 92–96% CLB.
2. "Determinism on FPGA" as the headline.
3. Speculation on the current batch-1 LM head.
4. "Verifiable"/"attested" wording at security venues while hashing runs on A53 Linux and weights are checked only at startup. Say "auditable/replayable" until T4 or CSU/PUF rooting exists.
5. The template maintenance benchmark as a headline, or complete-plan generation by a 0.6B model.
6. Activation sparsity, diffusion LMs, SSM/hybrid swaps, KV eviction. They give negligible gain for ≤64-token calls at ≤2k context.
7. Standalone papers on JSON-state memory, verified cold start, pass^k or cheap-board protocol. Each is a section.

## 6. Must-read before committing (verified to exist)

- [DetLLM, NeurIPS 2026](https://neurips.cc/virtual/2026/170003): integer-only Qwen3-0.6B; WikiText2 ppl 20.72 vs 20.95 fp16. Same model as ours.
- [SILK, arXiv 2608.26402](https://arxiv.org/pdf/2608.26402): TOCTOU closure on Zynq; ~0.68–0.76 GB/s.
- [arXiv 2609.07370](https://arxiv.org/pdf/2609.07370): CPU reliability benchmark for MCP-style tool calling in sub-2B models.
- TOPLOC (ICML 2025); bit-exact verification via emulation (ICML 2026); [arXiv 2609.25624](https://arxiv.org/pdf/2609.25624) cross-GPU bit-exact kernels.
- [XGrammar](https://arxiv.org/pdf/2411.15100) and [Gram2Token (ICML 2026)](https://icml.cc/virtual/2026/poster/62392): grammar decoding on GPU/CPU only.
- TeLLMe v2 and PD-Swap (KV260), Hummingbird (ICCAD'25): the speed/energy bar on the same SOM.
- [Replicable Conformal Prediction, arXiv 2608.23638](https://arxiv.org/pdf/2608.23638): scoop check for T6.
- AssetOpsBench, FailureSensorIQ, MaintIE/MaintNorm: the public industrial workloads to use instead of the template set.

## 7. Comparison with the earlier ChatGPT review

See `COMPARISON.md`, written after this file was finalised.
