# Compact typed FPGA calls deployed - 2026-10-19

The same real cold tool command completes in **42.209s**, versus **66.183s** for
the previous batched deployment: 1.568x faster, 36.22% less elapsed time. The
same 0.6B Q8 model and deployed batch FPGA image remain active at 99,999,999 Hz.
This improvement changes the prompt, command wire format, completion condition
and tokenizer lifetime; it is not an increase in FPGA arithmetic throughput.

## What changed

The model now generates the two-string typed wire value `[function_name,path]`.
Both strings, including the full path, are generated on the FPGA. The ARM host
validates those strings against the existing registry and expands their structure
into the same tool API object. It does not predict, repair, substitute or infer
argument values. No CPU model forward pass, logits correction, restricted output
vocabulary or replay is used.

Generation stops when the complete typed JSON array is available, rather than
continuing to generate Markdown closing fences or EOS. Ordinary JSON syntax
parsing on the host determines completion; it does not alter FPGA logits.
The actual model emitted an opening Markdown fence despite the instruction;
the parser accepts that framing and stops after the complete enclosed array.
There is no claim that this output includes EOS or a closing Markdown fence.
Invalid JSON, invalid types, an unregistered function/path, premature EOS or
truncation cause failure without tool execution.

A vocabulary-only native helper loads once per request and serves tokenization
and incremental token-piece decoding through a local pipe. It never creates an
inference context. Previously two helper invocations loaded the vocabulary
separately. Full resident model hash verification remains enabled on every call.

## One measured cold command

`Read the Linux boot ID from '/proc/sys/kernel/random/boot_id'.`

| Measurement | Previous | Compact |
|---|---:|---:|
| Total elapsed including initialization and real tool | 66.183s | 42.209s |
| Prompt tokens | 67 | 62 |
| Generated tokens | 35 (including EOS) | 16 (typed JSON completion) |
| Prefill | 21.119s | 19.579s |
| Subsequent decoding | 35.655s | 15.505s |
| Kernel commands | 2181 | 1221 |
| Semantic decoder-layer evaluations | 2828 | 2156 |
| Matrix-layer weight passes | 1428 | 868 |

New vocabulary setup: 1.917s. Full resident-model SHA256 verification: 4.699s.
Both are included in the total. Prefix cache is disabled and zero prompt tokens
were reused. All 151936 vocabulary rows were projected for each generated token.

The generated array contained exactly `read_linux_file` and
`/proc/sys/kernel/random/boot_id`. The actual tool returned unchanged boot ID
`6c80ec1a-e7ae-473f-b169-d54f129615d1`. Function, argument and tool result match
the previous real command. Prompt/generated token IDs intentionally differ with
the changed wire format; there is no exact-token-equivalence claim.

One cold board command passed. No warm repeat or benchmark sweep. The prior
hardware numerical checks remain applicable because the FPGA image and runtime
math are unchanged. The typed completion parser also received directed local
checks for partial JSON, complete JSON, Markdown framing and invalid types.
This is a fixed-command result, not general capability or deadline qualification.
Latency remains above the next 30-second milestone and 10-second MVP target.

## Deployment

`/usr/local/bin/sysone-qwen-fpga` now invokes
`/var/lib/sysone/qwen-fpga-decoder-v5/scripts/v2/run_qwen_fpga_command_v4.py`.

```sh
sudo sysone-qwen-fpga --query "Read the Linux boot ID from '/proc/sys/kernel/random/boot_id'."
```

This profile always performs cold prefill; `--no-prefix-cache` is accepted for
compatibility. Result: `/var/lib/sysone/qwen-fpga-decoder-v5/last-command-result.json`.
The preceding launcher bytes remain in that package as `sysone-qwen-fpga.previous`.
The previous package and firmware remain installed. No FPGA reprogramming,
Linux reboot, memory-allocation change, ARM model inference or paid compute.
The ARM model service remains stopped/disabled; R5 is unloaded; decoder is idle.
Same 39 DMA segments/639446688-byte pinned model and context256. Files/launcher
persist, but FPGA and model residency remain current-boot state. SSH closed after
promotion with no saved secret. No commit/push.

## Sources and evidence

CLI: `scripts/v2/run_qwen_fpga_command_v4.py`. Vocabulary helper:
`hls/qwen_decoder_v5/qwen_vocab_session.cpp` (software helper only; no new HLS
kernel). Package/promotion helpers: `package_qwen_fpga_v4.py` and
`finish_qwen_fpga_v4.py`. It reuses unchanged `qwen_fpga_runtime_v3.py` and the
qualified `hls/qwen_decoder_v4` image. `build/v2/qwen-fpga-decoder-v5/` contains
`deployment-proof.json`, `real-command-result.json`, archive, queue receipts,
installed source hashes, compiled helper hash and `seal.json`. Prior v2/v3/v4
sealed artifacts were verified unchanged.
