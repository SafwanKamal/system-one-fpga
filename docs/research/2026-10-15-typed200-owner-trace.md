# Owner-local pre-ACK diagnostic trace

Implemented a separate R5 service instrumentation candidate in
[typed200_trace](../../firmware/typed200_trace/README.md), continuing the
[offline capture qualification](2026-10-15-typed200-capture-qualification.md).
The reviewed v8 firmware, head/transport, startup/platform/linker, all RTL and
qualified 200 MHz package remain unchanged. No target access, PMU configuration,
Vivado run, board programming or automation was performed.

## What changed

The [generated service diff](../../firmware/typed200_trace/service.diff) adds
diagnostic hooks without changing the existing result-selection rules or ACK
policy. A 1,488-byte private BTCM record captures the first completed request per
successful initialization, then freezes. It stores the full raw terminal digest,
identity/payload/age, defined CSR observations, serialized completed mailbox and
32 bounded event slots. An overflow counter causes offline review to reject an
incomplete trace. No allocation or trace polling loop was added.

Raw terminal capture occurs under the existing service owner before ACK and reads
only the 22 defined read-only offsets plus a second status observation. Reading
the entire CSR window would access write-only/unmapped locations that return
SLVERR; those positions in the exported window are zero. Extra samples are
diagnostic only and never authorize publication or bypass current error/quiet,
session/request, profile or deadline checks.

The mailbox snapshot is serialized before the producer is released by DONE. Its
command_state bytes reflect the known DONE store the service subsequently makes;
the DONE event is logged after that store. No shared bytes are reread after DONE.
This distinction matters: v1's post-DONE copy was rejected during review because
the producer could already be submitting another command. v1 and its exact
sources remain preserved. v2 fixes that ordering; v3 adds a full per-poll comparison
against a separately compiled frozen-service control. No v1 evidence is promoted.

Events mark observed admission/completion, hidden-copy call, bridge/head call,
proposal, capture, mailbox release and ACK. They describe software observation
boundaries, not exact PL admission or final AXI beat edges. A failure can skip
actual head computation within the bridge/head interval. The default target ELF
records **order only**: no clock source is configured and timestamps are invalid.
The injected-clock interface is tested with a wrapping host mock; it does not
attest a real PMU/clock or establish an unambiguous elapsed duration.

## Verification and concrete artifacts

Final run: `build/v2/typed200-trace-host-v3/receipt.json`.

| Evidence | Result | Limit |
|---|---|---|
| Frozen-control differential | 49 paired poll records / 55,076 bytes exactly equal: service/bridge state, proposals, MMIO contents, token IDs, permit and complete mailbox | Same driven host/mock scenarios; not target timing or whole-program equivalence |
| End records | All five Accepted/Deadline/Fault/CPU-Invalid/CPU-Fault captures equal the frozen host baseline byte for byte; label 10 retains the independent image reference | No FPGA inference or ARM numerical execution |
| Host tests | 364 tests pass; address/undefined sanitizers pass for original service policy tests, capture harness and trace unit tests | Fixtures and component checks, not formal whole-service equivalence |
| Trace safety tests | Fixed capacity/overflow, commit/freeze, subsequent-command nonoverwrite, default clock invalid, mock tick wrap, producer mutation after snapshot, corruption/order checks | Clock callback and external observer ownership remain trusted deployment prerequisites |
| Cortex-R5 executable | Separate reset-entry ELF linked with no undefined symbols; actual ELF map and exported trace symbol audited | Never loaded or executed |
| CLI | Accepted trace reviewed; uncommitted trace rejected without success output; existing report preserved | Offline bytes cannot prove provenance or atomic capture |

The [actual ELF audit](../../build/v2/typed200-trace-host-v3/audit.json) reports:

| Region | Diagnostic candidate | Reviewed v8 reference |
|---|---:|---:|
| ATCM code/constants | 17,416 B | 16,080 B |
| BTCM BSS | 51,144 B | 49,640 B |
| Remaining BTCM work capacity | 2,104 B | 3,608 B |
| Exported trace | 1,488 B at R5-local 0x20010 | None |
| Shared mailbox | 384 B at R5-local 0x2f000 | Same |
| SVC stack / banked stacks | 8,192 B / 1,280 B | Same |

No trace is placed in DDR or the producer's shared ABI. R5-local addresses are
not A53 physical mappings. Three examined compiler frame sums are 488, 2,112 and
480 B, below the 8,192-byte stack; absent function names may be inlined. These are
not exhaustive call-graph, measured stack high-water or WCET proofs. The linker
retains the inherited .shared input-PROGBITS/output-NOLOAD warning seen in v8;
the actual diagnostic ELF section is checked as NOBITS at the required address.

Reproduce into a fresh directory:

```powershell
uv run --no-sync python scripts/v2/check_typed200_trace.py --name typed200-trace-host-v4
```

Review an exported record offline:

```powershell
uv run --no-sync python scripts/v2/check_typed200_trace_capture.py --trace build/v2/typed200-trace-host-v3/accepted.trace.bin --expected build/v2/typed200-qualification-host-v3/accepted.expected.json --output NEW-UNIQUE-REPORT.json
```

The [decoder](../../src/sysone/v2/typed200_trace.py) checks commit, fixed ABI,
identity, markers, event ordering, unused slots, source metadata, unchanged
status across capture, shared/PL consistency and the prior typed payload/deadline
checks. CPU faults may retain an inconsistent raw PL terminal for diagnosis; that
raw observation is not promoted to an authoritative CPU result. Reports retain
false target-execution, timestamp-provenance, bounded-overhead, useful-success,
WCET and external-delivery claims.

## What this enables and what remains

This candidate resolves the immediate software-side loss of reusable terminal
evidence after ACK. It gives a reviewable, owner-local instrumentation path for a
future target experiment. It does not establish target capture coherence merely
by using barriers, and it does not enforce exclusion of A53/DMA/other masters.
The trusted observer must wait for trace commit, use the correct TCM mapping and
ownership/cache protocol, and bind the exact ELF/session/PL/model/profile.

Instrumentation adds instructions and **23 MMIO reads** at terminal capture.
Their latency is unbounded in the present service model. Capturing a terminal
may delay CPU publication/ACK; earlier phase hooks may delay proposal enough to
change a target outcome. The independent PL deadline logic is untouched, but
host equality does not establish the same target result under timing pressure.
Keep this diagnostic executable separate from a production timing certificate.

The next prerequisites are a separately reviewed timed platform successor with
an explicit clock/counter startup contract, a recoverable typed deployment image
with adequate physical margin, loader/TCM/ECC validation, enforced ownership,
target numerical fixtures and measured instrumentation overhead. The current
typed physical candidates still fall below the preserved route-admission margin.
No clock, useful-success WCET or external-delivery bound is claimed here. Target
programming remains outside the authorization for these local experiments.
