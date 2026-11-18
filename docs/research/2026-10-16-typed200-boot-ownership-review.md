# FSBL / PMU / CSU / debug ownership review

The ownership source review is complete. **Deployment is not ready.** The
locally tested MVP remains frozen and unexecuted on ARM. This review found a
concrete FSBL memory conflict and gaps in the surrounding boot/management
profile that must be resolved before a target boot. No board was contacted,
rebooted, programmed or reconfigured; no new PL build, boot image, bitstream,
package, security-register write, commit or push occurred.

The exact preparation procedure is
[`2026-10-16-typed200-target-qualification-procedure.md`](2026-10-16-typed200-target-qualification-procedure.md).
Its machine-readable inventory is
[`2026-10-16-typed200-target-qualification-profile.json`](2026-10-16-typed200-target-qualification-profile.json).
Evidence is in `build/v2/typed200-boot-ownership-review-v1`.

## Findings and disposition

| Priority | Finding and source evidence | Required resolution |
|---|---|---|
| Blocker | Installed FSBL `lscript.ld:26–28` reserves `[0xfffc0000,0xfffe9e00)` for its primary memory. Both actual v5 A53 LOAD segments overlap: RX `[0xfffc0000,0xfffc6e3c)` and RW stack `[0xfffe0000,0xfffe4000)`. | Do not load the v5 A53 ELF as an ordinary application partition while FSBL is resident. Build/audit a DDR relay that receives final FSBL handoff and only then copies the unchanged A53 payload into OCM, or review a nonoverlapping relink. Neither exists yet. The generated `memory-map-review.json` detects both overlaps. |
| Blocker | No exact FSBL ELF, PMU ELF, their real effective macro dumps, or PM configuration object was found in the local build/firmware inventory. Existing BIFs package Linux FPGA overlays, not this bare-metal boot chain. | Pin/build the actual dedicated qualification chain and inspect its ELF/maps/macros/config object. Installed source defaults and historical Linux board status do not identify running firmware. |
| Blocker | PMU `pm_core.c` implements wakeup, shutdown, reset and clock APIs; `pm_master.c` and `xpfw_restart.c` implement restart flows. PMU can change the state R5 merely samples. | Exact normal-operation ownership policy must forbid wake/restart, reset/clock changes, PL reload and DDR suspend/retraining while admitted. Review pending IPI work and effective error/wake/recovery policy; source presence is capability evidence, not proof an action is currently enabled. |
| Blocker | PMU `pm_csudma.c:56–69` transfers through both CSU DMA channels; `pm_ddr.c` calls it in DDR-management paths. CSU DMA is not ADMA/GDMA and is absent from the v5 R5 monitor. | Require both CSU channels drained before admission plus a reviewed PMU/CSU policy preventing new operations. An idle snapshot cannot prevent later work. Finish PL loading and PCAP reset before handoff. |
| Blocker for isolation claim | `XFsbl_ProtectionConfig` branches on `XFSBL_PROT_BYPASS`. The source-default header defines `FSBL_PROT_BYPASS_EXCLUDE`; `xfsbl_hw.h` determines the inverse bypass macro. Generated `psu_protection_lock_data()` contains comments and returns, with no lock writes. | Inspect preprocessed real FSBL and actual generated protection operations, not comments/function names. Preserve required R5/ADMA/PL access. Current profile relies on trusted/reset-held masters; no XMPU/XPPU hostile-master guarantee is established. |
| Blocker for stronger timing claim | Debug/DAP can access memory independently of stopped A53 cores. Debug enable bits do not establish disconnection or absence of traffic. Current v5 has no reviewed passive end-of-run marker. | Separate breakpoint/inspection runs from timing runs. Review a passive terminal/park notification or explicitly bound observer traffic; do not call open-loop waiting followed by a debug read proof of zero interference. |
| Required protection | With `K26_SOM`, installed PMU config forces EM, overtemperature monitoring, board shutdown routing, dynamic MIO/ioctl and CSU multiboot support. Source defaults enable PM/scheduler/FPGA loading; recovery flags default off in the tested preprocessing example. | Keep K26 board/thermal protection. Constrain normal mutation paths and account for emergency shutdown as invalidating a run. Do not turn off PMU or thermal protection as an ownership shortcut. |
| Required target proof | R5 reset bits, NCPUHALT, TCM ECC access, R5/PL MMIO permissions and posted reset writes were only host-modeled. | Target startup/fault captures under the exact boot chain are mandatory. Finite C loop counts do not bound a stalled MMIO transaction. |

The source locations above refer to pinned installed AMD 2025.2 snapshots under
`build/v2/typed200-boot-ownership-review-v1/primary/`. They are not assumed to
match an arbitrary upstream version. `primary-sources.json` records original
paths and hashes for 24 files. The previous 200 MHz qualified package, numerical
baselines, routed checkpoint and all previously sealed sources remain unchanged.

## Selected qualification trust model

Use a controlled physical lab boot with a pinned, dedicated FSBL/PMU chain.
The producer, PMU, CSU ROM/firmware and debug operator are trusted. No Linux,
ATF/U-Boot client, concurrent A53 application, remoteproc service or other PL
master participates during the admitted request. A53_0 initializes/hands off,
all A53 cores reset, R5_1 remains reset/halted, competing peripheral masters
remain held and R5_0 alone runs the frozen typed service.

This is a **trusted lab profile**, not demonstrated secure boot. File hashes
establish artifact identity, not authentication. No authentication keys or
eFuse state are available to justify a secure-boot claim. Record CSU boot mode
without changing it. Do not program eFuses, change JTAG/security locks, replace
QSPI boot firmware, alter boot defaults or destroy the known recovery path.
Cryptographically authenticated boot and hostile-master isolation are separate
future profiles with their own provisioning and threat model.

Safety actions remain available. A thermal/emergency power or reset event ends
the run and invalidates any timing claim; it must never result in reuse of a
previous session's Accepted record. A terminal-by-D guarantee cannot continue
through loss of its clock/power/reset assumptions. Independent fault-tolerant
wall-time supervision would require additional hardware/platform work.

## FSBL requirements

Require final, non-early handoff on A53_0 in AArch64 EL3, with both R5 cores
unreleased until the candidate controls them. All partition loads, DDR/model
writes, cache clean/disable, protection setup and boot watchdog disposition
must finish before the relay can replace OCM. Do not combine this with an ATF
or Linux handoff. The installed `xfsbl_handoff.c:757–759` calls data-cache
disable with its clean semantics; `xfsbl_exit.S` invalidates instruction state
and clears EL3 MMU/cache bits. Inspect the actual linked implementation and exit
path; the v5 entry checks cache/MMU bits but does not itself prove dirty A53
cache lines were cleaned.

Preferred local next implementation: a small DDR-resident relay loaded by FSBL
at a separately reserved address, containing the exact frozen A53 LOAD payload
and request input. After final FSBL exit, it verifies entry/cache state,
initial permit-low and all source/destination ranges, copies and verifies OCM,
zeros the candidate stack, installs input/config, completes data/instruction
barriers and transfers to `0xfffc0000`. It must not return to FSBL. The PMU
policy must prevent FSBL-resume/APU-restart flows after OCM replacement. A
proposed relay reservation `[0x10000000,0x10100000)` is **not yet allocated or
proved safe**: actual FSBL scratch/authentication/partition staging and all
other maps must first be checked. A raw BIF listing v5's overlapping OCM ELF
does not resolve this conflict.

## PMU policy required for normal admitted execution

Pin executable, link map, compiler/version, true board definitions, all command
line defines, generated BSP and effective preprocessed configuration. Pin the
FSBL-supplied PM configuration object and permissions. Review direct-register
APIs, secure APIs, loaded modules, scheduler callbacks, error actions, wake
sources and hooks in addition to PM API permissions. Disabling one API or
setting `ENABLE_RECOVERY_VAL=0` is insufficient proof of immutability.

| Area | Admission invariant | Evidence needed |
|---|---|---|
| APU/RPU resources | No normal release of held A53/R5_1; no R5_0 halt/power/reset | Config-object master/resource permissions, compiled handlers and no queued requests |
| Clocks and PL reset | Keep reviewed parents/dividers/enables and EMIO reset state | Real macro/API/permission audit and target register captures; R5 RO MPU alone does not constrain PMU |
| DDR and CSU DMA | No suspend/self-refresh workaround, retraining, copy or secure-image operation during admission | Build-feature audit, pending-work drain, both channel status snapshots and policy excluding new submissions |
| FPGA services | No PMU FPGA load/readback/PCAP action after initial load | Effective FPGA module/API policy and configuration receipts |
| Error management | Preserve board protection; no ordinary auto-restart silently resumes replaced FSBL or Linux | Exact error table, WDT/recovery/escalation hooks and declared emergency invalidation behavior |
| IPI | Boot/config exchanges complete; no pending mutation request at admission | PMU IPI ISR0–3 status plus reviewed queue/handler state; zero ISR is necessary evidence, not a complete scheduler proof |

The saved `pmu-k26-source-defaults.macros` used an intentionally empty
`xparameters.h` stub and `-DK26_SOM` solely to inspect header defaults. It shows
that EM is defined despite the generic `ENABLE_EM_VAL=0`. It is **not a build
configuration for a deployable PMU ELF**. The FSBL macro example likewise is
source-only. Both real effective macro artifacts are still missing in the
qualification inventory.

## CSU and debug boundary

Before handing off, require CSU DMA source/destination BUSY, outstanding count
and FIFO level fields all zero (`STS & 0x1fff == 0`); ignore sticky completion
counts in that idle predicate. Capture source at `0xffc80008`, destination at
`0xffc80808`. Require PCAP reset bit1 at `0xffca300c` and PL_DONE at
`0xffca3010 & 8`. These conditions complement, rather than replace, a policy
forbidding subsequent CSU work. The pinned FSBL `xfsbl_bs.c` contains completion
waits and PCAP reset after PL configuration. Review the actual selected path.

Record CSU status (`0xffca0000`), chain status (`0xffca0034`), JTAG security
(`0xffca0038`) and DAP configuration (`0xffca003c`) for each diagnostic boot.
Decode them against the exact device/boot/debug profile. Do not invent a
universal magic debug-disable value or write security locks. Resetting the
A53 cores is not equivalent to blocking the DAP bus master.

For diagnostic runs, debugger stops/reads/writes and modified test firmware are
allowed only as explicitly marked experiments after preparation. Their phase
times are not clean timing evidence. For a timing run, all boot/debug activity
must end before admission, with a reviewed passive indication before capture
resumes. If that indication does not exist, report observer interference as
unresolved. Repeated snapshots or a successful capture do not prove continuous
ownership. No snapshot-file checker should assert that they do.

## Local results and next work

The new offline gate checks exact artifact hashes, fixed artifact/review roles,
hash-bound evidence, same target run for target receipts, and diagnostic versus
reviewed noninterfering timing metadata. It always reports hardware authority,
target-execution proof and WCET certification as false: completeness of trusted
review receipts is not hardware proof. The live preparation inventory correctly
fails with **eight missing boot/build artifacts** and all target receipts open.

**510 tests pass**, comprising the new preparation-gate tests and the frozen
typed MVP/capture/trace/PMU/contract tests. The actual frozen C ownership table
was compiled/exported locally: 20 rules and 131 checked bits, recorded in
`runtime-register-checks.csv`. Actual A53 ELF ranges, not abstract diagrams,
establish the FSBL overlap. No old experiment was rerun or overwritten.

Next local work, in order: implement/test the separate DDR relay; build and audit
a dedicated K26 FSBL/PMU/configuration chain; close normal-operation ownership,
CSU-idle and permissions reviews; add/review passive completion observation;
then create the recoverable volatile target artifacts and execute the staged
qualification procedure. The original baseline and frozen v5 remain intact
throughout. There is no credible deployment date before these boot blockers
close; the new finding refines the earlier conditional MVP estimate.

Public primary context:
[AMD FSBL documentation](https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/18842019),
[AMD PMU firmware configuration](https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/18841724),
[AMD PM initialization/configuration object](https://docs.amd.com/r/en-US/ug1137-zynq-ultrascale-mpsoc-swdev/Power-Management-Initialization),
[AMD PMU source](https://github.com/Xilinx/embeddedsw/tree/master/lib/sw_apps/zynqmp_pmufw/src),
[AMD FSBL source](https://github.com/Xilinx/embeddedsw/tree/master/lib/sw_apps/zynqmp_fsbl/src).
The conclusions about this candidate use pinned installed files and actual
local implementation artifacts rather than assuming current documentation
describes the board's existing firmware.
