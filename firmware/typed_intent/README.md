# Typed intent v1: isolated ARM/PL service prototype

This is an implementation and verification milestone, not deployed firmware or
a timing-qualified hardware service. The qualified 200 MHz system is unchanged.
Read the [implementation/evidence record](../../docs/research/2026-10-15-typed-intent-implementation.md).

`generated/contract.json` freezes the existing L12 INT8 model's `intent.atis`
head, its 18 labels, numerical decision and identity/deadline semantics. Its
contract SHA256 is `8133633315487f8f322ecac49e95e7aca3801d00fccb4b4fba36026c5b2752d2`.
`generated/manifest.json` seals the profile files. Regeneration refuses to
overwrite them. A changed numerical policy requires a new version and identity.

`typed_intent.c` provides exact pooling/logits/scaled argmax and a finite-state,
single-request bridge. `typed_mailbox.c` provides finite MMIO staging/observation
calls, ARM barriers and no polling loops. The caller supplies valid, exclusively
owned buffers, a privileged Device-memory mapping, initialized floating-point
state and a trusted model-deployment certificate. ARM code cannot independently
certify an encoder status or its own deadline. The PL endpoint owns publication.
Provisioning a new bridge session is a trusted boot operation, not timeout recovery.

The mailbox implementation is
[`typed_intent_axil.sv`](../../rtl/contracts/typed_intent_v1/typed_intent_axil.sv).
It requires a dedicated **256-byte** AXI4-Lite address window; no deployed address
has been assigned. Data is 32 bits. Byte offsets below are relative to that window.
All signals are synchronous to its PL clock. Do not connect asynchronous status
or multi-bit proposals directly. A system integration must supply/review the
PS-to-PL AXI clock conversion and reset sequencing.

| Offset | Access | Meaning |
|---|---|---|
| `0x00` | W | Exactly one full-strobe command: 1 provision session, 2 START, 4 proposal COMMIT, 8 ACK |
| `0x04` | R | bit0 ready, bit1 active, bit2 terminal valid, bit3 quarantine, bit4 session configured |
| `0x08,0x0c` | W | Session low/high words; locked after nonzero provision until reset |
| `0x10,0x14` | W | Request ID low/high words |
| `0x18` | W | Request budget, positive uint32 PL cycles |
| `0x20..0x3c` | W | Request contract, least significant 32-bit word first |
| `0x40,0x44` | W | Proposal session low/high words |
| `0x48,0x4c` | W | Proposal request ID low/high words |
| `0x50..0x6c` | W | Proposal contract, least significant word first |
| `0x70` | W | Proposal outcome bits2:0; label bits31:16; bits15:3 must be zero |
| `0x74` | W | Reserved score, must be zero |
| `0x80,0x84` | R | Published session low/high words |
| `0x88,0x8c` | R | Published request ID low/high words |
| `0x90..0xac` | R | Published contract, least significant word first |
| `0xb0` | R | Published outcome bits2:0 and label bits31:16 |
| `0xb4` | R | Published reserved score, always zero |
| `0xb8` | R | Elapsed PL cycles at terminal publication |
| `0xc0` | R | Prototype ABI identifier `0x54590101` |

Undefined/unaligned addresses, combined commands, partial command strobes,
incomplete frames and commands invalid in the current state return SLVERR.
Shadow writes honor every WSTRB byte. A zero-strobe write changes nothing.
Every frame byte must have been written before START/COMMIT. START clears the
request mask and the prior proposal mask; COMMIT consumes its proposal mask.
Data staging alone never publishes a label. AW and W may arrive in either order.
Read and write response payloads remain stable under backpressure.

START with a complete frame but zero budget, zero/non-increasing ID or wrong
contract publishes `INVALID_INPUT` immediately, with no encoder launch. Increasing
IDs are consumed even for INVALID frames. Wrong-contract INVALID records contain
the gate's zero contract; they cannot be interpreted as a bound accepted result.
An OKAY write response confirms command processing, not successful inference.
Only the `admitted` output pulse is a validated encoder launch; software confirms
the active/terminal identity before advancing its own bridge state.

The authoritative record is stable until ACK. Outcome values are 1 Accepted,
2 Clarify, 3 Abstain, 4 HardwareFault, 5 DeadlineExceeded, 6 InvalidInput.
Only Accepted carries an actionable label. Every failure has canonical zero
label and score. Accepted label zero remains a valid enumeration value; consumers
must inspect the outcome, not just whether the label is nonzero. This version
does not compute confidence, calibrated abstention or out-of-scope rejection.

Core completion must be bound to the admitted session/request. Accepted additionally
requires successful core status and **live** AXI/FIFO quiescence. The guard validates
those trusted inputs; it does not derive them from the existing encoder yet.
No new request or buffer reuse is permitted before matched terminal observation,
quiescence and ACK. Timeout/fault quarantines the endpoint; ACK cannot release it.
Coordinated reset cancels an interval; recovery must drain/reset outstanding work
and install a fresh nonzero session. Reusing a session forfeits cross-reset replay
protection. Session freshness is an external boot obligation, not a random-number
generator implemented by this RTL.

At validated admission, elapsed=0. With uninterrupted clock/reset, publication
occurs no later than edge D. A matching proposal on edge D is validated before
timeout selection. ARM/DDR stalling can cause DeadlineExceeded, but cannot stop
this local countdown. Terminal availability is distinct from when ARM/Linux or
an external consumer receives the result.

Reproduce in new output directories:

```text
uv run python scripts/v2/check_typed_intent.py --name <new-host-attempt>
python scripts/v2/build_typed_intent_r5.py --name <new-r5-attempt>
python scripts/v2/prove_typed_publication.py --target gate --name <new-gate-proof>
python scripts/v2/prove_typed_publication.py --target guard --name <new-guard-proof>
python scripts/v2/prove_typed_publication.py --target axil --name <new-axil-proof>
bash simulation/v2/run_typed_intent_axil.sh <new-rtl-attempt>
```

The host numerical runner uses Ubuntu-24.04 WSL GCC with ASan/UBSan. The RTL runner
uses Verilator 5.040. Formal uses ephemeral `yowasp-yosys` (recorded version in logs),
SAT induction, unconstrained external inputs and first-edge reset. The target
compiler script defaults to the locally installed AMD 2025.2 clang/LLD paths.
It emits relocatable objects and stack reports, not a bootable ELF or TCM map.
