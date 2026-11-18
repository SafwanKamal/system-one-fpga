# typed200 ARM companion: ABI 0x54590201

This additive driver uses the unchanged, frozen
[typed intent head/bridge/mailbox](../typed_intent/README.md). It is not a BSP,
bootable R5 image, deployed application or WCET certificate. The associated RTL
candidate is [`rtl/v2/candidates/typed200`](../../rtl/v2/candidates/typed200).
Read the [integration report](../../docs/research/2026-10-15-typed200-integration.md).

Use a single privileged owner and exclusive model/program/ID/result buffers.
Trusted deployment verifies the image and firmware/bitstream/profile certificate,
validates the token IDs, constructs the intended selected segment rows, and
provisions a fresh boot session. The PL validates shape and profile identity;
it does not authenticate a model merely because its hash is in a request.
The runtime must keep deployment validity asserted and prevent other masters
from modifying the admitted input/model/output buffers during the interval.

`ti200_start` checks ABI, readiness, session, profile, budget and shape, then stages
the shape and delegates the atomic START to the existing transport. Return 1 means
the command was staged. It is not evidence of admission. `ti200_admission_observe`
checks the active session/request/profile and latched shape once; call the bridge's
admission transition only for that matching active epoch. An immediately terminal
INVALID must be handled as a failed submission, not an encoder launch.

`ti200_copy_hidden` requires native complete, successful status, live drain and
valid deployment with no quarantine. It bounds every shape field before copying,
uses at most 49,152 byte loads, and constructs sorted contiguous selected rows.
The head then runs on that exclusively owned local `ti_input`. The driver never
polls/retries, resets, ACKs, proposes or releases a buffer implicitly. Observe the
authoritative terminal record, pass it through the bridge validator, and ACK only
an eligible non-quarantined record. Fault/timeout requires coordinated recovery.

MMIO must use a privileged Device mapping; the DDR result view must be coherent
with the PL writes and free of stale cached aliases. A proposed first BSP uses
explicitly noncacheable shared DDR with code/stack/head/local input in TCM, but
there is no linker map or target mapping implementation yet. ARM DMB barriers
order status observation, DDR copy and later publication. A final AXI B response
does not invalidate CPU caches. Linux/A53 cache ownership, tokenization, logging,
RPMsg and startup belong outside the initial admitted interval.

Every call has finite loops and fixed memory usage. A load/store may still stall
on DDR or AXI, and the R5 can be interrupted unless its environment bounds that.
The PL deadline remains independent; it guarantees a terminal failure outcome
under such stalls only within the stated clock/reset assumptions. Successful
inference and delivery deadlines require separate service/WCET evidence.

The candidate retains the v1 session/request/proposal/result layout and adds:

| Offset | Meaning |
|---|---|
| `0x1c` W | Shape staging: tokens bits15:0; selected first row bits31:16; all bytes required |
| `0x78` W | Selected row count bits15:0; upper bits zero; all bytes required |
| `0xc0` R | ABI `0x54590201`; the v1 driver alone cannot stage a complete request |
| `0xc4` R | Admitted tokens/first row, held independently of later shadow writes |
| `0xc8` R | Admitted count |
| `0xcc` R | bit0 quarantine, bit1 live quiet, bit2 core success, bit3 core complete, bit4 deployment/error admission permission |
| `0xd0` R | Encoder clocks sampled at the original raw completion edge |
| `0xd4` R | Request clocks sampled at that same edge, excluding added drain/head/publication latency |

H is fixed at 384. T must be 1..128, selected count positive and the contiguous
slice entirely inside T. Wrong shapes publish canonical INVALID without launch.
Program, ID-buffer and result-buffer addresses are elaboration constants in this
candidate, not mutable legacy descriptor CSRs. No deployed MMIO base is assigned.
