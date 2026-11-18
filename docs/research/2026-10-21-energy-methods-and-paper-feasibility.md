# FPGA inference energy: literature review and integrated-paper feasibility

Prepared 2026-10-21. Target: System One on KR260/K26. This is an evidence-based feasibility assessment and proposed protocol, not measured energy results. No board session, configuration change, benchmark restart, or deployment was performed. Existing frozen evaluations remain separate. Effort ranges below are planning judgments for one researcher familiar with the system, not commitments.

## 1. Decision

**One integrated project is feasible. One paper is feasible if energy evaluates one central system contribution. A general FPGA power estimator, new accelerator architecture, encoder/generator comparison, dependable execution mechanism, and state-management method are too many independent claims for one focused paper.**

The strongest current integration is a bounded-context embedded inference study: quantify how explicit state management changes task correctness, context capacity, end-to-end latency, and measured energy on a real FPGA system. Treat the accelerator and its qualified execution path as the platform; include one hardware ablation only if it explains a substantial result. A hardware-first paper is a viable alternative if the architectural comparison is stronger than the application evidence. These are alternative centers of gravity, not mandatory combined tracks.

Energy integration, idle subtraction, and action-count models already have extensive precedent. Our opportunity is to establish a useful result under declared quality, hardware, and workload boundaries. Neither a new ratio nor putting existing techniques together establishes novelty by itself.

## 2. Local evidence and remaining gaps

| Evidence inspected | What it establishes | What it does not establish |
|---|---|---|
| `BOARD_STATUS.json`, revision 8, saved verification 2026-10-21 | Recorded active v8 wide-int8 Qwen deployment, decoder about 125 MHz and memory interface about 250 MHz; v9a build 3 separately tested and v8 restored | Live state now, energy, or representative sustained performance |
| Same status file's candidate receipts | Three v9a cold commands median 6.956 s versus same-boot v8 control 9.140 s, identical generated IDs; 96-case causal smoke | General speedup, task-quality equivalence over a benchmark, or energy saving |
| `2026-10-21-v8-benchmark-harness.md` | Existing timing/identity/fixture infrastructure and cold versus persistent distinction | Energy collection; document explicitly says energy is unmeasured |
| v5 chain and v6 state pilots | Explicit parsers, state ownership, capacity handling and separation of inherited/new errors | Reliable arbitrary closed-loop planning or a matched CPU speed baseline |
| v9 retention and v10 development notes | Host-maintained JSON state and repeated extraction; v9 reports 210/224 correct, with status fidelity failures; v10 separates development from fresh evaluation | Autonomous memory, reliable 64-step reasoning, FPGA energy, or unbiased paired v9/v10 improvement |
| October 14 architecture/experiment review | Prior encoder locality, exactness, bandwidth and measurement questions | A description of the current decoder platform; those encoder results must not be relabeled as decoder results |

The CPU pilots include per-call process/model loading. They cannot support resident CPU-versus-FPGA energy or speed claims. The full historical sweep remains stopped. Reading saved board status is not a new board probe.

Relevant local documents: [current benchmark plan](2026-10-21-v8-milestone-benchmark-plan.md), [harness](2026-10-21-v8-benchmark-harness.md), [chain pilot](2026-10-21-v8-chain-pilot-v5.md), [retention v9](2026-10-21-v8-json-retention-v9.md), [retention v10](2026-10-21-v8-json-retention-v10.md), [earlier experiment plan](2026-10-14-system-one-experiment-plan.md).

## 3. What the literature supports

### 3.1 Physical measurement and complete-system boundaries

MLPerf Power makes performance, quality, and power part of the same experimental problem. The official framework emphasizes physical measurement, shared system components, and reproducibility. The archived Inference v2.0 rules specifically require total system power and performance/power from the same run. Those historical rules are useful precedent, not a claim about all current MLPerf tracks or a requirement to certify our experiment. [MLCommons framework overview](https://mlcommons.org/2025/03/ml-commons-power-hpca/), [archived v2.0 rules](https://github.com/mlcommons/inference_policies/blob/master/power_measurement.adoc).

**Application:** choose the physical boundary before comparing efficiency. Use one primary boundary consistently: preferably KR260 DC input for board energy, with SOM energy as a diagnostic. AC input additionally includes adapter losses. A laptop controller may be excluded when it only launches/logs tests, but any host doing essential tokenization, inference, state reduction or execution must be inside the declared system boundary or separately accounted for. Do not add nested measurements: board input already contains SOM consumption.

### 3.2 KR260 onboard telemetry

AMD documents a monitor on the SOM_5V0 rail, accessible through I2C and AMD utilities. The K26 module includes the MPSoC and runtime memory, making this an attractive combined compute/memory boundary. It is not the full carrier input, and the documented monitor does not imply independent measured PS, PL and DDR channels. [KR260 power guide](https://docs.amd.com/r/en-US/ug1092-kr260-starter-kit/Powering-the-Starter-Kit-and-Power-Budgets), [module description](https://docs.amd.com/r/en-US/ug1092-kr260-starter-kit/Summary).

**Feasibility:** promising, pending identification of the actual sensor, Linux driver, units, refresh behavior, access method and configuration on our deployed image. No local collector was identified by the targeted source search. This is not evidence that the board lacks telemetry. AMD documents `xmutil` generally, but its existence alone does not establish an energy logging interface. [Platform utility](https://docs.amd.com/r/en-US/ug1092-kr260-starter-kit/Platform-Management-Utility).

Digital monitors such as TI's INA260 support configurable averaging and current/voltage/power reporting. This illustrates why sensor averaging settings matter; it is not identification of our actual board sensor. Component specifications also do not establish end-to-end experiment accuracy. [TI INA260](https://www.ti.com/product/INA260).

### 3.3 Sampling, averaging, synchronization and short kernels

Yang, Adamek and Armour's GPU sensor study compares built-in readings with an external meter and exposes update/averaging behavior that can distort energy estimates. Polling an API faster does not guarantee new physical observations. Their hardware-specific findings do not transfer numerically to K26, but the characterization method does. [Author preprint, revised December 2024](https://arxiv.org/html/2312.02741v3).

**Application:** characterize fresh-sample cadence and load-step response before choosing analysis windows. Seconds-long complete calls are easier to measure than individual millisecond layer operations. Repeat controlled short work in longer windows if necessary, describing that result as sustained repeated-work energy. A repeated loop changes cache, thermal and duty-cycle behavior; it does not recover isolated-request energy automatically. Do not claim per-token or per-layer energy resolution from slow telemetry just because software timestamps are precise.

### 3.4 ROTA: route, data-pattern and working-set experiments

ROTA's public artifact provides explicit routes, constant/random payloads, working-set variation, randomized repetitions, idle windows, raw counters and an aggregate verifier. These are useful controls for asking whether lower data movement or a different memory regime saves energy even when throughput changes little. Its H100 coefficients and percentages are not FPGA coefficients. The manuscript was not located; this review evaluates the public artifact and author descriptions. [Artifact](https://github.com/Ribeirosk8/rota-artifact), [benchmark](https://github.com/Ribeirosk8/rota-artifact/blob/main/code/route_bench.cu).

Two implementation details deserve independent checking before reuse. The aggregate verifier uses a scripted 15 s idle denominator, whereas the README discusses 15.262 s timestamped duration. Energy snapshots in the sweep bracket a launched process, while active time is reported internally by the benchmark; those intervals may include different work. The public benchmark also invokes an external energy probe rather than implementing energy collection itself. We should integrate power over the same marked interval as the work denominator and use actual idle timestamps. These observations do not quantify the bias of any published result. [Verifier](https://github.com/Ribeirosk8/rota-artifact/blob/main/verify_aggregates.py), [sweep](https://github.com/Ribeirosk8/rota-artifact/blob/main/code/curve.slurm).

### 3.5 Vendor estimates: useful architectural evidence

Vivado Report Power supports vectorless activity propagation and simulation activity through SAIF. AMD recommends realistic stimulus and prefers post-implementation timing simulation for capturing glitch activity; unmatched nets still use vectorless analysis. Thus an activity-informed estimate can explain clock, logic and memory contributions without constituting a physical measurement. [UG907 activity guidance](https://docs.amd.com/r/2023.2-English/ug907-vivado-power-analysis-optimization/Specifying-Switching-Activity-for-Power-Analysis), [vectorless method](https://docs.amd.com/r/2024.1-English/ug907-vivado-power-analysis-optimization/Vectorless-Power-Analysis).

**Application:** use the project's actual Vivado version, routed design and documented activity coverage. Include clocks, enables, reset behavior, realistic quantized operands, voltage and temperature assumptions. Compare estimates and measurements only after reconciling boundaries: a PL estimate does not contain all module or board loads. One representative SAIF study is a reasonable optional explanation; exhaustive full-LLM timing simulation and calibrated primitive models are a substantial separate effort.

### 3.6 Analytical and counter-based energy models

The energy-roofline tradition separates arithmetic energy, memory energy and time-dependent baseline energy. It explains why performance bottlenecks and energy bottlenecks can differ. Choi's author thesis develops and experimentally investigates this formulation. [Energy-roofline chapter](https://jeewhanchoi.github.io/publication/pdf/phd_2015.pdf).

Accelergy estimates architecture-level energy from primitive/compound components and characterized actions. It provides a strong precedent for combining operation counts with energy costs, but its demonstrated accuracy is specific to its evaluated designs. ASIC-oriented component tables are not validated K26 DSP, LUT, BRAM or DDR models. [Accelergy, ICCAD 2019](https://ieeexplore.ieee.org/document/8942149).

Direct FPGA work is also mature: Jevtic and Carreras model routing, clock and component logic power using placement characteristics and correlated-input switching, validating against onboard measurements. This is stronger evidence than assuming watts scale with DSP count; its older-device coefficients are not transferable to our design. Only the publisher abstract and institutional record were inspected here, not an accessible full manuscript. [VLSI Integration, 2012](https://www.sciencedirect.com/science/article/abs/pii/S0167926011000782), [author institution record](https://oa.upm.es/86217/).

**Application:** a small calibrated explanatory model is feasible; a general architecture-independent predictor is not the minimum path. Do not infer joules/MAC and joules/DDR-byte separately if MACs, bytes and time all rise together in every experiment. Good fit alone cannot identify physical causes. Vary reuse or transfer granularity independently, validate on held-out workload regimes, and label fitted quantities as effective coefficients rather than device constants.

### 3.7 FPGA Transformer and edge-LLM comparisons

FTRANS establishes prior art for Transformer compression/architecture co-design and energy-efficiency comparison. Its reported evaluation tables are useful historical context; they do not supply a matched, calibrated KR260 measurement boundary. [FTRANS, ISLPED 2020](https://arxiv.org/html/2007.08563v1).

TeLLMe v2 is closer in platform class: K26/KV260 ternary inference, both prefill and decode, and a CPU vocabulary head included in its latency. It also reports a perplexity-normalized efficiency metric. The inspected setup does not give us enough instrument/boundary detail to reproduce a whole-board energy comparison from the headline power table. Different model/precision/software/carrier configurations prevent direct substitution into our calculations. Task correctness per joule is more relevant to our application than perplexity-normalized token rate. [TeLLMe v2](https://arxiv.org/html/2510.15926v2).

### 3.8 Context management is also established prior art

MemGPT already manages external memory around bounded model context; Gist Tokens learns prompt compression and caches its representation; ReAct studies interaction between reasoning and actions. Their implementations differ substantially from our explicit host-state reducer, but they rule out broad novelty claims for external memory, smaller prompts or tool workflows. [MemGPT](https://arxiv.org/abs/2310.08560), [Gist Tokens](https://arxiv.org/abs/2304.08467), [ReAct](https://arxiv.org/abs/2210.03629).

A defensible distinction would be measured, quality-controlled consequences of a transparent bounded-state contract on constrained embedded hardware. Showing that host state stays bounded while a transcript grows is expected; the research must establish task sufficiency, failure behavior, costs and a meaningful advantage over straightforward alternatives.

## 4. Calculations to implement

### 4.1 Primary measured quantities

For power samples P_i at actual monotonic timestamps t_i, estimate window energy using timestamp-weighted integration, for example:

    E_window = sum_i 0.5 * (P_i + P_(i+1)) * (t_(i+1) - t_i)
    E_total_per_request = E_window / N_attempted
    E_incremental_per_request = (E_window - integral P_idle_hat(t) dt) / N_attempted

Watts times seconds gives joules. Trapezoidal integration assumes interpolation between point-like samples. If the instrument reports interval averages or cumulative energy, honor those semantics instead. Clip/interpolate at marked boundaries only as supported by the sensor response; do not invent sub-sample phase detail. Integrate measured power or synchronized voltage/current products, not the product of unrelated mean voltage and mean current.

Report total energy first and idle-subtracted energy as a separate diagnostic. Define idle as the same configured system with model resident and no submitted inference; powered-down/unloaded idle answers a different question. Bracket runs with idle measurements and check drift. Subtraction removes idle activity as well as leakage; it does not isolate PL dynamic power or establish causal attribution to one module. Retain negative/noise-level differences and flag them as unresolved rather than clipping or silently excluding them.

For application utility use:

    useful_efficiency = N_correct_complete_on_time / E_all_attempts
    energy_per_useful_completion = E_all_attempts / N_correct_complete_on_time

Keep failures, rejected outputs, timeouts, retries and state-reducer work in E_all_attempts. If the successful-completion count is zero, efficiency is zero and energy per success is undefined. Report coverage and accuracy beside the ratio. A rejection can be a correct outcome for an explicitly unsupported-input task, but is not a completed requested workflow. Any deadline here is an empirical budget, not a WCET proof.

J/generated-token and tokens/J are supplementary fixed-work metrics. Different prompts, outputs, model quality and stopping policies can change their meaning. Prefill first-token work must not be counted again as a decode token operation.

### 4.2 Explanatory model, if warranted

Start with a deliberately small model:

    E_hat = P_resident * T + e_read * B_DDR_read + e_write * B_DDR_write
            + e_compute * N_useful_ops + E_host_extra

The terms require mutually consistent boundaries and calibration; do not add host energy already absorbed by a fitted baseline or compute coefficient. Byte counts should distinguish logical tensor bytes from physical bus transfers and include repeated weight passes, KV traffic, padding and copies where observed. If physical counters are unavailable, label the ledger analytical. Actual token distribution and precision remain model inputs.

A phase-duration model may be more identifiable than per-operation coefficients: resident baseline plus measured prefill, decode and host-extra contributions. Validate against a simple constant-power-times-duration baseline first. Reject complexity that does not improve held-out prediction beyond measurement uncertainty. No claimed universal pJ/MAC, pJ/bit, or DDR energy constant follows from this project.

### 4.3 Uncertainty and deployment duty cycle

Separate repeat-to-repeat variability from systematic sensor gain/offset, refresh/filter response, clock alignment, integration gaps, idle drift and observer overhead. Bootstrap by independent campaign block or workflow, not by every dependent step or repeated sensor read. Repetitions do not remove calibration bias. For a constant idle estimate:

    delta_E_incremental approximately delta_E_window - T * delta_P_idle
    relative difference uncertainty grows as active-minus-idle becomes small.

A useful screening bound for uncertain edges is E_edge on the order of P_max times the combined start/end uncertainty. This is a conservative diagnostic, not a complete uncertainty model.

For intermittent deployment, report a fixed observation horizon or request rate as well as saturated throughput:

    E_horizon approximately P_resident * T_horizon + N * E_incremental_request

This assumes a stable resident baseline and additive requests; sleep/wake transitions require additional terms. Compression could improve saturated energy/request while barely changing sparse-service battery use. A residency break-even calculation must measure startup, idle and demand; do not derive it from TDP.

## 5. One-paper scope options

| Center of paper | Energy's role | Feasibility | Main missing evidence |
|---|---|---|---|
| Bounded-state embedded inference, one model/platform | Co-primary outcome with correctness and latency | Best fit to recent work; conditional medium effort | Independent held-out task families, meaningful state/history baselines, synchronized energy, resident CPU baseline |
| Exactness-preserving accelerator/memory co-design | Co-primary outcome with end-to-end performance | Credible alternative if v8/v9a or another admitted comparison is the strongest result | Repeated matched hardware ablations, identical workload/outputs, energy and bottleneck attribution |
| General FPGA power predictor | Main contribution | Low feasibility as an add-on | Many independently varied architectures, physical calibration, held-out designs and baselines |
| Encoder + generator + hybrid + state + real-time assurance + energy | Several main contributions | Poor fit to one focused paper | Multiplied model, quality, hardware and assurance campaigns |

Recommended research question:

> Under a fixed embedded context budget, can an explicit, provenance-preserving state interface improve correct useful completions per joule and latency relative to practical history baselines, after counting all host work and failures?

Candidate title, conditional on results: **Bounded-State Language Inference on an Embedded FPGA: Correctness, Latency, and Energy Tradeoffs.**

For a hardware venue, choose the architectural mechanism as the main claim and use the application to demonstrate its effect. For a systems/embedded study, the state/execution interface and evaluation can be central. Venue suitability remains conditional on novelty and results; no acceptance prediction is justified.

The R5/result-publication mechanism can support the execution contract if actually used and tested. The saved current decoder status says R5 is not loaded; historical encoder/AMP properties cannot be attributed to this deployment. A new fault-isolation or hard-real-time theorem would be an additional substantial contribution.

## 6. Minimum viable experiment

### Stage A: qualify measurement first

Identify the instrument and boundary; capture raw readings with units and timestamps; characterize update cadence, duplicate readings and a sustained idle/load/idle response. Validate against an external instrument where available. SOM and board-input readings should differ because their boundaries differ; do not call that difference sensor error without accounting for carrier/regulator loads. Compare logging-enabled and logging-disabled latency/CPU behavior. Keep collector overhead explicit.

Use windows spanning many actual sensor updates, lengthened until uncertainty meets the proposed claim. Instrument choice and measured response determine duration; there is no universal safe polling frequency. External faster acquisition is necessary only if fine phase attribution is a required claim. Gate: proceed only when boundary, units, timing and uncertainty are defensible.

### Stage B: fixed-work characterization

Use three input lengths (for example 32/96/160 tokens) and two generated lengths (16/48), all within context256 after complete template accounting. Predeclare forced-length versus natural completion, and record actual tokens and EOS. Three frozen prompt variants per cell yield 18 workload points; five independently ordered blocks yield 90 observations per configuration, subject to pilot noise. Start resident-only and add a small cold-start study rather than multiplying every factor immediately.

This separates token work from application success. At fixed clock/precision, test whether constant power times duration already explains energy. Include a realistic quantized-data path; synthetic constant/random traffic is an optional diagnostic, not a substitute for task energy. Do not introduce arbitrary sensor or DDR stress tests into the primary workload boundary.

### Stage C: application comparison

Primary arms: full history, explicit sliding history with a fixed truncation policy, and canonical JSON current state. Add compact state only after these controls work. Hold model, output encoding, parser, sampler, output budget and available task information fixed. Evaluate selection of relevant state separately from its serialization. A fixed JSON state is not lossless for arbitrary tasks; add delayed dependencies and facts outside naive current-value fields to test sufficiency.

Include a deterministic software lookup/rule baseline. Today's retention workload supplies state and asks for an entity's stored fields; ordinary code can answer that task without an LLM. Its value is a diagnostic for fidelity and measurement, not evidence that neural inference is needed. The application benchmark needs natural-language interpretation or other capability that this simple baseline does not already solve. Report the rule baseline's accuracy/coverage and energy rather than constructing ambiguous inputs solely to defeat it.

The primary no-prefix-reuse comparison isolates representation cost on the deployed runtime. It can disadvantage transcript history relative to runtimes that cache unchanged prefixes. Include a software cached-history baseline if practical, or explicitly limit conclusions to fresh-prefill operation and quantify repeated token work. Do not label that result an advantage over all memory-management systems. Keep cold initialization separate from this cache-policy question.

Begin with a predeclared 24 fresh workflows balanced across three task families, at an 8-step common target: three arms imply at most 576 generated requests per block. Capacity stops reduce the count but are outcomes. Use at least three separately ordered blocks for energy repeatability; these are not 72 independent semantic workflows. Increase held-out workflows if the desired quality claim needs it. The existing two-entity synthetic tasks are pilot infrastructure; add realistic identifiers, units, overwritten facts and missing/error semantics for a credible application evaluation.

Compare equal requested goals/horizons, common executable prefixes, and cumulative correct work versus energy. A history arm that stops early can consume less total energy because it did less work. Do not present that as higher efficiency or force a nonexistent full-workflow energy value. Freeze retry/stop rules and count verification, tokenization, parsing, state reduction and simulated tool work. Report simulator scope; real actuation is unnecessary for this paper.

Use one resident CPU implementation on the same K26 if practical. Otherwise use a measured, fully specified external CPU system and treat the comparison as across systems. Match model arithmetic closely enough to verify output/task quality; CPU Q8_0 and FPGA integer execution are not automatically equivalent. Cross-model comparisons answer a different utility question and are optional.

### Stage D: one hardware ablation, optional

If v9a remains a qualified candidate, compare v8/v9a on identical fixed work, with repeated configuration blocks, identity checks and matched cold/resident boundaries. Earlier three-command timings motivate this experiment but cannot replace it. Hold the primary state study to one frozen hardware configuration. A full state-by-hardware-by-model-by-clock factorial is unnecessary unless interactions are the main claim.

## 7. Effort, experiment cost and gates

| Work package | Approximate additional focused effort | Dependency/risk |
|---|---|---|
| Sensor discovery and characterization | 2–5 working days | Actual telemetry access, instrument availability and effective update rate unknown |
| Collector, timestamp alignment, integration and raw-data verification | 3–5 days | Existing timing harness helps; observer effects need checking |
| Fixed-work/resident CPU and optional hardware baseline | 3–7 days | Matched runtime/precision may be the largest software obstacle |
| Stronger held-out workflow suite and frozen protocol | 1–2 weeks | Task sufficiency and quality are substantive research risks |
| Campaign, uncertainty analysis and reproducible report | 1–2 weeks | Serial board access, reruns and thermal stability |

A focused energy addition to an already stable experiment is plausibly **2–4 weeks**. A stronger integrated study from today's pilot evidence is plausibly **4–8 weeks**, with overlap among tasks and hardware availability assumed. Broader reliability, new model training or architectural redesign can extend this substantially. These estimates do not include equipment procurement or venue review cycles.

Budget machine time explicitly. For M requests of average duration tau seconds over R repeated blocks, core occupancy is approximately M*tau*R, plus startup, idle references and transitions. Illustratively, 576 requests at 10 s each over three blocks consume 4.8 hours before overhead. This is planning arithmetic, not a measured runtime forecast; longer prompts/outputs may be much slower.

Decision gates:

1. **Measurement:** if SOM telemetry is sufficient but no board meter is available, publish SOM-scoped energy. If neither method is characterized, retain latency/quality results and defer energy claims.
2. **Quality:** freeze a task-specific acceptable loss margin before evaluation. If smaller state is cheaper only because it loses required information, publish the tradeoff and do not claim an unconditional benefit.
3. **Effect size:** if the measured advantage is within systematic uncertainty or block variation, report it as unresolved. A planning target such as 5–10% relative precision must be chosen against the expected effect and achievable instrument performance, not adopted as a universal rule.
4. **Novelty:** if only deterministic state copying and a shorter prompt are demonstrated, treat the result as an engineering milestone. A paper needs stronger mechanism/evaluation evidence or should pivot to the hardware co-design track.
5. **Scope:** stop adding models, clocks or formats once the central question is answerable. Add a factor only to test a stated hypothesis.

## 8. Expected paper evidence and deliverables

The primary paper should have one boundary diagram; one table of platform/workload/instrument settings; quality versus energy and latency plots; context-capacity and common-prefix outcomes; cold/resident results; and one mechanism ablation. Include raw timestamped power, request/result traces, failure ledgers, source/model/bitstream hashes, instrument configuration, integration code, independent aggregate recomputation and uncertainty assumptions.

The central claim must remain conditional on the measurements: a transparent bounded-state interface may reduce repeated inference work while preserving useful output under a fixed context budget. Energy is the physical outcome that makes that claim relevant to an embedded system. A universal power estimator, arbitrary-agent competence, semantic safety, and hard-real-time successful completion are outside the minimum paper.

### Review depth and limitations

This is a targeted semi-deep review, not a systematic literature census. It uses primary papers, author/institutional artifacts and manufacturer documentation. Full HTML was inspected where available, with relevant setup/method sections examined; the older FPGA model was available as abstract/institutional summary only. ROTA's manuscript and our deployed sensor configuration remain unverified. Literature results establish precedent and experimental methods; the proposed scope, effort and gates are this review's engineering judgment.
