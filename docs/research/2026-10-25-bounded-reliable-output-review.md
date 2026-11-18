# Bounded, reliable output on computation-constrained critical systems

Review date: October 25, 2026, America/Chicago. Target: System One on KR260 and smaller embedded platforms. This is a focused literature review and engineering synthesis, not a systematic review with exhaustive database coverage, a certification assessment, or new hardware evidence. No board access, deployment, benchmark restart, or changes to existing experiments occurred.

## Finding

The strongest existing approach is to make a learned component propose a bounded decision and let a smaller, independently specified mechanism decide whether and how it may execute. Output grammar, task correctness, statistical confidence, safe execution, and real-time behavior require different evidence. None substitutes for the others.

For this project, the most promising combination is a compact typed plan, explicit trusted state, request-grounding checks, an uncertainty/clarification policy, and a resource-bounded execution monitor. Keep a small classifier and authored rules as first-class alternatives to the LLM. The architecture follows established runtime-assurance and verified-execution work; simply combining these components would not establish novelty.

## Scope and search method

Searches covered runtime assurance/Simplex, shield synthesis, embedded temporal monitoring, grammar and semantic constrained decoding, conformal prediction/selective classification, verified planning/execution, compact policies, numerical verification, and mixed-criticality isolation. Sources were sought through publisher proceedings, author papers, NASA NTRS, official repositories and documentation. Searches also checked recent 2026 work so the review is not confined to older constrained-JSON tools.

Primary-source material supports the claims below. Reading depth varies: selected full papers and documentation were inspected; some works were screened from author abstracts or publisher records. The companion source registry records that distinction. This review does not reproduce benchmarks, audit implementations, read paywalled standard clauses, or establish that an upstream tool is qualified on KR260. Reported GPU/desktop performance is not a board estimate. Search-engine crawl dates were not treated as publication dates; for example, Copilot 3 is an April 2020 NASA report.

## 1. Specify the guarantee before choosing the solution

| Desired property | Example | What can establish it | What remains outside it |
|---|---|---|---|
| Output size and work bounds | At most N actions, depth D, T tokens, deadline B | Restricted language, static capacity checks, watchdog and bounded executor | Successful completion by the deadline |
| Syntax/schema | Required keys, legal types and enum values | Grammar masks plus a strict final validator | Correct asset, operator or requested action |
| Referential/type consistency | Asset exists; unit matches metric; references resolve | Environment-dependent domains, type checking, semantic decoding | Whether the operator meant this asset |
| Domain safety | No action without fresh observations and required permission | Correct safety model, enforcement gate, invariant proof | Complete task correctness or hazards omitted by the model |
| Request fidelity | “Above” becomes `gt`, not `ge` | Grounding evidence, reviewed labels, narrow formal input language, selective acceptance | Universal correctness for unrestricted natural language |
| Statistical reliability | Wrong accepted plans below a specified risk | Independent calibration/testing with an appropriate risk-control theorem | Per-instance certainty or arbitrary distribution shift |
| Physical safety | Actuation keeps a plant within a safe region | Dynamics-aware controller/filter and timely observation | Protection from an inaccurate plant model or unmodeled disturbances |

A valid output prefix can still end at the token limit without a complete plan. A timeout is a bounded failure outcome, not successful constrained generation. Likewise, safe refusal is useful but cannot count as correct actionable completion when the request was supportable.

## 2. Existing solution families

### A. Runtime assurance and Simplex

Simplex separates an advanced controller from a trusted recovery controller and switching logic. NASA's 2024 formalization models this arrangement in hybrid programs and uses PVS to prove instantiated safety properties, illustrated with braking. The key requirement is intervention while recovery is still possible, including observation and switching delays. [NASA formal framework](https://ntrs.nasa.gov/citations/20230017350), [original SEI architecture](https://insights.sei.cmu.edu/library/an-architectural-description-of-the-simplex-architecture/).

For System One, the analogous boundary would place the model behind an admission gate. The trusted side owns actual tool handles, observations, state updates, budgets, and execution. Its recovery behavior must suit the application: rejecting a maintenance request may be appropriate, while stopping an active physical controller may not be. A second software process alone does not provide fault independence.

ASTM F3269-21 explicitly concerns bounding complex aircraft functions with RTA. Its public scope establishes the relevance of this architecture, not that our design meets the standard. EASA's SHEPHERD assessment says the standard requires an external safety assessment and cannot alone supply the assessed means of compliance. Only public scope/assessment text was reviewed. [ASTM scope](https://store.astm.org/f3269-21.html), [EASA assessment, section 3.7](https://www.easa.europa.eu/sites/default/files/dfu/shepherd_-_d2.2-d3.2_-_identification_of_satisfactory_industry_standards_and_justification_for_not_acceptable_industry_standards.pdf).

**Fit:** Very high as a system architecture. It does not require proving every internal computation of a large model.

### B. Shields and embedded temporal monitors

Shield synthesis constructs a reactive enforcement component from selected critical properties. Bloem et al. study hardware shields that correct outputs only when required. Its useful separation is between a complex producer and a smaller safety specification; construction can become expensive as the specification/state space grows. This is an offline-versus-runtime tradeoff, not a universal small-monitor guarantee. [Shield synthesis, 2015](https://chaowang-vt.github.io/pubDOC/BloemKKW15.pdf).

Copilot compiles stream specifications to C99 with fixed memory and execution structure for a fixed specification. Its documentation includes theorem-proving and generated-code verification facilities. Compilation occurs off target; the embedded device runs the monitor. FRET/Ogma connects structured requirements to generated monitors, helping address the gap between informal requirements and executable checks. Target WCET, compiler configuration, inputs, and monitor scheduling still need qualification. [Copilot](https://github.com/Copilot-Language/copilot), [NASA Copilot 3 report](https://ntrs.nasa.gov/api/citations/20200003164/downloads/20200003164.pdf), [FRET/Copilot integration](https://ntrs.nasa.gov/citations/20220000049).

R2U2 is especially relevant: its CAV 2023 toolchain supports FPGA and software monitoring of bounded temporal requirements, static memory arenas in C, and resource/WCET estimation. Estimates depend on formula queues, timestamp widths and platform; they are not universal LUT or latency numbers. Future-time requirements can only produce definitive verdicts when enough observations exist. The 2025 embedded-Rust follow-up is identified in official documentation, but its full text was inaccessible in this review. [R2U2 paper](https://cgjohannsen.com/papers/JJKRZ23.pdf), [documentation](https://r2u2.github.io/r2u2/).

TeSSLa provides a related event-stream approach, including nonsynchronized streams; an ETH CPU/FPGA thesis demonstrates that monitoring path. It merits comparison where events are naturally asynchronous. [Language record](https://research.uni-luebeck.de/en/publications/tessla-runtime-verification-of-non-synchronized-real-time-streams/), [author's FPGA thesis summary](https://www.pirmin-schmid.ch/publications/computer-science/runtime-verification/).

**Fit:** High for execution ordering, observation freshness, deadlines and state transitions. Monitoring is detection; prevention additionally requires an authoritative interlock and a timely recovery path. Choose past-time/current-state predicates for immediate admission and treat future obligations separately.

### C. Grammar-constrained generation

PICARD rejects inadmissible continuations through incremental parsing, demonstrated for SQL. Koo et al. formalize tokenization-aware automata composition; this matters because output-language characters and model tokens do not align. These methods constrain language membership rather than infer the operator's intended meaning. [PICARD](https://aclanthology.org/2021.emnlp-main.779.pdf), [automata-based decoding](https://arxiv.org/abs/2407.08103).

SynCode precomputes DFA mask stores. Its full paper distinguishes retaining all valid tokens from excluding all invalid ones under additional completeness conditions; implementation choices and acceptance length matter. It explicitly focuses on syntax. Do not read an abstract's soundness/completeness wording as a blanket end-to-end correctness guarantee. [SynCode, sections 4.4–4.7 and 7](https://arxiv.org/html/2403.01632v3).

XGrammar uses cached token checks and persistent parser stacks; its MLSys 2025 paper reports substantial acceleration. XGrammar 2 adds dynamic dispatch, JIT compilation and cross-grammar caching for agentic output structures. Their near-zero serving-overhead results rely on evaluated serving setups and overlap; they do not establish bounded ARM latency or small FPGA resource use. [XGrammar](https://proceedings.mlsys.org/paper_files/paper/2025/file/5c20ca4b0b20b0bd2f1d839dc605e70f-Paper-Conference.pdf), [XGrammar 2, 2026 preprint](https://arxiv.org/html/2601.04426v1).

llguidance and llama.cpp are practical implementation candidates. The latter documents subset-only JSON Schema conversion, performance pitfalls and silently skipped unsupported features. Pin the implementation and validate the actual supported schema fragment. JSONSchemaBench contributes 10,000 real-world schemas and separates schema coverage, efficiency and output quality—an appropriate evaluation discipline. [llguidance](https://github.com/guidance-ai/llguidance), [llama.cpp grammar documentation](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md), [JSONSchemaBench](https://arxiv.org/abs/2501.10868).

A recent ISSTA-accepted paper, Parser Stack Classification, moves work into preprocessing and reports vocabulary-independent mask computation in its formulation. It deserves scrutiny for fixed recurring contracts, especially its preprocessing break-even analysis. We screened its author abstract; no KR260 port or benchmark was inspected. [PSC, August 2026](https://arxiv.org/abs/2608.03065).

**Fit:** Useful if autoregressive output remains. It cannot make `gt` the right choice rather than `ge`, even when both are legal. Do not allow an incomplete output to execute; maintain a separate final validator.

### D. Semantic constraints and checked planning

Synchromesh predates many modern JSON tools and explicitly handles syntax, scope, typing and contextual logic through constrained semantic decoding. It is a particularly close precedent for generating a restricted maintenance language. [Synchromesh, ICLR 2022](https://arxiv.org/abs/2201.11227).

Logically Constrained Decoding enforces legal chess moves and sound resolution-proof steps using domain rules. Its proof-of-concept makes the relevant distinction: correctness of a transition or proof step comes from the formal world model. It does not imply winning chess, short proofs, or correct interpretation of arbitrary requests. [Ma and Hu, MathNLP 2025](https://aclanthology.org/2025.mathnlp-main.11.pdf).

Decode-Time Grammars instantiates names, fields and APIs from a runtime environment. Its No-Ghost guarantee addresses undefined references. A legitimate reference can still be the wrong reference for a request. This July 2026 preprint was screened from its author abstract, so it is a recent lead rather than a verified tool recommendation. [Decode-Time Grammars](https://arxiv.org/abs/2607.18357).

LLM-Modulo work places model proposals in interaction with external verifiers; a technical follow-up evaluates scheduling domains. Such a pipeline can guarantee acceptance only of outputs satisfying a complete set of sound checks. Its guarantee is relative to the formal model/specification supplied to those checks. Bound repair attempts: an unbounded “try again” loop is incompatible with a hard resource budget. [ICML position paper](https://proceedings.mlr.press/v235/kambhampati24a.html), [technical evaluation](https://arxiv.org/abs/2411.14484).

**Fit:** Very high for asset domains, units, dependencies and policy rules. It leaves an interpretation boundary: a verifier given the model's mistaken translation of the request may faithfully approve the wrong task.

### E. Confidence, abstention and asking for help

Selective Classification and SelectiveNet study rejecting uncertain inputs while balancing accepted-set error and coverage. The latter learns a reject mechanism jointly with prediction. These are stronger foundations than treating maximum softmax as a safety certificate. [Selective Classification, 2017](https://proceedings.nips.cc/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html), [SelectiveNet, 2019](https://proceedings.mlr.press/v97/geifman19a.html).

Conformal Risk Control controls expected monotone loss under its statistical assumptions. Learn then Test uses hypothesis testing to select settings with finite-sample risk control, including more general risks. Neither means a scalar calibrated confidence is a per-request proof. Define the actual loss—wrong accepted complete plans, not just per-field error—and use a procedure that supports that loss and threshold search. Ordinary temperature scaling or logistic calibration does not itself furnish the same guarantee. [CRC](https://research.google/pubs/conformal-risk-control/), [LTT](https://arxiv.org/abs/2110.01052).

KnowNo is directly applicable to bounded actions: use candidate sets and ask for help when the set is not a singleton. Its task-level assurances assume appropriately sampled scenarios and accurate human help; it develops sequence-level calibration because successive steps are dependent. Poor models can maintain coverage by asking for help frequently. Thus help burden is a primary result. CoFineLLM, L4DC 2026, studies fine-tuning to improve set efficiency/help rates; its publisher abstract was screened here. [KnowNo, CoRL 2023](https://proceedings.mlr.press/v229/ren23a/ren23a.pdf), [CoFineLLM](https://proceedings.mlr.press/v331/wang26c.html).

**Fit:** High, with cheap postprocessing once scores exist. Do not claim error bounds from correlated templates as if they were independent operator requests. Marginal set coverage does not automatically bound error conditional on singleton acceptance, nor every rare subgroup. New sequences, asset classes and language distributions need explicit treatment.

### F. Verified execution and proof-carrying artifacts

PLEXIL supplies preconditions, postconditions, invariants and explicit node execution semantics, with resource arbitration. It provides a more relevant execution precedent than treating generated JSON as an executable script. A plan can fail a precondition or postcondition without the executive inventing a replacement task. [PLEXIL reference](https://plexil-group.github.io/plexil_docs/PLEXILLanguage/PLEXILReference.html), [resource model](https://plexil-group.github.io/plexil_docs/PLEXILLanguage/ResourceModel/SimpleUnaryResources.html).

Proof-Carrying Code separates expensive construction from a smaller trusted checker. The transferable idea is a plan plus a machine-checkable certificate, not an English rationale. A certificate might bind a plan to a policy version, state generation and checked invariants. It cannot certify natural-language intent unless that intent has a trustworthy formal representation. Do not require a general theorem prover on the FPGA for a finite plan language. [Necula's PCC project](https://people.eecs.berkeley.edu/~necula/pcc.html).

**Fit:** High for a compact interpreter and policy certificate; full PLEXIL integration is optional. Recheck state-sensitive conditions immediately before dispatch, since a proof about an old snapshot can be stale.

### G. Physical control safety filters

Control barrier functions restrict control inputs to preserve a specified safe set, often through a small quadratic program. Model-predictive safety certification checks whether a proposed input admits a feasible safe trajectory and adjusts it when needed. The model, disturbance assumptions, numerical feasibility and sampling behavior define the guarantee. [Ames et al., 2017](https://authors.library.caltech.edu/records/jnhr0-1ww05), [Wabersich and Zeilinger, 2018](https://arxiv.org/abs/1803.08552).

**Fit:** Important if the project reaches continuous physical actuation. Less immediate for read/report/inspection requests. A discrete plan validator is not a control barrier function, and a QP safety filter does not check whether a language request was translated correctly. Per-cycle optimization must fit a measured deadline; precomputed safe action sets may suit smaller devices when their assumptions hold.

### H. Smaller policies, numerical fidelity and isolation

VIPER distills neural policies into decision trees that can be checked with existing verification methods. Its demonstrations concern particular symbolic-state control tasks, not arbitrary language understanding. Bonsai/ProtoNN show that useful classification can fit tiny devices; Microsoft's EdgeML documents Arduino Uno deployment with 2 KB RAM. Smallness alone confers neither correctness nor a safety proof. [VIPER](https://papers.neurips.cc/paper_files/paper/2018/hash/e6d8545daa42d5ced125a4bf747b3688-Abstract.html), [EdgeML](https://www.microsoft.com/en-us/research/project/resource-efficient-ml-for-the-edge-and-endpoint-iot-devices/?lang=zh-cn).

Reluplex/ACAS Xu is an important precedent for formally checking bounded advisory networks. QEBVerif addresses the separate issue that quantization may invalidate previously verified neural properties. These papers support offline verification of suitably bounded models/properties, not tractable full verification of our Qwen language understanding. [Reluplex](https://arxiv.org/abs/1702.01135), [QEBVerif, CAV 2023](https://faculty.sist.shanghaitech.edu.cn/faculty/songfu/publications/CAV23a.pdf).

Spatial and temporal isolation protect an enforcement component from the workload it supervises. seL4 is a reference architecture; verification coverage depends on configuration and architecture. Some official tutorial text still says MCS verification is ongoing, whereas Proofcraft reports a 2026 RISC-V functional-correctness milestone. Neither establishes a verified KR260 configuration or proof coverage for our DMA path. Linux locking/ownership is useful coordination, but does not equal this isolation argument. [seL4 caveats](https://github.com/seL4/seL4/blob/master/CAVEATS.md), [2026 proof-provider update](https://proofcraft.systems/news-2026/).

**Fit:** Compact policies are mandatory baselines. Preserve numerical qualification and explicit authority boundaries when changing model precision or deploying a monitor.

## 3. What this means for constrained hardware

These are engineering deductions from the reviewed methods, not published performance predictions for our board.

1. **Compile policy off target.** Generate grammar tables, monitor code, allowed-action domains and proof artifacts on a workstation. Ship fixed, versioned artifacts with declared size limits.
2. **Prefer the smallest output language that expresses the task.** Fixed action IDs and typed argument records can avoid JSON punctuation and free-form strings. Keep unsupported/ambiguous outcomes explicit. The language still needs numerical values and source spans if unseen thresholds are in scope; a closed training vocabulary cannot express arbitrary new values.
3. **Treat factorized outputs as structured decisions.** Independently selected legal fields can form an inconsistent or semantically wrong plan. Conditional heads, structured search or deterministic assembly rules may help, but each changes the admitted output space and requires evaluation.
4. **Bound every source of work.** Declare maximum input bytes/tokens, action count, nesting, candidates, retries, sensor reads, outstanding obligations, and tool timeouts. Bound schema compilation too, or forbid runtime compilation.
5. **Separate proposal timeout from enforcement timing.** If a language model misses its budget, the monitor and recovery path must still run. Target memory/bus contention and DMA access matter even when compute cores are separate.
6. **Distinguish local checks from search.** Scanning a fixed AST against R local predicates may take O(NR). Exploring all conditional branches or synthesizing a shield can grow exponentially; do not advertise every semantic validator as linear-time.
7. **Budget tables, not just arithmetic.** Our vocabulary has 151,936 tokens. A dense one-bit allowed-token mask is 18,992 bytes (18.55 KiB). Storing 256 independent masks would require 4,861,952 bytes (4.64 MiB), excluding indices/parser state. These are illustrative calculations, not a claim that any cited engine uses this layout. Sharing, sparse transitions and finite action selection can change the cost substantially.
8. **Measure the entire choice path.** A head-only cached timing omits the backbone. A token-mask speedup need not remove the model's full vocabulary projection. Conversely, a purpose-built choice head may eliminate that projection and autoregressive decoding but still pay state encoding and candidate scoring costs.

For a KR260 experiment, start with an ARM implementation of the small verifier and a simulated authoritative dispatch boundary. Compare an FPGA interlock only if isolation, deterministic timing, CPU load or energy supplies a reason. Existing FPGA monitor literature means “we implemented a checker in RTL” is not enough of a contribution.

## 4. Proposed System One architecture

```text
Operator request + versioned asset catalog
                 |
                 v
Bounded proposer: rules / TF-IDF / encoder / small LLM
                 |
                 v
Typed candidate plan + source spans + uncertainty information
                 |
                 v
Admission gate
  - strict syntax, size and capacity
  - identifiers, types, units and field dependencies
  - request-grounding consistency or explicit clarification
  - policy, authorization, observation freshness and state generation
  - complete-plan uncertainty/acceptance policy
                 |
          pass / clarify / reject
                 |
                 v
Bounded executive owns tools and trusted state
                 |
                 v
Temporal monitor + observation validation + watchdog + recovery
```

The diagram is a proposed architecture. Source spans provide auditability and can detect unsupported values, but a model-selected span can still be wrong. A second model reading the first model's explanation is not an independent formal check.

For “request inspection if temperature is above 70 C,” the admitted plan should bind the asset, `temperature`, `gt`, 70 and C; read the observation; explicitly handle read failure; evaluate the guard in trusted code; and only then issue the inspection request. Evaluating the comparison in trusted code removes arithmetic/branch execution from the model. It does not prove that `gt`, rather than `ge`, was the intended translation. A narrow controlled input language can make that translation deterministic; unrestricted language requires empirical and selective reliability evidence.

Validation should block or ask for clarification rather than silently rewrite the requested operator, threshold or action. If the system offers a changed plan, present it as a distinct proposal requiring the applicable operator workflow. This preserves the distinction between preventing harm and completing the requested task.

## 5. A focused experiment rather than another model sweep

Freeze one new protocol before evaluating new independently authored requests. Preserve current maintenance sets as development/regression evidence. Cross operators, thresholds, units, negation, multiple assets, stale observations, missing reads, updates and unsupported requests. Use complete episodes as calibration/evaluation units where steps are dependent.

| Arm | What it isolates |
|---|---|
| Authored rules + bounded executive | Whether learning is necessary within the supported domain |
| TF-IDF/structured encoder + same gate/executive | Cheapest learned semantic interpretation |
| LLM + syntax constraints only | Structural validity benefit |
| LLM + domain/grounding checks + executive | Added semantic and execution enforcement |
| Best proposer + calibrated abstention | Error/coverage/help tradeoff |
| Optional ARM versus FPGA monitor | Enforcement timing/isolation/resource tradeoff with identical policy |

Keep safety checks and observation access equal across proposers. Candidate pruning must depend on public state/catalog and policy, never gold decisions. A rule that computes the answer from a hidden label is not a validator. A trusted simulator can check execution semantics, but cannot independently certify the natural-language label from which its goal was constructed.

Report:

- Complete requested-task correctness over all requests, plus actionable completion.
- Wrong accepted plans / accepted plans, with confidence bounds and coverage.
- Executed policy violations, rejected unsafe proposals, unnecessary rejection and clarification burden.
- Operator/threshold/asset error subgroups and unseen-language/asset performance.
- Episode success, time to first error, stale-state violations and timeout recovery.
- End-to-end latency distribution, deadline misses, verifier WCET evidence, peak memory and complete model cost.
- Whole-system energy over all attempts and correct on-time completions; count failed attempts and clarification overhead.
- Numerical fidelity after quantization and changes to rankings, confidence, acceptance decisions and branch outcomes.

Do not claim rare-error reliability from a tiny perfect test. With zero errors in n independent accepted trials at a fixed acceptance policy, the one-sided 95% binomial upper bound is `1 - 0.05^(1/n)`. To bring this below 0.1% requires 2,995 accepted independent trials; below 0.001% requires 299,572. These are illustrative calculations under the stated assumptions, not requirements derived from an industrial standard. Adaptive threshold selection on the same test or correlated templates invalidates that simple reading. Report accepted and total trial counts separately.

## 6. Priorities and research positioning

**First:** Formalize the task contract and execution state machine. Select a small set of enforceable invariants with explicit assumptions and failure behavior. Define request fidelity separately.

**Second:** Implement the smallest software admission gate/executive and compare it against our current schema-only path. Study the exact failure types already exposed by conditionals, then test the revised design on new data.

**Third:** Add an appropriate acceptance-risk procedure and measure help burden. A stronger calibrated predictor is useful only if it accepts enough correct actionable work.

**Fourth:** Measure target resource/deadline costs and investigate hardware monitoring where it addresses an actual requirement. Do not begin with a general grammar accelerator or unrestricted on-board theorem prover.

The promising research question is: **At fixed task quality and compute/memory/deadline budgets, which combination of bounded proposal, admission checks, abstention and trusted execution maximizes correct on-time autonomous completion?** A second question is whether FPGA enforcement provides a measured benefit over a small ARM checker under contention and injected faults.

Prior art already covers grammar validity, shields, embedded temporal monitors, reject options, conformal help, checked planning and proof-carrying artifacts. Potential contributions must come from a well-defined remaining gap and controlled evidence: language-to-contract errors that escape conventional validators; acceptance-risk versus useful completion on small quantized models; or a measured enforcement boundary on heterogeneous constrained hardware. No novelty or publication claim is established by this review alone.

## Companion files and local context

Follow-up novelty screen, October 25: the implementation-plan search identified closer embedded/agent work omitted from the initial synthesis: LIR+LVM bounded MCU execution, VIGIL verify-before-commit, a guard-precision preprint, and an October 15 hardware-interlock defensive disclosure. These narrow the novelty of generic bounded execution and FPGA release gates. See `2026-10-25-bounded-maintenance-implementation-plan.md` for direct links, reading/access limits, and a revised contribution candidate. The registry adds S45–S48 without changing the initial 44-source reading-depth records.

- `2026-10-25-bounded-reliable-output-sources.json`: annotated primary-source registry with reading depth and guarantee boundaries.
- `2026-10-25-maintenance-decision-models.md`: current probability-output experiment and its limitations.
- `2026-10-22-maintenance-finetuning.md`: complete-plan and crossed-conditional evidence motivating this review.
- `2026-10-22-sealed-verification-prefix-v16-results.md`: execution/runtime integrity evidence, distinct from request semantics.

This review adds documentation only. It does not change the stopped full-sweep policy or qualify any new runtime, model, monitor or board configuration.
