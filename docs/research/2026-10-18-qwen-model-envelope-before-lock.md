# Model capability and hardware envelope before lock

The 0.6B decoder demonstrated one valid tool call, not general tool-calling
qualification. Its first deployment took232.887s. A same-command profiling run
measured232.991s:205.774s decoder blocks,17.554s vocabulary projection. Increasing
model size now directly conflicts with the current latency objective.

The immediate speed candidate is one100MHz build with matrix initiation interval
3 (previous4), explicit burst-loaded KV buffers in8URAMs, and grouped-query reuse.
It keeps the same pinned0.6B Q8 weights/prompt/full vocabulary and keeps all model
math on PL. Timing and hardware results belong in its deployment proof; synthesis
estimates are not a measured speedup or a deadline bound.

## Practical next model envelope

Qwen3-1.7B is a reasonable larger candidate to assess after improving the baseline.
Its official configuration retains28layers,Q16/KV8/head128, but increases hidden
width1024->2048 and feed-forward width3072->6144:
https://huggingface.co/Qwen/Qwen3-1.7B/raw/main/config.json

The calculated parameter counts are596049920 and1720574976. UniformQ4_0 tensors
for1.7B require968249344bytes (~923MiB), excluding tokenizer/GGUF metadata and
alignment. This is an ideal uniform-format estimate, not a quoted Q4_K_M file
size; mixed GGUF precisions can be larger. It exceeds the existing800MiB CMA
pool even if the current model is freed. Q8_0 tensors for1.7B need1828474880bytes.
See build/v2/qwen-fpga-decoder-v3/model-capacity-budget.json for reproducible
shape/weight-traffic calculations. Shared tied embeddings count once.

K26 has4GB DDR4 shared with Linux:
https://www.amd.com/en/products/system-on-modules/kria/k26/k26i-industrial.html
That makes a short-context quantized1.7B memory footprint plausible, not already
supported. Current owned-DMA firmware is constrained to64segments and32-bit
low-DDR addresses; the current accelerator implementsQ8_0 only and fixed0.6B
workspace shapes. A larger model needs a Q4/mixed-format datapath, wider workspace
layout, revised scatter/DMA address plan, and an explicit Linux memory margin.
There is no fundamental rule forbidding more model memory, but allocation must
remain kernel-owned and within accessible AXI address windows.

The KV-cache requirement remains56MiB at context256 because the official1.7B
KV-head count and dimension are unchanged. Hidden/FFN compute grows: per-token
non-embedding matrix parameters increase3.2x. UniformQ4 reduces weight traffic,
not that arithmetic count. Fitting the weights does not establish useful latency.
No larger model was downloaded, trained, built or tested in this speed task.

## Recommended freeze order

1. Define/version the tool ABI, argument types and failure behavior independently
   of the model. Invalid arguments continue to be rejected before execution.
2. Improve targeted tool calling on0.6B (fine-tuning/distillation is an option;
   improvement must be demonstrated) while fixing the accelerator bottleneck.
3. Consider1.7B Q4 as the next size candidate if quality requires it and latency
   permits. Avoid selecting a bigger model merely because its weights fit.
4. Select a bounded model profile: architecture/weight hash, hidden and FFN
   widths, layer count, quantization, prompt/context/output limits, memory map,
   scheduling and allowed tools. Then qualify routed timing and end-to-end bounds
   for that profile. A successful command and passing FPGA clock timing are not
   sufficient to claim a general worst-case execution-time bound.

Keep the profile and ABI versioned so weight-only capability updates need not
change the tool interface. Changing model shape/precision/context requires renewed
hardware/timing qualification. Prefill batching/weight reuse and lower-bit weights
are the next substantial architectural speed options after the current candidate;
prefix caching can help repeated requests but must be reported as warm-state
latency separately from cold latency.
