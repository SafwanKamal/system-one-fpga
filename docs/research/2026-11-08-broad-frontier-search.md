# Broader frontier search beyond the current gate

November 8, 2026. This is a discovery and adversarial review of three directions in edge intelligence and one wildcard in learning-assisted optimization. The starting point was the current repo and the latest Claude reports under research_notes and reports. This round deliberately searches for new scientific questions about information, adaptation, and computation.

This is a targeted primary-source screen. For most papers I inspected the author or venue abstract. I inspected selected technical sections for the closest active-feature, sensing/fusion, and dynamic-graph precedents. Several publisher pages were inaccessible, and those leads are identified accordingly. The proposed gaps below are hypotheses for experiments and a further novelty audit.

The most promising new question is **when an edge system should buy a new observation, spend more computation on existing observations, or update its model**. The distinction matters when sensing conditions change. More inference cannot recover a signal that was never acquired, and more adaptation can turn an unusual fault into the learned normal. The individual techniques are mature. A contribution requires a concrete coupled problem and a measured advantage over strong combinations of existing methods.

## Direction 1. Allocate effort between measurement and computation during change

**Application.** A battery or bandwidth constrained device monitors several channels. Most of the time a cheap stream suffices. After a transition, a different channel, sampling rate, or reference measurement may be more informative than a larger classifier. Examples include wearable activity transitions, a machine changing operating speed, or a sensor becoming less reliable.

**Research question.** With one fixed expenditure budget, can a controller learn when additional data is more useful than additional inference, while continuing to discover transitions outside its currently favored channel? Include acquisition latency and delayed feedback, rather than representing every feature as immediately available.

A concrete candidate has three choices at each decision point. It can infer from the current evidence, request one additional channel/window/reference, or use a limited update budget. The controller observes a small current feature state, sample ages, pending acquisition times, and past expenditure. Training and evaluation use causal observations. An optional low-rate exploration schedule is a baseline and part of the candidate comparison.

### What already kills the broad idea

- **AdaSense, DAC 2020** jointly selects sensing, features, and classification configurations on an accuracy/power frontier. It reports sensor power reductions with a small recognition loss. Adaptive sample rates and joint sensing/classifier tuning are established. [Author paper](https://arxiv.org/abs/2006.05884)
- **Active feature acquisition on data streams under feature drift, 2020** directly studies acquisition when feature utility changes. This is a compulsory baseline. The publisher metadata and institutional record were available, while the author PDF was bot-blocked. [Publisher](https://link.springer.com/article/10.1007/s12243-020-00775-2)
- **Efficient Online Decision Tree Learning with Active Feature Acquisition, IJCAI 2023** nests an acquisition planner inside online posterior learning, has costly features, and extends to concept drift. Its base setup receives each label after predicting the current point. Discounting and exploration already address changing feature usefulness. An uncertainty-only sampler becoming blind is insufficient novelty. [Conference paper](https://www.ijcai.org/proceedings/2023/0463.pdf)
- **Online Allocation of Sensing and Computation in Large Graphs** jointly chooses sensors and compute nodes for vehicle tracking, using cheap measurements to guide allocation. It already measures delay, communication, and measurement costs in numerical experiments. [Author paper](https://anrg.usc.edu/www/papers/IoBT_Sensor_Selection___Task_Scheduling.pdf)
- **ADMN, NeurIPS 2025** reallocates network depth across modalities as input noise and compute availability change. Simply routing more compute to a better channel has a close neural implementation. [Author manuscript](https://arxiv.org/abs/2502.07862)
- **MMEdge, SenSys 2026** pipelines sensing and encoding, jointly selects sensing/model configurations under latency constraints, and speculatively skips slower modalities. It includes a UAV testbed. A generic joint sensing and inference scheduler would closely overlap. [Author manuscript](https://arxiv.org/abs/2510.25327)
- **Not all those who drift are lost, 2025 preprint** models sensor response probabilistically and schedules calibration using uncertainty, with dissolved-oxygen sensor experiments. Active reference calibration also has direct prior art. [Author preprint](https://arxiv.org/abs/2506.09186)
- **Integrating Adaptive Sampling into Deep Learning-Based Human Activity Recognition, 2026** trains one continuous-convolution checkpoint for multiple rates and selects activity-specific sampling. The inspected author text describes frequency-dependent temporal support. A multirate model alone would add little. [Author paper](https://ubi29.informatik.uni-siegen.de/usi/pdf/ubi_iwoar2026c.pdf)

### Candidate gap after those objections

Study **joint acquisition and adaptation with physical acquisition delay, sparse delayed labels, and changes in which channel carries the event**. The useful outcome is timely event recognition, with missed transitions and long observation gaps visible. The inspected IJCAI base model reveals the label each round, while MMEdge centers current sensing/compute configurations and early fusion decisions. This observation identifies a testable intersection. It does not establish that all combinations have been unstudied.

The first algorithm can be simple. Use a frozen low-cost encoder and compare a small contextual decision policy with a discounted acquisition tree plus a fixed update rule. A learned controller must beat that combination. Allow the comparator to use the same ages, history, and acquisition-cost information.

**First experiment.** Replay complete chronological PAMAP2 sessions. The real recordings have three 100 Hz IMUs and an approximately 9 Hz heart-rate monitor, providing a useful multirate starting point. Preserve subject separation and missing values. Hide channels until the acquisition policy pays to obtain them. Compare all-channel fixed inference, optimized periodic sampling, random or round-robin exploration, discounted feature acquisition, adaptive model depth, and the joint controller. Add explicitly synthetic transport delays and channel-quality changes as separate stress arms. [Dataset documentation](https://archive.ics.uci.edu/ml/machine-learning-databases/00231/readme.pdf)

Report transition detection delay, event recall, minority-activity recall, macro F1, acquisition count, acquired bytes, inference/update time, and budget violations. A channel the simulator has not acquired cannot influence decisions. Tune every policy on separate sessions, and match the total budget.

**Kill tests.** Reject the algorithmic claim if periodic exploration plus a discounted tree matches the controller, if its gain disappears on held-out subjects or real transitions, or if it spends nearly the full budget continuously after a change. A second waveform or machine-condition dataset is required before interpreting wearable results as industrial value. A replay only estimates expenditure from explicit costs. Physical sensing-energy savings require actual configurable sensors.

**Repo and hardware fit.** Reuse the small encoder/head workflow, fixed-size buffers, and profiling discipline. A sensor encoder would require new data preparation and training. The ARM is sufficient for the initial decision policy. FPGA work becomes meaningful only if stream-processing or concurrent-channel costs dominate on a measured workload. A 100 Hz wearable task alone does not establish that need.

## Direction 2. Adapt on the edge when labels arrive after the raw data is gone

**Application.** An anomaly detector runs continuously. A human confirms events minutes or hours later, after the raw-data ring has overwritten them. Operating conditions recur, anomalies are rare, and some examples initially treated as normal are later confirmed abnormal.

**Research question.** Which information should a small device retain so delayed corrections improve future detection without erasing earlier faults? Compare raw snippets, frozen embeddings, prototypes, and compact sufficient statistics under the same memory and update budget. Make the feedback delay longer than some memory lifetimes, and measure the resulting lost learning opportunities.

This is an opportunity to connect the repo's frozen-backbone/action-head experience with temporal data. It is a different learning problem from recognizing the current input.

### Strong prior art

- **TinyOL, 2021** implements incremental online learning on MCUs. Adding a trainable head to an embedded network is established. [Author paper](https://arxiv.org/abs/2103.08295)
- **On-Device Training Under 256KB Memory, NeurIPS 2022** develops quantization-aware scaling and sparse updates for tightly constrained training. Memory-efficient embedded gradient updates have strong prior art. [Conference paper](https://papers.neurips.cc/paper_files/paper/2022/file/90c56c77c6df45fc8e556a096b7a2b2e-Paper-Conference.pdf)
- **TinyTrain, ICML 2024** selects model portions to update using task information, memory/compute limits, and scarce labels. A sparse adaptive update engine alone is insufficient. [Conference page and paper](https://proceedings.mlr.press/v235/kwon24c.html)
- **Label Delay in Online Continual Learning, NeurIPS 2024** explicitly separates label and data streams. It finds that more compute and generic self-supervised/test-time adaptation can fail to recover delayed-label performance. Its nearest-memory rehearsal method is an essential comparator. [Author paper](https://arxiv.org/abs/2312.00923)
- **On-device Online Learning and Semantic Management of TinyML Systems, 2024** combines online adaptation, federated meta-learning, and heterogeneous device/model management. Deployment-level adaptation and distributed sharing are also occupied. [Author paper](https://arxiv.org/abs/2405.07601)
- **Rethinking Continual Anomaly Detection on the Edge, ECCV 2026** finds that simple replay can outperform complex continual anomaly techniques. Its DINOSaur uses frozen DINOv3 representations and coreset memory. The inspected task is visual industrial inspection, so its exact backbone is not a direct audio/IMU control, but the frozen-feature memory design is. [Author manuscript](https://arxiv.org/abs/2605.24251)
- **Online Learning Extreme Learning Machine with Low-Complexity Predictive Plasticity Rule and FPGA Implementation, 2025 preprint** already supplies an FPGA online-learning implementation with local sparse updates. Porting a tiny online learner to fabric alone is insufficient. [Author preprint](https://arxiv.org/abs/2512.21777)
- **Latency-Aware Adaptive Learning for Nonstationary Data Streams: Coordinating Concept Drift and Delayed Supervision, TPAMI 2026** uses temporal anchors, model reuse, and a drift-guided randomized-network ensemble. Its primary PubMed abstract explicitly covers concurrent drift and delayed feedback. Those two conditions together are already a published problem. [Publisher DOI](https://doi.org/10.1109/TPAMI.2026.3742576)

### Candidate gap and first experiment

Focus on **retention decisions for delayed, selectively acquired event labels with a memory cap**, including actual event rates, rare positives, and correction of earlier pseudo-label contamination. The contribution cannot be a general claim to solve drift plus delayed labels. It needs either a new retention/update mechanism or an empirical result that changes which deployment architecture is preferable.

Start with a frozen audio or small time-series encoder so one can retain compact embeddings without representation drift. Compare no adaptation, exponential normalization, frozen-feature nearest neighbor or coreset, reservoir replay, recent-only replay, nearest-memory delayed-label rehearsal, and sparse head learning. Then introduce a controlled encoder-update arm that charges for feature incompatibility and re-encoding. An expensive learned memory selector must beat simple stratified storage.

MIMII DUE separates changes in operating/environmental conditions from normal/abnormal status. It is a useful source for distinguishing benign changes from anomalies. Its clips do not constitute a naturally timestamped lifetime deployment. Build a declared clip-order protocol with explicit label-delay and class-prevalence schedules, preserve official train/test separation, and distinguish the constructed chronology from naturally recorded transitions. [Dataset paper](https://arxiv.org/abs/2105.02702)

Measure prequential performance before label arrival, recovery after a delayed label, rare-anomaly recall at a fixed false-alarm rate, old-regime retention, memory occupied by each object, dropped label opportunities, inference disruption, and update compute. Revisit regimes in a held-out order.

**Kill tests.** Reject if a frozen encoder plus small coreset matches performance at lower cost, if the task requires continuous labeling to work, or if the apparent gain depends on letting test labels select memory before they should arrive. A benchmark-only result may still be publishable if it demonstrates that current adaptation claims fail under a realistic feedback model, but it needs externally chosen scenarios and comparisons.

**Hardware fit.** The current repo makes a software prototype feasible. On-board online updates can be considered later if they overlap inference enough to cause a measurable resource conflict. A53 or MCU implementations may be the better deployment. Hardware acceleration is an outcome to test.

## Direction 3. Spend time on alignment or prediction in asynchronous sensor fusion

**Application.** Different sensors report at different rates, with variable transport delays and occasional missing samples. The latest arrival from one channel may describe an older event than the latest arrival from another. A system must choose whether to wait for alignment, compute a prediction from partial data, or spend compute extrapolating a slow channel.

**Research question.** Under fixed memory, compute, and response budgets, which causal fusion policy best tracks the current event? The output is a time-indexed estimate or classification. Score it against the physical event time at which the result is available.

### Prior art and boundaries

- **Towards Streaming Perception, ECCV 2020** already combines accuracy and execution latency and shows that scheduling and forecasting affect streaming accuracy. A new latency-aware metric alone is weak. [Conference paper](https://www.ecva.net/papers/eccv_2020/papers_ECCV/papers/123470460.pdf)
- **Neural Controlled Differential Equations for Online Prediction Tasks, 2021** addresses causal interpolation for irregular streams. Non-causal preprocessing can invalidate online claims even when the network is recurrent. [Author paper](https://arxiv.org/abs/2106.11028)
- **Raindrop, ICLR 2022** learns relations among irregular sensor observations using a graph-guided architecture. Multirate and missing-sensor representation learning is established. [Author paper](https://zitniklab.hms.harvard.edu/publications/papers/raindrop-iclr22.pdf)
- **ADMN** already handles noise-dependent and compute-dependent modality allocation, and **MMEdge** already incrementally combines sensing and encoding with early decisions. A generic asynchronous neural fusion architecture is closely occupied. [ADMN](https://arxiv.org/abs/2502.07862) · [MMEdge](https://arxiv.org/abs/2510.25327)
- **Inference-Time Dynamic Modality Selection for Incomplete Multimodal Classification, 2026 preprint** selects which recovered modalities to fuse according to task-relevant information. Choosing which missing modality to impute is also occupied. [Author preprint](https://arxiv.org/abs/2601.22853)
- **Early Classification of Time Series in Non-Stationary Cost Regimes, 2026 preprint** adapts the decision trigger while holding the classifier fixed as decision/delay costs change. **End-to-end Early Classification of Time Series in Non-Stationary Environments, 2026 preprint** addresses coupled classification and triggering under drift. These are relevant trigger-learning comparators. [Cost-regime paper](https://arxiv.org/abs/2602.00918) · [End-to-end paper](https://arxiv.org/abs/2608.20044)

### Candidate experiment

Study event-time skew and out-of-order arrival explicitly, with causal signal processing and a small inference model. Compare wait-for-all, last-value fusion, bounded extrapolation with a conventional Kalman/state-space estimator, a causal irregular-time model, and a learned wait/compute decision. Match their compute and buffer budgets. Add a comparator that simply increases the output interval.

PAMAP2's real multirate signals support a first software test. Separate natural sample times from simulated network arrival times. Keep a family of delay distributions and burst outages unseen until evaluation. Report classification or estimation error at result availability, transition response time, stale-output duration, buffer occupancy, and discarded samples. A conventional filter must receive the same timestamps and noise model information.

**Kill tests.** Reject if a causal state estimator plus a fixed wait threshold matches the model, if only an offline interpolator produces the benefit, or if the evaluation makes synthetic delays correlate with labels. If the advantage persists only at high offered rates, state that regime and use independently profiled input/computation costs.

**Hardware fit.** FPGA timestamping and parallel transforms can reduce the overhead of many high-rate streams. The first question is whether temporal decision policy improves useful estimates. A demonstrated low-rate CPU result can stand as an algorithms result, while a separate high-rate workload is needed for an FPGA systems contribution.

This direction is ranked below the first two because MMEdge is particularly close. It is worth a narrow experiment only if temporal skew or out-of-order arrival creates failures that its current implementation and conventional filters do not already resolve.

## Wildcard outside sensing. Repair changing combinatorial decisions

An embedded service can repeatedly solve small graph problems such as radio-slot assignments, edge-job placement, or association of detections with tracks. Consecutive problems differ only slightly. A small model could choose an update neighborhood or solver parameters while a conventional optimizer repairs the incumbent solution. This would use the project's embedded runtime and hardware-design skills in a different computational domain.

The easy novelty claims fail quickly.

- **Machine learning-assisted high-speed combinatorial optimization with Ising machines for dynamically changing problems, Nature Communications, June 16, 2026** already combines embedded simulated-bifurcation hardware, compressed problem transfer, and learned parameter selection for changing TDMA problems. Primary article text was inspected, while repeat retrieval encountered access redirects. The publisher metadata and authors' Toshiba publication list confirm the date and an accessible March 2025 author preprint. [Publisher](https://www.nature.com/articles/s41467-026-73725-6) · [Author preprint](https://arxiv.org/abs/2503.23966) · [Authors' publication list](https://www.global.toshiba/ww/products-solutions/ai-iot/sbm/paper.html)
- **Unsupervised Learning of Local Updates for Maximum Independent Set in Dynamic Graphs, 2025 preprint** updates learned node memories and memberships in one parallel step after an edge change. Incremental learned graph repair is already explicit. [Author preprint](https://arxiv.org/abs/2505.13754)
- **Optimal Neighborhood Exploration for Dynamic Independent Sets, 2024 preprint** uses exact solutions to local subproblems, with a size parameter trading runtime and solution quality. This is a strong classical repair comparator. [Author preprint](https://arxiv.org/abs/2407.06912)
- **Dynamic Maximal Independent Set using Predictions, 2026 preprint** gives prediction-sensitive dynamic algorithms with graceful degradation. It solves maximal independent set, which differs from maximizing set weight or cardinality. Use it as learning-augmented algorithm precedent rather than claiming an equivalent optimizer. [Author preprint](https://arxiv.org/abs/2610.16637)
- **GPU-Initiated Discrete Simulated Bifurcation, 2026 preprint** measures request-to-reply overhead and streaming-coupling costs. A solver kernel speed comparison alone misses the current systems frontier. [Author preprint](https://arxiv.org/abs/2610.06622)

A first experiment can decide whether there is room for learning at all. Construct a held-out stream of real-sized scheduling graphs, retain the last feasible solution, and compare greedy repair, local search, an exact bounded-neighborhood repair, a general solver with an incumbent, and a learned selector under the same time budget. Charge feature extraction and the selector. Measure feasible objective value by deadline, number of changed assignments, and end-to-end update latency. Use unseen graph sizes and update types.

**Kill test.** If cheap greedy or neighborhood repair wins for the intended sizes, drop the learned accelerator idea. A continuation would require a specific workload property and a result that survives these dynamic baselines. This is a larger repo pivot and currently has less evidence of a concrete gap than the first two directions.

## Decision and next research step

The first experiment I would choose is a small software study of **additional measurement versus additional inference**, with a third adaptation option introduced only after the two-way comparison shows useful structure. Use a real chronological dataset and simple competing policies. The immediate deliverable is a Pareto curve of timely event recognition versus acquired data and compute, with a held-out drift/transition family.

The acquisition-tree literature and MMEdge already provide strong mechanisms. Their reproduction or implementation is the initial baseline work. If the proposed benefit reduces to exploration, ordinary sampling, or scheduling, that result should close the branch early. If a consistent residual gap appears only when feedback is delayed and acquisition consumes time, it gives a concrete problem definition for further algorithmic work.

Direction 2 is a reasonable independent branch because delayed corrections and limited retained evidence can be studied with the repo's existing frozen-feature workflow. Direction 3 and the optimization wildcard should remain alternatives. The available evidence does not yet justify declaring any of the four a cleared novelty claim or a reason to redesign the FPGA.

## Agent discussion after comparing the other broad searches

I read the independent application and hardware searches after writing the initial experiment priorities. For a broader capability pivot, my ranking is future-question memory first, temporally irreversible acquisition second, and manual-conditioned diagnosis third. This ranking favors the clarity and cost of a discriminating experiment. All three still carry high novelty risk.

**Future-question memory.** The question is scientifically attractive because retention happens before the query and information lost at that point cannot be recovered. However, RoboMem explicitly handles unknown future robot-history queries, StreamMem maintains fixed memory without advance questions, and workload-weighted wavelets already optimize query error. Those facts rule out claiming novelty from any of those ingredients. [RoboMem](https://arxiv.org/abs/2003.10553) · [StreamMem](https://arxiv.org/abs/2508.15717) · [Workload-weighted synopses](https://theory.stanford.edu/~matias/papers/mu-www-synopses-05.pdf)

The remaining experiment should combine uncertain learned event recognition with genuinely withheld temporal compositions and a changed future-question distribution. Its strongest cheap opponent is an interval event table retaining timestamps and top-k event probabilities, ordinary multiresolution numerical summaries, and a raw-snippet reservoir. Also compare mixtures of these structures. If all test questions reduce to a small known event vocabulary, this conventional representation may already preserve almost everything relevant. If test questions introduce entirely unknown predicates, the paper must acknowledge that compression cannot generally preserve arbitrary information at a small fixed size.

Hide each test query through the entire ingestion interval. Train and tune storage on other subjects/machines and other query compositions. Count event metadata, probability vectors, learned recurrent state, indexes, retained raw bytes, and incremental ingestion compute in the budget. Compare with reconstruction summaries and full-data retrospective answering, but require an improvement over the event-table combination before advancing a learned retention claim. A plausible discriminator is whether the gain survives a shift from frequent activity-name questions to rare duration/order questions without retraining the memory.

**Temporally irreversible acquisition.** The useful physical distinction is that enabling a sensor now cannot recreate a burst that ended earlier. Warmup, fill time for an FFT window, and pending acquisition duration change what can be learned by the next deadline. Compare a delayed-label active-feature learner with those constraints represented explicitly against a planner that accounts for future window availability. Include a zero-warmup, immediately queryable-feature arm. If the proposed advantage survives unchanged there, the claimed temporal mechanism is probably incidental. No policy can recover a short unobserved event retrospectively, so schedule comparisons must include the coverage cost of regular exploratory acquisition.

**Manual-conditioned diagnosis.** The application search identifies a real bottleneck in constructing executable physical hypotheses. The objection is now stronger than generic model-based diagnosis. DX 2024 already uses multimodal LLMs to construct fault-diagnosis models from diagrams and natural-language descriptions. BMD already alternates language hypotheses, numerical fitting, and experiment design. Giving a new method manuals while withholding them from these baselines would overstate transfer. [DX 2024](https://drops.dagstuhl.de/entities/document/10.4230/OASIcs.DX.2024.31) · [BMD](https://arxiv.org/abs/2610.25747)

A convincing residual would reduce expert correction effort on held-out equipment families while preserving intervention-prediction and diagnostic quality. Every method should receive the same manuals, configuration graph, component library, calibration observations, and numerical planner. Include a deterministic component assembler and BMD supplied with the documentation. Topology permutations of a familiar tank library offer a weaker test than equipment with new mechanisms and interfaces. This remains interesting, but the strong recent direct precedents and difficulty of independently validated physical models make the first study more expensive than the memory or acquisition tests.

The wildcard remains rejected as a generic proposal. Learned local graph updates, dynamic neighborhood optimization, and hardware tuning of repeated Ising problems already cover the initial idea. It can be reopened only around an independently valuable application where those baselines leave a measured gap.
