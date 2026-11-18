# Persistent ARM runtime review

Prepared 2026-10-22 from local sources and saved receipts. No board access,
deployment, frozen-source modification, or benchmark restart was performed.
Canonical board status revision 30 records an ongoing v9d experiment, not a new
verified observation. v9e source exists but its performance is not substituted
for the measured v9d results below.

## Finding

A persistent ARM service is primarily a lifecycle change. It requires no FPGA
rebuild and saves zero synthesized LUT, CLB, DSP, BRAM or URAM resources. The
existing benchmark already demonstrates a persistent engine/tokenizer lifecycle.
The standalone command runner still constructs and destroys both per request.
The model weights are already resident in DMA memory: do not describe this as
eliminating model loading on each request.

## Source map

- scripts/v2/run_qwen_fpga_command_v9d.py:30-87: per-command lock, parallel
  engine/tokenizer construction, prompt-file encoding, forced cold prefix,
  inference, tool execution, and final engine close.
- src/sysone/v2/qwen_fpga_runtime_v9d.py:57-153: profile/device/clock checks,
  DMA open, full resident-weight hash, MMIO/scratch mappings, prefix tag reset,
  page table/RoPE copies and hardware initialization.
- src/sysone/v2/qwen_fpga_runtime_v9d.py:155-161: intentionally aligned scalar
  stores into device-mapped scratch; generic memcpy is not a safe replacement.
- src/sysone/v2/qwen_fpga_runtime_v9d.py:185-241: per-command barrier and 50 us
  polling, Python layer scheduling, 8192-row output-head commands.
- src/sysone/v2/qwen_tokenizer_v1.py:12: compiled-tokenizer hash/unpickle and
  tables; encode_text already avoids temporary prompt files.
- scripts/v2/run_retention_comparison_v13.py:43-57: CandidateFPGA retains one
  engine and Vocabulary across requests and closes at session end.
- scripts/v2/run_prefix_comparison_v14.py:12-32 and
  src/sysone/v2/prefix_cache_v14.py:2: existing in-memory prefix tracker,
  physical tag check, eight-token alignment and actual-work counters.
- firmware/qwen_dma_v1/sysone_qwen_dma_v1.c:21-45: DMA mmap is writable;
  SYNC_COMMAND performs dma_wmb(), not integrity verification or ownership.

## Concrete implementation

1. Add a new service module rather than changing sources frozen by the ongoing
   v13/v14 experiments. Use an explicit package/runtime adapter; the preserved
   v8 launcher must not be used against v9d hardware.
2. Create a service-scoped session containing exactly one QwenFpga, Vocabulary
   and PrefixCache. Verify package/profile/image/clocks/resident bytes once at
   admission to the session, initialize page table/RoPE once, then mark ready.
   Close only after the worker is quiescent on shutdown. A first request still
   pays startup if the service has not already reached ready.
3. Expose a bounded local Unix-socket request API and one serialized inference
   worker. Convert the CLI into a client. Keep tokenization, parsing and existing
   tool allowlisting in software; keep all NN arithmetic on FPGA. Preserve
   each endpoint's current completion policy (typed-prefix completion versus
   complete EOS response); persistence must not silently change that policy.
4. Hold /run/lock/sysone-inference.lock for the service's hardware ownership
   lifetime. Deployment and other direct clients must stop/drain the service
   before taking ownership. The advisory lock alone does not prevent arbitrary
   privileged writes. An unbounded daemon must not inherit an experiment's
   board reservation indefinitely: integrate service ownership explicitly into
   board/deployment coordination when deploying it.
5. Reset per-request buffers, result state and pending cache metadata; report
   counter deltas because engine counters accumulate across the session.
   Validate prompt plus output capacity before launch. Use encode_text directly;
   write prompt artifacts only when requested for diagnostics.
6. Use PrefixCache rather than runtime begin_prefix(enabled=True), which reads
   package-local JSON and does not itself enforce eight-token reuse alignment.
   Preserve physical tags, exact identity, final-token recomputation and invalidation
   on exceptions. Commit only a completed engine transaction; semantic answer
   correctness must not determine whether KV is valid. One physical KV bank
   supports one active cached sequence. On conversation switches, start cold
   unless explicit KV save/restore is implemented and measured.
7. Add STARTING/READY/BUSY/FAULTED/DRAINING states. A request validation error
   need not kill a healthy session. A hardware timeout or uncertain in-flight
   state must fault the session, invalidate reuse and prevent another launch;
   client disconnect must not free buffers while hardware still runs. Do not
   blindly restart inference after the current 120-second command timeout.
8. Record queue, tokenization, prefill, decode, tool and end-to-end timings
   separately from one-time startup. On-demand health checks should verify the
   current image/clock/identity without issuing inference concurrently.

## Verification policy: two distinct service options

The current constructor hashes all 639,446,688 resident bytes per construction.
Persistence naturally moves this check to session startup; that is a verification
policy change, not proof that weights cannot change afterward. A held DMA file
descriptor pins the module but does not make its buffers immutable. Identity
hashes and inode checks also do not detect in-place weight writes.

Option A preserves a full hash before every request. Extract verification into
an explicit method, keep tokenizer/mappings/RoPE resident, serialize hashing
with hardware work and retain the same fail-on-mismatch semantics. This offers
smaller savings without changing the per-request byte-check boundary.

Option B verifies at session start and after every controlled model/image/DMA
transition. Use a single writer/loader lifecycle, unload/reload invalidation,
restricted device access and preferably a driver-managed sealed model state
with a generation identifier. Sealing must account for already writable VMAs;
rejecting only future writable mappings is insufficient. Privileged /dev/mem
writers remain outside such a driver's protection. Neither option guarantees
detection of every physical memory fault between checks. Runtime policy must
state its actual boundary. A sealed driver is ARM software, not FPGA fabric.

## Latency estimates

Measured source: build/v2/qwen-fpga-decoder-v9d/board-evidence-1.

| Receipt | Measured total | Measured startup | Total minus startup |
|---|---:|---:|---:|
| 05-command-v9d-1.json | 7.090 s | 2.891 s | 4.199 s |
| 06-command-v9d-2.json | 7.024 s | 2.827 s | 4.197 s |
| 07-long-prompt-v9d.json, 410 prompt tokens | 18.305 s | 2.841 s | 15.464 s |

For a ready service using option B and identical cold-prefill work, use
approximately 4.2-4.5 s as a provisional short-command engineering target,
versus 7.0-7.1 s measured. The exact arithmetic ceiling from startup removal is
40.2-40.8% less time, or 1.67-1.69x throughput for serial identical calls.
The target range allows unmeasured service/check overhead and is not a measured
service result. Long-command startup removal is about 15.5%, before overhead.
Queueing is excluded from those targets; a loaded service can have larger
end-to-end tail latency. Startup remains real work, amortized over requests.

For option A, the existing short-command SHA cost is 1.68-1.69 s. A simple
estimate is 4.20 + 1.69 = 5.89 s plus new service overhead. A provisional target
of roughly 5.9-6.2 s implies approximately 0.8-1.2 s saved. It needs measurement:
constructor setup currently overlaps tokenizer construction, and device/page
table/RoPE timing is not individually instrumented. Do not add the measured
0.69-0.76 s vocabulary time to full startup savings; they overlap.

No startup saving should be credited again against v13/v14 warm request
timings: those benchmark workers already amortize engine/tokenizer setup.
Saved startup records are 2.838 s (v13 evaluation) and 2.796 s (v14 qualification),
including 1.703 s and 1.676 s resident verification respectively.

Prefix caching is a separate, workload-dependent saving. Completed v14 FPGA
qualification passed all 12 exact generated-ID comparisons; it evaluated 2358
tokens and reused 1896. Examples from its paired saved output records:

| Qualification case | Reused tokens | Warm cold-prefill call | Warm cached call |
|---|---:|---:|---:|
| qualification-01 | 128 | 7.977 s | 4.980 s |
| qualification-06 | 216 | 10.303 s | 4.872 s |
| qualification-09, near-capacity | 880 | 41.883 s | 7.994 s |

These deliberately selected validity fixtures are not a representative workload
speedup. Invalidated/reset cases reused zero tokens. Decode remains fresh and
cached tokens still occupy the context window. The broader v14 run was still
recorded as running when inspected; no final campaign claim is made here.

## FPGA resources and follow-up experiments

Persistence and prefix tracking remove no synthesized resources: delta LUT,
CLB, BRAM, URAM and DSP are all zero with the same bitstream. Prefix reuse saves
executed work and DDR traffic, not allocated KV capacity. Moving tokenization,
parsing or tool handling to ARM cannot free fabric because they already run there.
The current 639 MB model allocation is also already resident; it is not new
service memory. Keeping Vocabulary alive increases idle ARM memory versus an
exited client; measure RSS rather than inventing an estimate.

The v9d report records CLB 96.2%, LUT 65.4%, BRAM 84.7%, DSP 46.6%. Freeing
fabric requires a separate hardware partition experiment and routed comparison.
There is no defensible percentage saving from moving RMSNorm/softmax/argmax
without identifying shared hardware and resynthesizing. Output-head matrix
projection remains large even if its final comparison is moved to ARM.

After lifecycle changes, optionally benchmark a native command-launch/polling
helper. The short receipts contain 989 commands; 989 x 50 us is 49.45 ms, only
a scale indicator, not a strict Linux scheduling bound or promised saving.
The 2265-command long call gives 113.25 ms on the same basis. Avoid busy-spinning
without measuring ARM energy. Retain the DMA write barrier, which is required
for ordering and is not an expensive full-weight cache flush in this driver.
Prepacking layer descriptors can remove repeated Python struct.pack allocations;
its latency contribution is unmeasured and excluded from the estimates.

## Minimal validation before deployment

Use a separately versioned candidate. Compare identical token IDs, completion
policy and generated IDs against current controls; exercise repeated unrelated
requests, exact/changed prefixes, conversation switches, capacity rejection,
client cancellation and faulty/timeout shutdown. Verify model reload invalidates
the session and cache. Measure cold service startup, warm uncached requests,
cached requests, queue delay and RSS separately. Preserve board reservation and
kernel-lock protocols; these offline estimates require no live board session.
