# typed200: live memory-drain and request-epoch integration

Prepared 2026-10-15 for the user's instruction to proceed with the next typed-output
milestone. A separate candidate integrates the publication endpoint with the real
encoder and memory port. It targets the existing 200 MHz operating point; it has
not undergone a new FPGA physical build or hardware qualification. The qualified
package, public RTL, recovery/numerical baselines and earlier sealed candidates
remain preserved.

## Architecture and trust boundary

[`typed200_encoder`](../../rtl/v2/candidates/typed200/platform/kr260/typed200_encoder.sv)
is a new top using all 23 sources copied directly from the qualified snapshot.
Every encoder arithmetic/pipeline source remains byte-identical to that snapshot.
The candidate's memory port adds a live `drained` observation output, with no
feedback into AXI or encoder scheduling. The old top is retained for provenance
but is not instantiated by the new service top. The new top has one typed AXI-Lite
control path and no legacy encoder start/descriptor CSR path.

| Boundary | Implemented rule | What remains an environment obligation |
|---|---|---|
| Admission | Complete identity/profile/budget/shape frame, nonzero session, increasing request ID, valid deployment, idle/drained encoder | Privileged verified firmware/deployment controller; immutable model/input/buffer ownership and valid token IDs |
| Descriptor | H=384; T=1..128; positive contiguous selected row slice within T; elaboration-time fixed program/ID/result addresses | Link the expected model/program and reserved DDR mappings; ensure no other master mutates them |
| Core epoch | Session/request captured on the validated encoder-launch pulse | Clock/reset domain and PS-to-PL AXI integration still require signoff |
| Raw completion | Preserve original encoder/request clock measurement edge and status | This point alone does not mean all DDR writes have committed |
| Memory completion | Read/write FSMs idle, no outstanding read bursts/delivery/length FIFO/write responses/pending descriptor slots, no upstream requests or live AXI activity | Compliant AXI responses and declared reset/recovery behavior |
| Native success | Raw done seen, idle + full drain observed, no sticky AXI/core fault in the owned epoch | Deployment validity must stay asserted through the admitted interval; CPU cache mappings must expose committed writes correctly |
| Typed publication | Existing fixed contract and identity guard requires successful matching epoch and live quiet for Accepted | Trusted head implementation/proposal source; structural legality is not semantic classification correctness |
| Ownership release | Legal endpoint ACK retires a completed, successful, drained epoch; fault/timeout quarantines | Coordinated recovery with fresh boot identity; no unsafe reset of returning AXI transactions |

Fixed default addresses match the frozen L12 fixture/image layout: program
1,610,613,760; ID buffer 1,645,215,744; result buffer 1,645,219,840.
There is no deployed address assignment for the publication slave. Its candidate
ABI is `0x54590201`, and the numerical contract remains
`8133633315487f8f322ecac49e95e7aca3801d00fccb4b4fba36026c5b2752d2`.
The fixed profile/certificate does not independently prove the bytes in DDR.

The new service narrows row selection to one contiguous segment slice, a subset
of the frozen contract's sorted unique row selections. It does not change pooling,
head weights/scales, argmax tie-breaking or the 18-label enumeration. Confidence
and OOS rejection remain absent. Accepted label zero is a valid label; failure
records also use zero as their empty payload encoding, so consumers must inspect
the variant tag and identity.

## Closing the completion gap

The original encoder reports `run_done` after its last accepted output W beat.
Its memory port may still be in `WRITE_RESPONSES`. The candidate's
[`typed_epoch_tracker`](../../rtl/v2/candidates/typed200/contracts/typed_epoch_tracker.sv)
latches raw completion/status and waits for a later idle/drain observation before
asserting native completion. Memory response errors remain sticky and prevent
native success even when data words happen to match the numerical reference.

The live predicate observes the memory-port-owned state directly: both FSMs,
read outstanding bursts, remaining delivery beats, length FIFO count, write
responses, registered/direct request-valid slots, upstream request/write-valid
and AR/AW/W/R/B activity. It includes same-edge activity, not just counters of
previous handshakes. The publication gate never uses telemetry counters or
snapshot-ready as proof of memory drain. The raw clock counters are separately
latched at the original completion edge, so drain/ARM/head/publication latency
does not silently redefine encoder performance.

An early Accepted proposal fails closed as HardwareFault, rather than waiting
inside a potentially blocking ARM transaction. The ARM companion must first
observe native complete/success/quiet and the matching epoch. HardwareFault or
DeadlineExceeded carries no prediction payload and cannot be ACKed back to ready.
A late B response may finish draining the old work but cannot reverse an already
published fault/timeout or allow another launch.

## Verification evidence

The [sealed validation record](2026-10-15-typed200-validation.json) is the final
authority for successful attempts and preservation checks. The integration run
uses an assertion-enabled paired co-simulation:

- Candidate encoder/memory port and qualified arithmetic/original memory port
  receive the same launch, descriptor, ready signals and R/B responses.
- Every driven AXI cycle, raw completion pulse/result and busy state is compared.
  This isolates any architectural cycle/transaction change from a changed random
  memory-stall phase introduced by different software register transactions.
- Golden L12 hidden outputs are checked word-for-word for T=1,2,3,4,5,12,64,128.
  The normal cases compare encoder/request counters sampled at the identical raw
  completion edge. Terminal publication age is reported separately.
- Additional real-encoder cases hold the final B beyond raw done, propose too
  early, inject BRESP/RRESP errors while preserving data, expire while B/ARM stall,
  deliver late B/proposals, reject stale sessions and reject malformed shapes.
  ARM label proposals are emulated in this RTL test. R5 execution/transfer/head
  integration is not claimed by a synthetic proposal payload.

**Completed:** `build/v2/typed200-integration-v2/` passes 5,400 golden words and
14 paired completions/launches: eight normal shapes and six repeated T=1 drain/
fault/session scenarios. Every driven AXI cycle and raw completion result matches
the qualified reference. The held-B timeout's age is checked at exactly 3,000,000
PL cycles; the stale-session case also rejects the proposal and expires under
that budget. Both retain canonical empty payload and quarantine. The
separate endpoint suite passes 636 writes, 80 reads and 14 valid admissions.
The existing 67 host contract/timing/candidate tests pass.

The first integration attempt is preserved as a testbench failure: it compared
the reference's counters after its FINISH state advanced, rather than sampling
at the raw completion edge used by the qualified wrapper. The corrected run
latches both at the same edge. No functional RTL fix was made for that failure.
Absolute counts from a differently phased saved random-stall test are not used
as an unmatched cycle-equivalence claim.

Separate endpoint tests extend the prior atomic protocol suite with ABI/legacy
bypass checks, deployment-blocked admission, malformed/oversized/overflowing
shape fields and immutable owned-shape readback. Formal induction passes for:

1. Epoch identity capture, done-before-drain completion, retained faults and
   conditional legal retirement, with arbitrary input values.
2. Candidate AXI AW/W capture and held B/R behavior, shape/deployment prerequisites
   for launch, canonical invalid-shape terminal behavior and held owned metadata.

The unchanged gate/guard hashes reuse their earlier scoped proofs. None of these
claims is a full-encoder formal proof, physical timing/CDC proof or R5 WCET proof.
The new formal scripts pin `yowasp-yosys==0.70.0.0.post1259`, assume first sampled
edge reset and a single synchronous PL clock, and preserve instrumented copies,
scripts, logs and receipts. All native simulations stage source copies first.

## ARM companion and timing contract

[`firmware/typed200`](../../firmware/typed200/README.md) adds an ABI-checking shape
submission/observation/copy driver while preserving the frozen head/bridge code.
It checks the active session/request/profile and admitted shape before transferring
ownership to the software bridge, and gates hidden-data copy on native status.
The copy has bounded dimensions, constructs sorted contiguous selected rows and
uses explicit ARM ordering barriers. Host tests use ASan/UBSan; the driver links
with the previous head/bridge/MMIO relocatable Cortex-R5 object without unresolved
symbols. This is not a bootable R5 ELF, linker map, target execution or cache/TCM
configuration. A defensive count check also rejects an all-ones MMIO count without
allowing unsigned addition to wrap into a valid bound.

The combined R5 relocatable object's `.text` is 3,712 bytes, `.rodata` 7,676 bytes
and `.ARM.exidx` 120 bytes. New functions report 40 bytes stack for submission,
168 for active identity observation and 16 for hidden copy. The existing nested
head/bridge stack report remains 1,688 bytes; startup/caller/interrupt stacks,
input storage and final linker alignment still require explicit placement review.

The endpoint guarantee remains **a structurally valid local terminal record by
D uninterrupted PL clock cycles after validated admission**, including a failure
if ARM or DDR cannot finish. Successful inference needs a justified bound on:

`encoder/request work + memory-response drain + R5 data transfer + head/validation + proposal commit`.

Convert external-stage bounds using the worst permitted ARM/PL clock ratio and
bus/preemption service, and select D with justified margin. A wall-time terminal
bound additionally requires a guaranteed minimum PL frequency and a clock/reset
ownership/fault model. The simulation's clock period and random memory service
are not board WCET measurements. Terminal availability is distinct from external
delivery latency or a guarantee of semantic correctness.

## Remaining gates before a deployed timing guarantee

1. **Hardware composition:** integrate the new slave/top in a separate block-design
   candidate, review reset/CDC/AXI clock conversion and constraints, then close
   setup/hold at 200 MHz. No physical build or board action is part of this record.
2. **Verified ARM environment:** produce a bare-metal R5 ELF/linker map for code,
   weights, local input and stack in configured TCM; initialize FPU/interrupts;
   establish privileged Device MMIO and coherent/noncacheable DDR ownership.
   Prevent A53/Linux or other masters from changing admitted data/program/model.
3. **Whole-service software:** bind token/segment validation and immutable ID-buffer
   preparation to the privileged submission path, run the actual frozen head on
   returned hidden codes, publish the proposal and validate/consume the terminal
   record. Provide fresh-session coordinated recovery and deployment certificates.
4. **Bounded successful execution:** establish the DDR/AXI service and transfer/head
   WCET envelope, measure target traces with injected contention/faults, and certify
   one declared shape/deadline profile. Consider the existing PL POOL/raw-LINEAR
   path plus R5 selection to reduce transfer from 49,152 bytes to 72 bytes, measuring
   added PL/DDR work rather than assuming a speedup from transfer size alone.

The original hardware-qualified system remains the sole qualified system.
Frequency optimization and generative inference remain separate workstreams;
this evidence is about encoder requests and typed publication, not generated tokens.
