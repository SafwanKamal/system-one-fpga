# v9g (v9f + P=4 attention): board pilot

Written 2026-11-19, before any board step. It follows the C-sim exactness audit
(`PROTOCOL.md`), which passed:
- the v9f and P=4 dumps are byte-identical;
- the mixed, rollback and decode schedules are identical to prefill8;
- both fixtures report worst=0.

## Image

- v9g is the routed place-and-route trial in `build/v2/core-feasibility/p4`:
  - WNS +0.463 ns, WHS +0.010 ns, bus skew slack ≥ 3.08 ns;
  - LUT 83.5%, CLB 99.3%.
- Its HLS source is byte-identical to `hls/qwen_decoder_v9g/`. Apart from two include
  paths, it is identical to the audited source.
- Its HLS and Vivado scripts equal v9f's apart from directory paths.
- `scripts/v2/package_qwen_fpga_v9g_pilot.py` checks all of this against hashes frozen in
  `build/v2/qwen-fpga-decoder-v9g/hardware-source-sha256.json`.
- The kernel CSR map equals v9e's, so the RC1 runtime drives it unchanged.

## Preconditions

- The user has approved the image swap.
- The board is reserved through `BOARD_STATUS.json`, and RC1.1 is running and READY.

## Sequence

The steps are the same as the v9f pilot (`experiments/batched_head/BOARD_PROTOCOL.md`), with
`swap_v9g.py` and `pilot.py` from this directory. The only change to those scripts is the app
name and compatible string (v9f → v9g).

1. **Drain:** `systemctl stop sysone-rc1.service`.
2. **Swap v9e → v9g:** `swap_v9g.py --direction candidate`. If the load fails, it reloads v9e
   automatically.
3. **Pilot:** `pilot.py` runs the 181-case qualification workload in its original order.
   Each case does one prefill (recorded as `prefill_seconds`), then `ar` and `batched`.
4. **Swap back v9g → v9e:** `swap_v9g.py --direction restore`.
5. **Restore:** start `sysone-rc1.service`; READY gate with a full SHA, then the RC1.1
   `status` and one probe.

If any step fails, go straight to steps 4 and 5. The pilot never changes the RC1 package,
units, launcher or model.

## Decision rules

The baseline for speed is the v9f pilot record (`build/v2/batched-head-board/pilot.json`,
boot `63cbeccc…`). The same workload ran on the same board.

1. **Exact:** for all 181 cases, `ar` and `batched` each equal the v9e qualification records:
   tokens, the head logit bits of every emitted token, and the SHA-256 of the committed K/V
   rows.
2. **Same speculation:** for the 170 `bootb-full` cases, `batched` passes, ar_steps, drafted,
   accepted, zero_accept and gated_off equal v9e `adaptive`.
3. **No single-step regression:** P=4 does not change one-token steps. The median per-case
   ratio of v9g `ar` to v9f `ar` decode time must be within 0.97–1.03.
4. **Gain.** `predict_pilot.py` on the v9f record predicts:
   - prefill 1.231x;
   - batched decode 1.197x (approximate: mean pass size per case);
   - end to end (prefill + batched decode) 1.224x.

   The thresholds, all aggregated over the 181 cases against v9f:
   - (a) prefill speedup at least **1.15**;
   - (b) end-to-end speedup at least **1.12**;
   - (c) batched decode speedup at least **1.00**.
5. **Restore:** RC1.1 READY, all 639,446,688 model bytes verified, probe
   `speculate=adaptive`.

All five PASS: v9g replaces v9f as the candidate for an RC1.2 release check. Any FAIL: the
failing rule and case are recorded. An exactness failure (rules 1–2) rejects P=4 outright. A
gain-only failure keeps v9f as the candidate and is analysed against the cost model.

## Limits

- One board, one workload, greedy decoding. The v9f baseline comes from an earlier boot.
- Timing margins are thinner than v9f's: hold slack is +0.010 ns and CLB use is 99.3%. The
  board run tests this image at room temperature only.
- v9g is loaded at runtime, not through the RC1 boot initializer.
