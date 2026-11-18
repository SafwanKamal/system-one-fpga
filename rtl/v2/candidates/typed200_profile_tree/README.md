# typed200_profile_tree: same-cycle balanced contract validation

Separate experimental sibling of sealed typed200_flush. Only typed_intent_guard
changes: all256 contract bits are compared in 32 byte groups, four reductions and
a final reduction. KEEP boundaries express bounded combinational depth to Vivado.
No register, digest truncation, admission delay or permission bypass is added.
Deadline, identity, current live quiet/error veto, ABI and numerical head are
unchanged. The candidate targets the measured24-level/21CARRY8 placed SHA-to-
admission path in the corrected clock-flow control. Formal equivalence, regression
and actual synthesis/placement are required; no timing benefit is claimed yet.

Use only this RTL namespace and the inherited qualified1024-capacity/16-attention-
lane physical profile. Target inference remains H384/T1..128. Qualified baseline,
all earlier candidates and numerical/package/recovery sources stay frozen.
No hardware programming is part of this experiment.
