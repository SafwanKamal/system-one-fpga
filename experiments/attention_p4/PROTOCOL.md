# Attention with four prompt tokens per K/V pass (P=4): exactness audit (C simulation)

Written 2026-11-19, before the first run.

## Why

The pilot timing fits (`docs/research/2026-11-19-core-feasibility.md`) split end-to-end time
on the qualification workload into about 41% attention and 40% matrix weight streaming.
Attention is compute-bound. Each pass over the on-chip K/V tile costs about 37 cycles per row
and serves P=2 tokens; that P was set in v9d. A model of the same fits predicts 1.22x end to
end for P=4.

A place-and-route trial of P=4 (`build/v2/core-feasibility/p4`) met timing at 125/250 MHz
(WNS +0.463 ns), with CLB occupancy at 99.3%.

## Change (v9f → candidate)

`experiments/attention_p4/qwen_decoder.cpp` is v9f with two changes:
- `P=4`;
- the carried per-slot attention state is indexed `[slot/P][slot%P]` and held in LUTRAM.

The second change is storage only. Each token keeps its own causal row count, max, sum and
accumulator, so v9d's design claims its per-token operations and order do not depend on P.
This audit tests that claim.

## Method

`testbench.cpp` is the schedule-invariance testbench with two additions: a dump of the
prefill8 record, and a switch to run only that schedule. It drives the kernel through all
28 layers on the first 24 ids of the v3 real command prompt. It uses the full pinned GGUF and
the v9e RoPE table. The K/V cache is filled with BF16 NaN before each schedule.

1. **Cross-kernel.** v9f (P=2, `run_v9f.tcl`) and P=4 (`run_p4.tcl`) each run prefill8 and
   dump:
   - the hidden state of every position after every layer (28 x 24 x 1024 words);
   - all K/V rows;
   - the final norm;
   - the first-8192-row winner token and its logit bits.

   The two dumps are compared word by word as raw 32-bit patterns.
2. **Schedules within P=4.** The mixed, rollback (wrong draft tails) and decode schedules each
   equal prefill8 on all four record types.
3. **Long context.** The v9e release testbench (`hls/qwen_decoder_v9f/testbench.cpp`) runs on
   the P=4 source: the block fixture, and the 2048-position long fixture, which crosses eight
   256-row attention tiles at layer 0. Both must report worst error 0, as v9e and v9f do.

## Decision rule

- **PASS:** 0 differing words in item 1, 0 differing words for all three schedules in item 2,
  and worst error 0 for both fixtures in item 3.
- **FAIL:** anything else. Report the first difference.

PASS allows a pre-registered board pilot of v9f+P4. That pilot would follow the v9f pilot
protocol, with the same exactness rules against the v9e records and a new speed threshold
set from this model.

## Limits

- C simulation of the HLS source, not the routed netlist or the board.
- One prompt and 24 positions for items 1 and 2. Tile crossing is covered by item 3 at layer 0
  only.
