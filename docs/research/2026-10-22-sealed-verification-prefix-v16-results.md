# Sealed weight ownership, transition verification and prefix caching

Implemented and measured on KR260, 2026-10-22. Same Qwen3-0.6B Q8_0 weights,
v9d FPGA image, Linux boot, clocks, model profile and task prompts. No FPGA
reprogramming, reboot, legacy package edits, launcher changes or full-sweep
restart. The versioned ABI2 driver replaces the live legacy DMA driver and
reloads the same pinned weights into owned buffers.

## Measured result

All means below are board-local CLI process wall times for six requests per
mode: three short tool prompts, two repeats each. Service startup is separate.

| Mode | Mean seconds | Saving from preceding mode |
|---|---:|---:|
| Persistent service, full SHA each request, no cache | 5.5990 | control |
| Startup/transition SHA, no cache | 3.8894 | 1.7095 s (30.53%) |
| Startup/transition SHA plus prefix cache | 3.1553 | 0.7341 s (18.88%) |

Combined reduction: **2.4437 s/request, 43.65%** versus diagnostic per-request
hashing on the same sealed/read-only implementation. Cache means include the
first request with zero reused tokens. One-time startup ranged 2.957-2.996 s
and includes full verification of all 639,446,688 resident weight bytes.

| Prompt | Diagnostic/no cache | Startup/no cache | Startup/cache |
|---|---:|---:|---:|
| Read /proc/sys/kernel/random/boot_id | 6.0186 s | 4.3234 s | 3.9235 s |
| Read /proc/uptime | 5.5145 s | 3.7724 s | 2.9213 s |
| Read /proc/version | 5.2638 s | 3.5724 s | 2.6211 s |

The cache sequence A/B/C/C/B/A reused 0/40/40/48/40/40 tokens (208 total).
These are sequential calls in one conversation; switching conversations starts
cold because there is one physical KV bank. Reuse does not enlarge context or
reduce allocated FPGA memory. FPGA LUT/CLB/DSP/BRAM/URAM changes are all zero.

## Timing attribution

| Mean component | Diagnostic/no cache | Startup/no cache | Startup/cache |
|---|---:|---:|---:|
| Request weight SHA | 1.6903 s | 0 | 0 |
| Prefill | 1.2598 s | 1.2593 s | 0.5059 s |
| Decode | 2.2832 s | 2.2823 s | 2.2823 s |
| Internal request wall | 5.2844 s | 3.5855 s | 2.8320 s |

Skipping request-time SHA explains the first improvement; skipped prompt work
explains the second. Decode is essentially unchanged in this sample. No energy
measurement or prediction is claimed. The previous v15 mean (5.5772 s) is a
separate run; the matched v16 diagnostic control is the primary baseline here.

## Ownership implementation

`firmware/qwen_dma_v2/sysone_qwen_dma_v2.c` implements:

- One open model owner. A second opener receives EBUSY. Open descriptors and
  surviving VMAs pin ownership and the module.
- Explicit BEGIN_LOAD and SEAL_MODEL operations with monotonically advancing
  generation and a random per-module instance identity.
- Sealing and transitions rejected while any VMA remains; old writable maps
  cannot survive sealing. Sealed mmap rejects write permission and clears
  VM_MAYWRITE, preventing mprotect from restoring write access.
- An inference lease which cannot perform load/unseal operations, even through
  its own descriptor. The device stays mode 0600.
- DMA architecture callbacks preserved by a per-mapping copy of vm_operations,
  wrapping open/close for tracking while retaining original private data and
  the other callbacks. Reference counting covers cloned/split VMAs.

The service owns the inference lock throughout its lifetime. A loader must
acquire that lock and verify AP_IDLE, so it cannot overlap the service. Every
new service instance claims a sealed lease and hashes the complete resident
model before READY. Each generation checks the lease/generation, model/kernel/
boot/package/clock identity. A mismatch faults the session and invalidates KV
metadata; continued inference requires a drained transition and new startup.

The explicit loader validates the source model, copies all bytes, closes all
writable mappings, seals and verifies the resident bytes. The next service
startup verifies again. The benchmark exercised this actual transition:
generation 4 -> 6, same instance and DMA table. No old cache is retained through
that transition.

This controls the DMA device and coordinated loader lifecycle. Administrators
with raw physical-memory, kernel or arbitrary FPGA/DMA access remain trusted.
It does not establish physical memory-fault detection between checks. The
`--verification per-request` diagnostic mode retains that extra full byte check.

## Runtime and cache

Versioned source bundle on target:
`/var/lib/sysone/benchmarks/persistent-arm-service-v16/bundle-r2`.

- `qwen_fpga_runtime_v16.py`: unchanged v9d command/math path, exclusive inference
  lease and read-only startup verification.
- `qwen_weight_verification_v16.py`: same ordered SHA/native-copy pipeline,
  using CPython's buffer API to read sealed mappings without writable exports.
- `qwen_arm_service_v16.py` under src: startup proof, per-request lightweight
  identity checks, diagnostic mode, exact-prefix tracking and counter deltas.
- `qwen_arm_service_v16.py` under scripts: local serialized socket server/client.
  Defaults: startup verification and prefix reuse. `--no-prefix-cache` disables
  reuse; `--verification per-request` enables diagnostic hashing.
- `load_sealed_qwen_v16.py`: explicit source/load/seal/verify transition.
- `firmware/arm_service_v16/`: operating instructions and optional systemd unit.

Prefix caching uses the already qualified v14 tracker. It checks exact token
prefix, ownership/model/kernel/runtime/boot identity and a physical scratch tag.
Reuse rounds down to eight-token boundaries and always recomputes final logits.
Answers are generated afresh. Physical prefill counters must equal prompt
length minus reused tokens. Failed transactions discard pending state. Changed
conversation IDs, explicit reset, tag mismatch and identity changes discard reuse.

## Validation

- 14 focused local tests passed; two stdlib Linux integration checks passed in
  WSL and again on ARM (real read-only mmap hash, tail corruption rejection,
  socket serialization/disconnect/rejection/cleanup).
- Native module build passed against running kernel 6.8.0-1036-xilinx.
- All ten actual DMA negative checks passed: concurrent open, uninitialized
  inference, sealing with live writable mappings, loading with mappings, sealed
  writable mmap, mprotect escalation, loading with read-only mappings, loading
  and sealing through an inference lease, and fd-close-with-live-VMA pinning.
- All 18 timed calls matched exact prompt IDs, generated IDs, output text and
  generated tool calls. They also match preserved v15 controls exactly.
- Four extra hardware cache checks passed: conversation switch, identical
  prompt, explicit reset and changed prefix. Capacity rejection preserved READY.
- All 616 causal checks passed before and after (1232 total), worst absolute
  error 2.384185791015625e-7.
- Actual controlled reload advanced generation and passed full post-seal SHA;
  subsequent service startups recorded full verification at the new generation.
- Final checks verified source and all package hashes, idle FPGA, no service
  processes/sockets, and sealed ownership with owner_tgid=0/vmas=0.

## Preserved first attempt

The first driver candidate conservatively refused an existing kernel DMA VMA
handler with EOPNOTSUPP. Its deployment aborted before neural work and restored
the legacy driver, fully reloaded/verified the model and reinitialized page
tables. The corrected r2 wrapper retains those callbacks; all target checks and
inference gates passed. Initial sources/archive/module, deployment error and
verified rollback remain preserved separately; no failed record was overwritten.

## Evidence and final state

Local raw evidence: `build/v2/persistent-arm-service-v16/evaluation`,
`deployment-r2/deployment.json`, `deployment/deployment.json` (first failure),
`driver`, `rollback`, `attempt1`, SSH receipts and `target-results.tar.gz`.
`evidence-seal.json` and `independent-validation.json` retain hashes/checks.

The live driver is ABI2 with the pinned weights sealed. Services are stopped;
no boot unit was installed or enabled. The new service must use the v16 runtime.
Legacy runtimes require writable weight mappings and are incompatible with the
sealed driver. Old packages, launcher and legacy module binary remain preserved.
The original boot startup has not been migrated to ABI2; current driver/model
residency is for this Linux boot. Canonical board status records this explicitly.

This is a finite, single-boot comparison with six timed requests per mode and
five service sessions. Modes were bracketed, not randomly interleaved; one
declared same-model transition occurred. It establishes the measured savings
for these calls, not tail latency, general workload throughput or energy.

Kernel reference for DMA mapping lifetime: the allocation must remain alive
until user mappings are released ([Linux DMA API documentation](https://www.kernel.org/doc/html/v5.15/driver-api/infrastructure.html)).
