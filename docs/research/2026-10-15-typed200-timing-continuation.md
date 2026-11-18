# Typed output timing continuation

Work resumed under the existing authorization to continue local implementation.
The qualified 200 MHz baseline, five prior validation seals, recovery and package
remain frozen. No board programming, builds of bitstreams or automation are part
of these experiments. This document is a live work record, not a validation seal.

## Clock synthesis experiment

[The clock experiment runner](../../scripts/v2/kr260/check_typed200_synthesis_clock.py)
stages the exact 28 compiled
encoder RTL inputs and the generated parameter wrapper from the sealed FIFO
candidate. It runs sequential unconstrained and explicit 5 ns OOC synthesis with
the same part, source order and synthesis options. All 602 preservation paths and
420 entries across the prior source/document/evidence maps passed the initial
rehash. The first attempt failed before native synthesis on S:/C: alias mapping;
its partial inputs remain preserved. Actual runs use
`build/v2/typed200-synthesis-clock-v2/` for the completed unconstrained control.
The corrected clocked run uses `typed200-synthesis-clock-v3`, reusing the exact
hash-identical completed control rather than rebuilding it.

`read_xdc` occurs before `synth_design`. The XDC creates the 5 ns clock using
only supported constraint commands. Native logs must show it parsed before
optimization; a post-synthesis native query must find exactly that clock and
period, with no critical synthesis warnings. Merely
adding a clock after synthesis would not test the synthesis optimization issue.
The unconstrained control intentionally has no timing estimate; it reproduces
the missing-clock condition. OOC I/O timing is not full-design timing closure.
The clean unconstrained control reproduces the original encoder synthesis
netlist checksum exactly: `aefdbf25` in both native logs. Thus the direct RTL plus
generated parameter-wrapper reconstruction reproduces the prior mapped control,
despite avoiding a mutable import of the original generated IP configuration.

Clean v3 synthesis completed successfully with zero errors/critical warnings.
Native query reports exactly one encoder_ooc_200 clock at 5.000 ns, and mapping
checksum changes to `7764d478`. Encoder-only LUT use is 65,679 versus 66,758 in
the matched unconstrained control (1,079 fewer); registers 51,048, DSPs 579,
BRAM tiles 50 and URAMs 36 are unchanged. The clocked OOC report estimates
+0.855 ns setup and +0.036 ns hold. It lacks 197 input/270 output delays and
HD.CLK_SRC clock-delay/skew context, so this is neither full-design closure nor
a frequency/speedup result. A same-period control timing audit and composed
synthesis/placement are required to judge timing benefit.

The same-period control audit reports -0.387 ns setup / +0.036 ns hold; its
worst internal path is the original request_tile to status enable (17 levels,
5.259 ns estimated data). Clocked mapping moves the OOC limit to read-address
update through burst sizing: address bit7 to bit39, 16 levels including six
CARRY8 cells, 4.141 ns data (1.637 logic / 2.504 estimated route). This makes
registered/cached burst descriptors a concrete possible next experiment if
composed placement confirms the path. Do not retime the MAC simply because
a published design reports a higher clock; this internal estimate still excludes
the composed AXI response distribution path.

The first clocked v2 attempt used if/puts assertions/logging inside XDC; Vivado
rejected those commands as unsupported. Its create_clock command was parsed,
but the attempt was rejected and its verified process tree terminated before
completion. Logs, rejection receipt and exact runner-v2.py are preserved. This
was a flow validation error, not an RTL or functional counterexample. v3 uses
only create_clock in XDC and keeps assertions in the surrounding Tcl.

The separate prepared physical runner
`scripts/v2/kr260/build_typed200_clock_physical.py` adds a pre-synthesis hook to
the encoder module-reference run, an OOC-only XDC, a clock assertion/report hook
and disables cache use for the new project. It never clears an old cache. It
requires the standalone synthesis experiment to prove clock application first.
This runner completed synthesis, placement and native placement audit in
`build/v2/typed200-clock-physical-v1/` on unchanged sealed RTL. Final results below
supersede intermediate progress descriptions. No routed improvement is claimed.

Full composition: **68,498 LUTs / 53,651 FF / 579 DSP / 50 BRAM / 36 URAM**,
versus 69,524 LUTs and identical other totals in the frozen FIFO candidate.
Estimated setup improves from **-0.612 to +0.624 ns**, with hold **-0.087 ns**.
The integrated encoder uses 65,732 LUTs (mapping checksum e2d57667), slightly
different from standalone synthesis; these integrated reports control the physical
comparison. OOC post-hook reports +0.855/+0.036 ns with the required 5 ns clock.

The full design retains only real clk_pl_0 at 5 ns and unused clk_pl_1 at 10 ns;
the artificial OOC clock is absent. Native internal unconstrained/multiple-clock
checks are zero; eight synthesis no_clock pins still need post-opt rechecking,
as in the parent. The hash-bound synthesis review verifies all 30 staged / 28
compiled RTL sources, clock hooks, wrapper, numerical parent inventory and DCP.
The first review parser expected report_clocks column order; the timing summary
instead prints waveform before period. It blocked placement; the original parser
and rejection receipt remain preserved. The corrected parser requires exact
waveforms, periods and frequencies for both clocks. It passed before placement
was launched. No clock relaxation or native synthesis rerun was used.

Final clock-flow control placement is **+0.371 ns setup / -0.087 ns hold**,
superseding the placer's intermediate +0.420 ns. All twelve post-opt clock/timing
categories are zero, CDC is safely timed, epoch/publication/GPIO logic is retained,
the 39 exceptions are scoped vendor XPM constraints, and FIFO mapping remains
free of async reset/preset and LUTAR-1. Routing is rejected because the preserved
+0.500 ns placed setup margin is not met. No routing or hardware action followed.
Placed resources are **63,331 LUTs / 53,055 FF / 579 DSP / 50 BRAM / 36 URAM**;
the frozen FIFO placement used 64,340 LUTs / 52,184 FF. This stage therefore saves
1,009 LUTs but uses 871 more fabric FF, unlike the equal FF totals at synthesis.

The placed limit changes to **typed contract validation**: contract bank[6][2]
through comparison logic into last_request[24]/CE, 24 levels including 21 CARRY8,
4.252 ns data (2.277 logic / 1.975 estimated interconnect). This supersedes the
synthesis-only burst-sizing hypothesis as the next priority. Earlier counter/LUT
siblings retain their immutable functional evidence; their physical work is lower
priority until measured paths justify it.

New separate `typed200_profile_tree` changes only typed_intent_guard: all 256 SHA
bits compare in 32 byte groups, four preserved intermediate reductions and one
final reduction. KEEP boundaries express a balanced mapping; there is no new
register, truncated digest, admission delay or permission bypass. Exact sequential
guard equivalence passes in `typed200-profile-tree-formal-v2` for arbitrary frames,
proposals, core status, current quiet and resets, including private identity/limit
history. The first harness failed on unsupported private hierarchical references
and missing check lowering; it did not produce a functional counterexample. The
corrected harness uses explicit proof-only observation ports on copied modules.

Full profile-tree integration and a matched register-to-guard mapping probe are
complete. Full integration passes 5,400 words / 14 paired completions, exact AXI/
output cycles, completion counts and emulated publication ages, including negative
cases. The matched probe reduces the targeted contract path from 25 to 17 logic
levels, 21 to 10 CARRY8 stages and 3.494 to 3.359 ns estimated data delay; slack
changes from +1.380 to +1.515 ns. Its source flops model the existing AXIL contract
bank and are not an added candidate pipeline stage. This is a mapped-path result,
not full-device placement or Fmax evidence.

A separate `typed200_validation_tree` refinement preserves individual sequence,
zero-budget and empty-contract decision boundaries as well. Full old/new guard-
AND-gate sequential equivalence passes. The same probe gives exactly the same
17 levels / 10 CARRY8 / 3.359 ns / +1.515 ns; no additional timing benefit was
observed. The simpler one-file `profile_tree` is selected for full native work.
The refinement's full regression also passes 5,400 words / 14 paired completions,
including normal and negative cases. Retain the result without promoting extra
source changes on intuition.

[Immutable validation functional/probe evidence](2026-10-15-typed200-validation-functional-evidence.json)
fixes both candidates' exact source inventories, creators, proof generators,
integration/probe runners and receipts. Both actual WSL source trees were rehashed;
every copied candidate file, including manifests and README, matches its original
pre-build hash. No corresponding source/evidence map may be edited. This record
is not composed physical qualification.

Selected `typed200-profile-tree-physical-v1` full synthesis completed with
**68,552 LUTs / 53,651 FF / 579 DSP / 50 BRAM / 36 URAM**. Estimated whole-design
setup is **-0.078 ns**, worse than the +0.624 ns unchanged-RTL clock-flow control;
hold is -0.087 ns. The local probe gain is therefore not a whole-design synthesis
gain. The new synthesized limit is SmartConnect read-FIFO empty/availability to
encoder status enable: 15 levels, 4.725 ns data, 3.667 ns estimated interconnect
(77.6%). Exact source/clock review passes.

Final profile-tree placement is **+0.358 ns setup / -0.106 ns hold**, compared
with **+0.371 / -0.087 ns** for the unchanged-RTL clock-flow control. It uses
**63,494 LUTs / 53,173 FF / 579 DSP / 50 BRAM / 36 URAM**. Native audit passes:
all twelve check_timing categories zero, CDC safely timed, retained epoch,
publication and permit logic, 39 vendor XPM exceptions only, no LUTAR-1 and zero
asynchronous-reset result-FIFO flops. The hash-bound placement review holds
routing below the same +0.500 ns margin. **Do not promote this candidate.**

The critical contract-bank-to-result-outcome path falls to 17 levels / 10 CARRY8,
but data delay is 4.233 ns: 1.672 ns logic plus 2.561 ns estimated interconnect.
Relative to the control's limiting path, logic improves 0.605 ns while wiring
worsens 0.586 ns and clock skew worsens 0.032 ns (-0.169 to -0.201). These are
different endpoints and placement solutions, not a controlled per-net attribution;
they explain why reduced carry depth did not establish a whole-design gain.

A separate physical-only Explore experiment starts from the stronger control's
original placed checkpoint, preserving both prior placement results and all RTL.
It uses `physopt_typed200_timing.tcl` and a fresh `postplace-opt-v1/` directory.
The review requires the original 5/10 ns clocks, retained typed controls, only
the same vendor XPM exceptions and the same +0.500 ns routing admission threshold.
No timing exceptions or semantic checks are weakened to obtain a pass.

Native Explore reports that all physical synthesis setup optimizations are skipped
because current WNS is already nonnegative (+0.371 ns). This command therefore
does not demonstrate an improved placement. Its fresh reports are retained for
audit, with no credit for a timing gain and no relaxation of route admission.
The run and hash-bound postplace review completed: **+0.371 ns setup / -0.087 ns
hold; route_approved=false**. All twelve timing checks remain zero; CDC, retained
typed controls, 39 vendor-XPM-only exceptions and synchronous FIFO mapping pass.
No native build or simulation remains active. No new routing, bitstream, package
or hardware deployment was performed. The qualified 200 MHz design remains the
only hardware-qualified implementation; none of these results establishes 300 MHz.

If placed typed validation still limits timing, a stronger *future* experiment is
incremental byte-equality flags in the AXIL shadow bank. Update each flag on the
same edge and same WSTRB byte enable as its corresponding stored profile byte,
using the newly written byte; otherwise hold it. Initialize each flag to whether
the expected contract byte equals the reset bank value zero. The required invariant
is `flag[i] == (bank_profile_byte[i] == expected_byte[i])` for every byte at every
sampled edge, including partial writes, reset, active-request writes and command
races. AND all 32 flags; never truncate the digest or let software set flags.
This could remove the wide compare from admission without adding an admission
cycle. It is not implemented or credited with benefit here. It needs endpoint-
level sequential equivalence and exact public/counter/deadline regression; current
live quiet, permission, error and epoch checks must remain uncached and immediate.
Only prioritize it if the selected candidate's actual physical result justifies it.

AMD documents loading XDC before synthesis, OOC clock constraints, synthesis
hooks and cache controls in [UG939](https://docs.amd.com/r/2022.1-English/ug939-vivado-designing-with-ip-tutorial/Step-6-Run-Synthesis),
[UG896](https://docs.amd.com/r/2023.2-English/ug896-vivado-ip/Constraint-File-Processing-Order),
[UG894](https://docs.amd.com/r/2023.1-English/ug894-vivado-tcl-scripting/Defining-Tcl-Hook-Scripts)
and [UG835](https://docs.amd.com/r/2024.2-English/ug835-vivado-tcl-commands/config_ip_cache).
Native 2025.2 execution, rather than documentation alone, determines acceptance.

## Separate RTL candidates

[The observation candidate](../../rtl/v2/candidates/typed200_observe/candidate.json)
changes only encoder_system plus a new
observed_cycle_counter. Accepted-start clear and increment events are registered
before the counter bank; the output applies the pending event so the value at
the original completion edge remains exact. Clear dominates increment, including
simultaneous events, with modulo-2^32 arithmetic. Admission, independent deadline,
epoch tracking, live quiet/error checks, numerical head and ABI are unchanged.

Actual 32-bit induction passed in `build/v2/typed200-observe-formal-v1/` against
the original counter recurrence under arbitrary clear/increment/reset, first-edge
reset and a single sampled clock. This is a counter proof, not whole-system or
physical evidence. Full independent frozen-parent AXI/output/cycle regression is
uses `simulation/v2/run_typed200_observe.sh`.
The observation regression completed successfully in
`build/v2/typed200-observe-integration-v1/`, using Verilator 5.040 in WSL:
5,400 golden words and 14 paired completions/launches, every driven AXI cycle
and raw encoder/request count unchanged. All eight T1/2/3/4/5/12/64/128 shapes
and six negative late/error/deadline/drain cases pass. Publication ages also
match the parent testbench; they remain emulated proposal timing, not R5 WCET.
Both new regressions assert raw encoder/request counter equality on every sampled
cycle, in addition to the completion-boundary and CSR comparisons.

[The LUT capture candidate](../../rtl/v2/candidates/typed200_lut_capture/candidate.json)
is a separate sibling experiment,
changing only linear_engine. It captures a LUT-load payload and row locally,
then writes the table one edge later. Request/load FSMs, ready/valid, bus error
and drain logic stay unchanged. The hypothesis is that table values are not
consumed until after subsequent parameter/weight loads, allowing unchanged
external cycles while removing AXI-to-table write fanout. This remains an
unverified hypothesis until regression passes.

`simulation/v2/run_typed200_lut_capture.sh` explicitly uses frozen independent
reference_encoder_system, reference_encoder_layer AND reference_linear_engine;
the reference must not accidentally share the changed arithmetic module. It
retains golden vectors and the parent negative deadline/error/drain scenarios.
It also asserts that no pending table capture overlaps valid drain data and
compares all 256 table bytes with the independent parent during valid drain.
Neither RTL candidate has physical timing or hardware qualification evidence at
this functional milestone. Their exact sources are now fixed by the external
functional evidence record described below.

The LUT write/capture proof passed in `typed200-lut-capture-formal-v2`: the
mechanically extracted write rules are scalarized at an arbitrary stable byte
address, universally covering all 256 table bytes. After initialization, each
byte agrees except while its row has the declared one-edge pending write. Reset
invalidates initialization evidence; arbitrary data, rows and stalls are allowed.
The direct whole-array v1 miter hit a WASM exception during SAT import, with no
functional counterexample; it remains preserved. The successful proof does not
prove the engine waits long enough before reading the table; full integration
is required for that scheduling claim.

Both sibling physical runners are prepared with the explicit OOC-clock hook and
require their own full integration and formal PASS before launch. No timing
benefit is credited before their mapped and placed reports exist.
Candidate README files were corrected after test staging to describe each new
sibling rather than the inherited parent. They are not compiled. Build admission
requires exact hashes for every staged RTL file and candidate manifest; only
README-only documentation drift is allowed and is explicitly recorded with old
and current hashes. Original staged README/source manifests remain preserved.

The [immutable functional evidence](2026-10-15-typed200-timing-functional-evidence.json)
now fixes both exact candidate inventories, creators, proof generators, regression
runners and receipts/logs. Both actual WSL staged source trees were rehashed
against their original pre-build manifests: no RTL or candidate-manifest drift.
The recorded README-only updates are noncompiled documentation. Candidate JSON
initial sealed:false metadata remains preserved; this external evidence record
fixes those exact source files. Physical builders/review helpers and this live
work report are outside the functional seal.
The LUT-capture full regression completed successfully in
`build/v2/typed200-lut-capture-integration-v1/`: 5,400 golden words / 14 paired
completions, unchanged driven AXI/output cycles and every-cycle raw counts.
All 256 table bytes match the independent frozen reference during valid drain;
no pending capture overlaps valid drain. Late/error responses, deadline/quarantine,
stale sessions and malformed shapes also pass. This confirms unchanged external
cycles for the tested scope despite the one-edge internal table-write delay;
physical benefit and target execution remain unmeasured.

## What the typed timing guarantee requires

The [ordered target qualification plan](2026-10-15-typed200-target-qualification-plan.md)
specifies the concrete deployment, ownership, numerical, phase-bound and fault
experiments, their acceptance criteria and missing evidence. It is prepared local
work; it does not perform or authorize target deployment.

The existing conditional contract is a structurally valid local terminal record
by D uninterrupted PL cycles after validated admission. Deadline and Fault are
legitimate outcomes with empty useful payload; they are not successful inference.
These timing experiments must preserve the independent deadline and same-edge
traffic/error veto. Observational counters must never authorize publication.

| Claim | Required evidence / present boundary |
|---|---|
| Structurally typed output | Accepted alone carries a label in the frozen 18-label set; failure payload/reserved fields are canonical; endpoint/transport proofs and tests exist |
| Correct request/model identity | Fresh session/request/contract checks exist; immutable model deployment and exclusion of other masters still require enforced deployment ownership |
| Local terminal by D | Conditional PL-cycle contract and scoped proofs exist; clock/reset continuity and physical implementation must be bound to the actual deployment artifact |
| Successful frozen-classifier computation by D | Exact target R5 head behavior, bounded encoder/drain/DDR/head/MMIO service and sufficient budget remain required |
| Correct real-world intent | Separate statistical model-quality question; a well-typed on-time label does not establish semantic accuracy or OOS rejection |
| Delivery outside PL by wall time | Additional bounded supervisor/transport and clock/reset fault policy remain required |

Successful typed inference additionally needs a justified bound for native
completion plus final B/R drain, hidden transfer to TCM, frozen head execution,
proposal MMIO and publication. External delivery requires its own bounded
supervisor/transport and a clock/reset fault policy. An observed maximum is not
a WCET proof. Stronger FPGA timing margin supports the physical assumptions; it
does not supply missing DDR or ARM service bounds.

The [reviewed R5 ELF v8 service](../../firmware/typed200_r5/README.md) remains
the deterministic-service candidate: code, stacks
and head work fit in TCM. Use A53 cores for tokenization, ingress and application
integration; exclude their Linux/DDR activity from the admitted ownership window
or establish a supported interference bound. R5 MPU permissions and a software
attestation alone do not enforce other-master exclusion. Target deployment still
requires reviewed RPU clock/split-TCM/ECC startup, fresh-session loader, enforced
buffer/model/MMIO ownership, target numerical goldens and PMU/PL timing evidence.
The current board remains on its stock overlay; no target execution is claimed.

Read-only inspection confirms that
[the active hidden-copy helper](../../firmware/typed200_v2/typed200.c) copies
`tokens * 384` volatile bytes, including rows not selected by `first/count`.
The prior R5 disassembly audit shows byte-load/store implementation. A later
versioned aligned-word or selected-row copy could reduce instruction/transfer
work for the fixed aligned immutable result buffer; do not equate byte loads
with a proven count of DDR transactions. It must preserve native complete/success/
quiet/environment guards, owned shape/row indices, barriers, exact frozen head
decisions and deadline/late-proposal behavior. First measure the reviewed R5
baseline under an approved target profile. No firmware was changed in this review,
and no ARM speedup or WCET improvement is claimed.

Continue the authorized local experiments through verification and synthesis/
placement without requesting another proceed at each intermediate milestone.
Keep hardware programming outside this scope.

## Current ranking and decision criteria

| Priority / objective | Evidence and likely benefit | Effort / risk | Required next experiment |
|---|---|---|---|
| 1. Correct synthesis clocks; establish typed200 physical margin | Controlled same-RTL OOC setup estimate improves 1.242ns; integrated full synthesis improves -0.612 to +0.624ns and removes 1,026 LUTs. Placement improves -0.066 to +0.371ns, with hold -0.087ns and changed FF mapping. No measured hardware speedup. | Low semantic risk; substantial native build time. No RTL/numerical/ABI change. | Control placement/audit complete; route held below +0.500ns. Evaluate separate physical-only Explore from this stronger control, then route only if the unchanged admission rule passes. |
| 2. Balanced full-width typed validation: preserve without promotion | Same-cycle sequential equivalence and full model regression pass. Probe improves, but final placement is +0.358/-0.106ns versus control +0.371/-0.087ns; wiring/skew erase the logic gain. | Low semantic risk, but no measured full-design gain; extra LUT/FF cost. | Completed synthesis/placement/audit rejects promotion. Extra decision KEEP refinement also gives no additional probe gain. A future bank-local equality invariant needs endpoint proof and a new independent physical comparison. |
| 3. Local LUT-load capture; reduce response distribution fanout | Prior routed limit is 90.8% interconnect. Universal-byte proof and independent full regression preserve every external cycle/count/output, including reset/error/deadline cases. Physical gain remains unknown. | Medium effort; table initialization/reset/scheduling risk addressed in scoped proof and valid-drain checks. | Prioritize physical work if the corrected validation design again limits on response distribution; inspect net fanout/resources/slack. Adopt only if measured benefit justifies added registers. |
| 4. Exact observational counter pipeline | Prior near-critical telemetry path; 32-bit induction and full every-cycle comparison establish exact counts with no encoder/control-cycle change. New worst path is elsewhere after clock-flow correction. | Low/medium effort; off-by-one risk explicitly tested/proved. Counter output never authorizes publication. | Preserve functional result; prioritize physical comparison if counter paths again approach the limit. Reject a whole-design speed claim if a different path limits frequency. |
| Conditional next step toward 300MHz: cached/registered burst sizing | Corrected synthesis moves the internal limit to address update through burst sizing: 16 levels/six CARRY8 cells. This is synthesis evidence, not a routed diagnosis. | Medium effort/protocol risk; address, remaining length, 4KiB boundaries and 256-beat limits must remain aligned. | Only prioritize if placement confirms it. Prove cached burst equals the current address/length function, then compare exact AXI traces, faults, drain and counts before physical work. |
| Required for useful typed success: R5/ownership/service bounds | Reviewed TCM-resident ELF exists; target numerical execution, enforced ownership and DDR/ARM/MMIO bounds do not. These measurements matter more to useful-success assurance than another headline clock target. | High deployment effort; startup/ECC/clock/ownership risks require a reviewed loader and explicit target authorization. | Under an approved target profile: startup/MPU/FPU/clock readback, exact goldens, PL/PMU traces, interference controls and justified service bounds. Observed maxima alone do not certify WCET. |

For the encoder, retain the exact frozen numerical contract and request boundary.
For 300MHz, optimize the actual placed/routed limiting path and certify the new
clock/artifact combination; a 200MHz synthesis estimate is insufficient. Generative
prefill/decode remains a separate execution/model/KV-cache project. No generated
token rate, prefill speedup or cross-workload speedup follows from these experiments.
