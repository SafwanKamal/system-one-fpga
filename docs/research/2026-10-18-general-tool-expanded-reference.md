# Expanded general function-calling reference and offline port foundations

Finite CPU work only. Both models' FPGA ports, base-family selection and the
typed terminal-by-D contract remain unfinished. No board changes or paid compute.

| Variant | BFCL complete correct | Correct accepted / accepted | Wrong accepted |
|---|---:|---:|---:|
| encoder | 165/1240 | 19 / 423 | 404 |
| functiongemma_official | 654/1240 | 482 / 836 | 354 |

Always-Reject scores 240/1240, with zero correct accepted commands. Results
use the pinned BFCL Python checker and all 1,240 declared requests: 400 simple,
200 multiple, 200 parallel, 200 parallel-multiple and 240 irrelevance. Every
completed failure remains in the denominator. The finalizer rescores all rows.
Correct refusals contribute to the overall score; correct accepted calls and
wrong accepted calls are reported separately above.

| Category | Encoder correct | Official FunctionGemma correct |
|---|---:|---:|
| simple_python | 13/400 | 250/400 |
| multiple | 3/200 | 115/200 |
| parallel | 0/200 | 67/200 |
| parallel_multiple | 3/200 | 50/200 |
| irrelevance | 146/240 | 172/240 |

These are public datasets, not a blind test or leaderboard submission; overlap
with official model pretraining is unknown. Five exact BFCL prompt overlaps
were removed from xLAM before the clean training/development split.

The encoder restarts pinned BERT-base with corrected extraction targets, using
2,048 xLAM originals plus 256 synthetic denials for two epochs. Both final
transformer blocks and the new heads train. All 4248
span targets round-trip exactly; 122 targets needed correction.
Reference/profile failures are preserved in preparation and effective counts.
Twenty development requests select the checkpoint; a separate 72-request audit
excludes every schema/prompt component in the previously inspected development
prefix. There is no cross-split exact prompt or component overlap. Individual
tools/paraphrases can still overlap. Encoder selection is
6/20 and the separate audit is 19/72.
The encoder remains an extractive prototype, including unrepresentable values.

FunctionGemma here is the original official FP32 checkpoint, with no adaptation
weights loaded. This is not equal task training, compute, representations or
context exposure: encoder passes allow 256 tokens versus generator 2048 context
and 256 output tokens, with at most 8 tools and 4 calls. No family winner follows.
The v3 tuned generator is preserved; its full-scope evaluation remains pending.

The reference preserves 527 completed single-request results exactly and evaluates
the remaining 713 in length-bucketed batches of 4. All 25 historical official
outputs/calls/validity/errors reproduced literally during batch qualification
(11/25 correct). One administrative in-flight interruption, parallel_67, was
recorded separately and reissued; no completed failure was retried. There are
1,240 completed case results and 1,241 attempts including that interruption.
The complete interrupted trace and lineage remain available. Runtime batching
is declared; combined latency is not compared with single-request latency.
CPU work overlapped; no A53 speed, energy, DDR bound or WCET result is claimed.

The offline FunctionGemma float reference covers explicit head width 256,
GQA 4:1, local/global RoPE, Gemma 1+weight RMS, gated tanh-GELU, all 18 blocks and
shared embedding/full 262,144-row vocabulary projection. Six real-weight block
fixtures pass predeclared atol 0.001/rtol 0.0001, including the 512-token window
boundary and position 8192. The whole decoder matches all 17 greedy
tokens through the function-response marker on one authored fixture. Maximum
logit absolute error is 0.000155263; this is one-fixture
numerical evidence, not general task accuracy or integer/RTL qualification.

Host integer RMS primitives pass 24 official-coefficient fixtures within one
output code; four attention fixtures preserve masked long rows within one
context output code. Q16 probabilities preserve a uniform 2,048-key row that
Q8 would round to zeros. Synthetic arithmetic scales are not task calibration.
6/7/8-bit candidate tile codecs preserve supplied integer codes for embedding
lookup and projection; nine real-weight packing fixtures pass. This proves
packing, not the quality of quantizing weights to those widths.

The new isolated packed_weight_row16 RTL unpacks 16 signed codes from a row into
INT8 lanes with one elastic register. All 3,988 simulated rows pass across
6/7/8-bit configurations, including every representable code, checkpoint-derived
samples, tile padding/boundaries, unused high bits, stalls, reset flushing and
back-to-back transfers. Isolated Vivado synthesis completed for all three widths
on xck26-sfvc784-2LV-c. This is offline FPGA implementation work: it is not
connected to the executor, DDR fetch, dot product or R5 ABI, and is not routed,
timing-qualified or tested on the board. Simulation does not establish the
quality of weight quantization.
Synthesis uses 3, 3, 3 LUTs and
97, 113, 129 registers for 6/7/8 bits respectively.

Uniform INT8 weights alone occupy 268,098,176 bytes, leaving 337,280 bytes in the
current 256MiB region; an INT8 KV cache adds 7,070,208 bytes. The conditional ledger
also includes norm/scale records, rotary tables, decoder pieces, scratch and
firmware/mailbox/header assumptions. Its totals are:

| Shared embedding/projection width | Estimated total bytes | Margin in 256MiB |
|---|---:|---:|
| 8 bits; other matrices 8 | 288,740,494 | -20,305,038 |
| 7 bits; other matrices 8 | 267,768,974 | 666,482 |
| 6 bits; other matrices 8 | 246,797,454 | 21,638,002 |

These are estimates, not allocated executable images. In particular, the 7-bit
option's margin is small; INT16 KV, additional padding/storage or a different
scratch schedule can exceed it. The 6-bit option has more margin but unmeasured
whole-model accuracy. No bit width has been selected. Existing UINT16 token
transport is incompatible with the model vocabulary; proposed storage is 32-bit,
with an embedding-range check. Added tokenizer image IDs 262144/262145 lack text
embeddings and must be rejected. All 1,240 declared text requests passed input
preflight; none was filtered on that basis.

No deployed image, R5 firmware, module, reserved-memory layout or dashboard was
changed. The new helpers are offline references. DDR fetch/unpacker integration, integer rotary
and gated activation integration, whole-model quantization/calibration, R5
token-piece decoding, typed-call payload validation and compiler/module ABI
still need implementation and qualification. Preserve the calibrated MiniLM
deployment. Reuse existing publication-gate work, but finite-label schemas and
128-token timing admission do not silently authorize this general-call profile.
A terminal record by D is distinct from successful inference and Linux delivery.
All 49 relevant local tests passed. Prior sealed artifacts were hash-verified
unchanged, and the new run/report/source artifacts have a separate seal.
