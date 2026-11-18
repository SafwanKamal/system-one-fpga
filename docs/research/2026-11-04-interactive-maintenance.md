# Interactive maintenance and an FPGA demonstration scope

## Maintenance experiment

Qwen3-1.7B Q4 produces one proposal at a time. The planner supplies the request, catalog, prior proposals and simulated read receipts. A proposal can name a read or action, state a comparison against a prior reading, clarify or reject a request, or finish. The assembler validates each partial plan with the existing maintenance schema. It can return up to three steps. Read receipts come from a fixed simulated plant during assembly. The evaluator replays the completed plan against the existing below, equal, above and read-error states. Guarded steps remain proposals during assembly.

The adaptation trains a maintenance-specific action head over the frozen Q4 model's final hidden state. A 128-unit GELU layer and categorical outputs predict the operation and applicable fields, including the source, comparison, bound and evidence indices. The head receives explicit catalog and integer-literal candidates drawn from the public input. Catalog entries mentioned in the current or prior request appear first, followed by the remaining entries in sorted order. That ordering provides a grounding prior shared by the interactive arms. The head uses 800 teacher-forced turn examples from 384 existing training cases. I chose 24 epochs and a fixed seed for the initial run. The pretrained GGUF is the pinned November 2 checkpoint.

The comparison uses all 184 prior maintenance cases, with the saved one-shot outputs as the historical reference and an unadapted next-step generation arm using the same interactive schema and inputs. After observing malformed arrays in the instruction-only run, I added a separate unadapted arm with six JSON format examples. After observing weak fit in the initial head, I compared raw, centered and standardized hidden states on a case-grouped split within the training set. At epoch 48 they scored 87, 125 and 125 of 192 held-out turns on exact applicable fields. I selected centering because it tied standardization without per-feature scaling. I fit the selected head for 48 epochs on all 800 training turns and revisited the original evaluation cases. The grouped probe used training cases only.

The general retest runs the same native generation route on 200 BFCL cases and 12 simulated two-turn cases in a separate server session. The head is selected only for maintenance. The corpus consists of authored template variants and public benchmark cases. The historical one-shot arm used two demonstrations, a different prompt and a 256-token cap. Interactive generation uses up to 96 tokens per turn. The action head emits categorical outputs after each prefill. Each interactive route may require multiple prefills.

## Results

| Maintenance arm | Fresh correct /120 | Conditional correct /64 | Schema-valid outcomes /184 | Incorrect schema-valid plans /184 |
|---|---:|---:|---:|---:|
| Prior one-shot generation | 15 | 0 | 82 | 67 |
| Interactive generation, instructions only | 3 | 0 | 3 | 0 |
| Interactive generation, format examples | 0 | 0 | 25 | 25 |
| Interactive raw-state head, 24 epochs | 20 | 0 | 171 | 148 |
| Interactive centered-state head, 48 epochs | 41 | 4 | 160 | 102 |

Compared with the prior one-shot result, the centered head recovered 38 fresh cases and four conditional cases, and lost 12 previously correct fresh cases. Its four correct conditional plans were one inclusive lower-bound case, two strict upper-bound cases and one inclusive upper-bound case. The format examples increased the number of schema-valid outputs while reducing exact answers. The head produced more correct plans and more incorrect schema-valid plans than the prior one-shot baseline. Keep the maintenance head at the proposal stage.

The existing authored-rule control scored 184/184 on the same template-derived corpus. The trained head's comparison establishes a development result against the generative arms. The next independent quality test would need new authors and language families. The raw and centered full runs also differ in training duration. The equal-epoch grouped probe is the comparison that isolates centering.

The separate general route scored 170/200 on BFCL and 9/12 on simulated two-turn tasks, compared with 172/200 and 9/12 previously. All 212 first-turn prompt ID sequences matched. Three BFCL cases became incorrect and one became correct. The two-turn correctness decisions matched on all 12 cases. The replay used the same base weights and Vulkan server binary.

The existing suite passed 71 checks. All 184 reference action sequences reconstructed the original plans or terminal outcomes. I checked the saved scores for 920 maintenance records across the five arms and re-scored 212 general and episode records. The training and evaluation public inputs had zero exact matches after sorting the catalogs. The CLI smoke request proposed a single status read for P61 and then finished. All new inference ran in software. [Result summary](../../build/v2/interactive-maintenance-20261104/summary.json) · [Smoke output](../../build/v2/interactive-maintenance-20261104/demo-proposal.json)

The local planner takes a JSON file with a request, catalog and optional context. The sample below uses the fitted centered head and simulated receipts. [Planner source](../../scripts/v2/interactive_maintenance_20261104.py)

```powershell
.venv/Scripts/python.exe scripts/v2/interactive_maintenance_20261104.py plan --request-file build/v2/interactive-maintenance-20261104/demo-request.json
```

## Measured fabric implementations

| Work | Model and platform | Measurement and relevance |
|---|---|---|
| openTPU | Qwen3-0.6B, Qwen3.5-2B and SmolLM3-3B, Kintex-7 PCIe card with two DDR3 channels | The project's board logs report 30.7, 12.03 and 8.72 tokens/s wall decode for the respective 4-bit configurations with INT8 heads. Its test uses 64 generated tokens after a 512-token prompt and host argmax. It publishes RTL, runtime and a simulator. [Project board results](https://github.com/FeSens/openTPU#results) |
| Melten N10 | Qwen2.5-0.5B, 1.5B and 7B, Virtex UltraScale+ XUP-P3R | The developer reports 18.8 tokens/s decode and 45.7 tokens/s prefill for 1.5B on a four-channel DDR4 board using group-64 INT8 weights and INT16 activations. The device matched the fixed-point reference on all 8,152 checked steps for that model. [Engineering note and methodology](https://www.melten.ai/blog/llm-accelerator-built-in-five-days/) |
| Redwood Nano | Qwen3-0.6B, Versal VPK180 | The authors report 12.1 tokens/s on the 250 MHz FPGA prototype, including prompt transfer and token streaming. The paper separately projects ASIC performance and power. [Primary paper](https://arxiv.org/abs/2608.26418) · [Board report](https://architectlabs.com/blog/redwood) |
| Li et al. | Llama 2 7B, AWQ W4A16 with KV8, KV260 | 4.9 tokens/s decode using four AXI ports and about 84.5% of their modeled bandwidth limit. Their datapath and memory packing are closely related to our weight-streaming problem. [Paper, setup and results](https://arxiv.org/html/2502.10659#S7) |
| Hummingbird | Llama 3 8B, GPTQ W4 with KV8, KV260 and ZCU104 | 4.8 and 8.6 tokens/s decode, respectively. The design offloads token embeddings to flash and uses a grouped-query attention schedule. The reported power comes from Vivado reports. [Paper, hardware setup and results](https://arxiv.org/html/2507.03308#S5) |
| TeLLMe | 0.7B ternary model with 8-bit activations, KV260 | Reports 9.51 tokens/s decode and 0.55 s to first token for a 64-token prompt. Its ternary matrix engine makes it a useful prefill/decode co-design reference. [Paper, experimental results](https://arxiv.org/html/2504.16266#S4) |
| LlamaF | TinyLlama 1.1B, W8A8, ZCU102 | Reports 1.33–1.48 tokens/s across 64–256 generated tokens, with a same-board ARM-only control. The asynchronous schedule overlaps parameter movement and fabric computation. [Paper, performance analysis](https://arxiv.org/html/2409.11424#S5) |
| FlightLLM | Llama 2 7B, sparse mixed precision, Alveo U280 | Reports about 55 tokens/s for the board demo. The authors released the hardware test artifact. This is a reference for measurement and reproducibility on an HBM system. [Paper](https://arxiv.org/abs/2401.03868) · [On-board artifact](https://github.com/FlightLLM/flightllm_test_demo) |
| EdgeLLM | ChatGLM2-6B, VCU128 | The authors report a deployed CPU–fabric implementation with 1.67× the throughput of their A100 baseline. Its HBM system and model are different from the KR260 design. [Paper](https://arxiv.org/abs/2407.21325) |

The Qwen-specific study closest in board class, *On-Device Qwen2.5*, studies Qwen2.5-0.5B with AWQ on KV260. Table III marks the 5.10 tokens/s accelerator result as co-simulation. The measured KV260 Llama results use different formats, memory placement and port configurations from our KR260 implementation. Our documented decoder uses a single 128-bit HP0 path at 250 MHz. [Qwen2.5 paper, Table III](https://arxiv.org/html/2504.17376#S4) · [Local feasibility audit](2026-11-02-model-capability-feasibility.md)

## A narrower demonstration

Use **exact-prefix reuse on a single-board Qwen decoder** as the primary scope. The existing v9d experiment observed 328/328 exact generated-ID matches across the two prompt representations against the sealed cold controls. Across the 224 structured-state calls, the fabric evaluated 8,464 of 28,896 logical prompt tokens, reusing 70.71%. I joined the v13 and v14 timing tables by request ID after verifying both tables against their original seals. Mean prefill fell from 3.195 s to 1.117 s (65.0%) and mean request wall time fell from 7.931 s to 5.852 s (26.2%). Cache reuse was faster on 221 of 224 requests. Each of the six chain means improved by 23.9–27.7%. The cold controls came from a separate matched-identity run. The inputs followed fixed traces, and the cache held one conversation. [Sealed v14 comparison](2026-10-22-v9d-prefix-comparison-v14.md) · [Paired reanalysis](../../build/v2/interactive-maintenance-20261104/prefix-scope-reanalysis.json)

For a final demonstration, interleave cache-on and cache-off calls with the same model, fabric image, clocks and prompts. Record actual evaluated prompt tokens, reused tokens, prefill and request latency distributions, and generated-ID agreement. Group by shared-prefix length and show reset and prefix-divergence cases. Measure the paired reduction in fabric prefill work on the declared workload, with output parity as an invariant.

If the project requires an RTL contribution, use **shared weight streaming across prefill lanes**. The existing four-lane design reduced the prefill matrix-layer weight passes from 1,876 to 476 and reduced wall time from 92.031 s to 66.183 s on one cold command with identical generated IDs. A repeated prompt-length sweep, with no prefix reuse and matched arithmetic, would extend that single-command result. [Batched on-board prefill](2026-10-19-batched-qwen06b-fpga-tool-command.md)
