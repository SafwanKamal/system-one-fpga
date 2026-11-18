# KR260 model scaling

## Next optimization priority (owner request, 2026-10-10)

Implementation in progress: optional `PIPELINED_URAM=1` stores each deep
activation buffer as a whole UltraRAM array with a registered output. The
default split-memory implementation is retained. Consumer read latency is
parameterized across LINEAR, ATTENTION, ADD_SKIP, LAYERNORM, EMBED, POOL and
request output reads; the candidate uses four clocks instead of three. A
matching selector stage keeps bank selection aligned. Port output registers
have a fanout limit of eight to address the prior routed setup failure:
port_data[0][127] to an attention query register, 162 loads and 7.797 ns routing.
The experiment is isolated in `build/v2/kr260-opt-memory`; baseline wide
artifacts and packages remain in `build/v2/kr260-opt-wide`.

The DDR4 adapter already queues request lengths, allows eight outstanding
read bursts, splits at 4 KiB boundaries, and uses bursts of up to 256 beats.
LINEAR already double-buffers weights and overlaps loading, compute and drain.
Keep model weights in DDR4 and hot activations on chip for this experiment.
Measure AXI service gaps, loader backpressure and compute waits before changing
prefetch depth; simulation stalls alone do not establish Linux/shared-DDR
bandwidth or a hard service bound. No DDR4 scheduling change is claimed here.

Optimize the UltraRAM/BRAM/DDR4 memory hierarchy together once the current
768-wide candidate is qualified. Placement currently allocates 24/64 UltraRAM
blocks and 123/144 BRAM tiles; these are placement counts, not final routed
timing or board evidence. Audit buffer packing, access ports and lifetimes to
move suitable deep storage into UltraRAM while retaining small or parallel
tables in BRAM. Investigate optional UltraRAM output registers flagged by
synthesis, align consumer/control latency, and evaluate DDR4 burst reuse,
prefetch and overlap using measured memory stalls. Compare resource use,
routed clock closure and bit-exact cycle counts before selecting a change.
Available UltraRAM alone does not establish usable bandwidth or lower latency.

Timing requirement update: the one-second first-word value is no longer a fixed
acceptance target. Establish a declared timing budget for each supported model,
maximum input/context/output length and operational profile. Record encoder,
memory service, CPU heads and end-to-end timing separately. Empirical maximum
and percentile timing are measurements, not hard worst-case guarantees. A hard
bound requires bounded memory service/arbitration and control flow; host-inclusive
bounds also require a controlled OS scheduling profile. Completion deadlines,
timeout handling and overload behavior belong in that contract. No hard timing
guarantee has yet been established on the shared-DDR Ubuntu configuration.

The measured starting point is the registered-MAC encoder at 124,999,999 Hz:
MiniLM-L12 completes the matched 350-case suite bit-exact, with mean encoder
17.1598 ms versus 29.9905 ms at 71,428,571 Hz. Increasing model capacity requires
separate work from clock optimization. The BRAM-table candidate is still routing.

## Capacity audit

- KR260 has 4 GB DDR4, shared with Linux and the ARM-side application. Source:
  [AMD DS988](https://docs.amd.com/r/en-US/ds988-kr260-starter-kit/Product-Details).
- The established board allocation is 64 MiB, at 0x60000000. The L12 image is
  33,916,928 bytes. Increasing this reservation requires checking the boot DTB,
  Linux/CMA layout, runtime guards and deployment manifests together.
  Software now supports a configurable persistent reservation and automatically
  discovers its size. The first proposed enlargement is 256 MiB at the same base;
  see `scripts/v2/kr260/memory_budget.md`. Board activation now passes after reboot:
  256 MiB discovered, pipeline at 125 MHz and existing L12 exact at eight lengths.
  No larger model or full-region memory sweep has been validated yet.
- The current Vivado block design maps HP0_DDR_LOW only. ZynqMP splits this
  memory into 2 GB low DDR at 0 and 2 GB high DDR at 0x800000000; see
  [AMD UG1137](https://docs.amd.com/r/2024.2-English/ug1137-zynq-ultrascale-mpsoc-swdev/Memory-Overview-for-APU-and-RPU-Executables).
- AXI addresses are 40 bits, but image headers, instruction addresses and run
  descriptor addresses are 32 bits. Widening the external bus alone does not
  make high DDR reachable. The compiler stores absolute addresses.
- MAX_HIDDEN=384, MAX_HEAD_DIM=64 and MAX_TOKENS=128 constrain this bitstream.
  Seven activation buffers hold nine token-by-hidden bytes in total, before
  accumulator/query/score storage and memory primitive rounding. Doubling hidden
  width doubles this logical activation storage; merely changing MAX_HIDDEN does
  not establish resource fit or timing closure.
- LINEAR source_row_reg and destination_row_reg are eight bits. For example,
  a 4096-wide FFN input needs 256 INT8 words per token, which wraps this field.
  These counters need widening and boundary regressions for 1024-wide encoders.
- The deployed encoder is INT8, with full-sequence bidirectional attention.
  It does not implement causal decoder attention, KV caching, rotary embeddings,
  gated FFNs or packed INT4 weights. Generative model support needs a distinct
  datapath/program contract and numerical reference.

## Work order

The first 768-wide candidate is now implemented as an isolated configuration:
`create_project_kr260.tcl -tclargs build optimized 125 bram wide` writes
`build/v2/kr260-opt-wide`. It retains 32x16 MAC tiles, 128 tokens, 64 dimensions
per attention head, registered MAC operands and BRAM softmax tables. Its BUILD
register is 0x20803004, and its separate deployment name is `sysone-v2-wide`.
Defaults and the working 384-wide apps remain intact.

Synthetic H768/A12/FFN3072 one-layer vectors match IntEncoder and ImageMachine
at eight lengths (1,2,3,4,5,12,64,128). The AXI-driven wide RTL matches all
10,512 words, with random memory stalls. The same wide RTL also passes the
existing MiniLM-L12 vectors at all eight lengths (5,256 words), with unchanged
simulation cycle counts relative to the 384-wide BRAM profile. These are
dimension/compatibility tests, not trained 768-model quality measurements.
Hashes and evidence: `build/v2/rtl-wide-check/summary.json`.

Reproduce with `simulation/v2/generate_kr260_wide_vectors.py`,
`simulation/v2/run_kr260_wide.sh` (Verilator 5.040), then
`simulation/v2/summarize_kr260_wide.py`. The full Vivado candidate build is
running via `scripts/v2/kr260/build_wide_candidate.ps1`. It automatically checks
setup and hold at both runtime clocks and packages a passing 100/125 MHz profile
only. Routed resource fit, operating rate and board validation remain pending.
After hardware fit is established, compile/calibrate a trained 768-wide encoder
and evaluate its task quality and timing under a declared workload budget.

1. Complete the BRAM candidate and compare full routed area/timing with the
   hardware-verified MAC candidate. Then reduce the measured activation-read
   fanout (160 sinks on the current worst path), preserving lookup/tag timing.
   Evaluate higher clocks only after setup and hold close; the first placement
   fails 150 MHz, so 150 MHz is a target rather than an approved operating rate.
2. Instrument actual AXI weight bytes, accepted beats and stall cycles. The
   current interface has one outstanding read burst; measure whether request
   gaps or compute dominate before implementing deeper prefetch/multiple reads.
   The old chain_hw_estimate.py's 250 MHz and 10 GB/s KR260 assumptions are
   hypothetical, not measurements of this design.
3. Add a versioned memory contract for high-DDR model storage: either relative
   model offsets plus a 40-bit base or explicit wide addresses. Update compiler,
   reference machine, descriptor decoding, every engine address, driver and
   HP0 high-DDR mapping together. Preserve the established Nexys/v1 format.
   Test addresses beyond 4 GB, 4 KiB burst boundaries and out-of-region rejection
   in simulation before changing the board's memory reservation.
4. Scale activation storage and row counters for a 768-wide encoder first,
   then larger widths. Use a checkpoint with a supported architecture and run
   calibration, integer-reference, full RTL and routed resource/timing checks.
   Spill/tile activation storage into DDR if on-chip storage becomes limiting.
5. For larger answer-generating models, establish a decoder integer reference,
   implement tiled matrix-vector/prefill kernels and KV-cache access, and add
   INT4 weight handling as an independently validated format. Budget weights,
   cache, scratch and Linux memory together. Choose the checkpoint from measured
   compute/bandwidth and quality requirements, not the goal of filling DDR.

## Quantitative limits

The present 32-by-16 MAC array issues at most 512 scalar products per clock:
64 billion products/s at 125 MHz, before stalls and non-matrix operations.
This is a theoretical ceiling, not sustained throughput. A dense 3-billion-MAC
projection workload takes at least about 46.9 ms at that ceiling; applying the
same workload to 128 tokens takes about 6 seconds before attention and overhead.
This example illustrates why storing gigabytes of weights does not guarantee a
particular first-word response budget. Decoder prefill, KV-cache traffic and sustained
DDR bandwidth must be measured separately.

Do not reserve all 4 GB for weights. A useful goal is a measured model-memory
budget, initially hundreds of MiB and eventually a multi-GiB pool when high DDR
and the execution architecture have been validated. No boot-memory change or
new large-model hardware deployment has been performed by this audit.
