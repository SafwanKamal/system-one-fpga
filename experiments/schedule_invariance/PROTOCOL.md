# Schedule-invariance audit of the v9e decoder (C simulation)

Written 2026-11-16, before the first run. Offline only: no board access, no new
bitstream, no change to `hls/qwen_decoder_v9e/`.

## Question

Does the unmodified v9e kernel produce bit-identical results for a token
position regardless of how the host schedules the work: one token per call,
eight per call, irregular groups, or a batch whose tail is later discarded and
recomputed (the pattern speculative verification would use)?

Existing evidence covers layer 0 only, against a NumPy reference with a 2e-5
tolerance (observed error 0). It does not cover all 28 layers, mixed schedules,
signed zero, or discarded batch tails.

## Method

`testbench.cpp` drives `qwen_decoder()` from the unmodified
`hls/qwen_decoder_v9e/qwen_decoder.cpp` in Vitis HLS C simulation, with the
full pinned Qwen3-0.6B Q8_0 GGUF as the model image (identity page table) and
the v9e RoPE table. It runs the first 24 token ids of the v3 real command
prompt through all 28 layers under four schedules:

| Schedule | Calls |
|---|---|
| S2 `prefill8` (stored baseline) | three 8-token groups |
| S3 `mixed` | groups of 3, 1 (decode path), 8, 1 (batch path), 5, 2, 4 |
| S4 `rollback` | 8; then 8 at position 8 with 6 wrong tail tokens (2 kept); 8 at position 10; 6 at position 18 with 5 wrong tail tokens (1 kept); one decode step at 19; 4 at position 20 |
| S1 `decode` | 24 single-token decode steps |

Before every schedule the whole K/V cache region is filled with BF16 NaN, so a
read of a row that the schedule did not write shows up as a difference. The
kernel's static state is deliberately left over from the previous schedule.

Compared as raw 32-bit patterns (so +0 and -0 differ and NaN is not skipped):

1. the hidden state of every kept position after every layer (28 x 24 x 1024 words);
2. the K/V cache rows of positions 0-23 for all layers and heads at the end;
3. the final-norm output of every kept position;
4. the winning token and logit bits over the first 8,192 vocabulary rows.

## Decision rule

- **Pass:** zero differing words in all four comparisons for S3, S4 and S1 against S2.
- **Fail:** any differing word. Report the first differing schedule, layer and
  position. The follow-on question is then whether a fix costs timing closure.

## Limits fixed in advance

- C simulation of the HLS source, not the routed bitstream or the board.
- 24 positions, so attention never crosses a 256-row tile boundary here; tile
  crossing stays covered at layer 0 only by the existing long fixture.
- One prompt. The head check covers 8,192 of 151,936 rows; the rest of the head
  uses the same lane-0 code path on inputs compared in item 3.
- Greedy selection only; nothing here concerns sampling.
