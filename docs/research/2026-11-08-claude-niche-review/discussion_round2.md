# Round 2: cross-examination and consensus

Written 2026-11-08. Inputs: repo_context.md, corrections.md (authoritative, especially items 1 and 5), persona_1–4 round-1 files, and spot checks of the lit_*.md citation IDs. I did not open the repository.

Personas:
- **P1**: FPGA architect
- **P2**: verifiable inference
- **P3**: industrial assurance
- **P4**: PC skeptic
- **MOD**: moderator

## 0. New evidence for this round (6 web searches, 2026-11-08)

| # | Question | Finding | Effect on the debate |
|---|---|---|---|
| W1 | Is there FPGA or edge-hardware work on grammar-constrained or jump-forward decoding? | None found. Every hit is on GPU or host CPU: XGrammar (F10), Gram2Token (ICML'26, GPU-native masking), SGLang (F11). | The novelty claim for N10 stands, with the caveat "as of this search". |
| W2 | Is there an FPGA/edge-hardware hit for LM-head vocabulary skipping or JSON tool calling? | None found. Hits are generic KV260 decoders: arXiv 2502.10659 (~5 tok/s LLaMA2-7B), TeLLMe, Qwen2.5-0.5B on KV260, and pccx (alpha). | Confirms W1. |
| W3 | Has anyone shown bit-identical LLM outputs across FPGA and GPU? | None found. The GPU-only work is cross-GPU bit-exact GEMM kernels (arXiv 2609.25624, Ampere/Ada/Hopper), Tree-Based Invariant Kernels (2511.17826) and Cankaya (C25, ICML'26: bit-exact recomputation across NVIDIA variants in software). | FPGA↔GPU identity is open but narrow. The crowding is rising (2609.25624 is from September 2026). |
| W4 | What is SILK's throughput (C30, 2608.26402), and does it have a GB/s DSP MAC variant? | Pipelined Ascon-PRF checker: 756 MB/s. At N=128 (2^-128 forgery bound): 678 MB/s. End-to-end Caliptra-on-Zynq prototype: 725 MB/s (90.6% of its own requirement). It checks each byte **once, at weight load**. The snippets show no DSP or universal-hash GB/s variant, but the full text was not read. | Our stream needs ~3.5 GB/s, re-read every token: about 4.6–5.2x SILK's figure. This is not definitive until someone reads the SILK PDF. |
| W5–W6 | What is the scoop risk from "Replicable Conformal Prediction" (2608.23638)? | The paper exists. Only its reference list was retrievable. It cites Ndiaye (stable CP), Quach et al. (Conformal Language Modeling), prediction-churn work and the algorithmic-replicability literature (Karbasi et al.). | **Inference, not verified:** it most likely treats *statistical* replicability (sets stable under resampled calibration data or shared randomness), not hardware or runtime nondeterminism of the score function. Scoop risk for N18 is **medium**, and reading the full text is day-1 of N18's gate. |

### Technical fact that reshapes two niches (corrections item 5)

The LM-head command is batch=1. It takes a contiguous row range (≤8192 rows per call) and returns only the running argmax.

- **Restricted LM head.** This is a host-only change *if* the allowed sets are a few contiguous ranges. Scattered token IDs mean many calls, each with unmeasured fixed overhead.
- **Speculative verification without an HLS change.** It costs k × 44 ms of LM head per k-token verify. Arithmetic, using P1's estimate of ~190 ms for a B8 layer pass:
  - Verify k=8 costs ≈ 190 + 8×44 = **542 ms**. At τ=2.5 accepted tokens per pass, that is ≈ 217 ms per token, **worse** than plain decode (169 ms).
  - With a batched LM head (one 165 MB stream for 8 rows, ≈ 50–60 ms), verify costs ≈ 245 ms, or **≈ 98 ms per token at τ=2.5 (1.7x)**.
  - So speculation on free-text positions is net-negative unless the LM head is batched. That is an HLS change in a 92–96% CLB design.
- **Exactness: the right reference.** A grammar-restricted argmax equals the *masked-greedy* reference, not unconstrained greedy. The two coincide only on calls where unconstrained greedy is already grammar-valid at every step. Claims must name the reference.
- **Exactness: jump-forward.** Only *token-level* forcing is exactly lossless with respect to masked greedy: inject a token only when the grammar admits exactly one token ID. *Text-level* jump-forward re-tokenizes forced strings and can change the token sequence (DOMINO, F12/B24). It is a separate, non-identical variant and must be reported apart.

---

## 1. Debate, niche by niche

Candidates are the niches that at least one persona ranked in its top 3. Persona top-3s:
- **P1:** schema decoding; DSP MAC; energy.
- **P2:** exact commit; streaming authentication; output-identity invariant.
- **P3:** typed extractor; replayable conformal; out-of-domain gating plus fault injection.
- **P4:** N10; N7 fault injection; N22 energy. P4 also lists N11 and N1+N4 in its top 5.

### Niche A. Exact schema-aware decoding: N10 token-level jump-forward, restricted LM head and N11 state-lookup speculation
Ranked #1 by P1 and P4. P2's #3 overlaps it.

- **P1 (support):** "Decode is ~85% of a warm call, and this is the only lever that cuts *bytes per useful token* without touching arithmetic. Forced tokens through B8 prefill cost ~24 ms instead of 169 ms. That is 7x on every forced token, and most of it is ARM code."
- **P2 (support with conditions):** "The headline has to be 'output identical to a named reference, N/N, at logit-hash level', not 'identical to greedy'. Item 5 means restricted-head exactness holds against masked greedy. Say so, or a reviewer catches the conflation."
- **P3 (lukewarm):** "Seconds per tool call do not matter to a maintenance planner who waits minutes for a technician. This is a hardware paper. Fine, but don't sell it as industrial value."
- **P4 (objection, then support):** "Speculation is dead on arrival with a batch-1 LM head: 542 ms per 8-token verify loses to plain decode. Cut N11 from the plan of record unless the batched-head HLS change closes timing. N10 alone is still the best paper on the table, provided B8-prefill KV equals sequential-decode KV bitwise. The 328/328 result does not prove that."
- **MOD verdict: ADOPT as the flagship core**, narrowed to **N10 (token-level forcing plus range-restricted head)** as the plan of record. **N11 is a stretch**, gated on a batched-LM-head build. Expected decode-phase speedup:
  - Inputs: forced fraction f; constrained-non-forced fraction c, costing ~125 + ~3 ms; free fraction 1−f−c, costing 169 ms.
  - f=0.4, c=0.3 → ~99 ms per token, **1.7x**.
  - f=0.6, c=0.2 → ~74 ms per token, **2.3x**.
  - Speculation could add ~1.2–1.4x on top, only with a batched head.
  - **Honest range: 1.5–2.3x decode, 1.4–2.0x warm call.** The previous 2–4x claims are not supported.

### Niche B. Output identity as a proved invariant: N1 prefix reuse plus the optimizations in A, with a Lean model
P2 #3.

- **P1:** "The proof is a scheduling lemma: rows are pure functions of the prefix. It is a section, not a paper. The board evidence is what matters."
- **P2:** "A machine-checked equivalence statement plus a reusable equivalence-test harness is what MLSys reviewers lack. EXSpec and 2607.17283 show that GPU speculation breaks equivalence."
- **P3:** "Useful to us only as the precondition for replayable calibration: the score function stays fixed under caching."
- **P4:** "Reviewers will call the proof trivial. arXiv 2604.15409 already shows GPU KV-cache ≠ recompute. Keep the N/N evidence and an SGLang deterministic+radix baseline. Cap the Lean model at ~1 week."
- **MOD verdict: FOLD into A** as its correctness section. That covers the invariant statement, slot-k hidden-state hash equality and the SGLang/llama.cpp divergence census. The Lean model is optional, ≤1 week. No standalone paper.

### Niche C. Exact commit plus cross-platform replay audit vs TOPLOC (N4)
P2 #1.

- **P2:** "A $350 prover, a GPU verifier running teacher-forced prefill, and zero tolerance. TOPLOC and SVIP must accept small perturbations by design. W3 found no FPGA↔GPU identity result. One more point: our independent C reference on x86 is *already* bit-exact with the board, so FPGA↔CPU identity effectively exists today."
- **P1:** "Replaying hls::expf and FP32 op order on CUDA with `--fmad=false` is a few weeks of numerics, not research. The research content is the detection matrix."
- **P3:** "This is the hardware half of replayable conformal. I'd share one replayer between the two."
- **P4:** "Novelty is eroding monthly. Cankaya (C25) and 2609.25624 do cross-GPU bit-exactness, and DetLLM does cross-vendor bit-exactness on the *same model*. 'Hashing a deterministic output is obvious' is the default review. It survives only if TOPLOC measurably misses attacks that we catch, at comparable commit size. And any 'verifiable' claim with the hash computed by the A53 Linux is dead at a security venue."
- **MOD verdict: ADOPT as a secondary paper**, positioned as **"auditable / replayable"** at a systems or ML venue, not "verifiable" at a security venue unless the commit is PL- or CSU-rooted. The TOPLOC detection matrix is the gating result.

### Niche D. Line-rate weight-stream authentication from spare DSPs (N5)
Ranked #2 by P1 and P2.

- **P1:** "W4 confirms the gap. SILK peaks at 756 MB/s and checks once at load. We need ~3.5 GB/s on every token. NH on DSP48E2: 32×32 products at ~4 DSPs each, 2–4 lanes, so 32–64 of ~1,248 DSPs. About 736 DSPs are free."
- **P2:** "It composes uniquely with C: an authenticated weight stream is what makes an exact commit meaningful. It also deletes the ~2.4–2.7 s startup SHA from the cold path."
- **P3:** "I want it, but I'd accept an ARM periodic re-hash (639 MB at the measured ~2.4 s per pass) as the minimum viable TOCTOU closure for a dependability paper."
- **P4:** "This is the highest-risk item. The fabric is CLB 92–96%, and even the 'under 1k LUT' accumulators and tag logic sit next to a 256-bit bus in the most congested region. A second edge-FPGA LLM security paper exists (2604.22935). And nobody has read SILK's full text."
- **MOD verdict: CONDITIONAL.** Run a 2-week out-of-context synthesis plus incremental-placement gate first. If it fails, deliver the ARM/R5 periodic re-hash inside Paper B and stop. This is not a flagship: novelty is real, but feasibility is ≤50% by my estimate.

### Niche E. Calibrated energy and J per validated call (N21/N22)
Ranked #3 by P1 and P4.

- **P1:** "Required at any FPGA venue. But FPGA power is flat, so J ≈ P̄ × t, and the 'breakdown' may just replay the latency breakdown."
- **P2:** "Joules per verified call, with commits and authentication on, is a nice column. It is not my paper."
- **P3:** "Air-gapped OT boxes have power budgets. A calibrated number matters there, even if it loses on J per token."
- **P4:** "Expect ~0.6–1.9 J per token against ~0.007 for TeLLMe v2 (author figure): about 100x worse. Never lead with it. Budget about $200–3k for a meter."
- **MOD verdict: REQUIRED SECTION** of A, and also of B. It is not a standalone paper unless phase dynamic power varies by more than 10% of board power.

### Niche F. Typed extractor under a sound verifier on MaintIE/MaintNorm (N19)
P3 #1.

- **P3:** "MaintIE has no LLM results (S3), and the rules-plan, LLM-extract split is what industry deploys (D05). Public, human-authored data fixes our circular 120/120."
- **P1:** "A 0.6B decoder at ~6 tok/s doing NER: a CRF or the MiniLM encoder, which we also have on the fabric, will likely match it at 1/100 of the latency."
- **P2:** "No determinism leverage here, except as a reproducibility footnote."
- **P4:** "IBM owns the venue (AssetOpsBench, PHMForge, FailureSensorIQ). 'Encoder beats decoder' is the likely outcome. That is fine for a student paper, but not for the FPGA story."
- **MOD verdict: DEMOTE to a downstream demo and evaluation workload** for A and E: real-text, typed extraction feeding the rules engine. Pursue as its own PHM Society paper only if the 2-week gate shows the 0.6B with grammar within 5 F1 of the encoder or CRF.

### Niche G. Replayable risk-controlled abstention (N18, with N17 heads)
P3 #2. P4 runner-up.

- **P3:** "This is the one place determinism becomes a *safety* argument. A third party can replay calibration, threshold and every accept/abstain decision by hash. S5 found nothing linking scorer nondeterminism to conformal validity."
- **P2:** "It shares C's replayer and seal format. I'd co-author."
- **P1:** "No hardware contribution, and only a few board-hours. It doesn't belong in an FPGA venue."
- **P4:** "Two problems. First, RCP (2608.23638) is out, and we haven't read it. Second, the validity effect may be tiny: flip rates far below finite-sample slack. Then it is an audit-protocol paper. And if GPU deterministic mode is bitwise at under 10% overhead, the hardware adds nothing beyond a config flag."
- **MOD verdict: ADOPT CONDITIONALLY**, gated on reading RCP plus a jitter census. The best framing is "auditability", with validity as an upside. It pairs with C into one "replayable edge inference" paper.

### Niche H. Exact-golden fault injection, TOCTOU demonstration and out-of-domain gating (N7 + N20)
P3 #3, P4 #2.

- **P4:** "The cheapest high-quality evidence we have. Flip resident DDR weights or scales from the ARM, with no RTL. Every deviation is attributable, which GPU SDC studies (C33, C34) cannot claim. Good for a student first-author paper."
- **P3:** "Add the outcome taxonomy at the CMMS boundary: masked / benign / caught invalid / abstained / **silent wrong-valid**, with Clopper-Pearson bounds. Then show the R5 typed gate's marginal effect."
- **P2:** "The writable 'sealed' mapping from root on the A53 *is* the TOCTOU demonstration. It motivates D and C."
- **P1:** "No objection. Keep R5 gating to what is measured. 'Just a whitelist' is the risk."
- **MOD verdict: ADOPT as Paper B** (student-led), with D's ARM re-hash fallback, or the DSP MAC if D's gate passes, as its mitigation section.

---

## 2. CONSENSUS: ranked viable targets

Calendar anchor: today is 2026-11-08, and the gates run through about 2026-11-22. **All venue deadlines below are typical-cycle estimates and must be verified.**
- Passed or too soon: FPGA'27, DAC'27, MLSys'27, DSN'27 main.
- FCCM'27: about January 2027, tight.
- SAFECOMP'27: about February–March.
- ISLPED'27: about March.
- FPL'27, EMSOFT/ESWEEK'27 and DSN workshops: about April.
- PHM Society'27: about June.
- FPT'27: about mid-2027.
- MLSys'28: about October 2027.
- TRETS and IEEE ESL: rolling.

### T1 (rank 1, flagship). Exact schema-aware decoding on a bandwidth-bound edge FPGA

- **Claim.** Token-level grammar forcing through the B8 prefill path, plus a grammar-range-restricted LM head, cuts the decode-phase latency of JSON tool calls by **1.5–2.3x** on a $350 KR260. Generated token IDs are **N/N bit-identical** (token and logit-hash level) to a masked-greedy reference executing the same arithmetic. On calls where unconstrained greedy is already grammar-valid, they are also identical to unconstrained greedy.
  - Lossless state-lookup speculation is a stretch goal. It needs a batched LM head.
- **Novelty evidence.**
  - Grammar engines exist only on GPU/CPU: F10 XGrammar, F11 SGLang, B22/B23, F12 DOMINO, Gram2Token (ICML'26).
  - W1/W2 and P1/P4 searches found no FPGA or edge-hardware grammar decoding.
  - FPGA speculation papers (F08, F09, SPECTRA 2609.24847, Cassandra 2605.26558) claim no bit-identity.
  - GPU equivalence failures: C12–C14, EXSpec 2510.22876, our 16 llama-server divergences.
- **2-week gate experiment. All four must pass.**
  1. *Offline traces* (C reference, BFCL/200 plus maintenance fresh/120 and conditional/64). Measure:
     - forced fraction f, counting only singleton allowed sets;
     - constrained fraction c;
     - **number of contiguous token-ID ranges per allowed set** (p50/p95);
     - fraction of calls where unconstrained greedy is grammar-valid.

     **Pass** if the projected decode-phase speedup is ≥1.4x, i.e. roughly f ≥ 0.3 with c ≥ 0.2 and p95 ranges ≤ 16.
  2. *Board B8-vs-sequential identity.* For ≥1,000 positions, compare K/V and final hidden-state hashes of forced tokens run through cmd 8 (prefill) against single-token decode, at every slot k of B8. **Pass:** 100% bitwise identical. If not, the whole exactness thesis needs repair before any engineering.
  3. *Host-only restricted head.* Measure fixed overhead per range call, and the restricted-argmax equality to the full-head masked argmax (including tie-breaking across merged ranges) on 200 calls. **Pass:** overhead ≤ 1 ms per call and 100% equality.
  4. *Speculation feasibility probe (informational, does not block):* τ distribution for a prompt/JSON-state suffix drafter (F06 REST-style) on free-text argument positions.
- **Full plan (about 12 weeks).**
  - **Weeks 3–6.** ARM grammar FSM, built from the existing JSON validator, with precomputed per-state range lists in XGrammar style. Forced-run injection through cmd 8. Range-restricted head scheduling.
  - **Weeks 5–8.** Exactness harness:
    - N/N against the masked-greedy C reference, token IDs plus per-token logit/hidden hashes;
    - prefix-reuse composition, extending the 328/328 result;
    - divergence census for the same optimizations on llama.cpp CPU and SGLang deterministic+radix on one rented GPU.
  - **Weeks 6–9 (stretch, only if a ≤2-iteration timing closure is plausible).** Batched-LM-head HLS mode, reusing the matvec batch-B path, plus a B8 verify that returns argmax per row.
  - **Weeks 2–8, in parallel.** Energy rig (T5).
  - **Weeks 9–12.** Evaluation and writing:
    - BFCL/200, a JSONSchemaBench subset, and a small real-text maintenance extraction demo (T7 workload);
    - baselines: llama.cpp with grammar on the A53, Pi 5 and Orin Nano at Q8_0;
    - metrics: weight bytes per useful token, decode and warm-call p50/p90, J per validated call, task accuracy.
  - Text-level jump-forward is reported separately as non-identical, with an accuracy delta.
- **Reuse.** B8 prefill and 2-token attention scoring; the LM-head row-range command; bit-exact C reference and board fixtures; ARM JSON validator; v15/v16 persistent service and prefix cache; 328/328 harness; BFCL/maintenance benchmarks; evidence seals.
- **Risk and kill criteria.**
  - Kill if gate 1 projects <1.4x, or gate 2 shows any unexplained bitwise mismatch after 2 weeks of debugging.
  - Drop the speculation section if the batched head fails timing in 2 P&R iterations.
  - Main residual risk: reviewers may see it as "an engineering port of XGrammar". The counter is the bytes-per-token analysis plus provable exactness, which GPU stacks cannot offer.
  - **Probability of a publishable result: about 65%.** The f/c/range statistics are the unknown.
- **Venue and timeline.**
  - **FPL 2027** (full paper, about April 2027). Submission-ready about 2027-03.
  - A FCCM'27 short paper or poster in January is possible only if gates pass early and the speculation stretch is dropped.
  - Journal extension to TRETS.
- **Composition.** This is the flagship. T5 (energy) and B (identity invariant) are its sections, and T7 is its demo workload. A one-paragraph cross-platform replay check from T3 can strengthen the exactness claim.

### T2 (rank 2, student paper). Exact-golden fault injection and the TOCTOU gap in an edge LLM tool-caller

- **Claim.** With a bit-exact golden model, every deviation caused by DDR bit flips (Q8 values vs FP16 block scales, BF16 K/V) in a Q8_0 tool-calling decoder can be attributed to its injection. Report:
  - the masked / benign / caught-invalid / abstained / **silent wrong-valid** rate per injection, with Clopper-Pearson bounds;
  - that startup-only SHA misses 100% of post-load tampering;
  - the detection latency and overhead of a periodic re-hash (and of the T4 DSP MAC if it lands).
- **Novelty evidence.**
  - GPU SDC studies must separate faults from nondeterminism statistically (C33, C34).
  - PrisonBreak (C32) shows targeted flips matter.
  - SILK (C30) addresses integrity, not attributed action-level outcomes.
  - No FPGA LLM paper studies runtime integrity (A-gap 3).
- **2-week gate.**
  - Build the injection path: root on the A53 writes to resident weights, demonstrating that the sealed mapping is writable by a privileged attacker. Run **500 random single-bit flips** plus **50 scale-field flips** over 50 BFCL calls on the board, checked against the C reference.
  - **Pass** if outcomes are fully attributable (0 unexplained deviations) and at least one non-masked class has ≥1% incidence. A study where 100% of flips are masked is weak.
- **Full plan (6–8 weeks).**
  - 5–10k injections: random, PrisonBreak-selected 5–25 flips, and value vs scale vs K/V.
  - Outcome taxonomy at the typed output boundary, with and without the R5 gate and abstention head.
  - Top-2-logit margin as a predictor of divergence (N8).
  - Periodic re-hash on the A53 or R5: detection window vs duty cycle. With ~2.4 s per pass, 25% duty gives about a 10 s window.
  - Energy and overhead.
- **Reuse.** Bit-exact references; evidence seals; sealed mapping; JSON validator; R5 typed-output path; BFCL harness.
- **Kill criteria.**
  - Kill if the silent wrong-valid upper bound without the gate is already statistically indistinguishable from the gated bound. Then the R5 gate adds nothing, and the paper shrinks to a pure attribution study, which is still a workshop paper.
  - Kill if no DDR write path can be built without disturbing the inference lease.
- **Venue and timeline.** DSN 2027 workshops (DSML), SELSE or IOLTS (about March–April 2027). SAFECOMP 2027 if the R5 gating result is strong.
- **Composition.** This is Paper B. It absorbs T4 (either outcome) and the N20 gating claim. It motivates T3, since without stream authentication commits are hollow.

### T3 (rank 3). Exact commit plus cross-platform replay audit for edge LLM outputs ("auditable", not "verifiable")

- **Claim.** A per-call Merkle commitment of per-token hidden-state hashes from the FPGA can be replayed **bit-exactly** on x86 and on ≥2 GPU generations by teacher-forced prefill of a published arithmetic spec. It has zero false positives, and it detects perturbations such as single-bit weight flips and Q8→Q4 substitution that tolerance-based commits (TOPLOC C21, SVIP C22) are designed to accept. Verifier throughput should be ≥20–100x the prover's ~6 tok/s.
- **Novelty evidence.**
  - Tolerance-based schemes: C21, C22, DiFR 2511.20621.
  - Substitution auditing fails under nondeterminism (C24).
  - Same-stack GPU re-execution with a TEE (C26).
  - GPU-only bit-exactness: C25, 2609.25624, 2511.17826.
  - DetLLM gives cross-vendor identity but no edge prover and no commit protocol.
  - W3: no FPGA↔GPU identity found.
- **2-week gate.**
  - Port the C reference to CUDA: one thread per output row, sequential in-row order, `--fmad=false`, hls::expf reproduced from the Vitis source. Run 1,000 tokens.
  - In parallel, run a TOPLOC pilot on 3 attacks (one INT8 value flip, one FP16 scale flip, Q8→Q4_K).
  - **Pass** if GPU replay is 100% bitwise identical and TOPLOC misses ≥1 of the 3 attacks at its recommended thresholds.
- **Full plan (6–8 weeks).**
  - Normative arithmetic spec; replayer on x86, A53 and 2 GPU generations at ≥10k tokens.
  - Commit cost: bytes per call and ms per token on the A53.
  - Detection matrix (7 attacks × 3 schemes, TPR/FPR, minimum detectable perturbation); spot-check economics.
  - Stretch: CSU/PUF-signed root.
- **Reuse.** Unchanged v9e decoder; independent C reference, already bit-exact to the board on x86; evidence seals; BFCL/maintenance traces; llama-server divergences as motivation.
- **Kill criteria (week 4).**
  - GPU replay is not bit-identical after spec cleanup;
  - replay is <20x faster than generation;
  - TOPLOC catches every attack at comparable commit size. Then it becomes a cost-only story and is folded into T1 as one paragraph.
- **Venue and timeline.** A NeurIPS/ICML 2027 verifiable-AI workshop (about May–June), then MLSys 2028 (about October 2027). USENIX Security only with the commit PL- or CSU-rooted and TOCTOU closed (T4).
- **Composition.** This is Paper C, "Replayable edge inference", together with T6. It shares the replayer and seal format.

### T4 (rank 4, conditional). In-stream DSP universal-hash weight authentication at line rate

- **Claim.** An NH/UMAC-style universal hash mapped onto DSP48E2s authenticates every weight byte on every token at ~3.5 GB/s (≈4.6–5.2x SILK's 678–756 MB/s). It uses 32–64 DSPs and <2k LUTs, with 0% decode slowdown and zero model change. It replaces the ~2.4–2.7 s startup SHA.
- **Novelty evidence.**
  - C30 SILK, with W4 figures; the snippets show no GB/s DSP variant.
  - C29 ShEF checks only at load.
  - Tessera 2604.23205 leaves integrity as future work.
  - P1's search found no DSP-mapped weight-stream MAC.
- **2-week gate.**
  - Day 1–2: read SILK's full text for any GB/s, DSP or universal-hash variant. If one exists, kill or re-scope to T2's fault-attribution study.
  - Week 1: out-of-context synthesis of the NH core.
  - Week 2: incremental placement into the routed v9e design in a pblock over DSP columns, tapping at the HP-port side.
  - **Pass** if it closes at the existing clocks, uses ≤2k LUTs, and other paths lose ≤0 ns of WNS.
- **Full plan (8–10 weeks).**
  - Tag provisioning under a device key wrapped by the Zynq RoT; PRF finalisation in the CSU or R5.
  - Verify-before-release through the R5 typed path.
  - Attack campaign, shared with T2; ≥10^6 tensor passes with 0 false positives.
  - Cold-start accounting.
  - Security argument from textbook UMAC with nonce = (tensor ID, epoch).
- **Kill criteria.**
  - Gate fails;
  - decode slowdown >3%;
  - SILK already covers it.

  Fallback: periodic re-hash on the A53/R5 inside T2.
- **Probability of passing the gate:** about 40–50%.
- **Venue.** FPT 2027 or HOST 2028 standalone. Otherwise a section of T2, which then becomes a SAFECOMP or DSN paper, or of T3, which then becomes security-venue-eligible.
- **Composition.** This is the enabler that upgrades T3 from "auditable" to "verifiable".

### T5 (rank 5, required section, not a standalone paper). Calibrated energy per validated tool call

- **Claim.** A calibrated rail-level energy breakdown (SOM / carrier / wall boundaries, idle-subtracted), reporting **J per validated tool call** with each exact optimization itemised: prefix reuse (−70.7% evaluated tokens), T1 forcing, and T4 if built.
- **Evidence.**
  - Edge-FPGA LLM papers report board envelopes only (E22–E24).
  - Calibration methods exist for Jetson and Pi (E05, E06, E11), not for K26.
- **2-week gate.** Buy a meter (about $200 for USB-C and shunt, up to about $3k for a DC analyser). Calibrate SOM_5V0 telemetry against it at ≥1 kHz. Measure dynamic power per phase: idle, SHA, prefill, layer stream, LM head.
  - **Pass for a standalone paper:** MAPE ≤ 5% and phase-to-phase dynamic power differs by >10% of board power.
  - Otherwise it stays a section of T1 and T2. This is the likely outcome, given flat FPGA power.
- **Plan (4–6 weeks, no RTL).** Three boundaries; same-prompt baselines on the A53, Pi 5 and Orin Nano (about $0.6k of boards); run-to-run variance. Determinism means all variance is physical.
- **Kill or limit.** Never compete on J per token. Expect 0.6–1.9 J per token against TeLLMe v2's ~0.007 (author figure).
- **Venue.** A section of T1. An IEEE ESL letter only if the standalone gate passes.

### T6 (rank 6, conditional). Replayable risk-controlled abstention on public benchmarks

- **Claim.** With a bit-exact scorer, calibration, threshold and every accept/abstain decision can be replayed and checked by hash. On common CPU/GPU stacks, batching and prefix caching cause score jitter and decision flips near the threshold. We quantify these, and their effect on stated coverage when calibration and deployment configurations differ.
- **Novelty evidence.**
  - Guarantee frameworks are silent on scorer nondeterminism: D21, D22, D37–D39.
  - D24 reports AUROC only on BFCL.
  - S5 found no link between nondeterminism and conformal validity.
  - **RCP (2608.23638): likely statistical replicability, not verified.**
- **2-week gate.**
  - Day 1: read RCP in full. If it covers runtime/hardware score nondeterminism or audit replay, kill or merge into T3.
  - Days 2–10: jitter census on a **1,000-item FailureSensorIQ (D01)** subset plus BFCL relevance, across 6 llama.cpp CPU configs (threads 1/8 × batch 1/8 × prompt cache on/off) and GPU default vs deterministic mode on one rented GPU.
  - **Pass** if the decision-flip rate is ≥0.1% at the calibrated threshold in at least one realistic config, *or* if GPU deterministic mode costs ≥10% overhead (auditability-only framing).
- **Plan (6–8 weeks).**
  - Cross-config validity over 1,000 splits at α = 0.05–0.2 (split CP and LTT).
  - Audit protocol with Merkle-rooted calibration sets; auditor cost.
  - Integer-folded temperature vs probe heads (N17), with ECE and AURC.
  - A few board-hours of replay.
- **Kill criteria.** Flip rate <0.1% everywhere, coverage inside the finite-sample band, *and* GPU deterministic mode at <10% overhead. Then fold one paragraph into T3.
- **Venue.** SAFECOMP 2027 (about February–March; tight) or as half of Paper C (MLSys 2028 or a verifiable-AI workshop).
- **Composition.** Shares the replayer and seal format with T3. Best as one "replayable edge inference" paper.

### T7 (rank 7, demo workload, optional student paper). Typed extraction on real maintenance text feeding the rules engine

- **Claim.** On MaintIE/MaintNorm (D06, D07), a grammar-constrained 0.6B on-fabric extractor plus a rules planner/verifier gives fewer unsupported actions than complete-plan generation by 1.7B–8B models, with 0 unverified actions by construction.
- **Evidence.**
  - MaintIE has no LLM results (S3).
  - D05 (Condition Insight) is the cloud analogue.
  - D28 LLM-Modulo.
- **2-week gate.** Run 200 MaintIE sentences through the 0.6B (few-shot plus grammar), the MiniLM slot head, a CRF and Qwen3-1.7B. **Pass** if the 0.6B is within 5 F1 of the best small baseline at equal coverage.
- **Plan.** 7–9 weeks if pursued, per P3's E1.1–E1.4.
- **Kill.** Trailing by more than 5 F1 → use the encoder. It stays only as T1's real-text workload.
- **Venue.** PHM Society 2027 (about June) or IEEE TII.
- **Composition.** The workload for T1's demo and T2's injection campaign. It replaces the circular template benchmark as the headline data.

### How the targets compose (3 papers, 1 flagship)

| Paper | Contents | Lead | Venue | Earliest submission |
|---|---|---|---|---|
| **A (flagship)** | T1 + B (identity invariant) + T5 (energy section) + T7 (workload) | PI + agents | FPL 2027 → TRETS | about 2027-03/04 |
| **B (dependability)** | T2 + T4 (DSP MAC or re-hash fallback) + R5 gating + T5 numbers | student | DSN-W / SELSE / IOLTS 2027, or SAFECOMP 2027 if strong | about 2027-02 to 04 |
| **C (replayability)** | T3 + T6 | ML-side student or PI | verifiable-AI workshop 2027 → MLSys 2028 (USENIX Security if T4 lands and the commit is PL/CSU-rooted) | about 2027-05 (workshop) |

Shared infrastructure, built once:
- the masked-greedy C reference and replayer (A, C);
- the evidence-seal and Merkle format (B, C);
- the BFCL + MaintIE + FailureSensorIQ harness (all);
- the energy rig (A, B).

Gates for T1, T2, T3, T4 and T6 can run concurrently in weeks 1–2. Most are software-only. Board time is needed for T1 gate 2, T2 and T4's placement.

---

## 3. Do not pursue (with reasons)

1. **Raw tok/s or J/token race (multi-HP-port scaling, N14).** TeLLMe v2 reaches 25 tok/s at about 5 W, PD-Swap 27 tok/s, and Hummingbird 93% of full DDR. The best case of 2–4x (12–24 tok/s) only reaches parity, and it means a multi-month timing fight at CLB 92–96%.
2. **Ternary/BitNet port (N13).** TeLLMe owns "ternary on K26". It needs a new datapath and a new model.
3. **"Determinism on FPGA" as a headline (N2).** DetLLM covers the same Qwen3-0.6B bit-identically across vendors, and C12–C14, C25 and 2609.25624 cover GPUs. Use determinism only as an enabler (T1, T2, T3, T6).
4. **Speculative decoding with the current batch-1 LM head.** It is arithmetically net-negative (~217 vs 169 ms per token at τ=2.5). Pursue only after a batched head closes timing.
5. **Claiming text-level jump-forward as exact.** Re-tokenization changes token sequences (F12/B24). Report it as a separate, accuracy-evaluated variant.
6. **"Verifiable" or "attested" at a security venue while hashes and seals run on the A53 Linux and weights are checked only at startup.** It would be rejected on threat model. Use "auditable/replayable" until T4 or CSU rooting exists.
7. **The template-derived maintenance benchmark as headline, in either direction.** The rules engine's 120/120 is circular. Keep it only as a stress test.
8. **Complete-plan generation by the 0.6B, or "LLM-Modulo for OT" as the main contribution (N19 as a paper).** It is capability-limited (1.7B scores 0/64 conditional), and IBM owns the venue.
9. **DetLLM integer-spec port (P2's Option B) now.** It costs 4–8 weeks of HLS on a full fabric, has ppl implications and depends on external code. Revisit only if T3's GPU replay fails because of FP32/expf numerics.
10. **Activation sparsity (N12) on this fabric.** Accuracy at 0.6B is unknown, and it needs a layout change plus PL changes.
11. **Standalone papers on verified cold start (N23), JSON-state memory (N16), pass^k methodology (N3) or the cheap-board protocol (N24).** Each is a table or section. Fold them into A or B.
12. **Standalone RoT attestation (N6).** ShEF is prior art. It is valuable only as T3's stretch.

---

## 4. Uncertainty ledger

| Quantity | Current belief | What resolves it |
|---|---|---|
| Token-level forced fraction f in Qwen3 tool-call JSON | 0.3–0.6. P1 guessed 40–60%, but singleton-set forcing is stricter than text-level forcing. | T1 gate 1 |
| Contiguous ranges per allowed set | Unknown. Could be >100 for "any string character" states, making the restricted head useless there. | T1 gate 1 |
| B8 prefill ≡ sequential decode, bitwise | Likely (v9d ≡ v9c, 328/328), but **unproven** | T1 gate 2 |
| Per-call overhead of the LM-head range command | Unknown | T1 gate 3 |
| SILK has no GB/s DSP variant | Snippet-level only | T4 day 1–2 |
| RCP does not cover runtime nondeterminism | Inferred from its references | T6 day 1 |
| TOPLOC misses small perturbations | Plausible by design, unmeasured | T3 gate |
| Phase dynamic power varies >10% | Probably not (flat FPGA power) | T5 gate |
| Overall: ≥1 accepted peer-reviewed paper by about mid-2027 | About 70% (A or B) | — |

Sources from this round's searches:
- [XGrammar](https://arxiv.org/pdf/2411.15100)
- [Gram2Token, ICML 2026](https://icml.cc/virtual/2026/poster/62392)
- [Cross-GPU bit-exact kernels, arXiv 2609.25624](https://arxiv.org/pdf/2609.25624)
- [Tree-Based Invariant Kernels, arXiv 2511.17826](https://www.emergentmind.com/papers/2511.17826)
- [Bit-exact verification, ICML 2026](https://icml.cc/virtual/2026/78626)
- [SILK, arXiv 2608.26402](https://arxiv.org/pdf/2608.26402)
- [Replicable Conformal Prediction, arXiv 2608.23638](https://arxiv.org/pdf/2608.23638)
- [Embedded-FPGA decoding, arXiv 2502.10659](https://arxiv.org/pdf/2502.10659)
- [On-device Qwen2.5 on KV260, arXiv 2504.17376](https://arxiv.org/html/2504.17376v1)
- [pccx](https://github.com/pccxai/pccx)
