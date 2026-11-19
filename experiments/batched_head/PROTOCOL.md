# v9f batched vocabulary head: exactness audit (C simulation)

Written 2026-11-18, before the first run.

## Why

Speculative verification (RC1.1) runs one batched decoder pass over up to eight
positions. It then scores the vocabulary head once per kept lane, using cmd 9 (copy
the lane to slot 0), cmd 3 (final norm) and 19 cmd 4 chunks. Each scan streams the full
165 MB head. Across the 179 qualification cases with timing data, the head was 19-35% of
decode time.

v9f adds two commands to the v9e kernel. The decoder layers, cmd 3 and cmd 4 are
otherwise unchanged.

- **cmd 11:** final norm for slots `0..rows-1` (v9e: slot 0 only).
- **cmd 12:** one head chunk for slots `0..layer-1` in a single weight pass. It keeps one
  running argmax per slot and writes slot `b`'s (token, logit) word at `result + 32*b`.

The 8-slot Q8 multiply array that the batched decoder already uses serves the head as
well. The only new hardware is a per-slot compare in the row reducer.

A replay of the qualification command timings predicts that the decode speedup over plain
decoding rises from 1.55 to about 1.91 (aggregate over 179 cases). That figure assumes one
head scan per verify pass, at the cost of a single-slot scan. The board measures the real
gain later, under its own protocol.

## Question

Does cmd 11 + cmd 12 give, for every slot, the same winning token and the same logit bit
pattern as the v9e sequential path (cmd 9 for that slot, cmd 3, cmd 4) over the full
151,936-row vocabulary?

## Method

`testbench.cpp` drives `qwen_decoder()` from `hls/qwen_decoder_v9f/` in Vitis HLS C
simulation. It uses:
- the full pinned Qwen3-0.6B Q8_0 GGUF, with an identity page table;
- the v9e RoPE table;
- the schedule-invariance metadata: the first 24 ids of the v3 real command prompt, plus
  24 distinct wrong ids.

Groups go through cmd 7/8 over all 28 layers:

| Group | Position | Tokens | Purpose |
|---|---|---|---|
| G1 | 0 | real 0-7 | full batch |
| G2 | 8 | real 8-9, then 6 wrong | verify pass with rejected tail (rollback) |
| G3 | 10 | real 10-17 | full batch after rollback |
| G4 | 18 | real 18-22 | partial batch (5 slots) |
| G5 | 23 | real 23 | one slot through the batch path (cmd 12 with layer=1) |

After each group, the batched path runs first: cmd 11 with rows=count, then 19 cmd 12
chunks with layer=count. Its per-slot words are read before anything else runs. Then the
v9e reference runs for each slot `s`: cmd 9 (if s>0), cmd 3, then 19 cmd 4 chunks. Every
cmd 12 lane is compared with its reference as raw 32-bit token and logit patterns. That
gives 30 lanes, each over the full vocabulary.

The reference also runs cmd 4 over the first 8,192 rows for each real position (0-23).
Its winners must equal `baseline_tokens` from the v9e schedule-invariance audit
(`build/v2/schedule-invariance-audit/results.json`). That checks the decoder and cmd 4 path
against the v9e source.

A synthetic reducer test feeds crafted partial sums to the v9f row reducer directly:
equal maxima within and across slots, +0/-0, and a slot count below eight. It checks each
slot's winner against a scalar model of the v9e slot-0 rule (larger sum wins; on equal
sums the lower row wins).

## Decision rule

- **PASS:** all of the following hold.
  - All 30 lanes have equal token and logit bits.
  - All 24 8,192-row winners equal the v9e baseline.
  - The synthetic reducer test matches.
  - No kernel status error occurs.
- **FAIL:** anything else. Report the first differing group and slot.

PASS allows HLS synthesis and implementation of v9f. Deployment needs routed timing
closure and a separate board protocol. That protocol covers the host change: one cmd
11 + cmd 12 sequence per verify pass instead of a cmd 9/3/4 scan per kept lane.

## Limits fixed in advance

- C simulation of the HLS source, not the routed bitstream or the board.
- One prompt, 30 lanes, positions below 256 (attention tiling is unchanged from v9e).
- The decoder layers are unchanged in source, apart from the reducer's argmax state
  becoming per-slot. Their bit-exactness against v9e is checked only through the 24
  8,192-row winners and the 30 full-vocabulary lane comparisons.
