# Linux-managed R5 smoke: successful target startup and recovery

The corrected TCM-only R5 smoke passed on KR260 in the existing lockstep mode.
The independent kernel work item stopped R5, confirmed firmware FORCEDOFF,
unmapped TCM, verified release of both ATCM leases, and allowed normal module
unload. Linux stayed on the same boot throughout. JTAG remained stopped.
This qualifies a narrow diagnostic sequence on the observed system, not full
typed inference, adversarial Linux containment, hard timing, or exhaustive
hardware fault behavior.

Evidence root: `build/v2/typed200-amp-linux-r5-controller-v1`.
Prior anchor is `2026-10-17-typed200-amp-linux-r5-validation.json`;
`preservation-before.json` verifies all 10,368 prior mapped files and preserves
the original anchor separately. No sealed RTL, previous firmware/ELF/package,
qualified numerical evidence or README was edited. No commit or push.

## Controller fixes

The separate GPL Linux module in `firmware/typed200_amp_linux_r5_controller`
uses a small tested session engine instead of the vendor remoteproc unwind.
It accepts only audit, prepare, start and stop for one embedded, hash-identified
smoke image. There is no arbitrary firmware, address, register or PM-node input.
Module loading itself performs no firmware calls or TCM mapping.

Preparation reserves the low 64 KiB TCM aperture and verifies no enabled R5 DT
owner, RPU0/RPU1 firmware state FORCEDOFF, a valid current mode and no owners for
ATCM PM nodes 15 and 17. Both banks are claimed conservatively so the low TCM
image can run in the already configured lockstep mode without changing mode or
TCM-combine settings. The low address mapping is consistent with AMD's
[TCM address map](https://docs.amd.com/api/khub/documents/xzMsp_c5sG9J6A3u7NkJYQ/content).
The actual mode getter uses the advertised ATF SMC return register directly,
avoiding the installed kernel getter's incorrect status-slot assignment.
Generic firmware debugfs IOCTL remains forbidden and unpatched on the board.

Each bank has its own pending-ownership bit, set before its request can have
side effects. Failed requests and failed releases are reconciled with the PM
usage query. Recovery releases only exclusively owned banks and clears each bit
only after no owner is confirmed. This handles a failed second request without
losing the first lease, and an error returned after release without double
release. Unknown ownership retains the remaining reservations and module pin.

The controller checks blocking stop plus a separate FORCEDOFF query before
mapping/loading and before releasing live resources. Wake is marked potentially
running before submission, including failed/ambiguous submission. A failed stop
or failed confirmation leaves mappings, leases and module reference retained in
quarantine. A later explicit recovery may retry stop; it never automatically
retries wake. No ordinary unload is possible while the session holds its module
reference. The module has no platform-driver unbind or overlay removal path.

There is one non-devm TCM mapping. Loading writes aligned 64-bit values throughout
the private 64 KiB aperture, then reads back every value. No TCM reads precede
that initialization. Error unwinding and ordinary cleanup use the same ownership
engine. Suspend/hibernate/restore preparation is refused while a session is held.

A kernel delayed work item is armed before prepare and rearmed before start,
with a five-second requested delay. It captures the trace then recovers without
an SSH stop command. The board-local root service also has start/stop timeouts
and ExecStopPost recovery. Linux scheduling and a blocked firmware call do not
have a proven WCET; this is not protection against a completely hung Linux/PMU.
The user was available for a physical power-cycle fallback, which was not needed.

## Validation and field trials

| Evidence | Result |
| --- | --- |
| session-check-v3 | 10,465 real session-engine trajectories with address/undefined-behavior sanitizers; single, paired, randomized and persistent failures |
| adapter-check-v6 | 25 blocked-build, 26 prepare-only and 35 modeled-live scenarios using extracted actual adapter functions, including mode ABI, TCM bounds/readback, both-bank rollback, failed wake/stop and PM suspend veto |
| module-build-v5 | Built against installed headers; prepare-only admission, start compiled off |
| prepare-trial-v1 | Hardware PASS: both leases, full TCM readback, no R5 start, watchdog cleanup, re-audit and module unload; service 5.963 s |
| module-build-v6 / smoke-trial-v1 | Original image reached undefined handler; trial FAILED, recovery and module unload succeeded |
| smoke-emulation-v1 | Corrected image PASS 164 actual-ELF execution/fault/publication cases, plus prior-VBAR rejection and CP15 allowlist |
| module-build-v7 / smoke-trial-v2 | Corrected hardware smoke and automatic recovery PASS; service 6.183 s |

The host mocks do not establish physical power/reset/ECC state or scheduler
timing. The prepare and smoke trials provide actual target observations for
this sequence; failed-stop hardware faults were not deliberately induced.

The final fresh target trace was:

```text
R5: PASS
SCTLR=00e50878
CPSR=000001d3
MIDR=411fc153
```

The image has no DDR, PL, PS MMIO, timer, IPI, inference or admission accesses.
It performs CP15 startup checks, trace formatting/publication and WFI in TCM.
Final corrected ELF:
`smoke-build-v1/sysone-r5-smoke.elf`, SHA256
`65033cebee9df86b202f0b86206302eb639768bd389884f22be3c891eaf23b53`.
Final actual ARM64 module:
`module-build-v7/target-build/module-binary.stdout`, SHA256
`9edf6bd825660bb65d7774d57c94ce175bd5a6c4cfc35e448ae42289ea63aeba`.
Kernel vermagic is `6.8.0-1036-xilinx SMP preempt mod_unload modversions aarch64`.
It is an unsigned external module, not a replacement installed kernel or vendor
module. BTF generation was skipped because the headers lacked vmlinux.

## Newly discovered startup defect and preserved failure

The original sealed smoke wrote CP15 VBAR. Cortex-R5 does not implement VBAR;
the hardware reported undefined instruction (`ERROR=00000001`). The
[barebox R5 startup correction](https://lore.pengutronix.de/barebox/20250113-k3-r5-v3-5-065fcdcc28d3@pengutronix.de/)
describes this architectural restriction. The preserved AMD BSP `boot.S` also
places VBAR writes inside its ARMR52 conditional. The previous audit overlooked
that distinction, and Unicorn's R5 model allowed the unsupported write. Its 164
earlier passing cases therefore did not establish instruction compatibility.

The new `smoke-v2.S` removes the VBAR setup and retains SCTLR.V selection for low
vectors. The successful hardware trial, after this sole executable change,
supports the diagnosis. The old image and failed trial remain unchanged. The new
checker explicitly rejects VBAR in the ELF, verifies that the old image fails
this check, and allows only the reviewed CP15 instructions during execution.

This issue also appears in preserved `typed200_r5/start.S`, `typed200_mvp/start.S`
and `typed200_amp_probe/r5_probe.S`. Their sealed artifacts must not be rebuilt
in place or treated as CPU-startup-qualified. Port the correction into separate
future candidates before executing them. The original DDR diagnostic ELF remains
unchanged and unexecuted.

## Board end state and replay

After the successful trial, post-health reports 9h09 uptime on boot
`6c80ec1a-e7ae-473f-b169-d54f129615d1`, CPUs 0-3 online, remoteproc empty and the
smoke module absent. Kernel taint is 12288 (`O` external module + `E` unsigned
module), which persists after unload until reboot. No additional taint bits or
new fault messages appeared in the captured post-trial kernel log. Earlier
storage/journal warnings predate the trials. No power-cycle is requested.
COM9 captures were passive, 115200 8N1, no flow control, DTR/RTS off; the board
produced no UART fault output during these trials. Captures were closed afterward.

The earlier successful services loaded hash-checked modules from the trusted
user build directory and used a root-private script. `smoke-replay-v1` is a
subsequent, unexecuted replay plan that additionally copies the exact verified
module bytes into the fresh root-private staging directory before insmod,
closing the build-path check/load race. Its root service still checks the module
hash and uses the same tested module/firmware and recovery. This hardening changes
staging only; it has not been claimed as another hardware execution trial.
Re-inventory kernel/firmware/ownership and arm UART before future runs; do not
create a repeating service or run the original invalid image.

The only board writes were additive build/staging files, transient module/service
state, Linux-managed RPU/ATCM PM operations and the private TCM image. There were
no JTAG connections, raw Linux PS/RPU MMIO, mode/config writes, PL programming,
DDR modification, boot changes, QSPI/fuse/security writes, commits or pushes.
Firmware PM APIs internally implement the RPU power/reset operations; this is
not a claim of no hardware state changes.

## Scope remaining

The requested smoke diagnostic has passed and recovered. Keeping UART and
Ethernet connected and being available for recovery is the useful user-side
acceleration; no further physical action or kernel rebuild is needed now.
Full inference deployment remains gated on separate corrected startup candidates,
R5 source tags, trusted firmware/session composition, firewalls/source filtering,
hidden outputs, exact numerical/cycle/fault/drain regression, physical checks and
target qualification. This smoke does not establish admitted timing, source-tag
identity, protected inference ownership or malicious-Linux safety.
