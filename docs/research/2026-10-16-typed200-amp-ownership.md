# AMP ownership candidate: access restored, protection and transport components

Status: **NOT READY FOR DEPLOYMENT**. This is a separate local candidate, not a
replacement for the qualified 200 MHz implementation. No target halt, reset,
programming, FPGA load, boot-image install, QSPI write, commit or push occurred.
The user power-cycled the board. The earlier automation remains paused.

## Board and boot evidence

SSH at 192.168.0.239 recovered after that power cycle. The saved host key matched
before authentication. The authenticated, read-only [inventory](../../build/v2/typed200-amp-ownership-v1/board-inventory.json)
identifies a KR260 revB running Ubuntu kernel 6.8.0-1036-xilinx. Its working
interface is eth1/GEM0 SGMII; GEM1 supplies the shared MDIO path. The live
[device tree](../../build/v2/typed200-amp-ownership-v1/board-runtime.dts) reserves
0x60000000–0x6fffffff for System One and 0x7ff00000–0x7fffffff for PMU use.
There are two 2 GiB DDR banks, including the bank above 32-bit address space.
The attempted direct /sys/firmware/fdt capture was denied; the successful DTB
was generated read-only from the live device-tree filesystem instead.

Previous-boot logs contain CPU2 soft lockups in the BPF/JIT instruction-cache
flush path and RCU stalls. These are consistent with an unresponsive Linux
system; the outage's root cause is not established. UART1 control 0x114 has
receive enabled: the earlier disabled-RX interpretation was incorrect.

The read-only [QSPI backup receipt](../../build/v2/typed200-amp-ownership-v1/stock-boot-readonly-v1/receipt.json)
records identical image-A and image-B contents, SHA256
`6b8bd7b57656e2ed80b51687bb25e2cc0eacb623f628480ae3ecaa9a2abb8216`.
The [header/partition audit](../../build/v2/typed200-amp-ownership-v1/stock-boot-readonly-v1/analysis/receipt.json)
identifies FSBL/PMU 2022.1, ATF v2.6/ec5dccc32 and U-Boot 2022.01.
Matching backups do not identify the active slot or prove candidate recovery.
JTAG enumeration and register reads succeeded; no recovery sequence was executed.

## Protection policy and its limits

The [boot-only plan v4](../../build/v2/typed200-amp-ownership-v1/protection-plan-v4/plan.json)
contains 774 protection-register writes. **Never execute this plan against
running Linux.** Its installer requires trusted execution and quiescence of
every affected master. Disabling a firewall while other masters run is not an
acceptable transition. Caller-provided gate bits are preconditions, not proof.

The plan respects fixed DDR XMPU granularity and preserves both live no-map
reservations. Allocation is:

| Range | Role | Proposed permissions |
|---|---|---|
| 60000000–620fffff | Immutable model/program | Secure R5 and HP0 encoder read |
| 62100000–621fffff | Token IDs | R5 read/write; HP0 encoder read |
| 62200000–622fffff | Hidden output | HP0 encoder write; R5 read |
| 62300000–623fffff | Untrusted ingress | APU read/write; R5 read |
| 62400000–624fffff | Published result | R5 read/write; APU read |
| Rest of 60000000–6fffffff | Reserved, unused | Denied |
| 7ff00000–7fffffff | Existing PMU reservation | Denied by this inference policy |

The hidden-output address must change from the parent's 62101000 to 62200000
in a new RTL/R5 composition before use. No parent RTL was modified here. All
64 HP0 local IDs are assumed to belong to the trusted encoder topology;
that assumption still requires actual integration and source-tag evidence.

FPD/OCM and XPPU permissions protect memory-protection registers, clocks,
resets, GPIO, pinmux/IOU configuration, PMU/CSU, watchdogs, QSPI and debug
windows. I2C controllers also require protection because they reach the PMICs.
IPI request/response windows distinguish APU↔PMU from R5↔PMU. Permissions on
IPI buffers do not establish that the software consuming them is correct.

Register semantics were checked against the locally preserved [AMD UG1085
v2.5](../../build/v2/typed200-amp-ownership-v1/ug1085-v2.5.pdf), chapter 16,
and the pinned SDK headers. XMPU overlapping-region priority is described as
higher-numbered first on page 393, despite the contradictory figure label on
page 407. The plan's protected DDR regions do not overlap the generic private
regions; FPD overlap semantics remain a target qualification item. XPPU
TRUSTZONE=1 permits both secure and nonsecure accesses, not strict nonsecure
matching. The independent oracle models that distinction explicitly.

The [host installer/policy receipt](../../build/v2/typed200-amp-ownership-v1/host-v5/receipt.json)
passes 921,600 PM API cases, 860,160 DDR boundary/access cases and 775
observable write/readback fault cases. A skipped write already holding its
intended value is not observably faulty. [Additional register-image tests](../../build/v2/typed200-amp-ownership-v1/firewall-v2/receipt.json)
pass 253,952 FPD, 20,480 OCM and 1,642,496 XPPU cases, with permission/parity
mutation checks. These are software-model results, not target denial tests.

## Secure firmware ownership

PMU filtering alone is insufficient: the stock ATF source contains direct
secure RPU/TCM IOCTL writes. The separate [ATF wrappers](../../scripts/v2/stage_typed200_amp_atf.py)
serialize the entire PM and raw-IPI service handlers with policy closure.
After closure, PM operations are restricted to canonical read-only queries;
raw IPI calls cannot impersonate an R5 local agent. Source snapshots are pinned
to AMD's 2025.2 [ATF commit](https://github.com/Xilinx/arm-trusted-firmware/tree/894ecd0737173617c91748dfbcfa1deca7971439).
This is not a rebuild-equivalent replacement for the stock 2022 ATF binary.

[ATF tests/build](../../build/v2/typed200-amp-ownership-v1/atf-staged-v3/receipt.json)
pass 65,536 FID and 9,216 raw-IPI cases and produce a native AArch64 BL31 ELF.
SHA256: `a06219743f8d36eace5fc24f19250d4c2510152e4eeaff8c62fae8370970fcca`.
Audited load segments fit fffea000–ffffefff and have no writable/executable
load segment. Linked PM service code calls the guard before its body; raw-IPI
guard calls survive optimization. This is not a full concurrent-system proof.
The trusted ATF activation entry is retained but not yet joined to boot/R5.

The PMU guard intercepts all module IPI dispatch, ordinary event dispatch and
scheduled callbacks after closure. Read-only requests remain possible. Reviewed
EM safety events remain possible and may invalidate an uninterrupted-clock run.
Thermal shutdown is not suppressed to sustain a timing claim.

The new [PMU lease transport](../../firmware/typed200_amp_ownership/pmu_lease.c)
accepts a close request only from controller-observed R5_0 on IPI0. It records
the pending session in private PMU RAM. The actual commit executes later in the
main loop, with interrupts masked and previous callbacks returned. A status
request returns a session-bound acknowledgement only after that commit.
Duplicate requests are idempotent; a different session cannot replace the
pending or owned session. This ABI identifies protocol version, not image
hashes; the trusted startup still must verify exact firmware/policy identities.

[Transport tests](../../build/v2/typed200-amp-ownership-v1/pmu-staged-v6/receipt.json)
reject 1,023 unauthorized source values and 160 malformed-field mutations,
check deferred activation, session binding, quarantine and interrupt-mask
preservation. The all-module guard regression also passes. The [native PMU
v3 image](../../build/v2/typed200-amp-ownership-v1/pmu-image-v3/receipt.json)
builds 63 units with prints disabled and the old BSP used read-only. SHA256:
`6f6288ded7e79677d52d697d780dcdd0ba8e8b5c866b6ebae98c1932cbb6cc08`.
Text/data/bss total 112,624 bytes; audited load segments fit the linker regions.

PMU image v2 built but is rejected for promotion: its inherited idle sleep
could miss a deferred request arriving between poll and sleep. Image v3 removes
that sleep and polls the closure path. The PMU idle-power cost is unmeasured.
No ACK grants FPGA admission by itself. ATF closure, direct-access protection,
source provenance, clock/reset readback and R5 initialization must also match.

## Linux request/result isolation

The new [mailbox wrapper](../../firmware/typed200_amp_ownership/mailbox.c) uses
a fixed 160-word input ABI and a separate 32-word published result. It takes
one finite snapshot, validates shape/IDs/session/reserved fields, and copies
the request into private R5 state. It never writes ingress and never reads it
after submission. Linux has no pointer to the service's command/result state.
Result serialization explicitly writes every field and reserved word, then
publishes a final marker. Hardware mappings/cache attributes still need testing.

A concurrent writer can produce a mixed snapshot; the captured validated word
vector is the request. Sequence rechecks do not prove transaction-wide atomicity.
There is one request per fresh cold-start session, including invalid requests.
After publication there is no new admission, cancellation, reset, buffer reuse
or Linux-controlled ACK. An incomplete AXI transaction retains its ownership.

[Mailbox tests](../../build/v2/typed200-amp-ownership-v1/mailbox-v1/receipt.json)
pass 5,120 request-bit mutations and nine matched traces using the actual frozen
service, driver and numerical head. Every MMIO register, software-poll transition,
input ID and canonical result is compared with the frozen service under matched
responses. The source also compiles for Cortex-R5. Static per-function stack
reports show 680 bytes for poll and 164 bytes for publication; they are not a
whole-program worst-case stack proof. No FPGA cycle-equivalence or WCET claim
is made from these software traces.

The six typed outcomes and numerical contract are unchanged. CPU rejection or
fault remains origin=0; only an observed authoritative PL record is origin=1.
Only Accepted can carry a nonzero label; failure payloads remain empty. The
intended guarantee remains a canonical local PL terminal by D after admission,
conditional on protected state and uninterrupted guard clock/reset. It does
not guarantee Accepted, Linux queue/snapshot latency, or SSH delivery by D.

## Linux-compatible PS generation

The [PS generator](../../scripts/v2/prepare_typed200_amp_ps.py) explicitly composes
the pinned local K26 SOM 1.1 and KR260 carrier 1.0 presets from the official
[AMD Board Store](https://github.com/Xilinx/XilinxBoardStore). Applying only the
SOM preset had left Ethernet disabled in the standalone parent configuration.
The new [v4 generation](../../build/v2/typed200-amp-ownership-v1/ps-profile-v4/receipt.json)
enables GEM0 SGMII, GEM1 RGMII/MDIO, UART1/I2C1 and the carrier's peripheral
configuration. No implementation run, bitstream, XSA or deployable boot package
was created. PS output generation is not synthesis/placement qualification.

Generated nominal clocks are PL0 199.998001 MHz, PL1 99.999001 MHz and R5
533.328003 MHz. RPLL and IOPLL settings differ from the stock running system.
In particular, runtime DP audio operations can affect RPLL/R5, and network
clocks share IOPLL with the PL. All such mutations must be closed before
admission; freezing only the PL divider is insufficient. Existing clock/timing
certificates cannot simply be transplanted to this profile.

The [native audit](../../build/v2/typed200-amp-ownership-v1/native-audit-v2/receipt.json)
records 18 derived MIO property differences: peripheral selection overrides
generic SOM pin direction/drive/slew defaults on RGMII/ULPI pins. Clock and
network selections match the requested configuration. Full property equality
is explicitly false; electrical compatibility/boot functionality is unqualified.
These differences need schematic/vendor-flow review rather than suppression.

## Remaining gates, in execution order

1. Compose trusted ATF closure, PMU session ACK and R5 startup. Establish a
   trusted pre-lease state; do not treat a compromised mutable boot phase or
   caller gate bits as attestation. Serialize with every existing handler and
   refuse admission on partial closure, reset, stale ACK or identity mismatch.
2. Define the pre-Linux protection image and the final lease transition.
   Prove affected-master quiescence at firewall enable/lock. Resolve PMIC,
   pinmux, storage, network, watchdog and idle/DVFS requirements before closing.
3. Compose the requester filter before AXI USER loss, for CSR and permit,
   with no bypass. Bind actual R5 USER/PROT and HP0 origin/security attributes.
   Change the hidden address only in a new RTL/R5 candidate. Run exact-output,
   counter, cycle and error/drain regressions under matched responses.
4. Build the actual R5 startup image with protected code/private state/input,
   finite ingress, read-only Linux result and correct cache/device mappings.
   Bind immutable model/contract hashes and fresh session. Qualify clock/reset
   ownership and new frequency profile, including PLL parents and debug policy.
5. Perform new physical integration at unchanged 5 ns/10 ns constraints:
   setup/hold, DRC, CDC and exception review. Do not reuse the parent's tight
   routed slack as AMP timing evidence, or relax constraints to promote it.
6. Prepare permit-low volatile target qualification with stock QSPI unchanged,
   exact recovery commands and immutable receipts. Target denial/clock/reset/
   session/deadline tests follow only after predeployment gates pass. Hardware
   qualification cannot be asserted before those measurements occur.

All failed attempts remain under build/v2/typed200-amp-ownership-v1. The new
validation anchor records preservation of all 8,312 prior sealed files and
hashes the immutable source/evidence snapshots. Mutable handoffs are excluded.
