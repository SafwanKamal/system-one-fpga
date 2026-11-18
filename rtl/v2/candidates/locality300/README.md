# Experimental locality300 candidate

Read [the implementation record](../../../../docs/research/2026-10-15-locality300-implementation.md).

These sources are an isolated copy of the qualified 200 MHz snapshot with local
query-read replicas, registered local MAC selects, a separate deadline outcome
supervisor and an experimental feature family. They do not replace `rtl/v2`'s
qualified public sources. `candidate.json` seals the source hashes; README is
documentation outside that source manifest. The candidate is not timing- or
hardware-qualified and has no package/deployment support.

Do not edit/recreate sources under an active build. Preserve all failed evidence.
Use `create_locality300_candidate.py --verify` to check sources and the original
baseline; never rerun historical integration or qualification scripts.
