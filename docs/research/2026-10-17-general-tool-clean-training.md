# General function calling: clean-data development experiment

Both models restart from their pinned official checkpoints. This is a finite CPU
development experiment, with no board access, paid compute or family winner.

| Model | Selected checkpoint | Selection correct | Audit correct | Correct accepted / accepted |
|---|---|---:|---:|---:|
| encoder | epoch1 | 5/20 | 12/72 | 4 / 41 |
| functiongemma | epoch1 | 14/20 | 55/72 | 47 / 62 |

Initial selection scores were 0/20 for the encoder's fresh heads and 9/20 for
official FunctionGemma. Both retained epoch 1 after epoch 2 tied. These selection
improvements are not paired evidence of improvement on the later audit.

The encoder starts with new random extraction heads. FunctionGemma already has
function-calling instruction training; initializations and representational
limits differ. Both update their final two transformer blocks for two epochs on
the same 512 original xLAM records plus 64 explicit no-action requests. They have
different learning rates and training jobs; this is not equal-compute training.
Encoder heads use a higher learning rate. Maximums are eight tools and four calls;
encoder passes allow 256 tokens, while generator context/output allow 2048/256.
The encoder remains extractive: values requiring rewriting can be unrepresentable.
The clean source split is general-tool-data-v1: xLAM revision
26d14ebfe18b1f7b524bd39b404b50af5dc97866 and BFCL revision
6ea57973c7a6097fd7c5915698c54c17c5b1b6c8. Five exact normalized BFCL prompts were
excluded before splitting. Train/development share no exact normalized prompts
or complete schema sets; individual tools and paraphrases can overlap. Both
datasets are public, and overlap with official model pretraining is unknown.

Twenty development requests select checkpoints, including four synthetic denials.
Promotion requires strictly more complete correct responses, at least as many
correct accepted commands, and no higher observed accepted error; ties retain
the earlier checkpoint. The separate 72-request development audit contains 64
original requests and eight synthetic denials, with different denial wording.
Audit originals start at shuffled development offset 80 and are disjoint from
the selection set and earlier diagnostic audit. It is not a blind or independent
external test. Checkpoint choice precedes the audit; results must not be used to
claim a family winner. BFCL did not affect training or checkpoint selection.
Selection and audit have no exact normalized prompt overlap, but share four
complete-schema/connected components. This is record-disjoint development
evaluation, not a schema-held-out test. The successor partition helper excludes
all previously inspected prefix components for its future audit.

Complete call multisets are scored with typed JSON arguments and multiplicity;
call order is ignored, and int/float equivalence applies only to number schemas.
All issued audit requests remain in denominators, including reference/profile
failures. A text refusal is nonactionable, not evidence of a correct clarification.
No tools are executed. Timing includes failures and overlapped CPU workloads;
it does not establish A53 performance, a deadline bound, energy or board speedup.

The first clean-training attempt (v2) was stopped after detecting unsupported
Python-style annotations in 207 of 576 training records. Its journals and partial
checkpoints remain diagnostic artifacts; no final audit is claimed. The v3
adapter recognizes optional scalar and nested List annotations without evaluating
expressions, coercing reference values or turning unknown types into any. Optional
means omission is permitted, not nullable. Tuples, unions, callables and other
unsupported declarations remain unsupported. Declared defaults are preserved.
The adapter reduces training reference-validation failures from 218 to 27; two
additional encoder jobs exceed its token limit. Detailed effective training
counts, failures, selection history and audit strata are in comparison.json.

An additional target audit found 37 of 1,115 encoder span labels did not decode
to the exact typed reference, all due to case differences. The reported encoder
weights were trained with those labels and remain diagnostic. A successor target
builder repairs those 37 targets: 31 find an exact alternate span and six become
unrepresentable. All 1,109 corrected span targets pass an actual decoder round
trip. These corrected targets are prepared for future training; the reported
models and predictions were not changed. Future training must use
general_encoder_targets.prepare_checked_jobs and general_call_matching.exact_calls.
The final verifier rechecks every selection and audit verdict with the latter,
which avoids lossy conversion of large integers to float; no cached verdict
is silently carried into the report.
The prepared successor runner is train_general_comparison_v4.py. It uses these
checked labels and matcher, with audit offset 144 by default and all earlier
prefix components excluded from its audit. It has not been
trained in this continuation; v3 weights must not be described as label-corrected.

Previous pilot sources, checkpoints and artifacts retain their original hashes.
The existing calibrated MiniLM/R5/PL deployment is untouched. The stronger-encoder
H768 ABI and FunctionGemma PL path remain unqualified; these host results must
not be deployed using the current H384 firmware/module ABI.

Next work remains adequate training and development calibration, the declared
full external evaluation and new human tests, followed by quantization and
separate qualification of both R5-controlled FPGA paths with Linux running.

Always rejecting scores 8/72 on the same audit, with zero correct accepted commands.

The separate frozen-checkpoint BFCL pilot repeats the same 25 public cases used
in the earlier pilot, after eight saved-audit predictions per model pass adapter
parity. It uses the pinned upstream checker, retains all failures, and does not
select checkpoints. This is not the full 1,240-request external evaluation or a
blind test. The larger encoder per-pass token budget also differs from the old
128-token pilot.

| Model | BFCL complete correct | Correct accepted / accepted |
|---|---:|---:|
| encoder | 3/25 | 0 / 9 |
| functiongemma | 8/25 | 6 / 18 |

The earlier official FunctionGemma FP32 pilot scored 11/25 on these same public
case IDs. Its reference remains preserved. The current tuned 8/25 provides no
evidence of improved external capability despite its stronger xLAM development
score. Adapter versions differ, so the historical baseline is not a matched new
rerun. Retain the official checkpoint and investigate transfer before deployment.
