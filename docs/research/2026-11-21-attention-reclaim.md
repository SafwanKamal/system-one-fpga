# Attention LUT reclaim for the full dual weight port (2026-11-21)

## Summary

- **Only one exact restructuring frees a useful amount of LUT: P=2 attention.** Serving two
  tokens per pass over the on-chip K/V tile instead of four removes 20.5k LUT in HLS from
  attention (48.0k → 27.5k). It also frees 167 DSP and 12 BRAM18. At the usual HLS-to-routed
  ratio of 0.74, that is about 15k LUT routed.
- **Everything that keeps P=4 frees at most 2–4k LUT in HLS, and each option has a blocking cost.**
  - Relaxing the helper loops to II=4 (`aux`) or capping the FP operators (`lim`): ≤ 0.1k.
  - LUTRAM → BRAM (`bram`): −2.0k, but it adds 192 BRAM18. v9h routes 117 of 144 BRAM36, which leaves about
    54 BRAM18.
  - Softmax lanes one per cycle (`tmx`): −1.8k, but a cached row then costs 48 cycles instead of
    36, so attention is 33% slower.
  - All three together: −3.9k.

  The operator pool is set by the score and value loops. The helpers and storage are small.
- **The trade is weak.** The cost model combines P=2 with the full dual port and replays the
  drafter on all 181 cases. It gives **1.065x end to end** over v9h.
  - Tool queries, the live service's workload: **1.31x**.
  - General: 1.16x. Maintenance: 1.11x.
  - Long-context cases: 0.96x.
  - Speculative decode overall: 0.88x, because passes of 3–8 tokens pay twice the attention
    compute.
- **For comparison:** the full dual port with P=4 would be 1.31x end to end, but it does not fit.
  Reclaiming LUT without losing P=4 throughput needs a different mechanism (see Next).

## Where attention's LUTs go (v9h, HLS csynth)

| Category | LUT | Notes |
|---|---|---|
| FP operator instances | 31.9k | 56 fmul (139 LUT, 3 DSP each), 58 fadd (214 LUT, 2 DSP each), 1 fexp, plus loop control |
| Multiplexers | 10.6k | operand selection on the shared pool (score, value, rescale, normalise loops) |
| Expressions | 3.4k | |
| Memory | 2.1k | run_acc / acc / query LUTRAM |
| **Total** | **48.0k** | 54.2k FF, 302 DSP, 24 BRAM18, 8 URAM |

The pool size equals one II=1 iteration of the score or value loop: P tokens × 2 heads × 8 lanes.
fadd `full_dsp` and fmul `max_dsp` are already the lowest-LUT IEEE cores on UltraScale+. The pool
therefore shrinks only if each cycle does less arithmetic.

## Variants (`experiments/attn_reclaim/make_attn.py`, csynth via `hls_attn.py`)

| Variant | Decoder LUT | Attention LUT | Attention FF | Attention DSP | Attention BRAM18 | Mux LUT | fmul / fadd |
|---|---|---|---|---|---|---|---|
| base (v9h) | 132,050 | 47,953 | 54,224 | 302 | 24 | 10,632 | 56 / 58 |
| aux | 131,958 | 47,901 | 55,916 | 302 | 24 | 9,566 | 56 / 58 |
| p2 | 111,517 | 27,499 | 27,795 | 135 | 12 | 5,961 | 24 / 28 |
| p2+aux | 111,429 | 27,451 | 28,719 | 135 | 12 | 5,315 | 24 / 28 |
| p2+aux+lim | 111,463 | 27,471 | 28,719 | 135 | 12 | 5,335 | 24 / 28 |
| aux+lim | 131,964 | 47,907 | 55,916 | 302 | 24 | 9,572 | 56 / 58 |
| bram | 130,002 | 45,905 | 41,934 | 302 | **216** | 10,632 | 56 / 58 |
| tmx | 130,047 | 46,179 | 53,093 | 295 | 24 | 10,139 | 56 / 60 |
| bram+tmx+aux | 127,889 | 44,061 | 42,495 | 295 | **216** | 9,055 | 56 / 60 |

All variants keep the score and value loops at II=1.

- **II warnings.** Most variants have the same 4 II warnings as v9g and v9h, all in pre-existing
  loops. `tmx` variants report 2, because their helper loops now meet the II they request.
- **Operator count.** The score and value loops each schedule P×2×8 multiplies and adds per
  iteration (64 at P=4, checked in the bind reports). The attention instance table lists 8 fewer
  fmul at both P values (56 and 24). I did not find where those 8 are bound. This does not change
  any conclusion: the `lim` cap at P×2×8 is non-binding either way, and it measured no change.

### Measured loop latency (csynth, II and iteration latency per loop)

Per KV head, per pass, per cached row:

| Variant | Score | Scale/max | Exp/mass | Value | Cycles per row per pass |
|---|---|---|---|---|---|
| base, aux, lim, bram, p2 | 16 × II 1 | II 1 | II 3 | 16 × II 1 | 36 |
| tmx (any combination) | 16 × II 1 | II 8 | II 8 | 16 × II 1 | 48 (+33%) |

**Fixed costs per tile and pass** (base / aux):

- query load: 128 / 128 cycles (64 for p2);
- rescale: 16 / 64;
- normalise: 32 / 128 per finishing token.

`aux` adds about 1.2k cycles per layer to a decode step, about 0.2% of the step.

**Pass counts.** P=2 keeps 36 cycles per row but makes ceil(k/2) passes instead of ceil(k/4):

- decode (k = 1): unchanged;
- passes of 3–4 tokens: twice the attention compute;
- prefill groups of 8: twice the attention compute.

The throughput table below prices this with the board-fitted model.

- **Exactness argument.** Each token keeps its own count, max, sum and accumulator, in the same
  operation order. The run state is indexed [slot/P][slot%P]. Only the schedule changes: a pass of
  k tokens makes ceil(k/P) sweeps over the on-chip tile instead of one.
- **Precedent.** P=2 against P=4 was already shown byte-identical in the v9g C-sim audit
  (`2026-11-19-v9g-p4-attention.md`).
- **This build.** The C-sim check is Gemini's harness (`experiments/attn_reclaim/audit/`). Its
  verdicts are added at integration.

## Throughput model (`model_p2.py`, `build/v2/attn-reclaim/claude/model_p2.json`)

**Pass cost.** The model uses the 7-coefficient v9h board fit (median error 0.2%), split into its
two hardware meanings:

- the port-split threshold: 4 tokens on v9h, all passes with the full dual port;
- the attention lane count P.

**Workload.** The RC1.3 drafter is replayed on all 181 cases with each hardware's own costs, so
drafts re-tune to the hardware. Prefill is each prompt after the 32-token cached template, in
groups of 8.

**Decode cost per pass.** Attention compute is 8 heads × 37 cycles × ceil(k/P) per cached row
(`2026-11-19-core-feasibility.md`).

| Hardware | Speculative decode | Prefill | End to end | Tool | Long |
|---|---|---|---|---|---|
| v9h | 1.000x | 1.000x | 1.000x | 1.000x | 1.000x |
| v9h + P=2 | 0.859x | 0.854x | 0.855x | 0.976x | 0.800x |
| full dual port + P=4 (does not fit) | 1.068x | 1.359x | 1.308x | 1.354x | 1.264x |
| **full dual port + P=2** | 0.884x | 1.103x | **1.065x** | **1.310x** | 0.956x |

Plain (non-speculative) decode is unchanged in every row. Single steps use one lane, and v9h
already splits them across both ports.

## Does dual port + P=2 fit?

**Estimate:**

- Out-of-context synthesis of the full dual port gave a 113.9k LUT decoder.
- P=2 saves about 15k routed, so the decoder would be about 99k.
- With the shell, the total is about 107k of 117k (91%).

That is plausible, but v9h already sits at 99.6% CLB. Only a route can confirm it.

## Recommendation and next steps

1. **Don't build dual port + P=2 as the general image.** It gains only 1.065x, and speculative
   decode and long contexts get slower. It is worth building only if the service stays dominated
   by tool queries (modelled 1.31x). That build would be the first route-level test (one Vivado
   run of about 2–3 h), followed by C-sim and a 36-case board check.
2. **The exact lever that keeps P=4 is a narrower multiplier, not a smaller pool.**
   - Every attention multiply is fp32 × bf16. The exact product needs only a 24×8-bit mantissa
     multiply: one DSP48E2 plus normalise and round-to-nearest-even logic. Today's fmul uses
     3 DSP and 139 LUT.
   - The custom core must match the Xilinx core: denormals flushed, and the same rounding.
   - Estimated saving: about 4–5k LUT and about 110 DSP. That is not enough alone, but it adds up
     with the SRL→BRAM FIFOs (2–4k) and the last duplicate RMS instance (about 2k) from the
     dual-port study.
