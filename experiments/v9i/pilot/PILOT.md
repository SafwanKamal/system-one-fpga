# v9i board pilot on the KR260

Run this only in a user-approved board window with one named operator. Require
the routed timing pass, the published batch-8 prefill C-sim exactness pass, and
the offline dry run below before reserving. The pilot ends with RC1.3 restored.
Use the approved session transport and enter credentials only in the local
secure prompt. Keep the board reservation throughout, including rollback.

## Offline preparation and dry run

From the assigned Windows worktree, with Vivado 2025.2 Bootgen and `dtc` available:

```powershell
$source = 'C:\Users\user\OneDrive - Texas Tech University\Desktop\Code\FPGA Project\system-one-fpga\system-one-fpga'
python experiments/v9i/pilot/dry_run.py --source $source
if ($LASTEXITCODE -ne 0) { throw 'RC1.4 dry run failed' }
python scripts/v2/package_rc14.py --source $source
```

The dry run packages and unpacks the real routed bitstream and XSA in a
temporary directory. It compiles the overlay, copies and checks the sealed RC1
package files, verifies the v9h register map and the P=2 cost formula, rejects
a tampered input, and exercises normal and failed-probe rollback using mocked
systemd, image switching and socket calls. It checks the bench row shape
against the recorded RC1.3 shared-cache run. Expected final line includes
`"result": "PASS"`. The packager writes `build/v2/rc1-4/rc14.tar` and prints
its SHA-256. Record that SHA-256 for transfer verification.

Preserve the original RC1.3 result formats. Put the 21-row `shared` array from
the historical report into a standalone bench JSON. The matched 36-case v9h
reference is already in the archive as `rc14/check/reference-pilot.json`.

```powershell
$evidence = Join-Path (Get-Location) ('build/v2/rc1-4/evidence-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory $evidence
$historical = Get-Content -Raw "$source/build/v2/rc1-3/board/bench-template-cache.json" | ConvertFrom-Json
if ($historical.shared.Count -ne 21) { throw 'Wrong RC1.3 reference size' }
[IO.File]::WriteAllText("$evidence/bench-rc13-shared.json", (ConvertTo-Json -InputObject $historical.shared -Depth 20))
tar -xf build/v2/rc1-4/rc14.tar -C $evidence rc14/check/reference-pilot.json
```

## Reserve, verify and begin

The sole status ledger is the original checkout's `BOARD_STATUS.json`.

```powershell
$status = Join-Path $source BOARD_STATUS.json
$boardTool = Join-Path $source scripts/v2/board_status.py
python $boardTool --file $status show
$owner = Read-Host 'Approved board operator name'
$reservation = python $boardTool --file $status reserve --owner $owner --purpose 'Approved v9i pilot and return to RC1.3' | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or -not $reservation.reservation.claim_id) { throw 'Board reservation failed' }
$claim = $reservation.reservation.claim_id
```

As the reserved operator, open the board session. Run the following in a root
Bash shell. Set `E` once, and keep that shell or reuse its exact path. Collect
initial status and ensure RC1.3 is READY on v9h. Verify the original RC1.3
drop-in is listed, the RC1.4 drop-in is absent, and there is no additional
image-switch override. Check that the DMA lease belongs to the service PID
and the model is sealed. Reconcile any discrepancy before proceeding.

```bash
b=/var/lib/sysone/rc1-4-pilot
E=$(mktemp -d /var/lib/sysone/v9i-pilot.XXXXXXXX)
printf '%s\n' "$E"
snapshot() {
  date -u +%FT%TZ
  cat /proc/sys/kernel/random/boot_id
  systemctl show sysone-rc1.service -p ActiveState -p SubState -p MainPID -p DropInPaths -p ExecStart
  systemctl cat sysone-rc1.service
  cat /sys/class/misc/sysone_qwen_dma/ownership
  cat /sys/class/fpga_manager/fpga0/state
  dt=/sys/firmware/devicetree/base
  region=$(tr -d '\000' < "$dt/__symbols__/fpga_full")
  tr -d '\000' < "$dt$region/firmware-name"
  printf '\n'
  sysone-qwen-fpga --health
}
set -o pipefail
snapshot | tee "$E/before.log"
```

Return to the host shell and mark the ledger before changing the board.

```powershell
python $boardTool --file $status begin --claim $claim --operation 'Install and test v9i, then restore and verify RC1.3'
if ($LASTEXITCODE -ne 0) { throw 'Board begin failed' }
```

## Stage, run the 21 tools, and check 36 cases

Transfer the local archive through the approved transport. On the board set
`ARCHIVE` to the transferred file's absolute path. Substitute the exact SHA
printed on the host. Check the exit status of each command before proceeding.

```bash
printf '%s  %s\n' 'HOST_ARCHIVE_SHA256' "$ARCHIVE" | sha256sum -c -
tar -xf "$ARCHIVE" -C "$E"
python3 "$E/rc14/install_rc14.py" install --staged "$E/rc14" 2>&1 | tee "$E/install.log"
```

Require successful installation and a READY probe reporting `rc1.4-costaware`.
For an install error, go directly to rollback. No package download or reboot
is needed. The activation probe warms the system prefix before timing.

```bash
label=v9i-$(date -u +%Y%m%d-%H%M%S)
python3 "$b/install_rc14.py" bench --label "$label" --keep-cache | tee "$E/bench-v9i.log"
cp "/var/lib/sysone/qualifications/rc1-4/bench-$label.json" "$E/bench-v9i.json"
snapshot | tee "$E/v9i-service.log"
```

The run uses 21 new conversations in workload order,
64 max tokens, and `reset_cache=False`, matching the historical RC1.3
shared-cache run. Preserve both the JSON list and its `BENCH-JSON` log line.
If the bench fails, keep any records and go to rollback.

The raw check uses the first 36 entries of the historical every-fifth v9h
sample, indices 0 through 175 in steps of five. The historical sample also
has index 180, which is outside this pilot. The raw checker preserves v9h's
original two-arm schedule and original qualification drafter in the
`candidate` arm. The 21-query service bench exercises the modelled v9i
drafter. Keep the socket service stopped during the raw check so the checker
can acquire the inference lock and exclusive DMA lease. Run in a session
with enough time to finish the ordered workload.

Run `stop` and `up` in the foreground. Never background them: on 2026-11-22 a trailing
`&` put the whole chain in the background, the SSH command returned, and `up` was killed between
`xmutil unloadapp` and `loadapp`, leaving no app loaded. The fix was `xmutil loadapp
sysone-qwen-decoder-v9e` and then `up` again. The check itself takes 15-20 min. Launch it as a
transient systemd unit so a dropped SSH session cannot kill it, then poll for `raw.rc`.

```bash
systemctl stop sysone-rc1.service
python3 "$b/rc14_image.py" up 2>&1 | tee "$E/image-up.log"   # must print "after": "...v9i.bit.bin"
systemd-run --unit=spec-qual-v9i-raw --collect --property=KillMode=process /bin/bash -c \
  "python3 -u $b/check_v9i.py --package $b/package --workload $b/check/workload.json \
   --expected $b/check/expected.json --reference $b/check/reference-pilot.json \
   --out $E/raw > $E/raw.log 2>&1; echo \$? > $E/raw.rc"
while [ ! -f "$E/raw.rc" ]; do sleep 15; done; tail -3 "$E/raw.log"; cat "$E/raw.rc"
```

Check the return status of each command before proceeding. `up` requires
released ownership and VMAs and verifies the idle image. Preserve
`$E/raw/pilot.json` as written, including the per-case `ar` and `candidate`
objects, `prefill_seconds`, `identical`, and top-level `passed`. Roll back
immediately after the raw check, including on a failed check or timeout.
If the raw process is still running, wait for it to exit and release its
lease before attempting an image switch.

## Restore RC1.3, record, release

With the same reservation, run on the board:

```bash
python3 "$b/install_rc14.py" rollback 2>&1 | tee "$E/rollback.log"
snapshot | tee "$E/after.log"
journalctl -b -u sysone-rc1.service --no-pager > "$E/service-journal.log"
```

The rollback stops the service under the volatile pilot unit if needed,
switches v9i to resting v9e, removes only the RC1.4 drop-in, reloads systemd,
and starts the original RC1.3 service, which switches v9e to v9h. Require
`rc1.3-costaware` from the rollback probe, an operating v9h image, READY,
the same boot ID, and a sealed DMA lease held by the RC1.3 service PID. Keep
the ever-present RC1.3 drop-in and its installation intact. If staging failed
before a bundle was installed, collect a fresh RC1.3 snapshot and the install
failure instead. If restoration fails, preserve logs and record `unknown`.

Copy `before.log`, `install.log`, `bench-v9i.json`, `bench-v9i.log`,
`v9i-service.log`, `raw/pilot.json`, `raw.log`, `rollback.log`, `after.log` and
`service-journal.log` when present into the host evidence directory, preserving
the relative paths. Board evidence stays under `$E`. Close the board session.
Write the on-host observation and record it with the same claim. For verified
ready, enter the full boot ID and UTC observation timestamp from `after.log`.
For failed or uncertain restoration, change the observation `state` to
`unknown`, omit the boot ID and package claims, and cite the failure logs.

```powershell
$observation = @{
  state = 'ready'
  verified_at_utc = (Read-Host 'UTC timestamp in verified after.log')
  boot_id = (Read-Host 'Full boot ID in verified after.log')
  active_package = '/var/lib/sysone/rc1-3-v1/package'
  evidence = (Join-Path $evidence after.log)
}
$observation | ConvertTo-Json | ForEach-Object { [IO.File]::WriteAllText("$evidence/observation.json", $_) }
python $boardTool --file $status record --claim $claim --observation "$evidence/observation.json"
if ($LASTEXITCODE -ne 0) { throw 'Board record failed' }
python $boardTool --file $status release --claim $claim
```

## Compare offline

Require 21/21 complete and successful tool rows, with exactly the RC1.3
generated token IDs and tool paths in the same order. Live values of the files
read by those tools can change between runs. Expect the same 32-token reuse
for each measured query in the shared-cache arm. Require 36/36 matching raw
case keys and both arms' exact token arrays, FP32 logit bits and K/V SHA-256,
with `passed=true`. Any identity failure is a NO-GO. Use the analyzer's
default thresholds of at least 1.03x aggregate decode and 1.00x aggregate
end-to-end against RC1.3.

```powershell
python experiments/v9i/pilot_analysis/analyze_pilot.py --rc13 "$evidence/bench-rc13-shared.json" "$evidence/rc14/check/reference-pilot.json" --pilot "$evidence/bench-v9i.json" "$evidence/raw/pilot.json" --out "$evidence/pilot-analysis.json" --check
```

The tool results carry prefill/decode/elapsed/wall seconds as RC1.3 did.
The raw workload's end-to-end figure in the analyzer is prefill plus
candidate decode. Keep the raw and socket timings identifiable. The expected
speedups of 1.31x on tools and 1.065x overall are model projections.
