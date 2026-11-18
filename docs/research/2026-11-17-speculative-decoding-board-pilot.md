# Bit-exact speculative decoding on RC1: board pilot (2026-11-17)

Pre-registered in `experiments/spec_pilot/PROTOCOL.md`; offline precursor
`experiments/schedule_invariance/` (C simulation, all 28 layers, PASS).
Raw results: `build/v2/spec-pilot/board-20261117/{pilot.json,analysis.json}`.

## Result

**Correctness: PASS, 27/27 cases bit-identical.** On the unchanged RC1 bitstream
(v9e, 125/250 MHz), host-only speculative decoding emitted exactly the tokens,
the head logit bits for every emitted token, and the SHA-256 over every
committed K/V row (all 28 layers, K and V, all heads) that ordinary one-token
decoding emitted. Prompts ran 219–867 tokens, with up to 96 new tokens, and
rejected draft rows were left in the cache and overwritten later.

**Speed (decode phase, time-weighted; prefill identical in both modes, 333.3 s each):**

| Domain | Cases | Tokens | AR s | Spec s | Speedup | Tokens / weight pass | Draft acceptance |
|---|---|---|---|---|---|---|---|
| maintenance | 12 | 760 | 172.1 | 107.1 | **1.61x** | 2.74 | 47.7% |
| tool call (RC1 service prompt) | 3 | 47 | 7.9 | 5.4 | 1.45x | 2.00 | 31.4% |
| general | 12 | 366 | 75.7 | 64.1 | 1.18x | 1.67 | 21.1% |
| all | 27 | 1173 | 255.7 | 176.7 | **1.45x** | | |

Per case, speedup ranges from 0.93x (general, 42 tokens) to 2.12x (maintenance, 96 tokens).
Six general cases ran slightly slower than plain decoding: when no draft is accepted,
the batched pass plus a head scan costs more than a single step.

**Decision rule:** maintenance at 1.61x is above the pre-registered 1.10x kill
line, so the host-only route continues.

**Cost model check:** the replay model, with constants fixed before the run, predicted
median per-case speedups of 1.71x for maintenance and 1.09x for general. The board
measured 1.62x and 1.03x, so the model is slightly optimistic. Measured plain decode
cost 214–230 ms/token at these context lengths, against the model's 170 ms.

## What this shows and does not show

- It shows the property a GPU stack does not give by default: verification
  batches and rollback leave the arithmetic bit-for-bit unchanged on the deployed hardware.
- One board, one boot, greedy decoding only, 27 cases. This is not a reliability sweep.
- The head is still scanned once per checked lane (44 ms each). A batched head
  plus a second weight port is the next hardware lever: the replay model puts
  maintenance near 2.9x with a batched head. This needs a new bitstream.
- The drafter is prompt or history lookup. The gains depend on repetitive outputs, which
  maintenance and tool traffic have and free-form general text has less of.

## Board recovery during this pilot

The first pilot attempt found the board off the network. Its root filesystem on
the 116 GB USB card was corrupted: file data had been written over inode tables,
`libpam.so.0` was damaged, systemd could not start, and the kernel panicked on
init exit 127. Evidence: `build/v2/spec-pilot-board-20261117/` (console logs,
read-only `fsck`).

The card was reflashed with the official Ubuntu 24.04 Kria x07 image. The image
was written and then read back, and its SHA-256 matched. RC1 was restored from pinned
artifacts with `experiments/kria_recovery/restore_rc1.py`:
- 256 MiB `sysone@60000000` reservation through `/etc/sysone/kr260-memory.json` and kernel hooks;
- kernel `6.8.0-1036-xilinx`, with the meta packages held;
- v9e app, RC1 package, `rc1-default-v1` boot bundle, units and launcher, every file hash verified.

The boot initializer loaded, sealed and verified the model. RC1 reported READY, and tool
queries matched the 8 November token IDs. Only a partial (~56 GB) image of the
corrupted card was kept (`C:\kria-recovery`). The card that corrupted itself is
still in use; it should be replaced if any further I/O errors appear.
