# KR260 requester-origin deployment trial

## Result and scope

The user's physical power cycle restored SSH at `192.168.0.239`. The saved
Ed25519 host key was verified before password authentication. Read-only
[readiness v4](../../build/v2/typed200-amp-deployment-v1/board-readiness-v4/receipt.json)
captured the stock and qualified application files, the 64 KiB no-map DDR
window at `0x63f00000`, clocks and relevant PS register state.

The reviewed 100 MHz diagnostic origin probe was uploaded and loaded through
the board's existing `xmutil` / `dfx-mgr` manager. The
[target observations](../../build/v2/typed200-amp-deployment-v1/probe-target-v1/apu-observations.json)
pass 64 aligned, ordered, 32-bit writes and exact address/data/sequence
readbacks, 16 on each affinity-pinned A53 core. All four 128-bit bus lanes
were exercised on each core. The write count is exactly 64; errors are zero;
the probe tick counter advances. The compiled AArch64 helper uses volatile
32-bit `ldr w` / `str w` accesses followed by `dsb sy`; these are not Python
byte-copy MMIO operations.

This deploys a **diagnostic**, without an encoder, PL DDR master, interrupt,
permit, or external PL I/O. It does not deploy or qualify the typed-output
MVP. No R5 code ran. No boot files, QSPI, fuses or security configuration were
changed. The additive diagnostic application directory remains installed,
but the active application is restored to `k26-starter-kits`.

## Measured origin metadata

All observed A53 transactions have AxPROT = 2 (nonsecure data). Tags below
are measured at the direct, full-width PS HPM0 AXI interface, before a
conversion could discard USER. IDs are observations, not identity policy.

| Core | ARUSER | AWUSER | ARID | AWID |
|---|---|---|---|---|
| A53 #0 | `0x0080` | `0x008c` | `0x000d` | `0x018d` |
| A53 #1 | `0x0081` | `0x008d` | `0x002d` | `0x01ad` |
| A53 #2 | `0x0082` | `0x008e` | `0x004d` | `0x01cd` |
| A53 #3 | `0x0083` | `0x008f` | `0x006d` | `0x01ed` |

Read and write USER values differ; do not hardcode one complete tag for both
directions. The frozen candidate filter's masked MID test excludes each
measured A53 origin independently of the nonsecure bit. This was checked
through its actual AXI behavioral harness:
[replay v2](../../build/v2/typed200-amp-deployment-v1/apu-tag-replay-v2/receipt.json)
passes 2,325 total transactions, adding 68 observed USER/PROT cases and 68
secure-bit mutations to the prior regression. Denied transactions produce
no downstream access. Payloads in this harness are its existing lane-pattern
data; it replays source attributes, not a byte-for-byte capture of the
hardware transaction stream.

These measurements do not prove all possible future Linux attributes, R5
identity, absence of integration bypasses, or deployed access protection.
The diagnostic intentionally permits accesses to log their origins.

## Recovery and the rejected raw-clock assertion

The trial ran as a board-local systemd oneshot, with a 120-second start
timeout and stock recovery in both `finally` and `ExecStopPost`. Its
[trial result](../../build/v2/typed200-amp-deployment-v1/probe-target-v1/trial.json)
passed before recovery. Stock reloading succeeded; however, the service
failed its assertion requiring the complete PL0 control register to equal
the initial value. Preserve that failure; do not relabel the service PASS.

Initial `PL0_REF_CTRL` was `0x01010a00`, despite Linux reporting zero
enable/prepare references. After probe unloading it was `0x00010a00`.
Only CLKACT bit 24 changed. Linux disabled the unused clock when removing
the probe's clock consumer. Stock has no PL0 consumer. Both clock summaries
report 99,999,999 Hz with zero references. Parent/divider fields are exact;
the probe ran with positive enable/prepare references at that same rate.
The AFI register remains exactly `0x00000a00` throughout.

A separate
[reviewed recovery completion](../../build/v2/typed200-amp-deployment-v1/probe-target-v1/recovery-reviewed-v1/recovery-reviewed.json)
checks the **exact single-bit difference**, unchanged clock rate and
references, stock overlay and operating FPGA manager, unchanged AFI,
unchanged RPU state, all six recovery-file hashes and the entire saved DDR
window. It then restarts and verifies the original dashboard service.
No raw PS clock write was used to force an unreferenced clock back on.
This is an explicit reviewed recovery difference, not a relaxed timing
constraint or a claim of identical raw PS state.

The target remains accessible over saved-key SSH after recovery. RPU global
control remains `0x50` and LPD reset remains `0x13`. Both R5 cores remain
reset. The qualified encoder package and numerical contract remain frozen.

## Retained failed attempts

* `board-readiness-v3`: authentication and stock inventory succeeded; the
  script stopped because this image lacks `fpgautil`. No target mutation.
  v4 uses the actually installed `xmutil`/`dfx-mgr` path and completes backups.
* The first local AArch64 compile lacked cross-libc headers. Installed
  `libc6-dev-arm64-cross` in WSL, then compilation passed with
  `-O2 -static -Wall -Wextra -Werror`. No board package installation.
* `probe-target-v1`: diagnostic checks passed, stock load passed, original
  raw-clock recovery assertion rejected the clock-gate change. Its journal,
  uploaded hashes and state are retained. The separate recovery review
  completes verification; never restart this trial or overwrite its files.
* `apu-tag-replay-v1`: generated task arguments used the wrong positional
  order and expected forwarding. It failed at the first new read case.
  The generated testbench, runner and failure output are preserved. v2 fixes
  the harness call order and passes; no filter RTL change.

## Next deployment gates

1. **RPU-only diagnostic startup and recovery.** Derive all masks from the
   pinned SDK headers; the RPU AMBA reset mask is `0x4`, not `0x10`.
   Read/verify the actual power state, unused RPU, clock, reset and mode;
   do not infer power state from the debug target label alone. Keep R5
   hardware-halted until its private entry and exception state are set.
   Save/restore DDR only while R5 is definitively stopped/reset. Arm local
   recovery before changing RPU state. Preserve all A53/GEM/PLL/ADMA state.
2. **Exclude unsafe reset helpers.** The installed AMD 2025.2
   `Vivado/scripts/xsdb/xsdb/svf.tcl` R5 processor reset implementation
   (around lines 1171–1184) writes a boot loop at `0xffff0000` and a broad
   LPD reset value. This is evidence about that SVF implementation, not
   proof of every native XSDB reset implementation. Do not invoke an
   opaque processor-reset helper on live Linux without an exact audited
   write set. Live ATF OCM must not be used as a scratch boot loop.
3. **Measure R5 AR/AW origins**, CPU state and all four markers using the
   existing audited ELF. Debug-started execution remains a diagnostic,
   not qualified reset startup. Bind the filter only after actual tags
   match the intended source policy. Re-run negative accesses with the
   integrated filter before admitting inference.
4. **Finish the full candidate**, including ATF/PMU/R5 session activation,
   a safe quiescent firewall transition, relocated hidden-output memory,
   protected clock/reset ownership, private R5 request capture and typed
   result publication. Existing component passes do not discharge this
   composition requirement. Do not apply the boot-only 774-write firewall
   plan to running Linux.
5. **Qualify inference** with matched outputs, exact counters/cycles,
   invalid/fault/drain cases, new implementation timing/CDC/DRC/exception
   evidence and target stress under Linux traffic.

The timing objective remains a canonical **local PL terminal outcome by D
after admission**, under uninterrupted protected clock/reset ownership.
Accepted, Clarify, Abstain, Fault, Deadline and Invalid retain their frozen
meanings. SSH response latency, Linux queueing and ingress capture are not
covered by that deadline. The source-tag probe adds isolation evidence; it
does not establish end-to-end timing, Accepted-by-D, or a 300 MHz result.
