# DDR relay follow-up to boot ownership review

The review and qualification procedure were completed and sealed first in
`2026-10-16-typed200-boot-ownership-validation.json`. To progress toward deployment,
the newly discovered FSBL/OCM overlap was then addressed in a **separate local
DDR relay candidate**. The earlier reports are preserved historical evidence;
this follow-up supersedes their statement that no relay implementation exists.
The frozen v5 A53/R5 images and qualified 200 MHz baseline are unchanged.

The relay implementation and local tests are complete. **It has not executed on
ARM, and the boot chain is still not deployment-ready.** Neither the earlier
source review nor this relay build establishes target FSBL/PMU policy or approves
the proposed DDR reservation. No board was contacted, booted or reconfigured;
no PL bitstream, boot image, package, QSPI/eFuse/security-lock operation, commit
or push was performed. Only a new AArch64 relay ELF was linked locally.

## Concrete implementation

`firmware/typed200_boot_relay` contains A53_0 EL3 startup, linker map, portable
copy/precondition logic and a host test of the actual C path. The relay's entry
is `0x10000000`. Its private DDR stack begins at `0x100c0000`; provisioning input
is448 bytes at `0x100f0000`, status at `0x100f1000`. The proposed1 MiB reservation
`[0x10000000,0x10100000)` must still be checked against the real FSBL ELF, all
partition/authentication/PL-load scratch ranges and PMU memory permissions.

FSBL must complete all loading/cache/protection work, keep peer A53/R5 cores
reset, and perform final same-core EL3 handoff to the DDR relay. The relay must
never be entered while FSBL still executes on another core or while a PMU flow
can later resume it. These are exact-chain review requirements, not facts this
ELF can prove on its own. The startup checks EL3/core0/MMU/cache conditions;
cache-enable bits alone cannot prove FSBL cleaned dirty lines correctly.

The C path checks responding permit-low, cold-POR history, peer/reset state,
typed ABI/inactive/drained state, both CSU DMA channels idle, PCAP reset and
PL_DONE. It snapshots and validates the matching boot/request session, nominal
Hz, versions and reserved fields. Every embedded segment's destination and
pairwise overlap is validated before any OCM copy. The code writes and verifies
the exact frozen A53 LOAD payload, zeroes its NOLOAD stack, installs the input,
finishes stores, invalidates old FSBL instruction state and branches to the
unchanged A53 entry at `0xfffc0000`. No reset/clock/security register is written.
The existing A53/R5 code subsequently performs ownership preparation/admission.

The producer now provisions the relay input at `0x100f0000`, **not directly into
live FSBL OCM**. The byte layout remains the existing448-byte `mvp_input`; the
relay installs it at `0xfffee000` only after final FSBL exit. Relay status2 is
copy-verified/transfer-issued, not R5 ownership or terminal completion. Capture
the original v5 pre-ACK/PMU/owner/parked result exactly as specified in the target
procedure; those v5 symbol addresses and numerical semantics remain unchanged.

## Local evidence

Final build/test directory: `build/v2/typed200-boot-relay-v1`.

| Check | Result |
|---|---|
| Relay ELF SHA256 | `8dd7e84b00637220bf7d3e488c6c57c73cb24d6cf5764eef536c3e44aa7f08b5` |
| Embedded frozen A53 ELF SHA256 | `63558ce920b53d32078c866fa223149f151f98cd41e3dbf54e37e9b92861ebb2` |
| ELF load map | DDR RX35548 B at`0x10000000`; RW/NOLOAD16 KiB stack at`0x100c0000`; no W+X/undefined symbols |
| Compiler static relay-main frame | 496 B, separate16 KiB stack; not measured high-water/WCET |
| Actual C execution under host UBSan | PASS exact payload/NOLOAD/input copy, verification and final jump target |
| Startup fault injection | PASS70 single-bit precondition faults, all reject before changing OCM |
| Other fault paths | PASS malformed/reserved/session input, warm boot, failed permit clear, corrupt code and corrupt copied config |
| Destination validation | PASS786432 address/size tests plus overflow/window-crossing rejection |
| Privileged instruction evidence | Actual linked disassembly contains EL3/cache guards, private DDR stack, DSB/IC IALLU/ISB sequence; no ARM execution claim |

The host uses fixed DDR/OCM mappings with mocked MMIO and jump/fault hooks.
It does not execute FSBL or privileged ARM instructions and cannot validate
silicon bus permissions, cache maintenance, reset propagation or the true
FSBL lifetime. A deliberately denied permit write cannot guarantee physical
permit-low; the relay rejects handoff and retains the failure. The clock/MMIO
assumptions remain explicit.

## Updated deployment preparation

The new `2026-10-16-typed200-target-qualification-profile-v2.json` binds this relay
alongside the frozen v5 and routed DCP. The original v1 profile stays unchanged.
The offline preparation gate still reports false. **Seven artifact roles remain
missing:** exact dedicated FSBL, PMU, their two effective macro dumps, PM config
object, typed bitstream and volatile boot recipe. All preparation/target receipt
gates remain open. No completion/authority/WCET flag was manually promoted.

Next work is concrete: build/audit that dedicated K26 FSBL/PMU/config chain,
prove its memory/scratch map admits this relay reservation and its final handoff
meets the required peer/reset/cache conditions, close ordinary PMU mutation and
CSU-idle policy, and prepare recovery plus a reviewed passive completion path.
Retain thermal/board protection. Then generate the exact recoverable volatile
target artifacts and use the already prepared qualification procedure. User's
conditional deployment intent is retained; existing evidence does not yet meet
its readiness conditions. Ethernet/SSH loss is planned once GEM/A53 are held;
independent serial/debug recovery is required before that transition.
