# Closed: future-question sensor memory

User decision: November 16, 2026.

Close the proposed future-question sensor-memory contribution and its retroactive
activity-learning follow-up. Preserve the source, predeclared protocols, byte
archives, audit receipts and negative results. Do not start another retention
method, tighter-budget variant, or FPGA implementation for this branch.

Evidence:

- [November 8 pilot](2026-11-08-future-sensor-memory-pilot.md): the proposed
  linked-evidence heuristic did not beat strong simple retention baselines.
- [November 16 raw-signal pilot](2026-11-16-retroactive-task-pilot.md): a
  task-blind 1 KiB/window archive achieved the raw reference's running F1 and
  slightly higher stairs F1 at 47.3× compression. Fixed general features also
  stayed close. Cycling failed the raw-reference learnability gate.

This closes the research direction, not the repository's current Git branch or
the independently maintained hardware/gate workstreams. No deployment files,
board state, historical commits or frozen experiment artifacts were changed.

Reopening requires a separately motivated application and new evidence of a
meaningful failure of strong simple baselines, rather than another variant of
the existing activity workload.
