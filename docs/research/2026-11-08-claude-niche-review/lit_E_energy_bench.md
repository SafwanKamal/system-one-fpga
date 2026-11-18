# Literature review E: Measuring and benchmarking edge LLM inference (energy, latency, cold start, caching, agents)

Agent E, 2026-11-08. All entries below were checked by web search or by fetching the arXiv/venue page in this session. Numbers come from abstracts or fetched text unless marked "derived", meaning I computed them from reported tok/s and W. Each entry is rated for closeness to the KR260 Qwen3-0.6B full-fabric decoder project, from 1 (background) to 5 (direct competitor or template). Where I could not pull a number out of a paper's text (it was only in a figure), I say so and give no number.

---

## A. Benchmark suites and methodology standards

**E01. MLPerf Power: Benchmarking the Energy Efficiency of Machine Learning Systems from µWatts to MWatts for Sustainable AI.** A. Tschand et al. (MLCommons, more than 20 organizations). HPCA 2025, pp. 1201–1216 (per dblp). https://arxiv.org/abs/2410.12032
- Numbers: 1,841 reproducible measurements from 60 systems. Measures whole-system power at the wall or DC input. Efficiency is reported as samples/J. LLM workloads (GPT-J, Llama 2) improved by more than 100x across about one year of versions.
- Relation: this is the boundary/disclosure template our methods study already copies. To match it, a KR260 number must state its measurement boundary (SOM rail, carrier board, or wall) and the scenario (single-stream).
- Closeness: 4

**E02. MLPerf Tiny Benchmark.** C. Banbury et al. NeurIPS 2021 Datasets & Benchmarks. https://arxiv.org/abs/2106.07597
- Numbers: four tasks (KWS, VWW, IC, AD) with models around 100 kB. Accuracy, latency and energy are measured using an EnergyRunner-style harness.
- Relation: its energy-harness rules are the closest precedent for v1 (the CLINC150 classifier on Artix-7). It has no LLM track, which shows the gap between "tiny" and "client" benchmarks.
- Closeness: 2

**E03. MLPerf Inference Benchmark.** V. J. Reddi et al. ISCA 2020. https://arxiv.org/abs/1911.02549 (venue from my prior knowledge; not re-checked this session)
- Numbers: defines the single-stream, multi-stream, server and offline scenarios, the LoadGen tool, and edge vs datacenter divisions. Llama 3.1-8B was first added in v5.1 (2025), per vendor write-ups. I did not verify official edge-division LLM results.
- Relation: "single-stream" is the right scenario for our batch-1 board. We should report p90 latency per query rather than a mean.
- Closeness: 3

**E04. MLPerf Client v1.0.** MLCommons, released 2025-07-30 (benchmark software, not a paper). https://mlcommons.org/benchmarks/client and https://github.com/mlcommons/mlperf_client/releases/tag/v1.0
- Numbers: models are Llama 2 7B Chat, Llama 3.1 8B Instruct and Phi-3.5 Mini. Metrics are TTFT and TPS for five prompt categories, combined by geometric mean. AMD (a participant, so a vendor figure) reports Ryzen AI Max+ 395 TTFT under 0.7 s on Phi-3.5.
- Relation: this is the only standardized client-LLM metric pair (TTFT plus TPS). It does not measure energy. Its smallest model (about 3.8B) is far larger than ours.
- Closeness: 3

## B. Power-measurement accuracy

**E05. Part-time Power Measurements: nvidia-smi's Lack of Attention.** Z. Yang, K. Adámek, W. Armour (Oxford). arXiv 2312.02741 (v3, Dec 2024); reported as SC'24 (venue not re-confirmed). https://arxiv.org/abs/2312.02741
- Numbers: on A100/H100, only about 25% of runtime is actually sampled. Error is about ±5% of reading, against NVIDIA's claimed ±5 W. Their best practices cut energy-measurement error by up to 35%.
- Relation: this is the main citation for "onboard sensors need validation". KR260 SOM rail telemetry needs a similar check of sampling coverage and averaging window.
- Closeness: 4

**E06. Accurate Calibration of Power Measurements from Internal Power Sensors on NVIDIA Jetson Devices.** N. Shalavi, A. Khoshsirat, M. Stellini, A. Zanella, M. Rossi. IEEE EDGE 2023. https://arxiv.org/abs/2306.13107
- Numbers: built-in Jetson INA sensors underestimate power by up to 50%. A regression against an external probe (PicoScope plus Keysight current probe) brings error within 3%.
- Relation: this is the direct methodological template for calibrating the KR260 SOM_5V0 rail against an external DC meter. It also shows how large the error can be if we skip calibration.
- Closeness: 5

**E07. Zeus: Understanding and Optimizing GPU Energy Consumption of DNN Training.** J. You, J.-W. Chung, M. Chowdhury. NSDI 2023. https://www.usenix.org/conference/nsdi23/presentation/you
- Numbers: 15.3–75.8% training energy savings from power-limit and batch-size tuning. It is also the measurement library behind ML.ENERGY.
- Relation: background for programmatic energy windows (begin/end window APIs). Our ARM service could expose similar per-request energy windows.
- Closeness: 2

**E08. The ML.ENERGY Benchmark: Toward Automated Inference Energy Measurement and Optimization.** J.-W. Chung, M. Chowdhury, et al. NeurIPS 2025 Datasets & Benchmarks. https://arxiv.org/abs/2505.06371
- Numbers: 40 model architectures across 6 tasks. It builds a time–energy Pareto frontier, and automated optimizations cut energy by more than 40% without changing outputs. A public leaderboard is at ml.energy.
- Relation: this is the datacenter reference for J/request and J/token methodology. It covers GPUs only, with no edge, FPGA or determinism dimension.
- Closeness: 3

**E09. From Words to Watts: Benchmarking the Energy Costs of Large Language Model Inference.** S. Samsi et al. (MIT LL). IEEE HPEC 2023 (Xplore 10363447; HPEC label not explicitly confirmed). https://arxiv.org/abs/2310.03003
- Numbers: LLaMA 7B–65B on V100/A100 with up to 32 GPUs. Energy per token and per response are measured using GPU telemetry.
- Relation: an early "energy per token" baseline that is often cited. It relies only on GPU telemetry, the weakness that E05 and E31 later quantify.
- Closeness: 2

## C. Edge-device LLM characterization (phones, SBCs, Jetson, Apple)

**E10. MELTing point: Mobile Evaluation of Language Transformers.** S. Laskaridis, K. Katevas, L. Minto, H. Haddadi. MobiCom 2024. https://arxiv.org/abs/2403.12844
- Numbers: Zephyr-3B 4-bit uses 0.20–0.21 mWh/token on MLC (about 0.72–0.76 J/token, derived) and 0.16 mWh/token (about 0.58 J/token) on LLMFarm on iPhone 14 Pro. TinyLlama-1.1B 4-bit on Galaxy S23 with llama.cpp runs at about 13.6 tok/s on CPU. iPhone peak power is above 18 W, sustained about 13.8 W. Phones were measured with a Monsoon meter at 5 kHz with the battery bypassed; Jetson with onboard sysfs probes at about 100 Hz. Model load takes about 2.4 s.
- Relation: this is the gold standard for edge LLM energy method (external meter, battery bypass, baseline subtraction) and the most-cited per-token phone figures. Our energy study should copy its subtract-idle protocol.
- Closeness: 5

**E11. Sometimes Painful but Promising: Feasibility and Trade-offs of On-Device Language Model Inference.** M. Abstreiter, S. Tarkoma, R. Morabito. arXiv 2503.09114 (v2; ACM-listed). https://arxiv.org/abs/2503.09114
- Numbers: Qwen2 0.5B/1.5B, Llama 3.2 1B/3B, Gemma 2 2B and Phi-3.5 mini were tested on a Raspberry Pi 5 (CPU) and a Jetson Orin Nano (CPU/GPU). The Orin GPU used 1.9–7.8x less generation energy than the Pi 5. Q4_0 cut CPU generation energy by 10–70%. The 15 W mode was up to 7% more energy-efficient than MAX. Llama 3.2 1B on GPU costs about 0.040 cents per million input tokens. On-board sensors were calibrated against a Monsoon meter (MAPE under 2.5%). Absolute J/token values appear only in figures.
- Relation: the closest model-size match (0.5–1.5B) on a cheap-board peer, and a template for a Pi 5 / Orin Nano baseline against KR260 at matched quantization (Q8_0).
- Closeness: 5

**E12. Characterizing and Understanding Energy Footprint and Efficiency of Small Language Model on Edges.** M. R. Islam et al. IEEE MASS 2025. https://arxiv.org/abs/2511.11624
- Numbers: Llama 3.2, Phi-3 Mini, TinyLlama and Gemma 2 on Pi 5, Jetson Nano and Orin Nano. Measured externally with an Otii Ace Pro. Metrics are energy per inference, accuracy per watt and EDP. The Orin Nano GPU is the most efficient.
- Relation: a peer study with an external meter. Its EDP and accuracy-per-watt metrics fit our "bounded reliability" framing (energy per *correct* answer).
- Closeness: 4

**E13. An Evaluation of LLMs Inference on Popular Single-board Computers.** T. Nguyen, T. Nguyen. arXiv 2511.07425 (Oct 2025). https://arxiv.org/abs/2511.07425
- Numbers: 25 quantized LLMs on Pi 4, Pi 5 and Orange Pi 5 Pro. SBCs reliably support models up to 1.5B. Llamafile gives up to 4x the throughput of Ollama and uses 30–40% less power. Peak draw is about 8 W (Pi 4) and 10 W (Pi 5), per search snippet.
- Relation: shows that runtime choice alone moves energy by 30–40%, so a fair KR260 comparison must use the best CPU runtime (llama.cpp/llamafile), not Ollama.
- Closeness: 4

**E14. LLMPi: Optimizing LLMs for High-Throughput on Raspberry Pi.** M. Ardakani, J. Malekar, R. Zand. arXiv 2504.02118 (Apr 2025). https://arxiv.org/abs/2504.02118
- Numbers: Pi 5 with 8 GB, 2–8-bit and ternary (BitNet) quantization, reported as tokens/J, measured with an inline USB meter. I could not extract the numbers from the fetched text.
- Relation: one more cheap-board tokens/J baseline that uses an external meter.
- Closeness: 3

**E15. LLM Inference at the Edge: Mobile, NPU, and GPU Performance Efficiency Trade-offs Under Sustained Load.** P. Tummalapalli, S. Arayakandy, R. Pal, K. Kundan. arXiv 2603.23640 (v2 Jun 2026). https://arxiv.org/abs/2603.23640
- Numbers: Qwen2.5-1.5B 4-bit with a 258-token prompt. Pi 5 + Hailo-10H: 6.9 tok/s at under 2 W, about 270 mJ/token (per a search snippet), with near-zero variance. RTX 4050 laptop: 131.7 tok/s at 34.1 W (about 0.26 J/token, derived). iPhone 16 Pro loses about half its throughput within two iterations. Galaxy S24 Ultra hits an OS GPU-frequency floor that stops inference.
- Relation: very close in decode rate (6.9 tok/s vs our ~8). It shows that sustained-load variance and throttling are publishable axes, and our deterministic FPGA should show near-zero variance too. The Hailo NPU is the main efficiency competitor in the cheap-board class.
- Closeness: 5

**E16. Understanding Large Language Models in Your Pockets: Performance Study on COTS Mobile Devices.** J. Xiao et al. arXiv 2410.03613 (v5; earlier title "LLM Performance Benchmarking on Mobile Platforms"). https://arxiv.org/abs/2410.03613
- Numbers: Llama, Qwen and Gemma families with llama.cpp and MLC on phones, covering latency, memory, thermal and DVFS behaviour. I did not extract specific J/token values.
- Relation: a phone-side characterization baseline. Not to be confused with Li et al., "Large Language Models on Mobile Devices: Measurements, Analysis, and Insights", EdgeFM 2024 (a separate workshop paper whose content I did not retrieve).
- Closeness: 3

**E17. GreenBench: Benchmarking Energy Efficiency and Carbon Footprint of Open-Source LLM Inference on Apple Silicon.** R. Kannan et al. IEEE ICCUBEA 2026; arXiv 2608.28667. https://arxiv.org/abs/2608.28667
- Numbers: M4 Pro running Ollama, measured with `powermetrics`. Total system power is 8–12 W. Llama 3.2 3B runs at 175 tok/s and Qwen2.5 7B at 59 tok/s. Per-token energy was reported as about 4.4 mJ (3B) and 11.6 mJ (9B) per search snippet (package-level, probably excluding DRAM and board). Not verified against the full text.
- Relation: shows how software-sensor energy figures inflate efficiency claims. Package-only Apple numbers are 10–100x lower than wall-meter figures and must not be compared to board-level KR260 numbers.
- Closeness: 3

## D. FPGA LLM accelerators and fair-comparison critiques

**E18. Large Language Model Inference Acceleration: A Comprehensive Hardware Perspective.** J. Li, ..., Y. Wang, G. Dai (Tsinghua/SJTU). arXiv 2410.04466 (v4 Jun 2025). https://arxiv.org/abs/2410.04466
- Numbers: argues that relative speedup and energy claims across papers are unfair and calls for absolute tok/s and tok/J. Compiled ranges: GPUs 18–343 tok/s and 0.06–0.86 tok/J; FPGAs 3.6–450 tok/s and 0.15–6.3 tok/J. The ranges mix models, batch sizes and measurement methods.
- Relation: the key "critique of unfair comparisons" citation. Our paper should report absolute tok/s and tok/J at a stated boundary, with a matched-quantization CPU/GPU baseline.
- Closeness: 5

**E19. FlightLLM: Efficient Large Language Model Inference with a Complete Mapping Flow on FPGAs.** S. Zeng et al. FPGA 2024. https://arxiv.org/abs/2401.03868
- Numbers: on Alveo U280, 6.0x the energy efficiency and 1.8x the cost efficiency of a V100S (LLaMA2-7B, batch 1). Versal VHK158 gives 1.2x the throughput of an A100.
- Relation: the canonical datacenter-FPGA-vs-GPU energy claim. It uses HBM cards with board power figures, so it is not edge.
- Closeness: 3

**E20. DFX: A Low-latency Multi-FPGA Appliance for Accelerating Transformer-based Text Generation.** S. Hong et al. MICRO 2022. https://arxiv.org/abs/2209.10797
- Numbers: 4x U280 against 4x V100 on GPT-2 gives 5.58x speedup and 3.99x energy efficiency.
- Relation: early batch-1 text-generation FPGA claim. Its multi-FPGA GPT-2 setup is a different regime from ours.
- Closeness: 2

**E21. HLSTransform: Energy-Efficient Llama 2 Inference on FPGAs Via High Level Synthesis.** A. He, D. Key, et al. ICML 2024 Workshop. https://arxiv.org/abs/2405.00738
- Numbers: on VU9P, energy per token is 12.75x lower than CPU and 8.25x lower than GPU. Speed is 2.46x a CPU but only 0.53x an RTX 3090 (small Llama-2 on TinyStories).
- Relation: an HLS LLM decoder with an energy-per-token claim, the closest methodological sibling to our HLS decoder. It uses a cloud VU9P and a toy-scale model.
- Closeness: 4

**E22. LlamaF: An Efficient Llama2 Architecture Accelerator on Embedded FPGAs.** H. Xu et al. arXiv 2409.11424 (2024). https://arxiv.org/abs/2409.11424
- Numbers: TinyLlama-1.1B W8A8 on ZCU102 (Zynq US+). 14.3–15.8x speedup and 6.1x power efficiency over the board's own ARM PS. The TeLLMe v2 table lists its power at about 1.5 W. Absolute tok/s is low (not extracted).
- Relation: the nearest prior work by platform: same Zynq UltraScale+ family, about 1B model, INT8. Its baseline is only the on-chip ARM, a comparison our paper should avoid or supplement.
- Closeness: 5

**E23. TeLLMe / TeLLMe v2: Energy-Efficient Ternary LLM Prefill and Decode Accelerator on Edge FPGAs.** Y. Qiao et al. arXiv 2504.16266 (2025) and 2510.15926 (Oct 2025). https://arxiv.org/abs/2504.16266 , https://arxiv.org/abs/2510.15926
- Numbers: v1 on KV260 runs 1.58-bit BitNet within 7 W at up to 9.51 tok/s decode (1024 context), with prefill 0.55–1.15 s for 64–128 tokens. v2 runs BitNet 0.73B at 250 MHz on KV260 at about 4.8–5 W, 25 tok/s and about 143 tok/J (about 7 mJ/token).
- Relation: **the most direct competitor**: same K26 SOM family, similar size. Our differentiators must be the unmodified pretrained model (Q8_0 Qwen3, not ternary retraining), bit-exact determinism, and measured rather than estimated energy. Their power method (estimated or measured) needs checking.
- Closeness: 5

**E24. MEADOW: Memory-efficient Dataflow and Data Packing for Low Power Edge LLMs.** A. Moitra et al. MLSys 2025. https://arxiv.org/abs/2503.11663
- Numbers: OPT-125M/1.1B on ZCU102 at under 10 W. Decode latency is 1.5x lower and prefill 2.5x lower than a GEMM baseline.
- Relation: a Zynq-class edge LLM dataflow paper. Its power figure is a board envelope, not per-token energy.
- Closeness: 4

## E. Cold start, TTFT and prefix/prompt caching

**E25. ServerlessLLM: Low-Latency Serverless Inference for Large Language Models.** Y. Fu, L. Mai, et al. OSDI 2024. https://www.usenix.org/conference/osdi24/presentation/fu
- Numbers: 10–200x latency reduction from a loading-optimized checkpoint format, multi-tier (SSD/DRAM/GPU) loading and locality-aware scheduling.
- Relation: defines cold start as checkpoint loading. Our startup (~2.7 s, dominated by SHA-256 verification of 639 MB of weights) adds an integrity-verification cost no serverless paper accounts for. "Verified cold start" is a new axis.
- Closeness: 3

**E26. Efficient Memory Management for LLM Serving with PagedAttention (vLLM).** W. Kwon et al. SOSP 2023. https://arxiv.org/abs/2309.06180
- Numbers: block-based KV cache. vLLM's Automatic Prefix Caching (hash-of-block reuse) is documented in the software, not the paper.
- Relation: the standard prefix-caching implementation. It does not claim bit-identical outputs under caching, and our llama-server observation of 16 divergences fits this.
- Closeness: 3

**E27. SGLang: Efficient Execution of Structured Language Model Programs (RadixAttention).** L. Zheng et al. NeurIPS 2024. https://arxiv.org/abs/2312.07104
- Numbers: a radix-tree KV reuse across calls, with up to several-fold throughput gains on agent and few-shot workloads (per the paper).
- Relation: the agentic-workload prefix-reuse reference. Its multi-call "LM programs" are exactly our tool-call loop, but on GPUs with no determinism guarantee.
- Closeness: 4

**E28. Prompt Cache: Modular Attention Reuse for Low-Latency Inference.** I. Gim et al. MLSys 2024. https://arxiv.org/abs/2311.04934
- Numbers: TTFT improves 8x on GPU and 60x on CPU by reusing precomputed attention states of prompt modules.
- Relation: the large CPU gain shows that prefix reuse matters most on low-compute devices, which supports our 70.7% reduction in evaluated tokens on the KR260.
- Closeness: 4

**E29. Cost-Efficient Large Language Model Serving for Multi-turn Conversations with CachedAttention.** B. Gao et al. USENIX ATC 2024. https://www.usenix.org/conference/atc24/presentation/gao-bin-cost
- Numbers: TTFT down by up to 87%, end-to-end cost down by up to 70%, via hierarchical KV storage across turns.
- Relation: multi-turn KV reuse. Our JSON-state compaction is an alternative to KV reuse: it shrinks the history instead of caching it. The two should be compared head-to-head.
- Closeness: 4

**E30. Don't Break the Cache: An Evaluation of Prompt Caching for Long-Horizon Agentic Tasks.** E. Lumer et al. (PwC). arXiv 2601.06007 (Jan 2026). https://arxiv.org/abs/2601.06007
- Numbers: across OpenAI, Anthropic and Google, cost savings are 41–80% and TTFT gains 13–31%. Full-context caching can *increase* latency because dynamic tool results cause cache writes that are never reused. System-prompt-only caching is the most consistent.
- Relation: the closest agentic-cache evaluation. It supports our design of reusing a stable prefix and compacting dynamic state into JSON. It measures cost and latency, not energy.
- Closeness: 4

## F. Energy of agentic workloads

**E31. Where Does the Energy Go? Profiling LLM Agent Inference on Blackwell GPUs.** Q. Luo, K. Li, Z. Wang, Y. Chen. arXiv 2609.29707 (Aug 2026). https://arxiv.org/abs/2609.29707
- Numbers: GPU-only telemetry misses 41–45% of system energy. A sequential agent uses 63x more system energy per output token than saturated serving. Thinking mode produces 21–75% more tokens at per-token energy within 1%. Batching 1 to 16 requests per second improves efficiency 3.2x.
- Relation: strong support for (a) full-system measurement boundaries and (b) the claim that batch-1 sequential agents are the energy-worst case on GPUs. That is exactly the regime where a dedicated low-power board could win per task.
- Closeness: 4

**E32. Energy per Successful Goal: Goal-Level Energy Accounting for Agentic AI Systems.** D. Panigrahy, A. Tyagi, S. Abkin, D. K. Houngninou, R. Mahapatra. arXiv 2605.22883 (v2 Oct 2026). https://arxiv.org/abs/2605.22883
- Numbers: the Orchestration Overhead Index (agentic vs linear J per successful goal) ranges 0.35–11.07x CPU-only and 0.4–26.48x with GPU energy. GPU is 83.8% of agentic energy in local inference.
- Relation: provides the metric we should adopt: J per *successful* goal, which pairs naturally with calibrated abstention and verified execution.
- Closeness: 4

**E33. Measuring the Energy Cost of Completing Tasks with Quantized Language-Model Agents.** S. Abkin et al. arXiv 2610.32417 (Oct 2026). https://arxiv.org/abs/2610.32417
- Numbers: 29 agent tasks, llama.cpp on A100, 4-bit vs 8-bit. 4-bit saves energy per token but can use up to 3.5x more energy per completed task because it needs extra tokens.
- Relation: directly supports keeping Q8_0 rather than lower bit-widths, and supports token-reduction (JSON state, −89.5% input tokens) as a first-order energy lever.
- Closeness: 4

**E34. Where Should Agents Live? Energy-Memory Characterization of Agentic AI for the Edge-Cloud Continuum.** C. Fortuna, V. Hanžel, T. Strnad, B. Bertalanič. arXiv 2609.18283 (Sep 2026). https://arxiv.org/abs/2609.18283
- Numbers: 16 open-weight models and 8 orchestration topologies on A100/H100. Inter-agent text transport is 0.25% of workflow energy. Gives a closed-form two-rate (prefill/decode) energy model. Edge placement is analytical, not measured on edge hardware.
- Relation: explicitly leaves edge agent energy unmeasured, an opening for a measured KR260 agent-loop energy study.
- Closeness: 4

---

## (1) What is saturated

- **GPU/datacenter energy-per-token benchmarking** (E01, E07–E09, ML.ENERGY leaderboard, MLPerf Power LLM results). New GPU J/token tables add little unless they bring a new boundary or workload.
- **"LLM on phone / Pi / Jetson" characterization with llama.cpp or MLC** (E10–E17). Many 2024–2026 papers already show memory-bound decode, quantization trade-offs, Orin beating Pi, and phone throttling. Another SBC table would not be novel.
- **Relative "FPGA is N x more energy-efficient than GPU" claims** (E19–E21). These are widely made, and E18 already criticizes them. A bare ratio against a V100 or the on-board ARM will not be accepted as a contribution.
- **Prefix/KV caching for throughput and TTFT on GPUs** (E26–E29, plus LMCache and others). The mechanisms are mature. Speedups alone are not novel.
- **Cost (USD) of cloud prompt caching for agents** (E30). Covered.

## (2) Gaps / open niches tied to our assets

1. **Calibrated, rail-level energy on an FPGA LLM.** Edge-FPGA LLM papers (E22–E24) report board envelopes ("<10 W", "~5 W") or vendor power estimates. None, as far as I found, calibrates onboard telemetry against an external meter the way E06 and E11 do for Jetson and Pi. A KR260 study using SOM_5V0 rail telemetry validated against an external DC meter (sampling coverage per E05, idle subtraction per E10, three boundaries: SOM, carrier board, wall) would be the first measured J/token for a pretrained, unmodified 0.6B LLM on Zynq US+ fabric.
2. **Energy of exact prefix reuse, and determinism as a measurement property.** Caching papers measure latency or cost (E26–E30), never energy. None test output identity under caching; our CPU baseline produced 16 formatting differences. Two measurements are open: J saved per reused prefix token, and "energy savings with a proof of bit-identical outputs" (328/328 matches). Determinism also makes energy measurements repeatable: identical token sequences mean variance comes from hardware only, which E15 shows is not true on phones.
3. **Energy per successful task with token compaction.** E32 and E33 establish J per successful goal and show token count dominates task energy. The JSON-state compaction (−89.5% input tokens) can be evaluated directly as joules per completed maintenance/tool task, alongside prefix reuse, on an edge device. E34 explicitly lacks measured edge agent energy.
4. **Verified cold start.** Serverless cold-start work (E25) and MELT model loading (E10, ~2.4 s) do not include integrity verification. Our cold tool call (~6.9 s, with SHA-256 over 639 MB) supports a "time and joules to first *verified* token" metric, separating integrity cost from inference cost.
5. **Fair comparison protocol against the cheap-board class.** At about 8 tok/s we are in the regime of Pi 5 + Hailo-10H (6.9 tok/s, <2 W, E15) and TeLLMe on KV260 (9.5–25 tok/s, ~5–7 W, E23). A fair protocol in the spirit of E18 would compare the same model (Qwen3-0.6B Q8_0) on llama.cpp/llamafile on Pi 5, Orin Nano and the KR260's own A53, at matched boundaries. That is a contribution even if the KR260 does not win on raw J/token, especially when sustained-load variance and determinism are added.
6. **Abstention-aware energy.** No energy benchmark accounts for calibrated abstention or cascades. Energy per correct answer at coverage c (v1 cascade: 97.4% accuracy at 50% coverage) is unexplored.

## (3) Reference table: reported edge J/token and tok/s (~0.5–3B models)

Values come from papers' text. "Derived" means computed as W ÷ tok/s by me. Boundaries differ (meter at wall/DC vs onboard sensor vs package), so values within a factor of about 2 should not be ranked.

| Platform | Model / quant | Decode tok/s | Power (W) | J/token | Boundary / method | Source |
|---|---|---|---|---|---|---|
| KV260 (K26) FPGA, TeLLMe v2 | BitNet 0.73B, 1.58-bit | 25 | ~4.8–5 | ~0.007 (143 tok/J) | Authors' board figure (method unverified) | E23 |
| KV260 FPGA, TeLLMe v1 | BitNet, 1.58-bit | up to 9.51 | ≤7 | ≤0.74 (derived upper bound) | Budget, not measured per token | E23 |
| Pi 5 + Hailo-10H NPU | Qwen2.5-1.5B 4-bit | 6.9 | <2 | ~0.27 | External/instrumented | E15 |
| Laptop RTX 4050 | Qwen2.5-1.5B 4-bit | 131.7 | 34.1 | ~0.26 (derived) | Device power | E15 |
| iPhone 14 Pro (LLMFarm) | Zephyr-3B 4-bit | n/a | ~13.8 sustained | ~0.58 | Monsoon, battery bypass | E10 |
| iPhone 14 Pro / Galaxy S23 (MLC) | Zephyr-3B 4-bit | n/a | <8.5–13.8 | ~0.72–0.76 | Monsoon | E10 |
| Galaxy S23 CPU (llama.cpp) | TinyLlama-1.1B 4-bit | ~13.6 | n/r | n/r | n/a | E10 |
| Apple M4 Pro (Ollama) | Llama 3.2 3B | 175 | 8–12 system | ~0.0044 package (snippet) / ~0.05–0.07 system (derived) | powermetrics | E17 |
| Raspberry Pi 5 CPU | Qwen2 0.5B–Llama 3.2 3B Q4 | >5.3 for ≤3B | ~≤10 peak | figures only; Orin GPU 1.9–7.8x lower | PMIC calibrated to Monsoon | E11, E13 |
| Jetson Orin Nano GPU (15 W) | Qwen2 0.5B–Phi-3.5 Q4 | >5.3 all models | ≤15 mode | figures only | sysfs, calibrated | E11, E12 |
| ZCU102 (Zynq US+) LlamaF | TinyLlama-1.1B W8A8 | low (not extracted) | ~1.5 (per E23 table) | n/r | n/a | E22 |
| ZCU102 MEADOW | OPT-1.1B | n/r | <10 | n/r | Board envelope | E24 |
| Cross-paper FPGA range | mixed | 3.6–450 | n/a | 0.16–6.7 (0.15–6.3 tok/J) | Mixed | E18 |
| Cross-paper GPU range | mixed | 18–343 | n/a | 1.2–17 (0.06–0.86 tok/J) | Mixed | E18 |
| **KR260 (ours), hypothetical** | Qwen3-0.6B Q8_0 | ~8 | 5–8 (SOM) / 8–15 (board) | **~0.6–1.0 SOM / ~1.0–1.9 board** | To be measured | none yet |

**Positioning.** At 8 tok/s and plausible K26 power, the KR260 would sit around 0.6–1.9 J/token. That is the same order as phones on 3B models (0.6–0.8 J/token), worse than Pi 5 + Hailo-10H (~0.27) and far worse than TeLLMe v2's ternary 0.73B (~0.007, an author figure). It will not win a raw J/token contest. Its credible niche is: an unmodified pretrained INT8 model, bit-exact determinism (including under prefix reuse), calibrated rail-level measurement, verified cold start, and energy per *successful, verified* task with token compaction (gaps 2–4).

### Notes on verification
- Not confirmed this session: the SC'24 venue for E05, the HPEC label for E09, and the ISCA 2020 venue for E03 (from my prior knowledge).
- E17's mJ/token values and E15's 270 mJ come from search snippets, not the fetched abstract.
- TeLLMe v2's power was given as both 4.8 W and 5 W in different sources.
- Absolute J/token for E11, E12, E14 and E16 appears only in figures and was not extracted.
