# Instruction-local rounding predecode experiment

User authorized this new candidate, sequencer stability/cycle proof, all-stage
probes and synthesis/placement if timing improves. Thread-bound overnight
follow-up `system-one-overnight-predecode` was configured every30minutes, with an8AM
Central October16 cutoff for new agent work and early pause after completion or
rejection. HANDOFF.md records its final paused state after the experiment is
sealed. The local computer, project and app must remain available for execution. This does
not reactivate older automations. No board programming/deployment/reboot,
package creation, commits or pushes are authorized by this local experiment.

## Candidate and proof

`typed200_predecode` changes only encoder_layer and ADD_SKIP from frozen
typed200_stage_clamp. Encoder_layer predecodes a26-bit rounding bias on the
same instruction-word0 fetch edge that stores shift bits101:96. ADD_SKIP uses
`signed26(product+bias) >>> shift` before the existing L+2 clamp. Bias is zero
for shift0 and otherwise `26'sd1 <<< (shift-6'd1)`. This preserves all64 shift
encodings,26-bit overflow, precision, addresses, control/valid/reset and cycles.
Bias storage has no reset, like instruction_reg; dispatch needs fresh word0.
No live quiet/error/epoch/deadline/identity permission is cached.

The cache mirrors **every** word0 write. Its correctness therefore does not
depend on an operation-long static-shift assumption. During a new instruction
fetch, bias and shift change together. Arbitrary untrusted bias suppliers are
outside the internal-port contract.

`build/v2/typed200-predecode-formal-v3/receipt.json` passes three actual-source
proofs: (1) extracted actual sequencer FSM/state/instruction/predecode capture
freshness, instruction stability after DISPATCH/EXECUTE, cached-bias equality
in every state after word0, and two-clock bias-history availability for actual
ADD_SKIP valid writes; (2) arithmetic equality for all26-bit products,64 shifts
and16-bit residuals; (3) conditional full-engine refinement, **886 proven
equivalence points / zero unproven**, including the clamp-stage relation.

Engine_done, fetch/control/data/reset inputs are arbitrary in the sequencer
lemma; there is no unproved other-engine completion assumption. Engine proof
copies substitute bias=f(current shift), with that premise discharged by the
sequencer/cache lemma for observable writes and their arithmetic history.
Corresponding initial datapath/clamp state, one sampled clock and two-state
semantics apply. Invalid startup datapath values are not admitted writes.
Default formal parameters are READ_LATENCY3, BUFFER_ADDRESS_WIDTH14, TILE_OUT32,
FPGA_HEADS0 and sequencer ADDRESS_WIDTH40. No analog reset/CDC/physical/WCET
claim follows.

`typed200-predecode-composition-v1/receipt.json` checks actual instance
shift/bias/start/reset/clock/shape/output bindings, exact control/address/valid
prefix identity with the actual control model, and exact state/capture/FSM
proof copies. These close the modular wiring boundary; arithmetic alone would
not prove the composed implementation.

Earlier sequencer induction attempts are preserved. v1 reached base12 with
808542 SAT variables/2368254 clauses; v2 reached base13 with894699/2631127.
Each exact own heavy solver process was identified and stopped. v3 adds
reachable intermediate invariants: unfilled FETCH_RECEIVE frame implies beat0,
frame implies prior capture, and busy/pipeline history. Final assertions and
RTL remain unchanged. No functional counterexample was observed.

## Measurement and admission

The matched probe compares against **profile_cache**, not the rejected
stage-clamp parent. Both versions have identical registered fetch/shift and
instruction/data input shells, with5ns clock before synthesis. New bias captures
on the same modeled instruction edge as shift. Shell registers model existing
launch/capture boundaries; they are not added candidate cycles. Reports cover
predecode, product, rounding and output register destinations, including residual
and control paths. The shell does not include full fetch-enable fanout, whole
sequencer placement or board clock skew. OOC estimates do not establish full-design
routed Fmax; the small observed gain especially requires full implementation.

Probe output is `build/v2/typed200-predecode-ooc-v1`. Full-model regression is
`typed200-predecode-integration-v1`, with separately renamed frozen parent
encoder_layer and ADD_SKIP, exact every-cycle raw counters/output/AXI/busy/done,
eight normal shapes and fault scenarios. One foreground pipeline waits on these
existing runs and admits a full build only after proof/composition/source checks,
completed regression and a strictly positive matched overall probe improvement,
as the user's latest instruction explicitly requests synthesis/placement if
timing improves. The earlier0.050ns experiment-cost threshold is superseded for
this requested experiment; the physical routing margin is unchanged.

The all-stage probe completed: control/predecode overall slack is+1.872/+1.887ns,
a small **+0.015ns** gain. Predecode-stage slack is+3.989ns; product+2.594ns;
rounding+1.887ns; output+2.840ns. This is insufficient to claim a robust gain
without full placement. It is0.628ns better than the rejected direct stage move
at the rounding stage, while retaining the0.968ns output-stage gain.

| Matched5ns probe | Profile-cache control | Predecode |
|---|---:|---:|
| Predecode capture slack, ns | +4.705 | +3.989 |
| Product-stage slack, ns | +2.594 | +2.594 |
| Rounding-stage slack, ns | +2.159 | +1.887 |
| Output-stage slack, ns | +1.872 | +2.840 |
| Overall slack, ns | +1.872 | +1.887 |
| LUT / FF | 2,866 /1,183 | 2,780 /1,133 |
| CARRY8 cells | 192 | 192 |

New rounding limit is bias register bit0 to clamped-skip bit0/D,3.110ns data
(1.508logic/1.602estimated wire),12levels/six CARRY8s. Bias capture itself is
0.846ns with one LUT6 level. These are mapped estimates, not routed measurements.

The original waiting pipeline used the earlier cost threshold. Before any full
build started, its exact waiting process was verified and stopped, with runner
snapshot/policy revision preserved in pipeline-v1. Pipeline-v2 reuses the same
proof/probe/regression jobs and applies the explicit positive-gain instruction.
No experiment was replayed and no timing clock or route gate was relaxed.

Full implementation retains the5ns real clock, explicit OOC clock during
optimization, one-large-job policy, source/clock review, timing/CDC/exception
checks and+0.500ns placed route gate. Only timing-only routing may follow an
approved placement. No bitstream/package/deployment is created. Final results
and preservation seal follow completion; HANDOFF.md lists active sessions.
Qualified200MHz sources/package/recovery/numerical fixtures and all earlier
sealed evidence remain frozen.

Full regression completed successfully: **5400 golden words /14 paired
completions /14 launches**, all eight normal shapes and delayedB/earlyproposal/
B/Rerror/timeout-lateresponse/stalesession/shape cases. Every sampled raw counter,
output/AXI/busy/done cycle matches. T128 retains7961537 encoder cycles /7966029
request cycles and emulated publication age7966096. Host simulation took470.283s;
these are not target R5 timings or WCET observations.

Immutable `2026-10-16-typed200-predecode-functional.json` fixes exact candidate,
creator/proof/composition/regression sources and evidence. Actual WSL staged
inputs were rehashed; **2291 prior preserved paths remain unchanged**. Do not
edit its mapped sources/evidence. Physical helpers and this work report remain
outside that functional seal; the physical builder is now separately hash-bound
by actual physical input-proof.json and must not change.

Full synthesis, exact-source/clock review, placement and native reopened-checkpoint
audit **completed successfully** in `typed200-predecode-physical-v1`, through
pipeline-v2. There was no simulation/proof/probe replay. The project used isolated
IP cache disabled, jobs1/maxThreads4 and the existingS: alias. Pipeline session23019
completed normally at the placement review; no jobs remain and routing is held.

## Completed full-design physical result

The [synthesis review](../../build/v2/typed200-predecode-physical-v1/synthesis-review.json)
verifies all30 staged /28 compiled RTL inputs, exact wrapper/runner/hook/source
identities, the5ns clock present before encoder OOC optimization, real full-design
5ns/10ns clocks and no OOC clock leakage. Full linked synthesis is **68499LUT /
53387FF /579DSP /50BRAM tiles /36URAM**, estimated setup+0.628ns /hold-0.087ns.
Encoder OOC is65733LUT/50784FF with estimated+0.862/+0.036ns. OOC lacks board
clock-skew/port-delay context and is not an Fmax result. The full synthesized
worst path is AXI deliver_left[12] to SmartConnect AWFIFO almost-full state,
4.142ns data (1.175logic/2.967estimated wire),13LUT levels. Placement changes
the limiting path; do not optimize solely from that synthesis estimate.

The [final placement review](../../build/v2/typed200-predecode-physical-v1/placement-review.json)
records **+0.449ns setup /-0.154ns hold**, independently confirmed by reopening
the exact placed DCP. This is **0.051ns short of the preserved+0.500ns setup
routing gate**. **Do not route or promote this checkpoint.** Negative placed
hold also needs routing/repair/final STA in any future admitted implementation.
No routed result, bitstream, deployment package or hardware qualification exists
for this candidate.

| Matched full-design200MHz experiments | Placed setup /hold, ns | LUT /FF |
|---|---:|---:|
| Corrected-clock unchanged-RTL control | +0.371 /-0.087 | 63331 /53055 |
| Full profile-cache parent | +0.417 /-0.072 | 63456 /52768 |
| Instruction-local predecode | **+0.449 /-0.154** | **63383 /52812** |

All have579DSP/50BRAM tiles/36URAM. Against the profile-cache parent, this run
uses73 fewer LUTs and44 more FF, improves setup by0.032ns and worsens placed
hold by0.082ns. Against the unchanged-RTL control, setup improves0.078ns,
with+52LUT/-243FF. These are single-run physical estimates; neither repeatability,
routed closure nor300MHz performance is established. The hardware-qualified
encoder remains a distinct frozen deployment.

The actual [placed worst path](../../build/v2/typed200-predecode-physical-v1/place/critical.rpt)
has moved out of ADD_SKIP: publication bank[5][17] to the encoder-system state
machine's state[3]/CE, **4.153ns data =1.633ns logic +2.520ns estimated wire**,
13levels including4CARRY8, skew-0.188ns. Bank5 contains token count and first
selected row; bit17 is first-row bit1. The inspected source shape predicate
checks positive bounded tokens, reserved bits, nonempty selection, first<tokens
and first+count<=tokens, then gates the request budget/admission. This is a
typed shape/admission path, not a new arithmetic-output bottleneck.

The native audit saved these selected stage-path minima:

| Native report scope | Slack, ns |
|---|---:|
| All paths to captured rounding-bias registers | +1.572 |
| All paths to ADD_SKIP product registers | +0.700 |
| All paths to clamped-skip registers | +0.640 |
| Paths **from clamped-skip registers** toward output | +1.373 |
| Paths from profile byte-equality registers | +1.333 |

The output query is source-restricted and must not be advertised as the minimum
over every residual/control input to that stage; the OOC all-destination probe
and full-design timing cover the broader boundary. Rounding is now bias bit3
to clamped-skip[3][0]. These reports support removal of the earlier ADD_SKIP
worst path without establishing a useful-inference deadline guarantee.

All12 check-timing categories are zero; defined-clock CDC paths are safely timed.
All39 false-path exceptions remain vendorXPM reset/synchronizer exceptions.
Deadline/epoch/publication/permit structure is retained, including GPIO output
driver;32 profile-equality registers and128 clamped-skip registers are verified
in native mapping, and captured-bias/product registers are present. No LUT
asynchronous reset or asynchronous-FIFO reset mapping is reported. Placed DRC
retains only the unrouted RTSTAT-13 condition and DSP pipeline advisories; it
does not certify a routed design.

## Decision and next evidence-driven experiment

Retain this candidate as a functionally verified and physically characterized
research result, with **routing held**. Do not weaken the margin requirement or
modify its now-sealed sources/evidence. Its supported contribution is an
instruction-word-local derived-state cache, with actual capture/freshness/history
and wiring proofs, exact finite-width numerical/cycle parity and inspected
physical stage paths. The measured whole-design setup improvement is small.

The strongest next zero-cycle experiment targets the **actual selected-row
shape predicate** rather than another ADD_SKIP change. Tokens are bounded to128,
so a separate candidate may be able to replace the wide range arithmetic with
explicit high-bit rejection and a narrow, carry-preserving sum. It must first
prove exact equivalence over **all raw token/first/count/reserved-bit encodings**,
including invalid shapes; no legal-input-only assumption may hide a changed
admission/fail-closed decision. Then prove full endpoint behavior under arbitrary
byte strobes, split writes, masks, commands and resets, and rerun independent
full numerical/cycle and physical checks. Benefit is unmeasured; effort is
small-to-medium and risk is changing rejection/overflow semantics.

A stored shape-valid cache is another option, but every affected partial write
must atomically update it from the correctly merged words, and its write-path
timing must be measured. Neither option may cache live ownership/quiet/error/
deadline permission. Both are recommendations, **not implemented in this
completed overnight experiment**. Broader extra-stage300MHz work remains a
different, explicitly cycle-changing project with new budgets.

Final immutable `2026-10-16-typed200-predecode-validation.json` binds the source,
functional record, proofs/composition, independent regression and actual staged
rehash, all-stage probe, full physical checkpoints/reviews/audit, policy/failed
attempt history and this report after preservation checks. HANDOFF files remain
editable. The overnight automation pauses after completion rather than starting
an unrequested new experiment.

The previously sealed conditional MVP-readiness estimate is unchanged. Local
optimization does not establish target ARM execution, enforced master exclusion,
bounded DDR/MMIO, useful-success WCET, external delivery or measured power.
