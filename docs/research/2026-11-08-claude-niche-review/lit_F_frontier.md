# Lit review F: frontier algorithmic directions for a bandwidth-bound, deterministic edge decoder

Agent F. Written 2026-11-08. I web-checked the identifiers of the 2025–2026 items and the FPGA items in this session. The older, well-known items (2022–2024 ML venues) are cited from memory with arXiv IDs. Before final citation, check them against the arXiv/venue pages.

**Our operating point.** Qwen3-0.6B Q8_0, about 0.64 GB of weights, streamed over one HP port at about 3.8 GB/s effective. Decode is weight-bandwidth bound at about 125 ms/token. The LM head takes about 0.7 s. The LM head alone is about 151,936 × 1024 × 1.0625 B ≈ 165 MB, so its bandwidth floor is about 43 ms. The 0.7 s figure is therefore far off its own roofline. The B8 prefill engine already exists, and outputs are bit-exact and deterministic.

**Closeness scale (5 = could drop into our decoder almost directly / same problem setting; 1 = background only).**

---

## Paper table

### A. Speculative / parallel decoding

**F01 — EAGLE: Speculative Sampling Requires Rethinking Feature Uncertainty.** Yuhui Li et al., ICML 2024. https://arxiv.org/abs/2401.15077
- Key result: a light autoregressive head predicts the next-layer features from the target model's top hidden state plus the shifted token. It reaches 2.7–3.5x latency speedup on LLaMA2-Chat 70B, and the output distribution is unchanged.
- KR260: the draft head is about one decoder layer, roughly 15–25 MB Q8 for 0.6B, so each draft step costs about 3–4% of a full weight pass. Draft k tokens, then verify them in one B8 prefill pass. The win depends on verifying 8 tokens costing close to one weight pass.
- Closeness: 4

**F02 — EAGLE-2: Faster Inference of Language Models with Dynamic Draft Trees.** Yuhui Li et al., EMNLP 2024. https://arxiv.org/abs/2406.16858
- Key result: the draft tree is built from draft-model confidence (a context-aware dynamic tree). It is 20–40% faster than EAGLE-1, with speedups of 3.05–4.26x.
- KR260: a dynamic tree needs tree attention masks in our 2-token/B8 attention path. A static 8-node tree fits the existing B8 batch shape and is simpler to keep bit-exact.
- Closeness: 3

**F03 — EAGLE-3: Scaling up Inference Acceleration of LLMs via Training-Time Test.** Yuhui Li, Fangyun Wei, Chao Zhang, Hongyang Zhang, NeurIPS 2025. https://arxiv.org/abs/2503.01840
- Key result: drops feature prediction, fuses low/mid/high-layer features, and trains with simulated multi-step drafting. Up to 6.5x speedup, about 1.4x over EAGLE-2.
- KR260: the drafter can be trained on our own tool-call/maintenance JSON traces. Taps from three layers need small on-chip buffers only. This is the strongest candidate for a learned drafter.
- Closeness: 4

**F04 — Medusa: Simple LLM Inference Acceleration Framework with Multiple Decoding Heads.** Tianle Cai et al., ICML 2024. https://arxiv.org/abs/2401.10774
- Key result: extra heads predict tokens t+2..t+k, and tree attention verifies them. 2.2x (Medusa-1) and 2.3–3.6x (Medusa-2).
- KR260: each Medusa head is a full vocab projection, which is about 165 MB for us. That makes it bandwidth-expensive on our LM-head-heavy design unless the heads share or prune the vocabulary. EAGLE-style heads are a better fit.
- Closeness: 3

**F05 — Break the Sequential Dependency of LLM Inference Using Lookahead Decoding.** Yichao Fu et al., ICML 2024. https://arxiv.org/abs/2402.02057
- Key result: Jacobi iteration plus an n-gram pool. Training-free, no draft model, 1.8x on MT-Bench and up to 4x with multi-GPU on code.
- KR260: it trades spare compute for fewer weight passes, which is exactly our regime. Our DSPs are only at 41%, but the B8 width limits the window and n-gram branches to about 8 tokens per pass.
- Closeness: 4

**F06 — REST: Retrieval-Based Speculative Decoding.** Zhenyu He et al., NAACL 2024. https://arxiv.org/abs/2311.08252
- Key result: drafts come from a datastore by suffix match, with no draft model. 1.62–2.36x on code and chat.
- KR260: the closest published analogue of prompt-lookup / n-gram drafting. Prompt Lookup Decoding (Saxena, 2023) is a GitHub technique, not a paper. For tool calls, argument values are often copied verbatim from the prompt or JSON state, so a suffix match over prompt + schema + past calls running on the ARM is almost free.
- Closeness: 5

**F07 — Constrained Decoding with Speculative Lookaheads (CDSL).** Nishanth Nakshatri et al. (Purdue / AWS), arXiv 2412.10418, 2024/2025. https://arxiv.org/abs/2412.10418
- Key result: a draft model proposes lookaheads, and the target verifies them under task constraints. 2.2–12.15x over constrained-decoding-with-lookahead.
- KR260: evidence that drafting and constraint checking compose. Our ARM already does the JSON validation, so it can filter drafts before verification.
- Closeness: 3

**F08 — Boosting the Performance of Tree-Based Speculative Decoding of LLMs on FPGAs.** DATE 2026. https://past.date-conference.com/proceedings-archive/2026/DATA/371.pdf
- Key result: a roofline model that ties verification length to accepted length ("effective performance"), plus a prior-score search for the tree shape. Evaluated on FlightLLM, with reported speedups of about 2.5–3.9x over autoregressive decoding. I only saw the abstract and introduction; check the numbers in the PDF.
- KR260: this is the direct prior art for speculation on FPGA. Our version would be distinguished by the edge SoC setting, a deterministic/bit-exact guarantee, and grammar-aware drafting.
- Closeness: 5

**F09 — SpecMamba: Accelerating Mamba Inference on FPGA with Speculative Decoding.** arXiv 2509.19873, 2025. https://arxiv.org/abs/2509.19873
- Key result: the first FPGA Mamba accelerator with draft-and-verify, co-designed for hidden-state rollback. About 2.27x over GPU and 2.85x over prior FPGA work.
- KR260: shows that FPGA speculation is publishable at venues in 2025–26. It is for SSMs, not transformers, so a transformer-on-edge-SoC version is still open.
- Closeness: 4

### B. Structured-output / grammar-aware decoding

**F10 — XGrammar: Flexible and Efficient Structured Generation Engine for LLMs.** Yixin Dong et al., MLSys 2025. https://arxiv.org/abs/2411.15100
- Key result: splits the vocabulary into context-independent tokens (prechecked) and context-dependent tokens, using a persistent stack. Grammar masking becomes nearly free, up to 10x over prior engines. Jump-forward decoding skips the model whenever the grammar forces the continuation.
- KR260: (1) Jump-forward means forced JSON tokens (braces, keys, quotes, enum completions) need no LM head and no sampling. They are appended as prompt-like tokens, so B8 prefill absorbs them. (2) The allowed-token mask can shrink the LM head to the allowed subset. This attacks our 0.7 s LM head directly.
- Closeness: 5

**F11 — SGLang: Efficient Execution of Structured Language Model Programs.** Lianmin Zheng et al., NeurIPS 2024. https://arxiv.org/abs/2312.07104
- Key result: RadixAttention prefix reuse plus a compressed finite-state machine that decodes multi-token forced segments in one step. Up to 6.4x throughput, and JSON decoding is noticeably faster.
- KR260: our exact prefix reuse (v16) is already a deterministic RadixAttention-lite. Adding compressed-FSM jump-forward is the natural next step.
- Closeness: 5

**F12 — Guiding LLMs The Right Way: Fast, Non-Invasive Constrained Generation (DOMINO).** Luca Beurer-Kellner, Marc Fischer, Martin Vechev, ICML 2024. https://arxiv.org/abs/2403.06988
- Key result: subword-aligned constraints avoid the accuracy loss caused by token misalignment. Speculative prefetching of grammar-forced tokens gives close to 2x over unconstrained generation on structured tasks.
- KR260: a correctness caution. Naive forcing can hurt the 0.6B model's accuracy. We should report task accuracy under forcing, not only speed.
- Closeness: 4

### C. Early exit / layer skipping

**F13 — LayerSkip: Enabling Early Exit Inference and Self-Speculative Decoding.** Mostafa Elhoushi et al., ACL 2024. https://arxiv.org/abs/2404.16710
- Key result: layer-dropout training plus an early-exit loss lets the first E layers draft and the remaining layers verify, with shared KV. 1.34–2.16x.
- KR260: self-speculation adds no extra weights. Drafting with 8 of 28 layers streams about 29% of the weights. This needs LayerSkip-style continued training of Qwen3-0.6B.
- Closeness: 4

**F14 — Confident Adaptive Language Modeling (CALM).** Tal Schuster et al., NeurIPS 2022. https://arxiv.org/abs/2207.07061
- Key result: per-token confidence-based early exit with calibrated consistency guarantees. Up to about 3x.
- KR260: early exit breaks the "always the same compute" determinism unless the exit rule is itself integer-deterministic, which our datapath can guarantee. Exiting also needs the LM head at the exit layer, so the 0.7 s LM head must be fixed first.
- Closeness: 2

### D. Ternary / low-bit

**F15 — The Era of 1-bit LLMs: All LLMs are in 1.58 Bits (BitNet b1.58).** Shuming Ma et al., arXiv 2402.17764, 2024. https://arxiv.org/abs/2402.17764
- Key result: ternary {-1,0,1} weights trained from scratch match FP16 LLaMA perplexity from 3B parameters up.
- KR260: about 1.6–2 bits/weight versus our 8.5 means about 4–5x less weight traffic. Decode would drop to roughly 30 ms/token if bandwidth stays the bottleneck, and matmuls become adds/muxes that free DSPs.
- Closeness: 4

**F16 — BitNet b1.58 2B4T Technical Report.** Shuming Ma et al., arXiv 2504.12285, 2025. https://arxiv.org/abs/2504.12285
- Key result: an open native-ternary 2B model trained on 4T tokens, competitive with same-size full-precision open models. Its non-embedding weights take 0.4 GB.
- KR260: a 2B-class model at the same byte budget as our 0.6B Q8. This is a direct path to better planning capability at constant tokens/s, and the most important "capability" lever in this review.
- Closeness: 5

**F17 — 1-bit AI Infra: Part 1.1, Fast and Lossless BitNet b1.58 Inference on CPUs (bitnet.cpp).** Jinheng Wang et al., arXiv 2410.16144, 2024. https://arxiv.org/abs/2410.16144
- Key result: lookup-table ternary kernels give 1.37–6.17x CPU speedups and run a 100B BitNet on one CPU at human reading speed.
- KR260: this is the honest CPU baseline that a ternary FPGA decoder must beat, and the A53s on our own board could run it.
- Closeness: 3

**F18 — TerEffic: Highly Efficient Ternary LLM Inference on FPGA.** Chenyang Yin, Zhenyu Bai et al., arXiv 2502.16473, 2025. https://arxiv.org/abs/2502.16473
- Key result: packs 5 ternary weights into 8 bits. The fully on-chip 370M model reaches 16,300 tok/s (v2), and an HBM 2.7B model reaches 521 tok/s at 33 W.
- KR260: shows that ternary changes the regime from DDR-bound to on-chip. A 0.37B ternary model is about 75 MB, which still exceeds K26 BRAM+URAM (about 4.6 MB), so we would remain DDR-bound at about 1/5 of today's bytes.
- Closeness: 4

**F19 — TeLLMe: An Energy-Efficient Ternary LLM Accelerator for Prefill and Decode on Edge FPGAs.** Ye Qiao et al. (UC Irvine), arXiv 2504.16266, 2025. https://arxiv.org/abs/2504.16266
- Key result: on an AMD KV260 (the same K26 SOM as our KR260), table-lookup ternary matmul plus fused attention. Up to 9 tok/s at 7 W over 1,024-token contexts, with 0.55–1.15 s prefill for 64–128-token prompts.
- KR260: the closest competitor in the literature. It is the same silicon, also does full prefill+decode on PL, and its tokens/s is comparable to ours. We have no energy numbers yet, so they currently win on reporting.
- Closeness: 5

**F20 — TeLLMe v2: End-to-End Ternary LLM Prefill and Decode Accelerator with Table-Lookup Matmul on Edge FPGAs.** Ye Qiao et al., arXiv 2510.15926, 2025. https://arxiv.org/abs/2510.15926
- Key result: up to 25 tok/s decode under 5 W and 0.45–0.96 s TTFT for 64–128-token prompts, using disaggregated prefill/decode dataflows.
- KR260: sets the edge-FPGA bar at 3x our decode rate. A ternary port of our pipeline would land in the same class. Our differentiators must be determinism, integrity, the structured-output co-design, and energy per verified tool call.
- Closeness: 5

### E. Activation sparsity

**F21 — Deja Vu: Contextual Sparsity for Efficient LLMs at Inference Time.** Zichang Liu et al., ICML 2023. https://arxiv.org/abs/2310.17157
- Key result: small predictors choose input-dependent attention heads and MLP neurons. Over 2x latency reduction on OPT-175B with no quality loss.
- KR260: skipping MLP rows/columns means skipping weight bytes, which is a direct win for a bandwidth-bound stream. However, DDR bursts and Q8 32-blocks force channel-granular layouts (pre-transposed down_proj).
- Closeness: 3

**F22 — PowerInfer: Fast LLM Serving with a Consumer-grade GPU.** Yixin Song et al., SOSP 2024. https://arxiv.org/abs/2312.12456
- Key result: power-law "hot" neurons stay on the GPU and cold ones go to the CPU. Up to 11.7x over llama.cpp.
- KR260: the analogue is pinning hot-neuron weights in URAM and streaming cold ones. But Qwen3 uses SiLU-gated MLPs, which are not ReLU-sparse, so this needs ReLU-fied or TEAL-style thresholds.
- Closeness: 2

**F23 — TEAL: Training-Free Activation Sparsity in Large Language Models.** James Liu et al., ICLR 2025 (spotlight). https://arxiv.org/abs/2408.14690
- Key result: magnitude thresholding of hidden states reaches 40–50% model-wide sparsity with small degradation. 1.53x/1.8x decode speedup at 40%/50%, training-free and SwiGLU-compatible.
- KR260: about 1.3–1.6x if the weight layout lets us skip input channels in burst-sized groups. Thresholding is deterministic in integer arithmetic. Accuracy at 0.6B is unknown, since the paper's results are 7B+.
- Closeness: 4

**F24 — CATS: Contextually-Aware Thresholding for Sparsity in Large Language Models.** Donghyun Lee et al., COLM 2024. https://arxiv.org/abs/2404.08763
- Key result: thresholds the SiLU gate output, reaching about 50% MLP sparsity with about 15% wall-clock gain from a custom kernel.
- KR260: the MLP-only, gate-based variant. Simpler to implement than TEAL, since one gate decides which up/down rows to fetch.
- Closeness: 3

**F25 — Q-Sparse: All Large Language Models can be Fully Sparsely-Activated.** Hongyu Wang et al., arXiv 2407.10969, 2024. https://arxiv.org/abs/2407.10969
- Key result: top-K activation sparsification with a straight-through estimator, composable with BitNet b1.58 ("Block Q-Sparse"). Matches baselines at about 40% activated parameters.
- KR260: the combination of ternary and sparse activations compounds the byte reduction, roughly 4.5x × 1.5x. A purpose-trained sparse-ternary small model is the extreme design point for a bandwidth-bound fabric.
- Closeness: 3

### F. Non-autoregressive / diffusion LMs

**F26 — LLaDA: Large Language Diffusion Models.** Shen Nie et al., NeurIPS 2025. https://arxiv.org/abs/2502.09992
- Key result: an 8B masked-diffusion LM trained from scratch, competitive with LLaMA3-8B on in-context learning, and better on reversal tasks.
- KR260: bidirectional attention means no KV cache, so every denoising step streams all weights. Speed depends on emitting more than one token per step. For a 64-token JSON with fixed skeleton tokens, it can fill slots in parallel.
- Closeness: 2

**F27 — Dream 7B: Diffusion Large Language Models.** Jiacheng Ye et al., arXiv 2508.15487, 2025. https://arxiv.org/abs/2508.15487
- Key result: a diffusion LM initialized from an AR model (Qwen2.5) with context-adaptive noise rescheduling. Matches Qwen2.5-7B on several benchmarks, with strong planning and infilling.
- KR260: AR-to-diffusion conversion is the plausible route to a small diffusion model built from Qwen3-0.6B. Schema infilling ("fill these 5 values into this skeleton") is a natural fit for template-shaped maintenance plans.
- Closeness: 2

**F28 — Mercury: Ultra-Fast Language Models Based on Diffusion.** Inception Labs (Khanna et al.), arXiv 2506.17298, 2025. https://arxiv.org/abs/2506.17298
- Key result: commercial diffusion coding LMs at 1,109 / 737 tok/s on H100 (Mini/Small).
- KR260: shows that parallel token emission pays off when compute is plentiful relative to bandwidth. Our fabric is the opposite (DSP-light), so it is less clearly a win at batch 1.
- Closeness: 1

**F29 — Fast-dLLM: Training-free Acceleration of Diffusion LLM by Enabling KV Cache and Parallel Decoding.** Chengyue Wu et al., arXiv 2505.22618, 2025. https://arxiv.org/abs/2505.22618
- Key result: block-wise approximate KV cache plus confidence-threshold parallel decoding, up to 27x on LLaDA/Dream.
- KR260: it uses an approximate cache, which conflicts with our bit-exact discipline, though a fixed-schedule version is deterministic. Mainly evidence that dLLM latency hinges on caching.
- Closeness: 1

### G. Multi-token prediction

**F30 — Better & Faster Large Language Models via Multi-token Prediction.** Fabian Gloeckle et al., ICML 2024. https://arxiv.org/abs/2404.19737
- Key result: n independent output heads on a shared trunk improve code quality at scale and allow up to 3x self-speculative inference.
- KR260: same bandwidth concern as Medusa (extra unembedding passes) unless the heads share the LM head through small adapters, as DeepSeek-V3's sequential MTP module does (arXiv 2412.19437, reported about 85–90% second-token acceptance).
- Closeness: 3

### H. Hybrid / SSM / linear-attention small models

**F31 — Transformers are SSMs: Generalized Models and Efficient Algorithms through Structured State Space Duality (Mamba-2).** Tri Dao, Albert Gu, ICML 2024. https://arxiv.org/abs/2405.21060
- Key result: SSD layers are 2–8x faster than Mamba-1 and competitive with Transformers.
- KR260: decode remains weight-bound. An SSM only removes the K/V cache traffic and storage, which is small for us at ≤2k context. Little gain for short tool calls.
- Closeness: 2

**F32 — Hymba: A Hybrid-head Architecture for Small Language Models.** Xin Dong et al. (NVIDIA), ICLR 2025 (spotlight). https://arxiv.org/abs/2411.13676
- Key result: parallel attention+SSM heads, meta tokens, and cross-layer KV sharing. 1.5B beats Llama-3.2-3B with an 11.67x smaller cache and 3.49x throughput.
- KR260: the capability-per-parameter argument matters more to us than the cache savings. Meta tokens resemble our prefix cache in learned form.
- Closeness: 2

**F33 — Falcon-H1: A Family of Hybrid-Head Language Models.** Jingwei Zuo et al. (TII), arXiv 2507.22448, 2025. https://arxiv.org/abs/2507.22448
- Key result: parallel attention + Mamba-2 heads, with 0.5B–34B releases. The authors claim strong small-model results (Falcon-H1-0.5B/1.5B).
- KR260: a drop-in candidate model at our 0.5B size. Porting it needs an SSM scan unit in the HLS decoder.
- Closeness: 2

**F34 — Gated Delta Networks: Improving Mamba2 with Delta Rule.** Songlin Yang, Jan Kautz, Ali Hatamizadeh, ICLR 2025. https://arxiv.org/abs/2412.06464
- Key result: a gated delta-rule linear attention. It is the linear-attention block later adopted in Qwen3-Next's hybrid layout (Qwen3-Next itself is a model release/blog, not a paper).
- KR260: fixed-size recurrent state gives constant per-token cost and deterministic memory. This matters only if context grows well beyond 2k.
- Closeness: 1

### I. KV eviction / compression

**F35 — H2O: Heavy-Hitter Oracle for Efficient Generative Inference of LLMs.** Zhenyu Zhang et al., NeurIPS 2023. https://arxiv.org/abs/2306.14048
- Key result: keeping 20% heavy-hitter + recent tokens gives up to 29x throughput.
- KR260: at a 129-token JSON state the KV cache is about 2 MB BF16, which is trivial next to 640 MB of weights. Not worth it for our workload.
- Closeness: 1

**F36 — SnapKV: LLM Knows What You are Looking for Before Generation.** Yuhong Li et al., NeurIPS 2024. https://arxiv.org/abs/2404.14469
- Key result: an observation window selects the important prompt KV per head, giving 3.6x speed and 8.2x memory efficiency at 16k context.
- KR260: relevant only for long-history agent sessions. Our JSON-state compaction already solves this at the application level, and more cleanly (89.5% fewer tokens).
- Closeness: 1

**F37 — Efficient Streaming Language Models with Attention Sinks (StreamingLLM).** Guangxuan Xiao et al., ICLR 2024. https://arxiv.org/abs/2309.17453
- Key result: keeping 4 sink tokens plus a sliding window gives stable perplexity to 4M tokens and up to 22.2x speedup over sliding-window recomputation.
- KR260: a cheap fixed-memory fallback for a 2048-token BF16 cache in perpetual closed-loop operation, and fully deterministic.
- Closeness: 2

### J. Test-time compute, tool-use distillation, System-1 distillation

**F38 — Scaling LLM Test-Time Compute Optimally can be More Effective than Scaling Model Parameters.** Charlie Snell et al., ICLR 2025. https://arxiv.org/abs/2408.03314
- Key result: compute-optimal allocation of verifier search / revisions beats a 14x larger model on some prompts.
- KR260: at 125 ms/token we cannot afford many samples. But "sample N, verify with the rules engine / JSON validator" is cheap for 16-token outputs. With prefix reuse, N=4 short candidates cost about 4×2 s.
- Closeness: 3

**F39 — Can 1B LLM Surpass 405B LLM? Rethinking Compute-Optimal Test-Time Scaling.** Runze Liu et al., arXiv 2502.06703, 2025. https://arxiv.org/abs/2502.06703
- Key result: with process-reward-guided search, a 1B model beats 405B on MATH-500, and the optimal strategy depends on the policy model and the reward model.
- KR260: an external, deterministic verifier (schema + rules engine) is a "free PRM" for structured plans. This could lift the 0.6B maintenance-plan scores without a bigger model.
- Closeness: 3

**F40 — TinyAgent: Function Calling at the Edge.** Lutfi Eren Erdogan et al., EMNLP 2024 (Demo). https://arxiv.org/abs/2409.00608
- Key result: 1.1B/7B models fine-tuned on curated function-calling data, with tool retrieval, match or exceed GPT-4-Turbo on a MacOS agent task.
- KR260: a recipe for distilling our maintenance and BFCL tool vocabulary into Qwen3-0.6B. Tool RAG also shortens prompts.
- Closeness: 4

**F41 — Octopus v2: On-device Language Model for Super Agent.** Wei Chen, Zhiyuan Li, arXiv 2404.01744, 2024. https://arxiv.org/abs/2404.01744
- Key result: functions are encoded as special "functional tokens", so a 2B model selects a function with one token and then emits arguments. GPT-4-level accuracy with 35x latency reduction versus RAG-based calling.
- KR260: functional tokens collapse the function name to one decode step and shrink the JSON. Combined with grammar forcing, most of the output becomes argument values only.
- Closeness: 4

**F42 — xLAM: A Family of Large Action Models to Empower AI Agent Systems.** Jianguo Zhang et al. (Salesforce), arXiv 2409.03215, 2024. https://arxiv.org/abs/2409.03215
- Key result: 1B–8x22B action models. xLAM-1B (the "Tiny Giant") posts strong BFCL results relative to its size.
- KR260: shows that small (about 1B) models can be competitive on BFCL with targeted data. It is a natural baseline for our BFCL/200.
- Closeness: 3

**F43 — Distilling Step-by-Step! Outperforming Larger LLMs with Less Data and Smaller Model Sizes.** Cheng-Yu Hsieh et al., Findings of ACL 2023. https://arxiv.org/abs/2305.02301
- Key result: LLM rationales as multi-task supervision let a 770M T5 beat 540B PaLM few-shot on some tasks.
- KR260: supports the "System 1" cascade in which an LLM teacher distills into the v1/v2 classifiers and decision heads. The board answers the easy majority without decoding at all.
- Closeness: 3

### K. FPGA LLM baseline

**F44 — FlightLLM: Efficient LLM Inference with a Complete Mapping Flow on FPGAs.** Shulin Zeng et al., FPGA 2024. https://arxiv.org/abs/2401.03868
- Key result: configurable sparse DSP chains, always-on-chip decode, and length-adaptive compilation. Raises bandwidth utilization from 35.6% to 65.9%, with 6x energy efficiency versus V100S.
- KR260: we already run at about 95% port utilization on a far smaller device. FlightLLM is the platform that F08's FPGA speculation paper builds on, so it is the incumbent to cite.
- Closeness: 4

(44 entries. At least 22 are distinct, verified papers. Non-paper techniques mentioned only in passing: Prompt Lookup Decoding (GitHub, 2023) and Qwen3-Next (model release).)

---

## (1) Ranking for short structured tool calls (≤64 output tokens, mostly predictable JSON) on our decoder

**Baseline model.** One output token costs about T_d ≈ 125 ms of weight streaming plus LM-head cost. For a 16-token call, decode is about 2.0 s plus the LM head. I treat the 0.7 s LM head as a per-call cost; if it is per token, every LM-head item below becomes even more important.

**Key enabler.** B8 prefill already exists, so verifying or absorbing up to 8 tokens costs about one weight pass, provided 8-wide compute keeps up with the stream. Our DSPs are at 41%, so this needs to be measured. Our hardware is batch-shape-invariant and bit-exact (proven by the 328/328 prefix-cache match). Greedy speculative decoding is therefore exactly lossless on our board: the output is bit-identical to plain decode. GPU stacks cannot claim this; the 16 llama-server formatting divergences show why.

| Rank | Technique | Mechanism on KR260 | Back-of-envelope gain (16–64 tok JSON) | Cost / risk |
|---|---|---|---|---|
| 1 | Grammar jump-forward + forced-token batching (F10, F11, F12) | Schema-forced tokens (`{"name":"`, keys, `","arguments":{`, closing braces) skip the LM head and sampling. They are pushed through B8 prefill in groups. | In tool-call JSON, 40–60% of tokens are typically forced. Forced tokens cost about T_d/8 ≈ 16 ms instead of 125 ms. With 50% forced, decode time drops about 2x (16 tok: 2.0 s → about 1.1 s). | Low hardware cost; ARM-side FSM. Accuracy risk from token misalignment (F12). Fully deterministic. |
| 2 | Draft-and-verify via B8 with a free drafter: prompt/state lookup + grammar (F05, F06, F07) | The ARM proposes up to 7 tokens (copied argument spans from the prompt/JSON state, enum values, grammar-forced runs). One B8 pass verifies them greedily. | Mean accepted length τ ≈ 2.5–4 on copy-heavy arguments. Speedup ≈ τ / (1 + overhead), about 2–3x on the unforced half. Combined with rank 1, total decode about 3–4x (16 tok: about 0.6 s). | Needs a verify mode that returns 8 argmaxes. That needs the LM head on 8 positions, so rank 3 is a prerequisite. |
| 3 | Vocab-restricted / mask-aware LM head (F10 masks + our LM head) | Compute logits only for grammar-allowed tokens (often under 1k of 152k), with a full head only in free-text slots. Fix the 0.7 s versus 43 ms roofline gap. | LM head 0.7 s → under 50 ms on constrained steps. If the 0.7 s is per call, that is −0.65 s of a roughly 2.7 s decode-plus-head phase, about 25%. | Pure engineering. Must keep argmax bit-exact (it is identical over the allowed set). |
| 4 | Learned drafter EAGLE-3 / LayerSkip self-spec (F03, F13) | A 1-layer head (about 20 MB) or the first 8 layers draft. B8 verifies. | Small-model drafting for 0.6B gives τ ≈ 3–4 on in-domain JSON. About 2.5–3x on free-text argument values, which ranks 1–2 cannot predict. Increment over 1+2: about 1.3x. | Training data needed (we have traces). Extra on-chip buffers. |
| 5 | Ternary / 2-bit weights (F15–F20, F25) | Weight bytes drop about 4–5x, so T_d ≈ 30 ms. Or keep T_d and use a 2B-class BitNet model for capability. | About 4x decode speed at equal parameters. Alternatively about 3x the parameters at the same speed. This is the largest single gain but needs a different model and datapath. | Large RTL/HLS rework. TeLLMe already occupies this space on KV260, so the novelty must come from elsewhere. |
| 6 | Activation sparsity TEAL / CATS (F23, F24, F21) | Skip weight channels whose activations fall under a threshold, with a burst-granular layout. | 1.3–1.6x on MLP-dominated bytes, about 1.2–1.4x end to end. Compounds with 1–5. | Unverified at 0.6B. DDR burst granularity erodes the gain. |
| 7 | System-1 cascade / distillation (F43, F40, F41, project v1) | The classifier or decision head answers or routes without the decoder. Functional tokens collapse the function name. | At 50% coverage, those queries drop from seconds to 0.6 ms, so mean latency roughly halves. Functional tokens save the 3–8 name tokens per call. | Already partly built (v1/v2). Mostly a systems-integration story. |
| 8 | Test-time verify-and-retry (F38, F39) | N short samples with prefix reuse, verified by the rules engine / schema. | Hurts latency (N×). Helps accuracy on maintenance plans: the gain is in capability, not speed. | Deterministic only with seeded or beam-style enumeration. |
| 9 | Diffusion / MTP (F26–F30) | Parallel slot filling. | Uncertain at batch 1 on a compute-light fabric. No sub-1B dLLM with tool-use ability exists. | High risk, low near-term yield. |
| 10 | KV eviction, SSM/hybrid (F31–F37) | — | About 0% for ≤64-token outputs with 129-token JSON state. The KV cache is under 1% of bytes. | Only for long-horizon agents. |

**Stacked estimate (16-token cold call, decode portion only).** Ranks 1+2+3 alone take the roughly 2.7 s decode + LM-head phase to about 0.6–0.8 s, a 3.5–4.5x improvement, with zero change to the model and bit-identical outputs. Adding rank 5 (ternary) would reach about 0.2 s but requires a new model.

---

## (2) Already done on FPGAs vs not

**Done or published on FPGA**
- Ternary / BitNet on FPGA: TerEffic (datacenter/HBM and multi-FPGA), and TeLLMe v1/v2 on KV260 (the same K26 silicon). This niche is taken.
- Tree speculative decoding on an FPGA LLM accelerator: DATE 2026 on FlightLLM (datacenter-class AMD parts).
- Speculative decoding for Mamba on FPGA: SpecMamba.
- Sparsity: weight sparsity (FlightLLM sparse DSP chains; N:M co-design, arXiv 2512.24713). I found no FPGA paper on contextual or activation sparsity (TEAL/CATS/Deja Vu-style) for LLM decode in my searches.
- On-chip decode and high bandwidth utilization: FlightLLM.

**Not found on FPGA (as of this search)**
- Grammar-constrained / jump-forward decoding co-designed with an FPGA decoder. XGrammar and SGLang are GPU or CPU-host only.
- Speculative decoding on an edge SoC FPGA (Zynq-class, DDR4, under 10 W) for a transformer.
- A provably lossless and bit-exact speculative decoder. GPU implementations are not bit-exact across batch shapes, and DATE 2026 / SpecMamba do not claim determinism.
- Vocab-pruned / mask-aware LM head in hardware.
- Self-speculative early exit (LayerSkip) on FPGA.
- Diffusion LMs on FPGA. I saw nothing credible.
- Energy per verified structured action, as a metric, on any FPGA.

---

## (3) Gaps / open niches for this project

1. **"Exact speculation".** Greedy draft-and-verify on a batch-shape-invariant, bit-exact fabric gives a speedup with a proof that the output token IDs equal non-speculative decode. We could demonstrate this with the same N/N exact-match methodology used for prefix caching. No GPU stack can claim it, and the FPGA speculation papers do not.
2. **Grammar-co-designed decoding for tool calls.** Jump-forward, forced-token B8 batching, and a mask-restricted LM head integrated with the existing ARM JSON validator. This attacks our largest known inefficiency (LM head 0.7 s versus a 43 ms roofline), and edge structured-output acceleration is absent from FPGA literature.
3. **Free drafters from agent state.** Prompt- and JSON-state lookup drafting (REST-style) fits our JSON-state memory design exactly, because arguments are copied from state. A measurable acceptance-length study on BFCL and the maintenance benchmarks would be new.
4. **A metric nobody reports.** Joules and seconds per *validated* tool call, with abstention, as opposed to tokens/s. TeLLMe reports W and tok/s, so we need energy numbers to compete at all.
5. **Activation sparsity on a DDR-streaming fabric.** TEAL/CATS with burst-aligned channel grouping on FPGA. Unexplored, and a test of whether TEAL holds at 0.6B.
6. **Ternary plus our determinism/integrity stack.** Only pursue this if capability demands it (BitNet 2B4T at 0.4 GB). Frame it as "2B capability at 0.6B cost", not as another ternary accelerator, since TeLLMe owns that framing.
7. **Avoid for now.** Diffusion LMs, SSM hybrids, and KV eviction. These are high cost with near-zero gain for ≤64-token outputs at ≤2k context. Mention them only as future work.
