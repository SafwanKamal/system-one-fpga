# v9f batched head: board pilot

Written 2026-11-18, before any board step. It follows the C-sim audit (`PROTOCOL.md`):
PASS, 30/30 lanes identical over the full vocabulary, and 0 reducer mismatches.

## Preconditions

- The v9f bitstream is built from the audited source (kernel SHA `ae90d997…`), and routed
  timing is met at 125/250 MHz.
- The user has approved the image swap.
- The board is reserved through `BOARD_STATUS.json`, and RC1.1 is running and READY.

## Sequence

1. **Drain:** `systemctl stop sysone-rc1.service`. The image and the sealed weights stay resident.
2. **Swap v9e → v9f:** `swap_v9f.py --direction candidate`. This follows the v9e deployment
   swap (`xmutil unloadapp` / `loadapp`). It takes the lock non-blocking, checks the decoder
   is idle and no MMIO client is live, and requires the DMA residency table to be unchanged.
   If the load fails, it reloads v9e automatically.
3. **Pilot:** `pilot.py` runs the qualification workload (181 cases, original order) on v9f.
   Each case does one prefill, then `ar` (plain steps) and `batched` (adaptive speculation,
   one cmd 11 + cmd 12 head scan per verify pass), in alternating order.
4. **Swap back v9f → v9e:** `swap_v9f.py --direction restore`.
5. **Restore:** `systemctl start sysone-rc1.service`. Its ExecStartPost READY gate runs a
   full startup SHA, then the RC1.1 installer `status` and one probe follow.
   `BOARD_STATUS` is recorded ready.

If any step fails, go straight to steps 4 and 5. The pilot never changes the RC1
package, units, launcher or model.

## Decision rules

1. **Exact:** for all 181 cases, `ar` and `batched` each equal the v9e records from the
   qualification boots (`bootb-full`, `bootc-resume`). That covers tokens, the head logit bits
   of every emitted token, and the SHA-256 of the committed K/V rows.
2. **Same speculation:** for the 170 cases recorded in `bootb-full` (the same sequence from
   case 0, so the gate state is the same), the batched run's passes, ar_steps, drafted,
   accepted, zero_accept and gated_off equal v9e `adaptive`. Only the head work may differ.
3. **No regression:** the median per-case ratio of v9f `ar` to v9e `ar` decode time is
   within 0.97-1.03.
4. **Gain:** the aggregate decode speedup, sum(v9e `ar`) / sum(v9f `batched`), is at least
   1.75 over all cases. A replay of the qualification command timings predicted 1.91; v9e speculation measured
   1.554.
5. **Restore:** after step 5, RC1.1 is READY with all 639,446,688 model bytes verified, and
   the probe generation reports `speculate=adaptive`.

All five PASS: v9f qualifies for an RC1.2 release check, a separate protocol in the
style of RC1.1's (sealed package update, boot path, rollback drill). Any FAIL: v9e stays,
and the failing rule and case are recorded.

## Limits

- One board, one prompt workload (the qualification's), greedy decoding.
- v9f is loaded at runtime here, not through the RC1 boot initializer. Boot integration
  belongs to the RC1.2 release check.
