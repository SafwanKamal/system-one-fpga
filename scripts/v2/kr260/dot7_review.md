# Dot7 cursor/shared-read candidate — October 13, 2026

## Full synthesis completed; placement active

All 53 KR260 numerical cases and two Nexys cases passed with unchanged encoder
cycle counts. Full synthesis and resource/RAM/fanout gates completed in 31m24s:
96555 CLB LUTs, 64795 registers, 59 BRAM tiles, 36 registered-output URAM and
610 DSPs. Compared with failed dot5, LUTs decrease 5894 (5.8%) and registers
decrease 48440 (42.8%). Actual memory LUTs 16060 (27.88% of device memory LUTs).
These full-design measurements supersede isolated area extrapolations.

Unplaced 300 MHz setup estimate remains -0.957 ns on instruction_reg[284] ->
embed_inst/p_term; no 300 MHz closure. One placement diagnostic is active in
session 72255, using the frozen synthesis project. It reports congestion and
125/150/200/250/300 MHz timing estimates. Routing remains deferred until review.
The deployed 125 MHz app is unchanged. Historical progress below is preserved.

The residual engine replaces token*row_words address products with a sequential
cursor. Its carry is retained before halving for INT8 reads, including exported
address wrapping. Legal rows are positive multiples of 16 elements. Instruction
start/reset reinitialize the cursor; row/token counters still control completion.
No added pipeline stages or external interface changes.

Attention LOCAL_ACCUMULATOR_CONTROLS=3 shares one registered read address between
weighted accumulation and context output. It captures word_next when state_next
enters WRITE, only after pipeline_busy drains. During weighted updates it captures
s_word[P-1], retaining consecutive one-word-head read/modify/write timing. A
simulation assertion checks that no bank write remains active during WRITE or
WRITE_FLUSH. Modes 0/1/2 and the frozen dot6 candidate are retained.

Focused residual equivalence passed 281736 writes against the frozen original:
widths 16/48/80/256/512/768/1008/1024, 1/3/7/128 tokens, non-power-of-two rows,
maximum 128-token buffer boundary, reset/restart, saturation and all shift values.
Dot widths 1..32 also passed unchanged. Evidence: rtl-dot7-arithmetic logs.

Residual OOC comparison versus dot6: CLB LUTs 2978 -> 2865, registers 864 -> 879,
estimated setup at 3.333 ns +0.185 -> +0.205 ns. This is synthesis only and is
not full-design 300 MHz timing closure. The small register increase implements
the cursor. No hardware or boot memory has changed.

Four-lane attention OOC comparison completed: CLB LUTs 8944 -> 7513 (-16.0%),
memory LUTs 3144 -> 1672 (-46.8%), registers unchanged at 4108. Actual DSP tiles
remain 13 and BRAM primitives remain 6. This is not a full-32-lane area/timing
result. Evidence: build/v2/dot7-ooc-summary.json and dot7-attention-ooc reports.

The full base gate passed: 32 KR260 cases, two Nexys cases and streamer stress;
source hashes match current RTL. Its snapshot is recorded in
build/v2/rtl-dot7-check/snapshot.txt. The 21 extra H1024-profile cases remain
active. Preserve all evidence and never alter RTL under test. Eleven additional
focused shared-read equivalence profiles also passed against the frozen dual-read
engine with nonzero recurrent data, dim=48 (three words), group/head transitions,
stalls and weighted-phase reset/restart. Focused reference/current hashes verified.
Evidence: build/v2/rtl-dot7-attention-equivalence. The simulation compiler grouped generated fast C++ into a large
translation unit; its initial compilation occupied one core for several minutes.
Explicit bank drain assertions also add simulation work; FPGA logic excludes them.
Simulation wall time is not deployed inference latency; cycle counts stay matched.

run_dot7_after_regressions.ps1 is active as one local dependency job (not recurring).
It waits for the complete numerical summary, detects regression failures and has a
two-hour dependency timeout. Queue status: build/v2/dot7-queue-status.json; logs:
build/v2/dot7-queue-console.log. It has NOT launched full synthesis yet.
After numerical completion it runs preflight_dot7_large_candidate.ps1, which requires
complete numerical/source/protocol/OOC gates and freezes the 17 tested sources.
It runs synthesis only at an exploratory 300 MHz constraint, requiring registered
UltraRAM, actual accumulator RAM inference and control fanout gates. Before
placement, require at least 5% CLB LUT relief versus the failed dot5 candidate;
this is a heuristic spending gate, not a routing or timing guarantee.
