# Quantized model capability comparison

Profile: 4,096 total tokens, 1,024 output tokens including any reasoning, thinking disabled, greedy full-vocabulary decoding, no grammar/semantic repair. Pretrained checkpoints; no task fine-tuning. Maintenance uses two fixed training demonstrations. General tool use uses a balanced public BFCL sample plus simulator-only dependent-action episodes. This is software inference; no FPGA performance is measured.

Runtime: Pinned b11540 Vulkan runtime, requested full GPU layer offload on Radeon780M. Backend arithmetic is not FPGA arithmetic. All primary candidates use this same runtime/configuration.

| Model | File GiB | Fresh screen /12 | Conditional screen /8 | BFCL screen /10 | Two-turn episodes /2 |
|---|---:|---:|---:|---:|---:|
| qwen06-q4 | 0.356 | 2 | 0 | 9 | 0 |
| qwen17-q4 | 0.984 | 2 | 0 | 9 | 1 |
| qwen35-2-q4 | 1.131 | 3 | 0 | 8 | 2 |
| qwen35-4-q4 | 2.406 | 5 | 0 | 7 | 2 |

## Finalist confirmation

| Model | Fresh /120 | Conditional /64 | BFCL /200 | Two-turn episodes /12 | Wrong accepted maintenance plans | Context rejections |
|---|---:|---:|---:|---:|---:|---:|

## Interpretation limits

- Software quantized-weight capability screen, not FPGA arithmetic or target latency.
- Public BFCL and previously inspected template-derived maintenance development evidence.
- Two fixed maintenance training demonstrations added after initial zero-shot codec failures; initial attempts retained.
- Prompt route selected on 22 development records; model selection uses screening data.
- Confirmation includes repeated screen cases; neither is an independent blinded test.
- Output/context sensitivity counts are retrospective capacity accounting, not separate inference at every setting.
- Software requests ran four-way concurrently; wall times include contention and are not FPGA performance estimates.

Re-scored 128 saved task records; scorer discrepancies: 0. Detailed category, operator, validity, capacity and latency counts are in independent-rescore.json.
