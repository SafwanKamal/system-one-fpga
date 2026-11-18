# Speculative decoding qualification and RC1 service integration

Written 2026-11-18, before the run. This follows the 2026-11-17 board pilot (27/27
bit-identical; 1.61x on maintenance prompts). Hardware: unchanged RC1 (v9e
bitstream, sealed package `/var/lib/sysone/hardware-consolidated-rc1-20261108`).
No programming, no change to the RC1 package, launcher or default service. The
speculative service is a separate script (`spec_service.py`) that imports the RC1
package code unchanged and replaces only the decode loop. It runs only for these
tests, with `sysone-rc1.service` stopped, and RC1 is restarted afterwards.

## What changed since the pilot

- `spec_decode.py`: one decode loop for both modes, with a per-token stop check, plus an
  adaptive gate. The gate keeps a running estimate (alpha 0.3, prior 1.0) of tokens
  accepted per verify pass for each draft match length. It speculates when the estimate
  is ≥ **0.25**, and otherwise takes a plain step, probing one draft in every 4 skipped
  opportunities.
- `spec_service.py`: RC1 `Session.generate` copied line for line, apart from the
  decode loop. Offline tests (`test_spec_decode.py`, `test_service_wiring.py`)
  show it matches the RC1 loop on typed-JSON stop, EOS refusal and truncation.
- `qual.py`: one prefill per case, shared by both modes. Decode only reads
  prompt K/V rows, which neither mode's decode writes.

## Workload (`select_workload.py` → `build/v2/spec-qual/workload.json`)

181 cases, with domains interleaved:
- 70 general and 70 maintenance prompts not used in the pilot, up to 96 new tokens;
- 20 synthetic long contexts of 1,201–1,717 prompt tokens (concatenated maintenance
  prompts), up to 64 new tokens;
- 21 RC1 tool queries (7 phrasings × 3 allowed paths), up to 64 new tokens.

46 cases (every 4th) form the boot-B subset.

## Runs

- **Boot A:** `qual.py` over all 181 cases (`ar` against `adaptive`, alternating which runs
  first). Then `e2e.py`: the 21 tool queries through the installed RC1 service,
  `spec_service --speculate off` and `spec_service --speculate adaptive`.
- **Boot B** (after a reboot that runs the normal RC1 boot path): `qual.py
  --only-subset --compare-with <boot A qual.json>`.

## Decision rules

1. **Exactness (boot A):** all 181 cases have identical tokens, head logit bits and
   committed-K/V SHA-256 for `ar` and `adaptive`. Any difference is a FAIL.
2. **Cross-boot (boot B):** all 46 subset cases equal boot A in both modes (tokens,
   logit bits, K/V SHA-256), and `ar` equals `adaptive` again.
3. **Service:** for every query, `off` and `adaptive` equal the installed RC1 service in
   `generated_ids`, generated text and executed tool path, and every request succeeds.
4. **Speed, reported only if 1–3 pass:** decode-phase speedup is time-weighted per
   domain. Pass requires ≥ 1.00 for general, maintenance and tool, and ≥ 1.10 for maintenance.
   At most 5% of non-long cases may fall below 0.95x. Long cases are reported separately.
5. **Next-step measurement (reported, not a pass/fail):** the share of adaptive decode
   time spent in head scans (commands 3+4) and lane copies (9), against layer passes (2, 8),
   per domain. If the head share in maintenance is ≥ 30%, the batched-head bitstream is
   the next lever; below that, it is not worth the hardware work.
6. **Service latency, reported:** median client latency of the RC1 service divided by
   `adaptive` on the tool queries.

## Limits fixed in advance

Greedy only. One board. Two boots, the second on a 46-case subset. Synthetic long prompts
test attention reach, not quality. The draft history depends on case order, which is fixed
by the workload. The full benchmark sweep stays stopped.

## Amendment 1 (written 2026-11-18T02:44:06Z, before the replacement run)

The first boot-A run (boot `bc43c3c6…`) stopped after 55 of 181 cases. Its SSH
session dropped and a later progress print raised `BrokenPipeError`. All 55
completed cases were bit-identical. The service check (rule 3) completed on that
boot and passed 21/21. The board was then rebooted as planned.

Replacement, to avoid a third reboot: on the new boot, `qual.py` runs all **181**
cases as a detached systemd unit (output to a file, so an SSH loss cannot stop it).
It uses `--compare-with` against the 55 cases from the first boot.
- Rule 1 (exactness) is judged on the 181-case run.
- Rule 2 (cross-boot) is judged on those **55** cases, instead of the 46-case subset:
  `ar` and `adaptive` must equal the first boot's tokens, logit bits and K/V SHA-256.
- Rules 4 and 5 (speed, head share) use the 181-case run.
- Rule 6 uses the first boot's service check. Rules and thresholds are otherwise unchanged.

## Amendment 2 (written 2026-11-18T07:10Z, after the stop and before the resumed run)

The Amendment 1 run (boot `e0251f62…`) was stopped by systemd at 06:58:28Z. The journal
shows a stop and restart of `spec-qual-bootb.service` that the qualification queue did not
issue. The cause is being checked on the board. The restarted process exited at once
because its output directory existed, then RC1 restarted. The last checkpoint holds
**170** cases (indices 0–169): all identical, and all 55 cross-boot cases equal. The
console log shows indices 170–176 identical as well, but they are not in the
checkpoint and are not counted.

Completion, on the same boot: `qual.py --resume-from <170-case qual.json>` runs the
remaining 11 cases (170–180) in the same order and lane-order parity. The drafter
history is seeded with the recorded `ar` tokens of the 170 completed cases. The gate
state is not replayed and restarts from its prior, which can change speed on those 11
cases but not exactness.
- Rule 1 is judged on the union (181 cases).
- Rule 2 is unchanged (the 55 cases).
- Rules 4 and 5 use the union, with a note that 11 cases started from a fresh gate.

Addendum (07:20Z): the board log shows that Ubuntu `unattended-upgrades` with needrestart
did the restart. It restarted `spec-qual-bootb` along with multipathd, packagekit and
fancontrol at 06:58:28Z. It did the same to the first resume unit at 07:15:53Z, after 5 of
the 11 cases (all identical, none checkpointed). The final attempt waits until
unattended-upgrades is idle, then runs `qual.py` in a detached login session with
`setsid` instead of as a systemd service, and checkpoints after every case. Analysis
rules are unchanged.

Addendum 2 (07:52Z, before the final attempt): at 07:27:38Z a further needrestart pass
stopped journald, udevd and resolved, and the board hung. It had no network, and the
serial getty was gone. A JTAG `rst -system` at about 07:46Z brought it back on boot
`e957130a…`: `dpkg --audit` clean, no I/O or EXT4 errors, RC1 READY by itself. The 11
remaining cases therefore run on a third boot. Exactness (rule 1) is a property of each
case and is judged on the union as before. The part from the third boot is labeled in
the analysis. Rule 2 is unchanged (55 cases from the first boot, compared with the
second boot).
