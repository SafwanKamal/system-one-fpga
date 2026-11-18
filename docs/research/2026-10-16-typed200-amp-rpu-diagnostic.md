# Guarded diagnostic continuation and actual RPU power state

Typed inference remains **NOT READY**. No PL programming, RPU power/reset/clock
write, R5 execution, DDR write, boot-file change, commit or push occurred in this
continuation. Existing deployment authorization remains active subject to the
readiness gates. The new controller has software verification only.

The working root is `build/v2/typed200-amp-rpu-diagnostic-v1`. Before new work,
both maps in the previous target-probe validation were verified: 10,007 preserved
files and 81 candidate artifacts matched. The validation anchor was copied and
its SHA256 recorded in `preservation-before.json`. `S:` still maps to the current
workspace. Only the existing `hw_server` was running; no native build was active.

## Actual RPU state

The read-only JTAG script used the PSU memory-access target, with no halt, reset,
download or resume operation. The cable is `XFL14EBBE1U3A`. Full output is in
`read-only-jtag.log`; decoded evidence and SDK identities are in `rpu-audit.json`.

| Register | Observed | Meaning relevant to this diagnostic |
|---|---|---|
| PMU_GLOBAL_PWR_STATE | `0x00ff008f` | R5 power bits `0x400` and `0x800` both clear |
| CPU_R5_CTRL | `0x01000200` | Interface gate set; core gate `0x02000000` clear |
| RST_LPD_TOP | `0x13` | Both R5 resets set; AMBA mask `0x4` clear; PGE bit `0x10` set |
| RPU_GLBL_CNTL | `0x50` | SLSPLIT clear, TCM_COMB and SLCLAMP set |
| RPU_0_CFG / RPU_1_CFG | `0x4` / `0x4` | VINITHI set; NCPUHALT clear |
| PL0_REF_CTRL | `0x00010a00` | Matches the previous recovered, unused-clock state |
| AFI | `0xa00` | Matches the previous recovered interface configuration |

These register observations do not establish Linux ownership or a usable halted
CPU debug entry. The cores are powered down according to the hardware power-state
bits; target labels and reset bits alone must not be used to infer power-on.

The installed SDK's `pm_power.c:PmPowerUpRpu` calls the PMU ROM
`XpbrPwrUpRpuHandler`, checks its status, then disables four RPU/LPD AXI isolation
barriers through `XPfw_AibDisable`. Its power-down path enables those barriers
before calling the PMU ROM. `pm_binding.c:XPfw_DapRpuWakeEvent` updates the PMU
software power state based on the hardware state. This makes a raw reset-only
startup inadequate. Exact stock PMU/ROM power-up writes, PM ownership, isolation
sequencing and rollback still need audit. No power-up helper was executed.

Five SDK sources were copied into `sdk-source-snapshot` and hashed. The AMBA
reset mask is `0x4`; `0x10` is the different RPU PGE reset field. The previously
rejected opaque processor reset/OCM boot-loop path remains excluded.

## New controller and verification

`scripts/v2/amp_probe_guarded_target.py` is a separate APU-only diagnostic
controller. It does not implement or execute R5 power-up, reset, image loading,
or release. `amp_probe_guard_policy.py` contains its checked clock/package policy
and a fail-closed RPU readiness checker for the future startup path.

The controller pins the existing package manifest and APU executable hashes,
hash-checks the additive installed package, and reuses its directory without
overwriting it. It requires root-controlled staging under
`/var/lib/sysone/amp-probe`, a board-local systemd invocation with a matching
`ExecStopPost`, 120-second start/stop timeouts, and an exclusive process lock.
The unit must set `SYSONE_PROBE_UNIT` to its own
`sysone-guarded-probe-*.service` name. There is no uploaded/started unit yet.

Before PL changes it verifies the reservation, baseline hashes, unused clock,
stock state, reset cores and DDR identity, and saves a fresh stopped-core DDR
snapshot. State is saved with file and directory synchronization before changing
the dashboard or PL. The controller only reads this DDR; it does not implement
DDR restoration while a core might be running.

Running PL0 must equal the initial register with CLKACT set, with a real Linux
clock consumer and the unchanged reviewed rate. Recovery accepts either the
unchanged idle gate or its clearing by Linux; every other register bit must
match. A clock initially off may not become enabled after recovery. Clock rate
and reference counts must match the initial unused state. No raw PS write forces
the gate on. All RPU/TCM power bits and RPU configuration/clock/reset registers
must match; independent A53/USB power transitions are observed without claiming
global power-state equality.

Recovery reloads stock if needed, checks operating manager/overlay, AFI, clocks,
baseline files and DDR, then restarts and verifies the dashboard when initially
active. Repeated recovery calls reverify observations instead of trusting a
saved success flag. Failed reloads or corrupted state remain failures.

`controller-check-v2/receipt.json` passes **72 offline cases**, including every
non-gate PL0 bit mutation, rate/reference faults, installed-package byte changes,
real controller recovery under injected register/DDR/baseline/load/dashboard
failures, repeated recovery and RPU readiness rejection. V1's earlier 70-case
receipt is retained. Source and embedded inventory command syntax also pass.
These checks are software fault injection, not live rollback qualification.

## SSH attempts and retained failures

Initial native SSH with BatchMode and StrictHostKeyChecking reached authentication
and returned `Permission denied (publickey,password)`. No unattended identity
was available. The user subsequently supplied authentication in this chat; the
password was entered through a hidden terminal prompt and was not written to
repository files or attempt receipts.

`amp_probe_rpu_inventory.py` verifies the saved Ed25519 fingerprint before
authentication and uses RejectPolicy. It only reads Linux ownership evidence,
registers, no-map DDR hash, clock/device-tree state and package hashes. It never
autoaccepts a host key. Its first two credentialed attempts failed before any
remote command: `inventory-v1` during the SSH handshake (`No existing session`),
and `inventory-v2` while waiting for the SSH protocol banner. Neither failure
tests whether the password is correct. Their failed directories are retained.
A native verbose SSH check also stalled after TCP connection and was terminated
by its exact local process ID. No board reset was issued.

The user has been asked to power-cycle once to recover Linux/SSH access. Wait
for confirmation, recheck the saved host identity, and use `inventory-v3` for the
next fresh read-only attempt. Do not overwrite or rerun v1/v2.

## Remaining work

After SSH recovery, obtain fresh Linux ownership and stopped-core backups.
Qualify the new APU controller's live rollback using a new attempt and the
existing probe package. Audit the complete powered-down-to-halted RPU path and
board-local stopped/reset recovery before loading the existing ELF. Preserve
A53, GEM, PLL, ADMA and live ATF OCM; do not invoke opaque reset helpers.

R5 tags remain unmeasured. Trusted ATF/PMU/R5 activation, quiescent firewall
installation, integrated pre-conversion filtering, hidden-output relocation,
protected startup, exact numerical/counter/cycle/fault/drain regression and new
physical/target stress qualification are still required. The conditional local
PL terminal-by-D contract and all six outcomes remain unchanged.

The prior seal includes `rtl/v2/README.md`. This report records the newly found
power/startup and connection problems without modifying that sealed baseline.
