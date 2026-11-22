# v9i (RC1.4) board pilot results (2026-11-22)

**Exactness: PASS on hardware.** All 57 compared outputs are identical to the RC1.3 / v9h
references: the 21 service tool queries (token IDs and tool paths), plus the 36 raw cases (tokens,
FP32 logit bits and K/V SHA-256 in both arms). **Speed: a clear win on tool queries, a loss on long
prompts.** The analyser's aggregate gate reports **NO-GO**. That verdict comes from the raw
workload, whose decode arm runs the old P=4-tuned drafter; see "Reading the NO-GO" below.

RC1.3 was restored and verified on the same boot. The board was released.

## Service bench: 21 tool queries (RC1.4 vs RC1.3, shared template cache)

| | RC1.3 | RC1.4 (v9i) | Speedup |
|---|---:|---:|---:|
| Identical outputs | | 21/21 | |
| Prefill | 11.84 s | 8.56 s | 1.38x |
| Decode | 10.48 s | 8.63 s | 1.21x |
| **End-to-end** | 23.46 s | 18.32 s | **1.28x** |

Model: 1.31x end-to-end on tool queries vs v9h; measured is 98% of that. Every query reused the same 32
template tokens on both sides. Prefill per query was 0.408 s, against 0.391 s predicted by the
attention-reclaim cost model.

## Raw check: 36 cases (v9i vs the v9h reference run)

`PILOT RESULT: PASS` (36/36 identical, both arms). Phase totals in seconds
(`results/raw-phase-breakdown.json`):

| Domain | n | Prefill v9h → v9i | Plain decode | Drafted decode* |
|---|---:|---|---|---|
| tool | 4 | 5.0 → 3.5 (**1.45x**) | 1.00x | 1.36x |
| general | 15 | 152.4 → 131.2 (1.16x) | 1.00x | 0.92x |
| maintenance | 13 | 218.1 → 202.6 (1.08x) | 1.00x | 0.93x |
| long | 4 | 208.2 → 234.9 (**0.89x**) | 1.01x | 0.78x |
| all | 36 | 583.7 → 572.1 (1.02x) | 1.00x | 0.90x |

\* The raw checker keeps v9h's qualification drafter (`coef_dev`, priced for P=4) in both images.
The RC1.4 service uses the v9i-modelled drafter instead (P=2 costs).

- **Plain decode (one token per pass) is unchanged**, as expected: that path is the same in both
  images.
- **Prefill gains on short prompts and loses on long ones.** At long positions attention dominates
  each batch-8 pass. P=2 sweeps the on-chip K/V tile four times per pass where P=4 sweeps it twice.
  The model has this term (`c_grp·p·ceil(k/P)`); the long cases here are 45-77 s prompts where it
  dominates.
- **Drafted decode with the P=4 drafter is slower** on v9i outside tool queries. Its draft lengths
  are priced for P=4. On the service path, the v9i drafter gave 1.21x decode on tool queries.

## Reading the NO-GO

The analyser pools all 57 pairs: decode 0.918x, end-to-end 1.003x, against thresholds of
≥ 1.03x and ≥ 1.00x. Most of the timed seconds come from the 36 raw cases. Their decode arm
measures the wrong drafter for RC1.4, and their long prompts are where P=2 loses. Split by source:

| Source | n | Identical | Decode | End-to-end |
|---|---:|---:|---:|---:|
| Service bench (RC1.4 drafter) | 21 | 21/21 | 1.21x | **1.28x** |
| Raw check (v9h drafter) | 36 | 36/36 | 0.90x | 1.00x |

Interpretation: for the service as it is used today (tool queries with a cached system template),
RC1.4 is a 1.28x end-to-end improvement with identical outputs. For long prompts (tens of
seconds of prefill), v9i is about 11% slower in prefill. Making RC1.4 the default is the user's
decision. It depends on whether long-prompt traffic matters, and it needs the user's approval.

## Run record

- Archive `build/v2/rc1-4/rc14.tar`, SHA-256 `ef578873e0c8b8027b391888a3e4b193147ea5e3588186aa0650b3f98522f1c6`
  (verified on the board before install).
- Board ledger claim `31264f98-35d4-41a7-8016-0b4f93aa4e20`: reserve 20:43Z, begin, record (ready,
  boot `d65e03c2-ebf7-4fe5-9b1c-75c47b3489f7`, verified 22:53:24Z), release.
- Restored state: `sysone-rc1.service` active on the RC1.3 unit (drop-ins `10-speculation.conf`,
  `20-rc13.conf` only), image `sysone-qwen-decoder-v9h`, READY, probe `rc1.3-costaware`, DMA lease
  held by the service PID. No reboot was needed.
- Left on the board for audit: `/var/lib/sysone/rc1-4-pilot`,
  `/lib/firmware/xilinx/sysone-qwen-decoder-v9i`, evidence in `/var/lib/sysone/v9i-pilot-20261122`.
  Host evidence: `build/v2/rc1-4/evidence-20261122-144249/` (not committed).
- Operator incidents, all recovered without user-visible service impact beyond the planned window:
  - The first detached raw-check launch was killed when its SSH command returned. A trailing `&`
    backgrounded the whole stop/up/launch chain.
  - That kill left the FPGA with no app loaded, between `unloadapp` and `loadapp`. The model stayed
    sealed and the DMA lease free. The lead reloaded v9e, ran `rc14_image.py up` in the foreground
    and relaunched the check as a transient systemd unit (`spec-qual-v9i-raw2`).
  - A queue command containing a NUL byte made sshd drop the connection, which caused repeated
    re-logins.
  - The service was stopped from 20:46Z to 22:53Z. The PILOT.md raw-check step should launch with
    `systemd-run`, as done here.

Files: `results/pilot-analysis.json` and `results/pilot-analysis.txt` (analyser `--check`
output) and `results/raw-phase-breakdown.json`.
