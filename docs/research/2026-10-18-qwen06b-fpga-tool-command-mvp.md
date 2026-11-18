# Qwen3-0.6B FPGA tool-command MVP — 2026-10-18

Completed one real end-to-end command with every model operation running on the
KR260 FPGA. Linux remained on the same boot. ARM/host model inference and host
FP32 correction were not used. The real file read was performed by Linux after
validating the FPGA-generated tool call.

## Observed command

Request: `Read the Linux boot ID from '/proc/sys/kernel/random/boot_id'.`

The FPGA generated:

```json
{"name":"read_linux_file","arguments":{"path":"/proc/sys/kernel/random/boot_id"}}
```

Linux executed the file read and returned
`6c80ec1a-e7ae-473f-b169-d54f129615d1`, also the unchanged boot ID before/after.
The 67-token prompt produced 35 output tokens including EOS. All generated token
IDs and text matched the separate pinned-Q8 CPU reference; that reference was
never consulted by the FPGA runtime and did not restrict its vocabulary.

Actual runtime: **232.887 seconds** (SSH receipt233.469s). This is a correctness
MVP, not a latency target or a general tool-calling quality result. No benchmark
sweep was run. The kernel executed2828 decoder blocks across101 input tokens,
3630 commands total, and projected5317760 vocabulary rows (all151936 rows for
each output token).

## Running the deployed command

On the KR260, for the current Linux boot:

```sh
sudo sysone-qwen-fpga --query "Read the Linux boot ID from '/proc/sys/kernel/random/boot_id'."
```

The launcher and sources are installed under `/usr/local/bin/sysone-qwen-fpga`
and `/var/lib/sysone/qwen-fpga-decoder-v2`. The next result is written to
`/var/lib/sysone/qwen-fpga-decoder-v2/last-command-result.json`.

`sysone-qwen-decoder` remains loaded at50MHz; the accelerator is idle after the
command. R5 is unloaded. The old ARM generation service is stopped and disabled.
The former MiniLM image and calibrated R5 module remain on disk for restoration;
the active PL image is now the decoder. Files/launcher persist, but the resident
DMA model and FPGA load are **current-boot state**; no boot autostart/reboot flow
was installed or tested. Context is limited to256 tokens. The MVP tool registry
allows read-only `/proc/sys/kernel/random/boot_id`, `/proc/uptime`, `/proc/version`.

## What ran where

The FPGA implements embedding, all28 decoder layers, Q/K per-head RMSNorm,
RoPE, causal GQA/KV attention, SwiGLU, final RMSNorm, full-vocabulary projection
and argmax. Weights use the pinned official GGUF Q8_0 representation. Activations
and arithmetic are FP32 **on the FPGA**, not a host FP32 correction. This does
not claim an integer-only activation datapath.

Linux tokenizes using a vocabulary-only helper, copies bytes/offset descriptors,
schedules FPGA commands, decodes returned token IDs and validates/executes JSON.
There is no CPU model forward pass, hidden-state correction, CPU logit selection,
reference-token replay or vocabulary masking in this runtime.

The full639446688-byte model is stored in39 Linux-owned coherent DMA segments,
allocated from the existing800MiB CMA pool without changing the boot reservation
or rebooting. SHA256:
`9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031`.
The existing256MiB no-map reservation holds descriptors/activations/KV; the KV
cache uses56MiB. Linux still has2664616kB available after the run.

The FPGA image routed at50MHz with setup+6.408ns, hold+0.010ns, and64052/64052 nets
fully routed, no routing errors. A two-token real-weight hardware fixture matched
the independent first-layer reference: max absolute errors2.145767e-6 and6.854534e-7.
This covers numerical execution, not broad model accuracy.

## Focused correction and provenance

The first hardware-smoke process hit SIGBUS while copying a156-byte page table
into device-mapped scratch RAM, before launching a decoder request. A diagnostic
trace located the copy. Aligned32-bit transfers fixed it; the successful hardware
fixture and full command followed, without reprogramming or reboot. Failed receipts
and the source-fix job are preserved in `board/results/05*`, `06*`, `07*`.

`qwen-fpga-deployment-initial.tar` preserves the original uploaded package.
`qwen-fpga-deployment.tar` contains the corrected runtime and the same routed
hardware. The board's corrected package-file hashes match this final package.

Evidence: `build/v2/qwen-fpga-decoder-v2/deployment-proof.json`,
`real-command-result.json`, `hardware-block-smoke.json`, `board/results/09*`,
`10*`, `11*`, routed timing/utilization and the final bitstream/XSA. `seal.json`
hashes the selected source and evidence artifacts. No JTAG, reboot, paid compute,
commit/push or benchmark sweeps were used. SSH credentials stayed in RAM only.
