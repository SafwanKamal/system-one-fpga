# Claude: independent ownership of FPGA hardware exploration

You are taking ownership of the hardware exploration workstream for our FPGA
LLM research project. This is an independent engineering responsibility, not
just a review subtask. Codex is working concurrently on evaluation methodology,
CPU controls, benchmark infrastructure, results analysis and paper evaluation.
You own hardware hypotheses, candidate architecture, HLS/RTL implementation,
simulation, synthesis, timing closure, candidate programming and hardware
validation. Coordinate runtime/ABI changes with the evaluation workstream.

## Objective and authority

Independently assess the current accelerator, identify its dominant bottlenecks,
and develop at least one justified hardware improvement. Choose the direction
from evidence: latency, prefill/decode efficiency, memory bandwidth/reuse,
resource efficiency or usable context capacity. Deliver an implemented,
reproducible candidate with measured results, or a well-supported no-go result
if the candidate does not improve the system. Preserve unsuccessful evidence.

The user explicitly authorizes BOTH Claude and Codex to program and test the
KR260. You do not need Codex's permission for each candidate programming action.
Board use must be serialized through the shared protocol below. This authority
supersedes earlier instructions assigning programming exclusively to Codex or
prohibiting Claude from accessing the board. The sealed baseline remains
immutable, but a separately packaged candidate may replace the active image.
The full benchmark sweep remains STOPPED; programming authority does not
authorize restarting that campaign. Bounded candidate validation is in scope.

Work autonomously through implementation and validation. Ask the user only for
genuinely missing information, credentials or a change to the agreed scope.

## Repository and first reads

Canonical original checkout on Windows PowerShell:

`C:\Users\user\OneDrive - Texas Tech University\Desktop\Code\FPGA Project\system-one-fpga\system-one-fpga`

Read these before editing or touching the board, relative to that checkout:

1. `HANDOFF.md`, especially its newest shared-board-authority section.
2. `BOARD_STATUS.json`, including its embedded protocol and canonical_path.
3. `scripts/v2/board_status.py` and `tests/test_board_status.py`.
4. `docs/research/2026-10-21-under10-qwen06b-fpga-tool-command.md`.
5. `build/v2/qwen-fpga-decoder-v8/README.md` and `seal.json`.
6. `build/v2/qwen-fpga-decoder-v8/deployment/sysone-qwen-decoder-wide-int8/build.json`.
7. `docs/research/2026-10-21-v8-chain-pilot-v5.md`, for evaluation limitations.

The current LLM accelerator is the HLS decoder in `hls/qwen_decoder_v8/`:
`qwen_decoder.cpp`, `matrix_q8.hpp`, `model_profile.hpp`, `testbench.cpp`,
`create_kr260.tcl`, and `release.tcl`. Older encoder RTL also exists in the repo;
do not mistake it for the deployed Qwen decoder.

The v8 host runtime retains the filename `src/sysone/v2/qwen_fpga_runtime_v7.py`.
Tokenizer code is `src/sysone/v2/qwen_tokenizer_v1.py`. Inspect existing
packaging/deployment scripts, their side effects, and the sealed package copies
before reusing them. Some old smoke scripts write into their package directory.
Do not replay historical SSH queue jobs.

There is substantial uncommitted/untracked project state. Inspect git status
first. A clean worktree from HEAD can omit the actual current HLS sources,
artifacts and documentation. Preserve unrelated work. Use an isolated checkout
or candidate source directories with recorded source hashes, and unique build,
package and result paths. Never run git clean/reset, delete shared build outputs,
or overwrite another agent's work. A separate branch alone does not isolate
artifact directories. Do not edit the canonical sealed v8 sources in place;
copy/version candidate sources instead.

## Baseline facts to verify, not assume live

- Board: KR260, SSH `ubuntu@192.168.0.239`.
- Last verified active app: `sysone-qwen-decoder-wide-int8`.
- Preserved package: `/var/lib/sysone/qwen-fpga-decoder-v8-startup-v2`.
- Global launcher: `/usr/local/bin/sysone-qwen-fpga`.
- Model: Qwen3-0.6B Q8_0 GGUF, SHA256
  `9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031`.
- Last verified resident allocation: 639446688 bytes in 39 segments. Reboots,
  model changes or incompatible programming invalidate old residency assumptions.
- Last verified clocks: approximately 125 MHz decoder and 250 MHz memory.
- Compiled profile: hidden1024, FFN3072, 28 layers, 16 query heads, 8 KV heads,
  head dimension128, vocabulary151936, context256, prefill batch8.
- B8 is tokens within one prompt, not eight independent simultaneous requests.
- Weight stream256 bits through a 128-bit HP0 clock/width conversion path;
  one Q8 block/cycle, paired query-head work, causal K/V reuse within prefill,
  and quantized-input reuse across related projections.
- Weights are Q8_0. Matrix activations are symmetric INT8 per block32, with
  INT32 dots and FP32 scaling/partials. Norm, RoPE, attention, KV and residuals
  remain FP32. All model arithmetic executes on FPGA; ARM handles tokenization,
  transfers, validation and orchestration. No CPU neural-network correction.
- V8 is not numerically equivalent to CPU Q8_0 inference with FP32 activations.
  Existing independent arithmetic/causal fixtures are the correctness reference.
- The sealed milestone was one correct tool command at 9.227829901 seconds,
  using 62 prompt and 16 output tokens, with zero prefix reuse. It includes
  tokenizer/setup and full resident-model verification; boot-time model loading
  is separate. This is not a throughput, worst-case or broad reliability result.
- V8 routed timing passed at its declared clocks. Read the actual reports,
  including retained CDC/methodology warnings; do not equate timing closure with
  zero warnings or extrapolate a higher safe clock without implementation.

These are historical baseline facts. BOARD_STATUS.json is the sole live
coordination record and can change while another agent works. Its initial
observation came from completed v5 evidence, not a new probe at file creation.

## Mandatory shared board-status protocol

Use this ONE physical file across every checkout:

`C:\Users\user\OneDrive - Texas Tech University\Desktop\Code\FPGA Project\system-one-fpga\system-one-fpga\BOARD_STATUS.json`

Never create an alternative live status file or use a worktree/cloud-sync copy
as the lock. Offline analysis, editing and synthesis do not need a reservation.
Every board session, including inspection, inference, programming, model loading
and service changes, does. The helper's reservation persists between commands.

PowerShell setup (these refer to the canonical original checkout):

```powershell
$canonicalRoot = 'C:\Users\user\OneDrive - Texas Tech University\Desktop\Code\FPGA Project\system-one-fpga\system-one-fpga'
$pythonExe = Join-Path $canonicalRoot '.venv\Scripts\python.exe'
$statusHelper = Join-Path $canonicalRoot 'scripts\v2\board_status.py'
$boardStatus = Join-Path $canonicalRoot 'BOARD_STATUS.json'

& $pythonExe $statusHelper --file $boardStatus show

$reservationJson = & $pythonExe $statusHelper --file $boardStatus reserve --owner 'Claude/hardware-session' --purpose 'Inspect and validate a versioned hardware candidate'
if ($LASTEXITCODE -ne 0) { throw 'Board reservation failed; do not access the board.' }
$claim = ($reservationJson | ConvertFrom-Json).reservation.claim_id
```

If another owner holds it, do offline work and coordinate availability. Never
use another owner's claim. Reservations do not expire automatically; do not
steal a reservation because it looks old. A stale/crashed-owner situation needs
an explicit coordinated handoff. A missing/corrupt status file fails closed.

After reserving, reconcile live boot ID, image/package, model residency, clocks,
services and processes with the last recorded observation. Do not assume the
board is still running v8. Mark the operation before acting:

```powershell
& $pythonExe $statusHelper --file $boardStatus begin --claim $claim --operation 'Describe the specific board operation here'
if ($LASTEXITCODE -ne 0) { throw 'Status update failed; do not proceed.' }
```

Actual hardware operations must also hold the board's Linux lock
`/run/lock/sysone-inference.lock`. Use an existing lock-aware runner or an
appropriate nonblocking flock wrapper for commands that do not acquire it.
Do not nest independent acquisitions of this non-reentrant lock. Do not program
over active inference, DMA or MMIO clients, or stop another owner's workload.

After the operation, create an observation JSON in your candidate evidence
directory, populated from actual live checks. For ready/stopped observations,
the helper requires `state`, `verified_at_utc`, `evidence`, `active_package` and
`boot_id`. Also record the actual active image, model identity/residency,
clocks, launcher/service changes and validation results relevant to your work.
Then:

```powershell
& $pythonExe $statusHelper --file $boardStatus record --claim $claim --observation 'ABSOLUTE_PATH_TO_YOUR_OBSERVATION_JSON'
if ($LASTEXITCODE -ne 0) { throw 'Observation update failed; retain ownership.' }
& $pythonExe $statusHelper --file $boardStatus release --claim $claim
if ($LASTEXITCODE -ne 0) { throw 'Release failed; reconcile ownership.' }
```

An observation file is experiment evidence, not another live status ledger.
If interrupted or validation fails and the actual configuration is uncertain,
record `state: "unknown"` with the failure/evidence instead of claiming ready.
Never restore stale v8 identity fields merely to release the board. The helper
blocks release while state is changing. Unknown state requires a reservation
purpose beginning `RECOVERY:` for subsequent reconciliation. If your process
dies, leave ownership in place for deliberate recovery; no blind auto-release.

Preserve sealed baseline files, model bytes and old evidence. Use separately
versioned candidate packages and keep an explicit recovery path. A candidate
may remain active after testing if its actual identity and condition are
accurately recorded. Any launcher/service change must have a recorded rollback.
Keep credentials in memory or an existing credential mechanism; never write
passwords into code, status/evidence files, command arguments or logs.

## Validation and workstream boundary

Start by measuring/reconstructing where time, DDR traffic and resources go.
Compare compute ceilings with achieved throughput and distinguish prefill,
decode, startup/verification, transfers and software overhead. Explore freely;
do not assume wider datapaths, more parallel MACs or higher clocks help without
checking memory delivery, routing, numerical behavior and implementation cost.

For a candidate, provide independent numerical/reference tests, meaningful
simulation, synthesis/implementation resource reports, routed timing and causal
board tests before performance claims. Save source, tool/configuration and
artifact hashes. Record numerical or quantization changes explicitly. Do not
drop hashing, reduce the vocabulary, reuse previous answers or add CPU model
computation to manufacture a speedup. If exploring a deliberate approximation,
label its quality/performance tradeoff and validate it separately.

Codex owns the shared evaluation methodology, datasets, parser/scoring policy,
CPU controls and paper evaluation. You may make hardware-specific tests and
microbenchmarks. Do not rewrite existing benchmark results, change gold answers,
train/tune against held-out qualification cases, or restart the stopped full
sweep. Propose interface/scoring changes explicitly instead of silently editing
shared files. Use versioned runtime adapters where your hardware requires them.

Recent evaluation shows real semantic weaknesses in this 0.6B model. Compact
state allowed eight requests under the current budget while full history hit
capacity before step three, but compact chains already failed semantically at
step two. These are not proof of eight correct dependent steps, a general Qwen
context limit, or a hardware defect. Avoid spending this hardware workstream on
further exact-format or Qwen-specific compaction tuning.

## Deliverables and first action

Deliver:

1. A concise architecture/bottleneck assessment with evidence and priorities.
2. A separately versioned candidate and reproducible build/program/test steps.
3. Correctness, routed timing/resource and bounded hardware measurement results,
   with raw logs, hashes, limitations and unsuccessful attempts retained.
4. Required runtime/ABI/model-profile changes and an integration handoff to Codex.
5. A candid recommendation: adopt, investigate further or reject the candidate.
6. Accurate shared board status and released ownership when the session ends.

Begin by inspecting the repository, baseline sources and reports offline.
Present your initial bottleneck hypothesis and first experiment, then proceed
with the authorized implementation and validation. You own this workstream;
coordinate shared resources without treating Codex as an approval gate.
