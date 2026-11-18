# R5 typed200 reset-entry candidate

Research candidate; never executed on target or hardware-qualified. Build and host
check with `python scripts/v2/build_typed200_r5_elf.py --name NEW_UNIQUE_NAME`.
Current reviewed executable: `build/v2/typed200-r5-elf-v8/typed200-r5.elf`.
It uses the sealed head in `typed_intent` and corrected transport in `typed200_v2`;
the historical SHA-bearing MMIO helpers are not linked.

## Deployment prerequisites (not implemented by this executable)

A trusted loader must initialize the PS/DDR and the separate typed200 PL design,
configure R5_0 split mode, enable/initialize split TCM including ECC, load the ELF,
and enter address zero in privileged ARM state with MPU and caches disabled.
The loader must establish exclusive access to the model, program, ID/result DDR,
typed CSR and deployment GPIO. An A53/Linux or other-master exclusion mechanism
is required; the R5 MPU alone cannot enforce it. The model must stay immutable
after its boot hash. No loader, device tree, remoteproc or board configuration is
installed by this work.

**After loading** the ELF (a loader may zero NOBITS segments), initialize the entire
384-byte shared structure at R5-local `0x2f000` to zero, then set magic `0x54594331`,
version 1, a fresh nonzero 64-bit session and exclusive_buffers_attested=1. Leave
command_state IDLE. The loader must translate local TCM addresses to the correct
system address; `0x2f000` is not an A53 mailbox address. Reusing a session or
booting against an already configured PL is forbidden. Acknowledge faults only
through coordinated fresh-session/reset recovery, not a running-service retry.

## Memory and startup

ATCM code/constant region: `0..0xefff`; banked exception stacks: `0xf000..0xf4ff`
(256 bytes each). BTCM work: `0x20000..0x2cfff`; SVC stack: `0x2d000..0x2efff`
(8192 bytes); shared area: `0x2f000..0x2ffff` (384 bytes used). Link assertions and
both host and target ABI assertions check capacity/layout. No heap or DDR code.

Startup masks IRQ/FIQ, selects low vectors, sets VBAR, initializes VFPv3-D16 and
FPSCR, clears private BSS and enables the MPU. Code/constants are privileged RO;
work/stack/shared are RW and execute-never. The 64 MiB DDR window at `0x60000000`
is normal noncacheable shared; 8 KiB MMIO at `0xa0000000` is shared Device/XN.
Caches remain disabled. ACTLR follows AMD's normal GHT/return-stack prediction
policy and disables DBWR for erratum 780125. Prediction has not been bounded for
WCET. RPU clock/split/TCM/ECC initialization remains the loader's responsibility.

## Cooperative command protocol

Wait for boot_status=1. A trusted producer fills tokens (1..128), first/count
(nonempty contiguous selected rows), positive budget in PL cycles and token IDs
(all <30522); writes a strictly increasing nonzero 32-bit sequence; issues the
required interprocessor memory barriers; publishes READY last. It must not modify
the command until DONE. Sequence exhaustion requires a fresh session/recovery.
Use the structure in `service.h`, not a packed alternate layout.

The R5 copies IDs before PL admission, owns the 64-bit request ID, observes actual
admission/shape, waits for native completion and drain, copies hidden codes into
TCM, runs the frozen head and submits its proposal. It checks the PL terminal
identity and outcome before publishing result/DONE. result_origin=1 means a
validated PL terminal; 0 means a CPU rejection/fault. CPU faults can occur after
admission. Non-Accepted payloads are empty. Only a successfully validated reusable
terminal is ACKed; deadline, fault or identity inconsistency halts the service.

boot_status high bit and exception_reason report a halted startup/runtime trap.
A stuck CPU or bus may prevent even this report. The authoritative PL terminal
must remain independently accessible to a trusted supervisor. No target client,
host/R5 memory-coherency test or bound on external delivery is claimed.

## Timing assurance boundary

The PL gate provides the already proved conditional **local terminal record by
D uninterrupted PL cycles** contract, including a failure outcome if useful work
does not finish. The R5 polling loop and MMIO/DDR completion are not currently
bounded. Host sanitizers and a successful link do not establish ARM binary64
numerical equivalence, WCET, successful inference by D or a wall-clock deadline.
Target boot/MPU/FPU readback, frozen golden vectors, PMU/PL traces, contention,
late-commit aborts, clock/reset fault tests and enforced buffer ownership are
required before deployment claims. See the
[physical/R5 research report](../../docs/research/2026-10-15-typed200-physical-r5.md).
