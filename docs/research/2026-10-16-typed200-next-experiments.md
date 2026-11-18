# Next experiments after full profile-cache placement

Prepared 2026-10-16. The [completed experiment](2026-10-15-typed200-profile-cache.md)
has exact functional evidence and +0.417/-0.072 ns placed setup/hold at 200 MHz.
Its +0.500 ns routing gate did not pass. Preserve its sources and evidence,
the qualified 200 MHz deployment and every earlier sealed candidate. No target
programming, automation or clock relaxation follows from this plan.

## Priority: a typed terminal response with an explicit timing contract

The useful external type is a discriminated outcome: Accepted carries the
identity-bound label and score; Deadline or Fault carries canonical empty label
fields. The existing ABI already implements that distinction. A terminal-by-D
claim and a successful-Accepted-by-D claim need separate evidence. A label being
well typed and arithmetic-exact does not prove it is semantically correct.

| Rank | Work and evidence | Benefit | Effort / risk | Required experiment and completion criterion |
|---|---|---|---|---|
| 1 | Make the intended deployment profile concrete using existing R5 timed provider, loader config and capture checker. Host/ELF evidence exists; target evidence does not. | Turns an informal guarantee into an auditable list of exact identities, boundaries and assumptions. | Medium / low for offline preparation; high assurance burden for target enforcement. | Specify PL/R5 clocks and reset policy, split TCM/ECC, ELF/model/contract hashes, admitted buffers/rows, session freshness, MMIO and DMA ownership, timeout response, recovery, and local versus external delivery. Every field needs an evidence source or an explicit unresolved status. No invented clock or ownership certification. |
| 2 | Resolve enforcement of exclusive access before a typed target deployment. | Prevents other masters from modifying input/model/results or issuing stale CSR/permit writes after admission. | High / high. | Inventory A53, R5, DMA, debug and interconnect paths; select a verifiable hardware protection or quiescence mechanism. Show forbidden accesses are blocked or lead to bounded fail-closed behavior. R5 MPU, Linux affinity and software attestation alone do not establish global exclusion. |
| 3 | Execute the existing owner-local capture and timed diagnostic service in a separate, recoverable target profile after the physical/startup prerequisites are satisfied. | Supplies missing real numerical and phase timing evidence without changing the qualified encoder. | Medium / medium; target execution prerequisite remains open. | Validate exact ARM decisions including all 40 scaled/raw argmax differences and ties. Capture admission, native completion, final bus drain, TCM copy, head, proposal and terminal publication. Verify each capture with the existing independent decoder. Preserve raw failures and identities. Observed maxima remain observations. |
| 4 | Establish bounds and test the deadline authority under CPU and memory faults. | Supports a useful-success bound where service is bounded; supports a conditional terminal bound otherwise. | High / high. | Compose nonoverlapping phase bounds using the minimum deployed ARM/PL frequency ratio and a bounded interference model. Test halted R5, stalled bus/consumer, stale session, late proposal, B/R errors and clock/reset interruption. Specify an independent supervisor policy for wall time when PL clocks stop. |
| 5 | Define A53 ingestion and delivery outside the admitted processing window. | Uses the KR260 ARM cores while keeping Linux variability out of the local PL deadline argument. | Medium / medium. | A53 tokenizes/stages before admission; R5 owns admitted work and the TCM head; PL owns the terminal deadline. Specify whether A53 delivery is best effort or separately bounded. Concurrent A53 execution needs a justified interference bound. R5 traces alone do not establish A53/network delivery latency. |

Use the [target qualification plan](2026-10-15-typed200-target-qualification-plan.md)
and the frozen timed-provider validation record for exact existing artifacts.
Do not alter a sealed firmware candidate simply to add a document field.

## Physical work, ranked by actual placement evidence

Continuation result: the first same-stage Boolean clamp candidate is now
implemented and formally proved (966 full-engine points). Its matched full-engine
probe regresses setup from +1.872 to +1.698 ns despite -128 LUT/-40 CARRY8 cells;
full physical build is held. See the [dated experiment](2026-10-16-typed200-clamp.md).
The next P1 refinement should move the first clamp into the existing rounding
register stage, retaining finite-width rounding and external cycles, then inspect
both rounding and residual-output cones. Do not repeat this rejected decomposition
or promote it based on reduced carry count.

The [deployment inventory](2026-10-16-typed200-deployment-profile-draft.json) now
binds the actual baseline/archive and unqualified typed/R5 artifacts. All 13
target gates remain unresolved; this is concrete preparation for priorities1–4,
not evidence of a qualified combined deployment or a successful-inference bound.

| Rank | Separate experiment | Evidence / expected benefit | Effort / risk | Admission experiment |
|---|---|---|---|---|
| P1 | Preserve-stage ADD_SKIP clamp decomposition on top of the profile cache. | Direct: current worst +0.417 ns, 6 CARRY8s, 4.219 ns data. A reduction/mux clamp may remove serial carry comparisons; physical benefit is unmeasured. | Medium / medium numerical and placement risk. | Prove exact two-clamp arithmetic for all 26-bit rounded values and INT16 residuals, including -32768 and both saturation boundaries. Prove full-engine state/output cycle correspondence with arbitrary data/control/reset. Compare mapped logic and delay against the exact parent; reject if no credible improvement. Then full independent-reference 5400-word/14-case cycle/count regression, followed by exact-source full synthesis/placement/audit. Route only if setup >=+0.500 ns. |
| P2 | Localize instruction and admission control if P1 exposes these paths. | Direct: instruction-to-ADD_SKIP +0.503 ns and other request-bank validation +0.503/+0.504 ns. Only 0.003 ns above the route threshold, so margin remains fragile. | Medium / medium; cached live permissions are unsafe. | Read exact endpoints/fanout and control lifetime. Duplicate only proven stable instruction fields at existing stage boundaries. Keep live quiet/error/epoch/ownership/deadline checks current. Require arbitrary-input equivalence and the same full regression; no timing exceptions for logic paths. |
| P3 | Evaluate existing elastic AXI request isolation if placed bus paths become limiting. | Direct near-critical SmartConnect +0.506 ns; synthesized delivery-counter path is not the placed worst. Potential control fanout reduction, with latency/area cost. | Medium / medium; may change request cycles. | Compare registered-request configuration against the parent with random backpressure, lengths, outstanding traffic, errors and drain. If cycles change, version and measure the contract rather than claiming zero delta. Re-establish deadline/publication budgets and full physical evidence. |
| P4 | Pipeline arithmetic and control for 300 MHz after typed 200 MHz margin is established. | Architectural hypothesis supported by serial arithmetic and control paths. Current placed period is 5 ns; it is not a 3.333 ns implementation. | High / high across data, valid, address, busy/done and budget bookkeeping. | Fresh 300 MHz OOC/full clocks before optimization, explicitly versioned cycle counts, exact numerical proof, full regression and routed setup/hold with margin. Measure end-to-end request time, not just clock rate. A 50% clock increase need not give 50% request throughput. |

P1 must not widen or narrow requantization intermediates without a proof of the
original finite-width semantics. In particular, preserve the 26-bit rounding
overflow and shift behavior and the existing latency. A Boolean rewrite of
clamps can be proved across the entire 26-bit domain without assuming all values
are reachable from the product stage. Full-engine correspondence is stronger
than testing a few clamp boundary vectors.

For the next full regression, the current runner's encoder reference must be
extended to use a separately renamed frozen parent encoder-layer and ADD_SKIP
module. Both sides currently share the ADD_SKIP implementation because this
completed experiment only changed the AXIL/guard endpoint. That sharing was
appropriate for its scope and would be insufficient for an arithmetic change.

## Claims and measurements to keep separate

Record encoder requests, prefill and generated tokens as different workloads.
The published KV260 clock rates do not establish a matched speedup. The best
local placed result is still below our routing gate, and no candidate here is
qualified at 250 or 300 MHz. Power, quality, reproducibility and successful
deadline completion remain separate axes. Do not update the original frozen
research matrix with these unqualified candidates as if they replaced its
hardware-qualified System One row; use this dated supplement instead.

The defensible current result is precise: a full-width identity-check cache can
remove an admission bottleneck with no external cycle or numerical change,
backed by endpoint induction, full differential simulation and inspected mapped
state. Its measured whole-design placement improvement is only 0.046 ns in this
single run. The stronger research contribution remains the composition of typed,
identity-bound fail-closed publication and an explicit conditional timing model;
useful-success WCET, master exclusion and target evidence are unfinished.
