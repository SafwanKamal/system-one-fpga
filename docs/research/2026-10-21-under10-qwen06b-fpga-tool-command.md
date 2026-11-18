# Sub-ten-second Qwen0.6B FPGA tool command — 2026-10-21

One real cold-prefill command completed in **9.227829901s**
(full SSH job 10.063s), versus v7 18.928106882s:
2.0512x and 51.25% less time.
This is one focused command, not a benchmark sweep or worst-case timing claim.

The FPGA generated read_linux_file('/proc/sys/kernel/random/boot_id'), and Linux
executed it, returning current boot e9728928-307d-485b-b40b-63fa29d9296d. The same Linux boot and
639446688-byte pinned Q8_0 model residency were retained. All NN arithmetic is on
the FPGA; no ARM/host NN, argument correction, output replay or vocabulary mask.
Zero prefix reuse. Model loading at boot is separate; cold-call timing includes
tokenizer startup and verification of every resident weight byte, as in v7.

Arithmetic precision changed: matrix inputs use dynamic symmetric INT8 per block
of 32, with ties rounded away from zero and saturation to [-127,127]. Weights
are the unchanged pinned Q8_0 bytes. Dot products accumulate INT32, then use
FP32 scales/partials. Norms, RoPE, attention, KV and residuals remain FP32.
This is not a claim of numerical equivalence to the prior FP32 matrix engine.
Generated IDs equal v7: True.

Hardware improvements: 256-bit weight stream; 125MHz decoder and 250MHz,
128-bit PS memory interface through a clock/width converter; eight-token
prefill weight reuse; one matrix block per cycle; paired query heads sharing
K/V reads; causal head-buffer reuse across a prompt batch; quantized input
reuse for Q/K/V and gate/up; shared deep URAM token banks.

Host setup uses native tokenizers 0.23.2 NFC/Split/ByteLevel operations and
compiled ranked BPE tables from the pinned official tokenizer. This avoids
constructing a full native BPE model while holding Python's GIL. Eight focused
normalization/Unicode/whitespace/special-token cases matched official IDs;
the exact prior prompt IDs and generated output bytes also matched. The ARM
wheel, official source and compiled tables are hashed. No CPU NN is loaded.
Ordered SHA256 checks every resident byte before FPGA inference and inside
the timer. Four bounded native staging buffers are immediately refilled after
SHA consumption, pipelining upcoming DMA reads with ordered hashing.

Prefill 3.054299s; subsequent decode 3.494616s;
startup wall 2.673105s. SHA 1.712556s
and vocabulary 0.749927s are measured within startup;
the wall measurement includes setup overhead and any task overlap.
Prompt/output tokens: 62/16; weight
passes 644; full-vocabulary rows 2430976.

The first v8 command was correct but took 12.045178s,
including 5.203310s startup. Promotion was refused.
After the compiled tokenizer and pipelined SHA changes, the second cold command
above passed. The FPGA image and causal fixture were unchanged. Both commands
and the failed threshold check are retained. No benchmark sweep was run.

Independent NumPy integer-dot and ordered FP32 reference: eight-token causal
layer, full8 and1+7, final norm, top32 argmax4 and scatter boundary passed Csim.
The board's 16 causal fixture cases passed, worst error
7.15255737e-07 against that INT8 reference, not against original FP32 matrix math.
Generic matrix capacity6144 at columns2048/6144/1056 also passed Csim.

Geometry derives from the model profile, and tensor alignment and clock guards
run before NN commands. Larger models still require their own weights, memory
allocation, quantization/quality validation and routed fit. No larger model was
deployed. The current DMA table remains limited to 64x16MiB.

Active app: sysone-qwen-decoder-wide-int8; launcher /usr/local/bin/sysone-qwen-fpga.
Previous launcher, firmware and release seals retained. Linux stayed running.
Model/FPGA residency lasts for this boot; package and launcher persist on disk.

The first load attempt stopped before NN inference because dfx-mgr had restarted
while an old configfs overlay remained applied. Its failed receipt is retained.
After checking idle state and absence of MMIO clients, only that verified orphan
overlay was removed and the manager restarted. Baseline reload and candidate
deployment then passed. Linux and the resident DMA buffers were retained.

Evidence: deployment-proof.json, real-command-result.json, hardware-block-smoke.json,
hardware-source-sha256.json, ip-rtl-consistency.json, tokenizer-correctness.json,
tokenizer-wheel-source.json, traffic-plan.json, routed reports under vivado/,
and board queue receipts. All earlier v2-v7 seals were verified unchanged.
