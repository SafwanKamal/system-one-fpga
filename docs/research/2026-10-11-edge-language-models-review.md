# Literature review: dependable language models at the edge

**Project:** System One FPGA  
**Review date and search cutoff:** 11 October 2026  
**Scope:** edge inference, FPGA acceleration, predictable timing, numerical and statistical reliability, typed outputs, and adjacent compiler/runtime research.

**Repository snapshot:** HEAD `bc27a36`, with existing uncommitted project changes inspected. This review records that working-tree state; it does not certify a clean release or rerun the hardware experiments.

## 1. Main finding

The strongest opportunity for this project is a **language inference service with an explicit contract across arithmetic, memory, timing, and output types**. Individual parts have substantial prior art. Combining them convincingly on a modest FPGA SoC remains a promising research direction.

The accelerator literature establishes that compressed language models can run efficiently on FPGAs, including Kria-class devices. Real-time systems research establishes how to reason about bounded computation and shared-resource interference. Programming-language research establishes mechanisms for enforcing syntax, some typing rules, and resource discipline. Statistical learning research establishes calibrated uncertainty, rejection, and certain distribution-dependent risk guarantees. These bodies of work support different properties. A fast decoder is not automatically deadline-guaranteed; a well-typed result is not automatically correct; bit-exact hardware can reproduce a wrong prediction perfectly.

**Assessment from this review:** the most defensible near-term research contribution is a bounded, integer, multi-task encoder with typed results and explicit failure/abstention semantics. A generative decoder is a valuable extension, but requires its own numerical reference, execution contract, and quality evaluation. This is a positioning hypothesis, not a claim of first-ever novelty.

### Current project evidence

The local repository already gives this direction a concrete foundation:

| Property | Evidence in the project | What remains to establish |
|---|---|---|
| Integer implementation agreement | Independent integer/image references, RTL simulation, and hardware comparisons | Proof or broader verification beyond the tested inputs |
| Embedded acceleration | Nexys and KR260 deployments with separate board image formats | Matched energy and sustained workload measurements |
| Multi-task language understanding | Shared encoder, intent/slot/dialogue/pair heads | Deployment-domain generalization and reliable rejection |
| Measured performance | Scaling notes report MiniLM-L12 at 124,999,999 Hz, mean encoder 17.1598 ms over 350 cases | A worst-case bound under a declared environment |
| Memory discipline | Reserved DDR, image CRCs, host range checks, runtime preflight | Hardware-wide descriptor/address validation and bounded DDR service |
| Generation | Separate Qwen3-0.6B CPU baseline prepared | FPGA decoder support and validated board quality/timing |
| Type safety | Bounded formats and some validation | A stated type system or checked semantic output contract |

These are **repository-reported results**, not independently rerun measurements in this review. Sources inspected locally include README.md, rtl/v2/README.md, rtl/v2/KR260_SCALING.md, scripts/v2/kr260/README.md, scripts/v2/kr260/generation.md, src/sysone/v2/ddr_image.py, memory_protocol.py, kr260_link.py, and kr260_runtime.py.

The current deployed datapath is an INT8, bidirectional encoder. The scaling notes explicitly identify missing causal attention, KV caching, rotary embeddings, gated FFNs, and packed INT4 support. They also supersede the generation baseline's earlier fixed one-second first-word target with per-model, per-workload timing budgets. The shared-DDR Ubuntu configuration currently has no established hard timing guarantee.

## 2. Review method and terminology

This is a focused narrative literature review, organized around the project's engineering questions. It is not a PRISMA-style systematic review or an exhaustive inventory. Searches combined FPGA/edge/transformer/LLM terms with WCET, deadline, memory isolation, reliability, quantization, constrained decoding, type systems, and compiler terms. Primary sources were prioritized: papers, proceedings, author repositories, and research-group documentation.

The accompanying registry records 64 works and the depth of inspection. All were screened through primary records or primary text; selected sections of the closest hardware papers, type-constrained generation, and scheduling papers were examined in more detail. Many adjacent works were screened at abstract level. Performance figures are author-reported unless identified as a local project result. Implementations and experiments in the papers were not reproduced.

Dates require care. A 2025 preprint may become a 2026 conference paper. TeLLMe's April 2025 paper, October 2025 v2 preprint, and FPGA 2026 publication should not be counted as three independent systems. TerEffic's versions report different performance values. LUT-LLM has a 2025 submission and 2026 revision. The registry generally uses first preprint year for preprint links and states inspection level.

### What the desired guarantees mean

| Term | A precise interpretation | Insufficient evidence |
|---|---|---|
| Edge-deployed | Runs in a specified local device/memory/power environment | A server FPGA called an “edge accelerator” |
| Hardware-accelerated | Declared portions of the request execute in hardware | A matrix kernel benchmark presented as whole-service performance |
| Timing-guaranteed | All admitted requests meet a defined deadline under stated assumptions, or a separately defined statistical guarantee | Mean, p99, maximum observed, or a clock-frequency target |
| Numerically reliable | Arithmetic matches a specified finite-precision semantics | Similar final accuracy alone |
| Fault-tolerant | Defined faults are detected, contained, or corrected within a fault model | Bit-exact operation when no faults occur |
| Statistically reliable | Stated risk or coverage behavior on a defined population | High average accuracy or low ECE alone |
| Structurally valid | Complete output belongs to a schema/grammar | Prompt instructions asking for JSON |
| Type-safe | Declared typing/resource rules are enforced at a specified boundary | Parseable JSON or Python type hints alone |
| Semantically correct | Output satisfies the task specification | Type checking, grammar validity, or fluent explanations |

The layers should be reported separately. Their composition is the system contribution to investigate.

## 3. FPGA and edge acceleration: the closest literature

### 3.1 Encoder accelerators are the immediate comparison set

[FTRANS][H01] compresses transformer weight matrices with block-circulant representations and co-designs FPGA execution. Its reported gains combine a changed model representation with hardware optimization. The relevant lesson is algorithm/architecture co-design; direct speed comparisons require matching the compressed model's quality and workload.

[FQ-BERT][H02] is closer to the existing implementation: it quantizes weights, activations, softmax, layer normalization, and intermediate values, then targets ZCU102/ZCU111. It makes the entire numerical path part of the accelerator problem. Use it as a direct related-work anchor for integer transformer execution.

[Chen et al.'s spatial acceleration study][H03] separates model-specific spatial execution from temporal reuse and uses an analytical resource/performance model. This is useful when considering whether to replicate operators, fuse stages, or retain the reusable MAC/sequencer design. Hardware replication buys locality and concurrency at a cost in routing, buffers, and model flexibility.

[FAMOUS][H12] targets dense multi-head attention. It is relevant to the attention engine and its memory organization, but its attention-kernel results must remain separate from end-to-end encoder results. Optimizing attention does not resolve embedding, FFN, normalization, transport, and host-head latency.

**Project implication:** compare the current encoder primarily with encoder accelerators using the same sequence lengths, model dimensions, precision, and quality target. Decoder token throughput is a different workload. An encoder can process a whole sequence with weight reuse; batch-one decoding repeatedly processes a new token against a growing state.

### 3.2 HBM FPGA LLM systems teach architecture, with limited board comparability

[FlightLLM][H04] integrates sparse DSP chains, mixed precision, heterogeneous memory, and compilation for generative inference. Its U280 implementation and Versal comparison demonstrate FPGA-specific optimization opportunities. The headline GPU comparisons are tied to compressed models, batch size, and much larger memory systems than KR260. “Always-on-chip decode” should not be interpreted as fitting all model weights into Kria SRAM.

[EdgeLLM][H05] combines CPU/FPGA execution, customized mixed-precision operators, structured sparsity, and asynchronous transfer/compute on VCU128. The work is architecturally relevant, but VCU128 is an HBM platform. Its name alone does not establish comparability with a small embedded SoC.

[LUT-LLM][H10] explores vector-quantized lookup computation, with a Qwen3-1.7B prototype on AMD V80. Its 2026 revision reports generation speedups, but comparisons with some FPGA baselines use modified simulators because those systems do not natively support the chosen model. Distinguish actual prototype measurements from modeled baseline results. Lookup computation is worth examining; its tables, codebooks, precision, and training costs need their own budget.

[ITERA-LLM][H11] combines sub-8-bit quantization with iterative low-rank error compensation. Its reported reduction of up to 41.1% concerns linear-layer latency against a quantization-only baseline. That supports testing alternative weight representations; it does not establish a corresponding whole-service reduction.

**Project implication:** borrow data-layout and fusion ideas before attempting to transplant architectures. An optimization should be justified by measured stalls, traffic, and resource pressure in this design.

### 3.3 The closest generative work is on Kria devices

[Li et al.'s embedded KV260 decoder][H06] runs LLaMA2-7B with W4A16 weights/activations and quantized KV storage. The paper reports approximately 5 tokens/s, 93.3% memory occupancy, and bare-metal execution to make room for model state. Its 6.57 W figure is a Vivado estimate. This is evidence that a large compressed decoder can fit, but also that capacity, OS requirements, prefill, and responsiveness must be considered together.

[TeLLMe's original paper][H07] addresses prefill and decoding with ternary weights and INT8 activations on an edge FPGA. Its reported prefill latency matters because decode throughput alone cannot describe first-response behavior.

[TeLLMe v2][H08] is the closest design reference for a Kria generative extension. The inspected preprint uses a BitNet 0.73B model on KV260, lookup matmul, URAM-aware buffering, fused operations, and separate prefill/decode attention. Its ternary/INT8 linear path is mixed with FP16 element-wise computation; it is not an integer-only decoder. It reports up to 25 tokens/s and 0.45–0.96 s TTFT for 64–128-token prompts under a roughly 5 W budget. The ARM NEON LM head is included in end-to-end results. These are workload measurements, not hard WCET guarantees. Its [FPGA 2026 author artifact](https://github.com/UCI-CORSA/TeLLMe_FPGA_2026) is valuable for reproduction planning.

[TerEffic][H09] requires especially careful interpretation. The inspected v2 uses MatMul-free recurrent models rather than ordinary attention-based decoders. Its fully on-chip 370M configuration spans two U280 cards and reports 16,300 tokens/s. Decoder-layer scope differs from complete generation. This is a strong specialized co-design result, not evidence that a standard transformer of similar parameter count will achieve comparable speed on KR260.

### 3.4 Hardware evidence matrix

| Work | Closest workload/platform | Transferable idea | Critical comparison limit |
|---|---|---|---|
| [FQ-BERT][H02] | Embedded BERT | Quantize the whole operator path | Architecture/model quality must match |
| [Spatial study][H03] | U280 BERT/GPT2 | Resource-aware spatial/temporal choice | Larger device; model-specific design |
| [FlightLLM][H04] | HBM generative FPGA | Layout, sparse execution, compilation | Compression and platform differ |
| [EdgeLLM][H05] | VCU128 CPU/FPGA | Fusion and overlap | HBM board |
| [Embedded KV260 decoder][H06] | LLaMA2-7B decode | Weight/KV packing and traffic efficiency | Bare metal, memory nearly full |
| [TeLLMe v2][H08] | KV260 BitNet prefill/decode | Lookup matmul, URAM, distinct phases | Native ternary model, finite workloads |
| [TerEffic v2][H09] | U280 recurrent ternary models | Model/hardware specialization | Different model family and multi-card case |
| [LUT-LLM][H10] | V80 lookup-based Qwen | Vector quantization | High-end board; some simulated comparisons |

None of these inspected acceleration results establishes all of edge deployment, full-service hard timing, semantic correctness, and output type safety together.

## 4. Quantization and model design

### 4.1 An arithmetic contract is more useful than an “INT8” label

[I-BERT][Q01] demonstrates integer-only approximations for GELU, softmax, and layer normalization. It is a key numerical reference for this project's all-integer encoder. Adopting an approximation still requires specifying scaling, rounding, saturation, and intermediate widths; “integer-only” does not imply bitwise equivalence to another integer implementation.

[SmoothQuant][Q02] moves activation outlier difficulty into weight scaling to enable W8A8 matrix products. It is relevant when widening or changing the encoder causes activation-range problems. It should be evaluated against the current calibration procedure rather than adopted solely because it works on large decoders.

[GPTQ][Q03] uses approximate second-order information for low-bit weight quantization. [AWQ][Q04] protects salient channels using activation statistics. Both are important decoder baselines, but weight-only quantization retains different activation arithmetic from the current INT8 datapath. Packed weights, group scales, bias semantics, and dequantization placement are architectural requirements.

**Project recommendation:** represent a tensor by at least its shape, signedness, storage width, accumulator width, scale interpretation, rounding rule, clipping rule, and layout. A checkpoint is compatible only if every operator can realize those semantics. A label such as W4A8 omits too much to be a deployment interface.

### 4.2 Ternary research supports a trained model family

[BitNet b1.58][Q05] motivates native ternary linear weights and dedicated hardware. The [2B4T report][Q06] supplies a trained 2B-scale model and released inference implementations. This does not establish that arbitrary pretrained weights can be rounded to ternary without quality loss, or that every tensor in the full model occupies 1.58 bits.

[T-MAC][Q07] is an essential adjacent CPU baseline: lookup-based low-bit matrix products avoid repeatedly expanding weights into high precision. Test an appropriate lookup CPU kernel when evaluating a ternary FPGA path; the ARM baseline should not be limited to a generic framework.

The project's v1 ternary experiment does not settle the prospects of native ternary transformer models. Its documented pooling-resolution problem and residual quality loss concern a different architecture, training regime, and task. Conversely, strong BitNet results do not resolve the project's domain-specific negation and slot errors.

### 4.3 Distillation is already part of the project's strongest results

[MiniLM][M01] distills attention relationships into smaller encoders. [TinyBERT][M02] combines general and task-specific distillation. They support the current strategy of acquiring pretrained knowledge in a small student rather than treating parameter capacity alone as the objective.

[FastText.zip][M03] is relevant to the compact v1 classifier and compressed feature models. Such a classifier can remain a useful baseline or bounded fallback even as the primary encoder grows.

[Qwen3][M04] provides context for the existing 0.6B generation baseline and configurable reasoning behavior. Its family-level results cannot substitute for task evaluation of the exact quantized checkpoint used on the board.

**Project recommendation:** optimize a Pareto frontier over task error, selective risk, deadline budget, memory, and energy. Select model capacity only after those axes are measured. “Fill the DDR” is an allocation target, not a language-capability objective.

## 5. Timing guarantees: where the missing theory lies

### 5.1 Clock closure, cycles, response time, and quality are different

[The WCET survey][T01] treats safe upper-bound analysis as a distinct task from measuring execution times. [Real-Time Calculus][T09] supplies a compositional language for workload arrivals and resource service. These are closer to a hard guarantee than an accelerator speedup table.

For this project, a proposed bound should name its boundary:

1. **Compute-only:** fixed model and shape, assuming operands are available.
2. **FPGA request:** includes bounded memory service and result writes.
3. **Local service:** includes tokenization, heads, validation, and OS scheduling.
4. **External request:** also includes transport and any remote dependency.

A routed design meeting setup/hold establishes operation at a stated clock under its implementation assumptions. It does not establish a request deadline. Exact RTL/Python agreement establishes numerical agreement, not a time bound. A maximum seen in 350 cases remains a measurement.

### 5.2 Memory interference is central to KR260

[PREM][T02] coordinates memory and compute activity to avoid uncontrolled shared-resource contention. [The PRET DRAM controller][T03] provides analytical latency/throughput bounds through bank-oriented isolation. Both show why predictable memory access must be designed explicitly.

[MemGuard][T04] distinguishes guaranteed from best-effort memory bandwidth. Its reclaiming mechanism can compromise delivery after prediction errors; the paper discusses disabling reclaiming for hard real-time tasks. It is a useful conceptual reference, not a drop-in proof for ARM/PL traffic through the KR260 controller.

The immediate research questions are:

- Which masters can contend with the PL port, and which can be bounded or disabled?
- What bounds exist on arbitration, refresh, read/write turnarounds, burst queues, and completion?
- Can CPU traffic be regulated without leaving peripheral DMA unaccounted for?
- Is a dedicated memory window, controlled boot profile, or alternative controller feasible?
- What detects and contains a stalled AXI transaction?

A no-map DDR reservation protects address ownership. It does not reserve bandwidth. More outstanding bursts may improve throughput while enlarging queues and blocking. Host polling cannot necessarily recover a CPU stuck in an MMIO transaction; the local link code already documents this limitation.

### 5.3 Modern serving work is useful, with a different guarantee boundary

[Clockwork][T05] builds predictable DNN serving through controlled scheduling and execution choices. Its very high measured SLO attainment is useful evidence for eliminating avoidable variability. It is not an all-input hard WCET proof for a Linux FPGA service.

[Sarathi-Serve][T06] splits prefill into chunks and schedules it around decoding to control generation stalls. This suggests choosing a bounded service quantum for future multi-request generation. A smaller chunk also introduces overhead; its appropriate size depends on the hardware and deadline.

[TimeBill][T07], AAAI 2026, predicts response length and execution time, then adjusts KV eviction to fit a time budget. Prediction-driven budget management is useful, but its predictor and quality changes require error analysis. It is not evidence that our DDR or Linux path has bounded service.

[JITServe][T08], NSDI 2026, supports diverse request SLOs and offers a goodput competitiveness guarantee under its scheduling model. The inspected theorem bounds goodput relative to an oracle. It does not say every admitted request completes on time on arbitrary hardware. This is a particularly useful example of reading the precise theorem behind “provable guarantees.”

### 5.4 A conservative contract to investigate

The following is a proposed project model, not a proven bound:

```text
C_encoder_bound(model, n)
    = C_control_compute_bound(model, n)
    + C_memory_wait_bound(model, n)

T_local_bound
    = T_admission_queue_bound
    + T_tokenize_bound
    + C_encoder_bound / f_min
    + T_heads_bound
    + T_validate_serialize_bound
```

Bounded memory wait must be derived from a service/arbitration model covering the actual traffic pattern. Average bytes divided by measured bandwidth cannot be substituted. Summing compute and memory worst cases is a conservative starting point only when the terms correctly cover all operations; a tighter pipelined analysis must account for dependencies and overlap.

For generation, bound prompt length, context length, output length, and auxiliary work:

```text
T_generation_bound
    <= T_prefill_bound(N_max)
       + sum(T_decode_step_bound(N_max + i), i = 0..K_max-1)
       + T_constraint_engine_bound
       + T_result_handling_bound
```

This only helps after every term has a justified bound and queue/host costs are included at the chosen boundary. A token cap bounds iteration count, not semantic completion. An answer can be truncated in a nonaccepting grammar state.

Admission should check sufficient budget before starting. For a single nonpreemptive engine, a simple FIFO proof must include all bounded jobs ahead and any job already executing. More sophisticated scheduling is useful only if its preemption, interference, and execution assumptions match the design.

**Two distinct outcomes should be specified:** useful inference completes by the deadline; or a bounded independent mechanism emits an explicit failure/fallback by the deadline. Guaranteeing the latter does not guarantee successful model completion. A watchdog sharing the blocked path may fail to provide either guarantee.

## 6. Reliability: numerical, statistical, semantic, and physical

### 6.1 Numerical reliability is an existing strength

The current integer reference, byte-image executor, RTL tests, readback, and board comparisons are a sound empirical foundation. They establish implementation agreement for tested workloads. Expand that evidence with boundary values, extreme dimensions, malformed descriptors, saturation/overflow cases, and invalid control sequences.

Verification should distinguish compiler correctness, image correctness, arithmetic correctness, protocol correctness, and deployment configuration. Shared calibration logic can create common-mode mistakes even when two execution paths agree. A third check using simple mathematical bounds is useful for accumulator widths and address spans.

**Recommendation:** derive accumulator bounds before allocating widths. For a dot product of length k with bounded signed operands, start from k times the maximum absolute product, add bias and any extra terms, then include rounding intermediates. Saturating after overflow is too late.

### 6.2 Confidence and rejection need explicit risk definitions

[Guo et al.][R01] motivates temperature scaling for calibration. [SelectiveNet][R02] jointly learns prediction and rejection, improving the risk/coverage tradeoff on its benchmarks. Calibration and selective prediction are related but distinct: good average calibration does not establish low error among accepted outputs.

[CLINC150][R11] was designed for intent and out-of-scope evaluation. Its OOS task is directly relevant, but its distribution is not the same as electronics commands, negated instructions, conflicting dialogue state, or arbitrary deployment traffic.

For the project, report accepted error, coverage, OOS false acceptance, missing-slot errors, and negation errors separately. Thresholds and temperatures should be selected on held-out calibration data from the **deployed quantized pipeline**. Test data should assess the chosen rule once.

[Conformal Risk Control][R03] supplies finite-sample control for suitable loss families under stated statistical assumptions. A selective error rate is a ratio and need not satisfy the original monotone-loss setup. Choose a method whose theorem matches the proposed accepted-risk quantity; do not simply apply a conformal threshold and inherit a guarantee.

[Conformal factuality][R04] backs off specificity to obtain probabilistic correctness guarantees using calibration. This is useful for bounded answers that can be weakened or refused. It does not provide per-input certainty or protection against arbitrary distribution shifts.

**Recommendation:** store the risk claim with its population, calibration split, loss, target, uncertainty level where applicable, and drift assumptions. Statistical guarantee metadata belongs beside model and clock metadata.

### 6.3 Grounding helps, but evidence quality matters

[RAG][R05] combines a language model with retrieved external memory. [Evidentiality-guided generation][R06] addresses the fact that retrieved passages may be irrelevant or insufficient. Together they motivate an encoder serving as a retrieval/reranking component for local documentation.

A useful bounded design is a fixed local corpus, bounded candidates, bounded passage lengths, and an explicit unsupported-answer outcome. Evaluate evidence retrieval and answer correctness independently. A source identifier attached to a statement is not proof that the statement follows from that source.

For structured commands, an even stronger boundary is a deterministic validator over domain state: device identity exists, units are consistent, values fall within permitted ranges, required parameters are present, and conflicting instructions lead to clarification. Correctness relative to the user's meaning remains an empirical semantic question.

### 6.4 Runtime assurance is an adjacent architectural foundation

[Neural Simplex][R07] places an advanced neural controller beside a baseline controller and decision mechanism under explicit safety assumptions. The useful pattern here is a separately justified guard and fallback around language-model proposals. The continuous-control results do not automatically transfer to natural-language understanding.

For System One, model outputs could be proposals that enter a typed validator. Execution or rejection is a separate decision. A fallback should have declared behavior and a bounded path; it cannot obtain safety merely by being smaller.

### 6.5 Bit-exactness does not address physical faults

[Algorithm-Based Fault Tolerance][R08] uses encoded matrix computations/checksums for fault detection and correction under its fault model. It suggests protecting expensive linear operations with cheaper checks. Integer saturation and requantization are nonlinear, so checksum identities must be validated at an appropriate arithmetic boundary.

[GoldenTransformer][R09] offers software fault injection for weights, activations, and attention. Its logical fault model helps prioritize experiments but does not replace physical/RTL fault characterization.

[Rotated Robustness][R10], a 2026 preprint, studies rotations against bit-flip sensitivity in quantized models. Treat its reported robustness as model- and fault-specific. Algebraic equivalence in real arithmetic does not by itself preserve the project's finite-width integer behavior.

A first practical campaign should inject errors into model bytes, scales, descriptors, address/control fields, activations, and result status. Measure silent wrong outputs, detected errors, safe rejection, hang behavior, and detection latency. Include the availability cost of checks and any permitted retry in the timing contract.

## 7. Type safety: three distinct research paths

### 7.1 Structured outputs and grammar-constrained decoding

[PICARD][Y01] rejects inadmissible tokens through incremental parsing for SQL. [Synchromesh][Y02] goes beyond grammar with constrained semantic decoding, including scope, typing, and domain/context restrictions. [LMQL][Y03] treats prompting as programming, compiling control flow and constraints into inference procedures.

[DOMINO][Y04] addresses subword alignment when enforcing constraints. Tokens can cross grammar boundaries, so character-level validity cannot be naively mapped to a token mask.

[XGrammar][Y05] uses precomputation, persistent parser state, and overlap to reduce grammar overhead. [XGrammar 2][Y06], from 2026, adds dynamic structured-generation machinery, JIT compilation, and shared caching. These are valuable software references; near-zero measured overhead on a GPU service is not a WCET bound for an ARM grammar engine.

[Grammar-Aligned Decoding][Y08] shows that ordinary token masking can distort the conditional language-model distribution. Format correctness and output quality should therefore both be evaluated after constraints are enabled.

**Project recommendation:** use a small, fixed output language first. A bounded action record with enums, device identifiers, required fields, and bounded numeric/string domains is easier to validate and time than general code. Precompile constraint structures where feasible, bound parser state, and define explicit failure for incomplete outputs.

### 7.2 Actual typing constraints

[Type-Constrained Code Generation][Y07], PLDI 2025, is the strongest direct type-safety anchor. It uses prefix automata, type inference, and search over inhabitable types. Its formal core establishes that accepted prefixes can be completed to well-typed expressions; practical pruning can be incomplete. The TypeScript implementation has a supported feature boundary. This establishes typing properties, not arbitrary program correctness or termination.

For this project, type safety can be achieved earlier without generation: a classifier or semantic parser selects a finite action constructor and supplies validated arguments. A deterministic serializer produces the external representation. This removes syntax generation from the critical path while leaving semantic prediction error to evaluate.

A proposed result type is:

```text
InferenceResult =
    Accepted(ValidatedIntentOrAction, ModelIdentity, TimingEvidence)
  | Clarify(MissingOrAmbiguousFields)
  | Abstain(RiskOrScopeReason)
  | DeadlineExceeded
  | InvalidInput
  | HardwareFault
```

This is a design proposal. A declaration alone supplies no guarantee. The checked constructors, serialization, consumer behavior, and hardware/host error mapping must enforce it. Confidence is evidence attached to a result; it is not authority to bypass validation.

### 7.3 Type-safe accelerator and model compilation

[Dahlia][C03] uses time-sensitive affine types to prevent conflicting consumption of hardware resources. It is particularly relevant to memory-port use and banking. Its predictable-compilation objective should not be confused with closed-form full-service WCET.

[Calyx][C04] separates structural hardware and control flow in an intermediate representation. [Allo][C05] composes hardware customizations in a type-safe manner. [Relay][C06] provides a statically typed tensor IR. These works support making shapes, layouts, resource use, and execution structure explicit at compile time.

The existing image compiler is already a valuable boundary for such checks. A proposed compiler-side contract could reject:

- hidden, head, FFN, token, and row dimensions outside hardware capacities;
- tensors whose scale/layout contracts do not match the consuming instruction;
- memory spans or alignment incompatible with the selected board ABI;
- unsupported address widths or opcodes;
- unbounded or structurally invalid programs;
- output records incompatible with task schemas.

A schema checker establishes conformance to those declarations, not semantic correctness of the language model. Compiler-side checks also need a runtime trust boundary: corrupted images or externally written descriptors cannot be assumed to have passed the compiler.

## 8. Adjacent directions worth tracking

### 8.1 IO-aware attention and KV management

[FlashAttention][A01] reduces attention IO through tiling and online softmax. The transferable idea is to optimize memory movement and locality, rather than counting MACs alone. Changing reduction order or softmax scaling requires re-establishing the integer reference.

[PagedAttention][A02] addresses dynamic KV fragmentation and sharing for high-throughput serving. For a small bounded service, fixed reservation can be easier to analyze. Paging is useful when utilization matters enough to justify translation, allocation, and reclamation behavior in the timing model.

### 8.2 Speculation and program-aware serving

[Speculative decoding][A03] preserves the target sampling distribution under its algorithm while accelerating typical generation. Low acceptance creates a relevant worst case: account for draft, verification, and recovery work. Mean speedup alone should not be credited in a hard deadline budget.

[SGLang][A04] exploits structured multi-call programs and shared prefixes for efficiency. It is relevant if the service grows into retrieval, constrained generation, and repeated dialogue calls. Dynamic reuse introduces cache state that must be bounded or isolated before claiming predictable timing.

### 8.3 State-space and recurrent alternatives

[Mamba][M05] supplies selective state-space sequence modeling. [MatMul-free language modeling][M06] explores ternary/recurrent computation, and [LightMamba][M07] co-designs low-bit quantization with FPGA scheduling.

These are useful alternatives when growing KV state or long-context cost dominates. They require different operators, numerical references, training/checkpoint support, and language-quality comparisons. A fixed-size recurrent state may simplify a memory budget, but does not prove task reliability or real-time service.

### 8.4 Earlier FPGA inference toolflows

[FINN][C01] demonstrates streaming low-precision FPGA inference with resource allocation per layer. [hls4ml][C02] arises from particle-physics trigger inference with stringent latency requirements. Their networks are much smaller than modern LLMs, but they offer relevant practices for precision/resource/latency co-design and controlled hardware execution.

## 9. Research gaps and a defensible contribution

The reviewed literature supports five hypotheses to investigate. These are opportunities inferred from the selected works; a targeted follow-up novelty search is still required before a publication priority claim.

| Hypothesis | Existing foundations | Evidence needed for System One |
|---|---|---|
| A small encoder can offer useful typed language decisions with bounded latency | Integer BERT, distillation, resource typing | Quality/risk frontier and full declared timing model |
| A deployment image can carry checked numerical, dimensional, memory, and timing contracts | Relay, Dahlia, Calyx, Allo | Validator coverage, runtime boundary, proof assumptions |
| Reliable rejection can be composed with deadline/fault outcomes | Selective prediction, conformal methods, runtime assurance | Appropriate risk theorem and bounded rejection/failure path |
| Quantization can be optimized for decision reliability | I-BERT, SmoothQuant, AWQ/GPTQ | Negation/slots/calibration/OOS evaluation after quantization |
| Grammar and type constraints can be co-designed with small FPGA generation | PICARD, Synchromesh, type-constrained generation, XGrammar | Bounded constraint state/work and complete-output semantics |

A plausible research question is:

> Under a declared workload and interference envelope, how much useful language coverage can a modest FPGA SoC deliver while enforcing numerical implementation fidelity, bounded response behavior, and typed output validity?

The outcome variable is not simply tokens/s. A proposed experimental metric is **correct, validated, on-time decisions per joule**, reported alongside coverage and the type of timing assurance. This is a project-specific metric proposal, not an established benchmark. Do not hide abstentions, deadline failures, or incomplete generation in its denominator.

### An honest claim ladder

| Stage | Claim that evidence could support |
|---|---|
| Current | Hardware and integer references agree on tested encoder workloads; timing is measured |
| Checked deployment | Supported images/descriptors satisfy specified structural contracts |
| Predictable operation | Timing variability is characterized under declared stress conditions |
| Bounded accelerator | A safe request bound follows from control and memory assumptions |
| Bounded local service | Host, queue, heads, validation, and fault response are included |
| Statistically controlled decisions | A specific risk/coverage guarantee holds under its sampling assumptions |
| Composed service | Each accepted result or defined failure meets the declared timing/output contract |

Move between stages only when the corresponding evidence is available. Neither a newer checkpoint nor a higher clock closes all gaps.

## 10. Recommended experiments and work order

These recommendations synthesize the literature with the repository state. They are a research agenda, not changes performed by this review.

### Step 1: freeze a trustworthy experimental baseline

Pin checkpoint, calibration, image, bitstream, build configuration, actual clock, tokenization, head execution location, and evaluation split. Preserve the 350-case suite for implementation regression, then use substantially broader held-out samples for quality/risk estimates.

Define deadlines per model, maximum lengths, and service profile. Specify whether startup, transport, heads, and validation count. Retain the established 384-wide pipeline as the baseline while the 768-wide memory candidate is qualified.

### Step 2: instrument the bottleneck needed for timing analysis

Count weight/activation bytes, accepted AXI beats, burst counts, service gaps, queue occupancy, loader backpressure, and engine idle causes. Sweep input lengths and stress CPU/peripheral memory traffic, OS scheduling, cache state, and cold/warm model conditions.

Use stress results to discover omitted mechanisms and validate a model. They do not turn an observed maximum into WCET. Record any unmodeled dependency explicitly.

### Step 3: make the image and request contract checkable

Build a declaration/validator around shape, opcode, arithmetic, region, alignment, and board-ABI restrictions. Include address widths beyond the external AXI bus: the local image and descriptor ABI currently constrain usable addresses.

Demonstrate rejection of malformed/corrupted inputs and prove or test that invalid inputs cannot launch unchecked memory operations. Tie model/bitstream identity to the validated contract.

### Step 4: add typed results and evaluate rejection

Start with intent/slots and a small domain command schema. Test valid commands, OOS inputs, missing fields, negation, ambiguous references, conflicting turns, unit mismatches, and adversarial near-neighbor phrasing.

Report full coverage/risk curves for each quantized model, rather than a single selected confidence threshold. Obtain enough accepted examples to quantify rare error uncertainty. Repeated variants of the same utterance should not be treated as independent evidence.

### Step 5: establish a restricted timing profile

First target a narrow workload and environment where shared traffic can be bounded. Derive the accelerator bound, then extend the boundary to host processing. Add admission control and an independently effective timeout/failure path.

If the platform cannot supply a defensible memory-service bound, publish measured performance and bounded failure behavior with that limitation. Do not relabel them as hard inference completion.

### Step 6: evaluate a small decoder as a separate architecture

Use TeLLMe and the embedded KV260 decoder as direct references. Implement a decoder numerical specification before RTL: causal/GQA semantics as applicable, RoPE, RMSNorm, gated FFN, weight format, KV layout, and logits/head behavior.

Compare a conventional low-bit checkpoint with a native ternary option under matched task-quality requirements. Bound prompt, context, output, and constraint work. Include ARM head/grammar time and incomplete-output handling.

### Step 7: fault and composition experiments

Inject byte/control/activation errors and stalled responses; verify detection, containment, reset, and stale-result rejection. Measure the extra cycles and risk impact of checks.

Test the composed service under overload, queue saturation, DDR interference, quantization shifts, malformed inputs, and model updates. A bounded result protocol must not convert a late success into an accepted on-time result.

### Minimum experiment table

| Dimension | Required comparison | Key output |
|---|---|---|
| Implementation | Float, integer reference, image executor, RTL, board | Decision/logit/state differences |
| Quality | Model/precision at matched tasks | Accuracy, slots, negation, OOS |
| Rejection | Threshold/calibration variants | Coverage, accepted risk, false acceptance |
| Timing | Length/model/interference profiles | Stage latencies, empirical tails, analytic bound separately |
| Resources | Working and candidate bitstreams | Routed area, clock, buffers, sustained traffic |
| Energy | Matched board/CPU work | Joules/request, idle and active boundary |
| Types | With/without validators | Invalid/incomplete/ill-typed outputs and rejection |
| Faults | Declared injected fault classes | SDC, detection, containment, bounded failure |

For whole-board energy, state whether power includes PS, DDR, FPGA, peripherals, and idle baseline. Keep Vivado estimates separate from external measurements. A MAC is one product-accumulation; do not silently switch to a two-operation convention when comparing throughput.

## 11. Reading sequence

The following order gives the best return for the current project:

1. **Encoder arithmetic:** [FQ-BERT][H02], [I-BERT][Q01], [MiniLM][M01].
2. **Closest decoder hardware:** [TeLLMe v2][H08], [embedded KV260 decoder][H06]; inspect their model and host boundaries.
3. **Memory and timing:** [WCET survey][T01], [PREM][T02], [MemGuard][T04], [PRET DRAM][T03].
4. **Typed interfaces:** [Synchromesh][Y02], [Type-Constrained Code Generation][Y07], [Dahlia][C03].
5. **Reliable decisions:** [calibration][R01], [SelectiveNet][R02], [Conformal Risk Control][R03].
6. **Larger-system ideas:** [FlightLLM][H04], [LUT-LLM][H10], [JITServe][T08], [XGrammar 2][Y06].

The key deliverable to aim for is a **contract whose assumptions, enforcement, failure behavior, and evidence are independently inspectable**. The accelerator, model, compiler, and runtime should each state which part of that contract they establish.

## 12. Source index and reuse

The companion [JSON registry](2026-10-11-edge-language-models-sources.json) records primary URLs, topic areas, years, abbreviated authors, and inspection level. The [BibTeX file](2026-10-11-edge-language-models.bib) is a starter bibliography with stable keys matching this review. It intentionally omits unverified publication metadata; preprints are not silently promoted to peer-reviewed publications. TeLLMe v2's FPGA 2026 DOI is additionally noted in the bibliography.

Links below resolve the paper citations used throughout this review.

[H01]: https://arxiv.org/abs/2007.08563 "FTRANS: Energy-Efficient Acceleration of Transformers using FPGA"
[H02]: https://arxiv.org/abs/2103.02800 "Hardware Acceleration of Fully Quantized BERT for Efficient Natural Language Processing"
[H03]: https://arxiv.org/abs/2312.15159 "Understanding the Potential of FPGA-Based Spatial Acceleration for Large Language Model Inference"
[H04]: https://arxiv.org/html/2401.03868v2 "FlightLLM: Efficient Large Language Model Inference with a Complete Mapping Flow on FPGAs"
[H05]: https://arxiv.org/abs/2407.21325 "EdgeLLM: A Highly Efficient CPU-FPGA Heterogeneous Edge Accelerator for Large Language Models"
[H06]: https://arxiv.org/html/2502.10659v1 "Pushing up to the Limit of Memory Bandwidth and Capacity Utilization for Efficient LLM Decoding on Embedded FPGA"
[H07]: https://arxiv.org/abs/2504.16266 "TeLLMe: An Energy-Efficient Ternary LLM Accelerator for Prefilling and Decoding on Edge FPGAs"
[H08]: https://arxiv.org/html/2510.15926v2 "TeLLMe v2: An Efficient End-to-End Ternary LLM Prefill and Decode Accelerator with Table-Lookup Matmul on Edge FPGAs"
[H09]: https://arxiv.org/html/2502.16473v2 "TerEffic: Highly Efficient Ternary LLM Inference on FPGA"
[H10]: https://arxiv.org/html/2511.06174v2 "LUT-LLM: Efficient Language Model Inference with Memory-based Computations on FPGAs"
[H11]: https://arxiv.org/abs/2505.08981 "ITERA-LLM: Boosting Sub-8-Bit Large Language Model Inference via Iterative Tensor Decomposition"
[H12]: https://arxiv.org/abs/2409.14023 "FAMOUS: Flexible Accelerator for the Attention Mechanism of Transformer on UltraScale+ FPGAs"
[Q01]: https://proceedings.mlr.press/v139/kim21d/kim21d.pdf "I-BERT: Integer-only BERT Quantization"
[Q02]: https://arxiv.org/abs/2211.10438 "SmoothQuant: Accurate and Efficient Post-Training Quantization for Large Language Models"
[Q03]: https://arxiv.org/abs/2210.17323 "GPTQ: Accurate Post-Training Quantization for Generative Pre-trained Transformers"
[Q04]: https://arxiv.org/abs/2306.00978 "AWQ: Activation-aware Weight Quantization for LLM Compression and Acceleration"
[Q05]: https://arxiv.org/abs/2402.17764 "The Era of 1-bit LLMs: All Large Language Models are in 1.58 Bits"
[Q06]: https://arxiv.org/abs/2504.12285 "BitNet b1.58 2B4T Technical Report"
[Q07]: https://arxiv.org/abs/2407.00088 "T-MAC: CPU Renaissance via Table Lookup for Low-Bit LLM Deployment on Edge"
[M01]: https://arxiv.org/abs/2002.10957 "MiniLM: Deep Self-Attention Distillation for Task-Agnostic Compression of Pre-Trained Transformers"
[M02]: https://arxiv.org/abs/1909.10351 "TinyBERT: Distilling BERT for Natural Language Understanding"
[M03]: https://arxiv.org/abs/1612.03651 "FastText.zip: Compressing text classification models"
[M04]: https://arxiv.org/abs/2505.09388 "Qwen3 Technical Report"
[M05]: https://arxiv.org/abs/2312.00752 "Mamba: Linear-Time Sequence Modeling with Selective State Spaces"
[M06]: https://arxiv.org/abs/2406.02528 "Scalable MatMul-free Language Modeling"
[M07]: https://arxiv.org/abs/2502.15260 "LightMamba: Efficient Mamba Acceleration on FPGA with Quantization and Hardware Co-design"
[T01]: https://www.es.mdh.se/pdf_publications/1258.pdf "The worst-case execution-time problem: overview of methods and survey of tools"
[T02]: https://ieeexplore.ieee.org/document/5767117 "A Predictable Execution Model for COTS-Based Embedded Systems"
[T03]: https://ieeexplore.ieee.org/document/6062323/ "PRET DRAM controller: Bank privatization for predictability and temporal isolation"
[T04]: https://www.ittc.ku.edu/~heechul/papers/memguard-rtas13.pdf "MemGuard: Memory Bandwidth Reservation System for Efficient Performance Isolation in Multi-core Platforms"
[T05]: https://www.usenix.org/conference/osdi20/presentation/gujarati "Serving DNNs like Clockwork: Performance Predictability from the Bottom Up"
[T06]: https://www.usenix.org/conference/osdi24/presentation/agrawal "Taming Throughput-Latency Tradeoff in LLM Inference with Sarathi-Serve"
[T07]: https://ojs.aaai.org/index.php/AAAI/article/view/40317 "TimeBill: Time-Budgeted Inference for Large Language Models"
[T08]: https://www.usenix.org/conference/nsdi26/presentation/zhang-wei "JITServe: SLO-aware LLM Serving with Imprecise Request Information"
[T09]: https://www.tik.ee.ethz.ch/file/994e3fb9a12a2471eb73d0d30a4317d3/scheduling.pdf "Real-Time Calculus for Scheduling Hard Real-Time Systems"
[R01]: https://proceedings.mlr.press/v70/guo17a.html "On Calibration of Modern Neural Networks"
[R02]: https://proceedings.mlr.press/v97/geifman19a.html "SelectiveNet: A Deep Neural Network with an Integrated Reject Option"
[R03]: https://arxiv.org/abs/2208.02814 "Conformal Risk Control"
[R04]: https://arxiv.org/abs/2402.10978 "Language Models with Conformal Factuality Guarantees"
[R05]: https://arxiv.org/abs/2005.11401 "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"
[R06]: https://arxiv.org/abs/2112.08688 "Evidentiality-guided Generation for Knowledge-Intensive NLP Tasks"
[R07]: https://arxiv.org/abs/1908.00528 "Neural Simplex Architecture"
[R08]: https://graal.ens-lyon.fr/~abenoit/CR02/papers/abft2.pdf "Algorithm-Based Fault Tolerance for Matrix Operations"
[R09]: https://arxiv.org/abs/2509.10790 "GoldenTransformer: A Modular Fault Injection Framework for Transformer Robustness Research"
[R10]: https://arxiv.org/abs/2603.16382 "Rotated Robustness: A Training-Free Defense against Bit-Flip Attacks on Large Language Models"
[R11]: https://aclanthology.org/D19-1131/ "An Evaluation Dataset for Intent Classification and Out-of-Scope Prediction"
[Y01]: https://aclanthology.org/2021.emnlp-main.779/ "PICARD: Parsing Incrementally for Constrained Auto-Regressive Decoding from Language Models"
[Y02]: https://arxiv.org/abs/2201.11227 "Synchromesh: Reliable code generation from pre-trained language models"
[Y03]: https://arxiv.org/abs/2212.06094 "Prompting Is Programming: A Query Language for Large Language Models"
[Y04]: https://arxiv.org/abs/2403.06988 "Guiding LLMs The Right Way: Fast, Non-Invasive Constrained Generation"
[Y05]: https://arxiv.org/abs/2411.15100 "XGrammar: Flexible and Efficient Structured Generation Engine for Large Language Models"
[Y06]: https://arxiv.org/abs/2601.04426 "XGrammar 2: Dynamic and Efficient Structured Generation Engine for Agentic LLMs"
[Y07]: https://arxiv.org/pdf/2504.09246 "Type-Constrained Code Generation with Language Models"
[Y08]: https://arxiv.org/abs/2405.21047 "Grammar-Aligned Decoding"
[C01]: https://arxiv.org/abs/1612.07119 "FINN: A Framework for Fast, Scalable Binarized Neural Network Inference"
[C02]: https://arxiv.org/abs/1804.06913 "Fast inference of deep neural networks in FPGAs for particle physics"
[C03]: https://arxiv.org/abs/2004.04852 "Predictable Accelerator Design with Time-Sensitive Affine Types"
[C04]: https://arxiv.org/abs/2102.09713 "A Compiler Infrastructure for Accelerator Generators"
[C05]: https://arxiv.org/abs/2404.04815 "Allo: A Programming Model for Composable Accelerator Design"
[C06]: https://arxiv.org/abs/1904.08368 "Relay: A High-Level Compiler for Deep Learning"
[A01]: https://arxiv.org/abs/2205.14135 "FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness"
[A02]: https://arxiv.org/abs/2309.06180 "Efficient Memory Management for Large Language Model Serving with PagedAttention"
[A03]: https://proceedings.mlr.press/v202/leviathan23a.html "Fast Inference from Transformers via Speculative Decoding"
[A04]: https://arxiv.org/abs/2312.07104 "SGLang: Efficient Execution of Structured Language Model Programs"
