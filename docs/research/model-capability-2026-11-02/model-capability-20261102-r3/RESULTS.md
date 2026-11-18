# Quantized model capability comparison

Profile: 2,048 total tokens, 256 output tokens including any reasoning, thinking disabled, greedy full-vocabulary decoding, no grammar/semantic repair. Pretrained checkpoints; no task fine-tuning. Maintenance uses two fixed training demonstrations. General tool use uses a balanced public BFCL sample plus simulator-only dependent-action episodes. This is software inference; no FPGA performance is measured.

Runtime: Pinned b11540 Vulkan runtime, requested full GPU layer offload on Radeon780M. Backend arithmetic is not FPGA arithmetic. All primary candidates use this same runtime/configuration.

| Model | File GiB | Fresh screen /24 | Conditional screen /24 | BFCL screen /50 | Two-turn episodes /6 |
|---|---:|---:|---:|---:|---:|
| qwen06-q4 | 0.356 | 2 | 0 | 33 | 4 |
| qwen17-q4 | 0.984 | 4 | 0 | 44 | 6 |
| qwen4-q4 | 2.213 | 6 | 1 | 42 | 4 |
| qwen35-2-q4 | 1.131 | 3 | 3 | 30 | 6 |
| qwen35-4-q4 | 2.406 | 7 | 0 | 31 | 6 |
| xlam3-q4 | 1.698 | 3 | 2 | 43 | 4 |
| lfm12-q4 | 0.648 | 0 | 0 | 34 | 6 |
| smol3-q4 | 1.687 | 3 | 4 | 19 | 1 |

## Finalist confirmation

| Model | Fresh /120 | Conditional /64 | BFCL /200 | Two-turn episodes /12 | Wrong accepted maintenance plans | Context rejections |
|---|---:|---:|---:|---:|---:|---:|
| qwen17-q4 | 15 | 0 | 172 | 9 | 67 | 0 |
| qwen4-q4 | 32 | 4 | 170 | 4 | 36 | 0 |

## Interpretation limits

- Software quantized-weight capability screen, not FPGA arithmetic or target latency.
- Public BFCL and previously inspected template-derived maintenance development evidence.
- Two fixed maintenance training demonstrations added after initial zero-shot codec failures; initial attempts retained.
- Prompt route selected on 22 development records; model selection uses screening data.
- Confirmation includes repeated screen cases; neither is an independent blinded test.
- Output/context sensitivity counts are retrospective capacity accounting, not separate inference at every setting.
- Software requests ran four-way concurrently; wall times include contention and are not FPGA performance estimates.

Re-scored 1624 saved task records; scorer discrepancies: 0. Detailed category, operator, validity, capacity and latency counts are in independent-rescore.json.
