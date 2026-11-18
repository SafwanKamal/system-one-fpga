# KR260 generated-answer baseline

Owner target: first answer words within one second. Classification and generation
are separate runtimes. This baseline uses the four ARM CPU cores, not FPGA decoder
acceleration, and does not write to the encoder's reserved DDR or unload its app.

Artifacts are pinned: llama.cpp b11540; official Qwen/Qwen3-0.6B-GGUF revision
23749fefcc72300e3a2ad315e1317431b06b590a, Apache2.0. Q8_0 SHA256 is verified
against Hugging Face LFS metadata. Q4_K_M is locally requantized from that Q8_0
with --allow-requantize; it is not an official Qwen Q4 export. Both are included
as quality/speed controls. Keep the original Q8 file and provenance manifest.

Sources: [Qwen model](https://huggingface.co/Qwen/Qwen3-0.6B-GGUF),
[llama.cpp build instructions](https://github.com/ggml-org/llama.cpp/blob/b11540/docs/build.md),
[server API](https://github.com/ggml-org/llama.cpp/blob/b11540/tools/server/README.md).

## Preparation and laptop evidence

`python scripts/v2/kr260/prepare_generation.py` downloads pinned artifacts,
quantizes with the official Windows CPU binary, and writes
build/v2/kr260-generation.tar.gz. Separate files/environment from encoder training.

Laptop quantized CPU runtime smoke: build/v2/eval/laptop-qwen-generation.json (Q4, eight requests)
and laptop-qwen-generation-q8.json (Q8, four requests). All requests produced
complete SSE responses, no reasoning output, and server cache_n0. First words
were below one second on the laptop, excluding server model startup. This is not
KR260 performance evidence. Q4 negation failed; Q8's leading Yes contradicted
its explanation to leave the lights on. H-bridge/context answers also require
manual correctness review. No operational actions are taken from generated text.

## Board run

From laptop PowerShell inside the inner repository directory:

```powershell
scp .\build\v2\kr260-generation.tar.gz ubuntu@192.168.0.239:~/
ssh ubuntu@192.168.0.239
```

On the KR260:

```sh
mkdir -p ~/sysone-generation
tar -xzf ~/kr260-generation.tar.gz -C ~/sysone-generation
sh ~/sysone-generation/setup_generation.sh
```

Setup verifies payload hashes, installs compiler/CMake if missing, compiles the
pinned CPU-only source natively on Cortex-A53 (no unsupported x86 or ARMv8.2
prebuilt instructions), and runs Q4 then Q8. Build progress is printed. Each
model runs four prompts twice: basic explanation, negation, clarification, and
supplied context. Each run owns and stops its own localhost-only server. No
sudo is used for inference. Per-case deadline180s, output limit64 tokens.

Retrieve both reports from laptop PowerShell:

```powershell
scp 'ubuntu@192.168.0.239:~/sysone-generation/kr260-generation*.json' .\build\v2\eval\
```

Reports separate model startup, first SSE event, first visible text, first
alphanumeric answer text, server prompt time/token counts, decode tokens/sec,
completion time, truncation and peak server RSS on Linux. Timings use a persistent
resident server, with cache_prompt false. Inspect cache_n in each server timing
to confirm full-prompt evaluation. An answer can meet latency and still be wrong;
correctness is manually reviewed, not inferred from speed or lexical patterns.
The context is a short synthetic supplied snippet, not retrieved documentation.
No grounded-electronics accuracy or one-second KR260 result is established yet.
