# Literature review C: numerics, determinism, verifiability and integrity of LLM inference

Prepared 2026-11-08 for the System One FPGA project (Qwen3-0.6B Q8_0 decoder running fully on KR260 PL fabric).
Verification notes: every entry below was confirmed by web search (arXiv IDs, venues, authors) or is a canonical, widely cited paper. Where only an abstract or a secondary summary was seen, the key result is marked "(abstract)". Treat the 2026 arXiv preprints as unreviewed.

Closeness scale: 5 = directly competes with or frames a claim we would make; 1 = background only.

---

## A. Quantization and number formats

**C01. LLM.int8(): 8-bit Matrix Multiplication for Transformers at Scale.** Dettmers et al. NeurIPS 2022. https://arxiv.org/abs/2208.07339
Key result: vector-wise INT8 plus mixed-precision decomposition of emergent outlier features (kept in FP16) gives no degradation up to 175B parameters.
Relation: this is the origin of the outlier problem that our symmetric per-32 INT8 activation scheme has to survive. Our Q8_0 block scaling is a cruder, hardware-friendly answer to the same issue. Closeness 3.

**C02. SmoothQuant: Accurate and Efficient Post-Training Quantization for LLMs.** Xiao et al. ICML 2023. https://arxiv.org/abs/2211.10438
Key result: moves activation outlier difficulty into the weights through a per-channel scale, enabling W8A8 with negligible loss up to 530B.
Relation: this is the standard W8A8 baseline. Our A8 path uses per-32 dynamic scales rather than smoothing, and comparing the two on a 0.6B model would be cheap. Closeness 3.

**C03. GPTQ: Accurate Post-Training Quantization for Generative Pre-trained Transformers.** Frantar et al. ICLR 2023. https://arxiv.org/abs/2210.17323
Key result: second-order (OBS-style) one-shot weight quantization to 3–4 bits in a few GPU hours for 175B models.
Relation: GPTQ would be the route to W4 weights, which would roughly halve our weight bandwidth and so decode time (decode is bandwidth bound). Closeness 3.

**C04. AWQ: Activation-aware Weight Quantization for LLM Compression and Acceleration.** Lin et al. MLSys 2024 (best paper). https://arxiv.org/abs/2306.00978
Key result: protecting about 1% of salient channels, chosen by activation magnitude, through per-channel scaling gives strong W4 results without backprop. It targets edge devices.
Relation: AWQ is the most likely W4 format if we move off Q8_0. The edge framing overlaps with ours. Closeness 3.

**C05. QuaRot: Outlier-Free 4-Bit Inference in Rotated LLMs.** Ashkboos et al. NeurIPS 2024. https://arxiv.org/abs/2404.00456
Key result: Hadamard rotations fused into the weights remove outliers, enabling W4A4KV4 end to end (LLaMA-2-70B keeps about 99% of zero-shot accuracy).
Relation: rotations are exact integer-friendly transforms (Hadamard), so they fit a bit-exact FPGA datapath. A rotated W4A8 variant could keep our determinism. Closeness 3.

**C06. SpinQuant: LLM Quantization with Learned Rotations.** Liu (Zechun) et al. ICLR 2025. https://arxiv.org/abs/2405.16406
Key result: learned (Cayley-optimised) rotations beat random Hadamard and narrow the W4A4KV4 gap to full precision to about 2.9 points on LLaMA-2-7B.
Relation: same as C05. It is from Meta and is aimed at on-device models. Closeness 2.

**C07. Microscaling Data Formats for Deep Learning.** Rouhani et al. (Microsoft, AMD, Intel, Meta, NVIDIA, Qualcomm) arXiv 2023, plus OCP MX v1.0 spec. https://arxiv.org/abs/2310.10537
Key result: block formats with a shared 8-bit exponent per 32 elements (MXFP8/6/4, MXINT8) work as drop-in replacements for FP32 inference, and sub-8-bit training was demonstrated.
Relation: our Q8_0 (one FP16 scale per 32 INT8 values) is structurally almost MXINT8 (which uses an E8M0 scale per 32). Supporting OCP MX in our fabric would make the determinism result vendor-standard rather than GGUF-specific. Closeness 4.

**C08. KIVI: A Tuning-Free Asymmetric 2-bit Quantization for KV Cache.** Liu (Zirui) et al. ICML 2024. https://arxiv.org/abs/2402.02750
Key result: keys are quantized per-channel and values per-token at 2 bits, giving 2.6x less peak memory and up to 3.5x throughput with near-baseline quality.
Relation: our BF16 K/V cache (v9e, 2048 tokens) is the conservative choice. INT8/INT4 KV would free URAM/DDR bandwidth, and integer KV is also naturally deterministic. Closeness 3.

**C09. KVQuant: Towards 10 Million Context Length LLM Inference with KV Cache Quantization.** Hooper et al. NeurIPS 2024. https://arxiv.org/abs/2401.18079
Key result: per-channel pre-RoPE key quantization, non-uniform datatypes and dense-and-sparse outliers give under 0.1 perplexity loss at 3 bits.
Relation: the pre-RoPE key quantization result matters for our FP32 RoPE placement if we quantize K. Closeness 2.

**C10. SLMQuant: Benchmarking Small Language Model Quantization.** arXiv 2511.13023 (Nov 2025). https://arxiv.org/abs/2511.13023
Key result (abstract): small language models (SLMs) differ fundamentally from large models in quantization sensitivity, and LLM-tuned methods transfer suboptimally. Qwen's hidden-to-embedding ratio is linked to higher KV and activation sensitivity.
Relation: this is directly about sub-1B/Qwen sensitivity, our exact regime. It justifies staying at Q8_0 for 0.6B and motivates our own small-model sensitivity table. Closeness 4.

**C11. A Systematic Evaluation of On-Device LLMs: Quantization, Performance, and Resources.** arXiv 2505.15030 (2025). https://arxiv.org/abs/2505.15030
Key result: a 1.5B model drops from 59.1% to 46.5% on GSM8K going from q5_k to q3_k GGUF, while 14B is nearly unaffected.
Relation: this is a GGUF-format evidence point that small models are fragile at low bits. It supports Q8_0 for our 0.6B decoder and frames any W4 move as a measured trade. Closeness 3.

## B. Nondeterminism and reproducibility

**C12. Defeating Nondeterminism in LLM Inference.** He (Horace) and Thinking Machines Lab, blog/report, Sep 2025. https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/
Key result: temperature-0 nondeterminism in serving comes mainly from a lack of batch invariance in RMSNorm, matmul and attention kernels, which depends on server load, not from "concurrency plus floating point" alone. Batch-invariant kernels make Qwen3-8B on vLLM bit-identical across 1000 runs, at a significant throughput cost (reported in the tens of percent).
Relation: this is the single most important framing paper for us. Our FPGA decoder is batch-shape-invariant by construction (fixed reduction order, prefill-8 equal to decode), and our llama-server prefix-cache divergence is exactly the phenomenon it describes. Closeness 5.

**C13. Towards Deterministic Inference in SGLang and Reproducible RL Training.** LMSYS/SGLang team, blog, 22 Sep 2025. https://lmsys.org/blog/2025-09-22-sglang-deterministic/
Key result: batch-invariant kernels were integrated with chunked prefill, CUDA graphs and radix (prefix) cache, using fixed split sizes for FA2. They are exposed through `--enable-deterministic-inference`. A third-party summary puts the overhead at about 34% (unverified).
Relation: this is the GPU counterpart of our "exact prefix reuse equals cold" claim. Any paper we write must compare against SGLang's deterministic plus radix-cache mode, not only default llama-server. Closeness 5.

**C14. LLM-42: Enabling Determinism in LLM Inference with Verified Speculation.** Gond, Kamath, Basu, Ramjee, Panwar (Microsoft Research India). arXiv 2601.17768, Jan 2026. https://arxiv.org/abs/2601.17768
Key result: a fast nondeterministic path plus a fixed-reduction-schedule verifier with decode-verify-rollback. SGLang's deterministic mode costs 24–36% throughput, while LLM-42 keeps over 94% of performance at up to 50% deterministic traffic.
Relation: this treats determinism as a priced service on GPUs. On our FPGA determinism costs zero, and quantifying "cost of determinism" across platforms is a clean comparison axis. Closeness 4.

**C15. Non-Determinism of "Deterministic" LLM Settings.** Atil et al. arXiv 2408.04667 (v5 2025); Eval4NLP workshop 2025. https://arxiv.org/abs/2408.04667
Key result: five "deterministic" hosted LLMs on eight tasks over 10 runs show up to 15% accuracy variation and up to 70% best-worst gaps, and none gave identical strings. It introduces the TARr@N/TARa@N agreement metrics.
Relation: we can report TARr@N = 1.0 by construction and adopt their metrics directly. This is the evaluation-validity motivation for deterministic hardware. Closeness 4.

**C16. Give Me FP32 or Give Me Death? Challenges and Solutions for Reproducible Reasoning** (later titled "Understanding and Mitigating Numerical Sources of Nondeterminism in LLM Inference"). Yuan, Li et al. arXiv 2506.09501, NeurIPS 2025. https://arxiv.org/abs/2506.09501
Key result: with BF16 greedy decoding, DeepSeek-R1-Distill-Qwen-7B varies up to 9% in accuracy and 9,000 tokens in length across GPU count, type and batch size. FP32 is near zero variance. The authors propose LayerCast (16-bit storage, FP32 compute).
Relation: our design is effectively "integer dots plus FP32 everywhere else, fixed order", which is LayerCast-like and fully deterministic. Their benchmark protocol is the one to replicate on board versus GPU. Closeness 5.

**C17. Beyond Reproducibility: Token Probabilities Expose Large Language Model Nondeterminism.** Fu, Martínez, Conde, Arriaga, Reviriego, Qi, Liu. arXiv 2601.06118, Jan 2026. https://arxiv.org/abs/2601.06118
Key result: logprob-level variation across runs is significant for token probabilities in 0.1–0.9 and similar across models. It is the first measurement on Huawei GPUs, and the authors suggest single-run estimation of nondeterminism impact.
Relation: this offers a metric (logprob variance) on which we can show exactly zero, and can show the CPU llama-server nonzero, at the logit level rather than only at the token level. Closeness 4.

**C18. Greedy Decoding Is Not Precision-Invariant: Cross-Precision Output Divergence in LLM Inference.** Du, Khan, Zhou, Liu, Chakrabarti, Suya, Li. arXiv 2609.26621 (2026). https://arxiv.org/abs/2609.26621
Key result (abstract): BF16 versus FP16 on identical hardware diverges on 49–100% of prompts across six models. Divergence is governed by the top-2 logit margin at the LM head.
Relation: "top-2 margin" is a measurable predictor we can compute exactly on board to explain where the CPU and FPGA differ. It also says a "reference" must specify precision, which supports our independent-reference methodology. Closeness 4.

**C19. Demystifying Numerical Instability in LLM Inference: Achieving Reproducible Inference for Mission-Critical Tasks with HEAL.** Zhu, Thai et al. (UCLA/Berkeley/UCAS). arXiv 2606.21023, Jun 2026. https://arxiv.org/abs/2606.21023
Key result (abstract): cross-GPU divergence is traced, using SASS-level profiling, to downcast truncation at kernel boundaries. HEAL uses INT16 QKV plus error-compensated 16-bit tensor-core matmuls to match FP32 reproducibility with up to 7.1x lower overhead. It introduces MCR-Bench.
Relation: this is explicitly framed as "mission-critical reproducibility", our application framing. MCR-Bench is a ready-made benchmark to run on the FPGA. Closeness 4.

**C20. Algorithms for Efficient Reproducible Floating Point Summation.** Ahrens, Demmel, Nguyen. ACM TOMS 46(3), 2020 (ReproBLAS). https://doi.org/10.1145/3389360 (tech report: https://www2.eecs.berkeley.edu/Pubs/TechRpts/2015/EECS-2015-229.html)
Key result: a binned accumulator (6 FP words) gives order-independent, reproducible sums in one pass at about 7n flops.
Relation: this is the classical HPC answer. We get reproducibility instead from fixed-order hardware, which is cheaper but platform-bound. ReproBLAS-style accumulators would make our FP32 reductions reproducible against a CPU reference regardless of order (cross-platform bit-exactness). Closeness 3.

## C. Verifiable and attested inference, integrity

**C21. TOPLOC: A Locality Sensitive Hashing Scheme for Trustless Verifiable Inference.** Ong et al. (Prime Intellect). ICML 2025 (PMLR 267). https://arxiv.org/abs/2501.16007
Key result: top-k activation commits encoded as polynomials detect model, prompt and precision substitution with no false positives or negatives in their tests. They use 258 bytes per 32 tokens and verification up to 100x faster than generation. The scheme is designed to tolerate GPU nondeterminism.
Relation: TOPLOC exists because GPUs are not bit-exact. With a bit-exact FPGA, a plain cryptographic hash of hidden states or logits serves as a commit, so the tolerance machinery becomes unnecessary. This is a direct, testable contrast. Closeness 5.

**C22. SVIP: Towards Verifiable Inference of Open-source Large Language Models.** Sun et al. (UIUC / Hyperbolic). NeurIPS 2025. https://arxiv.org/abs/2410.22307
Key result: a secret proxy task trained on returned hidden states identifies the model with under 5% false negatives and under 3% false positives, at under 0.01 s per query (13B–70B).
Relation: this is statistical model-identity verification. Our approach is exact replay against independent references, which is stronger but needs determinism. Closeness 3.

**C23. zkLLM: Zero Knowledge Proofs for Large Language Models.** Sun (Haochen), Li, Zhang. ACM CCS 2024. https://arxiv.org/abs/2404.16109
Key result: tlookup and zkAttn give a full-inference correctness proof for 13B models in under 15 minutes, with proofs under 200 kB verified in 1–3 s.
Relation: this is the cryptographic end of the spectrum. zk proofs need a fixed-point and integer circuit, which our quantized, deterministic arithmetic already resembles (integer dots, fixed order). Closeness 2.

**C24. Are You Getting What You Pay For? Auditing Model Substitution in LLM APIs.** Cai, Shi, Zhao, Song. NeurIPS 2025. https://arxiv.org/abs/2504.04715
Key result: output-based tests and logprob auditing fail to reliably detect substitution (including quantization swaps), partly because production inference is nondeterministic. The authors argue for TEEs.
Relation: this states explicitly that nondeterminism defeats auditing. Our determinism plus weight SHA is exactly the missing property, demonstrated on cheap hardware. Closeness 5.

**C25. Bit-Exact AI Inference Verification Without Performance Tradeoffs.** Cankaya. arXiv 2606.00279; ICML 2026. https://arxiv.org/abs/2606.00279
Key result (summary): bitwise re-computation of GPU LLM inference is possible without identical hardware, through software emulation that caches special-function instruction outputs in a lookup table.
Relation: this is a strong competitor framing ("bit-exact verification"), on GPUs. Our angle is a hardware design that is bit-exact natively, with an independent reference already part of the design flow. Closeness 5.

**C26. EigenAI: Deterministic Inference, Verifiable Results.** Ribeiro Alves, Patankar, Pereira, Stephens, Vaziri, Kannan (Eigen Labs). arXiv 2602.00182, Jan 2026. https://arxiv.org/abs/2602.00182
Key result (company-reported): bit-exact deterministic GPU inference, with 100% reproducibility over 10k runs and under 2% overhead, used for crypto-economic re-execution verification.
Relation: this shows a market and use case for deterministic inference (re-execution audits). It is unreviewed and vendor-run, which leaves room for an independent, open hardware result. Closeness 4.

**C27. Confidential Computing on NVIDIA Hopper GPUs: A Performance Benchmark Study.** Zhu et al. (Phala). arXiv 2409.03992 (v4). https://arxiv.org/abs/2409.03992
Key result: H100 CC-mode overhead for vLLM LLM inference is under 7% for typical queries and near zero for 70B. It is dominated by encrypted CPU-GPU transfers.
Relation: this is the GPU TEE baseline for "attested inference". The KR260 has a hardware RoT (Zynq UltraScale+ secure boot, eFUSE/PUF, AES/RSA in the CSU) that we have not yet used for attestation. Closeness 3.

**C28. Confidential LLM Inference: Performance and Cost Across CPU and GPU TEEs.** Chrapek et al. arXiv 2509.18886 (Sep 2025). https://arxiv.org/abs/2509.18886
Key result: H100 CC costs 4–8% throughput, shrinking with batch and input size. It also covers Intel TDX and SGX.
Relation: same as C27, and gives cost numbers to compare against an FPGA attestation path. Closeness 2.

**C29. ShEF: Shielded Enclaves for Cloud FPGAs.** Zhao, Gao, Kozyrakis. ASPLOS 2022. https://web.stanford.edu/~kozyraki/publication/2022-shef-asplos
Key result: an FPGA TEE using only existing FPGA root-of-trust mechanisms (secure boot, remote attestation, JTAG lockdown), plus a customizable "Shield" for memory encryption and authentication.
Relation: this is the canonical FPGA attestation design. Our sealed weight mapping and startup SHA are a partial, software-side version, and ShEF shows how to root it in the device's boot chain. Closeness 4.

**C30. SILK: Closing the Time-of-Check-to-Time-of-Use Gap in RoT-Protected AI Systems.** Qi et al. (incl. Saligane). arXiv 2608.26402, Aug 2026. https://arxiv.org/abs/2608.26402
Key result: load-time RoT measurement misses weight tampering in DRAM, DMA or interconnect. A streaming in-place checker gates unverified weights before compute. It caught every stream-modifying attack in their tests, at INT8 cost of at most 0.17 perplexity on eight LLMs. Prototyped on a Xilinx FPGA (ZCU102).
Relation: this is the closest integrity paper to us. It exposes the exact weakness of our "startup-only SHA" (v16): a TOCTOU gap during the weight stream. A streaming check on our 256-bit weight bus would be a natural extension. Closeness 5.

**C31. A Stealthy Hardware Trojan Exploiting the Architectural Vulnerability of Deep Learning Architectures: Input Interception Attack (IIA).** Odetola et al. arXiv 1911.00783. https://arxiv.org/abs/1911.00783
Key result: a Trojan in an FPGA CNN accelerator triggers on layer-output statistics with about 2% LUT overhead.
Relation: this is the threat model for fabric-level tampering. Bit-exact replay against an independent reference detects any functional Trojan payload on tested inputs, which is a cheap, testable detection claim. Closeness 2.

## D. Reliability under faults, safety

**C32. PrisonBreak: Jailbreaking Large Language Models With at Most Twenty-Five Targeted Bit-flips.** Coalson, Woo et al. arXiv 2412.07192 (2024/2025). https://arxiv.org/abs/2412.07192
Key result: 5–25 targeted weight bit flips remove safety alignment (80–98% attack success rate across 10 LLMs). An end-to-end Rowhammer attack on GDDR6 achieves 69–91%.
Relation: this is why weight integrity at runtime matters, not just at load. Our resident DDR weights with startup-only SHA are vulnerable to exactly this, so periodic or streaming re-hashing is the defense to evaluate. Closeness 4.

**C33. Bit-Flip Error Resilience in LLMs: A Comprehensive Analysis and Defense Framework.** Chen et al. EMNLP 2025 (pp. 10414–10424). https://aclanthology.org/2025.emnlp-main.528
Key result: exponent bits and specific components dominate bit-flip vulnerability. The FlipGuard defense (exponent protection plus self-correction fine-tuning) reduces degradation.
Relation: our weights are INT8 with FP16 block scales, so a flip in a scale's exponent hits 32 weights. This suggests a format-aware fault-injection study on Q8_0. Closeness 3.

**C34. Analysis of LLM Vulnerability to GPU Soft Errors: An Instruction-Level Fault Injection Study.** Chai et al. arXiv 2601.19912 (Dec 2025). https://arxiv.org/abs/2601.19912
Key result: NVBitFI-based injection shows that instruction type, bit position and layer govern LLM silent-data-corruption rates on reasoning and summarization tasks.
Relation: this is the GPU counterpart for a fault-injection campaign on our fabric. Determinism gives us a perfect golden reference to classify silent data corruption (SDC) exactly, which GPU studies lack. Closeness 3.

**C35. ISO/PAS 8800:2024 Road vehicles — Safety and artificial intelligence.** ISO, Dec 2024. https://www.iso.org/standard/83303.html
Key result: the first automotive AI safety specification, complementing ISO 26262 and SOTIF. It addresses AI output errors and hardware faults across the lifecycle.
Relation: this gives a vocabulary for our "bounded reliability" claims (typed outputs, abstention, verified execution). Reproducibility of AI component behavior is a prerequisite for the verification evidence it asks for. Closeness 3.

---

## (1) What is saturated

- **Weight-only and W8A8 PTQ algorithms** (C01–C06): GPTQ, AWQ, SmoothQuant and rotations are mature. A new quantizer is not a contribution for us.
- **KV-cache quantization** (C08, C09 and many follow-ups) is crowded on GPUs.
- **Diagnosing GPU nondeterminism**: since Thinking Machines (C12), the cause (batch-variant reductions, downcasts) is well understood. Follow-ups (C13, C14, C16–C19) already cover kernels, serving systems, precision and metrics. Another "GPUs are nondeterministic" measurement paper would be incremental.
- **GPU TEE overhead benchmarks** (C27, C28): settled at under about 8% overhead.
- **zkML for LLMs** (C23): cryptographically active but far from our regime and expertise.
- **Bit-flip attacks and resilience on GPUs/DRAM** (C32–C34): active, with many papers.

## (2) Gaps and open niches tied to our assets

1. **Determinism "for free" in hardware versus priced determinism on GPUs.** Every 2025–26 determinism paper (C12–C14, C16, C19, C25, C26) pays for reproducibility with throughput, precision or emulation. No peer-reviewed work we found shows a *complete generative LLM decoder* that is batch-shape-invariant and bit-exact *by construction* on an FPGA, with an *independent* reference (not just self-consistency). Our searches for FPGA bit-exact LLM inference returned only GPU work.
2. **Exact prefix/KV reuse as a correctness property.** SGLang (C13) claims radix-cache compatibility in deterministic mode. No paper we found *audits* prefix-cache equivalence (cached run equals cold run at token *and* logit level) across stacks. Our 328/328 exact matches versus CPU llama-server's 16 divergences is a concrete, rare data point.
3. **Commit-by-hash replaces fuzzy verification.** TOPLOC (C21) and SVIP (C22) exist because hidden states are not reproducible. On a bit-exact platform, a SHA-256 over logits or hidden states per token is an exact commit. Third-party replay on the same bitstream, or against the independent C reference, verifies it, with zero false positives by construction. Nobody has quantified this contrast (commit size, verification cost, false positive rate) on real hardware.
4. **Substitution auditing needs determinism** (C24 says this outright). A cheap edge device with weight SHA plus deterministic outputs is a working, non-TEE answer for auditing. It is not cryptographically attested yet, though, because we do not use the Zynq RoT.
5. **TOCTOU in weight integrity** (C30, C32). Our startup-only SHA (v16) has exactly the gap SILK identifies. A streaming or periodic integrity check on the 256-bit weight stream, measured for throughput cost, is a natural, publishable extension that only an FPGA can do cheaply.
6. **Fault injection with an exact golden model.** GPU SDC studies (C33, C34) must statistically separate fault effects from nondeterminism noise. Our determinism makes every deviation attributable. Format-aware Q8_0 scale-versus-mantissa vulnerability on a sub-1B model is unstudied.
7. **Small-model numerics** (C10, C11). Sub-1B quantization sensitivity is thin, with almost nothing on how *margin* (C18) interacts with Q8_0/MX for tool-call JSON outputs.

## (3) Experiments to turn determinism and integrity into a publishable contribution

E1. **Cross-platform determinism matrix.** Run the same Qwen3-0.6B Q8_0 prompts (BFCL /200, the maintenance set, plus MCR-Bench from C19 if obtainable) on: FPGA; llama.cpp CPU (threads 1/4, batch sizes, prompt cache on/off); llama.cpp/vLLM GPU default; and SGLang `--enable-deterministic-inference` with radix cache. Report TARr@N/TARa@N (C15), first-divergence position, logprob variance (C17), and top-2 margin at divergence (C18), for N = 10–100 runs under varied concurrent load. Headline: FPGA variance is identically 0 under load, cache and batch changes, and the "cost of determinism" is 0% on the FPGA versus the GPU deterministic-mode overhead measured ourselves (C13, C14).

E2. **Prefix-cache equivalence audit.** Generalise the 328/328 study: random prefix-split points × conversation lengths × cache eviction. Compare FPGA, llama-server and SGLang deterministic plus radix. Check equivalence at three levels: token IDs, logits (bitwise), and per-layer hidden-state hashes. Also release the harness as an "inference equivalence test" tool.

E3. **Exact commit versus TOPLOC.** Emit a per-token SHA-256 (or per-32-token Merkle root) of the final hidden state or logits from the ARM side. Verify by replay on (a) a second KR260 with the same bitstream and (b) the independent C reference. Measure commit bytes per token versus TOPLOC's 258 B per 32 tokens, verification time, and the detection rate for injected substitutions (Q8_0 to Q4, altered prompt, single-weight bit flip, a different 0.6B fine-tune). Expected: zero false positives, detection of any single-bit change.

E4. **Close the TOCTOU gap.** Add a streaming hash or CRC (or SILK-style sparse check, C30) on the 256-bit HP weight stream in PL, checked per tensor against sealed digests. Measure LUT/BRAM cost and decode slowdown (decode is bandwidth bound, so a check off the critical path may be about free). Run a PrisonBreak-style (C32) attack emulation by flipping the selected bits in DDR after startup. Show that startup-only SHA misses it and the streaming check catches it before the next token.

E5. **Exhaustive-attribution fault injection.** Inject single and multi-bit flips into weights (INT8 mantissa versus FP16 scale), K/V BF16 cache, and activations (through a debug path). With bit-exact golden outputs, classify each run as masked, benign deviation, JSON-invalid (caught by the validator), or silent wrong-valid tool call. Relate this to typed-output assurance ("bounded reliability"). Compare scale versus value vulnerability with C33's exponent finding.

E6. **Root-of-trust attestation.** Use Zynq UltraScale+ secure boot plus a CSU-signed measurement (bitstream hash, weight Merkle root, tokenizer hash, run config) to sign each evidence seal. Package it as an attestation report and a verifier script, which gives a ShEF-style (C29) story without a GPU TEE. Report the cost against GPU CC overhead (C27, C28).

E7. **(Optional) Format portability.** Implement MXINT8 (E8M0 scale, C07) next to Q8_0 and show that bit-exactness and determinism carry over to an OCP-standard format. Measure the accuracy delta on 0.6B (C10).

Suggested paper framing: "Determinism by construction: a bit-exact, batch-invariant LLM decoder on a $350 FPGA, and what it buys for verification, caching and fault attribution". The core evidence would be E1+E2+E3, with E4/E5 as the integrity and reliability extension. Target venues include FPL/FCCM/FPGA (hardware angle) or MLSys/EuroMLSys and the SysML reproducibility workshops (systems angle). A dependable-systems venue (DSN) fits if E5 leads.
