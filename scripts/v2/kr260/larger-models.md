# KR260 larger-model work (2026-10-09)

Generation measured on KR260 (2026-10-10): both quantizations complete8 requests.
Medianfirstword Q4 5.138s/Q8 5.046s, about5.3/5.8decode tok/s. No request
meets one second, prefill dominates. Peak server RSS709/941MiB. Negation and
technical-context quality remain inadequate. Review build/v2/eval/kr260-generation-review.md;
computed summary kr260-generation-summary.json. CPU generation baseline works
but is not accepted as the requested assistant; no FPGA generation acceleration.

Generation baseline prepared (2026-10-10): build/v2/kr260-generation.tar.gz
includes pinned llama.cpp source, verified official Qwen3-0.6B Q8, local Q4
requantization, setup and eight-probe streaming benchmark per model. Laptop
non-thinking CPU smoke passes and exposes negation/technical quality limitations.
No KR260 generation result yet. Read scripts/v2/kr260/generation.md for the
single board setup/build/benchmark sequence. Encoder FPGA app is unaffected.

Hardware verified (2026-10-10): KR260 L12 completed350/350 bit-exact frozen
cases; suite/image/token/hidden hashes checked independently. Encoder mean
29.9905ms,max100.672ms versus L6 mean15.1387ms on identical requests. HWU
slot F1 .65882 -> .77108, MSRP accuracy .64 -> .80, multiCLINC .89209 -> .94245;
SICK regressed .82 -> .74. Full summary build/v2/eval/kr260-minilm-l12-summary.json.
No claim that negation or automatic routing is fixed, and no generation capability
added. L12 Nexys has not been tested. This supersedes pending-board notes below.

Package ready (2026-10-10): all six preparation stages finished. Transfer
build/v2/kr260-minilm-l12-v1.tar.gz (33,812,416 bytes); frozen suite350 cases
matched both image variants. L12 physical-board validation remains pending.

Latest (2026-10-10): two training epochs and float/INT8/few-shot evaluation
completed. Baseline and KR260 images compiled, 350 image/reference chains
checked with zero hidden/head mismatches. Preparation stage4/6 is active on
the last HWU test pass for routing calibration. Frozen suite/package still
pending; L12 has not run on either FPGA yet. This supersedes the state below.

Current state: CPU training resumed at the owner's request after the Radeon 780M
test. Python PID23256 is active, UV parent PID22148, preparation waiter PID5184.
Verified external checkpoint epoch1/batch200. Do not launch duplicate training. GPU benchmark
report: build/v2/eval/minilm-l12-gpu-benchmark.md. DirectML works but shows no
clear training gain: short encoder steps slower, long encoder steps about11%
faster, single existing multi-head forward/backward steps slower on GPU.

Owner priorities: both classification/custom intents and generated answers.
Latency goal: first generated words within one second; measure full response time
separately. Retain both Nexys and KR260 baselines. Run batch experiments rather
than requesting one pasted utterance at a time.

## Immediate batch

`build/v2/kr260-smoke-batch.tar.gz` includes run_kr260_smoke.py and the existing
five-label custom-intent examples. On KR260 after extraction:

```sh
cd ~/system-one-fpga
sudo ~/sysone-venv/bin/python scripts/v2/run_kr260_smoke.py
```

Runs 12 automatic routing probes and four custom-intent probes; writes
build/v2/eval/kr260-routing-batch.json and .txt. Review ambiguity, negation,
misrouting, slot errors and custom-intent acceptance. The classifier only emits
intent/slot/embedding results; recognizing electronics_help does not generate
an explanation. Batch stops on client failure and saves completed cases.

## Larger encoder candidate

sentence-transformers/all-MiniLM-L12-v2: 12 layers, hidden 384. Official model:
https://huggingface.co/sentence-transformers/all-MiniLM-L12-v2

Model download added through fetch_models.py and completed. CPU forward passed
with finite output shape [1, 11, 384]; 33,360,000 parameters. Evidence:
build/v2/eval/minilm-l12-preflight.json. Same hidden width is
compatible with the deployed encoder's width limit; the layer program is compiled
from the model's layer count. Verify actual image/request size below the 64 MiB
reservation, instruction support, integer widths and numerical agreement before
claiming deployment compatibility. Deeper weights and new task heads require
fine-tuning and fresh calibration; do not reuse six-layer calibration or relabel
an L6 checkpoint as L12. Avoid --init with the complete L6 state: that overwrites
part of the pretrained L12 encoder. Keep separate names/artifacts.

Train/evaluate with the same task datasets, slot weighting and embedding
teacher objective. Select on development metrics, assess unseen intents and OOS,
compile an INT8 KR260 image, verify reference agreement, then load/read back/check
and evaluate hardware. More parameters do not guarantee better task scores.
Keep the existing L6 checkpoint/image/report as control. Run comparable model
experiments on the same selected requests, not different suite averages.

## Answer generation candidate and first measurement

Qwen3-0.6B is a small causal text-generation candidate with a non-thinking mode:
https://huggingface.co/Qwen/Qwen3-0.6B

It cannot run through the existing bidirectional encoder image format/bitstream.
A causal generation runtime needs per-token decoding and KV state; Qwen also
needs its own attention/position/norm/activation/tokenizer implementation. First
establish a quantized ARM CPU baseline on KR260, using short fixed prompts,
non-thinking mode, constrained context and output length. Record peak RAM,
prompt-prefill time, time to first token, tokens/second, answer correctness and
full completion time. Meeting the one-second first-token goal is unverified.
Do not attribute CPU results to the FPGA. Use trusted electronics documents as
retrieval context to assess grounded answers, separately from intent accuracy.

Only after those measurements choose decoder acceleration work or a larger
model/backend. Remote generation would need an explicit user choice because it
changes the on-board requirement. No paid compute or new hardware is authorized.


Batch completed; review: build/v2/eval/kr260-routing-batch-review.md. L12
training started as minilm-l12-v1 with slot weight4 and distillation10; log:
build/v2/eval/minilm-l12-v1-training.log. Check the running process/checkpoint
before restarting. Fine-tuning, calibration, integer/hardware validation remain
incomplete.


Checkpoint recovery (2026-10-09): original L12 run stopped while replacing
logs/minilm-l12-v1_checkpoint.tmp with .pt (WinError5), before first-epoch
validation. Cause of the file lock is not confirmed. The committed checkpoint
contains epoch0/batch2800; the temporary file loads correctly and contains
batch3000. Copied the newer candidate to
C:/Users/user/AppData/Local/SysoneCheckpoints/minilm-l12-v1_checkpoint.pt,
SHA256 0dd8fa8ecbdefb187f70e63441e4899dbe9d9086f86d27cc3c51889276cc364d,
with both originals preserved. Added --checkpoint-dir and bounded replacement
retries, preserving old/new recovery files if replacement stays locked.
Three focused checkpoint tests pass. Resumed with unchanged hyperparameters
and --checkpoint-dir outside OneDrive. New log:
build/v2/eval/minilm-l12-v1-resume.log; process session50200. Check this log and
the external checkpoint before launching again. Training/export still incomplete.
Recovery audit: build/v2/eval/minilm-l12-checkpoint-recovery.json. Problem28.

