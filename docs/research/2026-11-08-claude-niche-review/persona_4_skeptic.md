# Persona 4: the skeptic (program-committee member and feasibility/novelty triage advisor)

Round 1, written 2026-11-08. Inputs: repo_context.md, corrections.md (treated as authoritative), and lit_A through lit_F. I also ran five web searches for scoop risk (results at the end). I did not open the repository.

Constraints I am judging against: one PI, one student, two coding agents, one KR260, no GPU cluster (renting a single cloud GPU for baselines is fine), 3 to 6 months. The fabric is nearly full (CLB 92–96%, LUT ~60%), so any idea that adds substantial PL logic carries timing-closure risk. That alone can use up a month.

## 0. Three facts the team must settle before anyone writes an abstract

1. **The headline rate is ~6 tok/s, not 8.** Per token: ~125 ms of layer-weight streaming plus a ~44 ms LM head, about 169 ms. lit_A's table ("2.0 tok/s per GB/s", implied BW utilization above 1) and lit_F's claim that the LM head is "far off its own roofline" both rest on the old numbers. They are wrong and must not reach a paper. The LM head is about 26% of per-token time and already sits at its bandwidth floor. It gets cheaper only by evaluating fewer vocabulary rows or by skipping it entirely.
2. **Is the B8 prefill path bitwise identical to single-token decode?** Exact speculation (N11) and forced-token batching (N10) both need this. It does not follow from the 328/328 prefix-cache result. Test it directly with a gate test: same context, logits from a B8 verify pass versus logits from sequential decode, compared bitwise.
3. **Is the LM head batched across B8 positions** (one 165 MB stream serving 8 positions) or run per position? If per position, verifying 8 drafted tokens costs 8 × 44 ms, and speculation's economics change completely.

## 1. Deduplicated candidate niches (from all six "gaps" sections)

| ID | Niche | Raised in |
|---|---|---|
| N1 | Exact cross-request prefix/KV reuse with proven output identity ("cache-transparent" inference) | A-gap1, B-gap2, C-gap2, E-gap2 |
| N2 | Determinism by construction on FPGA vs. "priced" determinism on GPU (cross-platform determinism matrix) | A-gap2, B-gap1, C-gap1 |
| N3 | Determinism as evaluation methodology: pass^k collapses to pass^1, TARr@N = 1, variance moves to input perturbation | B-gap1 (τ-bench), C (E1) |
| N4 | Exact commit-by-hash replacing fuzzy verifiable inference (vs TOPLOC/SVIP); substitution auditing | C-gap3, C-gap4 |
| N5 | Closing the TOCTOU gap: streaming integrity check on the 256-bit weight bus | C-gap5, A-gap3 |
| N6 | Root-of-trust attestation of evidence seals (Zynq CSU, secure boot) | C (E6), A-gap3 |
| N7 | Fault injection with an exact golden model (Q8_0 scale vs. value bit flips, SDC classified via the JSON validator) | C-gap6 |
| N8 | Small-model numerics: Q8_0/MXINT8 sensitivity at 0.6B, top-2 logit margin as a divergence predictor | C-gap7, C (E7) |
| N9 | Q8 fidelity vs. 4-bit/ternary: what low-bit edge decoders lose on tool tasks | A-gap4 |
| N10 | Grammar-co-designed decoding in hardware: jump-forward, forced-token B8 batching, vocab-masked LM head | B-gap4, D-gap6, F-gap2 |
| N11 | Exact (bit-identical) speculative decoding with "free" drafters (prompt/JSON-state lookup, grammar runs) | A-gap8, F-gap1, F-gap3 |
| N12 | Activation sparsity (TEAL/CATS) on a DDR-streaming fabric | F-gap5 |
| N13 | Ternary/BitNet-2B4T on our determinism/integrity stack ("2B capability at 0.6B bytes") | F-gap6 |
| N14 | Multi-HP-port bandwidth scaling (2–4x decode) | A §3 |
| N15 | On-chip-resident System-1 classifier/head cascaded with the decoder on one fabric | A-gap7, F rank 7, D cascades |
| N16 | Typed, schema-validated JSON state as agent memory (vs. free-text compaction and KV reuse) | B-gap3, E (E29 comparison) |
| N17 | Decision heads over frozen hidden states vs. generation on the same 0.6B, with risk–coverage curves | B-gap5, D-gap7 |
| N18 | Replayable conformal escalation (a deterministic tier-1 makes the guarantee third-party checkable) | D-gap1, D-gap2 |
| N19 | On-device LLM-Modulo for OT: the LM normalizes and extracts typed slots, the rules engine plans; edge-first escalation with network-failure semantics | B-gap6, D-gap3, D-gap4 |
| N20 | Hardware-enforced action gating outside the LLM trust domain (R5 core) | D-gap5 |
| N21 | Calibrated rail-level energy for an FPGA LLM (SOM_5V0 vs. external meter, three boundaries) | A-gap6, E-gap1 |
| N22 | Energy per verified tool call / per successful task, including prefix reuse, compaction and abstention | B-gap7, E-gap2/3/6, F-gap4, A-gap5 |
| N23 | "Verified cold start" (time and joules to the first verified token) | E-gap4 |
| N24 | Fair comparison protocol vs. the cheap-board class (same Qwen3-0.6B Q8_0 on Pi 5, Orin Nano, the A53, and the KR260) | E-gap5 |

24 niches after merging. "Application-level eval in FPGA venues" (A-gap5) is folded into N22/N24.

## 2. Scores (1–5; scoop risk: 5 = low risk)

Nov = novelty vs. the cited literature; Feas = feasibility with existing assets in 3–6 months; Evid = strength of evidence obtainable; Venue = fit to a real venue; Scoop = scoop risk (5 = safe); Uniq = uses what is unique about this project.

| ID | Nov | Feas | Evid | Venue | Scoop | Uniq | Sum | One-line verdict |
|---|---|---|---|---|---|---|---|---|
| N10 grammar-co-designed HW decoding | 4 | 4 | 5 | 5 | 3 | 4 | **25** | Best single technical contribution; mostly ARM FSM + DMA row-gather, little new PL |
| N11 exact speculation, free drafters | 3 | 3 | 5 | 4 | 2 | 5 | **22** | Strong *only* bundled with N10; FPGA spec-decoding is now crowded (DATE'26, SPECTRA ICCAD'26, Cassandra) |
| N22 J per verified call (+N21) | 4 | 4 | 4 | 4 | 3 | 4 | **23** | Mandatory for any hardware paper; novel as a metric, not as a race |
| N21 calibrated rail energy (alone) | 2 | 5 | 4 | 2 | 4 | 2 | 19 | Methods section, not a paper |
| N1 exact prefix reuse identity | 3 | 5 | 4 | 3 | 2 | 5 | 22 | Data exists; needs SGLang deterministic+radix baseline or reviewers kill it |
| N2 free vs. priced determinism | 2 | 5 | 4 | 3 | 1 | 4 | 19 | DetLLM (same model) and the GPU deterministic-mode papers own this |
| N3 pass^k methodology | 3 | 5 | 3 | 2 | 3 | 4 | 20 | Nice paragraph; too thin for a paper |
| N4 exact commit vs TOPLOC | 3 | 5 | 4 | 3 | 3 | 4 | 22 | Good workshop paper; reviewers will say "hashing a deterministic output is obvious" unless the TOPLOC contrast is quantified |
| N5 streaming weight integrity | 2 | 2 | 4 | 4 | 2 | 3 | 17 | SILK already did it on a Xilinx Zynq; our CLB is full |
| N6 RoT attestation | 2 | 3 | 3 | 3 | 3 | 3 | 17 | Engineering (CSU signing); ShEF is prior art |
| N7 exact-golden fault injection | 4 | 4 | 4 | 4 | 4 | 4 | **24** | Underrated; ARM-side DDR bit flips need no new RTL; DSN/SELSE-shaped |
| N8 small-model numerics/margin | 3 | 4 | 3 | 2 | 3 | 3 | 18 | Supporting analysis only |
| N9 Q8 vs low-bit on tool tasks | 3 | 3 | 3 | 3 | 3 | 3 | 18 | Needs a 4-bit HW variant or is just a software study |
| N12 activation sparsity on fabric | 4 | 2 | 3 | 4 | 4 | 2 | 19 | Real gap but accuracy at 0.6B is unknown; needs layout + PL changes on a full fabric |
| N13 ternary + our stack | 2 | 1 | 3 | 3 | 1 | 2 | 12 | TeLLMe owns it; a new datapath; trap |
| N14 multi-HP-port scaling | 1 | 2 | 4 | 2 | 2 | 1 | 12 | Engineering; Hummingbird already at 93% of full DDR |
| N15 on-chip System-1 cascade | 3 | 3 | 3 | 3 | 3 | 4 | 19 | Integration story; v1/v2 lineage helps; cascades are saturated as ML |
| N16 typed JSON state memory | 3 | 4 | 3 | 2 | 3 | 3 | 18 | ACON/MemGPT neighbors; template benchmark is weak |
| N17 heads vs. generation | 3 | 4 | 3 | 3 | 3 | 3 | 19 | Fine ML workshop result if done on public data |
| N18 replayable conformal escalation | 4 | 4 | 3 | 3 | 2 | 4 | 20 | Conceptually clean, but "Replicable Conformal Prediction" (arXiv 2608.23638) appeared; move fast or merge |
| N19 LLM-Modulo for OT on device | 2 | 3 | 2 | 2 | 2 | 2 | 13 | IBM owns industrial agents; 0.6B capability is the weak point |
| N20 R5 action gating | 3 | 3 | 2 | 2 | 4 | 4 | 18 | Architectural claim with no attack evaluation |
| N23 verified cold start | 2 | 5 | 3 | 1 | 4 | 3 | 18 | One metric in a table; v16 already removed most of the cost |
| N24 fair cheap-board protocol | 2 | 4 | 4 | 3 | 3 | 2 | 18 | Needed as a baseline section, not as a contribution |

## 3. Top 5 and why

1. **N10 Grammar-co-designed decoding (jump-forward + forced-token B8 + masked LM head).** Searches found no FPGA work on this; the field is GPU-only (XGrammar, XGrammar-2, Gram2Token ICML'26, SGLang compressed FSM). It attacks real costs: about 26% of each token is LM head, and 40–60% of tool-call JSON tokens are grammar-forced. The gain is measurable as seconds per call, with outputs exactly equal to the unconstrained-then-validated baseline, which our bit-exactness lets us prove N/N. Most of the work runs on the ARM side (FSM, allowed-row list, DMA gather of LM-head rows), which keeps new PL logic small. Caveat (DOMINO/B24): we must report task accuracy under forcing, not just speed, and handle token-boundary alignment.
2. **N7 Exact-golden fault injection on a Q8_0 tool-calling decoder.** The cheapest high-quality evidence available. Flipping bits in resident DDR weights or scales from the ARM needs no RTL. Determinism means every deviation is attributable, which GPU SDC studies (C33, C34) cannot claim. The outcome taxonomy (masked / benign / JSON-invalid caught / silent wrong-but-valid call) ties directly to the "bounded reliability" thesis. Low scoop risk. A good DSN-W/SELSE/IOLTS short paper, and it gives the student an independent first-author paper.
3. **N22 (with N21) Energy per verified tool call.** This is not a contribution against TeLLMe; it is the price of admission to any FPGA venue. What can be novel is the metric and its composition: J per *validated* call at a stated boundary, with N10/N11/N1 savings itemized and outputs proven identical across all of those optimizations. It needs a calibrated external DC meter (E06/E11 protocol), which is a week of work and about $200.
4. **N11 Exact speculation with free drafters.** Prompt/JSON-state lookup plus grammar runs need no trained draft model. A bit-identical guarantee is something DATE'26, SPECTRA and Cassandra do not claim (Cassandra says "lossless", but on what hardware and with what proof is unclear). It is only viable if gate tests 0.2 and 0.3 pass, and it is strongest as section 2 of the N10 paper rather than standalone.
5. **N1 + N4 Cache-transparent, hash-committable inference.** The data mostly exists (328/328). It becomes publishable only with (a) SGLang `--enable-deterministic-inference` + radix cache as the GPU baseline on one rented GPU, (b) logit-level and hidden-state-hash equivalence rather than token IDs alone, and (c) the TOPLOC contrast (commit bytes, verification cost, detection of Q8→Q4 substitution and single bit flips). arXiv 2604.15409 already shows that FP16 KV-cache is not equivalent to recomputation on GPU, so the "GPU caching diverges" half is not new. Our half is the positive existence proof on an edge device.

Runner-up: N18 replayable conformal escalation. It is good, but the scoop risk is rising and it needs a public benchmark (FailureSensorIQ is the cheapest: an MCQA logit readout). Keep it as an option for the ML-side student.

## 4. Traps (attractive, but will get rejected or scooped)

- **Raw tok/s or J/token race.** TeLLMe v2: 25 tok/s at ~5 W, ~7 mJ/token (author figure). PD-Swap: 27 tok/s. Hummingbird: 93–94% of full DDR bandwidth. Pi 5 + Hailo-10H: ~0.27 J/token. We are at ~6 tok/s and plausibly 0.6–1.9 J/token, roughly 100x worse than TeLLMe v2 on J/token. Any abstract that leads with throughput or efficiency gets desk-compared and loses. Multi-HP-port scaling (N14) does not fix this; it reaches parity with work that already exists, at full-fabric risk.
- **Determinism alone.** DetLLM (NeurIPS'26) runs integer-only Qwen3-0.6B, the same model, bit-identical across nine platforms. Thinking Machines, SGLang deterministic mode, LLM-42, HEAL, EigenAI, Cankaya (ICML'26) and Tree-Based Invariant Kernels cover the rest. An FPGA with fixed reduction order is trivially deterministic, and a reviewer will say so in one line. Determinism is valuable only as an **enabler** of something measurable (exact speculation, exact caching, exact fault attribution, hash commits), never as the headline.
- **Maintenance planning with a 0.6B model.** Software Qwen3-1.7B scores 15/120 fresh and 0/64 crossed-conditional, while the rules engine scores 120/120. The benchmark is self-made and template-derived, and IBM (AssetOpsBench, PHMForge, FailureSensorIQ, Condition Insight) owns the venue's attention. A paper whose punchline is "rules beat the LLM" is a negative result in a domain someone else owns. Salvage only as a downstream demo (MaintIE/MaintNorm slot extraction feeding the rules engine) inside a hardware paper, not as a contribution.
- **Ternary port (N13).** TeLLMe owns "ternary on K26". It means a new datapath and a new model, and the novelty would have to come from elsewhere anyway.
- **"First Qwen on Kria / near-roofline decode on Zynq US+".** A01, A02, A04 and the TeLLMe papers already cover this. Saturated.
- **Streaming integrity (N5).** It looks like an obvious extension, but SILK did it on Zynq hardware with Ascon-PRF, a second edge-FPGA LLM security paper exists (arXiv 2604.22935), and it needs PL area we do not have.
- **Verified cold start and JSON-state memory as standalone papers.** Each is a table row. Reviewers will call them metrics engineering.

## 5. Bundling plan

**Flagship (FPL 2027 or FCCM 2027; TRETS as journal fallback). Working title: "Exact structured decoding on a $350 FPGA: grammar jump-forward, vocabulary-masked LM head and lossless state-lookup speculation for edge tool calls, with bit-identical outputs and per-call energy".**
- Contributions: N10 (core) + N11 (if the gates pass) + N1 (prefix reuse as the third exact optimization) + N22/N21 (J and s per validated call, at calibrated boundaries).
- Thesis: on a batch-invariant, bit-exact fabric, *every* latency optimization can be proven output-preserving N/N, which GPU stacks cannot do. That turns determinism from a claim into a verification tool.
- Evaluation: BFCL subset + JSONSchemaBench subset + a small real-text maintenance demo. Baselines: llama.cpp with grammar on the A53, Pi 5 and Orin Nano at matched Q8_0 (N24), and SGLang/XGrammar on one rented GPU for reference. Report absolute numbers at stated boundaries (E18 critique). Concede raw tok/s to TeLLMe up front.
- Expected result: per-call decode time down 2–4x, outputs identical 100%, energy per verified call itemized.
- Timeline: gate tests (week 1), ARM FSM + masked head (weeks 2–5), drafter (weeks 5–8), energy rig in parallel (weeks 2–4), writing (weeks 9–12). Roughly 3 months, and it fits a spring 2027 FPGA-venue deadline. Check actual deadlines; I have not verified them.

**Short paper 1 (student-led; DSN workshop / SELSE / IOLTS). "Exact fault attribution for an edge LLM tool-caller".** N7, plus N8's margin analysis as an explanatory variable (do flips cause divergence where the top-2 margin is small?). Needs no new RTL; 6–8 weeks.

**Short paper 2 (systems/reproducibility workshop, e.g. EuroMLSys or an MLSys/NeurIPS reproducibility workshop; post on arXiv early to stake the claim). "Cache-transparent and hash-committable: an equivalence audit of prefix reuse across FPGA, llama.cpp and SGLang deterministic mode".** N1 + N4 + N3 (pass^k/TARr@N reporting). Mostly existing data plus one rented-GPU week. Optional, depending on bandwidth: swap N4 for N18 (replayable conformal escalation on FailureSensorIQ) if the ML-side student prefers.

**Park:** N5, N6, N12, N13, N14, N19, N20 (future-work paragraphs). **Fold in as sections:** N3, N8, N15, N16, N23, N24.

## 6. Scoop-check searches (2026-11-08)

- FPGA grammar-constrained decoding: nothing FPGA found. GPU side active: XGrammar-2 (May 2026), Gram2Token (ICML 2026, https://icml.cc/virtual/2026/poster/62392). Risk: medium. An FPGA group could add jump-forward quickly.
- Bit-exact FPGA + prefix cache equivalence: nothing combined. arXiv 2604.15409 shows FP16 KV-cache not equivalent to recompute (GPU half done). DetLLM confirmed (https://neurips.cc/virtual/2026/178970).
- FPGA speculative decoding: SPECTRA (arXiv 2609.24847, ICCAD'26, 20-tile FPGA prototype); Cassandra (arXiv 2605.26558, lossless self-speculation for edge reasoning LLMs, HW co-design); DATE'26 tree spec on FlightLLM. Risk: high for "spec decoding on FPGA", lower for "bit-identical + free state drafters on edge SoC".
- Streaming weight integrity: SILK (arXiv 2608.26402) on Zynq; "Secure eFPGA-Enabled Edge LLM Inference" (arXiv 2604.22935). Risk: high.
- Conformal + reproducibility: "Replicable Conformal Prediction" (arXiv 2608.23638, unverified beyond snippet) uses LLM next-token logits. Risk for N18: medium-high.
