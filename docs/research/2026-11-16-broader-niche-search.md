# Broader search after closing sensor memory

November 16, 2026. Research screen and proposed experiment; no new experiment results.

**Experiment update:** the [diagnostic-probe pilot](2026-11-16-diagnostic-probe-pilot.md)
is now complete. Fixed probing substantially improves unknown-mechanism rejection;
the tested adaptive baselines do not beat it. A modest oracle-only opportunity
survives noise checks. Compare existing robust-design methods next; no new method
or FPGA implementation has been justified. The proposal below records the
pre-experiment reasoning.

## Recommendation

The next bounded experiment should investigate **short physical tests that reveal when a diagnostic model's fault catalog is inadequate**. A local monitoring system should distinguish “this is a known fault” from “none of my explanations fits,” before recommending a specific repair or adapting its baseline. The experimental question is whether choosing the test from the current evidence adds anything beyond an optimized fixed test and conventional model validation.

This is a more promising *problem to falsify*, not a demonstrated novel algorithm. Its attraction is that new excitation can expose a physical distinction that additional processing of an existing passive recording cannot. Its major risk is that ordinary system identification, a fixed probe, and an absolute residual threshold already solve it. We found substantial prior art and one particularly relevant negative toy result. A positive result against a passive classifier alone would be insufficient.

Confidence: moderate in the practical importance of model inadequacy; low-to-moderate in a remaining algorithmic contribution. Do not start an RL policy, LLM agent, or FPGA implementation. First measure the residual opportunity using existing methods and a clearly labeled action-selection ceiling.

The [sensor-memory direction is closed](2026-11-16-sensor-memory-closure.md). This recommendation does not reopen its storage allocator, question generator, or held-out activity benchmark.

## What was searched

I reread the current RC1 baseline, November 8 broad application/architecture/frontier searches, Claude's review outline, and the two negative memory experiments. I searched recent primary literature and public research artifacts across adaptation, active acquisition/calibration, compositional diagnosis, model-based experimental diagnosis, experimental agents, and intermittent edge systems. Search terms included open-set active diagnosis, incomplete fault models, model discrepancy, unknown fault input design, test-time intervention, active sensor commissioning, compound-fault generalization, and intermittent inference.

This is a targeted source screen, not a systematic review or a claim to have read another hundred complete papers. The [source ledger](2026-11-16-broader-niche-sources.json) distinguishes primary abstracts/previews, selected method inspection, and public code/documentation. Selected close sources received deeper checks. Indexed abstracts and publisher previews do not establish that a detail is absent from an inaccessible full paper.

## Directions considered and why the easy versions are weak

| Direction | Attractive capability | Evidence that constrains novelty | Decision |
|---|---|---|---|
| Adaptive sensing / buy more data versus more computation | Save acquisition cost without missing faults | AdaSense/MMEdge were already close in the previous search; recent safety-first acquisition adds confirmation, watchdogs, held-out faults and commissioning [S09]. Decision-based perception allocation is also explicit in DEEP [S10]. | Do not propose a generic uncertainty trigger or another sensing/compute scheduler. |
| Continual adaptation that preserves faults | Avoid treating a developing failure as a new normal | CANDI, TARD and TTA²D directly address contaminated adaptation or condition changes [S01–S03]. PORTAL selects interventions and sparse feedback; BoTTA studies on-device adaptation [S05–S06]. | High application value, crowded algorithmic pitch. Need an independently necessary feedback mechanism, not “adapt carefully.” |
| Sensor drift versus process fault / active calibration | Decide whether to recalibrate instrumentation or alarm on equipment | HRA already diagnoses sensor-local versus process perturbations; GP drift correction already schedules references; a November 6 calibration paper monitors cross-sensor inconsistency [S07, S11–S12]. | A distinction in labels or a reference scheduler alone is insufficient. |
| Unseen combinations of faults | Infer simultaneous causes without compound training examples | A September motor paper uses atomic primitives and cardinality-free composition; a recent diffusion paper also addresses generalized zero-shot compound faults [S13–S14]. | Reject the broad compositional-fault pitch. Real unseen mechanisms remain harder than recombining a supplied dictionary. |
| Active diagnosis of unknown physical behavior | Acquire evidence unavailable during ordinary operation | Active input design, passive/active integration, model invalidation, and safe nonlinear discrimination are established [S15–S20]. Robust experimental design explicitly addresses model mismatch [S21–S24]. | Keep only a bounded model-adequacy/probe-value experiment with strong fixed-probe controls. |
| Small experimental agents / model-building assistants | Interpret observations and choose useful tests | LUCA supplies a relevant environment, but its authors now warn that published baseline/model comparisons have defects [S25–S26]. Prior manual-to-diagnostic-model work was already close in the November 8 review. | Do not use frontier-agent failures as evidence that a new agent is needed. |
| Intermittent edge inference and reporting | Preserve useful decisions through power/connectivity gaps | Model optimization for intermittent learning, exact reporting/batching models and satellite inference-freshness policies already cover broad scheduling claims [S29–S31]. | A substantial measurement/deployment project; no sufficiently distinct cheap hypothesis emerged here. |
| Reusing/pretraining compact sensor models | Improve generalization with little edge compute | Edge/cloud refinement and recent frozen-foundation-model audits make conventional features and calibration important controls [S32, S34]. | No basis for another model-size or architecture novelty claim. |

These are comparative research judgments, not proofs that every subproblem is solved.

## Close precedents that change the proposed experiment

**Safe active discrimination is already strong.** Ni et al. optimize separating actions for nonlinear sensor/actuator fault models, with public unicycle code. Their formulation assumes the true mode belongs to a finite set, but their passive consistency procedure can also return no consistent model. Therefore neither active maneuvering nor “reject every model” is new. The narrower question is whether an input selected to expose catalog inadequacy helps at matched cost outside that catalog. [Paper, formulation and Algorithm 1](https://arxiv.org/html/2606.19590), [accepted manuscript](https://mornik.web.illinois.edu/wp-content/uploads/NOCC26.pdf), [author code](https://github.com/gtfactslab/Ni_RAL2026).

**Model adequacy as an experiment-design objective is also established.** Forster, Ivanova and Rainforth introduce an auxiliary model and explicitly include a variable for model correctness in experimental design. Maximin robust BED addresses misspecification, while AD-EKI designs observations to calibrate model discrepancy [S21–S24]. These are direct competitors to a future method, not optional background. The inspected Forster primary indexed abstract was available; direct full-PDF access encountered a browser challenge. Its full algorithm and artifact must be checked before claiming a new objective. [Forster et al.](https://openreview.net/pdf?id=uyNJLdCvFG), [Maximin robust BED, revised November 8, 2026](https://arxiv.org/abs/2603.14094), [AD-EKI](https://doi.org/10.1016/j.jcp.2025.114469).

**A fixed probe may already remove the opportunity.** Ashfall reports an archived CPU cart-pole/slip study in which an information-selected active probe tied an optimized fixed probe, at much higher search cost; passive abstention already rejected most unknown mechanisms. This is an author's public negative-results artifact, not peer-reviewed physical-robot evidence. It is sufficiently close to require fixed and random probe controls here. Do not rerun that toy and call it a new niche. [Primary repository and frozen-study description](https://github.com/yusufdxb/ashfall).

**Unknown interactions and model incompleteness are old diagnosis problems.** Kuhn and de Kleer explicitly study hidden interaction faults with incomplete models [S19]. The research cannot claim the invention of incomplete-model diagnosis merely because it uses a small neural policy.

**Experimental-agent benchmark numbers need independent validation.** LUCA is relevant conceptually, but its November 12 known-issues document identifies ignored intervention formats, a faulty heuristic baseline, held-out-protocol issues and other engine/scoring defects. The authors caution against relying on published comparisons. I therefore do not use the paper's reported diagnosis/rescue gaps or model rankings to establish this proposal. [Paper](https://arxiv.org/abs/2611.03100), [author issue disclosure](https://github.com/RelationRx/luca/blob/main/KNOWN_ISSUES.md).

## The specific niche to test

**Can a resource-limited physical monitor choose a brief test that exposes an unsupported diagnosis while preserving useful recognition of faults it really knows?**

Example: while a small mobile platform follows an ordinary path, a delayed position measurement and an actuator response problem may both appear as tracking error. A short speed change or turn may separate their responses. A classifier that simply becomes confident in the nearest catalog entry can prescribe the wrong fix. The system should instead retain multiple explanations or report that its catalog is inadequate when the new evidence warrants it. This example is a hypothesis; the proposed simulator must establish which cases are actually distinguishable.

Two distinctions matter. First, uncertainty **within** a model catalog differs from evidence **against** the catalog. Normalizing likelihoods across wrong models can still produce a confident winner, so the baseline must use absolute fit, not just posterior entropy. Second, the relevant output is an identifiable behavioral explanation or “unsupported,” not a named physical component that cannot be distinguished with the available sensors. Wheel-radius change and motor gain change can be observationally equivalent in a kinematic model; such pairs belong in a negative-control panel, not in an accuracy target that demands an impossible distinction.

The possible contribution is an empirically useful, low-cost rule for deciding when and how to validate an explanation under new physical mechanisms. That contribution exists only if conventional fit tests and cheap probe schedules leave a meaningful gap, and existing robust-design methods do not close it. Combining familiar constraints is not by itself novelty.

## First experiment

The [proposed protocol](../../experiments/catalog_validation/PROTOCOL.md) specifies a software-only diagnostic study. It is designed but **not run**.

1. Use a transparent differential-drive/unicycle simulator informed by the public author model. First reproduce a closed-catalog separating-input example. Then add declared actuator-dynamic and sensor-timing mechanisms for the evaluator. Do not claim these extensions reproduce the paper or physical hardware.
2. Give every policy the same passive command/pose history, known-model bank, benign uncertainty bounds, observations and allowed probe budget. Withhold entire final fault mechanisms from fitting, likelihood templates and threshold selection; hold out robot/controller configurations as well.
3. Compare passive residual/model-bank diagnosis with rejection; an optimized fixed step/turn sequence; random matched-cost probes; persistently exciting probes plus conventional identification; greedy Bayesian information gain plus absolute-fit rejection; and reachable-output-overlap selection plus model invalidation. Also give a compact classifier the same evidence. Do not compare a new policy only against entropy gating or passive neural classification.
4. Permit at most two one-second probe slots, in one continuous episode. Charge probe duration, effort, tracking disruption, selection compute and safety interventions. Account for abstention through required known-fault recall and healthy false-alarm limits.
5. Compute an explicitly nondeployable action-selection ceiling using counterfactual simulator branches with the **same incomplete catalog and decoder**. Separately use full-mechanism access only to check identifiability. Never attribute the full-catalog oracle's extra knowledge to an adaptive policy.

**Decision gate:** Continue only if the task is identifiable, cheap intervention helps beyond passive monitoring, and an action-selection ceiling remains at least 10 percentage points better than the strongest feasible simple policy on unknown-fault rejection while maintaining at least 90% known-fault macro recall and at most 5% healthy false alarms. Require the effect across at least two held-out mechanism families and multiple held-out configurations. The ceiling establishes opportunity, not a new method's success.

If an optimized fixed probe, conventional fit test or other simple policy is within 3 points of that ceiling, close the adaptive-method branch. If the ceiling fails, close or mark the task unidentifiable rather than training a larger policy. Intermediate results are inconclusive and do not authorize a scaled method or hardware claim. Do not keep escalating simulator complexity just to make fixed probes lose.

Before a method contribution, reproduce or faithfully adapt the closest robust BED and nonlinear discrimination competitors. A simulated gap still requires an independent physical setting before FPGA work. The first screen is useful precisely because it may recommend implementing an ordinary fixed test instead of inventing another model.

## Fit to this repository and expected value

The repo provides embedded inference and deployment experience. It does not currently provide a verified physical-diagnosis simulator or a fault-testing rig. The existing Qwen decoder is optional; explicit state estimation and hypothesis testing may be the right solution. No baseline image, live board state or unrelated gate work is changed by this search.

A positive result could support an embedded-intelligence study about obtaining diagnostic evidence and avoiding unsupported repairs. A new objective is unlikely to be the contribution given the prior art. An efficient approximation, new empirically justified decision rule, or carefully validated physical benchmark might be. This assessment is an inference from the literature, not a publication or impact guarantee.

The immediate deliverable should be the **baseline/ceiling comparison and a go/no-go result**, not a trained policy. The decision thresholds above are proposed screening thresholds; freeze the executable simulator, source revision, parameters, seeds and metrics before final evaluation.

## Inspected source index

Depth descriptions are literal: indexed text is a primary-source abstract or excerpt returned by search, not a full-paper read. Repository results are author reports, not independent reproductions.

| ID | Primary source | Inspection |
|---|---|---|
| S01 | [TARD: Test-time domain adaptation for robust fault detection under evolving operating conditions](https://doi.org/10.1016/j.ress.2025.112135) (2026) | primary abstract/publisher text |
| S02 | [CANDI: Curated Test-Time Adaptation for Multivariate Time-Series Anomaly Detection Under Distribution Shift](https://arxiv.org/abs/2604.01845) (2026) | primary abstract; venue PDF indexed abstract |
| S03 | [TTA2D: Bilevel Test-Time Adaptation with EVT Thresholding for Robust Industrial Time Series Anomaly Detection](https://skoge.folk.ntnu.no/prost/proceedings/ifac2026_IFACWC26_preprints/files/3884.pdf) (2026) | primary indexed abstract/introduction |
| S04 | [Monitoring Risks in Test-Time Adaptation](https://proceedings.neurips.cc/paper_files/paper/2025/file/746960ad49ddb47248970a0e1404230c-Paper-Conference.pdf) (2025) | primary indexed abstract |
| S05 | [BoTTA: Benchmarking On-device Test Time Adaptation](https://doi.org/10.1145/3774906.3800498) (2026) | primary publisher sections 2.1 and 2.2 preview |
| S06 | [When Should We Intervene at Test Time? (PORTAL)](https://arxiv.org/abs/2610.37658) (2026) | primary indexed abstract |
| S07 | [Not all those who drift are lost: Drift correction and calibration scheduling for the IoT](https://arxiv.org/abs/2506.09186) (2025) | primary abstract opened |
| S08 | [Value-Based Active Sensing for Demand-Driven Adaptive Sampling](https://www.repository.cam.ac.uk/handle/1810/410507) (2026) | official thesis abstract |
| S09 | [Resource-Aware Safety-First Active Sensor Acquisition with Few-Shot Commissioning for Edge Fault Warning](https://doi.org/10.3390/s26165065) (2026) | primary indexed abstract and baseline/discussion sections |
| S10 | [The Decision Value of Perception Compute](https://arxiv.org/abs/2609.35910) (2026) | primary abstract opened |
| S11 | [Hierarchical Residual Attribution with Supervised Channel Shortlisting for Sensor-Local and Process Fault Diagnosis in Multivariate Sensor Time Series](https://doi.org/10.3390/s26154986) (2026) | primary abstract opened |
| S12 | [Data-Driven Calibration and Reference-Free Drift Detection for Multi-Modal Sensor Systems](https://www.mdpi.com/1424-8220/26/21/7016) (2026) | primary indexed abstract/discussion excerpt |
| S13 | [Physics-Guided Compositional Diagnosis of Unseen Compound Faults in Variable-Speed Induction Motors](https://www.mdpi.com/2075-1702/14/9/1032) (2026) | primary indexed method and evaluation sections |
| S14 | [Physics-guided compositional diffusion with confidence-rectified ensemble for generalized zero-shot compound fault diagnosis](https://www.sciencedirect.com/science/article/pii/S0888327026012987/pdf) (2027 volume; online available November 2026) | primary indexed introduction and stated dictionary assumption |
| S15 | [Safe, Real-Time Active Model Discrimination and Fault Diagnosis for Nonlinear Systems via Differentiable Reachability](https://arxiv.org/abs/2606.19590) (2026) | primary selected formulation, Algorithm 1, examples; author source inspection |
| S16 | [Input design for active fault diagnosis](https://doi.org/10.1016/j.arcontrol.2019.03.002) (2019) | primary review abstract and discussion section |
| S17 | [Integrated Passive-Active Model Identification with Tunable Model Discrimination for Affine Discrete-Time Systems](https://qiangs.github.io/Papers/Liu2022LCSS.pdf) (2022) | primary indexed abstract |
| S18 | [Active Model Discrimination Using Partition-Based Output Feedback Input Design](https://qiangs.github.io/Papers/Conf_Shen2020ECC.pdf) (2020) | primary indexed abstract/introduction |
| S19 | [Diagnosis with Incomplete Models: Diagnosing Hidden Interaction Faults](https://www.papers.phmsociety.org/index.php/phmconf/article/download/1934/944) (2010) | primary indexed conclusion and formulation examples |
| S20 | [Model Invalidation for Switched Affine Systems with Applications to Fault and Anomaly Detection](https://ftp.eecs.umich.edu/~necmiye/pubs/HarirchiO_adhs15.pdf) (2015) | primary indexed conclusion |
| S21 | [Improving Robustness to Model Misspecification in Bayesian Experimental Design](https://openreview.net/pdf?id=uyNJLdCvFG) (2025) | primary indexed abstract/method excerpt; direct PDF browser challenge |
| S22 | [Maximin Robust Bayesian Experimental Design](https://arxiv.org/abs/2603.14094) (2026) | primary abstract and November 8 revision metadata opened |
| S23 | [DiffBED: Scaling Bayesian Experimental Design to High-Dimensions](https://ora.ox.ac.uk/objects/uuid%3Abf39c757-2cea-4ed9-b818-d99b9ee46392/files/sbv73c2988) (2026) | primary indexed abstract/introduction |
| S24 | [Bayesian experimental design for model discrepancy calibration: An auto-differentiable ensemble Kalman inversion approach](https://doi.org/10.1016/j.jcp.2025.114469) (2026) | primary publisher abstract/introduction |
| S25 | [LUCA: A Synthetic World for Experimental Reasoning](https://arxiv.org/abs/2611.03100) (2026) | primary selected design, baseline/failure discussion; checked subsequent author disclosure |
| S26 | [LUCA known issues, updated November 12, 2026](https://github.com/RelationRx/luca/blob/main/KNOWN_ISSUES.md) (2026) | author disclosure read through GitHub connector |
| S27 | [Ashfall: negative-results studies of failure-driven robot learning and simulator diagnosis](https://github.com/yusufdxb/ashfall) (2026 inspected; repository artifact) | author README and study summaries read through GitHub connector |
| S28 | [netfd: active fault diagnosis for networked LTI systems via nu-gap and PPO](https://github.com/uiengeen/netfd) (2026 inspected; repository artifact) | author indexed README |
| S29 | [Design-Time Optimization of Deep Neural Networks for Intermittent Learning on Microcontrollers](https://arxiv.org/abs/2608.03589) (2026) | primary indexed abstract |
| S30 | [Assessing Fixed-Batch Reporting for Deadline-constrained Inference in Intermittently Powered IoT](https://arxiv.org/abs/2609.06585) (2026) | primary indexed abstract |
| S31 | [In-Orbit Intelligence or Ground Offloading? Inference Freshness under Intermittent Satellite Connectivity](https://arxiv.org/abs/2605.27021) (2026) | primary indexed abstract |
| S32 | [Bridging Edge and Cloud: A Knowledge-Enhanced Framework for Efficient Time Series Anomaly Detection](https://doi.org/10.1109/TSC.2025.3610402) (2025) | primary publisher/indexed author abstract |
| S33 | [Decouple to adaptive diagnosis: A dual-head open-set framework for cross-condition injection molding process](https://doi.org/10.1016/j.jprocont.2026.103832) (2026) | primary publisher abstract/preview |
| S34 | [Representation stability is not detectability: A leakage-free evaluation of frozen time series foundation models for anomaly detection under concept drift](https://doi.org/10.1016/j.asoc.2026.116360) (2026) | primary indexed abstract |
| S35 | [Aalto Gear Fault datasets for deep-learning based diagnosis](https://doi.org/10.1016/j.dib.2024.111171) (2024) | primary indexed data-paper abstract |
| S36 | [System-Self as a Data Structure: An Architectural Approach to Bounded Adaptation](https://arxiv.org/abs/2607.13249) (2026) | primary indexed abstract |
