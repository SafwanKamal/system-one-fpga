# Separate R5 diagnostic trace candidate

This directory substitutes only the service unit and adds trace storage/functions
when linking with the unchanged reviewed head, typed200_v2 transport, startup,
platform, SHA and linker. It never overwrites or links changes into R5 v8. No
loader, board programming, PMU setup or target execution is supplied here.

`service.diff` shows the exact changes from the frozen service. The generator
refuses to overwrite an existing candidate. The initial candidate metadata's
service hash is checked by the final evidence seal; it is not a deployment
certificate.

`ty_trace` is an exported 1,488-byte private BTCM record, ABI version 1, with 32
fixed event slots. The record is reset on successful service initialization and
committed once, after the first output and its ACK if reusable. Subsequent
commands never overwrite it. Overflow saturates a dropped-event count; the
offline checker rejects incomplete/overflowed records. Ordinary polling neither
logs events nor repeatedly samples a clock. Invalid early startup does not create
a fresh trace: check the captured session and manifest, never infer a new boot
from an old record.

The raw pre-ACK snapshot reads only the 22 defined read-only CSRs, plus a second
status read to detect a changed terminal state. Other locations in the 256-byte
export are zero. The snapshot follows the original terminal observer, before
validation/output/ACK. A rejected raw terminal can therefore accompany a CPU
Fault record; it is diagnostic data and has no publication authority.

All mailbox fields are copied before publishing DONE, while the producer must
still leave them unchanged. The trace serializes command_state as the exact DONE
value the service subsequently stores, then records the DONE event after that
store. It never rereads producer-owned bytes after DONE. Thus the trace mailbox
is a serialization of the completed output at publication, not an independent
post-DONE memory dump. The snapshot is checked against the frozen output bytes in
host tests. Commit is written last after barriers. A reader must wait for commit
and establish exclusive ownership/coherence; barriers alone do not establish
cross-core cache/memory ownership.

Events bracket observed admission, observed native completion, hidden copy,
bridge/head call, proposal call, raw capture, DONE and ACK. Observed admission is
not the exact PL admission edge. Native completion is observed with drain/quiet
status, not a separately timestamped final bus beat. The bridge/head interval
includes bridge checks and may skip the head on a failure. These boundaries must
be respected when interpreting traces or composing later bounds.

The default linked ELF has **no timestamp provider**: clock_valid=0 and all ticks
zero, so only event order is available. `ty_trace_clock` accepts a trusted injected
read function/source/frequency before initialization for a future platform
successor; the host unit test uses a deterministic wrapping mock. That API is not
a clock attestation or PMU setup routine. The current target ELF may garbage
collect the unreferenced configuration function. Do not call it by a guessed
address. A real timed platform successor needs a separately built, identity-bound
clock configuration, loader/startup review, wrap/interference assumptions and
overhead measurements. No duration or WCET follows from this order-only ELF.

Instrumentation changes instructions and adds 23 MMIO reads at terminal capture;
their completion latency has no established bound. A bus stall can delay CPU
publication/ACK, although the PL terminal is already available under its own
assumptions. Earlier phase hooks can delay a proposal enough to change a target
outcome. Host equality under stable mock registers is not target timing or
whole-service equivalence. This ELF is for diagnostic qualification experiments,
never an automatically promoted production image.

Final reproducible run: `build/v2/typed200-trace-host-v3/receipt.json`. It records
364 tests, five fixture outcomes and 49 paired poll records, host sanitizers,
actual ELF map/stack information, source hashes and all command logs. v1/v2 and
their exact tested source snapshots remain preserved as intermediate iterations.
