# typed200_observe: exact observational cycle-count pipeline

Experimental successor. Functional verification below does not establish physical timing or hardware qualification.
Only encoder/encoder_system.sv changes and common/observed_cycle_counter.sv is
added. Counter control events are registered; pending clear/increment correction
preserves the original count at every sampled edge, with clear priority and
modulo-2^32 wrap. No delayed counter is used as a deadline or quiet/fault authority.

32-bit arbitrary-event induction passes. Full independent encoder regression
passes 5400 golden words / 14 paired completions with exact every-cycle counters,
AXI traces and unchanged core/request cycles, including negative drain/error/
deadline cases. ARM proposals are emulated; this is not R5 target/WCET evidence.

Parent: the immutable `typed200_flush` candidate. All prior sealed sources,
qualified 200 MHz package/recovery and numerical baselines remain unchanged.
The typed ABI remains 0x54590201; H384, T1..128 and the frozen numerical contract
are inherited unchanged. Deadline/epoch/live traffic/error veto logic is untouched.
Use the corrected `firmware/typed200_v2` transport and reviewed R5 service, not
historical SHA packing helpers. No board deployment is authorized by this work.

Compile only this candidate namespace. The physical runner uses the qualified
MAX_HIDDEN1024 / 16 attention-lane profile and inherited pipeline options, with
an explicit 5ns encoder OOC synthesis clock. Default module parameters alone do
not establish the tested composition. Frequency requests are not timing closure.

See `docs/research/2026-10-15-typed200-timing-continuation.md` and HANDOFF.md for
current evidence and active jobs. Candidate RTL inventory is bound by SHA256 in
candidate.json; create a successor for any further source changes.
