# Live INT8 tool execution and Qwen3-0.6B deployment — 2026-10-18

The command "Read the Linux boot ID from '/proc/sys/kernel/random/boot_id'."
completed on the KR260. Two INT8 FPGA encoder passes with R5 integer heads
produced read_linux_file(path="/proc/sys/kernel/random/boot_id"). The registered
Python tool read the actual procfs file. The deployed Qwen3-0.6B model returned
its exact value, 6c80ec1a-e7ae-473f-b169-d54f129615d1, with finish_reason=stop,
32 output tokens,140 prompt tokens and zero cached prompt tokens. This was real
tool execution, not a proposed-only call, canned result or laptop FP32 correction.
No arbitrary shell or external API was executed from generated output.

Evidence: build/v2/mvp-live-integration-v1/result.json,
results/08-real-tool-end-to-end-v2 and independently verified results/09.
The shell receipt was36.422s including source/image checks and module build
preparation; internal pipeline timer24.822s; Qwen request20.582s (reported prompt
14.422s, decode5.958s). No one-second latency target is established.

## Deployed roles

The FPGA runs H768 INT8 BERT; R5 controls inference and computes integer heads;
Linux decodes/validates the call and reads the registered file. There is no host
FP32 encoder model or correction. Qwen generation runs on KR260 ARM CPU using
native pinned llama.cpp b11540, NOT through the FPGA encoder bitstream.
No Qwen causal decoder is deployed on FPGA. Its Q4 weights also exceed the
current256MiB FPGA model reservation; this deployment uses normal Linux RAM
and leaves the FPGA reservation unchanged. Do not relabel this ARM deployment
as a0.6B FPGA deployment.

The Qwen3-0.6B-Q4_K_M model was already staged from the pinned official Q8 model,
locally requantized. Before startup its SHA256 was verified:
15e434d8ddf0af38fe3f7003af6ce6eac4edada6df34324aa45979f9cc79f02e.
The enabled/active sysone-qwen06b-mvp.service listens only on127.0.0.1:8016,
GPU layers0,4 ARM threads, context1024. Health=statusok. At verification RSS and
peak RSS were574372KiB. The service remains deployed after SSH closes.

CLI /usr/local/bin/sysone-mvp-int8; sources /opt/sysone-mvp/v2; encoder bundle
/var/lib/sysone/mvp-live-v1/encoder-registry-v2; last-result.json and
integration-proof.json under /var/lib/sysone/mvp-live-v1. The local README
contains the runnable command. Deployed source/launcher/service hashes were
matched exactly against the local snapshots.

## Focused registry integration

The earlier QAT candidate handled the song fixture but produced no calls for the
new Linux file tool. That failed live attempt is retained: no tool executed,
MiniLM restored. A fixed registry head adaptation resolved the live read command.
No benchmark sweeps or evaluation-based checkpoint selection were performed.

Training used48 synthetic requests:36 reads across three public proc files and
12 explicit no-action requests. These produce84 count/argument jobs. INT8 hidden
features were captured from the deployed QAT backbone on the board. Only count
rows0/1 and the span head were trained with fake quantized weights. Count rows2–5,
kind head, encoder, embeddings, program and tables stay unchanged. All non-head
sections were byte-verified identical to the previous QAT image. Training was
80epochs/560 small head updates with a fixed seed. The live query is not a
training phrase. This is narrow MVP registry adaptation, not general tool quality
evidence. Training includes negations, but denial behavior is not separately
claimed as hardware-qualified.

Registry image SHA256:
4cd8502e5b065cdbf1892c22c59605c8accca9f8d15481663c4a61391a378f30.
R5 ELF SHA256:
943478a490f8bcd04937e163600ab0b1b1a18e8ab364f571a25d95dcc93f19bb.
Original sealed candidates and runtime versions are retained. The handler only
reads /proc/sys/kernel/random/boot_id,/proc/uptime,/proc/version.

## Linux and restoration

After execution, calibrated MiniLM was independently byte-verified restored and
original R5 module/ELF identity verified. R5 pinned/mapped/may_run/quarantine/
reserved state and leases are zero. FPGA operating at199999998Hz. Linux same boot
ID as before deployment. SSH closed; no credential saved. Qwen stays active.
No reboot, JTAG, PL programming, dashboard restart, paid compute or commit/push.

An initial non-root inventory probe could not read the private candidate path;
root inventory succeeded. This and the first no-call attempt remain in results/.
No failed completed inference was erased or recast as success.
