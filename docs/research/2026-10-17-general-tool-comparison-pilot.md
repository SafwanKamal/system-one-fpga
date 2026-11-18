# General tool/function calling: first software pilot

2026-10-17. **Pipeline evidence, not base-model selection or board qualification.**
The user selected general tool/function calling. The earlier maintenance task is
retained only as a diagnostic. Neither candidate is ready for an accepted-command
deployment on the evidence below. No winner is selected.

## Frozen sources and task

Encoder: `google-bert/bert-base-uncased` at
`86b5e0934494bd15c9632b12f734a8a67f723594`. BERT-base was chosen as a concrete
H768/head64 encoder candidate compatible with the existing operator family,
rather than assuming a ModernBERT port. This does not establish better task
quality than MiniLM or the best encoder. Its extraction heads start untrained.
FunctionGemma: `google/functiongemma-270m-it` at
`39eccb091651513a5dfb56892d3714c1b5b8276c`. Both official checkpoints and
tokenizers are downloaded and hashed in the maintenance pilot inventory.

Official xLAM source revision: `26d14ebfe18b1f7b524bd39b404b50af5dc97866`;
BFCL source revision: `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`.
Prepared 1,240 external BFCL requests: 400 simple Python, 200 multiple,
200 parallel, 200 parallel-multiple and 240 irrelevant requests. Five exact
normalized BFCL prompt matches were excluded from the xLAM pool before training.
Public benchmark/pretraining and semantic-paraphrase overlap remain unknown.

The pilot issues five requests per category, seed 20261017, preserving all 25
requests for each variant, errors, proposals, raw generator text, timings and
configuration/checkpoint hashes. No generated API request is executed.
The shared software outcome is Accepted(calls), Clarify, Reject, Deadline or
Fault, with no actionable payload for failures. This JSON representation has
not been integrated into the deployed typed-result ABI.

The local evaluator imports pinned, unmodified upstream BFCL Python checker
functions with a small local model-registry adapter, no provider handlers and
no function-name rewriting. Positive/negative and parallel-call tests pass.
It evaluates whole calls and argument alternatives, including order-independent
parallel matching. This is not a leaderboard submission. Argument F1 is a
separate diagnostic with greedy same-name pairing. BFCL does not validate our
clarification reason, future conditional plans, or deadline contract.

## Observed results

| Variant | Complete correct | Accepted / wrong accepted | Argument F1 | p50 / p95 / p99 ms |
|---|---:|---:|---:|---:|
| BERT extraction FP32 (legacy pilot) | 2/25 | 6 / 6 | 0.047 | 304.1 / 566.5 / 695.3 |
| BERT dynamic INT8 | 3/25 | 2 / 2 | 0.000 | 56.3 / 162.1 / 189.5 |
| BERT FPGA arithmetic, host simulation | 3/25 | 6 / 6 | 0.062 | 769.6 / 2369.9 / 2781.6 |
| FunctionGemma official FP32 | 11/25 | 18 / 11 | 0.677 | 3974.9 / 9829.2 / 10705.9 |
| FunctionGemma 128-record pilot FP32 | 9/25 | 13 / 8 | 0.621 | 3854.3 / 7864.3 / 12317.4 |
| FunctionGemma pilot dynamic INT8 | 5/25 | 3 / 3 | 0.113 | 3229.7 / 14387.4 / 16676.2 |

An always-reject baseline is 5/25 on this balanced pilot. The encoder has zero
correct accepted calls; its correct cases are nonactionable irrelevant outcomes.
The dynamic-INT8 generator also has zero correct accepted calls. Parser validity
and typed refusal do not establish command understanding. Fine-tuning 128 records
did not improve FunctionGemma over its untouched checkpoint here.

These are small, deliberately incomplete software pilots. Both receive the same
128 issued xLAM records and tool catalog, but their adaptation budgets and views
differ. BERT trains the final two blocks plus count/kind/span heads for two epochs:
186 updates, 181.0 seconds,
737 prepared jobs and 38 preserved input-profile
failures. FunctionGemma trains its final block for one epoch: 128
updates, 86.5 seconds. The generator already has
function-calling pretraining; BERT has no pretrained QA head in this pilot.
These budgets cannot support a family-level capability conclusion.

The recorded encoder is an extractive prototype: at most two calls per tool,
four total, eight tools, and 128 tokens per schema-conditioned pass. It reads a
tool description and parameter signatures for count prediction and a selected
parameter description for extraction. It cannot freely rewrite arbitrary
argument strings; 96 training
argument targets were labeled unrepresentable. The generator receives the full
schema, permits four calls, uses a 2,048-token software profile and 256 output
tokens, with dense 262,144-row vocabulary projection. **These pilot profiles
are not the final matched-capability experiment.** The latest encoder source
supports four calls per tool for new training and retains legacy checkpoint caps.

CPU dynamic INT8 quantizes Linear operators; embeddings and the generator
vocabulary head remain FP32. It is not the FPGA integer format or a W4 image.
The full comparison JSON includes Wilson intervals, p50/p95/p99 prefill/decode,
whole-process memory observations, startup load timings and every denominator.
The reported load timer excludes Python/framework import and is not cold process
startup. Some runs overlapped on the host. Timings include early failures and
cannot support a matched-quality speedup. No A53 measurement, measured energy,
successful-inference WCET, or on-board comparison has been obtained.

## Integer-path progress, kept offline

Reused existing FloatEncoder, IntEncoder, image compiler and ImageMachine.
Paired token-type embeddings would be lost by the current constant-type0
embedding path. The adapter explicitly folds type1-type0 into a second bank of
word rows: `hardware_id = tokenizer_id + token_type_id * 30522`.
The derived vocabulary is 61,044 rows and fits uint16 IDs. This is a derived
layout with its own hashes, not an unchanged official checkpoint file.

Two float fixtures match the original paired Torch encoder within
1.24e-05
maximum absolute hidden error (declared tolerance 0.001). Two packed-image
fixtures exactly match 132,096
hidden codes and 370
integer logits against the integer reference. This narrow check does not qualify
all shapes or real hardware. CLS count/kind and per-token span heads are retained.

The general-task candidate image is 132,817,920 bytes,
SHA256 `d64801f880316a12c788db98056cd44e3251c91db834975c008ac4f10fc9dd89`. Its proposed token IDs, hidden output
and mailbox are 0x67eb0000,
0x67ec0000, 0x67ee0000.
The proposal fits 256 MiB but overlaps the current fixed-buffer layout.
It must never be loaded with the deployed H384 firmware/module/client ABI.
No hardware image, model, firmware or clock was changed.

FunctionGemma still needs head256 attention, 32-bit token IDs, causal/KV state,
its normalization/gating and vocabulary projection implementation plus a
qualified numerical/resource layout. R5 must remain in control in the production
PL path, with Linux running. A later A53-only run must be labeled separately.

## Corrected data for the next training run

The original whole-schema-set split had 170 exact normalized train/dev prompt
overlaps, 180 train/diagnostic and 46 dev/diagnostic. Those development files
were never used to fit or select the current pilot. They are preserved.
The corrected data at `build/v2/general-tool-data-v1` groups connected components
sharing an exact normalized prompt OR an identical complete tool-schema set.
Its counts are 42,197 train,
5,120 dev and
12,678 diagnostic, with zero
cross-split exact prompt and full-schema-set overlaps. Individual tool identities
and semantic paraphrases can still overlap; this is not an independent human
blind test. Split sizes follow components, not exact 80/10/10 proportions.

Of the 128 records used by the old pilot, migration is {'train': 113, 'dev': 1, 'schema-heldout-diagnostic': 14}.
**Restart future clean-split training from the original official checkpoints**;
warming from these pilot weights would contaminate some clean dev/diagnostic
records. Do not relabel these old results as clean-split results.

## Continuation

1. Use corrected data, a matched four-call profile and adequate task training.
   Improve encoder value decoding/initialization and generator adaptation on
   development data; keep the original generator as a reference. The resource
   question about CPU versus an existing GPU remains optional; no paid compute
   has been authorized or used.
2. Evaluate the full declared external subset and a separately authored human
   test including negation, missing arguments, corrections and conditional or
   composed requests. Report failures and retained coverage, not intent accuracy.
   Freeze choices before a genuinely blind test; add confidence calibration on
   separate data. The pilot is not grounds to drop either candidate.
3. Qualify actual deployment quantization, not just dynamic CPU INT8. Keep both
   deployment paths as goals, with independently qualified images, R5 control
   and Linux alive. Extend firmware/layouts and decoder operators explicitly.
   Integrate the existing typed deadline/result RTL rather than replacing it.
4. Obtain tuned A53 baselines, board startup/resident distributions, generator
   prefill/decode/full completion and energy only with real instrumentation.
   The existing calibrated MiniLM regression artifacts remain preserved; no new
   MiniLM regression or board state check was performed in this session.

Earlier maintenance artifacts, a failed 28-section image compile, the corrected
combined-head compile, the generator end-of-turn stopping error and superseded
CPU preparations are retained. The long maintenance-specific generator run was
stopped after the user chose general calling, with its completed-step journal
preserved. All finite final pilot variants above are complete. No board commands,
JTAG tools, power cycles, commit, push, recurring automation or paid compute were used.

Sources: [official FunctionGemma](https://huggingface.co/google/functiongemma-270m-it),
[official BERT](https://huggingface.co/google-bert/bert-base-uncased),
[official xLAM dataset](https://huggingface.co/datasets/Salesforce/xlam-function-calling-60k),
[pinned BFCL source](https://github.com/ShishirPatil/gorilla/tree/6ea57973c7a6097fd7c5915698c54c17c5b1b6c8/berkeley-function-call-leaderboard).
