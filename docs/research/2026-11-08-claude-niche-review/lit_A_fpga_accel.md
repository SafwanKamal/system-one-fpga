# Lit review A: FPGA and edge-ASIC accelerators for LLM decoding and edge LLM inference

Agent A, compiled 2026-11-08. Sources were checked by web search on 2026-11-08. Numbers are what the authors report; when an abstract version and a secondary summary disagree, this file says so. Closeness score: 5 means it directly overlaps a full-fabric Qwen3-0.6B decoder on a small Zynq UltraScale+ board with bit-exact determinism.

Our reference point: Qwen3-0.6B Q8_0, all arithmetic on the KR260 PL (K26, XCK26 ZU5EV-class), 125/250 MHz, a 256-bit weight stream at about 95% of a 4 GB/s HP port, about 8 tok/s decode (125 ms/token), BF16 KV cache with 2048-token context, bit-exact against independent references, exact prefix-cache reuse with identical outputs, and SHA-verified sealed weights.

---

## Paper list

### A01. Pushing up to the Limit of Memory Bandwidth and Capacity Utilization for Efficient LLM Decoding on Embedded FPGA
- Authors: Jindong Li et al.
- Venue: DATE 2025. https://arxiv.org/abs/2502.10659
- Setup: Kria KV260 (4 GB of 64-bit DDR4-2400, about 19.2 GB/s peak), bare-metal with no OS. LLaMA2-7B with 4-bit weights (about 3.5 GB).
- Results: about 5 tok/s decode. Uses 93.3% of memory capacity and reaches about 85% of the theoretical bandwidth bound. Context is limited to about 1K tokens.
- Relation to us: The closest prior "decode on a Kria" paper. It already claims near-roofline bandwidth use on the same SoM family, so "bandwidth-efficient decode on Kria" is not new. It uses 4-bit, bare-metal, has no determinism claim, uses a much bigger model, and has a short context.
- **Closeness: 5**

### A02. Hummingbird: A Smaller and Faster Large Language Model Accelerator on Embedded FPGA
- Authors: Jindong Li, Tenglong Li et al.
- Venue: ICCAD 2025. https://arxiv.org/abs/2507.03308
- Setup: KV260 and ZCU104 (with Alveo U250 and Spartan UltraScale+ ports). LLaMA3-8B with GPTQ 4-bit weights and an 8-bit KV cache. 4K context; embeddings are offloaded to flash.
- Results: 4.8 tok/s on KV260 and 8.6 tok/s on ZCU104, at 93–94% model-bandwidth utilization. Versus prior embedded designs: −67% LUT, −39% DSP, −42% power.
- Relation to us: The state of the art on our exact board class. It shows that small-footprint, high-utilization decode on Zynq UltraScale+ has already been done. It attributes the remaining loss to AXI port arbitration, the same issue we see on HP ports.
- **Closeness: 5**

### A03. Hummingbird+ (Qwen3-30B-A3B MoE on a low-cost ZU2CG/3EG custom board)
- Authors: same group as A02.
- Venue: 2026; the arXiv ID was **not verified** (only secondary coverage, e.g. ai-radar.it and an analysis blog).
- Results (per secondary sources): GPTQ 4-bit Qwen3-30B-A3B at about 18 tok/s decode and 50 tok/s prefill on an XCZU3EG with 24 GB memory, BOM under $150.
- Relation to us: If confirmed, a Qwen3-family model on a smaller and cheaper Zynq UltraScale+ than the KR260, with higher tok/s. MoE sparsity drives the speed. Treat as unverified until the primary paper is found.
- **Closeness: 4**

### A04. On-Device Qwen2.5: Efficient LLM Inference with Model Compression and Hardware Acceleration
- Authors: Maoyang Xiang, Ramesh Fernando, Bo Wang.
- Venue: arXiv 2025. https://arxiv.org/abs/2504.17376
- Setup: KV260. Qwen2.5-0.5B with AWQ 4-bit and custom weight packing. Hybrid design: the ARM runs part of the model and the FPGA accelerates the matmuls.
- Results: about 5.1 tok/s (secondary review) versus a 2.8 tok/s baseline; 55% compression.
- Relation to us: The closest model and board match (sub-1B Qwen on Kria). It is CPU+FPGA hybrid, not full-fabric, 4-bit, and makes no determinism claim. At Q8 we are roughly 1.5x faster on a model of similar size.
- **Closeness: 5**

### A05. TeLLMe: An Energy-Efficient Ternary LLM Accelerator for Prefilling and Decoding on Edge FPGAs
- Authors: Ye Qiao et al. (UC Irvine).
- Venue: arXiv 2025. https://arxiv.org/abs/2504.16266
- Setup: KV260, Vitis HLS. BitNet-style 1.58-bit weights with 8-bit activations. Table-lookup ternary matmul engine, fused attention, and an integrated norm/quant unit.
- Results: up to 9.51 tok/s decode under 7 W with 1024-token context; 0.55–1.15 s prefill for 64–128-token prompts.
- Relation to us: An end-to-end prefill+decode HLS design on the same SoM, with energy reported. We have no energy numbers yet, which is the clear gap against it.
- **Closeness: 4**

### A06. TeLLMe v2: An Efficient End-to-End Ternary LLM Prefill and Decode Accelerator with Table-Lookup Matmul on Edge FPGAs
- Authors: Ye Qiao et al.
- Venue: arXiv 2025. https://arxiv.org/abs/2510.15926
- Setup: KV260, ternary weights.
- Results: up to 25 tok/s decode under 5 W; TTFT 0.45–0.96 s for 64–128-token prompts.
- Relation to us: Sets the "tok/s and W on KV260" bar that reviewers will compare us against. Ternary models are far weaker than Qwen3-0.6B at tool use, which is an angle we can argue.
- **Closeness: 4**

### A07. PD-Swap: Prefill-Decode Logic Swapping for End-to-End LLM Inference on Edge FPGAs via Dynamic Partial Reconfiguration
- Authors: Yifan Zhang, Zhiheng Chen, Ye Qiao, Sitao Huang.
- Venue: arXiv Dec 2025. https://arxiv.org/abs/2512.11550
- Setup: KV260. Uses dynamic partial reconfiguration to time-multiplex prefill and decode attention logic.
- Results: up to 27 tok/s decode, 1.3–2.1x over prior edge state of the art; includes a roofline DSE model.
- Relation to us: Directly addresses our CLB-congestion issue (92–96% CLB). Swapping prefill and decode logic is an obvious next step for us and is already published.
- **Closeness: 4**

### A08. LlamaF: An Efficient Llama2 Architecture Accelerator on Embedded FPGAs
- Authors: Han Xu et al. (UIUC).
- Venue: arXiv 2024. https://arxiv.org/abs/2409.11424
- Setup: ZCU102. TinyLlama 1.1B, W8A8 group-wise PTQ (secondary). Pipelined group-quantized MV (GQMV) unit that overlaps compute with weight transfer.
- Results: 14.3–15.8x speedup and 6.1x power efficiency versus the ZCU102 PS. The absolute tok/s is low (about 1.5 tok/s; not re-verified).
- Relation to us: Very similar quantization (group INT8 weights and activations) on Zynq UltraScale+. It accelerates only the matmuls, while we run full-fabric at roughly 5x the tok/s.
- **Closeness: 4**

### A09. Designing Efficient LLM Accelerators for Edge Devices (SECDA-LLM)
- Authors: Jude Haris et al. (Glasgow).
- Venue: arXiv 2024. https://arxiv.org/abs/2408.00462
- Setup: PYNQ-Z1 (Zynq-7020, Cortex-A9). TinyLlama in llama.cpp with a block-floating-point matmul accelerator designed in SystemC/HLS.
- Results: about 1.7 s/token, 11x over the A9 NEON baseline.
- Relation to us: Uses the same GGUF/llama.cpp quantized-block lineage (our Q8_0). It offloads only the matmul; we use GGUF Q8_0 blocks natively, full-fabric.
- **Closeness: 3**

### A10. MEADOW: Memory-efficient Dataflow and Data Packing for Low Power Edge LLMs
- Authors: Abhishek Moitra et al. (Yale/IBM).
- Venue: MLSys 2025. https://arxiv.org/abs/2503.11663
- Setup: ZCU102 with a 10 W budget. OPT-125M and OPT-1.3B. Token-parallel head-sequential dataflow plus lossless weight packing.
- Results: 1.5x lower decode latency and 2.5x lower prefill latency versus a GEMM baseline; more than 40% end-to-end gain.
- Relation to us: An edge Zynq UltraScale+ design with lossless weight compression. Lossless packing that keeps bit-exactness could cut our weight bytes per token.
- **Closeness: 3**

### A11. FlightLLM: Efficient Large Language Model Inference with a Complete Mapping Flow on FPGAs
- Authors: Shulin Zeng et al.
- Venue: FPGA 2024. https://arxiv.org/abs/2401.03868
- Setup: Alveo U280 and Versal VHK158 (HBM). LLaMA2-7B and OPT-6.7B with N:M sparsity and mixed-precision quantization; configurable sparse DSP chain, always-on-chip decode, length-adaptive compilation.
- Results: 6.0x energy efficiency and 1.8x cost efficiency versus V100S (batch 1). 92.5 tok/s on VHK158 (1.2x A100), with 64.8% bandwidth utilization.
- Relation to us: The canonical datacenter FPGA LLM baseline. Its "always-on-chip decode" and instruction-compilation ideas are prior art for any decode-dataflow claim.
- **Closeness: 2**

### A12. DFX: A Low-latency Multi-FPGA Appliance for Accelerating Transformer-based Text Generation
- Authors: Seongmin Hong et al.
- Venue: MICRO 2022. https://arxiv.org/abs/2209.10797
- Setup: 4x Alveo U280. GPT-2 up to 1.5B in FP16; a custom overlay ISA with model parallelism.
- Results: 5.58x speedup and 3.99x energy efficiency versus 4x V100 for text generation.
- Relation to us: The first major FPGA text-generation system and the source of the "FPGAs win at batch-1 decode" argument. It is foundational background, not a competitor.
- **Closeness: 2**

### A13. Understanding the Potential of FPGA-Based Spatial Acceleration for Large Language Model Inference
- Authors: Hongzheng Chen et al. (Cornell, Zhiru Zhang).
- Venue: ACM TRETS 2024 (FCCM'24 journal track), DOI 10.1145/3656177. https://arxiv.org/abs/2312.15159
- Setup: U280 HLS kernels for BERT and GPT-2, plus an analytical model for spatial accelerators.
- Results: up to 13.4x over prior FPGA BERT accelerators. For GPT-2: 2.2x over DFX in prefill; 1.9x speed and 5.7x energy efficiency over A100 in decode.
- Relation to us: Gives the analytical performance model reviewers will expect us to use for our roofline argument. Its temporal/spatial taxonomy places our HLS decoder as temporal overlay-like.
- **Closeness: 2**

### A14. Allo: A Programming Model for Composable Accelerator Design
- Authors: Hongzheng Chen et al.
- Venue: PLDI 2024. https://arxiv.org/abs/2404.04815
- Setup: A Python-embedded ADL. Includes a GPT-2 spatial dataflow case study on U280.
- Relation to us: Tooling prior art. Composable HLS schedules could reduce our HLS refactoring cost. It is not a competitor.
- **Closeness: 1**

### A15. LoopLynx: A Scalable Dataflow Architecture for Efficient LLM Inference
- Authors: Jianing Zheng, Gang Chen (Sun Yat-sen).
- Venue: arXiv 2025 (DATE 2025 per some listings, unverified). https://arxiv.org/abs/2504.09561
- Setup: Alveo-class; GPT-2; hybrid spatial-temporal kernels, multi-FPGA.
- Results: 1.67x over A100 using 37.3% of its energy on a single FPGA with 2 nodes. Dual FPGA: 2.52x speedup at 48.1% of A100 energy (the figures vary between versions).
- Relation to us: Time-multiplexed large dataflow kernels are close to what our layer-reused HLS decoder does. It shows the architecture style is not new.
- **Closeness: 2**

### A16. EdgeLLM: A Highly Efficient CPU-FPGA Heterogeneous Edge Accelerator for Large Language Models
- Authors: Mingqiang Huang, Ao Shen et al.
- Venue: IEEE TCAS-I 2025. https://arxiv.org/abs/2407.21325
- Setup: VCU128 (HBM) with a host CPU. ChatGLM2-6B and others; FP16xFP16 for attention and FP16xINT4 for FFN; log-scale structured sparsity; end-to-end compiler.
- Results: 1.91x throughput and 7.55x energy efficiency versus A100 (v1 abstract; an earlier summary gives 1.67x/7.4x); 10–24% better than FlightLLM.
- Relation to us: "Edge" in name only (VCU128 is a large part). It is useful for the CPU-FPGA split framing; our A53 does control only.
- **Closeness: 2**

### A17. HLSTransform: Energy-Efficient Llama 2 Inference on FPGAs Via High Level Synthesis
- Authors: Andy He, Darren Key et al.
- Venue: ICML 2024 ES-FoMo workshop. https://arxiv.org/abs/2405.00738
- Setup: VU9P (AWS F1). Llama-2 110M (llama2.c) in INT8, Vitis HLS, open source.
- Results: 57.11 tok/s at 200 MHz. Energy per token is up to 12.75x lower than CPU and 8.25x lower than RTX 3090 GPU; 0.53x the 3090's throughput.
- Relation to us: The HLS-from-llama2.c precedent. It uses a toy model and a big FPGA. Our Qwen3-0.6B on a $350 board is a large step beyond it in realism.
- **Closeness: 3**

### A18. AccLLM: Accelerating Long-Context LLM Inference Via Algorithm-Hardware Co-Design
- Authors: Yanbiao Liang, Huihong Shi, Haikuo Shao, Zhongfeng Wang.
- Venue: arXiv 2025. https://arxiv.org/abs/2505.03745
- Setup: U280. Llama-2-7B with 2:4 pruning, Λ-shaped attention (KV eviction), and W2A8KV4.
- Results: 4.07x energy efficiency and 2.98x throughput versus FlightLLM. KV memory for 7K context drops from 3.5 GB to 1 GB (secondary).
- Relation to us: KV compression and eviction for long context on FPGA is saturated territory. Our BF16 2048-context cache is conservative by comparison, but lossless.
- **Closeness: 2**

### A19. SkipOPU: An FPGA-based Overlay Processor for LLMs with Dynamically Allocated Computation
- Venue: arXiv 2026. https://arxiv.org/abs/2603.14785 (authors not re-verified)
- Setup: U280 overlay. Token skipping with KV reuse for skipped tokens.
- Results: 1.31–2.55x bandwidth efficiency versus GPU and FPGA baselines.
- Relation to us: The only FPGA "KV reuse" we found. It is approximate and within one request, not exact cross-request prefix reuse as in our v16.
- **Closeness: 2**

### A20. FAST-Prefill: FPGA Accelerated Sparse Attention for Long Context LLM Prefill
- Venue: arXiv 2026. https://arxiv.org/abs/2602.20515 (authors not re-verified)
- Setup: FPGA sparse-attention prefill with a hot/cold dual-tier KV cache.
- Relation to us: Covers prefill/KV-tiering for long context. Exact cross-request prefix reuse is again absent.
- **Closeness: 2**

### A21. CXL-SpecKV: A Disaggregated FPGA Speculative KV-Cache for Datacenter LLM Serving
- Venue: arXiv Dec 2025. https://arxiv.org/abs/2512.11920 (authors not re-verified)
- Setup: A CXL-attached FPGA KV store with speculative prefetch and compression.
- Relation to us: The datacenter end of KV management on FPGA. It confirms that hardware KV management is active but not at the edge or deterministic.
- **Closeness: 1**

### A22. SpecMamba: Accelerating Mamba Inference on FPGA with Speculative Decoding
- Venue: arXiv 2025 (ICCAD'25 per listing, unverified). https://arxiv.org/abs/2509.19873
- Setup: AMD FPGAs; Mamba with speculative decoding; handles the difficulty of rolling back SSM state.
- Results: 2.27x over GPU and 2.85x over prior FPGA designs.
- Relation to us: Speculative decoding on FPGA exists, so it is not an open niche by itself. A DATE 2026 paper (proceedings item 371; title and authors not verified) also gives an analytical framework for tree speculative decoding on FlightLLM-class FPGAs. Exact-match speculative decoding is a natural fit for a bit-exact datapath, because verification is deterministic.
- **Closeness: 2**

### A23. SpecPIM: Accelerating Speculative Inference on PIM-Enabled System via Architecture-Dataflow Co-Exploration
- Authors: Cong Li et al.
- Venue: ASPLOS 2024. DOI 10.1145/3620666.3651352
- Setup: PIM plus a host accelerator; draft and target models split across processing-in-memory and the host.
- Relation to us: The draft/target hardware split. Relevant only if we add a draft model (e.g. a MiniLM-class model from v2) beside the Qwen decoder.
- **Closeness: 1**

### A24. LightMamba: Efficient Mamba Acceleration on FPGA with Quantization and Hardware Co-design
- Authors: Renjie Wei et al. (PKU).
- Venue: DATE 2025. https://arxiv.org/abs/2502.15260
- Setup: VCK190 and U280. Mamba-2.7B with rotation-assisted 4-bit quantization and power-of-two SSM quantization; Hadamard unit.
- Results: 93 tok/s on U280 (1.43x GPU); 4.65–6.06x energy efficiency on VCK190 (about 7.21 tok/s there).
- Relation to us: SSM decode avoids KV growth. This is an alternative architecture, not a competitor for a Qwen-based tool-calling system.
- **Closeness: 1**

### A25. TerEffic: Highly Efficient Ternary LLM Inference on FPGA
- Authors: Chenyang Yin et al. (incl. Tulika Mitra).
- Venue: arXiv 2025. https://arxiv.org/abs/2502.16473
- Setup: Alveo; a fully on-chip ternary 370M model (1.6-bit encoding) and an HBM variant for 2.7B.
- Results: 12.7k–16.3k tok/s (v1/v2 abstracts), 149–192x Jetson Orin Nano, about 455–467 tok/s/W. HBM 2.7B: 521 tok/s (2x A100).
- Relation to us: It shows that decode stops being DRAM-bound once weights fit on chip. That points to on-chip (URAM) weight residency for small task-specific models as the escape from our 8 tok/s.
- **Closeness: 2**

### A26. Scalable MatMul-free Language Modeling
- Authors: Rui-Jie Zhu et al. (UCSC).
- Venue: arXiv 2024. https://arxiv.org/abs/2406.02528
- Setup: Ternary-weight, MatMul-free LM with a custom RTL FPGA prototype.
- Results: billion-parameter scale at about 13 W, "beyond human-readable throughput". The multi-core numbers are projections from a single core.
- Relation to us: Model-architecture co-design on FPGA. It is not applicable to stock Qwen3, but it is cited as the "radical" alternative.
- **Closeness: 1**

### A27. LUT-LLM: Efficient Large Language Model Inference with Memory-based Computations on FPGAs
- Authors: Zifan He, Shengyu Ye, Rui Ma, Yang Wang, Jason Cong.
- Venue: arXiv Nov 2025 (rev. Mar 2026). https://arxiv.org/abs/2511.06174
- Setup: AMD V80. Customized **Qwen3-1.7B** with vector-quantized weights; centroid search and 2D table lookups in on-chip memory.
- Results: 1.66x lower latency than MI210 and 1.72x the energy efficiency of A100; 2.16x for the 32B model.
- Relation to us: A Qwen3-family model on FPGA (datacenter class, approximate VQ). It shows Qwen3 on FPGA is already in the literature; our differentiator has to be the edge board, Q8 exactness and determinism.
- **Closeness: 3**

### A28. FIGLUT: An Energy-Efficient Accelerator Design for FP-INT GEMM Using Look-Up Tables
- Authors: Gunho Park et al.
- Venue: HPCA 2025. https://arxiv.org/abs/2503.06862
- Setup: ASIC-oriented, LUT-based FP-activation by INT-weight GEMM for weight-only quantization.
- Results: 59% higher TOPS/W at 3-bit; 98% higher at matched perplexity (2.4-bit).
- Relation to us: LUT-GEMM style is irrelevant at Q8 (no LUT advantage). It matters only if we move to Q4 or lower.
- **Closeness: 1**

### A29. LUT-GEMM: Quantized Matrix Multiplication based on LUTs for Efficient Inference in Large-Scale Generative Language Models
- Authors: Gunho Park et al.
- Venue: ICLR 2024. https://arxiv.org/abs/2206.09557
- Relation to us: The algorithmic origin of FIGLUT, T-MAC and TeLLMe-style table lookup. Background only.
- **Closeness: 1**

### A30. T-MAC: CPU Renaissance via Table Lookup for Low-Bit LLM Deployment on Edge
- Authors: Jianyu Wei et al.
- Venue: EuroSys 2025. https://arxiv.org/abs/2407.00088
- Setup: CPU (ARM/x86) LUT kernels for 1–4-bit weights. Reports BitNet-3B at about 11 tok/s on a Raspberry Pi 5-class device (paper's own claim).
- Relation to us: The strongest "just use the CPU" rebuttal at the edge. Our A53 baseline comparisons should cite it and a llama.cpp/T-MAC run on the same board.
- **Closeness: 2**

### A31. CHARM: Composing Heterogeneous Accelerators for Matrix Multiply on Versal ACAP Architecture
- Authors: Jinming Zhuang et al.
- Venue: FPGA 2023. https://arxiv.org/abs/2301.02359
- Setup: Versal VCK190 AI Engines, dense GEMM for BERT/ViT/MLP.
- Relation to us: The main Versal AIE transformer reference. We found **no peer-reviewed Versal AIE work that does batch-1 LLM decode**. AIE4ML (arXiv 2512.15946) mentions decode only as motivation. Versal AIE for LLM decode remains thin, but it is the wrong platform for us.
- **Closeness: 1**

### A32. Slim-Llama: A 4.69 mW Large-Language-Model Processor with Binary/Ternary Weights for Billion-Parameter Llama Model
- Authors: Sangyeob Kim et al. (KAIST/Yonsei, Hoi-Jun Yoo).
- Venue: ISSCC 2025.
- Results: 4.69 mW at 25 MHz to 82 mW at 200 MHz; 500 KB SRAM; up to 3B binary/ternary Llama; about 9 pJ/param.
- Relation to us: The edge-ASIC end point. It shows that W/token claims are dominated by ASICs, and that FPGA energy claims must be framed as reconfigurable plus exact, not lowest energy.
- **Closeness: 1**

### A33. Eliminating Nondeterminism in LLM Inference via Integer-Only Arithmetic
- Authors: not verified (NeurIPS 2026 listing, https://neurips.cc/virtual/2026/178970).
- Setup: The **full Qwen3-0.6B** forward pass in exact integer arithmetic (matmul, softmax, RMSNorm, SwiGLU, RoPE) on GPUs and CPUs.
- Results: 9 runs across A100, H100, AMD, Intel and Apple produce one identical output hash (fp16 gives 9 distinct hashes). PPL 20.72 versus 20.95 fp16. 106 tok/s on A100 batch 1; prefill runs at 0.13x fp16.
- Relation to us: **The most dangerous overlap for a "determinism" claim.** It uses the same model and makes cross-platform bit-exactness its headline, so determinism alone is no longer novel. Our differences: deterministic FP32-in-fabric on a $350 edge board, exact prefix-cache equivalence, and a measured contrast with llama-server caching drift. Possibly also hardware-level reproducibility of an independent integer reference. We must read and cite it.
- **Closeness: 4 (on determinism), 2 (on hardware)**

(Not numbered, background only: I-LLM integer-only LLM inference, arXiv 2405.17849, and the Thinking Machines "Defeating Nondeterminism in LLM Inference" blog (2025), which is the batch-invariance argument behind our llama-server drift finding.)

---

## (1) What is saturated (claims we cannot make as novel)

1. **"First LLM on an embedded/Kria FPGA" and "near-roofline decode on Zynq UltraScale+".** A01 (7B on KV260, about 85% of BW), A02 (93–94% BW util., 4K context, KV260 and ZCU104), A04 (Qwen2.5-0.5B on KV260), A05–A07 (TeLLMe/PD-Swap, 9.5–27 tok/s on KV260) and A08/A09 cover it. Our ~95% HP-port efficiency matches theirs; it does not beat them.
2. **"Qwen-family model on FPGA."** A04 (Qwen2.5-0.5B, Kria), A27 (Qwen3-1.7B, V80) and possibly A03 (Qwen3-30B-A3B on a ZU3EG) cover it.
3. **Energy efficiency versus GPU at batch 1.** FlightLLM, EdgeLLM, Chen et al., LoopLynx, HLSTransform, TeLLMe and LightMamba all claim it. Edge ASICs (Slim-Llama) dominate absolute energy.
4. **KV-cache compression, eviction, sparsity and long context on FPGA.** AccLLM, Hummingbird (8-bit KV), FAST-Prefill, SkipOPU and CXL-SpecKV cover it.
5. **LUT/table-lookup low-bit matmul and ternary LLMs on FPGA.** TeLLMe v1/v2, TerEffic, LUT-LLM, FIGLUT, T-MAC and MatMul-free cover it.
6. **Prefill/decode specialization on edge FPGA.** PD-Swap (DPR) and TeLLMe cover it.
7. **Speculative decoding on FPGA.** SpecMamba and the DATE'26 analytical framework cover it.
8. **Integer/deterministic Qwen3-0.6B inference as such.** A33 shows cross-platform bit-identical Qwen3-0.6B on GPU/CPU.
9. **Analytical roofline/performance models for FPGA LLMs.** Chen et al. TRETS and PD-Swap's DSE cover it.

## (2) Gaps and open niches, tied to our assets

1. **Exact cross-request prefix/KV reuse in hardware with proven output equivalence.** No FPGA paper found does cross-request prefix caching. SkipOPU and FAST-Prefill reuse approximately or within one prompt. Our v16 (70.7% fewer prompt tokens evaluated, 328/328 identical ID sequences against cold controls, llama-server showing 16 differences under caching) is a clean, measurable, novel systems claim: "cache-transparent" edge inference. This is our strongest niche.
2. **Determinism as a systems property of an FPGA decoder, not an arithmetic trick.** A33 does integer-only arithmetic on GPU. Nobody reports bit-exact board output against an independent reference for a modern LLM on FPGA, nor determinism under caching, preemption or leasing. Our C-sim/board fixture chain plus the llama-server drift measurement is the comparison to make. We should position against A33 (FP32-capable fabric, no integer retraining or approximation, same GGUF weights).
3. **Integrity and assurance of edge LLM inference.** No accelerator paper treats weight-integrity verification (SHA), sealed read-only mappings, exclusive leases or evidence seals. Combined with typed outputs and R5 ownership (v2), this is a "trustworthy edge LLM appliance" angle that the throughput-focused FPGA literature ignores.
4. **Q8 (near-lossless) full-fabric decode.** Every edge-Kria competitor uses 4-bit or ternary (A01–A07), trading accuracy for bandwidth. A Q8_0 GGUF-exact full-fabric decoder that is *identical to the reference llama.cpp quantization* is uncommon. Its claim is fidelity, not speed. The task-capability benchmarks (BFCL, maintenance plans) let us quantify what 4-bit/ternary loses.
5. **Application-level evaluation.** Edge FPGA LLM papers report tok/s, perplexity and sometimes MMLU, but almost never structured tool-call validity or agent-memory metrics. Our JSON-state retention study (89.5% fewer input tokens) and BFCL subsets are unusual in this venue.
6. **Measured energy on the KR260.** TeLLMe and Hummingbird report watts; we have none. A rail-level SOM_5V0 measurement with MLPerf-Power-style boundaries, especially J/token with and without prefix caching, would close a reviewer objection. Prefix caching gives an energy saving no one else can claim.
7. **On-chip-resident small task models.** TerEffic shows that DRAM-free decode is orders of magnitude faster. A URAM-resident small head (the v1/v2 classifier or decision head) cascaded with the Qwen decoder ("System One / System Two" on one fabric) is unexplored on edge FPGA.
8. **Deterministic speculative decoding.** With a draft model (e.g. a pruned Qwen or n-gram/prefix-cache drafts), exact verification is trivially reproducible on our datapath. No edge-FPGA LLM paper does it. It is a natural way to raise our 8 tok/s without giving up bit-exactness.

## (3) Decode throughput per unit of memory bandwidth

Column definitions:
- **tok/s per GB/s** = decode tok/s ÷ peak DRAM bandwidth available to the accelerator.
- **Implied BW utilization** = tok/s × approximate weight bytes streamed per token ÷ peak BW (ignores KV traffic).
- Byte counts are our approximations from the reported precision. Treat them as ±20%.

| Work | Platform (peak BW) | Model / precision (≈ bytes/token) | Decode tok/s | tok/s per GB/s | Implied BW util. |
|---|---|---|---|---|---|
| **Ours (v9e)** | KR260, one HP port (4 GB/s as stated) | Qwen3-0.6B Q8_0 (≈0.64 GB) | ≈8 | **2.0** | ≈1.28 (see note) |
| Li et al. A01 | KV260 DDR4 (19.2) | LLaMA2-7B 4-bit (≈3.5 GB) | ≈5 | 0.26 | ≈0.85–0.9 (reported 85%) |
| Hummingbird A02 | KV260 (19.2) | LLaMA3-8B GPTQ-4b (≈3.7 GB excl. embed) | 4.8 | 0.25 | 0.93 (reported) |
| Hummingbird A02 | ZCU104 PS+PL DDR (≈38) | same | 8.6 | ≈0.23 | 0.94 (reported) |
| On-device Qwen2.5 A04 | KV260 (19.2) | Qwen2.5-0.5B AWQ-4b (≈0.3–0.4 GB) | ≈5.1 | 0.27 | ≈0.1 (CPU-hybrid bound) |
| TeLLMe A05 | KV260 (19.2) | ternary ≈0.7B (≈0.15–0.2 GB) | 9.51 | 0.50 | ≈0.1 |
| TeLLMe v2 A06 | KV260 (19.2) | ternary | 25 | 1.30 | ≈0.25 |
| PD-Swap A07 | KV260 (19.2) | ternary (likely BitNet-class) | 27 | 1.41 | ≈0.25 |
| SECDA-LLM A09 | PYNQ-Z1 DDR3 16-bit (≈2.1) | TinyLlama BFP (≈0.6 GB) | ≈0.59 | ≈0.28 | ≈0.17 |
| HLSTransform A17 | VU9P / F1 DDR4 (≈64) | Llama-2 110M INT8 (≈0.11 GB) | 57 | 0.89 | ≈0.1 |
| FlightLLM A11 | VHK158 HBM2e (≈819) | LLaMA2-7B sparse mixed (≈4–6 GB eff.) | 92.5 | 0.11 | 0.648 (reported) |
| LightMamba A24 | U280 HBM (460) | Mamba-2.7B 4-bit (≈1.4 GB) | 93 | 0.20 | ≈0.28 |
| Hummingbird+ A03 (unverified) | ZU3EG custom (unknown, LPDDR4) | Qwen3-30B-A3B 4-bit (≈1.5–2 GB active) | 18 | n/a | n/a |

**Where we sit.** On raw tok/s per GB/s we are at the top of the table (2.0), but only because our model is small. Bandwidth-normalized, every competent bandwidth-bound design converges to "bytes per token ÷ BW". Li et al. and Hummingbird are already at 85–94% utilization, the same as our ~95% port efficiency. So **our decode efficiency is at parity with the state of the art, not beyond it**.

Note: our implied utilization is above 1 (0.64 GB × 8 tok/s ≈ 5.1 GB/s > 4 GB/s), so the stated numbers do not reconcile. Either:
- the effective weight bandwidth exceeds 4 GB/s (256-bit × 250 MHz = 8 GB/s raw), or
- not all 0.64 GB is streamed per token (e.g. the embedding table is not re-read, or the LM head is amortized), or
- "~8 tok/s" excludes the LM head.

The team should pin down this number before publishing any bandwidth comparison.

The big lever is our **absolute bandwidth deficit**: we use about 4–8 GB/s of the K26's ~19.2 GB/s PS DDR4. Using multiple HP ports or HPC ports could reach Hummingbird-level utilization of the full DDR and give roughly 2–4x decode, i.e. about 20–30 tok/s at Q8, before considering 4-bit. That would make us competitive with TeLLMe v2 and PD-Swap at much higher model fidelity.
