# Comparison with the earlier ChatGPT review (2026-11-04)

I wrote this after finalising `README.md`. The earlier review consists of:
- `docs/research/2026-11-04-system-one-research-niche.md`
- `2026-11-04-niche-hardware-papers.md`
- `2026-11-04-niche-tool-papers.md`
- `2026-11-04-niche-assurance-papers.md`

## 1. Headline decisions

| | ChatGPT review (Nov 4) | This review (Nov 8) |
|---|---|---|
| Primary target | **Exact recovery of a committed KV prefix after interruption** at the PS–PL boundary. Qualify AXI write retirement and visibility, keep a watermark, replay only the suffix, and compare against full replay and the v16 happy path. | **Exact schema-aware decoding.** Token-level grammar forcing through B8 prefill plus a grammar-range LM head, with N/N output identity. |
| Follow-ons | (2) Characterise retention and prefix reuse on independent traces. (3) Conditional tool proposals with receipts and calibrated abstention. (4) A hardware gate for observable effects. | (2) Fault injection with exact attribution and the TOCTOU gap. (3) Cross-platform exact-commit replay vs TOPLOC. (4) DSP line-rate weight MAC. (5) Energy section. (6) Replayable conformal abstention. (7) MaintIE extraction. (8) Integer-spec (DetLLM) port. |
| Corpus | 131 distinct works (145 entries) | ~200 distinct works (225 entries, 186 unique arXiv IDs) |
| Depth on the repo | Deeper. Inspected the generated AXI adapter (`BRESP`/`RRESP` unused), ABI2 `SYNC_COMMAND` semantics, v9d routed reports and KV byte budgets, and re-checked v13/v14 seals. | Shallower on the repo. One source check: the LM-head row-range command is batch-1 and returns argmax only. Broader on the literature. |

## 2. Where the two agree (independently reached, so higher confidence)

1. **Exactness is the asset; it is not the claim.** Both reviews conclude that generic FPGA acceleration and fast Kria decoding are already published (Li et al., Hummingbird, TeLLMe v2, PD-Swap) and that a tok/s race is not a contribution.
2. **Do not headline maintenance quality.** The template set is circular. Both want independently authored or public workloads and keep the LLM in proposal mode.
3. **Exact prefix reuse (328/328) is real but not novel on its own.** SGLang, Prompt Cache and TensorRT-Edge-LLM content-addressed reuse exist. It is an enabler, so build on it.
4. **Claims must be scoped to qualified boundaries,** with go/no-go gates before any new routed build. Both apply kill criteria.
5. **Energy is an extension or section,** pending whole-board instrumentation, not a standalone result.

## 3. What the ChatGPT review found that this one missed

- **A whole cluster on KV recovery, rollback and serving fault tolerance.** This one missed it entirely:
  - Aborted but Not Forgotten (2608.15939), PatchKV, Concordia, KevlarFlow, LUMEN, HCache, Pensieve, mzCache, Range, "Silent and Costly", EfficientAgent;
  - TransKV and SubTernary (transactional KV for speculation);
  - the vLLM Holemiss RFC.

  These matter to us in two places:
  - **T1's speculation stretch** needs a KV rollback story. SubTernary/TransKV are the precedent for pointer-only commit and rollback.
  - **T2's fault study** should state what happens to cache state after a fault.
- **FPGA isolation and protection precedent.** Restuccia et al. AXI timeout/isolation on Zynq (FCCM 2020), Coyote (OSDI 2020), AmorphOS (OSDI 2018), and FINN-Tro (2026, datapath Trojan). T2 and T4 should cite these.
- **A concrete hardware observation:** the generated state AXI adapter does not use `BRESP`/`RRESP`. So a transport error on the KV/state path would be silent. That is directly a **T2 fault-model finding** and arguably the most valuable single fact in either review for the dependability paper.
- **Agent-abstention and tool-fault benchmarks:** AgentAbstain (2607.10059) and ToolBench-X (2606.25819). Both are relevant to T6 and to the public-workload requirement.

## 4. What this review found that the ChatGPT review missed

These are the gaps that most change the decision:

- **DetLLM (NeurIPS 2026).** Integer-only, bit-identical **Qwen3-0.6B**, our exact model. It is absent from the earlier review. It removes "deterministic FPGA LLM" as a contribution, and it opens a cross-vendor identity path (T8).
- **The entire verifiable-inference and nondeterminism literature:**
  - TOPLOC, SVIP, DiFR;
  - bit-exact verification via emulation (ICML 2026);
  - cross-GPU bit-exact kernels (2609.25624);
  - Thinking Machines batch invariance, SGLang deterministic mode, LLM-42;
  - Cai et al. on substitution auditing failing under nondeterminism.

  This is what turns our exactness into T3, and it explains our own 16 llama-server divergences.
- **SILK (2608.26402).** The TOCTOU gap in startup-only weight checks, demonstrated on Zynq. Our v16 "sealed" weights are verified only at startup. This gives T2/T4.
- **Grammar-constrained and jump-forward decoding, and speculative decoding:** XGrammar, Gram2Token, DOMINO, SGLang jump-forward, EAGLE/REST/lookahead, and FPGA speculation (DATE'26, SPECTRA, Cassandra). Plus the observation that nobody has done grammar-aware decoding in edge hardware. This gives T1. The earlier review mentions XGrammar once and speculation only as KV-transaction precedent.
- **Conformal, risk-control and abstention literature** (13 entries) and **public industrial benchmarks** (FailureSensorIQ, AssetOpsBench, MaintIE/MaintNorm, PHMForge). This gives T6 and T7, and it answers the earlier review's request for "independently authored cases" with concrete datasets.
- **Bit-flip and fault-injection literature** (PrisonBreak, GPU SDC studies) and the power-sensor calibration literature (Yang et al., Jetson sensor studies, TeLLMe v2 energy bar).

## 5. Assessment of the ChatGPT primary target

**Strengths.**
- It is tightly grounded in the actual hardware. The AXI retirement/visibility analysis is careful and correct in spirit.
- It needs no capability improvement from the model.
- It reuses the v14/v16 machinery directly.

**Weaknesses (my view).**
1. **Thin novelty margin, which the review itself concedes.** The rollback algorithm is already in Aborted but Not Forgotten, and copy-free rollback in SubTernary. The review states that "a cooperative-cancel-only result could amount to a local implementation of known truncation." The contribution survives only if the in-flight AXI fault boundary can be qualified, and that needs a new routed, instrumented image at 96% CLB.
2. **The benefit depends on interruption frequency,** which is low for a single-user edge tool-caller. The headline metric (time to matching answer after interruption) matters only if interruptions are common. Reviewers will ask for a realistic interruption model.
3. **It does not use the most distinctive asset at full strength.** Exactness is used as an oracle, but the paper's value is robustness engineering. T1–T3 make exactness the *enabling property* of the result.

**Verdict.** It is a solid **component**, not the best flagship. It fits naturally inside **Paper B (dependability)**. Fault injection (T2) creates exactly the interruptions and in-flight faults that the recovery contract must handle. The silent `BRESP` finding motivates the injection campaign. An "exact recovery vs quarantine" outcome class enriches the T2 taxonomy.

## 6. Merged recommendation

| Rank | Target | Source | Paper |
|---|---|---|---|
| 1 | **T1 Exact schema-aware decoding** (+ output-identity invariant over prefix reuse; speculation as a stretch once the LM head is batched, using SubTernary/TransKV-style rollback) | Claude | A (flagship, FPL'27) |
| 2 | **T2 + ChatGPT-R1 Exact-attributed fault injection with recovery-or-quarantine:**<br>• DDR bit flips<br>• silent AXI response path (`BRESP` unused)<br>• TOCTOU after startup SHA<br>• exact prefix recovery when the fence is qualified, quarantine otherwise | both | B (DSN-W/SELSE → SAFECOMP) |
| 3 | **T3 Cross-platform exact-commit replay vs TOPLOC** ("auditable") | Claude | C (workshop → MLSys'28) |
| 4 | **T4 DSP line-rate weight MAC** (conditional; read SILK in full first) | Claude | B or standalone FPT/HOST |
| 5 | **T6 Replayable risk-controlled abstention** on FailureSensorIQ / BFCL / AgentAbstain (conditional; read RCP first) | Claude + ChatGPT-3 | C |
| 6 | **T7 Typed extraction on MaintIE/MaintNorm** as the real-text workload | Claude, answering ChatGPT's "independent cases" | A's workload |
| 7 | **ChatGPT-R2 Retention/prefix-reuse characterisation on independent traces** | ChatGPT | a section of A (not standalone) |
| 8 | **T8 Integer-spec port for cross-vendor identity with DetLLM** | Claude | horizon (FCCM/FPGA'28) |
| — | **T5 Energy:** a required section of A and B | both | — |
| — | **ChatGPT-R4 Hardware gate for observable effects:** defer until capability evidence exists (both reviews agree) | ChatGPT | — |

**Immediate next step (2 weeks, mostly software, one short board window):**
- the T1 gate: offline forced-fraction and range statistics from the C reference, plus a board B8-vs-sequential bitwise test;
- the T2 gate: 500+50 flips over 50 BFCL calls;
- a quick read of SILK and RCP in full.

The ChatGPT review's AXI fence simulation (its §First experiment, step 1) slots in as T2's offline component.
