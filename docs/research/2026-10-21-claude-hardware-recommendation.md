# Hardware workstream: assessment, candidates and recommendation — 2026-10-21

Owner: Claude. Scope: docs/handoffs/claude-hardware-ownership.md. The full
benchmark sweep was not run; every board session was reserved through
BOARD_STATUS.json and ended with sealed v8 restored and verified.

## Update 2026-10-22: v9d

v9d (`sysone-qwen-decoder-v9d`, package /var/lib/sysone/qwen-fpga-decoder-v9d-candidate1,
archive sha256 e4e920f5…e6fda3) scores two prefill tokens per pass over the on-chip
K/V tile. Each token's arithmetic and order are unchanged, so it is bit-identical to
v9c. C simulation is exact on all 300 reference positions; board smoke 616/616,
worst 2.4e-7.

| Same boot | v8 control | v9c | v9d |
|---|---|---|---|
| Milestone command | 9.174 s | 7.08–7.22 s (earlier session) | 7.024 / 7.090 s |
| 410-token prompt, total | not possible | 21.120 s (same-session control) | **18.305 s (−13.3%)** |
| 410-token prompt, prefill | — | 14.848 s | 12.074 s (−18.7%) |

Generated IDs were identical: v9d matches v8 on the milestone command and
matches the same-session v9c control on the long prompt. The gain is below my
projection (21 s → 15–16 s): attention was about 4 ms of each ~10 ms long-context
prefill call, not the ~7 ms I estimated. Routed: WNS +0.656 ns, WHS +0.010 ns,
LUT 65.4%, CLB 96.2%, BRAM 84.7%, DSP 46.6%. Closing timing needed
congestion-oriented Vivado directives (Explore / AggressiveExplore); v8 to v9c
used the defaults. Evidence: build/v2/qwen-fpga-decoder-v9d/board-evidence-1/.

Updated recommendation: **adopt v9d** if long prompts matter; it is strictly
faster than v9c with identical numerics. Keep **v9c** as the fallback with more
placement headroom (92% vs 96% CLB) for future changes. Either supersedes v9a.

## Recommendation (2026-10-21, before v9d)

1. **Adopt v9c** (`sysone-qwen-decoder-v9c`, package
   /var/lib/sysone/qwen-fpga-decoder-v9c-candidate1, archive sha256
   42f4c1c7…c00dc) as the next deployed decoder, after Codex's evaluation-side
   review. It contains all of v9a's speedup and raises usable context from 256 to
   1024 tokens.
2. If Codex prefers the smallest change to the evaluated system, adopt **v9a
   build 3** (`sysone-qwen-decoder-v9a-b3`) first. It has the same register ABI,
   host layout and 256-token context as v8.
3. **Reject v9b as an add-on** (second weight port). It projects −18% more, but it
   would not fit without a structural LUT reduction first. See
   build/v2/qwen-fpga-decoder-v9b-explore/FEASIBILITY.md.

## Measured results (same Linux boot, same pinned model residency)

| Cold milestone command (62 prompt / 16 output tokens) | v8 control | v9a build 3 | v9c |
|---|---|---|---|
| End to end | 9.140 / 9.141 s | **6.956 s** median of 3 | 7.079 / 7.220 s |
| Prefill layers | 2.987 s | 1.528 s | 1.448 s |
| Decode layers | 2.775 s | 2.033 s | 2.021 s |
| LM head | 0.700 s | 0.698 s | 0.698 s |
| Startup (SHA + tokenizer) | 2.58 s | 2.60 s | 2.82–2.96 s |
| Generated IDs vs v8 | — | identical | identical |

v9c's extra ~0.25 s of startup is host-side, not hardware: it most likely comes
from copying a 4x larger RoPE table (512 KB) with 4-byte /dev/mem writes. A
runtime that writes the table once per boot, or copies it in wider aligned
chunks, would remove it. That is Codex's runtime call.

Context capacity on v9c: a 410-token prompt (impossible on v8) completed with a
correct tool call in 21.12 s (prefill 14.85 s). Layer-0 decode time grows
linearly with position: 4.71 ms at 39, 5.60 at 255, 6.76 at 511, 7.90 at 767,
9.04 at 1023.

Correctness on hardware: v9a build 3 passed 96/96 causal fixture cases (worst
4.8e-7). v9c passed 616/616 cases, including 300 positions across the 256-row
tile boundary in both prefill and decode (worst 2.4e-7).

## Where the time went in v8, and what changed

Offline cycle model (scripts/v2/hw_cycle_model_v9.py, within 3–9% of v8's
measurements): the weight stream runs at ~95% of the 4.0 GB/s port. Most of the
remaining time was serial vector work around it. In prefill this was ~67% of
each layer call: II=3 accumulation loops, FP32 staging copies, quantization at
2.4 cycles/element. Attention at II=3, 4-wide, with 512-byte K/V bursts and two
outstanding reads, was set to match the matrix time at 256 context. v9a fixed
each of these; v9c then tiled attention to lift the URAM context cap. Details:
docs/research/2026-10-21-v9a-hardware-candidate.md.

## Numerical changes (explicit)

Two FP32 summation orders differ from v8: the RMS sum of squares uses four lane
partials, and the attention score uses 16 chunk sums of 8-product trees. v9c adds
the online-softmax merge across 256-row tiles; within one tile it is identical to
v9a. INT8 quantization, Q8 dots and everything else keep v8's arithmetic.
References: scripts/v2/prepare_qwen_fpga_v9a*.py and prepare_qwen_fpga_v9c_long.py.
The latter takes every exp from hls::expf (hls/hls_expf_oracle), because NumPy's
exp differs by 1 ulp and keeps subnormals.

## Resources and timing (routed, 125 / 250 MHz)

| | v8 | v9a build 3 | v9c |
|---|---|---|---|
| WNS / WHS | +0.469 / +0.010 ns | +0.491 / +0.010 ns | +0.622 / +0.010 ns |
| LUT / CLB | 60.0 / 90.3% | 57.9 / 91.4% | 59.2 / 92.3% |
| BRAM / URAM / DSP | 68 / 62.5 / 31% | 72 / 62.5 / 40% | 78 / 62.5 / 41% |

All three builds retain one TIMING-9 (unknown CDC) methodology warning. The
packing analysis (v9a/packing-analysis/README.md) explains why CLB occupancy
ran far above LUT use.

## Unsuccessful attempts and process fixes (all evidence retained)

- Stale HLS export reused old RTL; the consistency check caught it before any
  bitstream was built.
- v9a build 1 missed routed timing by 0.030 ns.
- v9a build 2 halved the matrix rate via an ARRAY_RESHAPE. It was board-measured
  at 10.05 s vs 9.17 s. A new gate, check_hls_ii_v9.py, now fails such builds.
- The v9c reference initially used NumPy exp; this was diagnosed and fixed with
  the hls::expf oracle.
- My smoke script dropped case records from its JSON (the checks still ran).
  The records were recovered from stdout and the script was fixed.

## Limits of these results

One prompt and one output length, 2–3 runs per candidate, one boot. These are
not throughput, worst-case, reliability or quality results. The 410-token run
shows hardware capacity, not semantic quality at long context; that belongs to
Codex's evaluation. Startup (~2.6 s, dominated by the ordered SHA of 639 MB on
the ARM) is now the largest single phase and is a verification-policy question.

## Board state left

v8 `sysone-qwen-decoder-wide-int8` active and verified; BOARD_STATUS revision
16, released. Launcher and services unchanged. Inactive candidates remain on disk
(v9a-candidate1, v9a-candidate3, v9c-candidate1 and their firmware app
directories). Integration notes for Codex: docs/handoffs/claude-to-codex-v9a-integration.md.
