# Timed diagnostic provider and conditional phase observations

Implemented a separate timed successor to the
[owner-local trace](2026-10-15-typed200-owner-trace.md). It binds the existing
trace callback to checked Cortex-R5 cycle-counter reads, adds loader configuration
and PMU evidence, and produces offline phase observations. It does not modify
reviewed v8, the order-only trace candidate, numerical sources, RTL or the
qualified 200 MHz package. No target access, PMU writes, Vivado run, hardware
programming or automation occurred.

## Source basis and explicit assumptions

Arm documents PMCCNTR as a 32-bit counter; PMCR.E and PMCNTENSET.C enable it,
PMCR.D selects full-rate versus every 64th cycle, PMCR.DP can prohibit counting,
and PMOVSR.C is a sticky overflow flag. Debug halt stops counting. CP15 register
encodings and interrupt-enable state are checked against sections 6.3.1–6.3.7 and
6.3.11 of the [Cortex-R5 r1p2 TRM, DDI0460D](https://documentation-service.arm.com/static/5f04288cdbdee951c1cd8969).
The implementation accepts full-rate counting only. It deliberately rejects
overflow instead of recovering modulo differences. Counts are processor-cycle
observations under clock/ownership assumptions, not wall time through debug halt.

The [candidate README](../../firmware/typed200_timed/README.md) specifies the
complete loader contract. After ELF/NOBITS loading, the loader initializes a
32-byte configuration at R5-local **0x2f180**, following the unchanged 384-byte
mailbox. It supplies a fresh matching session, declared CPU Hz and exclusive-PMU
attestation. These are neither A53 physical addresses nor independently verified
frequency/ownership evidence. Private BSS clearing does not erase the NOLOAD
configuration. The new platform binds after the model hash and before service
initialization; binding failure halts with exception 14 while permit remains low.

The provider requires Cortex-R5 PMCR identity, counting enabled, full rate,
counting not prohibited, cycle enable set, cycle overflow interrupt disabled and
overflow clear. Two startup samples must advance. Every event sample checks
controls and overflow, reads PMCCNTR with ISBs, then checks overflow again.
Faults are sticky. The provider does not enable/reset/clear/reconfigure the PMU;
the loader must already have established the reviewed state. Register sampling
cannot exclude a transient reset/reconfiguration between samples. Ownership,
stable frequency and clock/debug continuity remain deployment prerequisites.

## Implemented artifacts and verification

Final run: `build/v2/typed200-timed-host-v3/receipt.json`.

| Evidence | Completed result |
|---|---|
| Host decoder tests | 396 pass, including prior capture/trace tests, counter-state/source/session/frequency errors, overflow/backward/equal ticks, sample-count mismatch and exact integer-ceiling conversion |
| Sanitized PMU tests | 14 startup rejection cases and five post-bind fault cases, plus valid progression and sticky-fault checks; address/undefined sanitizers enabled |
| Differential service behavior | 49 paired poll records / 55,076 bytes exactly match the separately compiled frozen service: state, bridge, proposals, MMIO contents, IDs, permit and mailbox |
| End records | All five fixtures equal the frozen Accepted/Deadline/Fault/CPU-Invalid/CPU-Fault capture bytes |
| ARM link/audit | Separate reset-entry ELF, resolved symbols, RX/RW separation, real counter/configuration functions linked, actual map and stack information audited |
| Instruction audit | PMU object contains expected counter/register MRC reads and no MCR writes |
| CLI | Valid timed mock accepted; sticky-fault evidence rejected without success file; existing output preserved |

The [provider](../../firmware/typed200_timed/pmu.c) exports a 72-byte evidence
record with session/frequency, initial/final control state, sample count,
first/last ticks and sticky faults. It freezes with the one-shot trace: the final
event samples before commit and committed logging stops calling the provider.
The observer must still establish coherent ownership and exclude reinitialization.

The actual ELF uses **18,160 B ATCM** and **51,216 B BTCM BSS**, leaving **2,032 B**
of work capacity. The trace remains 1,488 B; PMU evidence adds 72 B. The NOLOAD
shared section becomes 416 B: original mailbox 384 B plus configuration 32 B.
Trace is at R5-local 0x20010, PMU evidence at 0x205e0, configuration at 0x2f180.
SVC/banked stacks remain 8,192/1,280 B. Linker PROGBITS-to-NOLOAD warnings for
.shared and .clock_config are retained and documented; actual section type,
size and addresses are audited. Compiler frame checks are not exhaustive stack
high-water or WCET proofs.

The derived runner preserves the frozen trace runner and records the generated
source alongside exact command logs/hashes. v1's derived runner had a syntax
escape failure before execution. v2 passed; v3 adds clearer metadata and tests.
Intermediate runner/files and exact v2 tested sources remain preserved. The
exploratory object-inspection invocation initially lacked vendor DLL paths; the
successful inspection with the configured runtime is retained separately.

## How to use the local tooling

Reproduce into a fresh directory:

```powershell
uv run --no-sync python scripts/v2/check_typed200_timed.py --name typed200-timed-host-v4
```

Review captured bytes offline:

```powershell
uv run --no-sync python scripts/v2/check_typed200_timed_capture.py --trace build/v2/typed200-timed-host-v3/accepted.trace.bin --pmu build/v2/typed200-timed-host-v3/accepted.pmu.bin --expected build/v2/typed200-qualification-host-v3/accepted.expected.json --output NEW-UNIQUE-REPORT.json
```

The [timed decoder](../../src/sysone/v2/typed200_timed.py) first applies the exact
typed record/pre-ACK checks. It then requires fault-free matching PMU evidence,
the correct source, two bind samples plus one per event, valid initial/final
controls and strictly increasing ticks through the final event. It never applies
modulo correction. Phase differences bracket hidden copy, bridge/head, proposal,
raw capture and the observed request interval when present. Nanoseconds use
integer-ceiling conversion at **declared** Hz. No logging/provider overhead is
subtracted; these are instrumented intervals and software observation boundaries.

All fixture ticks are supplied by a host mock incrementing 100 per sample; its
500 MHz declaration is test data. The example 100-tick phase is not a hardware
measurement. Reports retain false target-execution, verified-frequency,
verified-PMU-ownership, provenance, bounded-overhead, successful-inference, WCET
and external-delivery claims.

## Remaining gates

A long model-hash/boot/producer-idle interval can overflow this 32-bit counter;
the strict one-shot policy rejects timing evidence in that case. Fresh reviewed
startup/recovery is required; do not clear a running evidence record to hide it.
For a usable target campaign, specify the whole capture window and counter
startup contract. No successful-service upper bound follows from sampled maxima.

This supplies the missing counter-read path and phase-analysis tooling, not a
target timing certificate. The remaining gates are a recoverable typed physical
image with adequate timing margin, reviewed loader/TCM/ECC, enforced other-master
and PMU exclusion, clock readback/continuity, target numerical fixtures and
instrumentation/service bounds. The existing typed physical candidates still
fail the preserved route-margin requirement; no board deployment is implied.
