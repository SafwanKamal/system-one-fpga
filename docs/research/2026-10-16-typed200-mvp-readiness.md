# Typed-output MVP readiness and planning estimate

The encoder already has a hardware-qualified 200 MHz baseline. The typed
publication/R5 system is a separate, unqualified successor. Its local formal,
numerical, host mock, firmware link/audit and physical experiments are substantial
preparation; none substitutes for a deployable typed image and target evidence.

**Planning estimate: approximately 5–10 focused engineering days for a supervised
board MVP**, conditional on obtaining routed typed timing closure and resolving
R5 startup and a practical enforceable ownership profile without platform
redesign. This is a low-confidence engineering estimate, not measured remaining
work, a completion promise or an unattended schedule. Native tool runtimes are
only part of that effort. Current local work does not program the board.

The MVP acceptance boundary is a recoverable exact-artifact deployment that
produces identity-bound typed terminal records, demonstrates useful Accepted
decisions against the frozen numerics, and fails closed under the stated
deadline/fault tests. Local terminal-by-D is conditional on clock/reset and
ownership assumptions. Useful successful requests are measured at this stage;
an observed maximum is not successful-inference WCET. A53/network delivery is
outside the PL-local deadline unless independently bounded.

| Gate | Existing evidence | Remaining MVP acceptance evidence |
|---|---|---|
| Deployable typed PL image | Separate RTL proofs/regressions and full-design placement experiments; qualified encoder recovery archive | Routed setup/hold and completed checks for the exact typed image, recoverable package and identity manifest. Retain the qualified baseline. |
| R5 startup and execution environment | Audited TCM-resident diagnostic ELF and checked read-only full-rate PMU provider | Exact loader/order/session configuration, actual clocks, split TCM/ECC and addresses validated on target; startup failures leave permit low. |
| Ownership during admitted requests | Explicit assumptions, R5 MPU configuration and software attestations | A verified mechanism excludes unintended A53/DMA/debug/other-master writes and interference as required by the declared profile. Trusted software attestation alone does not establish this. |
| Exact typed/numerical behavior | Frozen head and independent software/RTL comparisons | ARM target goldens including ties and the40 scaled-versus-raw argmax differences, canonical outcomes, held identity and correct session/request recovery. |
| Deadline and fault behavior | Scoped gate proofs and bus/deadline/stale-request simulations | Target captures for admission/native/drain/head/proposal/publication; CPU/bus/consumer fault and late/stale response campaign under declared clock/reset assumptions. |
| Demonstrable client path | Intended A53 ingress/R5 head/PL deadline split | Repeated end-to-end request/terminal demonstration, raw capture review, explicit success/fallback rates, recovery procedure and documented limits. |

The [concrete deployment inventory](2026-10-16-typed200-deployment-profile-draft.json)
contains13 unresolved target gates and exact existing artifact hashes. These
six MVP rows group that detailed inventory; they do not discharge any gate.
Hardware deployment and qualification are distinct later actions from the
currently authorized local source/proof/build work.

The stronger research milestone is a justified useful-success deadline:
nonoverlapping native/drain/copy/head/proposal/publication bounds, minimum deployed
ARM/PL clock ratio, bounded shared memory/MMIO service and explicit margin.
There is no credible calendar estimate for that stronger guarantee until an
enforceable interference/service model is selected and validated. If PL clocks
can stop, wall-time guarantees also need independent supervision and recovery.
Clock frequency improvements alone do not solve those requirements.

For MVP scheduling, first obtain a physically admissible typed implementation
and resolve startup/ownership. Use the first real target captures to revise this
estimate. Continue 300 MHz architecture work using separate candidates and
versioned evidence; no300MHz result or unrelated published token rate is a gate
for demonstrating the typed-output MVP.
