# Speculative decoding on RC1: qualification and service integration (2026-11-18)

Pre-registered in `experiments/spec_service/PROTOCOL.md`: rules written before any
board run, plus Amendments 1–2 and two addenda, each written before the run it
governs. It follows the 2026-11-17 pilot
(`docs/research/2026-11-17-speculative-decoding-board-pilot.md`, 27/27 identical).
Raw results are in `build/v2/spec-qual/board/`:
- `bootb-full/qual.json`: 170 cases;
- `bootc-resume/qual.json`: 11 cases;
- `boota-partial-qual.json`: 55 cases from the first boot;
- `e2e.json` and `analysis.json`.

Hardware is unchanged RC1: the v9e bitstream and the sealed package
`hardware-consolidated-rc1-20261108`. There was no programming and no change to the RC1
package, launcher or default service.

## Result: all pre-registered rules pass

| Rule | Result |
|---|---|
| 1 Exactness: `ar` and `adaptive` give identical tokens, head logit bits and committed-K/V SHA-256 | **PASS 181/181** |
| 2 Cross-boot: second boot equals the first, bit for bit, in both modes | **PASS 55/55** |
| 3 Service: `spec_service --speculate off` and `adaptive` equal the installed RC1 service (ids, text, executed tool) | **PASS 21/21 in each mode** |
| 4 Speed: domain ≥ 1.00, maintenance ≥ 1.10, ≤ 5% of non-long cases below 0.95x | **PASS**, no case below 0.95x |
| 5 Head share in maintenance (commands 3+4+9 as a share of adaptive decode FPGA time) | **35%**, at least 30%, so the batched-head bitstream is the next lever |
| 6 Service latency (median client time per tool query) | RC1 2.61 s, `off` 2.61 s, `adaptive` **1.64 s** (1.60x) |

Decode phase, time-weighted (prefill is shared by both modes):

| Domain | Cases | Tokens | AR s | Adaptive s | Speedup | Median case | Min case | Tokens / weight pass | Acceptance | Gated off |
|---|---|---|---|---|---|---|---|---|---|---|
| maintenance | 70 | 4279 | 982.7 | 539.8 | **1.82x** | 1.75 | 1.16 | 3.70 | 54% | 23 |
| tool (RC1 prompt) | 21 | 308 | 55.4 | 29.1 | **1.90x** | 1.95 | 1.32 | 3.28 | 56% | 0 |
| general | 70 | 2275 | 492.7 | 390.5 | 1.26x | 1.05 | 0.96 | 1.93 | 24% | 38 |
| long (1.2–1.7k prompt) | 20 | 822 | 254.1 | 189.2 | 1.34x | 1.22 | 0.44 | 2.52 | 35% | 11 |
| all | 181 | 7684 | 1784.9 | 1148.6 | **1.55x** | | | | | |

Compared with the pilot:
- **Gate:** the adaptive gate removed the pilot's slow general cases. The pilot's minimum was
  0.93x; here the worst non-long case is 0.96x.
- **Cross-request history:** this raised maintenance from 1.61x to 1.82x.
- **Long contexts:** these are reported separately, as pre-registered. One synthetic
  long case ran at 0.44x, where drafts kept failing. Long prompts are not the service
  workload, but the gate's probe rate would need work before enabling speculation for
  them.

Head share: in plain decoding the head (norm, head scan and lane copies) is about 19% of
maintenance decode time. Speculation cuts the layer passes, so the head's share rises to
35% (47% on tool queries). The v9e head scans 8,192-row chunks one lane at a time. A
bitstream that scans every lane in one pass over the head weights is now the largest
remaining cost, and this is the measured case for building it.

## Deviations (all written into PROTOCOL.md before the run they affected)

1. **Amendment 1:** the first full boot-A run died at 55 cases. An SSH reset turned a
   progress print into `BrokenPipeError`. On the next boot all 181 cases were run as a
   detached unit, and cross-boot was judged on those 55 cases instead of the planned 46.
2. **Amendment 2:** the board's Ubuntu `unattended-upgrades` and needrestart restarted
   the qualification unit at case 170 (06:58Z) and the first resume unit after 5 cases
   (07:15Z). At 07:27Z a further needrestart pass stopped journald, udevd and resolved, and
   the board hung. There was no network and no getty, but the CPUs were running. A JTAG
   `rst -system` (approved by the user) recovered it cleanly: dpkg audit clean, no I/O errors,
   RC1 READY by itself.
   - **Final 11 cases (170–180):** run on that third boot with `qual.py --resume-from`,
     detached with `setsid` so needrestart could not restart them, and checkpointed after
     every case.
   - **Drafter:** history seeded from the recorded tokens of the 170 cases. Gate state was
     not replayed.
   - **Reproducibility:** cases 170–174 also completed in the interrupted resume on the
     second boot, with the same identical results and per-case times within 2%.

## What this shows and does not show

- **Shows:** host-only speculation on the deployed RC1 hardware is bit-exact over 181
  cases, three boots and a service path, and it speeds up the target workload (tool and
  maintenance) by 1.8–1.9x in decode and 1.6x in client latency. The service wrapper
  reuses RC1's code unchanged apart from the decode loop.
- **Does not show:**
  - Sampling: greedy only.
  - More than one board.
  - Quality on real long documents.
  - Behaviour under concurrent requests.
  - Production readiness of `spec_service.py`. It is a test entry point; RC1's default
    service is unchanged.

## Operational finding (important beyond this experiment)

The freshly flashed card runs Ubuntu `unattended-upgrades` with needrestart in automatic
mode. It can restart `sysone-rc1.service` mid-request, as it did to the test units, and
once it hung the whole board. RC1 needs a decision here: either disable unattended
upgrades, or blacklist the sysone units in needrestart and schedule upgrades in a
maintenance window.

**Resolved later on 2026-11-18 (user-approved):** two drop-in files were added, and RC1
kept running throughout (no restart):
- `/etc/apt/apt.conf.d/99sysone-no-auto-upgrade` sets `Unattended-Upgrade "0"` and
  `Download-Upgradeable-Packages "0"`. Package lists still refresh.
- `/etc/needrestart/conf.d/99-sysone.conf` sets `restart = 'l'` (list only) and never
  restarts `sysone-*` or `spec-qual*`.

The effective configuration was verified, and RC1 then answered a query correctly. 204
package upgrades are pending, with the kernel meta packages held. Apply them by hand in a
maintenance window with RC1 drained, then reboot and verify RC1. To undo, delete the two files.

## Next

1. ~~Decide the unattended-upgrades and needrestart policy on the board~~ (done, above). The 204 pending upgrades still need a maintenance window.
2. Batched-head bitstream (rule 5 says yes): one head pass that serves up to 8 lanes.
3. Promote speculation into the RC1 default service behind a flag, after (1).
4. Replace the SD card, which is still the card recovered on 2026-11-17.
