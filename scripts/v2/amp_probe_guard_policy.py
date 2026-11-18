"""Fail-closed checks for the separate diagnostic controller; no hardware I/O."""
import hashlib
import json
from pathlib import Path

APP = 'sysone-amp-origin-probe'
MANIFEST_SHA256 = '161d3a60e8372523299e99ff445862fe8136ad0ae166362c10c6e88185ce0230'
CLKACT = 0x01000000
RPU_RESET = 0xff5e023c
RPU_GLOBAL = 0xff9a0000


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def package_files(directory):
    """Accept only the already reviewed package, including its exact manifest."""
    directory = Path(directory)
    manifest = (directory / 'build.json').read_bytes()
    require(hashlib.sha256(manifest).hexdigest() == MANIFEST_SHA256, 'unreviewed manifest')
    m = json.loads(manifest)
    for name, digest in m['files_sha256'].items():
        require(hashlib.sha256((directory / name).read_bytes()).hexdigest() == digest,
                'package hash mismatch: ' + name)
    return {**m['files_sha256'], 'build.json': MANIFEST_SHA256}


def verify_idle_clock(before_reg, after_reg, before_clock, after_clock):
    # Removing the probe's consumer may clear CLKACT. No other bit may change,
    # and recovery must never turn on a clock initially off and unreferenced.
    require((before_reg & ~CLKACT) == (after_reg & ~CLKACT), 'PL0 parent/divider/reserved bits changed')
    require(not (after_reg & CLKACT and not before_reg & CLKACT), 'idle clock unexpectedly enabled')
    require(before_clock == after_clock, 'idle Linux clock state changed')
    require(after_clock['enable'] == 0 and after_clock['prepare'] == 0, 'clock consumer remains')


def verify_running_clock(before_reg, after_reg, before_clock, after_clock):
    require(after_reg == (before_reg | CLKACT), 'running PL0 register mismatch')
    require(before_clock['hz'] == after_clock['hz'] and 95_000_000 < after_clock['hz'] <= 100_000_000,
            'probe rate outside reviewed limit')
    require(after_clock['enable'] > 0 and after_clock['prepare'] > 0, 'probe clock consumer absent')


def rpu_start_blockers(registers, linux_ownership_verified=False, halted_entry_verified=False,
                       local_recovery_armed=False):
    """Readiness only. Neither a powered target nor an ACK grants execution."""
    blockers = []
    if registers['power_state'] & 0xc00 != 0xc00:
        blockers.append('R5 power islands not both on; audited power-up/rollback required')
    if registers['r5_clock'] & 0x03000000 != 0x03000000:
        blockers.append('R5 interface/core clock gates not both enabled')
    if registers['lpd_reset'] & 3 != 3:
        blockers.append('both R5 cores must initially be reset')
    if registers['rpu0_cfg'] & 1 or registers['rpu1_cfg'] & 1:
        blockers.append('NCPUHALT must be low before reset release')
    if registers['rpu_global'] != 0x50:
        blockers.append('RPU mode differs from reviewed initial lockstep state')
    for passed, message in [
        (linux_ownership_verified, 'fresh Linux RPU/remoteproc ownership not verified'),
        (halted_entry_verified, 'private halted PC/vector/exception state not verified'),
        (local_recovery_armed, 'board-local recovery not armed'),
    ]:
        if not passed:
            blockers.append(message)
    return blockers
