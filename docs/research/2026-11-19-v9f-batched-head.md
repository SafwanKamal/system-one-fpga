# v9f: batched vocabulary head for speculative verification (2026-11-18/19)

## Result: PASS at every stage, decode speedup 1.55x → 1.92x, bit-identical

RC1.1's speculative decoder verifies up to 8 drafted tokens in one batched decoder pass. It
then scanned the 165 MB vocabulary head once per kept token. v9f adds two kernel commands:
- **cmd 11:** final norm for all slots.
- **cmd 12:** scores every slot in one pass over the head weights, with one running argmax
  per slot.

The 8-slot Q8 multiply array that the batched decoder already uses serves the head too. The
only new hardware is a per-slot compare in the row reducer.

| Stage | Evidence | Result |
|---|---|---|
| C-sim audit (`experiments/batched_head/PROTOCOL.md`), full model, 28 layers | 30 lanes over the full 151,936-row vocabulary, including 6 rejected-draft lanes, compared with the v9e cmd 9/3/4 path; 24 first-8192 winners compared with the v9e audit; crafted tie/±0 reducer test | **30/30 identical** (token and logit bits); 24/24; 0 mismatches |
| v9e regression C-sim (release flow) | block fixture (8 batch lanes) and 2048-position long-context fixture | worst error 0 for both |
| HLS / routed | same II warnings as v9e; WNS +0.671 ns (v9e +0.542), hold met | LUT 66.1% → 66.7%, CLB 96.1% → 96.5%, BRAM/DSP unchanged |
| Board pilot (`BOARD_PROTOCOL.md`), 181 qualification cases | each case checked against the v9e qualification records | all five rules PASS |

Board pilot rules:
1. **181/181 identical:** tokens, head logit bits and committed K/V SHA, for both plain and
   batched speculative decoding.
2. **170/170 equal speculation statistics:** passes, drafted, accepted and gated_off equal
   v9e's. Head scans fell to exactly passes + AR steps (2,756).
3. **No regression:** the plain-decode median ratio of v9f to v9e is 1.002.
4. **Gain:** aggregate decode speedup against plain decoding is **1.919**. The threshold was
   1.75 and the timing replay predicted 1.91.
5. **Restore:** RC1.1 restored on v9e: READY, all 639,446,688 bytes verified, probe
   `speculate=adaptive`.

Decode speedup against plain v9e decoding:

| Domain | n | v9e speculation (RC1.1) | v9f batched head | v9f / v9e speculation |
|---|---|---|---|---|
| general | 70 | 1.262 | 1.441 | 1.14 |
| maintenance | 70 | 1.821 | 2.450 | 1.35 |
| long | 20 | 1.343 | 1.518 | 1.13 |
| tool | 21 | 1.902 | 2.819 | 1.48 |
| **all** | 181 | 1.554 | **1.919** | **1.24** |

The median per-case speedup is 1.76. The slowest case is 0.59, a long case where drafts
were mostly rejected; the gate is unchanged from RC1.1.

## Why it works

The v9e kernel's per-slot arithmetic does not depend on how the host groups positions. That
was established in the schedule-invariance audit, and the C-sim and board results here confirm
it for the head. Scoring all lanes in one weight pass therefore cannot change any slot's
winner or logit bits. The head is weight-stream bound, so the extra slots cost almost nothing.

## Board note

The pilot ran after a user-approved JTAG reset. Before that, the board had hung twice:
- **Idle on RC1.1:** userspace stopped and CPU cores dropped out (seen as Reset Catch over
  JTAG).
- **Minutes after the first reset:** the previous boot's journal ends with `watchdog: BUG:
  soft lockup - CPU#1 stuck for 26s`.

The root filesystem is on USB storage, and `usb-storage` was in D state during startup I/O.
The cause is not fixed; it is unrelated to v9f, because both hangs came before any v9f
step. After the third reset the board ran the full pilot, swap and restore without
incident.

## Next

- **RC1.2 release check:** v9f in the sealed boot path (package, initializer pins, runtime
  app name), the batched spec service, and a reboot and rollback drill, in the style of
  RC1.1's.
- **Gate retune:** a verify pass now costs one head scan, so the 0.25 gate threshold and the
  draft length chosen for v9e costs could be revisited. Any change must stay pre-registered,
  and it changes speed only, never output.
- **Board stability:** investigate the soft lockups (USB root filesystem, HDMI console).
