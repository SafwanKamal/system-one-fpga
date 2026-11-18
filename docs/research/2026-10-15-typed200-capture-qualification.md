# Typed200 offline capture qualification

Implemented an executable first step of the
[target qualification plan](2026-10-15-typed200-target-qualification-plan.md):
independent decoding and consistency checks for the frozen 384-byte R5 shared
mailbox and 256-byte typed200 CSR observation. This work does not modify the
reviewed R5 v8 executable, firmware, RTL, numerical contract or qualified package.
It performs no target reads/writes, programming, Vivado build or automation.

The [decoder](../../src/sysone/v2/typed200_capture.py) checks explicit byte offsets
and little-endian integers rather than relying on host C structure packing. It
preserves the complete 256-bit digest and understands the numeric least-significant
word-first CSR encoding. Accepted is restricted to labels 0..17; all other outcomes
have label zero and no actionable label in the report. Reserved score, mailbox
padding/reserved fields and exception state must be canonical.

An explicit expected-command record binds session, request, sequence, all input
token IDs, tokens/first/count, budget, frozen contract, outcome and expected label.
Input IDs must be in vocabulary for an admitted command. This is an independent
expectation supplied by the experiment, not an observation of hardware admission.
A PL-origin record requires a matching independent PL observation, configured
terminal state, identical terminal identity/payload/age and matching owned shape
for admitted commands. Accepted also requires the native successful, quiet and
permitted status. Fault/Deadline require quarantine. An admitted terminal age must
be in 1..D; Deadline must have age exactly D. A matching Accepted at D is permitted.

CPU rejection/fault is a separate origin. It cannot supply an Accepted payload or
an authoritative local deadline observation. Its reported PL age and observed
budget compliance are null. Bad records raise an error; the CLI writes no success
report for them. Output creation is exclusive, preserving an existing report.

## Completed evidence

The final reproducible run is `build/v2/typed200-qualification-host-v3/`:

| Check | Result and scope |
|---|---|
| Decoder tests | 332 pass: every SHA bit flipped individually; reversed digest words; stale identity/sequence; changed input IDs/shape/budget; reserved/padding bits; invalid labels; wrong PL ABI/state; late/early deadline; missing quarantine; mismatched mailbox/PL and CPU origin |
| Frozen service capture harness | Five scenarios pass under address/undefined-behavior sanitizers: Accepted, Deadline, Fault, CPU Invalid and CPU Fault; the original frozen service policy tests also execute |
| Independent label reference | Zero-hidden Accepted label 10 matches the frozen image's head reference, independently of the captured C result; this is a host fixture, not target numerical qualification |
| Layout | Static assertions cover all decoded mailbox/record offsets and sizes on host and Cortex-R5 compilation; ARM object inspected as little-endian ELF32 ARM |
| CLI rejection | Corrupted digest rejected with no success report |
| Preservation | All files in the previous continuation seal's three maps are rehashed before and after the run; no change |

The [host harness](../../firmware/typed200_qualification/capture_host.c) calls the
unchanged service with mock MMIO. Ages 91 and 500 are **supplied mock values**, not
measured latencies. The compile-only
[ARM ABI probe](../../firmware/typed200_qualification/abi_layout.c) is never linked
into v8. v1/v2 are preserved intermediate checker iterations; v3 is the final
source-bound evidence. The initial exploratory harness run is retained separately
in `typed200-capture-host-v1/`. All generated command logs and bytes remain available.

To reproduce in a fresh directory:

```powershell
uv run --no-sync python scripts/v2/check_typed200_qualification.py --name typed200-qualification-host-v4
```

To assess a coherent captured case offline:

```powershell
uv run --no-sync python scripts/v2/check_typed200_capture.py --expected build/v2/typed200-qualification-host-v3/accepted.expected.json --shared build/v2/typed200-qualification-host-v3/accepted.shared.bin --pl build/v2/typed200-qualification-host-v3/accepted.pl.bin --output NEW-UNIQUE-REPORT.json
```

The JSON expectation is the concrete example in the run directory; `token_ids`
is an array and `admitted` is a Boolean. The checker hashes exactly the input
bytes it assessed and does not open live device memory or change boot state.

## Capture and guarantee boundaries

Each PL observation must be coherent while RESULT_VALID is held **before ACK**,
with no concurrent reset, ACK or owner change. Each shared observation must be
coherent after DONE and before the producer submits another command. The two
observations can be captured at different times, but must name the same immutable
request and match exactly. Byte files and self-reported expectations alone do not
establish physical provenance, actual admission, ownership, clock rate or atomicity.

The reviewed service ACKs reusable PL terminals immediately. Consequently, a
register dump after seeing mailbox DONE may already have lost RESULT_VALID. A
target instrumentation successor must preserve the pre-ACK observation within the
existing exclusive owner, or provide a reviewed independent trace mechanism. It
must not add an uncoordinated concurrent MMIO reader or pause the PL deadline.
No target capture path is implemented by this host kit. Its mock registers retain
terminal values after the simulated ACK; that convenience is not assumed on hardware.

Every report keeps target_execution_verified, successful_inference_guaranteed,
wcet_certified and external_delivery_guaranteed **false**. Label agreement is a
comparison with the experiment's expected label, not a semantic accuracy claim or
a proof that hidden codes came from a particular input. Full target numerical
qualification still needs protected hidden-code fixtures and frozen expected head
results, including the scaled-vs-raw argmax cases. Observed elapsed compliance
does not establish an upper bound for all admitted executions.

Next work should prepare owner-local pre-ACK capture and phase timestamping in a
separate firmware candidate, test that its proposals/results and deadline/fault
behavior remain unchanged, and quantify its instrumentation overhead. Keep it
separate from the reviewed production candidate. Target loader/startup, enforced
other-master exclusion, real numerical execution, service bounds and external
delivery remain the unpassed gates in the target plan. Frequency work remains
independent; no new 300 MHz or hardware qualification is claimed.
