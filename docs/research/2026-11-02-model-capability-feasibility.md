# Model capability before execution enforcement

Research date: November 2, 2026, America/Chicago. Scope: maintenance planning and general tool use on the existing KR260, with neural model computation on programmable logic and weights in board DDR. Thresholds remain undecided until feasibility measurements. This report contains source research, reproducible tensor/cache budgets and an implementation audit. It contains no new model inference, training, board probe, synthesis, deployment, energy measurement or reliability qualification. The stopped historical full sweep stays stopped.

## Finding

We have not established the most capable deployable model. Qwen3-0.6B is the hardware-demonstrated baseline. The practical region to investigate next is roughly 1–4B parameters with quantized weights; this is a candidate region, not a proven maximum or a capability ranking. Approximately 3–4B at Q4 deserves screening rather than assuming 1.7B is the ceiling. Newer hybrid small models deserve the same capability screen even when porting them would require different kernels.

The board's physical DDR capacity, current driver allocation envelope, supported model operators, physical design capacity, runtime memory, task quality and latency impose different limits. A checkpoint fitting DDR proves only one of them. No published benchmark identifies the best model for our maintenance distribution.

The next decision should choose a small set of nondominated model/precision/context profiles from capability measurements and resource estimates. Then implement and validate the best hardware candidate. Execution-enforcement research is deferred until a useful capability/reliability operating region has been demonstrated.

## Hardware envelope: observed versus estimated

AMD specifies 4 GB DDR4 for K26 and 117,120 LUTs, 144 BRAM tiles, 64 URAM blocks and 1,248 DSP slices. DDR is shared with Linux and runtime storage; it is not 4 GB available for model weights. Sources: [K26 product](https://www.amd.com/en/products/system-on-modules/kria/k26/k26i-industrial.html), [DS987 PL resources](https://docs.amd.com/r/en-US/ds987-k26-som/Programmable-Logic).

Current implementation facts, inspected locally:

- `firmware/qwen_dma_v2/sysone_qwen_dma_v2.c`: 64 segments of 16 MiB, so at most **1 GiB model extent**, and each allocation must end at or below physical `0x80000000`. Historical boot preparation reserved 800 MiB CMA. These are implementation/allocation limits, not a physical 1 GiB board limit. They need live reconciliation before a candidate allocation experiment.
- `hls/qwen_decoder_v9e/qwen_decoder.cpp`: another independent 64-entry model page table. Increasing the driver limit alone does not fix hardware addressing. State/model interfaces and the DDR address assignments also need revision before using additional address windows.
- `model_profile.hpp`: Q8 matrix engine, 128-dimensional heads, eight-token prefill batch and shape constants. The implementation additionally asserts query/KV head ratio at most two. Wider model profiles need new workspace sizing and physical builds.
- v9e routed evidence: LUTs 77,415/117,120 (66.10%); occupied CLBs 14,065/14,640 (96.07%); BRAM 122/144 (84.72%); URAM 40/64 (62.50%); DSPs 582/1,248 (46.63%). Routed WNS +0.542 ns and WHS +0.010 ns at declared clocks. Occupied CLBs and BRAM make 'spare LUTs' an inadequate fit argument. These are historical v9e results, not a prediction for a wider build.
- `create_kr260.tcl`: 125 MHz decoder, 250 MHz memory/interconnect, 128-bit HP0 connection shared by model and state traffic. Nominal port payload ceiling is 4.0 GB/s; achieved bandwidth is lower. More ports/tiling/caching would change that envelope and require implementation evidence.
- v9e supports 2,048-token BF16 KV storage; archived numerical smoke and short commands exist. This does not establish maintenance accuracy at 2,048 tokens. Recorded board identity was restored to v9d after the candidate tests; no live state was checked for this report.

Evidence: `build/v2/qwen-fpga-decoder-v9e/vivado/routed-{utilization,timing}.rpt`, `board-evidence-1/validation-summary.json`, `board-evidence-4/validation-summary.json`, canonical `BOARD_STATUS.json`.

## Reproducible tensor and context budgets

`scripts/v2/research_model_envelope_20261102.py` fetched public configs/cards and API metadata for 15 checkpoints, pinned by repository revision under `model-envelope-2026-11-02/`. No weight files were downloaded. `estimates.json` computes unique parameter counts from ordinary dense-transformer configs and separates matrices from FP32 norm/bias parameters. API totals are retained separately: for Qwen3-0.6B/1.7B they include an extra embedding-sized count relative to the tied-weight analytic model and are not used blindly as deployment sizes. Packed BitNet API counts and multimodal totals likewise do not represent unique text parameters or inference bytes.

Q4_0 uses 18 bytes per 32 matrix weights; Q8_0 uses 34. Non-matrix parameters remain FP32 in this budget. Figures exclude GGUF metadata/alignment, tokenizer, activation/scratch, OS, duplication during loading and fragmentation. They are **not Q4_K_M file sizes**. The current datapath supports Q8_0; Q4_0 itself requires a new kernel. Quantization can change task correctness and must be evaluated.

| Model | Unique parameters | Q4_0 tensors, GiB | Q8_0 tensors, GiB | BF16 KV at 2,048 total tokens, MiB | Main porting issue |
|---|---:|---:|---:|---:|---|
| Qwen3-0.6B | 0.596B | 0.313 | 0.590 | 224 | Existing baseline; Q4 remains new work |
| Qwen3-1.7B | 1.721B | 0.902 | 1.703 | 224 | Wider workspaces; Q4 or larger DMA region |
| xLAM-2-1b-fc-r | 1.544B | 0.809 | 1.528 | 56 | Actually ~1.5B; Qwen2 biases/no QK norm; head ratio six |
| xLAM-2-3b-fc-r | 3.086B | 1.617 | 3.054 | 72 | Qwen2 semantics; head ratio eight; larger DMA region |
| SmolLM3-3B | 3.075B | 1.611 | 3.043 | 144 | Head ratio four; layer-dependent RoPE; larger DMA region |
| Qwen3-4B-Instruct-2507 | 4.022B | 2.108 | 3.981 | 288 | Head ratio four; wider workspaces; Q4 and DMA redesign |
| Qwen3-8B | 8.191B | 4.292 | 8.106 | 288 | Exceeds board DDR at Q4 before runtime/OS |

Rounded numbers should be regenerated from `estimates.json`; the source JSON is authoritative. The cache calculation is `layers × 2 × KV_heads × head_dim × bytes_per_element × total_tokens`. Total tokens includes prompt and generated tokens. FP32 doubles the cache; 4,096 tokens doubles it again. Other runtime buffers remain additional. New profiles must prove BF16 acceptability instead of inheriting the v9e qualification.

Example sensitivity: Qwen3-4B Q4 tensors plus BF16 KV at 2,048 tokens is about 2.39 GiB before everything else. A **hypothetical** 1.0 GiB OS/runtime reservation gives about 3.39 GiB total; a 1.5 GiB reservation gives about 3.89 GiB. These are budgeting scenarios, not measured free RAM or a validated allocation. Actual boot reservations and reachable physical regions decide feasibility. Qwen3-1.7B Q4 can fall below the 1 GiB driver extent while still exceeding historical 800 MiB CMA. Passing the driver size check is therefore insufficient.

Qwen3-8B Q4 is excluded from a fully resident deployment by weights alone. Two/three-bit formats can change the memory result; do not call 4B a fundamental maximum. Treat larger aggressively quantized models as boundary experiments whose semantic loss, kernel cost, cache and total allocation need evidence. MoE active-parameter counts also do not replace total resident weight accounting.

## Which candidates deserve capability screening?

This is a targeted shortlist, not an exhaustive survey or demonstrated winner.

1. **Qwen3-1.7B and Qwen3-4B-Instruct-2507:** the closest scalable architecture family. The latter provides a useful upper candidate for this implementation lineage and uses non-thinking output. Its publisher reports BFCL-v3 61.9 and substantially lower multi-turn task scores; these are screening evidence, not a reliability guarantee or our quantized result. [Official card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507).
2. **Qwen3.5-0.8B/2B/4B:** important newer capability candidates. The 2B card reports BFCL-v4 43.6 in its thinking comparison; the 4B card reports 50.3. The versions, modes, budgets and tasks differ from BFCL-v3. Configs show Gated DeltaNet layers, gated full attention, 256-wide attention heads and changed RoPE; our Qwen3 kernel cannot execute these by changing dimensions. Text-only deployment needs an explicit export that excludes vision and optional prediction components. Full multimodal API parameter totals are not a text-only footprint. Recurrent state also requires a separate budget. [2B official card/config](https://huggingface.co/Qwen/Qwen3.5-2B), [4B official card](https://huggingface.co/Qwen/Qwen3.5-4B).
3. **xLAM-2 1b/3b:** specialized tool-use comparators based on Qwen2.5, with official GGUF releases. More relevant than selecting a generic model by size alone. The model names understate the smaller checkpoint's actual ~1.54B parameter count. Research-use/noncommercial license recorded in the source metadata. [Official card](https://huggingface.co/Salesforce/xLAM-2-3b-fc-r), [official quantized release](https://huggingface.co/Salesforce/xLAM-2-3b-fc-r-gguf).
4. **SmolLM3-3B:** another dense candidate with explicit tool support, fewer KV heads and a distinct attention/position configuration. Its advertised BFCL figure must not be ranked directly against unrelated BFCL versions/settings. [Official card](https://huggingface.co/HuggingFaceTB/SmolLM3-3B).
5. **LFM2.5-1.2B-Instruct:** smaller hybrid candidate with function calling and convolution blocks. It may provide a useful capability/resource tradeoff, but vendor CPU/mobile throughput is not a KR260 estimate. A different kernel is required. [Official card](https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct).
6. **Granite-4.0-micro and Phi-4-mini-instruct:** secondary dense tool-capable comparators in the ~3–4B region. Inspect actual configs: Granite micro uses all attention layers in this pinned checkpoint despite the shared hybrid architecture class; do not conflate it with H-Micro. Both require model-specific scaling/normalization/position and layout checks. [Granite card](https://huggingface.co/ibm-granite/granite-4.0-micro), [Phi card](https://huggingface.co/microsoft/Phi-4-mini-instruct).
7. **FunctionGemma-270M and BitNet b1.58 2B4T:** small specialized and native-ternary controls, respectively. Existing maintenance FunctionGemma results should remain visible. BitNet's training/quantization/kernel contract is different from post-quantizing Qwen and offers no established maintenance advantage here. The public FunctionGemma config fetch returned 401; reuse only legitimately available local artifacts or public documentation, without treating a missing config as verified. [FunctionGemma publisher](https://deepmind.google/models/gemma/functiongemma/), [BitNet official model](https://huggingface.co/microsoft/bitnet-b1.58-2B-4T).

## Latency feasibility before choosing thresholds

Archived v9e cold short-command runs took 6.85–6.95 s, including 2.71–2.80 s startup; prefill ~1.437 s and decode ~2.70 s for 16 generated IDs. This is one narrow command, not a general task distribution. Separately, v16 service/caching improvements on v9d reached mean client wall 3.1553 s across 18 short calls in the recorded comparison. Do not combine the fastest pieces of different experiments into a fictitious measured system.

For a **single request using full-vocabulary dense decoding**, with weights streamed once per generated token, the current 4.0 GB/s nominal shared-port ceiling gives an optimistic bandwidth floor. Qwen3-1.7B Q4 matrix bytes imply roughly 0.242 s/token; Qwen3-4B Q4 roughly 0.566 s/token. Thus 32 decoded tokens alone require roughly 7.75 and 18.1 s respectively under that idealized schedule. This ignores cache/activation traffic, arbitration, bubbles, computation and prefill. It is neither predicted achieved latency nor a universal lower bound across redesigned multi-port, cached-weight or speculative architectures. The tiny final-token/EOS scheduling difference is immaterial to this screening calculation. Q4_K_M changes traffic and kernels.

Consequently there is no evidence yet for subsecond complete generated plans from these larger candidates on the current design. Short typed decisions, smaller candidate models, prefill reuse and changes to the memory datapath can occupy different operating regions. Measure them separately. Long thinking output can consume much more time than the final answer length suggests.

## What reliability can research honestly establish?

Existing maintenance Qwen generation achieved fresh 111/120 but crossed-condition stress 22/64, with 23 wrong accepted stress plans. The authored rule solver achieved 120/120 and 64/64 on that bounded task. New decision-head experiments did not solve recombination. These inspected template-derived sets are development evidence. They do not establish performance of a larger/newer checkpoint or an independent deployment guarantee. Sources: existing `maintenance-decisions-v4/REPORT.md` and the October 25 decision-model report.

Evaluate two separate axes: maintenance semantic correctness (including strict comparisons, units, dependencies and observation failures) and general tool use (tool selection, argument grounding, irrelevant/missing tools, clarification, parallel and multi-turn calls). Use the [official BFCL task taxonomy](https://gorilla.cs.berkeley.edu/leaderboard) as one external reference, pin evaluator/data versions and report subcategories. Audit labels and evaluate task execution in a sandbox. A BFCL percentage is not a probability that our service safely completes a maintenance request.

Reliability should be a curve over error, accepted coverage, correct on-time completion, context and output budget. Report valid-but-wrong outputs, refusals, timeouts and parser failures separately. Grammar enforcement is a separately named condition; it cannot silently repair semantics. Model confidence is not automatically calibrated. Score complete multi-step/turn episodes as well as individual calls.

Even zero errors among 299 independent representative accepted episodes only supports an approximately 1% one-sided 95% binomial upper error bound; about 2,995 are needed for 0.1%, and 29,956 for 0.01%. Formula: `ceil(log(0.05)/log(1-target_error))`. This is an experimental sample-size illustration, not a recommended tolerance or a universal guarantee. Template dependence, model/threshold selection on test data and distribution shift invalidate naive interpretations. Threshold calibration and final evaluation need separate data, with uncertainty reported. [NIST exact binomial confidence limits](https://www.itl.nist.gov/div898/software/dataplot/refman2/auxillar/exacbino.htm).

## Finite next experiment and decision points

First complete a software capability screen before expensive FPGA ports. Preserve Qwen0.6B, FunctionGemma, TF-IDF and rules as controls. Run Qwen1.7B, Qwen4B-2507, Qwen3.5 2B/4B, xLAM3B and LFM1.2B as the first candidate group; use the remaining shortlist to resolve clear gaps or close tradeoffs. Publish the candidate inclusion rule and fixed development budget before scoring; this proposed ordering is not a final model selection.

Use official chat/tool templates and declared non-thinking/thinking modes; pin revision, tokenizer and weights. Screen the precision that could actually deploy, with a higher-precision comparison to expose quantization loss. CPU/GPU execution is a capability reference, never called FPGA latency or FPGA numerical qualification. Generic llama.cpp Q4 weights with floating activations need comparison to the proposed FPGA activation arithmetic. Do not assume software scores survive the hardware port.

Measure a context/output grid rather than impose a tolerance now: total context 512/1,024/2,048/4,096 where each exact template fits; output caps 32/64/128/256 including any reasoning; cold and repeated-prefix conditions separately. These are exploration settings, not user acceptance thresholds. Rejection for capacity stays visible. General tool schemas may consume most of a short context window; count their actual tokens.

After development screening, report each promising profile's complete-task accuracy, wrong accepted rate, coverage, peak memory and output lengths. Estimate its implementation work and memory traffic. Reserve independent language/template families and numerical boundary cases for final testing; do not use them to select candidates. Then build the leading hardware profile, check quantized numerical behavior, routed timing and target allocation, and run a finite paired validation with measured p50/p95/p99/max latency. Only then recommend attainable error/coverage/latency/context thresholds and decide whether the original research angle is viable. Observed maxima remain distinct from proven worst-case bounds.

## Completion status

Completed here: primary-source shortlist, 15 pinned metadata snapshots, seven analytic ordinary-transformer budgets, cache scaling, local implementation/resource audit, and explicit latency/sample-size calculations. Not completed: candidate inference comparison, measured larger-model FPGA fit, independent reliability test or selection of a best model. The useful result of this first pass is that neither the current 0.6B model nor 1.7B should be treated as the hardware's established capability ceiling.
