# Persona 3: industrial AI / CPS assurance reviewer (DATE, EMSOFT, IEEE TII, PHM Society, SAFECOMP)

Round 1. Inputs: repo_context.md, corrections.md (taken as authoritative: decode is about 6 tok/s end to end; the LM head is already at its bandwidth floor; no energy has been measured), and lit files A–F. I also ran five web searches on 2026-11-08; their results are cited below as [S1]–[S5].

## How I read the project as a reviewer

To an assurance reviewer, the honest negative result is the most useful asset here. Small LLMs write poor complete maintenance plans (Qwen3-1.7B scores 15/120 fresh and 0/64 conditional), while a rules engine scores 120/120. Do not hide this. It is the empirical premise of LLM-Modulo (D28), and industry has already landed on the same architecture: IBM's Condition Insight (D05) uses deterministic evidence, constrained synthesis and a rule-based verifier, and is deployed in production.

That gives us the question an industrial reader actually asks. In which narrow job does a bounded on-device LLM add value next to a sound rules engine? Can we prove, in a way a third party can re-check, how often it is allowed to be wrong?

One caveat before anything else: the 120/120 result is circular. The rules engine and the template generator encode the same rules, so a reviewer will dismiss that number. Headline claims must therefore come from public, human-authored data: MaintIE/MaintNorm (D06, D07), FailureSensorIQ (D01), AssetOpsBench (D02) and PHMForge (D03).

What the assets support. These are the ones I would build on:
- A bit-exact, batch- and cache-invariant decoder: 328/328 cached runs identical to cold controls, against 16 divergences on llama-server.
- Per-token logits and hidden states that are free to read.
- Integer-folded temperature calibration and OOS thresholds from the v1 lineage.
- Decision heads trained over frozen hidden states.
- Typed outputs, with the R5 owning the output path.
- Weight SHA checks, sealed read-only mappings and evidence seals.
- A self-contained ~$350 board with no network dependency.

What does not help us in these venues: throughput (TeLLMe v2 reaches 25 tok/s at about 5 W on the same K26), and energy, since nothing has been measured yet.

---

## Niche 1: The LLM as a typed extractor and proposer under a sound verifier, offline, on real work-order text

**(a) Claim.** On real maintenance short text (MaintIE/MaintNorm) and on an AssetOpsBench/PHMForge work-order subset, an air-gapped pipeline has three parts: a 0.6B on-fabric LLM that only extracts typed slots and proposes candidate actions, an abstention head, and a rules engine that plans and verifies. At a stated coverage, this pipeline gives far fewer unsupported or unsafe actions per 100 work orders than complete-plan generation by 1.7B–8B models, and no action reaches the CMMS boundary without verification.

**(b) Why this is not already done.**
- **Industrial LLM-Modulo exists, but only in the cloud.** Condition Insight (D05) and LLM4PLC/Agents4PLC (D12, D13) run on cloud or workstation hardware with no abstention guarantee. D-gap 3 states that "no paper reports an on-device, air-gapped LLM-Modulo loop with abstention for OT."
- **MaintIE has no LLM results yet.** It has only 2024 NER/RE baselines. My search [S3] found no 2025–26 comparison of small models against LLMs on MaintIE.
- **Neighbouring benchmarks score other things.** DiagnosticIQ (May 2026; found in [S4], not yet in our lit files, so it must be added and checked) turns engineer rules into MCQA for action recommendation. It scores recommendation accuracy, not extraction feeding a verifier, and it is not on-device.
- **Small-model work points the same way.** The SLM tool-calling literature (B13, B14) concludes that sub-2B models are "components in bounded local tool systems." B14 shows this on CPU only, with about 5% strict JSON validity and no verifier.
- **Air-gapped OT deployment is vendor marketing, not peer-reviewed evidence.** My search [S2] returned only vendor pages, such as on-prem NVIDIA appliances. I found no peer-reviewed evaluation.

**(c) Minimal experiments and metrics.**
1. *E1.1 Extraction.* Map MaintIE entities and relations, a subset of its 224 leaf types, onto a compact ISO 14224-aligned typed schema (D09 suggests the mapping).
   - Systems compared:
     - Qwen3-0.6B few-shot with grammar-constrained output.
     - Qwen3-0.6B with a LoRA fine-tune (assumes a merged model of the same architecture can be re-quantized to Q8_0 and resealed).
     - A MiniLM encoder slot head from the v2 lineage.
     - A CRF or TF-IDF baseline.
     - Qwen3-1.7B, 4B and 8B in software.
   - Metrics: field-level precision, recall and F1, and selective field precision at 50/80/95% coverage.
2. *E1.2 Normalisation robustness.* Run the same models on MaintNorm-style shorthand ("c/o", "u/s") with and without a deterministic normaliser in front. Also rename schema fields and tool names to test the overfitting effect Hammer (B05) reports.
3. *E1.3 End to end.* Extracted slots go to the rules engine, which plans; the plan is checked by the verifier. Compare against complete-plan generation by the 1.7B–8B models on 40–60 AssetOpsBench work-order/FMSR queries plus 30 PHMForge scenarios, using PHMForge's deterministic evaluators.
   - Task success at fixed coverage.
   - **Unsupported Claim Rate** (adopted from D05).
   - **Unverified-action count**, which must be 0 by construction.
   - Escalations per 100 work orders.
   - p50/p90 wall time per work order on the board. Typed outputs of about 40 tokens at about 6 tok/s with jump-forward come to roughly 5–8 s, which is acceptable for maintenance work but must be reported.
4. *E1.4 Board replay.* Rerun the final configuration on the KR260 and confirm the outputs are bit-identical to the C reference, with an evidence seal.

**(d) Reused assets.** Qwen3-0.6B Q8_0 fabric decoder; ARM JSON validator; typed output schemas; the rules engine and verifier (already 120/120 on its own domain); decision and abstention heads; MiniLM encoder heads (the v2 slots task); BFCL harness; prefix cache, since a fixed schema and system prompt make prefix reuse very effective here; JSON-state compaction.

**(e) Cost and main risk.**
- *Cost.* About 7–9 weeks for one person.
  - 2 weeks: the schema mapping and the rules engine adapter for MaintIE and AssetOpsBench.
  - 2 weeks: software sweeps.
  - About $50–150 of GPU time for LoRA runs.
  - 1–2 weeks: board replay and the write-up.
- *Main risk.* The 0.6B decoder may not beat the MiniLM encoder or a CRF at extraction, in which case "LLM" is not the right System-1. That result is still publishable as a decision-relevant finding in TII or PHM ("use the encoder; keep the decoder for free-text proposals"), but it weakens the FPGA-LLM story. A second risk is AssetOpsBench tooling: CouchDB plus cloud-agent orchestration may be heavy to port offline, so fall back to PHMForge's deterministic evaluators.

**(f) Venue.** PHM Society Annual Conference 2027 (applied, values public-benchmark honesty) or the IEEE TII journal. ACL/EMNLP Industry Track is an alternative if the NLP part dominates.

**(g) Kill criterion.** Kill the "on-device LLM" framing and pivot to the encoder if either of these holds:
- At 80% coverage, the best on-device configuration does not reach field precision of at least 0.95 on MaintIE.
- The 0.6B decoder trails the MiniLM/CRF baseline by more than 5 F1 at equal coverage.

Kill the end-to-end paper if extractor + rules engine does not beat complete-plan generation by the 1.7B–8B models on Unsupported Claim Rate by at least 2x on the public subset.

---

## Niche 2: Replayable risk-controlled abstention, where coverage guarantees can be audited because the score function is bit-exact

**(a) Claim.** Conformal and risk-control guarantees for selective typed decisions assume a fixed score function. Only a bit-exact inference platform lets a third party replay the calibration set, the threshold and every deployed accept/abstain decision, and verify them by hash. On common CPU/GPU stacks, we measure score jitter under batching and prefix caching, and the accept/abstain flips it causes near the threshold, which make the stated guarantee unauditable.

**(b) Why this is not already done.**
- **The guarantee frameworks are mature and silent on determinism.** This covers KnowNo (D22), conformal factuality (D21), Trust-or-Escalate (D37), Conformal Cascade (D38), Conformal Arbitrage (D39) and CAP/conformal abstention [S1]. All of them assume exchangeability under a fixed score function, and none treats run-to-run non-determinism of the scorer. My search [S5] found no paper connecting batch invariance or non-determinism to the validity or auditability of conformal guarantees. The closest is work showing coverage collapses when the model changes (continual-calibration paper, alphaXiv 2604.23987).
- **Function-calling UQ reports AUROC only.** D24 (Apple, 2026) evaluates UQ on BFCL with AUROC and no coverage guarantee.
- **The determinism literature does not touch calibration.** It covers B39, C12–C16, DetLLM (NeurIPS 2026, same Qwen3-0.6B model, integer-only on A100) and TOPLOC/SVIP (C21, C22). It treats reproducibility for verification and RL, not the validity of calibrated abstention. C-gap 3, "commit-by-hash replaces fuzzy verification", is the hardware half of this niche.
- **One relevant theory paper.** arXiv 2606.29054, "When Can Conformal Risk Control Certify LLM Outputs? … Structured Generation" (found in [S1]; must be read), characterizes the abstention forced under schema-validated losses. That is theory our measurements can instantiate.

**(c) Minimal experiments and metrics.**
1. *E2.1 Score jitter census.* Run three tasks under nine runtime configurations.
   - Tasks: FailureSensorIQ (D01; option logits, about 8.3k items, objective answers), the BFCL relevance/irrelevance split with the D24 protocol, and MaintIE field-level decisions from Niche 1.
   - Configurations: FPGA; llama.cpp CPU with threads 1/4/8, batch 1/8, prompt cache on/off; a GPU default; GPU in deterministic mode (SGLang or batch-invariant kernels).
   - Metrics: the fraction of items whose nonconformity score changes bitwise; the max and p99 score delta; the **decision-flip rate** at the calibrated threshold; the first-divergence token.
2. *E2.2 Guarantee validity.* Calibrate on one configuration and deploy on another, as happens in practice when a cache or batch size changes in the field. Report empirical risk against nominal α, from 0.05 to 0.2, over 1,000 random calibration/test splits. Compare with the finite-sample slack band.
   - Methods: split conformal (KnowNo-style singleton-or-escalate sets) and Learn-Then-Test risk control for field-level back-off (Mohri-style, D21).
3. *E2.3 Audit protocol.* For each decision, the evidence seal records the input hash, the score, the threshold, the calibration-set Merkle root, the weight SHA and the bitstream hash. An auditor reproduces the result on the C reference or a second run. Measure the auditor's cost (s/decision), the seal bytes, and how often an injected change is detected: a Q4 weight swap, a single-bit flip, a threshold edit, a calibration-set edit.
4. *E2.4 Small-model calibration.* Compare the integer-folded temperature against verbalized confidence and a probe head on frozen states (B37, D18), measuring ECE and AURC on the 0.6B model.

**(d) Reused assets.** Bit-exactness against an independent C reference; the 328/328 cache-equivalence harness; the llama-server divergence finding; the v1 integer-folded temperature and threshold rule; decision heads; evidence seals and weight SHA; BFCL harness.

**(e) Cost and main risk.**
- *Cost.* About 6–8 weeks, mostly software. Board time is spent replaying FailureSensorIQ items: one forward pass of prefill plus option scoring per item, roughly 1–2 s, so about 3–4 board-hours with prefix reuse of the shared instructions. GPU runs need a short rental.
- *Main risk.* Jitter may be negligible in practice: flips sit far below the finite-sample slack, so the effect would be real but small. The paper then becomes "auditability, not validity", which is weaker but still relevant to SAFECOMP. Reviewers will also note that GPUs can be made deterministic (B39, DetLLM). Our answer has to be cost and independence. On the FPGA, determinism costs nothing at the same speed and is checked against an independent reference. DetLLM's prefill is 0.13x fp16. The deterministic-mode GPU overhead should be measured ourselves rather than asserted.

**(f) Venue.** SAFECOMP 2027 (dependability plus ML assurance; its usual spring deadline fits a 3–5 month window), or EMSOFT through ESWEEK/TECS. The UAI/AISTATS application tracks are an alternative if the statistics carry the paper.

**(g) Kill criterion.** Kill the validity claim and keep only an audit-protocol short paper (or fold it into Niche 1 as one section) if both of these hold:
- Across all non-FPGA configurations, the decision-flip rate is below 0.1% of decisions on all three tasks.
- Cross-configuration empirical risk stays inside the finite-sample band at every α.

Kill the niche entirely if a GPU in deterministic mode reaches bitwise score identity with less than 10% overhead, because then the hardware adds nothing beyond a configuration flag.

---

## Niche 3: Gating LLM actions outside the model's trust domain in OT, with fault-injection evidence and an assurance case

**(a) Claim.** On a single Zynq SoC, the LLM's typed actions can be gated outside its trust domain: an R5-owned output path, a rule check on that path, sealed weights, and a periodic or streaming weight-integrity check. Under three attack and fault classes, this gating ensures that no silent "valid-looking but wrong" action crosses the CMMS/actuation boundary, at measured overhead:
- weight and K/V bit flips;
- DDR tampering after startup (the TOCTOU gap);
- prompt injection embedded in work-order text.

**(b) Why this is not already done.**
- **Agent guardrails share the agent's trust domain.** AgentSpec, ShieldAgent and Progent (D25–D27) run in the same software domain as the agent, as D-gap 5 notes.
- **SILK solves integrity, not action safety.** SILK (corrections item 3; C30) closes the TOCTOU gap for accelerator integrity, but it is not tied to LLM action safety.
- **GPU fault-injection studies cannot attribute deviations.** GPU SDC studies (C33, C34) must separate faults statistically from non-determinism. Our exact golden model makes every deviation attributable (C-gap 6).
- **Accelerator papers ignore integrity.** No FPGA LLM paper treats it (A-gap 3).
- **Production systems keep the verifier in the cloud.** Industrial LLM work (D05, D12) does not put the verifier in a separate hardware domain.

**(c) Minimal experiments and metrics.**
1. *E3.1 Fault-injection campaign.* Inject single-bit and multi-bit flips into Q8 values versus FP16 block scales, BF16 K/V and activations, using DDR writes from the ARM and a debug path. Use about 5–10k injections on Niche 1/2 inputs.
   - Classify each outcome as masked, benign deviation, invalid-and-caught by the validator, abstained by the head, or **silent wrong-valid**, measured with and without the gate.
   - Metric: silent wrong-valid rate per injection, with a Clopper-Pearson upper bound.
2. *E3.2 TOCTOU.* Flip selected weight bits in DDR after startup verification. Show that startup-only SHA misses the change. Then measure detection latency and decode slowdown for two checks: (i) an ARM-side periodic re-hash, which costs zero PL area; (ii) a streaming CRC or sparse keyed check on the 256-bit weight stream, if routing allows.
3. *E3.3 Injection in operator text.* Insert adversarial instructions into MaintIE-style work orders, AgentDojo-style. Measure the attack success rate at the CMMS boundary for three systems: the LLM alone, a software guard on the ARM, and the R5-owned typed gate.
4. *E3.4 Assurance case.* Build a GSN argument mapping the evidence to IEC 62443-4-2 component requirements (integrity, least privilege) and to a SOTIF-style hazard list for maintenance actions. Mark the residual claims, such as verifier completeness, explicitly as out of scope.

**(d) Reused assets.** R5 AMP output-path ownership and typed decisions (v2 assurance work); weight SHA plus sealed read-only mapping; exclusive inference lease; evidence seals; bit-exact references for attribution; the rules verifier from Niche 1.

**(e) Cost and main risk.**
- *Cost.* About 8–10 weeks. The fault harness and ARM periodic re-hash take 3–4 weeks. The GSN case takes 2 weeks.
- *Main risk.* PL is already 92–96% CLB, so a streaming in-fabric checker may not route at 250 MHz. Mitigate with the ARM re-hash and a sampled check, and report the area as a limitation.
- *Second risk.* Reviewers may see the gate as "just a whitelist." The contribution has to be the measured attribution of silent wrong-valid actions and the trust-domain separation, not the rule logic itself.

**(f) Venue.** EMSOFT (ESWEEK) or SAFECOMP 2027. DATE 2028 fits the hardware-integrity part, but its deadline (usually September) falls outside the 5-month window. A DSN workshop (DSML) is a quick option.

**(g) Kill criterion.** Kill if either holds:
- Without the gate, the silent wrong-valid rate is already statistically 0 (the upper bound is below the gated system's bound), because then the validator plus abstention head explain everything and the hardware domain adds nothing measurable.
- Both the ARM re-hash and the in-fabric checks cost more than 15% of decode time and cannot route.

---

## Strongest niche overall, and one trap

**Strongest:** Niche 2, executed on Niche 1's public tasks. "Calibrated typed abstention whose coverage guarantee is replayable and auditable because the scorer is bit-exact" is the only claim where determinism, the project's one property competitors cannot easily match, becomes a *safety argument* rather than a systems curiosity. It is cheap: mostly software, plus a few board-hours of FailureSensorIQ and MaintIE replay. It uses public, objective benchmarks, and my searches found no paper linking scorer non-determinism to the validity or auditability of conformal guarantees.

Niche 1 supplies the industrial motivation and the "LLM proposes or extracts, rules engine disposes" architecture. Niche 3 is the natural follow-on journal extension.

**Trap:** leading with the template-derived maintenance benchmark, in either direction. The rules engine's 120/120 is circular because the same rules generated the labels, and the LLMs' low scores partly measure template mismatch. A TII or PHM reviewer will reject a paper whose headline numbers come from a self-built benchmark that the baseline wrote. Keep the template set only as a controlled stress test (crossed-conditionals). Put every headline number on MaintIE, FailureSensorIQ and PHMForge/AssetOpsBench. Never call a conformal bound a "guarantee" for a live plant without stating the exchangeability assumption and a drift-monitoring plan.

---

## Web searches run (2026-11-08)
- [S1] "conformal prediction maintenance work order LLM extraction abstention coverage guarantee". Found CAP (arXiv 2502.06884 / PMLR v304), arXiv 2607.04430, arXiv 2606.29054 (CRC certification for structured generation) and a Chalmers thesis. Nothing specific to maintenance.
- [S2] "air-gapped OT on-premise small language model maintenance assistant verifier rules engine 2026". Vendor pages only (ifactoryapp, premai, others). No peer-reviewed work.
- [S3] "MaintIE small language model LLM information extraction benchmark 2025 2026 results". Only the original LREC-COLING 2024 paper. No LLM results.
- [S4] "LLM proposer symbolic verifier maintenance planning work order generation …". DiagnosticIQ (May 2026, maintenance action recommendation from symbolic rules, MCQA); SafePilot (arXiv 2603.21523, LLM planner with formal verifier for CPS); LLM-R (RAG maintenance schemes). None is on-device or has abstention guarantees.
- [S5] "conformal calibration nondeterministic LLM inference batch invariance …". No direct hit. Closest is coverage collapse under model change (alphaXiv 2604.23987) and black-box agent reliability certification (arXiv 2602.21368).

Items from [S1]–[S5] that are not in lit files A–F (DiagnosticIQ, SafePilot, arXiv 2606.29054, arXiv 2604.23987) were seen only as search snippets. Check them before citing.
