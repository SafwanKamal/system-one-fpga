# Deployment continuation: diagnostic requester probe prepared, target recovery open

The user now authorizes deployment after readiness checks. Full typed-output
AMP deployment remains **not ready**; no candidate FPGA image or R5 firmware
has been loaded. The qualified 200 MHz sources/package/recovery/numerical
evidence remain preserved. The new work root is
`build/v2/typed200-amp-deployment-v1`, with 9,844 earlier sealed/evidence files
verified before work.

## Concrete deployment preparation

A separate [AXI origin probe](../../rtl/v2/candidates/typed200_amp_probe/axi_origin_probe.v)
records actual AWUSER, AWPROT and AWID into 16 diagnostic slots. Read registers
return actual ARUSER/ARPROT/ARID. There is no inference engine, permit output,
PL DDR master, interrupt, or external PL I/O. The intended trial measures real
A53 and R5 identities before enabling the production access filter. Payload
data is never treated as a requester identity.

[Simulation v4](../../build/v2/typed200-amp-deployment-v1/probe-sim-v4/receipt.json)
passes 2,048 source/security/lane/ID traces, exact readback, held responses,
rejected burst draining and reset. Earlier test attempts are retained: v1 had
an incorrect port-count assertion; v2 exposed a testbench signed-extension bug.
The corrected test explicitly zero-extends expected 32-bit values. The current
RTL also makes the 32-bit lane extraction explicit.

The [physical review](../../build/v2/typed200-amp-deployment-v1/probe-physical-v2/physical-review.json)
is for this diagnostic image only. It has one 10.000 ns clock and no top-level
external ports. Routed setup is +4.346 ns and hold +0.031 ns. Placement passed
the +0.500 ns gate before routing. DRC has zero checks, CDC reports all paths
safely timed, check_timing reports zero problems in all 12 categories, and all
routable nets are routed without errors. The two scoped false paths target
the first synchronizer stage of the vendor reset block's auxiliary and
external reset inputs. No other timing exceptions were accepted.

The bitstream and [package](../../build/v2/typed200-amp-deployment-v1/probe-package-v1/receipt.json)
were generated after that review. This is a PL-only diagnostic package, not a
boot image or typed-output MVP. No PS initialization script is to be executed.
The overlay retains the live PL0 rate and must pass before/after clock checks;
it selects the matching 128-bit HPM interface through the AFI configuration.
The existing stock application and exact recovery files must be backed up and
verified before loading it. No package has been copied to the board.

A tiny [R5 diagnostic image](../../firmware/typed200_amp_probe/r5_probe.S) and
[audited ELF](../../build/v2/typed200-amp-deployment-v1/r5-probe-build-v1/receipt.json)
are prepared for subsequent tag measurement. It uses only the existing no-map
DDR window 63f00000–63f0ffff, avoiding TCM initialization and the active ATF's
OCM. It has separate non-WX code/result segments, masks interrupts, checks
cache/MPU reset state, checks the probe identity and emits four write markers.
It is a debug-started diagnostic, not qualified R5 startup or a timing proof.
The DDR window must be saved first and restored after R5 is safely reset.
RPU-only setup/restore and actual execution remain unqualified and unexecuted.

## Target state and recovery attempts

An authenticated [read-only preflight](../../build/v2/typed200-amp-deployment-v1/board-preflight-v1/board-inventory.json)
succeeded at 192.168.0.239 with the saved host key. Linux was running the stock
`k26-starter-kits_image_1` overlay, all A53s were online, no remoteproc was
active, and the only Python server was the existing Kria dashboard. The
qualified System One application files were still installed separately.

Later SSH connections failed before authentication with both Paramiko and
Windows OpenSSH. The native client timed out during banner exchange. The
attempts to capture new recovery-file/DDR backups therefore did not run.
No claim is made that this is the earlier kernel soft-lockup's root cause.

Under the user's deployment/recovery authorization, the agent issued one
`rst -system -start`, then one `rst -por`, through the identified JTAG cable.
Both commands returned issued, but **neither is established as a successful
stock cold-boot recovery**. QSPI boot-mode reads remained 2, with no alternate
mode selected. UART1 registers were reset-blocked after the system reset.
No SSH responder was found in a bounded scan of the existing local /24.

For diagnosis the agent briefly stopped A53 #0, read PC/PSTATE, then explicitly
resumed it. PC was fffea16c, matching the stock ATF warm-entry code in the
previously saved binary; PSTATE was 0x3cd. The exact cause of the failed boot
is unresolved. This is not evidence that the JTAG POR command performed a
complete physical power cycle. No code was downloaded during these attempts.

The user has been asked to physically power-cycle the KR260 once. That reply
is pending. Avoid repeated reset attempts or attributing an unproven cause.
No QSPI/eMMC/boot file/security/fuse write, new PL configuration, or R5 execution
has occurred in this continuation. The existing baseline's **files** are intact;
the live board's Linux/SSH availability is presently unresolved.

## Exact continuation

1. On the user's power-cycle reply, retry the saved-key handshake at the previous
   address. If DHCP changed it, discover only on the known local subnet and
   verify the existing host key before authentication.
2. Resume `amp_probe_board_preflight.py` with a fresh `board-readiness-vN`.
   Its dashboard lookup now follows the current PID rather than the old PID.
   Obtain the exact stock and qualified-app file backups, no-map DDR snapshot,
   clock/reset/interface readbacks and recovery procedure before any load.
3. Complete a bounded probe deployment/rollback controller. Quiesce the current
   dashboard's actual service, unload the stock overlay through its normal
   manager, load only the reviewed diagnostic package, verify clocks/AFI/ABI,
   and compare A53 read/write tags and all lane markers. Restore stock on error.
   Do not reuse the production encoder deployer's allowlist or weaken it.
4. Review and test RPU-only setup/restore before starting the diagnostic R5 image.
   Never run the old sole-R5 loader: it deliberately resets A53/GEM resources.
   Do not touch PLL parents or Linux-owned ADMA for this probe.
5. Actual tags then bind the access filter. Continue full ATF/PMU/R5 activation,
   safe firewall transitions, hidden-output relocation, protected R5 startup,
   matched full regression and new physical timing/CDC/DRC/exception checks.
   Only the completed full candidate may be described as typed-output deployment.

No native build remains running after the prepared probe package. Do not
restart completed simulations, implementations, bitstream generation or resets.
