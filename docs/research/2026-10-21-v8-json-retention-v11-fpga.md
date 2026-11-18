# Fixed JSON retention prompt: paired CPU/FPGA qualification

This is a finite qualification on the existing v8 image, not the full sweep.
The board must be reserved through the canonical BOARD_STATUS.json, and actual
board operations hold `/run/lock/sysone-inference.lock`. No FPGA programming,
launcher changes, model/package updates or persistent service changes are made.
All new artifacts are separate from earlier sealed experiments.

## Frozen workload and gates

Two fresh eight-step trusted-observation sequences use opposite target entities.
They cover successful observations, distractor updates, missing/error count
preservation, conflicting non-ok statuses, no new observation and successful
recovery. There are16 primary requests and4 repeats per backend. Repeats select
steps4 and6 of each sequence, covering missing/error rather than just easy ok
answers. Primary status distribution is ok6, missing4, error6; both entities are
queried eight times. New state/query identities are checked against v9/v10 data.

The instruction and logical chat prefix are the frozen v10-r3 status-copy
prompt. No prompt search, model-specific examples, value repair or parser changes
are introduced. The v6-r2 tolerant parser and v9 read-only retention scorer are
reused unchanged. Host observations alone update state; closed-loop is excluded.

Both backends use the same frozen129 input token IDs and48-token output budget,
with context256 and no inter-request prefix reuse. CPU uses pinned Qwen3-0.6B
Q8_0 greedy llama.cpp; FPGA uses the sealed v8 runtime and resident weights.
Outputs run to actual EOS or budget; no parseable-prefix salvage or tool execution.
CPU process time includes model loading and is not a comparable FPGA latency.

Qualification gates require20/20 parsed and semantically correct outputs per
backend, all input token IDs aligned, paired semantic agreement, exact FPGA
repeat token IDs, passing causal fixtures before/after and unchanged deployment
identity. Raw text agreement is reported separately because arithmetic differs
between CPU Q8_0 execution and FPGA INT8 block32 activation arithmetic.

## CPU prompt-file framing issue found before board access

The first new CPU request enabled llama.cpp verbose prompt-token logging. It
found that the CLI removes one final LF from file input: the recorded frozen
prefix ended in token271 (two line feeds), while actual CLI input ended in
token198 (one line feed). Both had129 tokens, so count checks alone did not
detect this. The generated answer was correct, but actual input parity failed
before a scored request was committed or any board access occurred.

That attempt, including raw stdout/stderr and the frozen bundle, is preserved
under `build/v2/v8-json-retention-v11` with a25-file seal and disposition. The
separate final revision is `v8-json-retention-v11-r2`. It adds one **file-framing**
LF via binary output; the CLI removes it, leaving the intended frozen prompt
unchanged. Every request now verifies all actual CLI token IDs from verbose
stderr, not a host-computed token list alone. The parser, instruction, logical
prefix, seeds and case values are unchanged. A regression test checks the file
framing, and actual inference checks enforce it independently.

This also limits earlier CPU evidence: v10's224/224 remains an observed CPU
quality result, but its stored prompt IDs were nominal, not independently
verified actual CLI IDs. It cannot establish exact CPU/FPGA input parity. This
qualification reruns CPU with corrected framing rather than reusing old scores.
Earlier artifacts remain unchanged; use frozen snapshots to reproduce them.

## Board controls and provenance

The shared status initially had no reservation and recorded v8 restored by
Claude's hardware session. Codex reserved the board before SSH access, then
verified the live image, package manifest, launcher, boot ID,125/250MHz clocks,
DMA layout, R5 state, services and competing inference processes under the
kernel lock. Live identity matched v8. Both MVP and full-sweep services were
inactive/dead. A pinned SSH host key is checked; authentication stays in memory.

Only a new benchmark bundle is uploaded, to
`/var/lib/sysone/benchmarks/v8-json-retention-v11-r2`. A separate transient
finite unit runs exactly20 FPGA requests. The runner verifies every bundled
source/input hash, validates the existing59-file deployment package before and
after, verifies resident model bytes during startup, and runs causal single/batch
fixtures before and after inference. The original v8 runtime is copied from
the sealed baseline rather than from a hardware candidate worktree.

The final live inventory must match the initial one. A verified observation is
recorded in the canonical board-status file before ownership is released.
Uncertain failure keeps ownership and records unknown; no reset is attempted.
34 focused tests passed, including serial board reservation tests, independent
event replay, immutable state after wrong answers, fixed prompt identity,
non-ok repeat coverage and CPU file framing.

## Completed results

**Qualification passed all gates.** CPU and FPGA each scored20/20 parsed and
semantically correct records:16/16 primary answers plus4/4 repeats. Including
repeats, both scored ok6/6, missing6/6 and error8/8. All20 pairs used identical
actual input IDs, verified from CLI verbose logs on CPU and the tokens supplied
to FPGA prefill. All20 normalized semantic records matched.

Raw text matched19/20 pairs. On `qual-1-005`, CPU emitted a pretty-printed object
and FPGA emitted a fenced JSON object; both supplied error, B and737. The fixed
parser already permits both forms, so no correction was required. Raw-text or
cross-backend generated-token identity is not claimed. All four FPGA repeats
did reproduce their original complete generated token-ID sequences exactly.

Both causal fixture checks passed16 cases each; worst absolute error was
7.152557373046875e-7 against the2e-5 threshold. Startup verified the complete
resident model with `resident_pipelined_native_copy_ordered_sha256`, model SHA256
`9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031`.
Package hash, launcher, boot, active image, clocks, DMA layout and services
matched before/after. The kernel inference lock was released, the SSH session
closed, and the canonical board status recorded ready before reservation release
(revision12 at completion). MVP and full-sweep services remained inactive/dead.

The final qualification is separately sealed under
`build/v2/v8-json-retention-v11-r2`, including `qualification-summary.json`,
`paired-comparisons.csv`, `paired-comparisons.json`, `repeat-checks.json`,
`cpu/`, `fpga/`, `board/`, frozen bundle, archive and reporting source. All prior
v8/v6/v7/v9/v10 and framing-diagnostic seals verified unchanged. There were
20 CPU qualification inferences and20 FPGA qualification inferences, plus the
one preserved CPU framing diagnostic; fixture commands are separate checks.

This supports the frozen status-copy prompt on v8 for this small paired
retention workload. It does not extend the CPU64-step qualification to FPGA,
establish arbitrary model/context reliability, qualify closed-loop reasoning,
or justify a speedup claim. V8 was unchanged and the full sweep stayed stopped.
