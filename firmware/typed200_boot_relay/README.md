# DDR relay candidate for the frozen typed MVP

Local-only, unexecuted on ARM. This ELF is not a boot image or a replacement
FSBL/PMU. It addresses the frozen v5 A53 ELF's overlap with live FSBL OCM by
running from DDR **after final FSBL exit**, then copying the exact frozen A53
LOAD bytes/NOLOAD stack into OCM and transferring to its entry point.

The entry/stack must be outside all live FSBL and loader scratch regions:

| Region | Candidate address |
|---|---|
| Relay entry/code/constants | `0x10000000` |
| Private stack reservation | `0x100c0000–0x100c4000` |
| Provisioned input, exactly448 B | `0x100f0000` |
| Relay status word | `0x100f1000` |
| Declared DDR reservation | `[0x10000000,0x10100000)` |
| Destination frozen A53 entry | `0xfffc0000` |
| Destination frozen A53 input | `0xfffee000` |

This reservation is **proposed, not target-approved**. Actual FSBL ELF/maps,
scratch/authentication/partition staging and PMU permissions remain unreviewed.
No ordinary FSBL-loaded application partition may overwrite its running OCM.
The dedicated boot recipe must arrange input after any overlapping zeroing;
input/status are outside this relay's ELF LOAD segments.

Entry requires same-core final A53_0 EL3/AArch64 handoff, cleaned caches and
MMU/I/D caches disabled, permit initially low, no Linux/ATF/application peer,
all A53 peers and both R5 cores held reset, cold POR, drained typed endpoint,
completed PL configuration, idle CSU DMA and PCAP reset. The relay checks the
listed execution/register/input conditions, but cannot infer FSBL's complete
cache-clean/loader/PMU policy from them. PMU must never resume the replaced FSBL.

Assembly initializes private DDR stack/BSS and exception vectors before C.
The C path clears/readbacks permit, validates all destination ranges and
overlaps before writing OCM, copies/zeros the frozen A53 segments, installs
the snapshotted input and verifies all bytes. It uses DSB, I-cache invalidation
and ISB before branching. It does not alter clock/reset/security controls.
Malformed request shapes/IDs are left to the frozen typed service's Invalid
handling; malformed boot identity/session/reserved fields reject handoff.

Status1 means checks started; status2 means copy verified/transfer issued,
not R5 ownership or a completed inference. Bit31|reason records a C/exception
failure. Wrong execution-mode/cache entry prerequisites park before C; do not
expect a typed request record for startup failure. Permit MMIO must respond.

The current ELF is `build/v2/typed200-boot-relay-v1/relay.elf`; its payload comes
from `build/v2/typed200-mvp-host-v5/a53.elf` with an enforced exact hash.
Completed tests/builds must not be rerun into the same directory. See the
dated relay report and latest qualification-profile-v2 for remaining gates.
No board action, boot image, new PL bitstream or firmware installation occurred.
