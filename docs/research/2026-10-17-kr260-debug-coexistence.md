# KR260 repeated outage investigation: debugger isolation restores availability

The leading cause is interference between low-level debug/register access and
the running Linux power-management state. This is a strongly supported working
diagnosis, not a demonstrated single failing instruction. Keep live JTAG and
direct PS/RPU `/dev/mem` inspection excluded until a separate compatible debug
setup is audited. The stock board is currently accessible; no further reset or
firmware replacement is required for ordinary Linux access.

## Evidence and limits

1. Following the first user-confirmed restart, ordinary saved-key SSH queries
   succeeded: stock app active, all A53s online, manager/dashboard active,
   no remoteproc instances. A combined inventory containing direct PS/RPU MMIO
   failed without usable output. Later ordinary Linux queries succeeded, then
   a PSU/JTAG register inventory completed, followed by loss of network access.
   This sequence does not isolate one particular read as the trigger.
2. COM9 is the connected board's FTDI channel B. Initial WMI serial enumeration
   missed it; broader present-device enumeration located it. UART capture at
   115200 8N1 recorded Linux journal/cron tasks blocked for over122s and taint M.
   Thus at least this outage includes a kernel/system stall, not merely a bad
   password or an sshd configuration problem. The earlier hardware exception
   that set M was not recovered; M alone does not prove faulty physical RAM.
3. Previous sealed logs show CPU2/systemd waiting in cross-CPU instruction-cache
   synchronization during BPF JIT compilation, with repeated soft lockups.
   BPF is the observed waiting path, not a proved source-code defect.
4. AMD [UG1137](https://www.amd.com/content/dam/xilinx/support/documents/user_guides/ug1137-zynq-ultrascale-mpsoc-swdev.pdf)
   documents unsupported JTAG access while software powers CPUs down and lists
   CONFIG_CPU_IDLE,CONFIG_PM,CONFIG_SUSPEND,CONFIG_FREEZER and CONFIG_PERF_EVENTS
   among debugger-incompatible settings. The saved exact kernel configuration
   enables all five. Fresh Linux sysfs evidence also shows `cpu-sleep-0` enabled
   on each of four cores. These facts support the interference hypothesis.
5. Stopped the laptop's existing hw_server after verifying PID24808 and its
   executable/TCP3121 command line. The user then restarted the board with UART
   recording. No debugger was restarted, no MMIO probe was issued, and no Linux
   power-management, kernel, boot, flash or FPGA configuration was changed.
6. The resulting boot ID is `6c80ec1a-e7ae-473f-b169-d54f129615d1`.
   `linux-stability-v1` captured25 samples spanning360s, each with taint0,
   CPU0-3 online and root device state `running`. At the final fresh SSH check
   on2026-10-17, uptime was4h32m on the SAME boot ID, taint remained0, and the
   storage and all four CPUs remained available. The stock app, dfx-mgr and
   dashboard are active. No new lockup/machine-check signature was found in the
   captured current-boot warning output. Existing pinctrl/old-firmware warnings
   remain and have not been silently treated as resolved.

The controlled comparison removes both debugger polling and direct MMIO probes.
It does not distinguish those two mechanisms, prove permanent reliability, or
exclude a separate storage/firmware problem. No intentional crash reproduction
was attempted. Do not present this as a confirmed bad cable, broken board, BPF
bug, repaired filesystem, or completed AMP deployment.

## Containment and next safe work

- Keep hw_server/XSDB/Vivado hardware connections closed during stock Ubuntu.
  USB UART may stay connected; it is a separate FTDI channel and does not require
  a JTAG server. [UG1092 identifies J4 as UART/JTAG](https://docs.amd.com/r/en-US/ug1092-kr260-starter-kit/Interfaces).
- Use `amp_probe_saved_ssh.py` with explicit Linux-only plans to collect ordinary
  kernel logs, sysfs CPU/driver state, file hashes and manager state. Verify the
  pinned SSH host key on every connection. Credentials remain in hidden terminal
  input and process memory.
- Do not run `amp_probe_rpu_inventory.py` or the new guarded target controller
  unchanged: both contain direct PS/RPU `/dev/mem` reads. Offline recovery checks
  do not discharge this newly identified live coexistence gate. Their sealed
  sources/receipts are retained; neither is rewritten or relabelled qualified.
- Before future R5/JTAG work, establish a separately audited Linux-compatible
  power/debug configuration through supported ownership interfaces, arm UART
  capture and local recovery, and verify the exact helper write set. Do not
  force power/clock/reset state with raw PS writes or apply the boot-only firewall
  plan to running Linux. This investigation did not change CPU idle settings.
- R5 power-up/entry/recovery, measured R5 tags, trusted ATF/PMU/R5 activation,
  safe firewall/filter/memory composition, exact inference regression and new
  physical/target qualification remain open. Deployment authorization remains
  active once the actual gates pass; no inference image was deployed here.

## Artifact locations

New evidence is rooted at `build/v2/typed200-amp-rpu-recovery-v1`:
`linux-inventory-v1`, `read-only-jtag.log`, `backup-v1` (TCP failure),
`uart-boot-v1.txt`, `uart-isolation-v1.txt`, `linux-diagnosis-v1`,
`linux-stability-v1`, `post-isolation-v1`, and `sdk-aib-audit`.
The original `inventory-v3` failure is retained under the preceding diagnostic
root. A source-audit finding also remains relevant: the SDK isolation-enable
helper's void return does not propagate ACK timeout; future power-down recovery
must check ACK explicitly.

The console capture jobs and the six-minute observation have completed. No
debugger, build, SSH monitoring job or serial-port owner is left running.
