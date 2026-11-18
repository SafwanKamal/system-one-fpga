# typed200_lut_capture: local linear table-load capture

Experimental sibling. Full encoder regression passes; physical benefit remains a separate measurement.
Only encoder/linear_engine.sv changes. LUT payload and row are captured locally,
then written one edge later. Request/load FSMs and ready/valid are unchanged.
No numerical arithmetic, deadline, epoch or live memory drain/error logic changes.

Universal-byte induction over actual table-write rules passes for all 256 byte
addresses after pending write drain. Reset invalidates initialization evidence;
this is not a whole-engine scheduling proof. The full regression uses independent
frozen encoder_system, encoder_layer and linear_engine and checks table equality
throughout valid drain, as well as golden outputs/AXI/counters and typed failures.
5400 golden words / 14 paired completions pass, with identical external cycles, outputs and raw counts. No physical timing benefit or hardware qualification is claimed by the functional evidence.

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
