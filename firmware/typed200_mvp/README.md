# Cold-boot typed-output MVP candidate

Unexecuted candidate. No boot image, PL image, package or deployment is produced.
The qualified baseline and all earlier firmware remain separate and frozen.

`a53_start.S` / `a53.c` form a secure EL3, OCM-resident A53_0 handoff.
`start.S` / `platform.c` form the R5_0 reset-entry supervisor. `ownership.c`
contains the same register policy exercised by host fault injection.
`supervisor.c` gates the frozen typed service; `vendor_regs.h` uses pinned AMD
definitions from `reference/`. The loader embeds the newly linked R5 ELF's
load segments, zeros its NOLOAD memory, verifies the load, then writes config.

This profile deliberately stops A53/Linux and other DMA-capable application
masters. R5_0 runs one preloaded request and parks with permit low. PMU, CSU,
authenticated boot, debug and the board's other PL masters are trusted and must
remain quiescent under the declared profile. This does not implement XMPU/XPPU
protection against a hostile privileged master or a live Linux client.

Cold-boot loader prerequisites, before entering A53_0 at `0xfffc0000`:

- DDR, the exact reviewed typed PL design, PS clocks and GPIO reset initialized;
  permit initially low, no prior admitted work or outstanding master traffic.
- RPU power/TCM clock/AMBA and access permissions supplied; both R5 cores are
  available to be halted/reset; PS clocks already stable (no immediate enable).
- A53_0 at secure EL3, MMU/I-cache/D-cache off; no bootloader return is expected.
  Candidate entry checks these execution conditions and otherwise parks.
- A trusted producer loads the exact model and a fresh nonzero session plus
  one request. `struct { struct mvp_boot boot; struct ty_shared request; }`
  occupies 448 bytes at `0xfffee000`. All boot reserved words must be zero;
  request identity/config must match. The command must be READY. Invalid shape
  or ID fields are left to the frozen typed service, which returns Invalid.
- PMU/CSU/debug cannot release held cores/masters, change clocks/reset, access
  buffers or modify PMU state while the request is admitted. This is a TCB
  prerequisite, not something proved by a mailbox flag or register snapshots.

R5 code/constants are privileged RO executable TCM. Private data/stacks are
RW/XN TCM; model/hidden DDR is RO/XN, only the 4 KiB ID overlay is writable.
Clock/reset/GPIO-control registers are Device RO. PL CSR/permit remains Device
RW. Boot and PMU configuration overlays are RO after MPU initialization.

The final mailbox has `boot_status=2` after terminal parking. Use the separate
`sysone.v2.typed200_mvp.assess_mvp` offline consistency gate with the raw trace,
PMU evidence, final shared mailbox, boot config, owner evidence and permit word.
It checks agreement with the frozen pre-ACK trace without editing that trace.
The frozen v1 shared decoder expects boot_status=1 and must not be used directly
on the parked mailbox. Offline bytes do not establish target provenance or WCET.

Local verification uses `scripts/v2/check_typed200_mvp.py --name
typed200-mvp-host-vN` with a NEW directory. Completed attempts must not be
overwritten/restarted. Current final run: `typed200-mvp-host-v5`; final review:
`typed200-mvp-review-v1`. See the dated research report for receipts and the
target-only acceptance gates. Do not run this candidate on the board yet.
