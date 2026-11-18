# Linux-managed R5 startup audit, 2026-10-17

The separate TCM-only smoke candidate passes local execution and driver tests.
Live startup remains blocked by exact-kernel mode-query, allocation cleanup and
ambiguous-start containment issues. No R5 firmware, overlay or kernel was installed
or started. JTAG stayed stopped; target commands only read Linux files and status.

Evidence root: `build/v2/typed200-amp-linux-r5-v1`. Prior seal:
`2026-10-17-kr260-debug-coexistence-validation.json`, SHA256
`2e009354749afca8b6f4de58012bae984990a84a517dcb99b26204ceb248e8d1`.
Its two maps cover 10,112 preserved and 80 candidate files. The previous qualified
RTL, packages, diagnostics and numerical evidence remain untouched.

## Exact installed interface

Safe SSH inventory found Ubuntu kernel `6.8.0-1036-xilinx` and signed vendor
`zynqmp_r5_remoteproc.ko.zst`, srcversion `7D40C73BB90D8F2C1D12ABD`.
This uses the older `xlnx,zynqmp-r5-remoteproc` binding, rather than the newer
upstream R5FSS interface. The actual compressed module was copied read-only,
checked against its remote SHA256, decompressed and disassembled locally.
Its linked start/stop functions confirm status query, conditional blocking power
down, NOACK wake request and blocking stop. This is not a reproducible full-kernel
binary comparison.

Selected exact source files were reconstructed from Ubuntu `linux-xilinx
6.8.0-1036.37`, using the base archive and contextual distribution diff from the
[Ubuntu primary archive](https://archive.ubuntu.com/ubuntu/pool/universe/l/linux-xilinx/).
Archive SHA256 values match the downloaded DSC:

| File | SHA256 |
| --- | --- |
| linux-xilinx_6.8.0.orig.tar.gz | 26512115972bdf017a4ac826cc7d3e9b0ba397d4f85cd330e4e4ff54c78061c8 |
| linux-xilinx_6.8.0-1036.37.diff.gz | c4153e2477adcabcef15fdd2b0f8ae4107f778297d614ab83fe180e4b8fecf7f |
| DSC | d93671d02af94ce313b98780432a41e9d0f927af3e7b02176cf8b2835f38a9e2 |

The DSC PGP signature was not verified. `kernel-source-v3/receipt.json` seals
16 selected reconstructed files; no full kernel or target module was built.
The advertised stock ATF commit resolves to
`ec5dccc32c6334f271881f7f6c58f98fd49d0753`. Its pinned
[SMC dispatch source](https://github.com/Xilinx/arm-trusted-firmware/blob/ec5dccc32c6334f271881f7f6c58f98fd49d0753/plat/xilinx/zynqmp/pm_service/pm_svc_main.c)
and IOCTL implementation confirm status in the low return word and RPU mode in
the next word. This audits the advertised source ABI, without proving equivalence
to every byte of running ATF/PMU/ROM firmware.

## Findings that gate live use

1. The vendor start callback selects low TCM or high OCM vectors; it does not
   honor an arbitrary ELF entry address. The preserved DDR diagnostic at
   `0x63f00000` therefore cannot be started directly through this interface.
2. `auto_boot=false` does not make driver binding passive: probe already queries
   and sets RPU mode and TCM configuration. Recovery must precede overlay binding.
3. Exact-source `zynqmp_pm_get_rpu_mode` assigns output slot 0, which is status,
   rather than slot 1, which is mode. Successful split mode can appear as
   lockstep. The original error was reproduced locally using the actual functions.
4. Generic firmware debugfs PM_IOCTL supplies a four-word response buffer to an
   SMC helper that writes seven words. A host harness compiled the actual helper
   and demonstrated writes into modeled adjacent storage. Do not issue this
   debugfs IOCTL on this kernel. It was not called in this audit and is not
   asserted to have caused earlier board outages. Dedicated PM status helpers
   use a different path and must be audited individually.
5. Wake uses NOACK. Sysfs `running` is insufficient proof of actual execution.
   On startup failure, generic remoteproc cleanup may release resources without
   separate confirmation that R5 is stopped. The subdevice-error branch calls
   stop but ignores its result. Ordinary shutdown retains resources after a stop
   error, which is better, but does not close startup-error containment.
6. `xlnx_rpu_pm_request_sram` can request one TCM node then return on the next
   request failure without releasing the first. `parse_tcm_banks` has not yet
   registered a carveout for that failed bank. Preparation failure bypasses
   generic resource cleanup. A successful lease followed by mem-entry allocation
   failure also lacks local rollback. These are source-path findings; no target
   fault was induced.
7. `sram_mem_alloc` makes both plain and devm mappings. Failure of the second
   retains the first until later cleanup; successful release removes the plain
   mapping but devm mappings remain until device unbind. Host tests reproduce
   those function-level lifetimes, not an unrecoverable leak for every full-kernel
   path: later generic cleanup can release registered entries. Request/release
   errors must retain ownership information and be handled explicitly.
8. ZynqMP prepare skips RPU-node request, assuming default power. Earlier saved
   evidence found powered-down R5s, so this assumption is not sufficient here.
   Exact PMU transitions, reset state, TCM power/ECC and rollback remain open.

`kernel-fixes-v1/fixes.patch` stages two narrow source corrections: mode slot
0 to 1, and debugfs response capacity to `PAYLOAD_ARG_CNT` (7). Actual-function
regressions cover six mode/error cases and the seven-word output guard. These
fixes are local, uninstalled and insufficient alone to admit live startup.

## Separate firmware and overlay candidate

`firmware/typed200_amp_linux_r5/smoke.S` is an ARM Cortex-R5 reset-vector image
using only one private 64 KiB TCM bank. It masks IRQ/FIQ, selects SVC, installs
low vectors, checks reset MPU/cache state, CPU identity and CPSR, then publishes
a trace with its final aligned PASS-word store and waits. Exceptions and failed
checks publish failure. It contains no DDR, PL, PS MMIO, IPI, timer, inference,
mailbox or admitted-transaction access. Stack pointer initialization performs
no stack memory access in the tested code.

Latest image: `smoke-build-v2/sysone-r5-smoke.elf`, SHA256
`dd9b3eb2d18006a15acd1d2806f02bc2a89781eb5a89fbd000087656a26b9bc5`.
Entry is 0; PT_LOAD regions are 512 bytes at 0, 72 bytes at 0x800, and 256 bytes
at 0x1000. All segment addresses and lengths are eight-byte aligned. This avoids
partial trailing doubleword loads but does not prove hardware ECC initialization.
The resource table contains only a 128-byte RSC_TRACE, no virtio/RPMsg resources.
Original unpadded build v1 remains preserved.

The overlay declares one TCMA bank and R5 cluster/core with PM IDs 15 and 7.
Local `dtc` plus `fdtoverlay` on the captured live DT preserves every property
of all 227 existing nodes and adds three nodes plus two symbols. No DDR reserved
memory, OCM, PL or A53/GEM nodes are changed. This is a structural dry run, not
a live Linux overlay/probe test or proof of physical ownership.

## Validation and target state

| Evidence directory | Result and scope |
| --- | --- |
| smoke-emulation-v2 | 164 actual-ELF Cortex-R5 Unicorn scenarios, only 64 KiB modeled TCM; faults, exceptions, reset checks and interrupted publication |
| driver-host-check-v1 | 226 actual callback mode/start/stop fault and ordering scenarios; separate actual-SMC buffer demonstration |
| cleanup-host-check-v1 | 7 actual-function lease/mapping scenarios, including three successful request/allocate/release cycles |
| kernel-fixes-v1 | 6 corrected mode/error cases, original split-mode misread reproduced, seven-word guard checked |
| overlay-check-v1 | local compile/dry apply and all 227 existing nodes preserved |

Normal emulated trace is `R5: PASS`, SCTLR `00000000`, CPSR `000000d3`, MIDR
`411fc153`. Software models cannot establish physical reset, timing, ECC,
firmware ownership or target negative-access properties.

Post-audit SSH health v1 reached the same boot at 5h10, taint 0, CPUs 0-3 online,
remoteproc empty and dfx-mgr active. Its final `xmutil listapps` exited 1 because
it required root; the failed attempt is preserved. The corrected v2 uses sudo
only for the read-only ownership query. No debugger processes were present and
the S: mapping remained correct. No powercycle request is pending.

Corrected `post-audit-health-v2` passed both queries: same boot, taint 0, CPUs
0-3, no remoteproc instances or loaded R5 module, dfx-mgr active and stock
`k26-starter-kits` slot active. This confirms health at the observation time,
without proving causality for the earlier hangs or future stability.

Retained earlier failures include the timed-out partial source download, initial
empty source extraction receipt, and Unicode export failure; successful v2/v3
attempts supersede them without overwriting them. Local dependencies only:
Unicorn 2.1.4, zstandard 0.25.0 and WSL device-tree-compiler 1.7.0. Target packages
and boot settings were unchanged.

## Deployment work remaining

Implement and qualify an additive Linux interface that obtains correct mode,
tracks each acquired lease and mapping, and prevents cleanup/reuse after
ambiguous wake or unsuccessful stop. Test prepare/parse/load/start/trace/stop
and every failure/unbind branch using exact kernel sources; build against the
installed ABI and account for module signing and kernel taint. Do not substitute
generic debugfs IOCTL, raw PS MMIO or JTAG for this interface.

Before live bind, arm and verify independent board-local recovery with UART
capture, establish exclusive ownership and a proven powered-down/reset/TCM entry
sequence, and qualify TCM mapping/ECC and blocking stop semantics. Only then run
the TCM smoke, require fresh trace evidence and verify recovery. Existing DDR
probe/package must not be rebuilt. Full typed inference additionally needs R5
source tags, trusted firmware composition, firewalls/filter/hidden outputs and
exact numerical, cycle, physical, fault/drain and target qualification. Existing
deployment authorization persists once these gates pass; readiness has not passed.
