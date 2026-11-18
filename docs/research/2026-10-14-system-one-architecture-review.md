# System One FPGA architecture review

Review date: 2026-10-14, America/Chicago. Some qualification receipts are dated 2026-10-15 UTC. This is a documentation-only review of saved evidence, source code and primary publications; no implementation, synthesis, routing, deployment, authentication or new board experiment was performed.

Companion deliverables: [comparison matrix](2026-10-14-system-one-comparison-matrix.md), [experiment plan](2026-10-14-system-one-experiment-plan.md), [source and artifact registry](2026-10-14-system-one-sources.json), [recomputed 200 MHz profile](2026-10-14-system-one-profile-analysis.json), and [preservation audit](2026-10-14-system-one-preservation.json). The older October 11 literature survey remains background, not current hardware status.

## 1. Architectural verdict

The qualified design is a credible, programmable, integer **encoder** with unusually explicit numerical and deployment evidence. Its best-supported optimization direction depends on request length. Short requests nearly saturate the existing 128-bit input path while waiting for weight banks. Longer requests reuse those weights effectively and spend more time issuing MAC operations, executing nonlinear operations, and holding off incoming data. A blanket claim that the implementation is DDR-bound is unsupported.

The most defensible near-term work is to characterize those regimes and evaluate selective memory-path changes for short requests and compute/control changes for longer requests. Merely proposing double buffering, outstanding reads, lookup-table nonlinearities or on-chip activation reuse adds features the implementation already has.

Reaching 300 MHz is primarily a physical locality and control-distribution problem, with pipeline alignment and storage-port constraints. Final routed timing points to activation-capture/query distribution; placement also exposes opcode-to-DSP selection. Raising the clock constraint alone is not a solution. A separate, smaller-capacity encoder configuration is worth evaluating because the qualified image reserves H1024 storage while the deployed trained model is H384. Capacity and efficiency should be separate design points.

Autoregressive generation requires a distinct execution contract, complete model numerical reference, KV-cache engine, causal attention, model-specific nonlinearities and vocabulary projection. Existing SYS3/INT4/RoPE/KV proofs are useful components, not a deployed decoder. Neither published decoder establishes a speedup over this encoder. The comparison matrix deliberately does not calculate one.

## 2. Evidence hierarchy and preservation

The controlling receipt is [hardware-qualification.json](../../build/v2/kr260-opt-attention-context-capture-large/hardware-qualification.json). It records actual 199,999,998 Hz, feature `0x5377ffff`, eight H1024 fixtures, four head32/query-group fixtures, eight real L12 smoke cases and 350 frozen L12 requests, all bit-exact. It records preserved 125 MHz recovery, unchanged boot reservation, and exact model restoration/readback. [final-state.json](../../build/v2/context-capture-board-validation/final-state.json) is a saved observation, not a fresh live-board probe.

The tested archive SHA256 is `ecd320163baa3c289c64e069186497974d4703039df4a455bc8620d357d7ec99`. The historical package/route metadata contains `hardware_qualified:false` and obsolete authentication status because it predates qualification. Preserve that chronology; the separate hash-bound hardware receipt supersedes the status without rewriting the tested package.

This review independently matched the 23 public RTL hashes to the frozen regression manifest before analysis. A broader before/after hash audit covers sources, model image, snapshots, recovery artifacts where locally available and the tested archive. The pre-existing worktree contains many modified/untracked files; this review does not attribute them to itself or reset them. Only research documentation and the handoff are intended changes.

Evidence strength in this report:

- **Observed:** saved hardware counters, exact output comparisons and live-clock receipts.
- **Implemented:** source behavior, with the qualified profile checked against its manifest rather than inferred from default parameters.
- **Estimated:** algebraic service/compute ceilings or publication estimates, with assumptions stated.
- **Hypothesis:** a proposed change whose benefit still requires a controlled experiment.

## 3. Actual execution path

### 3.1 Host, ABI and request boundaries

The deployed model is `minilm-l12-v1-kr260`: 12 layers, hidden width 384, 12 heads of dimension 32, FFN width 1536, vocabulary 30,522 and a 128-token runtime window. The compiled image is 33,916,928 bytes, SHA256 `4129baded344729ccc7ef6a3f0a2b34799280a91d88173ae1c0b197cdef8c3bb`. H1024 is hardware capacity tested with synthetic fixtures; it is not the deployed model size.

[`ddr_image.py`](../../src/sysone/v2/ddr_image.py) defines the executable format: little-endian 16-byte beats; 1 KiB section alignment; 64-byte instructions; per-channel bias and multiplier records; tiled INT8 weights; embedding, LayerNorm, GELU, exponent and pooling data; and task-head descriptors. Embedded pointers and the RUN descriptor are absolute 32-bit byte addresses. A 40-bit AXI master therefore does **not** establish support for high DDR or relocatable model execution.

[`kr260_link.py`](../../src/sysone/v2/kr260_link.py) maps reserved PS memory through uncached `/dev/mem` with `O_SYNC`, appropriate to the current noncoherent HP0 interface. It validates platform state, dimensions and memory spans and verifies the loaded image before inference through its calling workflow. AXI-Lite registers at `0xA0000000` provide control, program pointer, shape, token/result addresses, cycle results, build/features and diagnostics. The host writes a request and starts execution, polls completion, then reads hidden states and executes task heads. Polling includes a 0.2 ms sleep; host round-trip is not a pure fabric counter.

[`encoder_system.sv`](../../rtl/v2/encoder/encoder_system.sv) orchestrates instruction execution and result output. [`encoder_layer.sv`](../../rtl/v2/encoder/encoder_layer.sv) decodes EMBED, LAYERNORM, LINEAR, ATTENTION, ADD_SKIP, optional POOL and END. Operations execute sequentially at the instruction level. LINEAR internally overlaps loading, computation and draining; that is different from overlapping arbitrary encoder instructions.

The measured deployment returns encoder hidden states to CPU heads. The format also has optional head-program support; availability in source must not be confused with the measured CPU-head configuration. Results are streamed by [`result_streamer.sv`](../../rtl/v2/encoder/result_streamer.sv) in the qualified profile.

### 3.2 Numerical contract

The executable specification is in [`ddr_image.py`](../../src/sysone/v2/ddr_image.py), its `ImageMachine`, [`int_encoder.py`](../../src/sysone/v2/int_encoder.py), and [`encoder_pkg.sv`](../../rtl/v2/encoder/encoder_pkg.sv). This is not simply “all 8-bit.”

| Path | Implemented representation and ordering |
|---|---|
| Linear | Symmetric INT8 operands, INT32 accumulation/bias; per-output-channel multiplier and shared shift; widened requantization product; saturation; optional INT8 GELU table |
| Requantization | `(a*M + 2^(S-1)) >>> S`, or product for S=0; signed arithmetic shift; rounding rule matters for negative halfway values |
| Residual | INT16 with explicit intermediate and final clamps at ±32767 |
| Attention scores | Signed dot products; narrower RTL storage justified from maximum dimensions and operand ranges |
| Exponents/probabilities | 256-entry UINT16 exponent table; clipped distance index; index 255 produces zero; reciprocal `floor(2^24 / sum(e))`; rounded UINT8 probability capped at 255 |
| Context | UINT8 probability × signed INT8 value, accumulated then requantized/clamped to ±127 |
| LayerNorm | Rounded integer mean, centered square reduction, truncated variance, integer square root with minimum 1, integer reciprocal, fixed-point affine and final clamp; F=12 |
| Embedding | Separate per-dimension word/position requantization and clamps before type addition and final residual clamp |

Compiler limits include 17-bit requantization multipliers and operation-specific shifts. These checks are part of the ABI. Replacing arithmetic with library IP or changing reduction/fusion order must retain intermediate widths, signedness, truncation and saturation, not merely compare final class labels. The integer reference uses float64 BLAS on integer-valued arrays in some matrix paths under a stated exact-integer range; “integer-only inference semantics” is more precise than claiming every host reference instruction is integer machine code.

An online softmax, RMSNorm substitute, INT4 conversion, ternary conversion, altered calibration or changed clipping is a **new numerical/model variant** unless equivalence is demonstrated. In particular, an online running maximum with rescaling generally changes this finite-precision exponent/reciprocal contract even when the real-valued softmax is mathematically equivalent.

### 3.3 Compute and buffering

The qualified manifest enables 32 linear output lanes, 16 attention query lanes, registered MAC inputs, pipelined dot reduction, five-cycle activation reads, local capture/distribution, pipelined URAM, registered FIFO flags, BRAM linear accumulators, four drain lanes and four normalization lanes. Default-off RTL parameters are not the deployed settings. See [regression profile](../../build/v2/kr260-opt-attention-context-capture-large/regression.json) and [packaged app metadata](../../build/v2/context-capture-board-validation/app.json).

[`mac_array.sv`](../../rtl/v2/encoder/mac_array.sv) supplies a shared 32×16 multiplier array. The A operand is signed 9-bit so unsigned attention probabilities up to 255 fit; B is signed INT8. Linear and attention consume the same array at different times. The qualified plain mapping is not the optional packed-DSP branch. The dot tree is explicitly registered; operand/tag delays in consumers must match its latency.

[`linear_engine.sv`](../../rtl/v2/encoder/linear_engine.sv) is weight-stationary across request tokens. A 16×32 tile needs 32 input beats and supports 512 products per issued token. Requests run ahead, two weight banks and two channel banks serve the loader, and two accumulator banks overlap one output tile's drain with the next tile's computation. The BRAM implementation and source-row cursor are already present. The practical inner-tile competition is approximately `max(n,32)` cycles for n tokens before pipeline overhead: 32 cycles to load a tile versus n MAC issues to apply it. This predicts a transition near 32 tokens and agrees with the saved counter trend; it does not prove every stall's cause.

[`attention_engine.sv`](../../rtl/v2/encoder/attention_engine.sv) processes heads sequentially and groups **query tokens** across 16 lanes. Within each group, a key/value word is shared across those queries. Scores and exponents are buffered on chip, with one reciprocal divider per query lane, followed by P×V accumulation and four context output lanes. Storage is proportional to the query-group width times the key count, not a DDR materialization of every head's complete N×N score matrix. Halving lanes does not halve the number of heads.

The 16-query schedule has an explicit cost: the regression receipt records 0–5.3200% encoder-cycle increase versus its 32-query comparison across its declared cases. The matched hardware suite shows 2.00375% more mean encoder cycles versus the qualified 125 MHz baseline, which includes the complete profile change and DDR behavior. Those are different comparisons; neither is a free frequency gain.

[`layernorm_engine.sv`](../../rtl/v2/encoder/layernorm_engine.sv) fetches parameters, makes sum and centered-square passes, runs sequential divisions and integer square root, then emits normalized elements. Increasing output lanes alone cannot remove the row-level reduction/division/root cost. Earlier bring-up reports attributing ~31% to normalization describe older profiles; the current aggregate counters do not provide a current per-opcode LayerNorm fraction.

### 3.4 Memory lifetime and physical organization

Eight logical buffers map to **seven physical** 128-bit stores. X/Q/K/V/CTX are INT8; R/A are INT16. FFN intermediate G aliases Q/K/V/CTX after their attention values die. This lifetime reuse is already implemented. At capacity H and N tokens, raw activation payload is `9NH` bytes. H1024,N128 requires 1,179,648 bytes (1.125 MiB) before primitive rounding and other state; the H384 live tensor footprint is 442,368 bytes.

The routed design allocates 36 URAM blocks, whose raw capacity is 1,327,104 bytes; this is not equivalent to an arbitrary multiported scratchpad of that size. Banking, read latency, byte writes, port arbitration and memory shape constrain usability. The rest of the state occupies BRAM, LUTRAM and registers, including accumulators and attention tables. G aliasing precludes concurrently reusing the same banks for new KV state without a new lifetime schedule.

The 256 MiB reserved range begins at `0x60000000` and ends at `0x6fffffff`. The current block design maps HP0 DDR_LOW. Linux, uncached host copies and PS DDR arbitration remain part of the system. No reserved-memory enlargement or boot change is justified by this review.

### 3.5 AXI traffic and existing safeguards

[`axi_memory_port.sv`](../../rtl/v2/platform/kr260/axi_memory_port.sv) has one 128-bit AXI master; up to eight outstanding read **bursts**; a four-entry logical-request length queue; registered requests/flags in this profile; bursts split at 256 beats and 4 KiB boundaries; and directly propagated R-channel backpressure. Writes have address/data/response states and start only after the adapter's prior read delivery drains. Error responses are latched. Eight outstanding bursts is not eight simultaneous independent compute streams or eight DDR channels.

At 200 MHz, one 128-bit beat/cycle is an ideal **3.2 GB/s** read interface ceiling. This is a fabric-interface ceiling, not a measured DDR-controller peak. Four PS ports can raise the aggregate path ceiling but still share the same physical DDR controller, its arbitration and CPU traffic. Widening an internal bus behind one 128-bit PS port does not create that bandwidth.

Model weights are read once per layer operation and reused over all tokens in that request. Embedding rows, instructions, metadata and nonlinear tables add traffic. Intermediate activations remain on chip; final hidden states are written back. Therefore total image size is not equal to bytes transferred per inference: a large embedding table is indexed rather than streamed in full.

## 4. Reanalysis of saved measurements

### 4.1 Matched latency

[performance-comparison.json](../../build/v2/context-capture-board-validation/performance-comparison.json) verifies the same 350 frozen inputs, model, outputs, predictions and aggregate task statistics.

| Saved measurement | Qualified 125 MHz | Qualified 200 MHz |
|---|---:|---:|
| Mean encoder time | 17.27168 ms | 11.01110 ms |
| Encoder p95 | 36.08026 ms | 23.24372 ms |
| Observed encoder maximum | 57.98782 ms | 38.25647 ms |
| Mean encoder clocks | 2,158,959.69 | 2,202,219.78 |
| Mean host round-trip plus CPU heads | 19.26884 ms | 13.00962 ms |
| Mean CPU heads | 1.52643 ms | 1.53268 ms |

Mean encoder improvement is 1.56857× and 36.2477% less latency; host round-trip plus heads improves 1.48112×. These saved runs have no repeated-run confidence intervals. The separate deterministic 128-token smoke measures 60.31250 versus 39.78674 ms; it need not equal the maximum of a differently composed 350-request suite. Tokenization, cold model loading and application queueing are excluded from the host-plus-head figure.

### 4.2 New analysis, no new hardware run

The companion profile JSON recomputes aggregates directly from all 350 records in [the 200 MHz eval](../../build/v2/context-capture-board-validation/eval.json), retaining its SHA256. Across the suite, mean token count is 28.386, mean AXI read payload is 21.687 MB/request and accepted reads average 200.79 beats/burst. Total read beats and burst counts equal the saved 125 MHz run: this optimization did not reduce total DDR read payload.

| Input token range | Cases | Mean request ms | Accepted payload GB/s over whole request | Linear issue cycles / request cycles | Weight-bank wait | R-channel backpressure |
|---|---:|---:|---:|---:|---:|---:|
| 1–8 (observed requests start at 3) | 44 | 7.430 | 2.917 | 19.16% | 69.45% | 0.20% |
| 9–16 | 116 | 7.829 | 2.769 | 32.54% | 51.58% | 0.19% |
| 17–32 | 77 | 8.803 | 2.463 | 54.54% | 20.86% | 0.73% |
| 33–64 | 81 | 14.054 | 1.544 | 68.95% | 0.56% | 22.63% |
| 65–128 | 32 | 25.142 | 0.864 | 68.04% | 0.14% | 41.88% |

Definitions come from [`kr260_encoder.sv`](../../rtl/v2/platform/kr260/kr260_encoder.sv): read service wait counts pending accepted beats with RREADY but no RVALID; backpressure counts RVALID without RREADY; linear weight wait is a compute C_WAIT condition with the needed bank unavailable. Counters reset at accepted RUN and freeze at completion; event counters overlap. They are **not a partition** of total time, and issue cycles are not a dimension-independent measure of useful arithmetic.

Whole-suite request-window ratios: read service wait 0.826%, backpressure 15.609%, linear issues 53.429%, attention issues 2.524%, weight wait 21.898%, drain wait zero and result source wait zero. An increase in attention issue cycles partly reflects less lane reuse, not more useful model work.

Short-bin accepted payload is about 91.1% of the 3.2 GB/s interface ceiling **over the entire request**, a strong reason to investigate more input bandwidth or fewer weight bytes. It is not a measurement of 91.1% of physical DDR peak, nor a DDR microbenchmark. Long-bin backpressure shows the consumer often refuses already offered data, a reason to measure compute/nonlinear scheduling before adding ports. Near-201-beat average bursts also weaken the idea that universally tiny bursts are the main problem; the distribution and per-opcode attribution are still missing.

### 4.3 Explicit analytical limits

For the deployed L=12,H=384,F=1536 encoder, its six dense matrices per layer contain `L(4H²+2HF) = 21,233,664` INT8 weights. Ignoring startup, metadata and nonlinear operations:

- Linear compute lower bound at 200 MHz: `n × 21,233,664 / (512 × 200e6)` seconds. At n=128 this is 26.542 ms.
- Bidirectional QK and PV work: `2Ln²H` products. Using 16×16 active attention multipliers gives 2.949 ms at n=128, assuming full issue utilization and no partial-group loss.
- Since these share the array, their ideal arithmetic times add: approximately 29.491 ms at n=128, before buffer reads, softmax, LayerNorm, drain and other stalls. This is a favorable lower bound, not a predicted implementation time.
- About 21.7 MB transferred through an ideal 3.2 GB/s path needs about 6.8 ms. At short n the weight traffic sets a meaningful floor; at n=128 linear arithmetic alone exceeds it.

For a modification that accelerates only a measured fraction p of serial time by factor s, use `1 / ((1-p)+p/s)` as an upper-bound model. Overlapping diagnostic events cannot be substituted for p. A 300/200=1.5 clock ratio is only a constant-cycle thought experiment; new schedules, DDR clocking, added latency and host time can change the result.

## 5. Timing and resources: what 300 MHz entails

| Stage | LUT | FF | BRAM36 tiles | URAM288 | DSP |
|---|---:|---:|---:|---:|---:|
| Full synthesis | 68,765 | 52,552 | 50 | 36 | 579 |
| Routed full design | 63,609 | 51,942 | 50 | 36 | 579 |

The final [`utilization.rpt`](../../build/v2/kr260-opt-attention-context-capture-large/utilization.rpt) explicitly says **Routed**, so these are better comparison counts than synthesis. Routed LUT use is 54.31%, yet occupied CLBs are 11,996/14,640 = **81.94%**. LUT count alone substantially understates placement pressure. Neither spare DSP count nor unused URAM guarantees routable compute expansion.

The legal 200 MHz route has +0.101 ns setup, +0.010 ns hold, 122,669/122,669 nets routed and zero routing errors. The [final timing report](../../build/v2/kr260-opt-attention-context-capture-large/timing.rpt) identifies:

- Setup: local activation capture `port_data_reg[0][86]` to attention `gen_query_distribution.gen_group[3].data_reg[86]`; data delay 4.850 ns = 0.114 ns logic + **4.736 ns route**. Physical distribution, not arithmetic depth, dominates this worst path.
- Hold: query distribution into local query storage, only +0.010 ns slack. New pipeline/replication changes need both setup and hold evidence.
- The [placed 200 MHz path](../../build/v2/kr260-opt-attention-context-capture-large/placement/critical-200mhz.rpt) instead runs instruction/opcode selection to MAC DSP A input: 3.892 ns data, 3.492 ns estimated routing, three LUT levels. The fact that the worst path moves is evidence against optimizing just one isolated datapath.

The placed sweep is +3.503/+2.170/+0.503/−0.497/−1.164 ns at 125/150/200/250/300 MHz. These are placement estimates; there is no 250/300 MHz legal route. The historical 200 MHz placement met its unchanged +0.500 ns route admission by only 0.003 ns. Seven older rejected placements remain rejected; no later literature result changes that decision.

Synthesis fanout reports show reset at 3,572 loads and embedding beat controls near 1,390. Those are secondary locality candidates, not proof they are the routed worst paths. The context-capture mapping proof matters: four full-hierarchy DSPs use AREG0/BREG1/MREG0/PREG1 with 92 fabric capture FFs. The standalone probe's BREG0 is not the full-system contract; an earlier erroneous gate was corrected without changing arithmetic. Do not infer a new stage from the different standalone mapping.

**Recommended physical sequence:** localize capture-to-query distribution; localize registered instruction selects around MAC groups; evaluate a model-sized capacity profile; then examine residual reset/embedding/control fanout. Preserve throughput and tag alignment. A spatially partitioned array or bank-local pipelines may help, but hard pblocks, duplicated engines and extra registers can worsen packing. Require path-class and congestion evidence at each step. Isolated slack gains must never be added to full-design WNS.

## 6. Published solutions and inspected artifacts

Full values, workload boundaries and primary links are in the [matrix](2026-10-14-system-one-comparison-matrix.md). Paper summaries there are kept separate from artifact observations below. Repository snapshots were retrieved read-only into a temporary cache, pinned by commit and selected file SHA256; no third-party code was executed or imported into the project.

### 6.1 300 MHz embedded LLaMA2 design: artifact lessons

The [author repository](https://github.com/adamgallas/llama-fpga/tree/bdd90206675594ab6b710a32d5319c68a58d9c36) contains actual SpinalHDL modules, generated-system projects, conversion software and bare-metal host code, beyond an abstract/demo. Inspected paths include `scala/src/main/scala/top/BusInSubMod.scala`, `DataPath.scala`, attention softmax/KV packing, `python/model2bin.py`, `kv260/kv260_sdk.c`, and the KV260 block-design JSON. The BD uses HPC0, HP0, HP2 and HP3; these are four access ports into shared PS memory, not independent physical DDR channels.

The host has low/high memory regions and cache maintenance. Its printed `ps_tps` timer starts before submitting prompt tokens and increments its token count for prompt submissions as well as generated tokens. **That console field must not be treated as a clean decode-only replication of the paper's number.** A future reproduction must instrument prompt and generated-token boundaries separately. The README also contains superseded/commented buggy-download references; the pinned files and explicit current link matter. No complete automated model-quality/rail-power reproduction was established here. No top-level repository license was detected; that is a code-reuse consideration, not a barrier to architectural comparison.

The current repository also covers later platforms/design variants. Its commit and available hardware files are not a demonstrated source-to-bitstream reproduction of the specific paper configuration; retain that provenance gap.

Transferable hypotheses are efficient metadata packing, local streaming control and phase overlap. Their value to System One must be measured because our activations already stay on chip and weights already reuse across encoder tokens. A narrow vector engine is particularly well suited to bandwidth-limited decode; it is not automatically a better multi-token encoder engine.

### 6.2 TeLLMe v2: artifact lessons

The [pinned release](https://github.com/UCI-CORSA/TeLLMe_FPGA_2026/tree/139ad882aba8485048e08993022872128bc00f51) includes HLS source, `.bit`/`.hwh`, PYNQ host, tokenizer and NEON code, under BSD-3-Clause. Large weights/caches/goldens are external downloads and were not retrieved or run. The inspected configuration is 24 layers, H1536, 16 attention heads, with G=3 ternary groups, 5-bit indices and T=28 tables. This differs substantially from our model.

`top_bitnet.hpp` maps buffers and weights across four M_AXI bundles and binds weight storage to URAM. `.hwh` confirms 256-bit HLS interfaces and four enabled PS GP2–GP5 slave paths (the HP interfaces); physical PS-port widths and interconnect conversion must be kept distinct from HLS widths. `load_weight.hpp` combines three 256-bit records and extracts five 140-bit index vectors, plus embedded metadata. This is concrete evidence of layout/loader co-design. `linear.hpp` binds multi-read lookup tables to LUTRAM with a declared latency of three.

The host reverses/pads prefill, handles KV movement/synchronization, executes decode, and explicitly includes NEON head work in its prefill timing path. It also maintains more granular timer categories than the single public throughput headline. Its no-FPGA path returns mock outputs in relevant code paths and must not be used as a numerical CPU reference. Golden verification is available but is not a substitute for an independently bound model-quality evaluation. Reversed causal attention is not directly applicable to our bidirectional encoder; LUT matmul requires ternary weights and a different trained/quantized model.

The pinned source has an additional reproducibility issue: headers reference `../config/config.hpp` and `../config/macro.hpp`, whereas the released tree puts configuration under `src/config/` alongside `src/top_bitnet.hpp`. The repository tree has no HLS project/build Tcl to establish the intended include layout. A future source rebuild must resolve that layout and bind rebuilt output to the supplied overlay; no repair/build was attempted here. Nominal ternary entropy is not actual transferred bytes: five-bit indices for three weights and the 700-bit index payload inside 768 transferred bits incur overhead before dimension padding. The source also uses FP32 norm reductions, reinforcing the mixed-precision description.

### 6.3 Integer encoders and other generative systems

FQ-BERT is a particularly relevant algorithm/architecture precedent: matrix-array sharing, integer nonlinearities and buffering already have prior art. I-BERT's [author code](https://github.com/kssteven418/I-BERT/tree/1b09c759d6aeb71312df9c6ef74fa268a87c934e) exposes quantization, integer GELU/softmax/LayerNorm semantics. The inspected PyTorch LayerNorm code still uses a sqrt expression with a comment calling for an equivalent integer kernel, so an algorithm repository is not itself a verified FPGA implementation.

The [trans-fat artifact](https://github.com/cjg91/trans-fat/tree/548db9e42160103db1fe6818164c0105652c962f) provides staged HLS optimization and tests. Inspected v3 config is N128/H768/A12/FFN3072, and stage2 mixes integer matrices with floating scale/exp/sqrt operations. Its two-U200, single-layer experiment should not be relabeled as an end-to-end integer BERT engine.

The newly located [QFlash source](https://github.com/wzh0715/QFlash/tree/d5376b423bf2c2688823bf7a070e40a12faff5db) is useful adjacent encoder work: quantized attention, AddNorm, explicit HLS scripts/testbenches and a tiled attention reference. The scripts inspected target U50 at 5 ns; this target is not proof of 200 MHz routed board timing. The repository chiefly presents ViT/ImageNet algorithms; no verified publication identity or matched language-model result is assumed from its comparison table. Its alternative softmax/normalization semantics require a new model/reference variant here.

NPE supports the importance of nonlinear throughput matching and scheduling, but its timing evaluation explicitly uses software-simulated inference times; the matrix does not upgrade those to saved hardware measurements. SECDA's primary case study and unavailable author repository are distinguished from a different, available SECDA-TFLite toolkit. LlamaF's host/FPGA split highlights CPU attention and quantization costs. FlightLLM's [release README](https://github.com/FlightLLM/flightllm_test_demo/blob/4a9625149e19c3baccad0786ae0d90bab2410890/README.md) explicitly separates actual U280 tests from simulated VHK158 profiles. The spatial-acceleration paper's timing difficulty with larger systolic arrays is directly relevant to our locality risk; HBM systems still do not establish a transferable embedded speedup.

## 7. Model quality, power and reproducibility

### 7.1 Quality is a separate axis

[Training/evaluation history](../../results/v2/chain/minilm-l12-v1.json) includes full-test float and `test_int8` entries. For example, float versus the recorded INT8 evaluation is CLINC in-scope 0.96644/0.96400, ATIS intent 0.97312/0.97200, SICK 0.78161/0.78283 and MSRP 0.68696/0.68870. These are saved model-study results, not a fresh run and not automatically the exact ImageMachine or FPGA deployment path; the producing script and calibration stage must accompany a publication table.

The hardware suite's 350 requests cover seven datasets, with only 50 requests/dataset and different counts of task predictions/segments. SGD has fewer labeled intent cases; multi-CLINC has multiple segment predictions. Do not average those counts into an unexplained global “accuracy.” Bit-exact output parity is implementation evidence; it does not prove generalization, safety, calibration, generation quality or improved accuracy after retiming.

Keep model bytes, tokenizer, calibration chains, task heads, reject thresholds, splits and sample IDs fixed for architecture experiments. Changes to quantization, context packing, attention masks or model family need a separately named model-quality study. The older L6 task results and L12 results must not be merged into one best-of-model table. WikiText perplexity and intent/slot scores are different quality measures; perplexity-normalized “intelligence/J” across tokenizers/models is not a substitute for matched utility.

### 7.2 Energy evidence

No current board/rail power trace is tied to the System One qualification workload. Neither resource counts nor a higher clock establishes energy efficiency. Use total-board energy/request and, where instrumentation permits, PS/PL/DDR rails with idle and active intervals, sampling rate, integration window, fan/cooling and CPU settings. Report cold startup and resident inference separately. For generation, report joules/prompt and joules/generated token with prompt/output lengths and head work included.

The source matrix separates measured, estimated and unspecified power methods. In particular, a Vivado estimate must not be compared as if it were measured wall or rail power. Published tables with unspecified rail boundaries are useful context, not a matched energy benchmark.

### 7.3 Reproducibility strengths and gaps

Strengths are source/fixture/package hashes, exact capability checks, image readback, random-stall simulation, eight short/boundary lengths, larger-capacity fixtures, frozen request identifiers and separate recovery. These are publishable evidence practices but not alone an architectural novelty claim.

Gaps: clean source revision/package of the currently dirty worktree; a small documented public reproduction path; pinned tool/IP versions and generated constraints; model/checkpoint redistribution provenance; an explicit source-to-bitstream/receipt chain; multiple independent measurement runs; temperature and DDR contention profiles; per-opcode cycle attribution; burst/occupancy distributions; sustained rail power; and full quality results for the exact exported integer model. An observed maximum on shared Linux DDR is not WCET. Capacity fixtures need a trained larger-model test before any quality/performance claim for H1024.

## 8. Three separate recommendation tracks

The [experiment plan](2026-10-14-system-one-experiment-plan.md) supplies detailed ranks, effort, risks, acceptance criteria and dependencies. Highest-priority conclusions are:

1. **Encoder:** use existing evidence to establish request-length regimes; then test more effective weight bandwidth for short requests, and measured nonlinear/compute scheduling for long ones. Do not widen drain lanes first when drain-wait is zero. Evaluate metadata caching and a dedicated H384 capacity configuration before a wholesale engine rewrite.
2. **300 MHz:** address actual routed capture/query locality and placed opcode selection using bank/group-local state and carefully aligned pipelines. Consider smaller capacity and physical decomposition. Treat independent-engine or multiple-clock designs as higher-risk alternatives with CDC/throughput implications.
3. **Generation:** define the model, precision, memory/ABI and complete CPU reference first. Establish an ARM baseline, then offload enough adjacent work to avoid per-operation transfers. Add prefill and decode schedules separately. INT4 mixed precision is a plausible standard-model path; ternary LUT matmul is a different model-family path. Neither is an automatic extension of SYS2.

For generation, budget `weights + scales/zero points + embedding/head + KV + temporary buffers + runtime/OS`. Dense weights alone for a 0.6B W4 model are about 300 MB decimal, already larger than the preserved 256 MiB reservation. A 7B W4 capacity strategy that displaces Linux does not fit the existing runtime contract. KV cache payload is `2 × L × context × KV_heads × head_dim × bytes_per_element`, before metadata/alignment. GQA changes KV_heads, not the query count. Compute actual model-specific packing and host-side copies before claiming fit; this review authorizes no allocation change.

## 9. Research contributions worth testing

| Candidate contribution | Existing support | Evidence needed for a defensible claim |
|---|---|---|
| Numerically invariant, locality-aware retiming of a programmable embedded encoder | Exact source/profile/package/output chain and routed 200 MHz result | Ablations linking each register/storage/control change to routed paths, cycles, energy and unchanged quality; compare with prior encoder methods |
| Capacity-versus-latency design methodology with lifetime-reused memories | G aliases dead Q/K/V/CTX storage; H1024 capacity and H384 real model | Matched capacity-specialized profiles, port/lifetime model, packing and routed results; exclude synthetic capacity from model-quality claims |
| Length-dependent encoder memory/compute co-design | New saved-counter analysis exposes a transition near 32 tokens | Controlled bandwidth/compute ablations, per-opcode attribution, repeated timing/energy and predictive accuracy across model sizes |
| Reproducible numerical ABI and recovery-aware deployment for embedded language inference | Hash-bound manifests, exactness, memory and feature guards, preserved recovery | Public artifact, malformed/overflow/fault cases, clear comparison with existing reproducibility practices; avoid calling process alone a new accelerator architecture |
| Hybrid encoder plus small generative engine for bounded tasks | Components and separate CPU generation preparation only | Full model implementation, quality/usefulness evaluation, complete TTFT/decode/energy evidence and robust memory coexistence |

“First integer FPGA BERT,” “first on-chip activations,” “first double buffering,” “300 MHz is novel,” “H1024 gives better answers,” and “encoder requests/s beats generated tokens/s” are not defensible contributions. The strongest potential paper is an evidence-backed co-design method and ablation study; novelty remains a hypothesis pending those results and a broader submission-time search.

## 10. Completion and continuation

This review leaves the 200 MHz package, frozen sources, numerical/image baselines and locally available recovery artifacts intact. The automation remains completed/deleted; it was not recreated. No new hardware state is asserted. Next work is the prioritized experiment plan **only if separately scoped for implementation/measurement**; the completed E0 saved-evidence analysis can already be used in a research draft. HANDOFF.md points to these deliverables.
