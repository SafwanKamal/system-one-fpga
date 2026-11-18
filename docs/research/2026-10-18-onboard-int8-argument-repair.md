# Onboard INT8 argument repair — 2026-10-18

The same engineering command now produces the correct call proposal on the KR260:

```json
{"name":"songs_v2_get_details","arguments":{"is_id":"45077244","l":"en-US"}}
```

R5 controlled three H768 FPGA encoder passes and computed the integer classifier
logits. Linux used the existing token/span decoder to reconstruct arguments.
There was no host FP32 model, correction pass, cached answer or special-case
language rule in this physical run. No external API/tool was executed.
Evidence: build/v2/general-tool-int8-board-v4/result.json and
results/03-verify-restored/stdout. The receipt binds the request, candidate image
and R5 firmware. The actual hardware proposal equals the CPU integer-image
reference on this one command. This is engineering fixture success, not a
benchmark/generalization or deadline qualification.

## What fixed it

The original encoder accumulates quantization error: final hidden cosine against
float is about 0.452 on the problematic argument. A training-derived scalar
attention compensation and then span-head-only adaptation both failed this same
fixture and were not promoted. Softmax reciprocal truncation contributes loss of
mass but was not sufficient to explain/repair the whole drift.

The successful candidate adapts only encoder blocks 10 and 11 and the span head
with quantization-aware training. Embeddings and blocks 0–9 remain byte-identical
to the sealed original image; meta-head weights remain unchanged. The original
activation scales, image layout and operator ABI are retained. Training simulates
INT8 per-channel weights/activations, INT16 residuals, fixed-point softmax,
LayerNorm rounding and GELU lookup. Final qualification uses the actual exported
integer-image interpreter and actual FPGA/R5 execution, not the training surrogate.

A fixed 128 saved training jobs were used: 64 spans copied from schema metadata
and 64 copied from the query, first qualifying unique record per stratum.
The engineering fixture xlam_48473 is absent from training. Features were
collected with the frozen encoder on the board; one complete DDR feature frame
matched the integer reference exactly. A separate early-END image captured
block-9 outputs. Both collection windows restored and verified MiniLM.
Training was three epochs / 96 updates, batch four, encoder LR 5e-5 and span
LR 5e-4, seed 20261018. A small CLS preservation term limits call-selection drift.
There was no checkpoint selection or benchmark sweep. Original float runtime and
prior sealed sources were not modified.

Candidate: build/v2/general-tool-int8-mvp-v3/qat-bundle.
Checkpoint: qat-last2.pt. Candidate image SHA256:
f96d65f5bfb6996fdbe96dda05d32b4d220b1359a3554cf0fa3e19d67cf0ea0c.
Original matching R5 ELF SHA256:
943478a490f8bcd04937e163600ab0b1b1a18e8ab364f571a25d95dcc93f19bb.
Only a 13.1MB compressed patch was uploaded into a fresh staged candidate. The
full local image and its manifest are saved for reproducibility.

## Restoration and staging note

Final restoration independently verified every MiniLM image byte and original
R5 firmware identity. Linux boot ID remained
6c80ec1a-e7ae-473f-b169-d54f129615d1. FPGA state operating, clock 199999998 Hz.
R5 pinned/reserved/mapped/may_run/quarantine are zero and leases are zero.
SSH closed and no credential was saved. No JTAG, PL programming, reboot,
dashboard change, permanent deployment, paid compute or commit/push occurred.

One staging job failed after applying and SHA-verifying the patch because system
Python lacked numpy. No board switch occurred in that job. After resume the
bring-up ran under the target venv, independently verified the candidate SHA,
and completed inference/restoration successfully. The proposed additional CRC
repair job was never executed because the runner resumed its already enumerated
queue and closed after success; it is retained under cancelled/, not active queue.
Local export verifies all CRCs, and remote candidate bytes match that exact SHA.
All failures and receipts are retained.

The calibrated MiniLM system remains deployed. This candidate now has one
correct hardware call proposal; broader capability and external tool dispatch
are not established by this result. No host FP32 correction is required for the
successful candidate request.
