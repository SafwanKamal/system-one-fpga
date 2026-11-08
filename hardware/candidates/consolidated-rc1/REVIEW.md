# Hardware consolidation review — 2026-11-08

## Decision

Use **consolidated-rc1**: the existing v9e bitstream and numerical profile with
the v16 sealed-ownership persistent service and v9e candidate5 scratch-copy
optimization. This is the single integration candidate. Keep v9d as the recorded
recovery configuration and v9c as the lower-placement-pressure fallback. Archive
history in place; no historical source, seal, model, result or board state is
replaced. The combined service requires bounded board qualification before adoption.

## Scope and evidence

Git contained `main` at bc27a36 and `hw/v9-candidates` at e9079d0. Remote head
discovery returned only `main` at bc27a36. There were no separate remote hardware
branches to merge. The hardware alternatives are source-directory branches of the
design. `review-inventory.json` records all 30 decoder/encoder candidate directories
and their source-tree digests, including uncommitted alternatives. Legacy `rtl/`
classifier and `rtl/v2/encoder` implementations are separate model architectures.

Reviewed progression through the implementation sources, adjacent variant diffs,
candidate manifests, hardware recommendation/handoff, and retained reports under
`build/v2/qwen-fpga-decoder-v9*/`. A source-tree digest records the reviewed snapshot;
it does not confer qualification. The working checkout had 32 modified tracked
files plus substantial untracked research, firmware, sources and results. These
remain outside the consolidation commit, except the explicitly selected runtime
dependencies and new candidate files. `HANDOFF.md` and `BOARD_STATUS.json` remain
untouched. No board session, full sweep or new model inference was run.

## Progression disposition

| Implementation | Progress / evidence | Candidate disposition |
|---|---|---|
| Legacy classifier / encoder | Different fixed-output/classification model, arithmetic and transport | Preserve as independent architecture |
| Qwen v1 | Early HLS decoder prototype | Superseded by deployable lineage |
| Qwen v2 | Full FPGA tool-command correctness milestone; reported 232.887 s | Inherit correctness path through later decoder, preserve evidence |
| Qwen v3 | Earlier latency/host optimizations | Superseded; no parallel module to append |
| Qwen v4 | Four-token batched prefill, shared weights, lane selection commands | Inherited and expanded to batch8 |
| Directory v5 | `llama.h` software-reference tooling, not a newer FPGA top | Reference only; no CPU NN in candidate |
| Qwen v6 | Streaming Q8 core, shape profile, larger-model transfer checks; reported 27.430 s milestone | Streaming structure inherited |
| Qwen v7 | Burst-loaded norm/RoPE data, buffered reuse; reported 18.928 s milestone | Inherited |
| Qwen v8 | 256-bit stream, INT8 block32 activations, batch8, paired query heads, quantized input reuse; sealed 9.228 s milestone | Immutable numerical/performance baseline, inherited with explicit later arithmetic changes |
| Qwen v9a build3 | Four vector lanes, packed quantization, shared RMS, 8-wide attention, head-major KV, 256-bit state | Inherited; earlier timing failure and II2 build remain rejected |
| Qwen v9b explore | DSP placement experiment and proposed second HP weight port; cost exceeds demonstrated placement margin | Exclude; no qualified two-port implementation or measured gain |
| Qwen v9c | 256-row tiled online softmax, context1024 | Inherited; fallback at about 92% CLB |
| Qwen v9d | Two prompt tokens per K/V tile pass; same per-token order as v9c | Inherited; recorded live/recovery image, 96.2% CLB |
| Qwen v9e | BF16 RNE K/V, context2048, reduced cache traffic | Selected hardware, 96.07% CLB |
| v9e runtime candidate5 | Aligned 64-byte device writes with scalar tails, optional ABI2 compatibility | Copy improvement inherited; ABI1 fallback removed |
| ARM service v15 / prefix v14 | Resident process and exact-prefix reuse | Inherited through v16 service |
| ARM service v16 | Mandatory sealed ABI2 lease, read-only weights, startup SHA and identity checks | Selected runtime/service ownership policy |

The older reported timings above come from different experiment stages and are
not a controlled across-version benchmark. Source order matters: v9a changes RMS
and score reduction order; v9c adds tiled online softmax; v9e rounds K/V stores
to BF16. RC1 does not claim FP32 equivalence, a new speedup, or semantic quality
at 2,048 tokens. The selected model remains Qwen3-0.6B; larger-model software
capability results do not qualify a larger FPGA port.

## Encoder and typed200 alternatives

All candidate manifests reviewed continue to declare `hardware_qualified: false`:
`counter300`, `locality300`, `typed200`, `typed200_flush`, `typed200_lut_capture`,
`typed200_observe`, `typed200_profile_cache`, `typed200_profile_tree`,
`typed200_validation_tree`, `typed200_predecode`, `typed200_clamp`,
`typed200_stage_clamp`, `typed200_row_range`, `typed200_row_range_csa`.
`typed200_amp`, `typed200_amp_probe` and `typed200_amp_r5_profile` have no
`candidate.json` in their source directories; absence is not qualification.

The 300 MHz variants restructure counters/locality; typed200 adds guarded typed
publication, request epochs and real memory-drain tracking; its successors alter
capture, flush, profile lookup, decode/clamping and row-range paths. AMP/R5 work
changes control/ownership placement. These belong to the encoder service, whose
18-label contract, fixed descriptor/profile and separate CSR ABI cannot be
substituted into the autoregressive decoder. Their firmware/physical evidence
remains preserved. They are excluded from this candidate rather than claimed as
completed decoder features. The useful general ownership concept is represented
by the decoder's existing v16 ABI2 lease; this is not an equivalence claim.

## Review findings and resolution

1. **High: the latest hardware and service did not integrate.** v16 hardcoded
   v9d identity and FP32 cache sizing; v9e's standalone runtime optionally fell
   back to ABI1. Combining them naively would either reject v9e, demand twice
   the cache bytes or weaken startup-only verification's ownership premise.
   RC1 explicitly uses v9e firmware identity and two-byte K/V sizing, requires
   ABI2 before model access, and retains v16's generation/identity checks.
2. **Medium: device-memory bulk copies can fault.** The retained candidate2/4
   failures show SIGBUS from bulk memset/DC ZVA and unaligned tail stores.
   RC1 uses candidate5's full aligned 64-byte calls and scalar word tails.
   Linux tests check bytes, boundaries and issued store formats; historical
   board evidence separately validates those transfers on actual device memory.
3. **Medium: the old II gate counted exceptions rather than identifying them.**
   A matrix II2 regression could fit inside its allowance of two misses.
   The RC1 packager requires exact loop names for the two recorded residual
   exceptions and rejects any other target miss. The historical checker remains
   unchanged; use the RC1 gate for this candidate. Source/log hashes bind loop
   labels to the reviewed build; a changed build needs fresh reviewed exceptions.
4. **Medium: package metadata contradicts implemented precision.** v9e's
   `build.json` says FP32 in `kv_cache_layout` while its cache field and code
   specify BF16; packaging documentation also mentions 1024 instead of 2048.
   RC1's manifest/README identify BF16 and 2048 explicitly while preserving the
   historical metadata unchanged for provenance.
5. **Remaining physical constraint:** CLB occupancy is 96.07%, despite only
   66.10% LUT use. Extra datapaths are not justified by unused LUT percentage.
   Keep the exact routed image; new structural changes need new implementation.
6. **Remaining evidence gap:** independent arithmetic and causal fixtures prove
   the implementation against its chosen reference, not broad model reliability
   or BF16 semantic equivalence. The combined persistent service has no new
   board timing/result yet. Do not add its component speedups together.

## Evidence retained and verification

The pinned v9e release reports routed WNS +0.542 ns, WHS +0.010 ns and minimum
bus-skew slack +3.028 ns at 125/250 MHz; utilization is 66.10% LUT, 96.07% CLB,
84.72% BRAM, 62.50% URAM and 46.63% DSP. Retained TIMING-9 CDC/methodology warnings
are not erased by timing closure. The bitstream SHA256 is
`824d99571dae7412ab684d8bab8a9900954e8adca1a624963b4a3b92d034c61f`.

Historical board evidence reports 4,112/4,112 causal checks with worst absolute
error zero against the BF16 reference. Candidate5 standalone runs were 6.949 /
6.855 s with ABI2 and identical generated IDs to earlier v9e runs. These runs
predate consolidation and are not measurements of RC1's persistent service.

Fresh verification is recorded in `validation.json`: host and Linux lifecycle,
context-boundary, prefix, weight-corruption, socket-lock and scratch-transfer
checks; pinned historical package/source/export/timing checks; and the offline
package receipt. Local C-simulation attempts/results are stated separately from
historical synthesis and board evidence. No new routed build is necessary for
the unchanged FPGA image. Exact source line endings are declared in
`.gitattributes` so candidate source hashes survive cross-platform checkouts.

Before deployment/adoption, follow the README's canonical board reservation and
bounded smoke/parity procedure. Preserve the active v9d recovery package, driver,
launcher and boot behavior unless a separately recorded operation changes them.
