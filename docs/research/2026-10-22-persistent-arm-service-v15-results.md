# Persistent ARM service v15: implementation and measured comparison

Implemented and tested on KR260, 2026-10-22. The existing v9d FPGA image,
resident Qwen3-0.6B Q8_0 weights, boot, clocks, launcher and deployment package
were retained. The full benchmark sweep remains stopped.

## Result

Mean client process wall time fell from **6.9267 s to 5.5772 s**, saving
**1.3495 s/request (19.48%)** with full per-request weight verification.
All 12 requests completed. Each of the three prompts ran twice per backend.
Prompt IDs, generated IDs, generated text and generated tool calls matched
exactly across all repeats and both backends.

| Request | Standalone mean | Service mean | Saving | Reduction |
|---|---:|---:|---:|---:|
| Read /proc/sys/kernel/random/boot_id | 7.3682 s | 6.0509 s | 1.3173 s | 17.88% |
| Read /proc/uptime | 6.7913 s | 5.4421 s | 1.3492 s | 19.87% |
| Read /proc/version | 6.6207 s | 5.2388 s | 1.3819 s | 20.87% |
| Equal-weight aggregate | 6.9267 s | 5.5772 s | 1.3495 s | 19.48% |

The service's one-time startup took **2.9854 s**, reported separately from
ready-service requests. Startup is real work, not eliminated work. Queueing and
power were not measured. No FPGA resources were removed or added.

## Implementation

- `src/sysone/v2/qwen_arm_service_v15.py`: service-scoped engine/tokenizer,
  input validation, request counter deltas, unchanged compact prompt and typed
  completion semantics, faulted-session rejection, identity checks.
- `src/sysone/v2/qwen_weight_verification_v15.py`: full resident byte coverage
  with the same ordered SHA256/four-buffer native-copy pipeline as v9d.
- `scripts/v2/qwen_arm_service_v15.py`: serialized Unix-socket server/client,
  bounded framing, socket mode 0600, lifetime hardware lock, disconnect-safe
  transaction completion and quiescent shutdown.
- `firmware/arm_service_v15/`: operating instructions and optional systemd unit.
  The unit was not installed or enabled; benchmarking used a temporary process.
- `scripts/v2/benchmark_arm_service_v15.py`: preserved standalone runner as
  control, exact output checks, before/after causal fixtures and identity checks.

Historical runtime, tokenizer, runner and hardware sources were not edited.
The candidate source bundle is installed additively at
`/var/lib/sysone/benchmarks/persistent-arm-service-v15/bundle`.

Every service generation verifies all **639,446,688 resident bytes** before
any request neural operation. This also applies to the first request after
startup verification; there is no startup-only verification shortcut. Prefix
reuse is disabled on both arms, so the measured change is persistence rather
than cache reuse. All embedding, matrix, normalization, attention and vocabulary
projection operations remain on the FPGA.

## What explains the saving

| Mean component | Standalone | Service |
|---|---:|---:|
| Resident SHA256 | 1.6950 s | 1.6929 s |
| Prefill | 1.2604 s | 1.2613 s |
| Decode | 2.2850 s | 2.2835 s |
| Runtime's internal request timer | 6.3907 s | 5.2841 s |
| Client process wall | 6.9267 s | 5.5772 s |

Hashing and neural execution remain essentially unchanged in this sample.
Approximately **1.1066 s** of saving is inside the runtime timers, which include
repeated tokenizer/engine setup in the control. The remaining approximately
**0.2429 s** is outside those timers, including process startup/import/exit work.
These differences are descriptive accounting, not individually instrumented
causal attributions to each constructor step.

The service retains the tokenizer, DMA descriptor, MMIO and scratch mappings,
initialized page table and RoPE table. It still creates bounded verification
staging buffers/mappings/workers for each full hash. This first implementation
does not optimize the hash itself or move any neural operation onto ARM.

## Protocol and validation

The fixed order was baseline prompts A/B/C, service A/B/C/C/B/A, then baseline
C/B/A, with no concurrent hardware client. Standalone blocks bracket the
service to expose gross drift; the experiment is not randomized/interleaved
per request. All timings were measured on the board, not across SSH. Both arms'
primary metric includes launching their CLI client process; service startup is
separate. Prompt/output lengths were 56/16, 53/13 and 52/12 tokens respectively.
The tool-call arguments matched; live tool return values such as uptime are
expected to change and were not used as output-identity gates.

- Nine local focused tests passed (service lifecycle and existing prefix tracker).
- Two stdlib Linux integration tests passed in WSL and again on ARM: real mmap
  hashing with tail-byte corruption rejection, socket serialization, client
  disconnect, invalid request, lock exclusion and shutdown cleanup.
- Service rejected an invalid request on hardware and remained READY.
- All six service requests explicitly reported full byte verification.
- All 616 causal fixture cases passed before and after (1232 total), worst
  absolute error 2.384185791015625e-7.
- Before/after board inventory matched; frozen source hashes passed.
- Final check acquired the hardware lock, verified the service PID was gone,
  socket absent, and FPGA AP_IDLE asserted. SSH helper closed afterward.

The service is intentionally left **stopped**, with no boot enablement or
launcher change. The board retains v9d and its resident model. Future service
operation must still follow canonical board ownership and hardware locking.

## Evidence and limits

Local evidence: `build/v2/persistent-arm-service-v15/evaluation/summary.json`,
`requests.json`, individual baseline/service JSON and stdout/stderr,
`ready.json`, `shutdown.json`, causal fixture reports, inventory snapshots,
`final-observation.json` and source hashes. The original collected archive and
SSH receipts are retained outside the evaluation directory.

This is a finite smoke/performance comparison: three short tool prompts, two
repeats per backend, one boot and one service session. It supports a measured
latency improvement for these calls, not a general throughput, tail-latency,
energy-efficiency or long-context claim. The earlier projection was based on a
different milestone prompt; compare the paired measurements here directly.
