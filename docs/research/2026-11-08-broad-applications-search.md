# Three application directions beyond command gates

November 8, 2026. This search follows a separate audit of Claude's value review and the local simulator. I considered three different decisions an edge system could make about physical evidence. It can choose an experiment to learn what is wrong, decide what to sense for an already stated question, or choose what to remember before the question is known. Each changes the problem being solved rather than adding another execution check to an existing language-model output.

Follow-up primary checks found direct predecessors for the initially attractive manual-to-diagnostic-model direction as well as active diagnosis, sensor acquisition and future-query memory. No candidate in this document is established as a new research niche. The best cheap discriminator is the physical acquisition/label-delay interaction discussed in the final appendix. A more ambitious diagnostic study would need to demonstrate held-out configuration transfer of intervention predictions beyond existing manual-to-model systems.

The strongest recent papers narrow all three directions. The candidates below are hypotheses to test, with specific comparisons that could reject them. No model, dataset or board experiment was run for this document.

## 1. From equipment knowledge to a useful physical experiment

A technician sees low flow. Possible causes include an obstructed line, a weak pump, a leaking bypass or a biased sensor. Another paragraph of explanation may add no evidence. Temporarily choosing a different operating point or reading a second sensor can separate the hypotheses. The interesting role for language is to make a newly documented piece of equipment diagnosable with less manual model authoring.

Consider an assistant given a new pump assembly's manual, its component arrangement and available test interfaces. It instantiates competing mechanisms and predicts what each permitted test would measure. A numerical planner selects tests and updates beliefs from actual outcomes. The model is evaluated on whether its interpretation of the new assembly produces informative tests and correct predictions, rather than the persuasiveness of its explanation.

**What is already established**

- Heirung and Mesbah's 2019 review covers input design that improves fault distinguishability under parameter, initial-state, disturbance and measurement uncertainty, together with physical and operational constraints. These are the foundations of active fault diagnosis. [Input design for active fault diagnosis](https://par.nsf.gov/servlets/purl/10180014)
- Awasthi, Palmer and Bollas jointly select sensors and discrete or continuous test conditions for uncertain systems using mixed-integer nonlinear optimization and information measures. Their three-tank case already defeats a claim of novelty from “choose the next sensor and test under uncertainty.” [Optimal test and sensor selection, 2020](https://www.sciencedirect.com/science/article/pii/S0959152420302419)
- Massa and Paulson use active deep learning to locate minimally invasive inputs that separate fault models in nonlinear systems under bounded uncertainty, using reachability-based safety/separability oracles. A learned low-cost input selector and a physical safety constraint are also established. [Optimal input design for guaranteed fault diagnosis, 2024](https://www.sciencedirect.com/science/article/pii/S0967066124002776)
- Cost-sensitive troubleshooting predates modern language models. Heckerman, Breese and Rommelse choose observations and repairs based on expected repair cost. Repair actions that change the state and yield information are part of that lineage. [Decision-Theoretic Troubleshooting](https://www.microsoft.com/en-us/research/publication/decision-theoretic-troubleshooting/)
- ACTMED already combines language models with Bayesian experimental design for sequential clinical tests. BMD and Model Discovery Agent already combine language-model hypotheses, numerical posterior inference and experiment selection, including expansion of the hypothesis class. These are essential method baselines even when the target domain is industrial equipment. [ACTMED](https://arxiv.org/abs/2510.18988) · [BMD](https://arxiv.org/html/2610.25747) · [Model Discovery Agent](https://arxiv.org/abs/2608.09696)

**The current diagnostic benchmarks leave a useful test opportunity**

CoffeeBench exposes an espresso-machine simulator with nine fault modes, eight sensor snapshots and four actions. Its methods explicitly give correct/incorrect feedback for every diagnostic guess, allowing elimination independently of physical evidence. It deliberately provides snapshots to avoid confounding from time-series reasoning. This makes it useful for a paired change in feedback and observation design, but its original results cannot establish diagnostic performance without that answer feedback. [CoffeeBench methods](https://arxiv.org/html/2610.19291#S2)

DiagFlowBench contributes 50 anonymized real-manual troubleshooting graphs and 838 paired on/off-procedure conversations. It can support grounding and procedure interpretation checks, while a simulator or rig is still required for physical experiment outcomes. DiagnosticIQ already checks rule-to-action recommendation and condition-inversion sensitivity. A new “LLM for troubleshooting” benchmark alone would face both precedents. [DiagFlowBench repository](https://github.com/aixpert-rug/DiagFlowBench) · [DiagnosticIQ](https://arxiv.org/abs/2605.08614)

FactoryBench adds industrial telemetry and state/intervention/counterfactual/decision questions across robot faults. It is a useful external evidence-understanding check, with deterministic structured formats available. Offline telemetry cannot supply the outcome of an arbitrary newly chosen physical test without an identified causal simulator. [FactoryBench](https://arxiv.org/abs/2605.07675)

**A direct predecessor narrows the original proposal.** Lu and Itard's P&ID-to-code work already uses documentation and diagrams to generate diagnostic Bayesian networks for HVAC. The B4B primary report identifies time- and knowledge-intensive network construction as an industrial bottleneck and describes automated generation tested on an actual building. Lu, Itard and Saelens's 2026 RAG paper explicitly targets the same manual-effort barrier and reports improved network structural quality. Automated diagnostic model construction from equipment knowledge is therefore established. [B4B primary report](https://brains4buildings.org/wp-content/uploads/2026/03/B4B-WP1-D1.01-Real-time-implementation_FINAL.pdf) · [2026 author publication](https://research.tudelft.nl/en/publications/retrieval-augmented-llm-framework-for-robust-automated-generation/)

**A testable residual thesis**

> When a component arrangement or control mode changes, can an automatically instantiated diagnostic model preserve the predictions needed to select a genuinely discriminating intervention, and how does that transfer compare with existing P&ID-to-DBN generation and numerical model-discovery methods?

This is a narrower prospective evaluation question. Classical planners can select excellent tests once candidate models and observation interfaces are correct, and prior language-model work already aims to reduce model construction effort. The candidate must show a previously unmeasured transfer regime or a concrete method improvement. Variation in component arrangement, control mode and interface meaning should change predicted intervention outcomes while retaining the same vocabulary. Merely adding a planner after an automatically generated DBN would be an integration.

Treating the Symptom, Missing the Cause further narrows the question. Its November 5 preprint uses synthetic biological regulatory systems to separate successful rescue from correct diagnosis and identifies difficulty predicting outcomes under competing causes even after informative experiments were observed. A new industrial analogue needs new transfer evidence or an effective mechanism, rather than restating that distinction. [Primary preprint](https://arxiv.org/abs/2611.04473)

The research artifact should make a component hypothesis executable. It should declare the affected component and mechanism, observable channels and units, test preconditions, predicted response or response family and unknown parameters. Numerical fitting estimates the unknowns from calibration observations. Supplying a valid-looking record provides no credit without correct intervention predictions on independently generated episodes.

**Experiment and baselines**

Use a small component library for pumps, valves, bypasses, thermal elements and sensors. Build multiple assemblies with held-out arrangements and independent engineering documentation. An expert signs off the physical model, available tests, cost model and fault mechanisms before the semantic method sees the test configurations. Use public manuals where licensing permits or independently authored engineering descriptions that truthfully derive from the physical library. Synthetic descriptions should remain labeled as synthetic.

Initially provide ambiguous nominal observations, then allow costed measurements or short interventions. Give no per-guess fault-name answer. A final diagnosis is scored once, or the agent chooses a specified unresolved outcome. Track physical test duration, disruption, diagnostic success, intervention prediction error and expert correction time. Keep correct diagnosis and successful restoration separate because a repair can restore service while removing evidence about the original cause.

Compare all of the following under the same experiment engine and costs.

- Expert-authored mechanistic models, measuring the configuration effort as well as the resulting quality.
- A component-library/topology assembler with rules and no language model.
- Retrieved manual text fed to a direct language-model agent.
- BMD/MDA-like model proposal from numerical observations and domain context.
- Manual-conditioned executable hypotheses with the unchanged numerical planner.
- A full-model/full-observation reference for attainable diagnosis.

The most informative ablations mask the manual, swap in a plausible but incorrect assembly manual, anonymize component names, and change the true topology while retaining the same component vocabulary. An advantage that disappears when names are anonymized may be memorized equipment association. A model that ignores a mismatched manual has not demonstrated manual-conditioned transfer. Include withheld fault combinations and nuisance changes only after the topology and procedure interpretation work.

Record both the time required to build a deployable diagnostic model and its downstream experiment performance. Count all language-model calls, rejected hypotheses, numerical fits and human edits. If a deterministic component assembler is as capable with the same engineering inputs, the semantic-model generation claim fails. If direct language reasoning improves over an unaided model but stays below a specialist, there is also no integration gain. A recent five-dataset study reports exactly that risk for implicit LLM/specialist integration. [When LLMs Sit Above Diagnostic Tools](https://arxiv.org/abs/2610.05031)

This direction has application value because translating existing engineering knowledge into working diagnostic models remains laborious. Its scientific novelty is less certain after the direct HVAC predecessors. A rigorous transfer study could still identify which documented relationships support valid interventions and which require numerical calibration. The programmable-logic board has no necessary role in that initial result.

## 2. A sensor that acquires evidence for the question the user actually asked

A user asks, “During the next hour, count pump starts followed by a brief pressure collapse, and save the vibration around those cases.” The system must choose channels, resolution, temporal operators and retained windows before the events happen. A generic downsampler may preserve mean-square signal fidelity while losing the short event that determines the answer.

The research opportunity is an acquisition plan optimized for the downstream question. It differs from retrospective sensor QA because sensing itself is a decision. The natural-language front end is useful when questions vary and combine learned event concepts with numeric and temporal predicates.

**Closest precedents and the remaining question**

TinyDB already performs acquisitional query processing, integrating query predicates, sampling and energy decisions in sensor networks. BBQ chooses acquisitions using probabilistic models and query error requirements. Therefore, natural-language input plus an existing query engine is an interface implementation rather than a new sensing method. [TinyDB author reading list](https://telegraph.cs.berkeley.edu/tinydb/reading.htm) · [Model-Driven Data Acquisition in Sensor Networks](https://ai.stanford.edu/~guestrin/Publications/VLDB04/vldb04.pdf)

SensorChat already decomposes a question, searches sensor embeddings and performs explicit query functions before answer assembly. LaSTR already learns language-to-time-series segment retrieval. Neither title can serve as a new contribution by adding an industrial example. [SensorChat](https://arxiv.org/html/2502.02883) · [LaSTR](https://arxiv.org/abs/2603.00725)

Agentic LLM Compilation of Adaptive Sampling Policies already compiles a compact causal policy offline and compares candidate policies through deterministic trace evaluation. Its reported objective is reconstruction error against a sampling-duty proxy. Semantic Sensing also optimizes task-relevant information under sensing constraints, using an OFDM target-sensing example. These precedents make the objective and workload the crucial distinction. [Adaptive sampling compiler](https://www.mdpi.com/1424-8220/26/17/5519) · [Semantic Sensing](https://arxiv.org/abs/2603.29102)

**Possible thesis**

> Optimizing an acquisition plan for compositional temporal questions preserves answer-critical brief events at lower sensing/storage cost than optimizing signal reconstruction or fixed activity classification.

The method could factor the problem into explicit temporal/numeric operators and learned local sensor predicates. A planner chooses among channel subsets, detector rates, burst capture windows and retained representations. The novelty would have to be a formulation or algorithm for this joint choice and convincing transfer to unseen compositions. A language-model-generated sample-rate table is already covered.

Use held-out robot runs from FactoryWave/AURSAD/voraus-AD for industrial traces and SensorQA/ExtraSensory for human activity questions. Physical acquisitions are emulated by exposing only the samples the policy requests. This gives a fair software experiment before power measurements. Existing datasets do not automatically label every proposed temporal event. Restrict the first study to questions with trace-derived deterministic labels and independently audit those labels.

At equal acquired samples and retained bytes, compare fixed-rate sampling, classical adaptive sampling, reconstruction-optimized policy, query-blind learned policy, explicit query optimization with hand-translated queries, and language-to-query planning. The hand-translated arm isolates the acquisition algorithm from language errors. A full-resolution trace engine supplies the answer reference.

Report complete answers, missed rare events, timestamp/count/duration error and acquisition costs. Use held-out operator compositions and changed channel aliases. Treat signal sampling duty as a proxy until actual sensor, compute and radio energy is measured. Low-frequency environmental or minute-labeled phone data cannot substantiate a claim about MHz acquisition.

The primary risk is that the supported question family admits an exact conventional query plan with little room for learning. That would still identify a useful efficient system, while narrowing the ML contribution. A second risk is numerical evidence neglect. COMMON-TSQA already tests perturbations and unsupported reasoning in time-series QA, so equal scores with the series removed should fail this experiment's evidence-use check. [COMMON-TSQA](https://arxiv.org/html/2610.05686)

## 3. Remember the evidence before knowing the future question

The second direction knows the question before collecting data. Here a wearable or machine recorder runs all day and learns the question later. The device cannot retain everything. A retrospective question may depend on a rare transition, order of events or brief anomaly that a generic summary discarded.

For example, “Did the pressure dip before the operator opened the bypass, or after?” needs temporal evidence. A memory of “one abnormal pump event” loses the distinguishing information. Embedding similarity can preserve activity identity while merging events whose order or duration changes the answer.

**What prior work already supplies**

SensorQA offers 5.6K human-created questions over long-duration sensor data. Its source data come from ExtraSensory, with smartphone/watch contexts from 60 people collected in everyday settings. This supplies a useful, less template-driven question distribution, with the source's observational labels and sampling limits retained. [SensorQA](https://arxiv.org/html/2501.04974) · [ExtraSensory primary paper](https://extrasensory.ucsd.edu/papers/vaizman2017a_pervasiveAcceptedVersion.pdf)

LifeDialBench explicitly enforces an online temporal evaluation and finds sophisticated memory systems can lose to a simple RAG baseline. StreamMem already studies fixed-size, query-agnostic streaming video memory. Both preclude a broad novelty claim about answering future questions from bounded streaming memory. [LifeDialBench](https://arxiv.org/abs/2604.11182) · [StreamMem](https://arxiv.org/abs/2508.15717)

Memento already uses an MCU, persistent storage and vector matches to transmit recurring sensor observations by compact reference. It evaluates communication/energy versus accuracy on image/radar workloads. A new project must preserve the temporal distinctions and future-query capabilities that matter in its declared task, beyond reusing similar observations. [Memento](https://arxiv.org/abs/2610.19227)

The conceptual memory problem is older still. RoboMem explicitly considers unknown future queries over long-term robot sensor history, storing compact preprocessed information and selectively reprocessing relevant frames. Palpanas et al. support user-defined age-dependent fidelity in streaming summaries. Matias and Urieli optimize synopses against weighted query workloads, so measuring error over likely questions instead of raw signal reconstruction is also established. [RoboMem](https://arxiv.org/abs/2003.10553) · [User-defined amnesic summaries](https://helios2.mi.parisdescartes.fr/~themisp/publications/tkde08.pdf) · [Workload-weighted wavelet synopses](https://theory.stanford.edu/~matias/papers/mu-www-synopses-05.pdf)

TimesJev learns time-series compression with sufficiency and realizability objectives and a gating mechanism. The paper supplies another close precedent for learned task-preserving representation. These sources substantially lower confidence that the candidate below, in its generic form, offers a new method. [TimesJev](https://arxiv.org/abs/2610.26002)

**Possible thesis**

> A memory allocator trained to preserve distinctions among possible future temporal questions retains rare-event and ordering evidence more efficiently than reconstruction-, novelty- or caption-based retention at the same byte budget.

Treat this as a testable performance question. The possible residual concerns uncertain learned sensor predicates and their temporal composition under a changed future-question distribution. Existing numeric synopses assume a specified numeric query/error model, while sensor-language systems must also contend with recognition uncertainty and concept drift. This distinction does not itself establish novelty. Compare against the older summary algorithms plus an ordinary learned event detector, and retain the simple combination if it performs as well.

A possible representation combines numerical summaries with explicit interval structure and a small budget of selected raw snippets. Retention should depend on how different possible histories would answer different questions. It should not simply retain whichever events a language model calls important. This gives an operational meaning to information loss and supports an answerability estimate when evidence has been discarded.

Run streaming ingestion with questions hidden until after the queried interval. Train on question families from training users/machines, hold out combinations and subjects, and add a separate distribution-shift panel for changed question frequencies. An offline compressor that sees the future question belongs only as an upper reference.

Compare raw ring buffers, uniform reservoir, fixed multiresolution summaries, workload-weighted and amnesic summaries, reconstruction compression, novelty/anomaly-triggered retention, embedding archive with simple RAG, SensorChat-like querying, and a bounded-memory learned approach. Account for all indexes, text, metadata and retained raw data. Keep the answer model identical across memory arms.

Measure answer correctness, interval retrieval and order/count/duration fidelity versus retained bytes. Also report rare-event strata and errors on claims where evidence is absent. Test question-independent near-duplicate streams with different event order or duration. Full raw evidence plus the same answer engine estimates the memory loss, while an exact trace evaluator isolates answer-model errors where the task permits it.

This is an attractive systems/representation question, but the prior art is broad and strong. A useful first test is whether structured intervals plus simple sampling already dominate learned memory. If so, the question remains valuable and the elaborate memory model is unnecessary. A quantitative win must survive simple RAG and multiresolution-statistics baselines.

## Selection and the concrete next decision

| Direction | New scientific variable | Strongest baseline that could defeat it | First convincing result |
|---|---|---|---|
| Manual-conditioned diagnostic experiment models | Semantic transfer across unseen equipment configuration | Expert model and deterministic topology/component assembler, with identical numerical experiment planner | Lower model-authoring effort while retaining diagnosis and test efficiency |
| Question-directed acquisition | Answer distortion under sensing/storage budget | Classical acquisitional query optimization with hand-translated query | Better brief-event/temporal answers at matched sample and byte budgets |
| Evidence memory before future queries | Which learned semantic/temporal distinctions survive bounded retention | RAG, weighted/amnesic summaries plus learned event detector, fixed-budget raw sampling | Better held-out temporal answers at equal total bytes, beyond a simple combination of known methods |

The diagnostic direction is suitable for an ambitious application study if the specific transfer question remains after inspecting the full HVAC generation artifacts. First determine whether an existing P&ID-to-DBN or MDA-style method already handles the proposed changed topology. Generic active diagnosis and automatic model construction are established. Any new claim needs a measurable residual beyond their combination.

A minimal diagnostic pilot could use two familiar component arrangements for development and an independently authored third arrangement for a sealed study. Those few configurations establish feasibility and failure types, not broad statistical generalization. A later study should hold out whole configuration families and document human model-building effort. Before a larger implementation, require the compiled model to beat the closest existing generated-model method on intervention predictions and match a useful fraction of expert-model diagnostic efficiency. Register the fraction and practical engineering-time target after the pilot exposes the attainable scale.

The diagnostic direction has an identifiable engineering bottleneck and direct competing solutions. The acquisition and memory directions also have dense prior art. The search did not establish an unpublished algorithm or a demonstrated advantage. The final discussion favors a cheap interaction test for acquisition and delayed labels, with rejection by simple existing controls treated as a useful outcome.

## Source depth

Relevant method sections were inspected for CoffeeBench, SensorChat, SensorQA, FactoryBench, BMD and COMMON-TSQA, and the official DiagFlowBench release was read. Classical active diagnosis checks used the primary 2019 review and publisher method/abstract previews for the 2020 and 2024 papers. The adaptive-sampling compiler was accessible through indexed primary article text after direct retrieval returned an access error. Other cited recent works were primary abstract screens. No external benchmark installation or source-code execution was performed.

## Discussion appendix after cross-examination

The parallel architecture review proposes joint acquisition, delayed-label adaptation and representation retention as a preferred cheap experiment. Its strongest point is temporal availability. A spectral feature can require a window that has already passed, and a late label cannot restore raw samples that were never collected. The relevant task is how much present acquisition should support future learning, when obtaining current predictions cheaply changes the future training set. [Architecture review](2026-11-08-broad-hardware-search.md)

**The generic motivation already has direct prior art.** Žliobaitė et al. explicitly identify the confident-wrong blind spot of boundary-focused active learning under drift and study dynamic budgets and randomization. Castellani et al. study unknown and time-varying verification latency under drift and choose requests while earlier labels are still pending. Beyer et al. and UFODT study changing feature acquisition and online learning. These remove novelty from “explore despite confidence” and “request useful examples while waiting for delayed labels.” [Drifting-stream active learning](https://doi.org/10.1109/TNNLS.2012.2236570) · [Verification latency](https://arxiv.org/abs/2204.06822) · [Beyer et al.](https://aiml-research.github.io/files/20.AnnalsOfTelco.ActiveFeatureAsquisitionStreams.pdf) · [UFODT](https://www.ijcai.org/proceedings/2023/0463.pdf)

I would challenge the proposed interaction on five grounds.

1. **A retained feature may dissolve the retention problem.** If a frozen encoder gives a compact vector and only the head adapts, store that vector until its label arrives. A full raw waveform is unnecessary for that update. The candidate must show a regime where acquiring an adequate representation is itself expensive or where adapting the encoder makes old compressed features inadequate. Count retained bytes and recomputation for the simple vector queue before designing a learned retention mechanism.
2. **Physical irreversibility can be simulated accidentally.** Masking a field in a prerecorded row does not demonstrate channel warmup, phase-dependent window completion or lost transient evidence. Identify a real sensor/task in which those constraints determine which examples exist. Otherwise the experimental modification is a delayed-label AFA wrapper.
3. **Delay is sometimes the dominant information limit.** Under a change in label meaning with no change in the observable input distribution, more unlabeled acquisition cannot identify the new mapping before feedback arrives. Extra sensing may help covariate or placement shifts and fail on concept changes. Report the kind of drift and delay relative to its persistence, since obsolete labels can be harmful even when retained perfectly.
4. **The evaluation population can shrink with sensing.** A method that never observes a difficult event can look accurate conditional on its retained examples. Score against the complete independent event timeline, including missed events, and keep coverage visible. Time-window overlap requires subject/session split boundaries before any windows are built.
5. **Acquisition is an intervention in the training distribution.** A JMLR study formalizes evaluation assumptions for time-varying feature acquisition, including whether acquisition affects underlying features and whether acquisition choices depend only on observed variables. Replay can be a clean full-information testbed when these assumptions hold. It should not imply field performance from selectively observed retrospective records with no support for skipped acquisition decisions. [AFA performance evaluation](https://jmlr.org/papers/v26/23-1635.html)

**A compelling rejection test** gives a delayed-update UFODT or comparable AFA learner the same acquisition budget, fixed randomized exploration, quantized feature queue and a prior delayed-label replay sampler. Compare equal total bytes, label budget and compute over independently collected chronological shifts. Keep labels hidden until their arrival and mask all unacquired samples from the policy. If that simple combination matches the joint method, or if the same advantage remains when warmup/window-expiry constraints are removed, reject the claimed new interaction. If retaining all acquired feature vectors is comfortably affordable, reject raw-retention scarcity as the central application premise. Physical energy claims need sensor duty measurements as well.

The qualitative value is real when a battery-limited or intermittently connected sensor must remain adaptable for months and human-confirmed labels arrive after events. Saving training-relevant observations can prevent an energy optimization from making its own model permanently uncorrectable. However, this value is specific to a resource regime. A mains-powered machine with cheap local flash, modest channel rates and an immutable feature extractor may be better served by retaining all relevant vectors. Selecting a battery/warmup/window-limited deployment is part of validating the application, rather than a reason to assume programmable logic is needed.

After the additional HVAC and causal-reasoning primary checks, my ranking for the next discriminating experiment is as follows.

| Rank for next experiment | Candidate | Why | Observation that would compel rejection |
|---|---|---|---|
| 1 | Acquisition, delayed feedback and representation retention | A narrow but falsifiable interaction can be tested cheaply, with practical value in a physically constrained sensing regime | Existing delayed AFA plus exploration and feature retention reaches the same frontier, or realistic workloads have no meaningful acquisition/retention scarcity |
| 2 | Changed configuration to diagnostic intervention predictions | Tests a narrower downstream transfer property beyond already established P&ID/documentation-to-DBN generation | Existing generated-DBN/MDA method or deterministic component assembler transfers equally well with comparable engineering effort |
| 3 | Memory for future sensor questions | Directly useful to users, but highly occupied from numeric synopsis work through RoboMem and modern sensor/video memory | Weighted summaries plus ordinary event detection/RAG match the learned memory at the same full byte budget |

The delayed-acquisition study can use existing chronological labeled streams and expose whether a real interaction exists. The changed-configuration diagnostic study has higher dataset/expert burden and direct competing methods. Its first pilot should test intervention predictions before a large assistant is built. Neither merits a publication or novelty claim until the closest prior method and strongest simple control have been run.
