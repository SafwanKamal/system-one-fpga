# Separate timed R5 diagnostic candidate

This candidate links the frozen owner-trace service with a new platform entry,
read-only PMU provider and extra loader configuration. No reviewed firmware,
numerical source, RTL or qualified package is edited. Nothing here installs a
loader or programs a target.

The loader must configure the R5 PMU before entering this executable: Cortex-R5
full-rate cycle counting enabled, PMCR.D=0, PMCR.DP=0, cycle-enable set, cycle
overflow interrupt disabled and overflow flag clear. Exclusive PMU ownership,
no debug halt/counter reset/frequency change, privileged execution and clock
continuity are profile assumptions. The provider never writes PMU registers,
changes the divider, resets the counter or clears overflow. AMD standalone code
may use the PMU for sleep, including divided counting; sharing that service is
outside this profile.

After ELF loading (including NOBITS zeroing), initialize the original 384-byte
mailbox exactly as required by v8. Also initialize the 32-byte
`struct ty_pmu_config` at **R5-local 0x2f180**: magic 0x504d5531, version 1,
the same fresh nonzero session, positive declared CPU Hz, exclusive_pmu_attested=1
and both reserved words zero. These are local R5 addresses, not A53 mappings.
The loader must translate mappings correctly and finish all writes/barriers
before entry. Startup clears private BSS but leaves this NOLOAD configuration
intact. Preserve it under exclusive ownership; the producer's command ABI remains
the original 384 bytes. Configuration and frequency are supplied assumptions,
not self-verifying attestations.

After the model hash, platform startup binds the PMU provider before service
initialization. Invalid configuration/state halts with exception 14 while permit
remains low. The first two checked samples must progress. Each event sample checks
control/enable/interrupt/overflow registers and samples the counter with ISBs;
overflow is checked again after the tick. A 72-byte private evidence record keeps
initial/final controls, session/frequency, first/last ticks, sample count and sticky
fault bits. A sampled bad state cannot heal when subsequent reads return normal.
No resets/tampering between samples are excluded by these checks alone; enforced
ownership remains necessary.

The trace and PMU evidence freeze together when the one-shot trace commits:
the final event samples the counter before commit, and committed logging never
calls the provider again. Observer coherence/ownership and no reinitialization
remain required. The exported symbols are located by the exact audited ELF.

Offline timing review rejects a provider fault, missing samples, any observed
overflow, backward/equal ticks, source/session/frequency mismatch or invalid
controls. It performs no modulo-wrap recovery. A long boot/idle interval can
overflow and make the whole one-shot timing trace unusable; use fresh reviewed
configuration/recovery rather than silently clearing a running trace. Full-rate
32-bit range is finite. The strict policy sacrifices traces to avoid ambiguous
durations.

Phase differences include instrumentation and PMU sampling overhead. Nanoseconds
are integer-ceiling nominal conversions at declared Hz. They are not wall time,
uninstrumented latency bounds or WCET, and they must never be used to claim
successful-inference or external-delivery guarantees. No target measurements are
included: host tests use deterministic 100-tick increments and a fictitious
500 MHz declaration solely to check arithmetic and faults.

Final local run: `build/v2/typed200-timed-host-v3/receipt.json`. It includes 396
tests, PMU sanitizer fault tests, five mock captures, 49 exact paired control
polls, actual ARM disassembly and ELF audit. The target ELF is diagnostic only.
