# Persona 2: verifiable / attested / deterministic inference (MLSys, USENIX Security, NeurIPS systems reviewer)

Round 1. Inputs: repo_context.md, corrections.md, lit_A–lit_F. Novelty checks: 4 web searches on 2026-11-08 (listed at the end).

## Reviewer's prior: what is no longer novel

- "Deterministic / bit-exact LLM inference" as a headline claim. Already published: DetLLM (integer-only Qwen3-0.6B, NeurIPS 2026, A33/corrections), Thinking Machines and SGLang batch invariance (C12, C13), LLM-42 (C14), HEAL (C19), Cankaya's bit-exact GPU emulation (C25, ICML 2026 workshop best paper), EigenAI (C26), and an integer-only ARM/x86 engine (arXiv 2603.24904, found in my search). A paper that says "our FPGA is deterministic" gets "so is DetLLM, on the same model, and faster" as the first review line.
- "We hash the weights at load time." SILK (C30) shows this is a TOCTOU hole, and that is the paper we would be rejected against.
- "Speculative decoding on FPGA": already done (F08 DATE'26, F09 SpecMamba).

What is still open, from this persona's view, is what determinism lets a third party *do*:
1. check an edge output exactly, on different hardware, cheaply;
2. close the weight-integrity loop at stream time without changing a single output bit;
3. let the operator optimize (cache, speculate, skip the LM head) while keeping output identity as a checkable invariant rather than a hope.

The project already has the hard prerequisite that the GPU and verifiable-inference work lacks: a batch-shape-invariant datapath that is bit-exact against an independent C reference, plus 328/328 cache-identity evidence.

---

## Niche 1: Exact-commit, cross-platform replay audit for edge LLM outputs ("fuzzy-free verifiable inference")

**(a) Claim.** A $350 FPGA decoder can emit a compact per-token hash-chain commitment of its hidden states. Any third party can then verify that commitment *bit-exactly* on a commodity GPU or CPU by teacher-forced replay of a published arithmetic spec. This gives zero false positives and detects any single-bit change to model, prompt, KV or arithmetic, a class of change that TOPLOC-style tolerant commits must accept by design.

**(b) Why it has not been done.**
- TOPLOC (C21), SVIP (C22) and DiFR (arXiv 2511.20621) are all tolerance or statistical schemes, because GPU replay is not bit-exact. Their tolerance is an attack surface that nobody has quantified against small, targeted perturbations such as single weight flips (C32 PrisonBreak) or a near-identical fine-tune.
- C24 (NeurIPS 2025) states outright that substitution auditing fails because of nondeterminism.
- EigenAI (C26) does byte-equality re-execution, but only GPU to GPU on the same stack, it is vendor-run, and it relies on a TEE.
- Cankaya (C25) emulates GPU FP behaviour on a CPU, so the verifier needs a model of the prover's hardware.
- DetLLM gives cross-platform identity (A100/H100/AMD/Intel/Apple), but it is not a commit/audit protocol and has no edge prover.
- My search "bit-identical LLM inference FPGA GPU cross-platform" found **no FPGA↔GPU bit-identity result** (closest: ARM↔x86 in 2603.24904, and a Waterloo integer-FPGA thesis with no cross-platform claim).
- Key insight to stress: verifying a decode trace is a *prefill* (all positions in parallel, teacher-forced). The verifier is therefore much faster than the prover even with fixed-order reductions. GPU determinism papers pay their cost on the serving path; we put it on the verifier side, where it is cheap.

**(c) Minimal experiments and metrics.**
- E1.1 *Spec + replayer.* Write down the FPGA arithmetic as a normative spec: Q8_0 dot order, INT32 accumulate, FP32 op order, no FMA contraction, FTZ/denormal policy, the hls::expf algorithm, and BF16 KV rounding. Port the existing independent C reference to CUDA with one thread per output row and sequential in-row order (compile with `--fmad=false`).
  - Metrics: bit-identical final-hidden-state hashes on FPGA, x86, A53 and ≥2 GPU generations for ≥10k tokens of BFCL/200 plus maintenance traces (target 100%).
  - Also report replay throughput (tok/s verified) versus FPGA generation speed (~6 tok/s). Target ≥100x.
- E1.2 *Commit cost on device.* Per-token SHA-256 of the final hidden state (4 KB) chained into a per-call Merkle root, optionally also of the top-k logits. Report bytes/token (expect 32 B per call root plus an optional 32 B per token, versus TOPLOC 258 B/32 tok), added latency per token (expect <1 ms on A53, against 165 ms/token), and joules if the energy rig exists.
- E1.3 *Detection matrix (headline table).* Attacks:
  - Q8_0→Q4_K swap;
  - single-bit weight flip in an INT8 value and in an FP16 scale;
  - PrisonBreak-style 5–25 flips;
  - a LoRA fine-tune with low KL divergence;
  - a one-token prompt edit;
  - K/V cache corruption;
  - a tampered FP32 op (e.g. an RMSNorm epsilon change).

  Columns: our exact commit vs TOPLOC (open-source; run on GPU replay of the same model) vs DiFR-style token-only audit. Metrics: TPR/FPR per attack, and minimum detectable perturbation. Expected story: exact detects all; TOPLOC misses some low-magnitude ones *by design*.
- E1.4 *Spot-check economics.* Sample-rate auditing (verify 1 in N calls). Report the detection probability versus verifier GPU-seconds per 1k edge calls.
- Stretch: sign the Merkle root with a key held by the Zynq CSU/PUF (C29 ShEF-style) so the commit is not forgeable by a compromised Linux.

**(d) Reused assets.** v9e decoder unchanged, the independent C reference and board causal fixtures, the evidence-seal infrastructure, BFCL/maintenance traces, and the llama-server divergence data (as the "why tolerance exists" motivation).

**(e) Cost and risk.** About 6–9 person-weeks, with no RTL change. Main risk: reproducing hls::expf, FP32 rounding and denormal behaviour bit-for-bit on the GPU. Mitigation: replace exp with a table or integer spec on both sides (a small HLS change), or adopt DetLLM's integer nonlinearity spec (see Option B). Second risk: TOPLOC's tolerance thresholds may in fact catch most of our attacks. That still leaves a publishable "cost/size/verifier-independence" contrast, but a weaker one.
- *Option B (DetLLM spec):* port DetLLM's integer softmax/RMSNorm/SiLU/RoPE into the HLS decoder, so that the FPGA output hash equals DetLLM's published cross-platform hash. That gives a very strong one-line demo ("same hash on A100 and a $350 FPGA"). It costs 4–8 extra weeks of HLS work, depends on DetLLM code and Q8_0-compatible weights, and has ppl/accuracy implications. Possible side benefit: removing FP32 units may relieve the 92–96% CLB packing. Treat it as a stretch, not as the plan of record.

**(f) Venue.** USENIX Security 2027 or IEEE S&P (if the threat model and RoT signing are done properly); otherwise MLSys 2027 or ACM CCS. A workshop version would fit the ICML/NeurIPS verifiable-AI workshops (Cankaya's venue class).

**(g) Kill criterion.** Kill or reshape if any of the following holds by week 4:
- GPU replay is not 100% bit-identical on ≥1k tokens after spec cleanup;
- replay is <20x faster than FPGA generation (the auditor economics fail);
- TOPLOC (at its recommended thresholds) detects every attack in E1.3 at a comparable commit size (the "exactness buys detection power" story collapses into a cost-only story).

---

## Niche 2: Exactness-preserving in-stream weight authentication on a bandwidth-bound decoder (closing TOCTOU at zero throughput cost)

**(a) Claim.** Because edge decode is weight-bandwidth bound with idle DSPs (41% used), a universal-hash MAC (NH/UMAC- or Poly1305-style, built in DSPs) on the 256-bit weight stream can authenticate every weight byte on every token, before use. It changes no output bit and costs no decode time. It catches post-load DRAM tampering by a compromised A53/Linux or DMA master, which startup-only SHA (our v16) and RoT measurement miss.

**(b) Why it has not been done.**
- SILK (C30, arXiv 2608.26402) is the direct prior work: a streaming checker on ZCU102 with Ascon-PRF and a keyed dependency network across the stream. It reports up to 0.17 ppl cost at INT8, i.e. it *perturbs the model*, and it does not combine with deterministic output commits.
- Tessera (arXiv 2604.23205, found in my search) streams encrypted weights on UMA edge accelerators, but explicitly leaves integrity (MAC or Merkle tree) as future work.
- GPU chunked-Merkle verification (Corca 2026) runs at load time on GPU+TDX.
- No accelerator paper in lit A treats runtime weight integrity at all (A gap 3), and E notes that "verified cold start" is unmeasured.
- Our differentiators:
  1. it is bit-exact (zero model change), so authentication and determinism compose end to end: authenticated weights ⇒ exact commit (Niche 1) is meaningful;
  2. a realistic attacker, the co-resident A53 Linux writing DDR, a threat SILK models less directly on an MPSoC;
  3. the startup SHA (~2.7 s) is replaced by streaming verification, so cold start drops as well. That is a security *and* latency win, which reviewers like.

**(c) Minimal experiments and metrics.**
- E2.1 Build an NH-style universal hash (8×32-bit lanes/cycle at 250 MHz, roughly 16–32 DSPs) per tensor tile, finalized with a keyed PRF (short Ascon core, or a final step on the R5/A53 with a key held in PL/eFUSE), and compared against sealed per-tile tags.
  - Metrics: LUT/FF/DSP/BRAM delta, Fmax, decode ms/token (target Δ<1%), and detection latency (≤1 token).
  - Gate policy: abort the token, or quarantine before the output is released through the typed output path.
- E2.2 *Attack emulation.* From user/root Linux on the A53, flip PrisonBreak-selected bits (C32) and random bits in DDR after startup; corrupt the DMA descriptor; replay stale weight pages (rollback). Show that startup-only SHA misses 100% of these and the streaming MAC catches 100%. Also report the effect of undetected flips on BFCL tool-call outputs, to quantify that the attack is real.
- E2.3 *Cold-start accounting.* Time and J to first verified token: startup SHA vs streaming MAC (expect −2 to −2.5 s).
- E2.4 *Comparison table vs SILK.* Model change (ppl Δ: ours 0), security notion (universal hash + PRF: ε-forgery bound), area, and throughput.

**(d) Reused assets.** HLS weight-stream path (256-bit AXI), sealed weight digests, evidence seals, R5 ownership/typed-output gate from v2 (for "release only after verify"), and BFCL harness.

**(e) Cost and risk.** About 8–12 weeks including RTL, closure and attack harness. Main risk: **LUT/CLB at 92–96%** means even a DSP-heavy hash may fail timing or routing. Mitigation: put the MAC in a lightweight shell at the HP-port interface, or time-multiplex it with prefill logic. Second risk: novelty against SILK. Reviewers may call it "SILK without the ppl cost". To counter, the composition with exact commits and the MPSoC co-resident attacker must be front and centre. Crypto risk: NH needs a secret key per message plus nonce management (a per-boot key and a per-tile counter), and this must be argued properly.

**(f) Venue.** HOST 2027, or ACM CCS/USENIX Security if combined with Niche 1; DAC/FCCM/FPL (security track) for the hardware angle alone.

**(g) Kill criterion.**
- The MAC cannot close at 250 MHz without degrading decode by >5%;
- or it cannot fit after one floorplan iteration;
- or SILK (or a successor) already reports zero-model-change streaming authentication on Zynq MPSoC (re-check before starting).

If routing fails, fall back to periodic background re-hashing by a PL DMA engine. That is weaker and probably only workshop-grade.

---

## Niche 3: Output-identity as a proved invariant for edge-inference optimizations (prefix cache, exact speculation, grammar jump-forward, restricted LM head)

**(a) Claim.** On a datapath whose per-row computation is a pure function of (weights, token prefix), independent of batch slot, batch size and cache state, a family of latency optimizations is *provably output-identical* to cold greedy decode. These are cross-request prefix reuse, greedy draft-and-verify through the B8 prefill path, grammar jump-forward, and an allowed-set-restricted LM head. We give the proof (a small mechanized model) and back it with exhaustive N/N board evidence. GPU stacks demonstrably violate this (llama-server's 16 divergences; EXSpec reports that batched speculative implementations break equivalence).

**(b) Why it has not been done.**
- SGLang deterministic mode (C13) and LLM-42 (C14) obtain identity at a 24–36% throughput cost and argue it empirically.
- EXSpec (arXiv 2510.22876) and "Lossless but Not Free" (2607.17283) report equivalence failures and statistical checks.
- My search found **no formal or machine-checked proof** of bit-exact equivalence for speculative decoding or prefix caching (see search 2).
- FPGA speculation papers (F08, F09) make no determinism claim.
- Grammar jump-forward and a mask-restricted LM head are absent on FPGA (F gaps 2–3).
- Our 328/328 prefix result is the only cross-stack cache-identity audit we know of (C gap 2).

**(c) Minimal experiments and metrics.**
- E3.1 *Invariant.* State "batch/slot/cache invariance" formally. Prove in Lean or Coq, over an abstract model (rows as functions of prefix; argmax over an allowed set equals argmax over the full set restricted when the grammar forbids the others), that each optimization yields the same token sequence. The proof is a few hundred lines; it covers the scheduling logic, not the RTL.
- E3.2 *Discharging the invariant on hardware.* Per-row hash equality of hidden states for the same prefix computed in slot k of B8 versus single decode, for all k; C-sim plus board, over ≥10^5 rows.
- E3.3 *Exactness under optimization.* Prompt lookup/REST drafting (F06) plus grammar forcing on BFCL/200 and the maintenance sets. Metrics: speedup (target ≥2x on 16–64-token calls), accepted length τ, and **divergences = 0/N** at the token *and* logit-hash level.
  - Same protocol on llama.cpp CPU and SGLang (deterministic on/off), reporting divergence counts and the determinism overhead.
  - The restricted LM head must give an argmax identical to the full head on constrained steps (bandwidth floor ~44 ms → small).
- E3.4 *Composability.* Run all optimizations together with Niche 1 commits: the commit for an optimized run equals the commit for the cold run, so the auditor cannot tell whether optimizations were applied. That is the security payoff: optimizations do not widen the verification surface.

**(d) Reused assets.** v16 prefix cache and the 328/328 methodology, B8 prefill and 2-token attention path, ARM JSON validator (as grammar FSM), the CPU llama-server baseline, and the exact C reference.

**(e) Cost and risk.** About 8–10 weeks: verify-mode HLS (8 argmaxes needs LM-head work on 8 positions), ARM drafter/FSM, Lean model, and baselines. Main risk: B8 verify requires 8 LM-head evaluations per pass, and the LM head is already at its bandwidth floor, so the speedup only appears with the restricted head and jump-forward. Speedup may be ~1.5x rather than 3x. Second risk: reviewers call the proof "trivial". Counter with the GPU counterexamples and by making the invariant check (E3.2) a reusable "inference equivalence test" tool.

**(f) Venue.** MLSys 2027 (strongest fit); EuroMLSys/ASPLOS as alternatives; FPL/FCCM if framed as hardware.

**(g) Kill criterion.**
- Any reproducible divergence on board that cannot be traced to a fixable bug within 2 weeks (that would falsify the invariant);
- or a combined end-to-end speedup <1.3x on 16–64-token tool calls (then it is a correctness note, not a systems paper).

---

## Strongest niche overall, and one trap

**Strongest: Niche 1 (exact-commit, cross-platform replay audit), built so that Niches 2 and 3 slot in as its integrity and performance sections.** It turns the project's one genuinely rare asset, an FPGA decoder that is bit-exact against an *independent* reference, into a security property that DetLLM, TOPLOC, EigenAI and Cankaya each only half-deliver. It needs no RTL change for the core result. It has a sharp, falsifiable headline table: the detection matrix against TOPLOC. Its cost asymmetry is real and new: verification is a parallel prefill on a GPU, while the prover is a 5–7 W edge board.

**Trap:** claiming "verifiable" or "attested" while the hash and seal are computed by the A53 Linux, which is the same software trust domain an attacker would compromise, and while weights are only checked at startup. A USENIX/S&P reviewer will dismiss the whole paper on threat model alone. Before any security claim, the commit must be computed in PL (or by the R5 with PL-held keys) and rooted in the Zynq CSU/PUF, and the TOCTOU gap must be closed or explicitly scoped out. Otherwise, position honestly as "auditable/replayable" at an MLSys venue rather than as "verifiable" at a security venue. A secondary trap: leading with "deterministic" as the novelty, which DetLLM on the same model already owns.

---

## Searches run (2026-11-08)
1. "bit-identical LLM inference FPGA GPU cross-platform integer-only verification": no FPGA↔GPU identity result. Found arXiv 2603.24904 (integer engine, ARM↔x86), 2606.00279 (Cankaya), 2608.13756 (INT8 kernels in vLLM disagree), and a Waterloo integer-FPGA thesis.
2. "deterministic speculative decoding bit-exact proof equivalence": LLM-42 (empirical), EXSpec 2510.22876 (existing batched spec decode breaks equivalence), 2607.17283 (statistical). No formal proof found.
3. "streaming weight integrity ... FPGA": SILK 2608.26402; Tessera 2604.23205 (encryption only, integrity as future work); Corca GPU Merkle verification; 2604.17249 (KV-cache bit flips in vLLM).
4. "verifiable LLM inference exact hash commitment re-execution": DiFR 2511.20621 (token-level post-hoc audit), TensorCommitments 2602.12630 (Terkle trees), EigenAI. No edge-device exact-commit audit found.
