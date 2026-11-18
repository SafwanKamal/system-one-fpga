# What System One should build: encoder versus small generator on KR260

Research date: 2026-10-17. Recommendation and experiment design, not a new implementation or benchmark. Primary papers, official model documentation/configurations and author artifacts were inspected; individual evidence levels are recorded in [the source registry](2026-10-17-encoder-vs-generator-sources.json). No board commands, model downloads, training, PL changes, JTAG operations, paid compute or deployments were performed for this review. The calibrated R5 deployment remains the working baseline.

## Decision

Build a **local language-to-maintenance-command compiler on KR260**, with a finite API, explicit clarification/rejection, and a hardware-controlled result endpoint. Its model must interpret arguments, negation, context and bounded command composition; merely selecting an intent is insufficient.

Use an **encoder-first implementation with a generative challenger**:

1. Fine-tune a stronger encoder on this actual task. Evaluate ModernBERT-base as the modern quality reference; evaluate a BERT-base-shaped model and a teacher-distilled student as practical hardware candidates.
2. Fine-tune FunctionGemma 270M on the identical task and compare full command correctness. Keep Qwen3-0.6B in non-thinking mode as an optional second generative reference, not the first hardware target.
3. Choose the first new FPGA compute implementation from measured quality, risk, memory and latency. A generator must earn its additional hardware work through better command capability. A hybrid is a subsequent ablation, not the assumed solution.
4. Make the research contribution a **schema-derived execution/result contract**, evaluated across both model families. The contract connects a bounded command language, maximum model work/state, result identity, validation, deadlines and failure authority. Individual components have prior art; novelty is an experimentally testable hypothesis about this specific co-design.

Do not first build the largest model that fits, a generic chatbot, an arbitrary-JSON decoder, an unqualified 300MHz successor, or a two-model hardware cascade. Those choices add substantial work before establishing the application's advantage.

## Useful application and first capability target

The application is a maintenance console for a small industrial cell or inspection robot. The first endpoint produces proposals for a simulator/test consumer, not direct motor actuation. Example:

> Read motor M7's temperature; if it exceeds 70 degrees Celsius, create a high-priority work order.

The desired output is a bounded typed plan containing a sensor read, a threshold predicate with explicit units, and a work-order action. Missing identity, contradictory conditions, insufficient state or unsupported requests yield a structured clarification or rejection. This is a meaningful capability test beyond today's CLINC and slot labels.

Proposed initial scope: 12 catalogued APIs, at most two action nodes and one conditional, bounded asset/sensor identifiers, bounded fixed-point numeric arguments, and at most two dialogue turns. Publish one canonical binary record; software can render JSON afterward. A state snapshot carries an epoch, and the consumer rechecks execution preconditions. Structural checks cannot establish that the model understood the user's meaning.

Both models receive the same task information and catalog access. The encoder predicts action/condition structure, argument spans or enum values, and a clarification decision. The generator emits the same canonical plan using a constrained grammar. Count the entire prompt, schema and state representation in each timing/memory boundary. Begin with requests fitting the deployed encoder's128-token input window; separately evaluate longer cases in software and identify the required RTL extension. Do not attribute a ModernBERT8192-token capability to the present bitstream.

## What current research establishes

| Evidence | Finding | Consequence for this project |
|---|---|---|
| [ModernBERT, ACL2025](https://aclanthology.org/2025.acl-long.127/) and [author model card](https://huggingface.co/answerdotai/ModernBERT-base) | A modern encoder family targets classification and retrieval; base has149M parameters and22layers. | A stronger encoder is a credible quality reference. Existing generic pretraining does not establish our command accuracy. |
| [FunctionGemma overview](https://ai.google.dev/gemma/docs/functiongemma) |270M function-calling specialist intended for task-specific fine-tuning. | Prefer this focused challenger over immediately porting a much larger conversational model. |
| [FunctionGemma model card](https://ai.google.dev/gemma/docs/functiongemma/model_card) | Google reports Mobile Actions improving58% to85% after fine-tuning. Its phone CPU measurements use different hardware. | Measure tuned command execution; do not assume zero-shot competence or transfer phone throughput to KR260. |
| [STAR,2026](https://arxiv.org/html/2602.03022v1) | Studies teacher-assisted training for very small function-calling models. | Specialization and distillation are substantive model work; more parameters are not the only capability lever. |
| [Extending FunctionGemma, September2026](https://arxiv.org/abs/2609.25373) | Authors report gains on a new mobile-action dataset with a cross-dataset specialization tradeoff. | Test unseen compositions and retained generality. This preprint's results are not independent evidence of KR260 performance. |
| [TeLLMe v2](https://arxiv.org/html/2510.15926v2), [author release](https://github.com/UCI-CORSA/TeLLMe_FPGA_2026) | KV260 BitNet0.73B: authors report up to25 decode tokens/s and0.45–0.96s TTFT for64–128-token prompts. Its ternary design includes a CPU vocabulary head. | K26 generation is feasible, but already prior art. The release is a mechanism reference, not a drop-in FunctionGemma design. |
| [Pushing up to the Limit,2025](https://arxiv.org/html/2502.10659v1) | A KV260 design reports4.9 decode tokens/s for4-bit LLaMA2-7B at300MHz, using bare metal. | A7B model fitting4GB does not make it the useful Linux-compatible target. Decode rate excludes a full command-quality comparison. |
| [XGrammar2,2026](https://arxiv.org/abs/2601.04426) | Efficient dynamic structured generation already exists. | Grammar-constrained output is necessary machinery, not sufficient novelty. |
| [ART,2025](https://peipeizhou-eecs.github.io/publication/2025_glsvlsi_art/), [DERCA](https://peipeizhou-eecs.github.io/publication/2025_rtss_clare/2025_rtss_clare.pdf) | Real-time scheduling and preemption on reconfigurable accelerators already have dedicated research. | Do not claim the first real-time FPGA inference accelerator. Distinguish language semantics and result authority from scheduling alone. |

KV260 publications use the same K26 family, but different carrier/software/clock/memory configurations. The KR260 has4GB shared DDR according to [AMD DS988](https://docs.amd.com/r/en-US/ds988-kr260-starter-kit/Product-Details). Published250/300MHz operation, DDR bandwidth, power and throughput are not promises for our200MHz Linux-running design.

## Concrete model and hardware comparison

All model sizes below are approximate. Storage estimates are ideal homogeneous weight payloads, not deployment footprints; quantization scales, mixed-precision weights, padding, buffers and runtime memory add overhead.

| Candidate | What to train/evaluate | Approximate weight payload | Mapping to our current system |
|---|---|---|---|
| Current MiniLM-L12 | Retrain command structure/argument heads; retain calibrated model as regression | Actual image33.9MB | Working R5/PL path; baseline, not a new capability result |
| BERT-base-shaped encoder |12layers,H768,FF3072; task fine-tuning and teacher distillation |110M parameters:110MB W8 or55MB W4 ideal | Most compatible larger encoder family. Head dimension64 matches existing attention limit; larger model/layout/head code still require qualification. |
| ModernBERT-base | Fine-tuned quality reference and possible teacher; direct hardware port only if justified |149M:149MB W8 or74.5MB W4 ideal | H768/head64, but rotary positions, local/global attention and gated feedforward computation need compiler/RTL support. Not a model-file swap. |
| FunctionGemma270M | Fine-tune single/conditional/two-action calls, clarification and rejection |270M:135MB W4 ideal; about270MB W8 before workspaces | Most relevant first generator. Requires head256, decoder attention, KV, normalization/gating, large vocabulary and wider token IDs. |
| Qwen3-0.6B | Optional broader reference in non-thinking mode, trained/evaluated on the same command task |0.6B:300MB W4 ideal | Exceeds current256MiB reservation on nominal weights alone; head128, GQA and sizeable KV require new mapping. Not first choice. |

Model architecture sources: [BERT config](https://huggingface.co/google-bert/bert-base-uncased/raw/main/config.json), [ModernBERT config](https://huggingface.co/answerdotai/ModernBERT-base/raw/main/config.json), [Google Gemma source](https://github.com/google-deepmind/gemma/blob/main/gemma/gm/nn/_gemma.py), [Qwen model card](https://huggingface.co/Qwen/Qwen3-0.6B) and [Qwen config](https://huggingface.co/Qwen/Qwen3-0.6B/raw/main/config.json). The Qwen card and raw config advertise different maximum context values; neither is a proposed operating point here.

### Constraints that a model-size comparison misses

- **Reserved memory is256MiB, not all4GB.** Current token/hidden/mailbox buffers begin near33–36MiB above the model base. A larger image would overlap them unless the manifest, buffers and R5 address table are relocated. A model fitting total RAM is insufficient.
- **Current attention head dimension is capped at64.** BERT-base's64 fits this dimension; FunctionGemma's256 and Qwen's128 do not. Synthetic H1024 checks do not qualify either decoder.
- **Token IDs currently use16bits.** ModernBERT's50,368 vocabulary fits that representation; FunctionGemma's262,144 and Qwen's151,936 require a reviewed32-bit token path or a deliberately retrained/remapped tokenizer. Silently truncating IDs is invalid.
- **R5 firmware is currently specialized toH384 and at most384 classes per job.** It cannot be reused as a dense262k-token vocabulary projection engine. In a production decoder, move substantial matrix work to PL; R5 controls bounded generation and validation. A53/Linux performs provisioning and I/O. An A53-only generator is a separately labelled experimental baseline.
- **KV storage is not the only decoder cost.** Using the published architecture dimensions, a simple FP16 K/V allocation for512 total tokens is about9MiB for18-layer Gemma270M and56MiB for28-layer Qwen0.6B. These are arithmetic sizing estimates, not measured allocations; production layout and local attention can differ.
- **The vocabulary head matters.** Google's [270M release](https://developers.googleblog.com/introducing-gemma-3-270m/) attributes about170M parameters to embeddings and100M to transformer blocks. Small parameter count does not mean a small output projection.
- **Existing latency includes lifecycle overhead.** Our paired baseline was188.5ms median forCLINC and210.0ms forMulti-CLINC; calibration measured188.3/214.5ms. Encoder-only hardware time is much shorter. Measure R5 startup/TCM preparation separately before asserting that a larger encoder or CPU baseline is slower. Persistent service needs bounded recovery, not simply removal of its watchdog.

A useful decoder optimization is to project only grammar-legal vocabulary rows. With identical arithmetic and a complete legal-token set this can preserve dense-mask greedy decisions. However, this idea already appears in [Murali's2025 implementation study](https://gitlostmurali.com/blog/structured-generation-optimizations/) and [Grammar-Conditioned Sparse Projection](https://github.com/StealthEyeLLC/grammar-sparse-projection). The latter is a research prototype with a stated submission target, not evidence of peer-review acceptance. Arbitrary strings can make the legal set broad; bounded enums, numbers and identifiers make a much more tractable first command language. Skipping output work does not remove the full input embedding table or transformer/KV work.

## Comparative capability assessment

| Dimension | Stronger encoder | Small generator |
|---|---|---|
| Fixed APIs, argument extraction | Natural fit with task-specific structure/span heads | Requires sequence training and decoding; can also perform well after specialization |
| Unseen combinations and conditional plans | Possible with explicit structure prediction; must test | A plausible advantage, not established for270M by parameter count or generic benchmarks |
| Newly described API schemas | Requires schema-conditioned training and suitable heads/retrieval | More natural interface, but tiny models can fail on unseen schemas |
| Output length and work | One bounded pass plus a small structured decoder | Prefill plus sequential output steps, KV, grammar and vocabulary selection |
| Engineering risk here | Moderate for compatible BERT family; higher for direct ModernBERT | High: multiple new operators/state paths and new numerical reference |
| How it can win | Better exact commands per joule/deadline, useful coverage, lower integration cost | Better semantic coverage/composition at acceptable error, latency and memory |

No current evidence establishes the winner on our proposed task. Google reports specialization effects, and2026 papers show compact function calling is active research; these do not substitute for the same-input comparison we need. [PORTS](https://arxiv.org/abs/2607.05441) also studies encoder-based tool selection; selecting a tool alone should not be presented as a novel complete command compiler.

## A contribution with a defensible novelty boundary

**Research question:** Can an API-schema-derived execution/result contract improve the number of semantically correct, validated, on-time commands produced per joule on a Linux-running K26 system, across an encoder and a small generative parser?

The concrete artifact is a small compiler/checker that binds:

1. A bounded command AST and canonical response variants to a model, tokenizer, quantization and schema version.
2. Maximum input/output length, argument counts, KV bytes and per-grammar-state vocabulary work. Reject an image whose declared workspace or grammar exceeds the supported profile.
3. A checked work profile and admission policy. A measured profile initially supports empirical SLOs, not successful-inference WCET.
4. An independent PL result register with request/session/schema identity, atomic proposal/commit, deadline outcome, late-result rejection and quarantine/recovery behavior.
5. A matching evaluation record separating semantic correctness, structural validity, accepted coverage, rejected commands and timing failures.

The proposed new element is the **implemented schema-to-resource/result contract and its measured quality/energy/timing consequences across model families**. Neither a larger encoder, fine-tuned small function caller, grammar filter, model router, watchdog nor their unexamined assembly is a novelty claim. [RouteLLM](https://arxiv.org/abs/2406.18665) already establishes model routing; [KnowNo](https://arxiv.org/abs/2307.01928) establishes uncertainty-aware clarification with statistical assumptions; [FPGA stream monitoring](https://finkbeiner.groups.cispa.de/publications/emsoft19.pdf) precedes our independent monitor.

There is also direct conceptual overlap with the public [Deadline-Typed Inference proposal](https://github.com/Ewo8om3/deadline-typed-inference), whose author labels it a concept architecture, first public editionJuly2026. It must be cited as an overlapping concept, not treated as measured silicon or silently ignored. Our project's possible distinction would be a narrow working language-command system, concrete compiled contracts, formal endpoint properties, controlled hardware experiments and reproducible negative results. A submission-time novelty review remains necessary. This search does not establish a first-ever claim.

An unverified secondary-index lead for “Deadline-Guarded Edge Inference with FPGA Preemption” could not be confirmed in primary text; it is recorded separately in the registry and is not used to support technical assertions. Resolve it before publication.

## Experiments and decision gates

### 1. Prove the application capability in software before a new bitstream

Create a small human-reviewed pilot with commands, state snapshots and executable ground-truth plans. Include negation, unit conversion, unknown assets, ambiguous references, unsupported requests, paraphrases and two-turn corrections. Train MiniLM, a stronger compatible encoder, a ModernBERT reference and FunctionGemma on the same task information. Measure quantized as well as floating variants.

For the full study, split by paraphrase/template family, composition, author and asset identifiers. Teacher-generated examples can augment training but must not dominate the blind test. Reserve separate validation and acceptance-calibration data. The55,961 existing evaluated requests are regressions; they are not a fresh blind test for this new capability. Use a pinned [BFCL](https://gorilla.cs.berkeley.edu/leaderboard.html) subset as an external diagnostic, with training-overlap limitations stated, plus a new domain-specific human test.

Proposed targets, not results: at least95% full-command correctness on supported unambiguous commands; accepted error at most1% with at least80% coverage on the declared distribution. Report confidence intervals. Approximately300 independent accepted examples with zero errors give a one-sided95% upper error bound near1%; multiple strata, correlated synthetic prompts and distribution shift require more evidence. Do not inherit a formal risk guarantee from a softmax threshold.

### 2. Make the generator earn its hardware port

An explicit initial engineering gate: FunctionGemma must improve full-command accuracy by at least5 absolute points, or accepted coverage by10 points at matched accepted error, over the best encoder on the compositional subset while fitting the proposed memory profile. These are project decision thresholds, not statistical laws. Fit all model/threshold choices before the blind test.

Measure prefill, decode, output completion and peak memory independently on the available software target. An optimized A53-only board run is a necessary later comparator, clearly separated from the production R5-controlled path. Do not copy phone or KV260 throughput as an A53/KR260 measurement. If no substantive generative advantage appears, stop the decoder port and deploy the stronger encoder. That is an informative model/hardware result.

### 3. Qualify one new hardware path at a time

For the encoder, compile and relocate the larger image, generalize the R5 dimensions, check numerical decisions/slots, and qualify the supported shape/window. Direct ModernBERT additionally needs its operator/masking specification.

For the decoder, first freeze one checkpoint and a fixed context/output cap. Initially cap total context at512 tokens and output at64 tokens, counting schema and state. These are experimental starting limits, not claims about our current128-token hardware. Implement verified32-bit IDs, required head dimension, causal/GQA/local attention, KV ownership, RoPE, normalization/gating and output projection. Start from author references where appropriate; TeLLMe's ternary arithmetic cannot directly implement dense4-bit FunctionGemma weights. Retain the current known-working package and use a separately qualified successor. Do not presume two engines fit simultaneously in the routed design.

### 4. Evaluate the system claim, not tokens/s alone

Compare matched variants: optimized A53 encoder with software checks; the same CPU model with the PL result gate; current FPGA encoder; stronger FPGA encoder; A53 FunctionGemma; FPGA FunctionGemma if its port passes admission. This separates the benefits of the model, accelerator and independent endpoint. Add a cascade only if those measurements justify it and its resource mapping is feasible.

For each, report exact full-command/execution accuracy, argument accuracy, accepted error, coverage, semantic failures, structural invalidity, clarification, timeouts, peak memory, thermal state and energy. Measure batch1 and separate cold startup from a resident bounded service. Count all energy consumed by rejected, late and retried requests. Report correct on-time commands divided by all issued requests, and correct on-time commands per joule; do not make an abstain-everything system look successful.

Sweep proposed budgets100,250,500,1000 and3000ms as empirical tradeoff points. Under CPU/DDR contention, injected missing/late proposals and malformed records, verify that the PL endpoint's terminal outcome follows its contract. Pin the clock/reset fault model and distinguish endpoint availability from Linux/network delivery. A clocked independent timeout can provide a bounded failure outcome; successful completion for every admitted request still needs justified memory-service and execution bounds. The present trusted-Linux deployment does not establish protection against a malicious Linux master or exclusive R5 ownership of every shared path.

### 5. Decide whether the project has earned its claim

Proceed toward publication only if the system demonstrates an advantage over appropriate software/model/monitor baselines, with a reproducible artifact. Useful outcomes include higher correct-on-time coverage at matched error/energy, or a proved result-publication property exercised under declared processor stalls. Do not claim semantic safety from a finite type or that a watchdog alone is novel. If the stronger encoder matches generator capability at substantially lower cost, publish that bounded task result rather than forcing generation into the system.

## Immediate deliverables

The next substantive implementation work should be the12-API task/specification, human-reviewed pilot, canonical AST validator/evaluator and matched fine-tuning/evaluation pipeline. That produces new learned task capability and answers the model-choice question. Then implement the winning hardware path and its schema-derived endpoint contract. Another CLINC threshold sweep or unmeasured larger-model upload would not answer this research question.

This recommendation is research-grounded and deliberately falsifiable. It does not assert that the proposed system is already novel or that either untested candidate already meets its quality, latency, energy or resource targets.
