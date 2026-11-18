# Request window and embedding row-address integration proposal

This is a proposal, not authorization to bypass gates or a production edit.
Read the current handoff and actual job status before acting. Preserve all six
rejected placed candidates and the hardware-qualified 125 MHz package.

The private request-window limit already passed full output/cycle equivalence
and isolated request-admission composition synthesis. The private embedding
offset cut passed focused whole-engine descriptor/output/cycle comparisons;
combined numerical regression and a dynamic-address whole-engine OOC comparison
are still running or pending. Inspect their existing controllers; do not repeat
them. Review the new source-data-to-offset multiplier path and actual inference,
area and timing before selecting this cut. The offset stage uses the existing
ID_WAIT acceptance edge, and the base add uses ROW_ADDRESS. No FSM state is added.

If both cuts have supporting numerical and mapped timing evidence, integrate
separate default-off CACHED_REQUEST_WINDOW and PIPELINED_EMBED_ROW_ADDRESS
parameters. The former belongs to LINEAR; the latter belongs to EMBED. Propagate
each through encoder_layer, encoder_system, KR260 and its wrapper and simulation
parameters. Keep the exact old branches when disabled, including default Nexys
outputs and cycles. Never replay previous integration scripts.

Proposed candidate: request-window-embed-large. Proposed separate app:
sysone-v2-request-window-embed. All lower 16 bits retain the existing
attention16-distance flags. A new feature family 0x53600000 reserves bit16 for
cached request window and bit17 for staged embedding row address. The fully
enabled paired profile would be exact 0x5363ffff. The old attention16-distance
profile remains 0x535affff when both new options are disabled. Partial words
0x5361ffff and 0x5362ffff must be rejected by package, deployment and runtime
admission; no software support or public capability is applied by this document.
The unrelated experimental SYS3 relative-address ABI remains 0x53590300/bit0.

Require a fresh parameterized 36 KR260, six partial tile and two default Nexys
proof with exact prototype output/cycle equality before freezing sources. Bind
the numerical logs, complete fixtures, component proofs and OOC source hashes.
Derive new register-inventory gates from the actual mapped offsets and window
registers, including constant-bit optimization; do not assume 64 active offset
FFs. Retain all existing URAM, local capture, FIFO, drain, dot, query, probability,
distance, row and LINEAR read-first/no-extra-output-latency gates.

The placed attention16 design also has query/MAC selection, AXI weight acceptance
and layernorm address paths around +0.357 to +0.369 ns. These remain concerns.
Review them alongside the independent cuts before another expensive full build;
isolated gains cannot be added to placed slack to claim closure. One heavy job
at a time. A new full synthesis still requires resource/inference/timing review,
then one placement diagnostic and a candidate-specific routing decision with
at least +0.5 ns meaningful 200 MHz setup margin. Positive legally routed setup
and hold, matching XSA/bit/source/fixture receipts and board tests remain required
before any qualified package or deployment claim.
