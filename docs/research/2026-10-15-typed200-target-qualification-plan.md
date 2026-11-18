# Typed output target qualification plan

Prepared local work only; no loader installation, board configuration or target
execution is performed by this plan. Preserve the qualified 200 MHz package and
the reviewed R5 v8 executable. Any later target run needs its own exact deployment
profile and recoverable package; it must not silently replace the qualified image.

The first objective is a typed, identity-bound terminal response within a declared
window. A useful Accepted label within that window is a stronger objective. The
existing gate allows Deadline and Fault with empty payload when useful processing
cannot finish. Neither claim establishes the classifier's real-world accuracy.

Use the [reviewed R5 service](../../firmware/typed200_r5/README.md),
[current physical work](2026-10-15-typed200-timing-continuation.md) and
[original typed timing plan](2026-10-15-typed-timing-contract-plan.md) together.
This is an ordered experiment plan, not a certificate that its gates have passed.

| Order | Experiment and artifact | Acceptance criterion | Present status |
|---|---|---|---|
| 1 | Deployment manifest: exact PL checkpoint/package, clock constraints/readback, model SHA, contract SHA, R5 ELF SHA, loader/version and supervisor | Every executable/configuration identity matches; actual clock/reset assumptions stated; recovery archive verified before programming | Qualified encoder package exists; new typed deployment is unqualified |
| 2 | Loader startup trace and readback: RPU clock, split mode, TCM/ECC, ELF entry, initial cache/MPU state and fresh session after ELF loading | Matches reviewed reset-entry prerequisites; no stale session or NOBITS-zeroed configuration; boot failures leave publication permit low | Not executed |
| 3 | Ownership enforcement demonstration: model/program/IDs/results, CSR and permit GPIO | Explicit mechanism excludes A53/Linux, DMA and other masters during ownership; attempted forbidden access is blocked or causes bounded fail-closed termination | R5 MPU and attestation alone are insufficient |
| 4 | Target numerical record: exact hidden-code inputs and frozen expected head decisions, including ties and all 40 known scaled-vs-raw-argmax differences | ARM binary64 implementation matches frozen decisions, first-tie behavior, row selection and canonical failure fields exactly | Host tests and ELF audit exist; target evidence missing |
| 5 | Phase timing traces: native completion, final AXI drain, hidden-to-TCM copy, head, proposal and local publication | Each phase has a stated boundary and justified bound under the admitted ownership/interference profile; timestamps tied to PL cycles and calibrated ARM clock | Simulation counts exist; target bounds missing |
| 6 | Boundary/fault campaign: zero/insufficient budget, late proposal, stale session/request, bad digest/shape, B/R error, delayed responses, CPU halt and unexpected master traffic | No stale or mismatched Accepted output; fault payload canonical; independent local deadline survives CPU failure while PL clock/reset assumptions hold | Scoped formal and simulation evidence exist; target campaign missing |
| 7 | Supervisor delivery and recovery: stalled R5, stalled consumer, reset/clock loss, terminal readout and coordinated new-session recovery | Distinct external-delivery bound and fault policy; local terminal remains independently observable; service never resumes a quarantined session by retry | Not implemented/qualified on target |

Keep A53 ingress, tokenization and Linux application work before admission. Have
R5 own admitted request processing and TCM-resident head execution. If A53 or any
other master runs concurrently, document and justify its bounded interference;
core affinity and priority alone do not bound shared DDR or interconnect service.
The PL deadline remains the authority when the R5 or its MMIO transaction stalls.

Define a successful-inference budget in PL cycles only after establishing bounds:

`D_success >= B_native + B_final_drain + B_hidden_copy + B_head + B_proposal_publication`.

Specify whether `B_native` already includes drain before adding terms, so the
composition neither double counts nor omits final bus retirement. Convert ARM
phase bounds using the deployed minimum ARM/PL clock ratio, including handoff and
synchronization overhead. Reserve explicit margin. Treat clock/reset interruption
as a separate fault model; uninterrupted-cycle proofs cannot certify wall time
through a stopped clock. If any service bound is unavailable, advertise only the
conditional terminal-by-D contract and the measured success distribution.

Each phase record should contain request/session/shape, selected rows, budget,
PL admission/native/drain/publication timestamps, ARM start/end timestamps,
clock readbacks, contention profile, outcome, exact numerical result and artifact
hashes. Preserve failures and raw traces. Report distributions and maxima as
observations; neither a long stress test nor the largest observed value proves
WCET. Tests validate assumptions and implementation; a guarantee additionally
needs an argument bounding all admitted executions under those assumptions.

Defer firmware optimization until this reviewed baseline is measured. Then compare
an independent aligned-word/selected-row copy candidate against the same exact
goldens and ownership profile. The existing byte-copy instruction count does not
by itself establish a DDR transaction count. Keep the PL deadline, current quiet/
error veto and request identity checks unchanged in every experiment.
