# Value review A: where an FPGA SoC wins, and where it does not (2026-11-08)

Agent A, landscape review. All numbers below come from web searches or page fetches done in this session. Labels:

- **[V]**: read on a fetched primary or near-primary page.
- **[S]**: taken from a search-result summary only.
- **[D]**: derived by me from other cited numbers.
- **[U]**: unverified or from memory. Do not cite these in a paper without checking.

Model sizes differ between rows, and so do boundaries (wall, board, package or none) and quantizations. Do not rank two rows that are within about 2x of each other. A strong regularity holds at batch 1: **decode tok/s ≈ effective DRAM bandwidth ÷ bytes streamed per token.** Bandwidth, not TOPS, decides who wins on decode.

---

## Part 1: Small-LLM competitive table (0.5–2B, batch 1)

### 1a. Same model as ours (Qwen3-0.6B), or as close as available

| Platform | Model / quant | Decode tok/s | Prefill | Power / J per token | Price | DRAM BW | Source |
|---|---|---|---|---|---|---|---|
| **KR260 fabric (our RC1)** | Qwen3-0.6B Q8_0 | **~6** | **~20 tok/s** (1,454 tok in 76.5 s cold) | not measured; board ~10–16 W plausible → **~1.7–2.7 J/tok** [D/U] | $349 MSRP [S] | 19.2 GB/s peak, **~4 GB/s used** (one HP port) | repo context; price https://www.amd.com/en/products/system-on-modules/kria/k26/kr260-robotics-starter-kit.html ; KV260 15–16 W wall under load https://hothardware.com/reviews/xilinx-kria-kv260-vision-ai-starter-kit-review?page=2 [S]; K26 7.5 W typ / 15 W max https://www.cnx-software.com/2021/04/28/xilinx-kria-k26-som-vision-ai-devkit-zynq-ultrascale-xck26-fpga-mpsoc/ [S] |
| KR260 **own 4x A53** (llama.cpp) | Qwen-class ~0.6B Q8 | 5.78 | first word ~5 s on short prompts | – | same board | same DDR | repo baseline (Oct 2026) |
| Jetson Orin Nano 8GB (TensorRT Edge-LLM) | Qwen3-0.6B INT4 AWQ | **77.0** (61-tok prompt); 61.0 at 2,048 KV | 61 tok in 30.7 ms; **2,048 tok in 445 ms (≈4,600 tok/s)** [D] | 7–25 W modes → **~0.1–0.3 J/tok** [D/U] | $249 (Super dev kit) https://www.dfrobot.com/product-2900.html [S] | 102 GB/s (Super) https://cnx-software.com/2024/12/18/249-nvidia-jetson-orin-nano-super-developer-kit-targets-generative-ai-applications-at-the-edge/ [S] | https://nvidia.github.io/TensorRT-Edge-LLM/latest/user_guide/performance/performance-benchmarks.html [V]. The page says "Orin Nano 8GB"; whether it ran in Super mode is unstated. |
| Jetson Orin NX 16GB | Qwen3-0.6B INT4 | 124.9 | 2,048 tok in 269 ms | – | – | – | same TRT Edge-LLM page [V] |
| Jetson AGX Orin 64GB | Qwen3-0.6B INT4 | 200.5 | 2,048 tok in 118 ms | – | – | 204.8 GB/s [U] | same [V] |
| Jetson AGX Thor | Qwen3-0.6B INT4 / NVFP4 | 319.7 / 306.4 | 2,048 tok in 17.9 ms (NVFP4) | up to ~130 W [U] | ~$3,499 dev kit [U] | 273 GB/s [U] | same [V] |
| Raspberry Pi 5 CPU (llama.cpp, 4 threads) | Qwen3-0.6B Q8 | **~21.5** (informal blog) | not reported | Pi 5 peak ~10 W → **~0.4–0.5 J/tok** [D] | ~$80 (8 GB) [U]; prices rose in 2025–26 [U] | ~17 GB/s LPDDR4X [U] | https://hashnode-hub.vercel.app/posts/682432507da5ff91f5f0985a [S]; Pi 5 ~10 W peak, per lit_E summary of an SBC study |

**The decode verdict on our own model:** a $249 Orin Nano decodes Qwen3-0.6B about **13x faster** than RC1 (INT4 vs Q8, so roughly 6–7x at matched bytes) and prefills about **230x faster**. An informal Pi 5 llama.cpp run at Q8, with DRAM bandwidth similar to the K26's, decodes about **3.5x faster**. The KR260's own A53 cores are at parity with the fabric decoder.

### 1b. 1–1.7B models (Llama 3.2 1B, Qwen2.5 1.5B, Qwen3 1.7B)

| Platform | Model / quant | Decode tok/s | Prefill / TTFT | Power | Price | BW | Source |
|---|---|---|---|---|---|---|---|
| Jetson Orin Nano 8GB | Qwen3-1.7B INT4 | 36.5 | 2,048 tok in 1.02 s | – | $249 | 102 GB/s | TRT Edge-LLM page [V] |
| Jetson Orin Nano Super | Qwen2.5-1.5B Q4_K_M (llama.cpp) | 38.4; 2.29 tok/s/W (→ ~16.8 W, ~0.44 J/tok) [D] | pp512 not extracted | – | – | – | https://aicoding.csdn.net/6a686cfd10ee7a33f2934eb5.html [S, single blog] |
| Jetson AGX Thor | Qwen3-1.7B NVFP4 | 153.6 (vanilla); 312 with EAGLE3 speculation | 2,048 tok in 27.7 ms | – | – | – | TRT Edge-LLM page [V]; EAGLE figure [S] |
| Pi 5 CPU (Ollama) | Qwen2.5-1.5B instruct | 11.73 | prompt eval 21.4 tok/s | CM5 10.2–10.6 W (DeepSeek-R1 1.5B) | – | – | https://www.cnx-software.com/2026/01/20/raspberry-pi-ai-hat-2-review-a-40-tops-ai-accelerator-tested-with-computer-vision-llm-and-vlm-workloads/ [V] |
| **Pi 5 + Hailo-10H (AI HAT+ 2)** | Qwen2.5-1.5B instruct | **6.74** (CPU alone was faster) | not measurable with the tools | Pi 5 + HAT 7.2–7.6 W → ~1.1 J/tok [D] | $130 HAT [S] | 8 GB LPDDR4X-4267 on the HAT [S] | same CNX review [V]. Vendor/blog claims of 20–35 tok/s (https://raspberry.tips/en/?p=9674) are **not** reproduced. A paper figure of 6.9 tok/s at <2 W NPU-only is in lit_E. |
| Pi 5 + Hailo-10H | Qwen2-1.5B (official build) | 8.3–9.45; TTFT ~0.29–0.41 s | – | – | – | – | https://www.codesota.com/embedded-ai/hailo-10h-llms [S]; https://github.com/marco-tinkerer/hailo-llm-server [S] |
| RK3588 NPU (RKLLM) | Qwen2.5-1.5B W8A8 | 16.3 | TTFT 412 ms (128-tok prompt) | ~5–10 W board [U] | ~$100–180 boards [U] | LPDDR4X/5, ~30 GB/s [U] | https://sensecraft.seeed.cc/ai-lab/en/tutorials/rk/benchmark/llm [S]; 15.8 tok/s on ROCK 5C https://huggingface.co/oliver0804/MiniCPM5-2B-RK3588-rkllm-w8a8 [S] |
| RK3588 CPU (llama.cpp) | Qwen2.5-1.5B Q8_0 / Q4_K_M | 15.3 / 22.6 | – | – | – | – | https://turingpi.com/llm-inference-benchmarks-rk3588-gguf-quantization/ [S] |
| Snapdragon 8 Elite (phone NPU, Genie) | Llama 3.2 1B w4a16 | 67.2 | TTFT 0.031 s (≤128 tok) to 1.0 s (4,096 tok) → ~4,000 tok/s prefill [D] | phones ~0.6–0.8 J/tok on 3B (lit_E) | phone | ~77 GB/s LPDDR5X [U] | https://huggingface.co/qualcomm/Llama-v3.2-1B-Instruct [V] |
| Qualcomm IoT (Dragonwing IQ-9075, ex-QCS9075) | Llama 3.2 1B w4a16 | 41.6 | TTFT 0.053–1.71 s | – | industrial module | – | same [V] |
| Qualcomm automotive SA8295P | Llama 3.2 1B w4 | 13.1 | TTFT 0.16–5.1 s | – | – | – | same [V] |
| Intel Core Ultra 7 356H NPU (OpenVINO GenAI) | Llama 3.2 1B INT4 | 65.3 | TTFT 275 ms | laptop SoC | mini PC ~$600+ [U] | – | https://www.linuxlinks.com/minisforum-m2-panther-lake-mini-pc-npu/ [S] |
| Intel 15-TOPS NPU (EQi 304) | Llama 3.2 1B INT4 | 34.4 | TTFT 719 ms | – | – | – | https://www.linuxlinks.com/beelink-eqi-304-mini-pc-npu-llama/ [S] |
| AMD Ryzen AI 7 350 NPU (FastFlowLM) | Llama 3.2 1B | 62.7 at 1k ctx | **1,442 tok/s at 1k; 1,766 at 2k** | – | laptop | – | https://fastflow-page.pages.dev/docs/benchmarks/llama3_results [S] |
| AMD Ryzen AI 9 HX 375 (LM Studio, CPU/iGPU) | Llama 3.2 1B | 50.7 | – | – | – | – | https://www.tomshardware.com/pc-components/cpus/ryzen-ai-300-takes-big-wins-over-intel-in-llm-ai-performance-up-to-27-percent-faster-token-generation-than-lunar-lake-in-lm-studio [S] |
| Apple M4 (base, llama.cpp Metal) | **Llama 2 7B** Q8_0 | 13.5 (pp512 224) | – | – | Mac mini ~$599 [U] | 120 GB/s | https://github.com/ggml-org/llama.cpp/discussions/4167 [V]. Scaled to 0.6B Q8 by bytes, this is roughly 140+ tok/s [D] |
| Apple M1 (base) | Llama 2 7B Q8_0 | 7.9 | pp512 108–117 | – | – | 68 GB/s | same [V] |
| Apple M4 Max | Qwen3-0.6B 4-bit (MetalRT, vendor) | up to 658 | – | – | – | 546 GB/s | https://hn.jakechampion.name/reader/https://www.runanywhere.ai/blog/metalrt-fastest-llm-decode-engine-apple-silicon [S, vendor] |
| MCU (ESP32-S3, llama2.c ports) | 0.26M–29M-param TinyStories models | 12–30 | – | <1 W [U] | <$10 | PSRAM-limited | https://github.com/doryiii/esp32-llm [S]; https://insiderllm.com/guides/llm-on-microcontroller-esp32-s3/ [S]. **No MCU runs a 0.5B model usefully.** |

Reference FPGA peers on the same K26 silicon (from lit_A and lit_E; not re-verified here):

- TeLLMe v2, BitNet 0.73B ternary: 25 tok/s at ~5 W.
- TeLLMe v1: 9.5 tok/s at 7 W.
- Hummingbird, Llama3-8B: 4.8 tok/s on KV260 at 93–94% bandwidth utilization.

### 1c. Where RC1 stands, and the bandwidth ceiling

Per-token bytes for Qwen3-0.6B Q8_0: about 0.47 GB of layer weights plus about 0.165 GB of LM head (tied 151,936 × 1,024 Q8), so about 0.63 GB/token. This matches the 639 MB resident image.

| Scenario | Bytes/token | Peak at 19.2 GB/s | Realistic (70–85% of peak, shared with ARM) |
|---|---|---|---|
| Today (one HP port, ~3.5–4 GB/s effective) | 0.63 GB | – | **~6 tok/s (measured)** |
| All DDR4 bandwidth, Q8, full LM head | 0.63 GB | **~30 tok/s** [D] | ~21–26 tok/s [D] |
| All bandwidth, Q8, grammar-restricted LM head (most rows skipped) | ~0.47 GB | ~41 tok/s [D] | ~29–35 tok/s [D] |
| All bandwidth, Q4-class (~4.5 bits/weight) | ~0.33 GB | ~58 tok/s [D] | ~40–50 tok/s [D] |
| Weights fully on chip (URAM+BRAM ≈ 64×288 Kb + 144×36 Kb ≈ 2.9 MB) | – | only models of a few million parameters fit | not an option for 0.6B |

The 19.2 GB/s figure assumes the K26's 64-bit DDR4-2400 PS interface [U]. Lit_A cites ~19.2 GB/s.

**Brutal reading:**

1. Even a perfect 30 tok/s KR260 at Q8 would only match a Pi 5 CPU (~21 tok/s Q8 [S]) and an RK3588 NPU (~16 tok/s at 1.5B). It would stay 2.5x behind a $249 Orin Nano (77 tok/s at INT4) and far behind phones and laptop NPUs (35–67 tok/s on Llama 3.2 1B at 2.5x our parameter count).
2. The K26 simply has 5x less DRAM bandwidth than an Orin Nano. No amount of RTL changes that.
3. **Prefill is the bigger gap.** RC1 does about 20 tok/s. Orin Nano does about 4,600 tok/s (2,048 tokens in 445 ms) [V]. Laptop and phone NPUs do about 1,400–4,000 tok/s. The K26 has 1,248 DSPs at a few hundred MHz, about 0.3–0.6 dense INT8 TOPS [D/U], against tens of TOPS on NPUs and GPUs. Prefill is compute-bound, so the gap is structural: 2 to 3 orders of magnitude.
4. Energy: unmeasured. At a plausible 10–15 W board power and 6 tok/s, RC1 is ~2 J/token, roughly **10x worse** than Orin Nano (~0.2 J/tok) and 4x worse than a Pi 5 CPU. Even at the 30 tok/s ceiling it would be around 0.4 J/tok: Pi 5 territory, not better.

**Conclusion for Part 1:** as an LLM throughput, latency or efficiency engine, the KR260 does **not** beat anything in its price class except the Hailo-10H's disappointing measured decode, and only on decode. Claims along the lines of "faster, cheaper or greener small-LLM inference on Kria" are a vanity project. What the fabric uniquely offers on this workload is control, not speed:

- bit-exact deterministic arithmetic, including under prefix reuse;
- no OS or driver in the arithmetic path;
- inspectable, certifiable datapaths;
- co-location with I/O and real-time logic.

---

## Part 2: Where FPGAs and adaptive SoCs genuinely win in deployed practice

| Domain | Deployed evidence | Quantitative advantage | Vs GPU/NPU/MCU | Sources |
|---|---|---|---|---|
| **Deterministic µs/ns in-line inference (physics triggers)** | CMS/ATLAS Level-1 triggers. hls4ml is used for NN/BDT inference at a 40 MHz collision rate. | Phase-2 L1 total budget 12.5 µs. Small hls4ml models run at **~50–200 ns** (io_parallel) and **60 ns at II=1** for CMS b-tagging. BDTs run under 100 ns. | GPUs reach µs-scale latency only with large batches; at batch 1 on streaming sensor data a GPU behaved like a CPU, so the authors chose an FPGA SoC. A cell-sorting NN on FPGA took 14.5 µs, beating the GPU's best at batch 1. | https://indico.cern.ch/event/1156222/contributions/5076141/attachments/2522824/4338292/DH_CMS_L1.pdf [S]; https://arxiv.org/pdf/2311.05716 [S]; https://arxiv.org/pdf/2503.12622 [S] |
| **HFT / ultra-low-latency trading** | AMD Alveo UL3524 (Virtex US+); Exegy nxFramework. | <3 ns transceiver latency (vendor). STAC-T0 minimum tick-to-trade **13.9 ns**, 49% below the prior 24.2 ns record. | No GPU or NPU competes: PCIe plus kernel launch alone is µs. CPUs with kernel-bypass NICs sit in the ~µs range [U]. | https://www.amd.com/en/blogs/2024/amd-sets-stac-benchmark-world-record-for-fastest-e.html [S]; https://stacresearch.com/node/48577 [S] |
| **Line-rate packet processing / SmartNICs** | Azure AccelNet: FPGA SmartNICs on all new Azure servers since 2015, >1M hosts. | <15 µs VM-to-VM TCP, 32 Gbps, with CPU cores freed. | CPU software stacks add latency and variability and burn cores. ASIC NICs are now competitive for fixed functions [U]. | https://www.microsoft.com/en-us/research/publication/azure-accelerated-networking-smartnics-public-cloud/ [S] |
| **In-network ML** | Taurus (Stanford): per-packet ML at line rate, with an FPGA prototype. | ~1 Gpkt/s line rate. Adds up to 221 ns latency and 3.8% area. Detects ~100x more anomaly events than control-plane ML. | Control-plane or server ML is orders of magnitude slower. A GPU cannot sit in the packet path. | https://arxiv.org/abs/2002.08987 [S]; https://blog.apnic.net/2022/10/12/taurus-a-data-plane-architecture-for-per-packet-machine-learning/ [S] |
| **TSN / industrial Ethernet** | KR260 ships an AMD 100M/1G TSN subsystem in PL (802.1Qbv/AS) with a ROS 2-over-TSN reference app. Fieldbus ASICs/FPGAs run EtherCAT, PROFINET IRT and Sercos. | 802.1AS synchronization **<20 ns** (vendor). EtherCAT/Sercos/Powerlink jitter **<100 ns**. PROFINET IRT cycles down to **31.25 µs**. | Jetson and NPU SoCs offer standard MACs with software TSN at best. MCUs with integrated TSN MACs exist (TI Sitara, NXP i.MX RT [U]) and are cheaper for simple nodes. | https://xilinx.github.io/kria-apps-docs/kr260/build/html/docs/ros2_multinode_communication_via_tsn/src/hw_arch_platform.html [S]; https://edge-ai-vision.com/wp-content/uploads/2022/05/E3T08_Khona_AMD_2022.pdf [S]; https://copperhilltech.com/blog/industrial-ethernet-guide-technology-and-performance-features/ [S] |
| **Motor control / power electronics** | Kria K24 SOM and KD240 drives kit: FOC with ADC, PWM and encoder in PL (Vitis Motor Control Library). | Vendor: ~120 ns control-loop latency, about half that of a TI AM64x in a full loop. Advantage grows to up to 7x with more axes, because loops run in parallel instead of time-multiplexed. | MCUs (C2000, STM32G4) dominate single-axis drives on cost [U]. The FPGA wins at multi-axis scaling, very high PWM rates (GaN/SiC) and sub-µs protection. | https://community.element14.com/learn/learning-center/the-tech-connection/b/blog/posts/achieving-deterministic-latency-with-the-amd-kria-k24-som [S]; https://xilinx.github.io/kria-apps-docs/kd240/foc-motor-ctrl/0_5/build/html/docs/introduction.html [S] |
| **High-rate sensor / DSP front ends: RF, radar** | Zynq US+ RFSoC used in phased-array radar and 5G mMIMO radios (RFSoC DFE). | On-chip 14-bit ADCs at 5 GS/s and DACs at 10 GS/s, 6 GHz analog bandwidth. Up to 50% power and footprint reduction by removing JESD204 converters (vendor, early claim). | No GPU or NPU has GS/s converters or deterministic sample-synchronous datapaths. GPUs only appear downstream on decimated data. | https://www.amd.com/en/products/adaptive-socs-and-fpgas/soc/zynq-ultrascale-plus-rfsoc.html [S]; https://www.eenewseurope.com/en/zynq-ultrascale-rfsocs-offer-full-sub-6ghz-spectrum-support/ [S] |
| **Ultrasound beamforming** (analogous to acoustic emission and partial-discharge front ends) | FPGA beamformers are standard in research and commercial systems. | 128-channel DAS at **2.17 GS/s beamformed**, 11 kHz PRF. 32×32 volumetric beamforming on one KU040 at 50 vol/s. | GPU beamforming exists in research but needs the FPGA to aggregate channels first. | https://dspace.lib.ntua.gr/xmlui/handle/123456789/58835?show=full [S]; https://si2.epfl.ch/demichel/publications/archive/2016/FPL2016_PhDForum.pdf [S]. I found no PD/AE-specific FPGA source this session [U]. |
| **Machine vision pipelines** | KV260 vision kit. FPGA frame grabbers and smart cameras (industry-standard, [U]). | Vendor: ROS perception pipeline 3.5x faster than Isaac ROS GEMs on Jetson Nano (an old Jetson). | For CNN inference alone, Jetson and Hailo now usually win on TOPS/$ [U]. The FPGA wins on sensor interfaces (MIPI, CoaXPress, multi-camera sync) and on low, fixed-latency pre-processing. | https://edge-ai-vision.com/wp-content/uploads/2022/05/E3T08_Khona_AMD_2022.pdf [S, vendor] |
| **Functional safety** | Zynq US+ MPSoC assessed by Exida: SIL 3 capable, HFT=1. Automotive XA parts: ISO 26262 up to ASIL C. Vivado flow TÜV SÜD certified to IEC 61508-3. R5 cores run in lockstep. Versal AI Edge Gen 2: ASIL D / SIL 3 from PS through NoC to DDR (vendor), with Subaru EyeSight as a design win. | Lockstep R5, isolated power domains and certified tools cut the safety-case cost. | Jetson Orin/Thor have safety packages only for specific automotive variants [U]. Consumer NPUs (Hailo, RK3588, Pi) have no SIL/ASIL story. | https://www.eenewseurope.com/en/xilinx-zynq-ultrascale-products-assessed-to-sil-3/ [S]; https://iwavesystems.com/?p=8556 [S]; https://www.amd.com/content/dam/amd/en/documents/products/adaptive-socs-and-fpgas/versal/versal-ai-edge-gen2-product-brief.pdf [S]; https://www.yolegroup.com/?p=3076485 [S] |
| **Long lifecycle** | AMD: 7-series supported to 2040; **UltraScale+ (incl. Zynq US+/K26 silicon) to 2045**; Versal to 2045+. HBM parts are excluded. | 15–20+ years of supply. | Jetson modules typically have ~7–10-year lifecycles [U]. Consumer SBCs and NPUs are shorter [U]. | https://www.amd.com/en/blogs/2024/amd-supports-new-long-lifecycle-fpga-designs-thro.html [S] |
| **Radiation tolerance / space** | XQR Versal AI Edge XQRVE2302 is Class B flight-qualified. It is in-flight reprogrammable, uses <30% of the board area of XQRVC1902 and ~75% less power. | Rad-tolerant from LEO to GEO and beyond (vendor). | No COTS GPU or NPU is rad-qualified at this class. | https://themachinemaker.com/news/now-available-flight-qualified-amd-xqr-versal-soc-brings-ai-acceleration-to-space/ [S]; https://www.amd.com/en/products/adaptive-socs-and-fpgas/versal/space-grade.html [S] |
| **Determinism vs GPU jitter (evidence)** | A Jetson AGX Orin + ZCU102 hybrid uses an FPGA fallback model. | FPGA has "near-zero jitter". **Up to 20x fewer deadline misses.** Jetson DVFS transitions take 1/5/8 ms (CPU/GPU/EMC). Long tails on all Jetson devices in AV DNN timing studies. | – | https://tanrui.github.io/pub/TMC-FPGA.pdf [S]; https://www.emergentmind.com/papers/2606.16106 [S]; https://arxiv.org/pdf/2209.05487 [S] |
| Market context | FPGA market ~$11.4–13.9 B in 2025 (estimates vary). Defence/aerospace, industrial, automotive and telecom are the named end markets. | – | – | https://www.fortunebusinessinsights.com/field-programmable-gate-array-market-104798 [S]; https://www.knowledge-sourcing.com/report/field-programmable-gate-array-fpga-market [S] |

**Pattern:** every deployed FPGA win is one of three kinds:

- **(a)** sits in a data path at line or sample rate, where batching is impossible and latency is ns to µs;
- **(b)** talks to non-standard or high-rate I/O directly;
- **(c)** has to be certified, kept in supply for 15–20 years, or survive radiation.

None of the deployed wins is "big-model throughput per dollar". Where FPGAs did run big ML in production (Microsoft Brainwave, Catapult), the reason was low-latency serving at datacenter scale, and Microsoft has since moved much of that ML work to ASICs and GPUs [U].

---

## Part 3: Synthesis. FPGA sweet-spot properties versus transformer and LLM workloads

| # | FPGA sweet-spot property | Do LLM/transformer workloads benefit? | Verdict |
|---|---|---|---|
| 1 | **ns–µs deterministic latency at batch 1, streaming** | Generative LLM: **no**. Token latency is 10–170 ms and bandwidth-bound, so ns determinism buys nothing. **Tiny** encoders and classifiers (our v1, at 13 µs compute and ~75 µs wire-to-wire; small MiniLM-class heads) placed in a control or packet path: **yes**. | **RIGHT tool:** tiny in-line classifier, anomaly scorer or gate in an I/O path (v1 class). **VANITY:** chasing LLM tok/s. |
| 2 | **Bit-exact, reproducible arithmetic with no OS or driver in the datapath** | Yes, and this is real. A CPU llama-server was not bit-exact under caching. A NeurIPS 2026 paper (DetLLM) needs integer-only kernels to get bit-identical Qwen3-0.6B on GPUs. Auditability and regulator replay matter for safety and industrial logs. Caveat: integer-only GPU kernels now reach this too (106 tok/s on A100), so determinism alone is **not exclusive** to FPGAs. | **RIGHT, if framed as** "certifiable, replayable inference whose datapath is inspected and formally verified", not "the only deterministic LLM". |
| 3 | **Direct, high-rate, custom I/O** (ADCs, encoders, TSN, fieldbus, MIPI) | A transformer's *input* can come from a sensor stream: vibration, AE/PD bursts, motor current. Front-end DSP, feature extraction and a small encoder in PL is plausible. The LLM itself does not benefit. | **RIGHT:** sensor-to-feature-to-small-model in PL, with typed outputs to an LLM elsewhere. **VANITY:** an LLM in PL "because the I/O is there". |
| 4 | **Hard real-time co-processing (R5 lockstep + PL) beside Linux** | The LLM tolerates jitter. The *guard* around it does not: action validation, interlocks, deadline/epoch/quarantine, typed-output enforcement on the R5/PL (our v2 assurance work). | **RIGHT:** a "safety shell" that gates what an LLM-proposed action may do, at µs latency and certifiable. LLM generation itself does not need it. |
| 5 | **Functional-safety certifiability (SIL 3 / ASIL C–D parts, certified tools)** | No small-LLM edge device has a safety case. The PL/R5 path can host the certifiable *non-LLM* parts. Certifying the LLM is unrealistic. | **RIGHT** for monitor and arbiter logic. **VANITY:** claiming a certifiable LLM. |
| 6 | **15–20-year supply (UltraScale+ to 2045)** | Industrial installed bases want a frozen model that runs identically for years. A fixed bitstream plus sealed, SHA-verified weights fits this. A weak argument for LLMs, whose models churn every 6 months. | **Plausible niche:** a "frozen, verified appliance". It is an argument, not a measurement. |
| 7 | **Radiation tolerance / space** | Space-qualified Versal AI Edge exists. Small LMs or encoders on orbit are emerging but niche. Our K26 is not rad-tolerant. | Out of scope for this project. Cite only as context. |
| 8 | **Line-rate packet / data-plane processing** | Per-packet transformers are too big. Tiny models fit (Taurus-class). | **RIGHT** for tiny models (v1-class over raw Ethernet). **VANITY** for LLMs. |
| 9 | **Custom numerics (ternary, INT4, block formats) at bit level** | Yes for edge LLMs. TeLLMe gets 25 tok/s at 5 W on the same K26 with BitNet. Custom formats cut bytes per token, which is the only decode lever on a bandwidth-starved device. But NPUs and GPUs are adding FP4/INT4 and LUT kernels quickly (NVFP4 on Thor, T-MAC on CPUs). | **Research-legitimate but crowded.** Defensible only with a clear bytes/token or J/token result, measured. |
| 10 | **Energy at low duty cycle / always-on small models** | An FPGA idles at several watts. NPUs and MCUs idle far lower [U]. The FPGA does not win on always-on LLM energy. | **VANITY** unless measured and beaten. |

### Clear calls for the team

**Stop / do not build (a GPU, NPU or CPU already does it better):**

- Any push to make the KR260 a competitive small-LLM *throughput* or *TTFT* engine. The ceiling is about 25–30 tok/s at Q8 (Pi 5 / RK3588 class), and prefill trails by 100–1,000x.
- Energy-per-token leadership claims.
- "First LLM on Kria" claims: prior art includes TeLLMe, Hummingbird and others on the same silicon.

**Worth building (the FPGA is the right tool):**

1. µs-latency tiny classifiers and gates in I/O paths (v1 lineage: wire-to-wire over raw Ethernet or TSN).
2. A sensor front end in PL (vibration, AE, current) → small encoder → typed, calibrated outputs.
3. An R5/PL "safety shell" that validates, rate-limits and interlocks actions proposed by any LLM, wherever that LLM runs (possibly on an Orin or a Pi).
4. Deterministic, replayable, integrity-verified inference as an *assurance artifact*. Report it honestly, alongside a DetLLM-style GPU baseline.

**Honest positioning sentence:**

> The KR260 should be the deterministic, certifiable, I/O-attached edge of the system: sensing, gating, verifying and arbitrating. The LLM itself belongs on whatever cheap GPU, NPU or CPU decodes 5–15x faster.
