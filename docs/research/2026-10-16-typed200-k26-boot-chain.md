# Dedicated K26 FSBL/PMU chain and relay reservation

2026-10-16. **Local boot artifacts built and audited; deployment NOT READY.**
No board contact, reboot, programming, persistent-media write, commit or push
occurred. The original hardware-qualified encoder and all previous sealed
sources, packages, numerical evidence, routed checkpoints and MVP files are
preserved. The overnight automation remains paused.

## Concrete results

| Item | Evidence / result |
|---|---|
| Hardware description | Read-only `write_hw_platform -fixed` from the existing typed physical project. Exported PS init exactly matches frozen SHA256 `79e70111dd3aa4e47d6ebcf0ab20d87eb59cf7992ba938cc7fe1aa5d1fdc7bc5`; HWH exactly matches generated typed HWH. `hardware-metadata-audit.json`. |
| Dedicated A53 FSBL | Actual ELF/map built from matching AMD 2025.2 BSP plus separate final hook. Text 78,917 B; data 3,592 B; BSS 84,360 B. BootROM flattened load 106,336 B; NOLOAD work areas are additional. Actual effective macro dump, compiler commands and final disassembly retained. |
| Dedicated PMU firmware | Actual MicroBlaze ELF/map with K26 board configuration and one-way seal. Text 73,680 B; data 20,908 B; BSS 19,660 B. BootROM flattened image 129,760 B includes reserved table placement/gaps. Effective macros verified, rather than inferred from defaults. |
| PM configuration | Exact 1,744-byte `.sys_cfg_data` extracted from the linked FSBL to `pm-config-object.bin`. The vendor base object grants broad cross-master management permissions; the central seal blocks ordinary PMU dispatch after handoff. This is not a hostile-master hardware firewall. |
| Typed bitstream | Exported only from frozen `typed200-row-range-csa-route-v1/routed.dcp`, SHA256 `2d24f5f04d94c17299a32a04190c32118526221f1ab76888baf814fb733cfc88`. No synth/opt/place/route or constraint change. Rechecked +0.048 ns setup, +0.011 ns hold, 5/10 ns clocks and zero DRC errors; prior CDC/exception receipts remain applicable to the identical DCP. Local export is not board qualification. |
| Boot image | Local `image-layout-v2/BOOT.bin`, 41,996,956 B. Actual headers/checksums and all file-backed FSBL/PMU/relay bytes independently verified; model/input exactly match source bytes. Five partitions; only relay has a nonzero application entry. Unsigned, unencrypted trusted-lab layout; no secure-boot claim. |
| Relay reservation | Exact image allocation and both firmware maps exclude live relay code, stack, provisioning input and status. PL scratch, model, IDs and hidden buffer ranges are disjoint. Reservation is a reviewed allocation, not XMPU enforcement or measured target permissions. |

Build/evidence root: `build/v2/typed200-k26-boot-chain-v1`.
New sources: `firmware/typed200_k26_boot`.
Final identities are in the new qualification profile v3 and validation seal;
the profile is authoritative for hashes, including the fresh session image.
Image v1 and initial binary snapshots are superseded, retained attempts.

## Ownership and sequencing

The generated application copies are patched; the installed AMD sources and
frozen MVP/relay are unchanged. `staged-patches.json` records initial exact-anchor
patches. Final source hashes and attempt snapshots cover subsequent changes.

The final FSBL hook runs inside `XFsbl_HandoffExit`, after the FSBL-completion
flag and UART drain; the normal final path has already stopped its watchdog and
disabled/cleaned D-cache. The usual early hook was insufficient: PMU's common
completion callback still performs final error/policy configuration afterward.
The new hook checks A53_0, EL3, AArch64 exit flag, exact DDR entry `10000000`,
cold-POR reason, typed ABI, unconfigured/drained guard and permit zero. It powers
the RPU island, holds A53 peers and both R5 CPUs reset, enables RPU AMBA, then
waits for PMU common completion and checks CSU DMA/PCAP idle state.

It sends a dedicated module `0x53` seal request containing the fresh input
session. Source must be APU mask 1 on PMU IPI0; header, version, magic, nonzero
session and every reserved word are checked. There is no reopen/query-to-unlock
operation. The interrupt handler only stages a successful request. PMU commits
at the main-loop boundary **after all active scheduler callbacks return**, with
interrupts masked, and only then writes the matching success response. This
prevents an interrupted normal callback from resuming after a seal ACK.
ISR/main-loop state is explicitly volatile and aligned 32-bit under LTO.

After seal, central dispatch rejects all ordinary IPI calls, including PM,
runtime FPGA/CSU and error-policy changes, and skips scheduled callbacks.
Normal wake/sleep/DAP/legacy power/isolation module events no longer dispatch.
Only EM error events 4/5 remain eligible, preserving physical safety handling.
Actual K26 macros keep EM, 90 C overtemperature shutdown, board shutdown MIO,
PM and scheduler initialization. Runtime FPGA load/readback, DDR FSBL restart
copy, unused-RPU powerdown, recovery/restart escalation, WDT and DDR self-refresh
workaround features are compiled out. EM/overtemperature paths have no ordinary
scheduler dependency in the installed sources. Fatal errors/thermal shutdown
invalidate the experiment; they do not guarantee inference during a power fault.

The FSBL response check is bounded and identity-specific; a hardware IPI ACK
alone is insufficient because it precedes the deferred response. Failure parks
with permit zero and a diagnostic DDR status. There is no CSU work after the
seal; final exit assembly disables MMU/I/D state and branches to the DDR relay.
The relay then copies **unchanged frozen A53** bytes over the former FSBL OCM,
never returning to FSBL. A53 installs the unchanged R5, resets all A53 cores,
and R5 independently checks the frozen 20-rule/131-bit ownership table before
permit. No other normal client is allowed during this trusted boot sequence.

Limits: host mocks do not execute cache/interrupt hardware. BootROM, debugger,
loader, PMU safety handlers and absence of other pre-seal clients remain TCB.
The vendor power-up helper has an unbounded pre-admission startup poll; no
bounded-startup claim is made. Vendor FSBL has RWX OCM LOAD permissions; this
candidate adds no W^X or adversarial isolation claim. Target protection/power/
clock behavior must still be observed. Neither polling ownership bits nor
freezing PMU APIs proves freedom from all hardware interference.

## Exact memory allocation

Half-open physical address ranges, hex:

| Allocation | Start | End | Basis |
|---|---:|---:|---|
| PL staging scratch | `00100000` | `0086fbbc` | Actual PL partition payload 7,797,692 B; FSBL dummy-PL address remap |
| DDR relay RX | `10000000` | `10008adc` | Actual frozen ELF and Bootgen payload, 35,548 B |
| DDR relay stack | `100c0000` | `100c4000` | Actual ELF NOLOAD 16 KiB; not a Bootgen application partition |
| Provisioned input | `100f0000` | `100f01c0` | Exact 448-byte frozen boot/request ABI |
| Relay status | `100f1000` | `100f1004` | Diagnostic status only |
| Full reserved relay window | `10000000` | `10100000` | Contains above relay allocations with gaps; no other candidate load |
| Model | `60000000` | `62058800` | Exact frozen 33,916,928-byte image |
| IDs | `62100000` | `62101000` | Frozen runtime allocation |
| Hidden | `62101000` | `6210d000` | Frozen runtime allocation |

Actual FSBL LOADs are entirely OCM; PMU LOADs entirely PMU RAM. The FSBL static
authentication/read/hash work areas are included in ELF memory extents; its
bitstream NOLOAD buffer is `ffff0040..fffffc40`. USB boot scratch at `04000000`
is compiled out, as is PMU's normal DDR restart copy. This trusted local image
has no authentication/encryption certificates or additional partitions. The
audit makes no claim that arbitrary BIFs, malformed lengths, authenticated
images or future partitions preserve these bounds: regenerate/review the image
and full artifact bindings for every change.

## Verification and retained failures

- 479 policy bit/matrix cases plus transition assertions pass with UBSan trap.
- Actual `pmu_seal.c` host integration passes deferred ACK, sticky seal,
  all 83 event IDs for EM/normal modules and ordinary IPI rejection.
- Actual `fsbl_final.c` passes success plus 23 wrong entry/EL/core/reset/ABI/
  permit/power/MMIO/completion/CSU/protocol/timeout cases; ASM and SDK/MMIO mocked.
- 474 existing typed capture/trace/PMU/MVP/qualification tests pass.
- Actual final ELF maps, macro preprocessing and linked PM configuration pass.
  No undefined symbols in either final ELF. Final disassembly retains actual
  interrupt masking, seal loads/stores, dispatcher branches, cache maintenance
  and the final transfer; source tests are not substituted for binary review.
- Bootgen headers are independently decoded using the installed FSBL layout;
  checksums, attributes, lengths, addresses, payloads and sole relay entry pass.
  Bitstream export checks pass without changing the routed checkpoint.

Retained failures: Vitis platform RPC generation (`ws`, `ws-v2`, `ws-v3`),
Lopper handling of C: paths with spaces, missing AArch64 compiler, initial host
UBSan runtime-link attempt, and first image-auditor word/byte offset mistake.
Successful flow uses actual cwd `S:` plus candidate-local, published-checksum-
verified Arm GNU 13.3.rel1. The auditor offset was corrected, not the boot image.
Initial binaries/images are retained; final image v2 binds the volatile-state fix.

## Deployment blockers and next work

1. **Independent recovery:** user currently has SSH only and will arrange JTAG
   after returning home. No matching connected USB UART/debug device was found
   in the read-only host inventory. Do not infer recovery from that future plan.
   Sole-R5 startup intentionally resets A53/GEM and loses SSH/Ethernet.
2. **Compatible cold-POR launch:** KR260 carrier presets QSPI32. An ordinary SD
   `BOOT.bin` does not replace the primary FSBL/PMU. AMD's development override
   writes `BOOT_MODE_USER` then invokes system reset. The frozen ownership/relay
   rejects that reset history. A reviewed cold-POR debug interception route,
   with proof no stock/concurrent application survives, must be established
   using the actual connected hardware. No working route is claimed here.
   Do not clear reset history, relax the frozen predicate, chain from running
   Linux/U-Boot, or write QSPI to make the current local image appear ready.
3. **Physical admission evidence:** capture actual board identity, cold-POR
   history, voltage/temperature/fan status, power/permissions, clocks and debug
   state. Then execute staged diagnostic boots with independent recovery.
4. **Timing observer and campaign:** define/verify passive completion capture
   before clean timing runs. Debug reads/breakpoints after a diagnostic run can
   help establish function but cannot certify uninterrupted timing. Measure
   ARM phase bounds, memory service and clock calibration; compose the deadline
   scope explicitly. Keep the frozen 200 MHz baseline separate throughout.

The local image starts with fresh-session IDs `[101,102]`, pool row 0/count 1,
budget 1, intended to exercise **Deadline if admitted**, not successful
classification. Later accepted/invalid/fault/reset/deadline campaigns each need
new session-bound images and expected receipts. No successful-inference rate,
model-quality change, target latency, external-delivery guarantee or WCET result
has been measured in this task.

The distinctive claim remains: a typed local terminal outcome under explicitly
stated ownership/clock/reset assumptions, with numerical results only in
Accepted; failed admission/invalid/fault/deadline outcomes do not become labels.
ARM performs trusted startup and exact numerical/service work; the PL guard
bounds its local terminal record in PL cycles. This does not guarantee Accepted
for every request, bound startup, survive a stopped clock/reset, or guarantee
host delivery. The next research evidence is a correctly launched, passively
observed target campaign, not another unmeasured frequency claim.

## Primary sources inspected

- Installed AMD 2025.2 `Vitis/data/embeddedsw/lib/sw_apps/zynqmp_fsbl/src`:
  `xfsbl_handoff.c`, `xfsbl_exit.S`, `xfsbl_partition_load.c`, `xfsbl_config.h`,
  `xfsbl_misc.c`, `xfsbl_bs.*`, `xfsbl_image_header.h`; copied candidate sources,
  effective macros and disassembly are retained locally.
- Installed AMD 2025.2 `.../zynqmp_pmufw/src`: core/interrupt/IPI manager,
  scheduler, common/PM/DAP/legacy/EM/overtemperature modules and configuration.
  Actual generated BSP includes `xipipsu_g.c`, standalone A53 cache routines
  and xilpm `pm_cfg_obj.c`; final linked bytes are audited.
- [AMD K26 boot sources, DS987](https://docs.amd.com/r/en-US/ds987-k26-som/Boot-Sources-and-Storage-Devices).
- [AMD Kria development boot-mode scripts](https://xilinx.github.io/kria-apps-docs/creating_applications/2022.1/build/html/docs/bootmodes.html): volatile overrides explicitly reset the system; consulted as procedure evidence, not executed.
- [AMD K26 primary/secondary boot overview](https://xilinx.github.io/kria-apps-docs/bootfw.html).
- [AMD Bootgen PMU image semantics](https://docs.amd.com/r/2024.2-English/ug1283-bootgen-user-guide/pmufw_image): actual installed 2025.2 Bootgen help/output independently confirms inline PMU firmware and partition layout.
- [Arm GNU 13.3.rel1 download](https://developer.arm.com/-/media/Files/downloads/gnu/13.3.rel1/binrel/arm-gnu-toolchain-13.3.rel1-mingw-w64-i686-aarch64-none-elf.zip), published checksum fetched from the same official release; verified SHA256 `c7b14079f405b20b47eaf5fd0121209a27481cf77db2a0cabbb586871f917049`.
