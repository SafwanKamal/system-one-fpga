# Repeated Linux outage investigation after power cycle

Update2026-10-17: the requested UART-captured restart and isolation observation
completed. Same-boot SSH remained healthy at4h32m with taint0. Read
`2026-10-17-kr260-debug-coexistence.md` for the current conclusion/containment.
The pending-action descriptions below record the investigation sequence.

Working root: `build/v2/typed200-amp-rpu-recovery-v1`. Prior diagnostic validation
was copied and both maps verified before new work. No FPGA/R5 image was loaded,
no target reset/power/clock write or boot-file change was issued. A UART newline
was sent. Debug access itself may have side effects; the absence of explicit
register writes does not establish noninterference.

After the user's confirmed power cycle, `inventory-v3` authenticated but its
combined root command returned no usable stdout/stderr and failed. Its collector
did not record the remote exit status; the exact failing operation is unknown.
The failed directory under the preceding diagnostic root is preserved.

The new `scripts/v2/amp_probe_saved_ssh.py` collects stdout/stderr incrementally,
records exact exit statuses and bounds command waits. Its `linux-inventory-v1`
passes all four commands: uname/uptime/CPU state, stock app and manager/dashboard,
clock summary, remoteproc listing and iomem. All four A53s were online, stock
`k26-starter-kits` active, manager/dashboard active, no remoteproc instances.
Kernel is 6.8.0-1036-xilinx. System One and PMU reservations remain visible.

A subsequent PSU-only JTAG register read recorded both R5 power bits still clear,
R5 clock01000200, reset13, global50 and cfg4/4. PL0 was01010a00 after cold boot;
AFI remaineda00. No halt/reset/download/resume or explicit target write was used.
Afterward, the next SSH attempt timed out during TCP connect, before any backup
command. A five-second TCP recheck also timed out. A bounded scan of local /24
port22 found no endpoint. Fresh DDR backup and live new-controller rollback
qualification therefore remain incomplete.

## Console and stronger diagnostic evidence

Initial Win32_SerialPort enumeration missed the board. Broader Get-PnpDevice
enumeration identifies the existing FTDI device XFL14EBBE1U3 and channel B's
USB Serial Port COM9. No extra cable/terminal installation is currently needed.
The port opens at115200,8N1,no flow control,DTR/RTS disabled. An eight-second
passive capture and a separate newline check were blank. A subsequent continuous
capture (`uart-boot-v1.txt`) receives real Linux messages:

```
[492.530426] INFO: task jbd2/sda2-8:330 blocked for more than 122 seconds.
[492.537258]       Tainted: G   M               6.8.0-1036-xilinx #37-Ubuntu
[492.552303] INFO: task cron:1814 blocked for more than 122 seconds.
```

This establishes a Linux blocked-task condition during the current outage.
The `M` taint records a processor machine-check exception according to the
[kernel taint documentation](https://docs.kernel.org/admin-guide/tainted-kernels.html).
It does not identify a defective component, prove that storage initiated the
failure, or establish that this outage has the same cause as prior soft lockups.
The earlier event that set the taint must be recovered from full boot/kernel logs.

Prior sealed `extra-inventory-v1/previous_boot.txt` shows systemd on CPU2 stuck in
`smp_call_function_many_cond -> kick_all_cpus_sync -> flush_icache_range ->
bpf_int_jit_compile`, followed by repeated soft-lockup reports. This identifies
a CPU synchronization wait; it does not by itself identify a BPF implementation
bug or prove which remote CPU failed to respond.

The leading interference hypothesis is supported by the timing around debugger
access and AMD's documented JTAG/power-management compatibility restriction.
[AMD UG1137](https://www.amd.com/content/dam/xilinx/support/documents/user_guides/ug1137-zynq-ultrascale-mpsoc-swdev.pdf)
warns that JTAG accesses are unsupported when software powers CPU cores down,
and lists CONFIG_CPU_IDLE,CONFIG_PM,CONFIG_SUSPEND,CONFIG_FREEZER and
CONFIG_PERF_EVENTS as conflicting configurations. The saved exact board kernel
config enables all five. This is a hypothesis pending controlled observation,
not a proved diagnosis of this board.

The installed SDK's DAP module also contains PMU ROM wake-event handling. That
reinforces why a debug read must not be assumed free of power-management effects.
Stock PMU equivalence and exact ROM operations remain unaudited.

Stopped the existing local hw_server PID24808 after verifying its executable and
TCP3121 command line. This removes active debugger polling from the next boot;
it issues no target reset. No Vivado/XSDB/hw_server job remains. Preserve the S:
alias. Do not restart hardware server or run JTAG/MMIO probes during isolation.

The user has been asked for one further power cycle WITH UART capture already
armed, to obtain a controlled boot without debugger polling. Do not issue
repeated blind resets. A Linux-only plan `linux-diagnosis-plan-v1.json` is prepared
to collect previous/current kernel logs, taint/cmdline, root storage, network and
CPU idle state without /dev/mem, JTAG, power writes or configuration changes.

## RPU source audit

`sdk-aib-audit/receipt.json` records four RPU isolation masks at request register
ff413030:10000,20000,40000,80000 (combinedf0000). XPfw_AibDisable clears selected
request bits. XPfw_AibEnable sets a bit, polls acknowledgement, and returns void;
timeout only prints. A future recovery path must explicitly verify isolation
acknowledgement before power-down rather than treating helper return as proof.
ROM service indexes106/138 select RPU up/down handlers; their exact write sets
and equivalence to the running stock2022 PMU remain open. No AIB/ROM operation
was executed. New SDK snapshots and their hashes are preserved.

Typed-output deployment remains NOT READY, and R5 source tags remain unmeasured.
The live clock/RPU recovery controller has not been qualified. Preserve all
previous sources/artifacts/seals and failed attempts; no commits/pushes.

For physical reference, J4 is the board's micro-USB UART/JTAG connector in
[AMD UG1092](https://docs.amd.com/r/en-US/ug1092-kr260-starter-kit/Interfaces).
