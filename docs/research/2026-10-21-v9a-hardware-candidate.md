# v9a hardware candidate: vector-path, attention and K/V rework — 2026-10-21

Owner: Claude hardware workstream. Status: **validated candidate, recommended for
adoption**, pending Codex's evaluation-side review. Not a benchmark sweep.

## Result

Same Linux boot (e9728928-307d-485b-b40b-63fa29d9296d), same pinned Q8_0 model
residency, same cold command as the v8 milestone, run back to back:

| | v8 control | v9a build 3 (median of 3) | change |
|---|---|---|---|
| End to end | 9.140 s | **6.956 s** (7.030 / 6.956 / 6.952) | **−23.9%** |
| Prefill layers (cmd 8) | 2.987 s | 1.528 s | −48.9% |
| Decode layers (cmd 2) | 2.775 s | 2.033 s | −26.7% |
| LM head (cmd 4) | 0.700 s | 0.698 s | unchanged |
| Startup (incl. ordered SHA ~1.69 s) | 2.582 s | 2.601 s | unchanged |

Generated IDs were identical to v8 in all three runs; the tool executed and
returned the live boot ID. Decode-layer time vs position (layer 0, single token):
4.69 ms at 39, 4.84 at 63, 5.08 at 127, 5.40 at 191, 5.68 at 255. The offline
cycle model predicted 5.72 ms at 255 and 7.0–7.4 s end to end.

## What changed (hls/qwen_decoder_v9a)

- Attention: 8-wide score and value accumulation at II=1 (v8: score II=3,
  4-wide); chunk-major scoring with >=16-row padding and a declared dependence
  distance; head-major K/V cache so each head is one contiguous burst.
- State AXI port 128 -> 256 bits, 8 outstanding reads.
- Quantization reads activations directly (FP32 staging copy removed), four
  lanes per cycle in three passes, packed into one 256-bit BRAM word per block.
- Norm, RoPE, residual and output copies move four lanes per cycle.
- One shared RMS engine (v8 instantiated four copies).
- Matrix core: identical INT8 arithmetic; v9a's copy adds `accumulate_q8_packed`
  that reads the packed input word once per token and block.
- Register ABI, host scratch layout and commands unchanged from v8.

## Numerical changes vs v8 (explicit)

- RMS sum of squares: four lane partial sums combined (l0+l1)+(l2+l3).
- Attention score: 16 sequential chunk sums, each a balanced 8-product tree.
- Everything else (INT8 quantization, Q8 dots, softmax, value accumulation,
  SwiGLU, residuals) keeps v8's order. Max-abs uses integer compares on |x| bit
  patterns: identical for finite inputs.
- Reference: scripts/v2/prepare_qwen_fpga_v9a.py and _long.py (exact order).
  Against v8's reference, the order change flips one INT8 rounding at fixture
  positions 5 and 7 (≈2e-3); reproduced in NumPy, so arithmetic, not a defect.

## Verification

- C simulation: 8-token fixture worst 2.4e-7; 40-position fixture (5 prefill
  groups + 40 decode steps) worst 4.8e-7.
- Routed (build 3): WNS +0.491 ns, WHS +0.010 ns, all constraints met at 125 /
  250 MHz; bus-skew slack +2.815 ns; LUT 57.9%, CLB 91.4%, BRAM 72.2%, URAM
  62.5%, DSP 39.7%. TIMING-9 (unknown CDC) retained, as in v8.
- Board causal smoke: 96/96 cases (block prefill, long prefill, long decode),
  worst 4.77e-7, all finite.
- Hashes: build/v2/qwen-fpga-decoder-v9a/hardware-source-sha256.json,
  ip-rtl-consistency.json (Vivado-imported RTL verified), package archive
  sha256 1a0317cb50aadb3ee782cf5f824cb8397ba884bfc8fe63887c740c3e5d5c64f2.

## Unsuccessful attempts (retained)

1. Stale export (`STALE-EXPORT-1.md`): export_design reused old RTL; caught by
   the consistency check, Vivado stopped, no bitstream.
2. Build 1 (`timing-fail-1/`): routed WNS −0.030 ns in the quantize max-abs
   pass; CLB 96.2%. Fixed by moving the 4:1 compare to the next pass.
3. Build 2 (`build2-matrix-ii2/`, `board-evidence-1/`): packing fixes worked
   (CLB 84.9%) but an ARRAY_RESHAPE made the matrix accumulator II=2. On board:
   correct, 10.050 s vs v8 9.173 s. Gate added: scripts/v2/check_hls_ii_v9.py.
4. Reference fidelity (v9c work): NumPy exp differs from hls::expf by 1 ulp and
   in subnormal flushing, which flipped INT8 rounding at position 118 of a
   300-position fixture. References now take exp from hls/hls_expf_oracle.

## Packing analysis

build/v2/qwen-fpga-decoder-v9a/packing-analysis/README.md: CLB occupancy was
driven by carry chains, four duplicate RMS engines and the 256-bank LUTRAM
input buffer, not LUT count.

## Board state left

v8 `sysone-qwen-decoder-wide-int8` active and verified (BOARD_STATUS revision 8,
released). Launcher and services unchanged. Inactive candidates on disk:
/var/lib/sysone/qwen-fpga-decoder-v9a-candidate1 and -candidate3,
/lib/firmware/xilinx/sysone-qwen-decoder-v9a and -v9a-b3.
Evidence: build/v2/qwen-fpga-decoder-v9a/board-evidence-3/.

## Limitations

One prompt, one output length, three runs on one boot: not a throughput,
worst-case or reliability result. Context remains 256 (v9c addresses this).
The ~2.6 s startup (ordered SHA of 639 MB on the ARM) is unchanged and is now
the largest single phase.
