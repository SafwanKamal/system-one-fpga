# FPGA MVP progress — 2026-10-18

The first H768 hardware candidate is built, not deployed. The board was not
contacted. Next is a temporary physical request with restoration of MiniLM;
an explicit exception to HANDOFF.md's no-board instruction is pending.

Candidate: build/v2/general-tool-encoder-mvp-v1. It contains a 132,817,920-byte
INT8 BERT-base image, matching linked R5 firmware, relocated buffers, a Linux
module candidate and a lightweight general-call ingress. It uses existing FPGA
operators and needs no bitstream rebuild. The initial package uses v4 baseline
weights. The R5 head ABI smoke matches 19 integer logits on one fixture.
The CPU image client reaches typed JSON but returns no calls for the sample
addition request: semantic success is NOT demonstrated. This is not a completed
MVP, hardware qualification, or terminal-by-D result.

The bring-up script builds against the target kernel BEFORE switching anything,
checks the current model and rollback-module identity, runs one candidate
request, then restores the baseline. A busy PL or unsafe R5 state blocks memory
replacement. No JTAG, reboot, PL reprogramming, permanent entrypoint or dashboard
changes are planned. The candidate firmware identity is checked before a request
is written. Physical execution and positive semantic command behavior remain.

Parallel FPGA work: DDR fetch→6/7/8-bit unpack→signed INT8 dot passes 10,719 row
checks and 72 fault/reset checks. Isolated KR260 synthesis uses 344/384/425 LUTs,
326/342/358 registers, 20 DSPs and no BRAM. This excludes the AXI port from synthesis;
that port is included in simulation via a recorded enum-ternary compatibility
rewrite. No routing/timing/full-model claim. A checked row descriptor stage is
unfinished and deferred; it is not part of the qualified first bundle.

Model work is now frozen for MVP bring-up. The encoder count/kind heads received
147 updates with BERT/span frozen. Reused selection 40 improved 10→11 correct,
correct accepted 2→3, wrong accepted 19→17; epoch 1 retained on ties. Its fresh larger
audit is deferred at the user's request. The earlier typed-span decoder gained
2 audit-correct responses but 10 more wrong accepted calls; it is diagnostic.

FunctionGemma's already-completed fixed candidate run selected v3 adaptation:
28/40 versus official 22/40 on selection. On the paired audit it regressed:
50/72 versus official 52/72; correct accepted 42 versus 44, wrong accepted 19 versus 18.
No general capability improvement or family winner is claimed. A parameter-name
prompt repair fixes 27 prior training prompts and preserves 549 unaffected prompts
byte-for-byte; it tied official on selection and is not promoted for MVP.
The full public BFCL benchmark was not repeated. These are public development
sets, not blind tests or matched-compute family comparisons.

The proposed 32-bit token boundary passes 28 host/C frames and a Cortex-R5 compile;
it is separate from the deployed ABI and not a complete decoder controller.

The user explicitly prioritized MVP speed over further experiments. Larger
model audits, new sweeps and decoder optimization are deferred. Existing sealed
artifacts were hash-verified unchanged. The immediate work is the first board
vertical slice, not another benchmark campaign.
