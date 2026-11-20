# v9g: four tokens per attention pass (P=4): PASS on the board, 1.21x over v9f, bit-identical (2026-11-19)

## Result

v9g is v9f with the attention core serving four tokens per pass over the on-chip K/V tile.
v9e and v9f serve two. Every token keeps its own causal row count, max, sum and accumulator,
so its arithmetic and its order do not change. Only the number of tokens sharing each tile
pass does.

| Stage | Evidence | Result |
|---|---|---|
| Cost model (`2026-11-19-core-feasibility.md`) | fits of the v9f pilot timings: attention 41.5% of time, compute-bound at 37 cycles per row per pass | predicted 1.22x end to end |
| Place and route (`build/v2/core-feasibility/p4`) | 125/250 MHz | WNS +0.463 ns, WHS +0.010 ns, bus skew ≥ 3.08 ns. LUT 83.5%, CLB 99.3%, BRAM 113, DSP 749 |
| C-sim audit (`experiments/attention_p4/PROTOCOL.md`), 28 layers | v9f vs P=4 dumps; mixed, rollback and decode schedules; block and 2048-position fixtures | byte-identical; all identical; worst=0 |
| Board pilot (`experiments/attention_p4/BOARD_PROTOCOL.md`), 181 qualification cases | against the v9e records, and v9f pilot timings as the speed baseline | all five rules PASS |

## Board pilot

The pilot ran from 17:56 to 19:29 UTC on boot `62097330…`, with a pre-run hash receipt. It
loaded v9g at runtime and restored RC1.1 on v9e afterwards.

| Rule | Measured | Threshold | Prediction |
|---|---|---|---|
| 1. Exact: tokens, head logit bits, committed K/V SHA, both modes | 181/181 | 181/181 | |
| 2. Same speculation statistics | 170/170 | 170/170 | |
| 3. Single-step median ratio vs v9f | 1.002 | 0.97–1.03 | no change |
| 4a. Prefill speedup vs v9f | **1.223** | ≥ 1.15 | 1.231 |
| 4b. End to end (prefill + speculative decode) vs v9f | **1.214** | ≥ 1.12 | 1.224 |
| 4c. Speculative decode vs v9f | **1.181** | ≥ 1.00 | 1.197 |
| 5. Restore | RC1.1 READY, 639,446,688 bytes verified, `speculate=adaptive` | | |

Totals for the 181 cases:
- prefill: 3,405 s → 2,784 s;
- speculative decode: 930 s → 788 s.

Speculative decode is now **2.27x** faster than plain v9e decoding. v9f was 1.92x and RC1.1 is
1.55x.

| Domain | n | Prefill | Speculative decode | End to end | Decode vs plain v9e |
|---|---|---|---|---|---|
| general | 70 | 1.134 | 1.131 | 1.133 | 1.63 |
| maintenance | 70 | 1.187 | 1.196 | 1.189 | 2.93 |
| long | 20 | 1.327 | 1.283 | 1.322 | 1.95 |
| tool | 21 | 1.021 | 1.021 | 1.021 | 2.88 |
| **all** | 181 | **1.223** | **1.181** | **1.214** | **2.27** |

The gain grows with context length, as the model says: attention cost is proportional to
cached rows. The long domain gains most. The tool domain's short prompts gain almost nothing.

## Board note

The board was found with its root filesystem failing before the pilot:
- the serial console showed journald `Input/output error` every second;
- SSH closed without a banner;
- this was about 16 h into the boot that had run the v9f pilot cleanly.

The root disk is the SD card behind the KR260's onboard USB reader (`sda`). This is the
likely cause of the earlier soft lockups and hangs.

A user-approved JTAG reset brought a clean boot. A new health gate in the queue then
passed: no I/O errors, lockups or USB disconnects in dmesg, and a write probe succeeded.
The pilot ran only after that. The medium is still suspect.

## Next

- **RC1.2 release check:** take v9g rather than v9f into the sealed boot path. That covers
  the package, initializer pins, runtime app name and the batched speculative service, plus a
  reboot and rollback drill.
- **Timing margin:** hold slack is +0.010 ns and CLB use is 99.3%. A full rebuild with a
  different placement seed would show whether the margin is stable before the release.
- **Dual weight port:** the next lever, modelled at about 1.35x on top of v9g. It needs CLB
  space, likely by packing two INT8 products per DSP.
- **SD card:** the root medium threw I/O errors; a filesystem check or replacement is due.
