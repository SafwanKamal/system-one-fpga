# Broader research search: keeping sensor history useful when the questions change

**Status: closed by user decision, November 16, 2026.** Both the [first software pilot](2026-11-08-future-sensor-memory-pilot.md) and the [raw-signal held-out-category experiment](2026-11-16-retroactive-task-pilot.md) failed to establish a useful contribution over strong simple baselines. No further method development or FPGA implementation is planned for this research direction. The proposal below is historical rationale, not the current recommendation. See the [closure record](2026-11-16-sensor-memory-closure.md).

Research cut: November 8, 2026. This report proposes a new research direction; it does not report an implemented method or establish a first-in-literature claim.

My preferred direction to investigate is **memory for multichannel sensor streams that remains useful when future questions change**. A device observes continuously, has a fixed storage and processing budget, and later receives questions involving event order, duration, repetition, or relationships between channels. The scientific problem is deciding which distinctions to preserve before those particular questions are known.

The concrete niche is narrower than general streaming memory: **retaining relational evidence under a shift in future temporal questions, when the event predicates themselves are learned and uncertain**. This is an edge intelligence and representation problem with a possible FPGA implementation. The existing decoder is optional. This choice is my assessment of experiment value after the discussion below, rather than a consensus novelty verdict.

A second worthwhile branch is acquisition and learning when labels arrive late and the needed signal window can no longer be acquired. Manual-conditioned diagnostic model generation and learning-assisted combinatorial optimization are interesting alternatives, but this round found particularly direct predecessors for both.

## What changed in this search

I reread the RC1 baseline and Claude's latest gate novelty checks, including the November 8 checks of inline refusal, controller confirmation, stale observations, isolation, and approval. Those are useful engineering findings. They increasingly leave narrow implementation and evaluation distinctions. I would stop using proximity to that implementation as the main filter for the next research question.

The working platform is a KR260 with a qualified Qwen3-0.6B decoder, an embedded runtime, and other encoder and Ethernet workstreams. The baseline has a 2,048-token context and eight-token prefill. That is an asset for experiments in local intelligence, but it does not establish an advantage for continuous sensing or adaptation. See [the adopted baseline](../../hardware/BASELINE.md). A new sensor front end should be costed as a separate design; the existing decoder's tightly packed image is not spare fabric.

Three independent searches examined applications, architecture, and learning frontiers, followed by cross-criticism and targeted historical searches. The accompanying notes are:

- [Applications and diagnostic transfer](2026-11-08-broad-applications-search.md).
- [Architecture, shared features, and acquisition with delayed labels](2026-11-08-broad-hardware-search.md).
- [Observation versus computation, adaptation, asynchronous fusion, and an optimization wildcard](2026-11-08-broad-frontier-search.md).

This is an additional focused search beyond the earlier 100-plus-work screen. It is not another claim to have read 100 new papers in full. The notes distinguish primary abstract screens, inspected method sections, and access limitations. No board experiment or benchmark reproduction was performed in this round.

## The broader opportunity landscape

| Direction considered | Capability that makes it interesting | Strong prior that defeats the easy pitch | Decision |
|---|---|---|---|
| Future-question sensor memory | Reinterpret a physical history after information needs change | RoboMem, StreamMem, SVMemAgent, SAVEMem, workload-based synopses | Develop a precise relational/query-shift experiment |
| Acquisition with delayed learning | Save observation cost while retaining the ability to discover a changed regime | AdaSense, active feature acquisition under drift, UFODT, delayed-label learning | Keep as the second experimental branch |
| Equipment documentation to diagnostic models | Commission a new assembly with less specialist model authoring | DX2024 multimodal model generation; Lu et al. HVAC DBN generation; BMD/MDA | Downgrade broad novelty; retain a difficult transfer question |
| Question-directed future sensing | Acquire the channels and windows needed by a stated temporal question | TinyDB, BBQ, LLM adaptive-sampling compiler, intent-driven trigger DSL | Potential extension; interface alone is insufficient |
| Shared features and useful freshness | Serve changing tasks without recomputing every overlapping window | SensiX++, stream aggregation, age/error inference scheduling | Conditional systems follow-up |
| Small on-device continual learners | Learn from corrections after deployment | TinyOL, TinyTrain, LifeLearner, delayed-label rehearsal, frozen-feature coresets | Supporting mechanism; generic online learning is occupied |
| Asynchronous fusion | Choose whether to wait, predict, or process a partial multirate observation | Streaming Perception, causal irregular-time models, Raindrop, MMEdge | Lower priority until a specific skew failure is demonstrated |
| Personalized detectors from language | Let users define new events | Gensors, SensorLM, intent-driven collection DSL | Useful product capability, weak standalone novelty |
| Learned repair of changing schedules/graphs | Reuse yesterday's solution for the next small graph update | Embedded ML-assisted Ising systems and learned dynamic MIS updates | Larger pivot with direct prior; defer |

These directions concern different decisions: what to observe, what to remember, what to learn, and what experiment to run. They offer substantially more room than another restriction on the current inference execution path.

## Preferred niche: an edge recorder that can answer a changed question

Imagine a machine recorder that currently distinguishes normal operation from known faults. Tomorrow an engineer asks whether a short current pulse repeatedly preceded a vibration event, or whether pressure drops happened only after a particular operating transition. An archive of predicted labels may have discarded the distinction. A good reconstruction codec might preserve it; a compact semantic archive might also preserve it. Which representation wins under a severe budget is the research question.

The questions concern observable temporal relationships. A lead–lag association alone would not establish a causal explanation. Physical interventions belong to the separate diagnostic branch.

The task has three important forms of generalization:

1. The precise question arrives after collection. The policy knows a training distribution of questions, not the future test question.
2. Test questions use held-out compositions of familiar predicates and temporal operators. A harder, separately reported panel changes which question families are frequent or important.
3. A further panel asks about sensor concepts supplied or refined after collection. This tests whether retained representations allow reinterpretation. It should not be mixed into the first study, because it adds a different source of difficulty.

An example family is “count occurrences of A followed by B within an interval, excluding periods in operating state C.” A and B can be uncertain learned local concepts; timing and counts are calculated by a common query engine. The method needs to preserve enough joint evidence to revisit those local decisions later.

The prospective contribution is a **streaming representation and retention policy that preserves combinations of evidence needed by relationships**, together with an evaluation exposing how retention fails when questions change. Retaining isolated high-salience windows can be inadequate if the answer depends on two endpoints or on the interval between them. Conversely, a simple event table can solve the task very well when the predicates are stable and known. That table is an essential competitor.

### The closest work substantially narrows the claim

| Primary source and inspected depth | What is already established | Consequence for our proposal |
|---|---|---|
| [RoboMem, 2020](https://arxiv.org/abs/2003.10553), primary abstract | Compact long-term robot memory for unanticipated queries, with selected frame reprocessing | Unknown future queries and compact physical memory are established |
| [SensorChat, 2025](https://arxiv.org/html/2502.02883), query method sections | Sensor/text embeddings stored across history, explicit quantitative query functions, language-based decomposition and assembly | Long-duration sensor QA and temporal/count/duration functions are established |
| [StreamMem, 2025](https://arxiv.org/abs/2508.15717), primary abstract | Fixed-size query-agnostic streaming video KV memory | Query-agnostic bounded memory is established |
| [SVMemAgent, September 2026](https://arxiv.org/html/2609.18540), method sections | An online retain/discard/replace policy trained with future-QA rewards; separate semantic and temporal branches | Learning retention from a training question distribution is already a direct method precedent |
| [SAVEMem, May 2026](https://arxiv.org/abs/2605.07897), primary abstract | Constant-budget streaming visual memory shaped by a pseudo-question bank, then query-aware retrieval | Generic proxy questions and multilevel semantic memory are established |
| [TimesJev, October 2026](https://arxiv.org/html/2610.26002), feature-selection and analysis sections | Learns compact time-series features through a sufficiency-oriented objective and aligns them to a frozen decision model | Task-relevant feature compression and sufficiency language cannot serve as novelty |
| [Memento, October 2026](https://arxiv.org/abs/2610.19227), primary abstract | Persistent local vector memory to send recurring sensor observations by reference, implemented on an MCU | Local sensor memory, reference reuse, and communication savings are established |
| [Workload-based weighted wavelet synopses, 2005](https://theory.stanford.edu/~matias/papers/mu-www-synopses-05.pdf), introduction and formulation | Optimizes compact representations for error over future queries drawn from a workload | Optimizing answer error rather than whole-signal distortion is an old database idea |
| [NeaTS, ICDE 2025](https://arxiv.org/abs/2412.16266), primary abstract | Nonlinear time-series compression with random access and bounded residuals | Efficient numerical history is a serious alternative to learned semantic retention |

The remaining distinction is a hypothesis about a workload and mechanism: uncertain multichannel predicates, complementary temporal evidence, and future question shift may favor joint retention of linked intervals and refinable signal information. It has to beat adaptations of these methods and simple combinations. Moving a video memory policy to vibration data would be a domain transfer, with limited algorithmic novelty on its own.

### A concrete method to investigate

For each incoming window, make several representation choices available: compact numerical features, a quantized sensor embedding, timestamped event probabilities, a selected raw or transform residual block, or a link to a related earlier window. Charge actual stored bytes and processing work for each choice.

The first baseline should be a hybrid interval table, multiresolution numerical summary, and small raw reservoir. This is likely stronger than any one of those alone. It must include uncertainty about event identity rather than keeping only a top-1 label.

The candidate allocator would score **bundles** of related evidence, such as two windows and their relative timing, against a declared set of temporal question families. It would decide when to preserve a cheap summary and when to reserve refinable data for a relationship that the cheap representation obscures. A complementary-witness objective is a design hypothesis: test whether valuing bundles changes the retained information beyond ordinary per-window novelty or uncertainty scores.

One possible training formulation minimizes the largest expected answer loss across declared question families, subject to memory and ingestion-work limits. Robust optimization itself is established. The research has to supply an effective streaming approximation, explain when complementary evidence matters, and show a useful frontier. An expensive general RL agent is unnecessary unless simpler allocation fails.

There is no universal lossless solution under an arbitrarily small budget and unrestricted future questions. If two distinct histories produce identical memory, any later question distinguishing them cannot be answered from that memory alone. The claim therefore needs an explicit question family, an error tradeoff, and a statement of which distinctions are sacrificed.

### The first experiment should decide whether this deserves a project

Use two complementary data panels. [SensorQA](https://arxiv.org/abs/2501.04974) supplies human-created questions over daily-life sensor histories, giving a useful check against a purely invented query workload. A separate machine or waveform panel should contain channel relationships at the timescale being studied. FactoryBench/FactoryWave and the industrial datasets in the application notes are candidates for a data audit. Existing annotations must be inspected before claiming they support a particular event, relationship, or temporal precision.

Human-activity questions cannot substantiate a claim about millisecond machine transients. Concatenated clips and synthetic event modifications should be labeled as constructed evaluation streams. Raw-history query answers should be independently audited. Questions cannot demand facts that the original recording never measured.

Run ingestion causally with the test questions hidden. Enforce a total byte budget including timestamps, indexes, metadata, text, embeddings, residuals, and any archive the query engine can access. Keep query interpretation and answer generation identical across arms. First evaluate machine-readable queries to isolate retention; natural-language parsing is a subsequent layer.

Required competitors are a raw ring buffer; uniform reservoir; multiresolution/wavelet summaries; a strong numeric codec; anomaly-triggered snippets; a compact embedding archive; an uncertain event-interval table; the hybrid table/summary/reservoir baseline; and a task-reward streaming selector modeled on SVMemAgent. Use appropriate sensor encoders for all sensor arms and charge their work. Full raw history with the same answer engine is an attainable-information reference. An offline selector that sees the question is an explicitly privileged upper reference.

Test familiar questions, held-out temporal compositions, changed family frequencies, and rare-event questions separately. Include paired histories with similar per-channel statistics but different ordering or cross-channel relations. Those pairs diagnose a failure mechanism; real unmodified histories determine whether it matters in practice.

Measure answer error, count and duration error, retrieval of the relevant intervals, and rare-event recall at equal bytes. Also measure ingestion work and query latency. Report all errors against the full-history reference so language-model mistakes do not masquerade as retention loss. If the raw reference cannot answer the task reliably, first fix or narrow the task.

Stop the proposed algorithm if the hybrid baseline matches its quality/resource frontier, if the advantage requires knowing the test question during retention, or if its gain disappears under an independently defined question mix. Stop the broader edge-storage motivation if a simple codec retains the required complete history cheaply at the intended deployment scale. These are substantive ways for the idea to fail.

For a promising pilot, I would want a repeatable advantage at several byte budgets on both data panels, including changed question families, without losing ordinary queries. A proposed planning threshold is either roughly 20% fewer bytes at matched answer quality or a clearly useful reduction in relational-query errors at equal bytes. This is an experiment-selection threshold, not a prediction or publication criterion. Select it before the confirmatory study and report uncertainty across users/machines and runs.

### Where an FPGA could matter

An always-on front end can compute multirate transforms, maintain interval candidates, and write selected residual blocks while an occasional CPU or remote model handles questions. This creates a hardware question about the cost of preserving future utility at ingestion time. It does not require accelerating another large vocabulary decoder.

The rate must justify fabric. Sixteen 16-bit channels at 100 ksample/s generate 3.2 MB/s, or 11.52 GB per hour before metadata and compression. This is an illustrative workload calculation, not a measured deployment or evidence that an FPGA beats a CPU. Low-rate wearable inputs may be handled efficiently by a microcontroller or CPU. A later board comparison should include an optimized CPU implementation and, where appropriate, an existing edge accelerator.

The KR260 would initially receive network-replayed recordings. Actual acquisition needs suitable external sensors or converters. Replay can validate ingestion throughput and representation cost; it cannot establish sensor duty-cycle savings. Measure whole-system power and storage traffic before claiming energy value.

## Second branch: acquiring the evidence needed to learn later

An adaptive sampler may reduce a channel because its current model regards it as uninformative. After a change, the missing channel can become decisive. A delayed label then arrives after the event window has passed. Requesting that channel now cannot recover the missing past, and retaining a feature vector helps only if it contains the needed distinction.

The niche worth testing is the interaction of **window availability, sensor warm-up/window-fill time, delayed feedback, and bounded retention**. The baseline acquisition tree should receive the same sample ages, pending windows, and cost information. Simply adding random exploration or a replay buffer is insufficient novelty.

[Beyer et al., 2020](https://link.springer.com/article/10.1007/s12243-020-00775-2) already studies active feature acquisition under drift. [UFODT, IJCAI 2023](https://www.ijcai.org/proceedings/2023/0463.pdf) already joins acquisition planning, online learning, and exploration under concept drift. [Label Delay in Online Continual Learning](https://arxiv.org/abs/2312.00923) supplies delayed-feedback learning controls. [AdaSense](https://arxiv.org/abs/2006.05884) and [MMEdge](https://arxiv.org/abs/2510.25327) supply strong sensing/inference system controls.

A causal replay can compare those combinations with a joint acquisition/retention policy at the same expenditure. Crucially, release neither a sample nor its label before it becomes available. Compare fixed exploration plus delayed-label replay before constructing a new learner. The claimed mechanism fails if compact frozen features remove the retention bottleneck or a delayed acquisition tree with ordinary storage matches the proposed policy. This is a good cheap experiment, though the algorithmic novelty risk remains high.

## Why I downgraded the more adventurous alternatives

Manual-to-experiment reasoning initially looked strongest. Further searching changed that assessment. [DX2024](https://drops.dagstuhl.de/entities/document/10.4230/OASIcs.DX.2024.31) already generates physical diagnostic models from diagrams and descriptions. [Lu, Itard, and Saelens, 2026](https://repository.tudelft.nl/record/uuid%3A73d7e7ad-75fd-45ba-8813-a77d4dcc70f9) directly targets automated HVAC diagnostic Bayesian-network construction with retrieval-augmented language models. [BMD](https://arxiv.org/html/2610.25747) already links proposed model families, numerical fitting, and information-based experimental design.

A residual study could ask whether documentation-derived models transfer to interventions on entirely new equipment families with less expert correction. Every competitor must receive the same manuals, component library, topology information, fitting tools, and experiment budget. A deterministic component assembler could win. The contribution would have to concern demonstrated intervention-model transfer; documentation-to-model generation is already occupied.

The November 3/5 preprint [Treating the Symptom, Missing the Cause](https://arxiv.org/abs/2611.04473) also directly studies the gap between successful repair and correct diagnosis in synthetic regulatory systems. That distinction is interesting, but it is already a current research subject.

For the optimization wildcard, [Hamakawa et al.](https://doi.org/10.1038/s41467-026-73725-6), published June 16, 2026, already combines embedded Ising hardware, problem-transfer compression, and learned parameter prediction for changing optimization problems. [Learned local MIS updates](https://arxiv.org/abs/2505.13754) and [classical dynamic neighborhood repair](https://arxiv.org/abs/2407.06912) weaken the obvious incremental-repair extension. A specific new workload could still be worthwhile, but I found less reason to select it now.

## What the agent discussion actually resolved

The architecture reviewer initially favored acquisition with delayed labels, then ranked diagnostic transfer highest for scientific upside. The application reviewer also initially preferred diagnostic transfer. The direct HVAC predecessors caused the application reviewer to withdraw that broad novelty recommendation and favor the irreversible-acquisition experiment. The frontier reviewer ranked future-question memory highest for the value of a broad-capability experiment, with acquisition second and diagnostic transfer third.

The shared conclusion was that generic combinations are heavily occupied. There was no consensus that a niche was cleared. The useful disagreements concern the best first discriminator: a retention/answer-quality experiment, an acquisition/feedback interaction experiment, or a difficult documentation-transfer evaluation. The preferred memory direction above is my final choice because it asks about a capability people can recognize and has strong, inexpensive controls capable of rejecting it.

The final targeted search also found SVMemAgent and SAVEMem. Their query-reward and pseudo-question mechanisms further narrow any generic memory-policy claim. They are incorporated above rather than treating an earlier favorable ranking as settled.

## Value assessment and a bounded next step

The potential value is **moderate to high if the new capability is demonstrated**, with high novelty risk at present. Continuous sensor systems increasingly have richer models and changing questions, while retained evidence is finite. A finding about which representations preserve useful reinterpretation could transfer across industrial recorders, wearables, and mobile robots. That breadth is a motivation to test, not evidence of market demand.

A new task setting and benchmark alone would be a limited contribution unless it reveals a reproducible failure that current evaluations miss. A retention mechanism that materially improves the quality/byte frontier under independently defined query shift could support a stronger systems or representation paper. A measured FPGA advantage would add an architecture contribution. A dashboard around an embedding archive would have modest research novelty given the sources above. Publication venue and impact cannot be estimated reliably before the effect is measured.

I would fund a small software study before choosing a new hardware architecture: audit the data, freeze a temporal question family, implement the uncertain interval-table/summary/reservoir baseline, and measure how much capability is lost under storage pressure and changed questions. Compare a task-reward selector next. Develop a complementary-evidence allocator only if those results reveal the proposed failure. Run the acquisition/feedback branch as an alternative if the memory baseline already solves the task.

This produces a concrete decision about a new edge intelligence capability. The current repository remains useful as an experimental platform, while the research question has room to determine the eventual model and hardware.
