# Where the remaining time goes on v9f, and two bit-exact levers (2026-11-19)

## Measured cost model

Linear fits to the v9f board pilot's per-case command timings (181 cases,
`build/v2/batched-head-board/pilot.json`). Times are per layer:

| Command | Fit | R² |
|---|---|---|
| single-token step (cmd 2) | 4.49 ms + 3.41 µs × position | 0.9999 |
| batched pass of k tokens (cmd 8) | 4.37 + 0.18 k ms + (1.88 + 1.08 k) µs × position | 0.9998 |
| prefill group of 8 (cmd 8) | 5.93 ms + 10.46 µs × position | 1.0000 |

Summed over the workload (prefill plus speculative decode), the model gives 4,325 s against
4,335 s measured. The split:

| Part | Share |
|---|---|
| attention (grows with position) | 41.5% |
| matrix weight streaming | 40.0% |
| fixed per-layer vector work | 14.1% |
| head | 2.8% |
| per-lane | 1.6% |

Prefill is 78% of the workload's time because the qualification measures cold prompts. The
service's prefix reuse removes part of that.

**Matrix.** 491,520 Q8 blocks per layer stream at 16 blocks per 17 cycles at 125 MHz, which
is 4.18 ms. The weight path is 4 GB/s: the 256-bit m_axi port at 125 MHz feeds HP0, which is
128-bit at 250 MHz. The head scan reaches 3.85 GB/s. The matrix core is bound by the port
and by its one-block-per-cycle accumulator, which are matched.

**Attention.** This is compute-bound, not K/V-read-bound. Per KV head and cached row, one
pass costs:
- 16 cycles of scoring (one 8-wide chunk per cycle);
- about 1 cycle of scaling;
- about 4 cycles of exp and mass sum (a carried FP add);
- 16 cycles of value accumulation;
- plus 16 cycles per row per head to load the K/V tile.

A pass serves P=2 tokens. Cost per position per layer is therefore
8 × (16 + 37 × ceil(k/P)) cycles. That predicts:
- 10.5 µs for prefill (fit: 10.46);
- 3.4 µs for a single step (fit: 3.41).

## Levers and modelled end-to-end gains

Both levers are bit-exact by construction: per-token and per-row operation order is unchanged.

| Design | Gain | Resource evidence |
|---|---|---|
| Attention P=4 (4 tokens per K/V pass) | 1.22x | Routed trial: WNS +0.463 ns. LUT 97.8k (83.5%), CLB 99.3%, BRAM 113, DSP 749 |
| Dual weight port: rows split across HP0/HP1 and two accumulators | 1.27x | Not built. The accumulator is the largest block (HLS: 226 DSP, 18k LUT, 73k FF) |
| P=4 + dual port | 1.65x | Does not fit next to P=4 at 99.3% CLB without reclaiming space |
| P=8 + dual port | 1.95x | Needs a larger device or a resource rework |

P=4 initially failed: HLS split the carried attention state into one 256-bit bank per token
slot, which took 351 BRAM18 against 288 available. Indexing the state `[slot/P][slot%P]` in
LUTRAM fixed it (223 BRAM18 in HLS, 113 tiles routed).

## Status and next steps

1. **P=4 exactness: PASS** (C-sim audit, pre-registered in
   `experiments/attention_p4/PROTOCOL.md`; results below).
2. **Next:** a board pilot of v9f+P4, on the v9f pilot pattern. It needs a full bitstream
   build from the audited source and user approval for the image swap.
3. **Dual port:** needs space first. The candidate is packing two INT8 products into one
   DSP48E2, which is exact and possible because the token lanes share the weight operand. A
   new HP1 path and a second unpacker/accumulator are needed in any case.

## P=4 exactness audit: PASS (2026-11-19)

Candidate source `experiments/attention_p4/qwen_decoder.cpp` (sha256 3649cd0f…), full pinned
GGUF, all 28 layers. Artifacts are in `build/v2/attention-p4-audit/`.

| Item | Check | Result |
|---|---|---|
| 1. Cross-kernel | v9f (P=2) vs P=4 prefill8 dumps, compared as raw words: hidden 688,128, K/V 688,128, norm 24,576, 24 tokens, 24 logits | 0 differing. The dump files are byte-identical (sha256 576653a3…) |
| 2. Schedules within P=4 | mixed, rollback (wrong draft tails) and decode, each vs prefill8 | all three IDENTICAL; `AUDIT RESULT: PASS` |
| 3. Fixtures on the P=4 source | block fixture (8 batch lanes); 2048-position long fixture (8 attention tiles) | worst=0 for both |

Every item meets the pre-registered PASS rule. P=4 changes only how many tokens share each
K/V pass; each token's arithmetic and its order are unchanged, as designed. The limits in
PROTOCOL.md still apply: this is C simulation, not the routed netlist or the board.
