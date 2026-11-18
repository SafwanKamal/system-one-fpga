"""Separate board-local APU diagnostic controller with reviewed clock recovery.

Stage beside the pinned package, apu_probe, policy module, and a FRESH readiness
receipt. Run only under a root-owned systemd unit with this file's --recover as
ExecStopPost. This controller does not power, reset, load, or release an R5.
R5 startup remains gated on a separately audited power/start/rollback path.
"""
import argparse
import hashlib
import json
import mmap
import os
from pathlib import Path
import struct
import subprocess

from amp_probe_guard_policy import APP, package_files, require, verify_idle_clock, verify_running_clock

HERE = Path(__file__).resolve().parent
SERVICE = 'snap.kria-dashboard.service.service'
STOCK = 'k26-starter-kits'
REGISTERS = dict(afi=0xfd615000, pl0=0xff5e00c0, rpu_reset=0xff5e023c,
                 rpu_global=0xff9a0000, rpu0_cfg=0xff9a0100,
                 rpu1_cfg=0xff9a0200, r5_clock=0xff5e0090, power_state=0xffd80100)
APU_SHA256 = 'da0f4daaac0c406921491b1d7abce68a5eaf56d8661bfbc31b405047ae62d076'


def save(name, data):
    path = HERE / name
    tmp = HERE / (name + '.tmp')
    with tmp.open('w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)
    fd = os.open(HERE, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def run(args, name, timeout=30, check=True):
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    # Separate recovery attempts retain earlier failure logs.
    with (HERE / name).open('ab') as f:
        f.write(p.stdout)
    if check:
        require(p.returncode == 0, 'command failed: ' + str(args))
    return p


def reg(address):
    fd = os.open('/dev/mem', os.O_RDONLY | os.O_SYNC)
    try:
        with mmap.mmap(fd, 4096, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ, offset=address & ~4095) as m:
            return struct.unpack_from('<I', m, address & 4095)[0]
    finally:
        os.close(fd)


def clock():
    rows = [line.split() for line in Path('/sys/kernel/debug/clk/clk_summary').read_text().splitlines()
            if line.split() and line.split()[0] == 'pl0_ref']
    require(len(rows) == 1, 'ambiguous PL0 clock')
    return dict(enable=int(rows[0][1]), prepare=int(rows[0][2]), hz=int(rows[0][4]))


def overlays():
    return sorted(p.read_text().strip() for p in Path('/sys/kernel/config/device-tree/overlays').glob('*/path'))


def ddr():
    fd = os.open('/dev/mem', os.O_RDONLY | os.O_SYNC)
    try:
        with mmap.mmap(fd, 65536, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ, offset=0x63f00000) as m:
            return m[:]
    finally:
        os.close(fd)


def hashes():
    r = json.loads((HERE / 'readiness.json').read_text())
    require(r['passed'], 'readiness failed')
    for name, digest in r['recovery_files_sha256'].items():
        require(hashlib.sha256(Path(name).read_bytes()).hexdigest() == digest, 'recovery file changed: ' + name)


def check_ddr():
    r = json.loads((HERE / 'readiness.json').read_text())
    require(hashlib.sha256(ddr()).hexdigest() == r['reserved_ddr_sha256'], 'reserved DDR changed')


def installed_package():
    expected = package_files(HERE / APP)
    target = Path('/lib/firmware/xilinx') / APP
    # Additive app is already installed. Reuse only after checking every byte;
    # never overwrite an existing directory or fail merely because it exists.
    require(target.is_dir(), 'reviewed additive package must already be installed')
    for name, digest in expected.items():
        require(hashlib.sha256((target / name).read_bytes()).hexdigest() == digest, 'installed app mismatch: ' + name)


def observe():
    return dict(registers={name: reg(address) for name, address in REGISTERS.items()},
                clock=clock(), overlays=overlays(), manager=Path('/sys/class/fpga_manager/fpga0/state').read_text().strip())


def unchanged_registers(before, after):
    for name, value in before.items():
        if name == 'pl0':
            continue
        # Linux may independently idle/wake A53 or USB power islands. Only the
        # RPU/TCM bits are this diagnostic's power-state invariant; retain the
        # complete observations rather than claiming global equality.
        mask = 0xfc00 if name == 'power_state' else 0xffffffff
        require(after[name] & mask == value & mask, 'register changed: ' + name)


def recover():
    state = HERE / 'state.json'
    if not state.exists():
        return
    s = json.loads(state.read_text())
    # Always reverify, including after a previous successful recovery.
    if s['unload_started'] and overlays() != ['k26_starter_kits.dtbo']:
        run(['xmutil', 'unloadapp'], 'recovery-unload.log', check=False)
        run(['xmutil', 'loadapp', STOCK], 'recovery-load.log', timeout=45)
    a = observe()
    save('recovery-observation.json', a)
    require(a['overlays'] == ['k26_starter_kits.dtbo'] and a['manager'] == 'operating', 'stock not operating')
    unchanged_registers(s['before']['registers'], a['registers'])
    verify_idle_clock(s['before']['registers']['pl0'], a['registers']['pl0'], s['before']['clock'], a['clock'])
    hashes()
    check_ddr()
    if s['dashboard_active']:
        run(['systemctl', 'start', SERVICE], 'recovery-dashboard.log')
        run(['systemctl', 'is-active', '--quiet', SERVICE], 'recovery-dashboard-active.log')
    save('recovery.json', dict(passed=True, observed=a, baseline_files_unchanged=True,
                               reserved_ddr_unchanged=True, rpu_unchanged=True))


def trial():
    require(os.geteuid() == 0, 'root required')
    # A writable home-directory parent could replace the frozen staging tree.
    # Require a root-controlled tree before arming privileged execution.
    require(HERE.is_relative_to('/var/lib/sysone/amp-probe'), 'root-controlled staging path required')
    for path in [HERE, *HERE.parents, Path(__file__), HERE / 'amp_probe_guard_policy.py',
                 HERE / 'readiness.json', HERE / 'apu_probe']:
        stat = path.stat()
        require(stat.st_uid == 0 and not stat.st_mode & 0o022 and not path.is_symlink(),
                'staging is not root controlled: ' + str(path))
    require(not (HERE / 'state.json').exists(), 'existing attempt must only be recovered/collected')
    require(os.environ.get('INVOCATION_ID'), 'board-local systemd invocation required')
    # Independent timeout recovery must be armed before any dashboard/PL mutation.
    unit = os.environ.get('SYSONE_PROBE_UNIT', '')
    require(unit.startswith('sysone-guarded-probe-') and all(c.isalnum() or c in '-.' for c in unit), 'invalid unit')
    props = run(['systemctl', 'show', unit, '-p', 'ExecStopPost', '-p', 'TimeoutStartUSec', '-p', 'TimeoutStopUSec'],
                'armed-unit.log').stdout.decode()
    require(str(HERE / 'amp_probe_guarded_target.py') + ' --recover' in props, 'recovery command not armed')
    require('TimeoutStartUSec=2min' in props and 'TimeoutStopUSec=2min' in props, 'bounded unit timeouts missing')
    dt = Path('/sys/firmware/devicetree/base')
    require((dt / 'model').read_bytes().rstrip(b'\0') == b'ZynqMP KR260 revB', 'wrong board')
    require(not list(Path('/sys/class/remoteproc').glob('remoteproc*')), 'remoteproc present')
    reserved = dt / 'reserved-memory/sysone@60000000'
    base, size = struct.unpack('>QQ', (reserved / 'reg').read_bytes())
    require((reserved / 'no-map').exists() and base <= 0x63f00000 and 0x63f10000 <= base + size, 'no-map missing')
    installed_package()
    require(hashlib.sha256((HERE / 'apu_probe').read_bytes()).hexdigest() == APU_SHA256,
            'unreviewed APU executable')
    hashes()
    before = observe()
    require(before['overlays'] == ['k26_starter_kits.dtbo'] and before['manager'] == 'operating', 'stock required')
    require(before['registers']['rpu_reset'] & 3 == 3, 'R5 not reset')
    require(before['registers']['afi'] == 0xa00, 'wrong AFI width')
    require(before['clock']['enable'] == before['clock']['prepare'] == 0, 'unexpected PL0 users')
    require(95_000_000 < before['clock']['hz'] <= 100_000_000, 'clock outside probe limits')
    check_ddr()
    # Fresh stopped-core snapshot, retained before any change; no writes to DDR.
    with (HERE / 'reserved-ddr-before.bin').open('xb') as f:
        f.write(ddr())
        f.flush()
        os.fsync(f.fileno())
    active = subprocess.run(['systemctl', 'is-active', '--quiet', SERVICE]).returncode == 0
    s = dict(before=before, dashboard_active=active, unload_started=False)
    save('state.json', s)
    run(['systemctl', 'stop', SERVICE], 'dashboard-stop.log')
    busy = []
    for maps in Path('/proc').glob('[0-9]*/maps'):
        try:
            for line in maps.read_text().splitlines():
                words = line.split()
                if len(words) >= 6 and words[-1] == '/dev/mem' and 0xa0000000 <= int(words[2], 16) < 0xb0000000:
                    busy.append(str(maps))
        except (FileNotFoundError, ProcessLookupError):
            pass
    require(not busy, 'PL aperture mapped: ' + str(busy))
    s['unload_started'] = True
    save('state.json', s)
    run(['xmutil', 'unloadapp'], 'unload.log')
    run(['xmutil', 'loadapp', APP], 'load.log', timeout=45)
    require(overlays() == [APP + '.dtbo'], 'probe overlay absent')
    require(Path('/sys/class/fpga_manager/fpga0/state').read_text().strip() == 'operating', 'probe not operating')
    amba = (dt / '__symbols__/amba').read_bytes().rstrip(b'\0').decode()
    for node, driver in [('amp-probe-clock', 'xilinx_fclk'), ('amp-probe-afi', 'afi-fpga')]:
        matches = [p for p in Path('/sys/bus/platform/devices').iterdir()
                   if (p / 'of_node').exists() and (p / 'of_node').resolve() == (dt / amba.lstrip('/') / node).resolve()]
        require(len(matches) == 1 and (matches[0] / 'driver').resolve().name == driver, 'driver binding missing: ' + node)
    after = observe()
    verify_running_clock(before['registers']['pl0'], after['registers']['pl0'], before['clock'], after['clock'])
    unchanged_registers(before['registers'], after['registers'])
    result = json.loads(run([str(HERE / 'apu_probe')], 'apu-observations.json', timeout=15).stdout)
    require(result['passed'] and result['writes'] == 64 and result['errors'] == 0, 'APU exact checks failed')
    save('trial.json', dict(passed=True, diagnostic_only=True, r5_executed=False, inference_deployed=False, observed=result))


if __name__ == '__main__':
    import fcntl
    parser = argparse.ArgumentParser()
    parser.add_argument('--recover', action='store_true')
    args = parser.parse_args()
    # A second invocation cannot race recovery against the first controller.
    # systemd releases this process lock on timeout before ExecStopPost runs.
    with (HERE / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.recover:
            recover()
        else:
            try:
                trial()
            finally:
                recover()
