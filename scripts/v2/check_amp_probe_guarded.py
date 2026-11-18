"""Offline fault-injection checks of the actual diagnostic recovery controller."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import amp_probe_guarded_target as target
from amp_probe_guard_policy import package_files, rpu_start_blockers, verify_idle_clock, verify_running_clock

ROOT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(exist_ok=False)
    cases = []

    def case(name, fn, rejects=False):
        try:
            fn()
        except RuntimeError:
            if not rejects:
                raise
        else:
            if rejects:
                raise AssertionError('fault accepted: ' + name)
        cases.append(name)

    idle = dict(enable=0, prepare=0, hz=99_999_999)
    running = dict(enable=1, prepare=1, hz=99_999_999)
    for initial, final in [(0x1010a00, 0x10a00), (0x10a00, 0x10a00), (0x1010a00, 0x1010a00)]:
        case(f'idle-{initial:x}-{final:x}', lambda: verify_idle_clock(initial, final, idle, idle))
    for bit in range(32):
        if bit != 24:
            case(f'idle-register-bit-{bit}', lambda b=bit: verify_idle_clock(0x1010a00, 0x10a00 ^ (1 << b), idle, idle), True)
    case('idle-no-force-on', lambda: verify_idle_clock(0x10a00, 0x1010a00, idle, idle), True)
    for field in idle:
        changed = dict(idle)
        changed[field] += 1
        case('idle-' + field, lambda: verify_idle_clock(0x10a00, 0x10a00, idle, changed), True)
    for initial in [0x10a00, 0x1010a00]:
        case(f'running-{initial:x}', lambda: verify_running_clock(initial, 0x1010a00, idle, running))
    case('running-no-gate', lambda: verify_running_clock(0x10a00, 0x10a00, idle, running), True)
    case('running-no-consumer', lambda: verify_running_clock(0x10a00, 0x1010a00, idle, idle), True)
    case('running-rate-change', lambda: verify_running_clock(0x10a00, 0x1010a00, idle, dict(running, hz=100_000_001)), True)

    pkg = ROOT / 'build/v2/typed200-amp-deployment-v1/probe-package-v1/sysone-amp-origin-probe'
    case('existing-reviewed-package', lambda: package_files(pkg))
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        for name in package_files(pkg):
            (p / name).write_bytes((pkg / name).read_bytes())
        for name in package_files(pkg):
            data = (p / name).read_bytes()
            (p / name).write_bytes(data + b'x')
            case('package-mutation-' + name, lambda: package_files(p), True)
            (p / name).write_bytes(data)

    regs = dict(afi=0xa00, pl0=0x1010a00, rpu_reset=0x13, rpu_global=0x50,
                rpu0_cfg=4, rpu1_cfg=4, r5_clock=0x1000200, power_state=0xff008f)
    before = dict(registers=regs, clock=idle, overlays=['k26_starter_kits.dtbo'], manager='operating')
    recovered = copy.deepcopy(before)
    recovered['registers']['pl0'] = 0x10a00
    state = dict(before=before, dashboard_active=True, unload_started=True)
    # Run the actual recovery path with injected I/O; prove recovery is repeated
    # and reverified, and never load an image unnecessarily when stock is active.
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        (p / 'state.json').write_text(json.dumps(state))
        actions = []

        def run(argv, *a, **kw):
            actions.append(argv)

        with patch.object(target, 'HERE', p), patch.object(target, 'save', lambda n, d: (p / n).write_text(json.dumps(d))), \
             patch.object(target, 'run', run), patch.object(target, 'hashes') as hashes, \
             patch.object(target, 'check_ddr') as ddr, patch.object(target, 'observe', return_value=recovered) as observe, \
             patch.object(target, 'overlays', return_value=['k26_starter_kits.dtbo']) as overlays:
            case('recovery-stock-active', target.recover)
            case('recovery-repeat-reverifies', target.recover)
            assert observe.call_count == hashes.call_count == ddr.call_count == 2
            assert not any(a[0] == 'xmutil' for a in actions)
            assert ['systemctl', 'is-active', '--quiet', target.SERVICE] in actions
            overlays.return_value = ['sysone-amp-origin-probe.dtbo']
            actions.clear()
            case('recovery-probe-active', target.recover)
            assert actions[:2] == [['xmutil', 'unloadapp'], ['xmutil', 'loadapp', 'k26-starter-kits']]
            def failed_load(argv, *a, **kw):
                if argv[:2] == ['xmutil', 'loadapp']:
                    raise RuntimeError('injected stock load failure')
                actions.append(argv)
            with patch.object(target, 'run', failed_load):
                actions.clear()
                case('stock-load-failure-stays-failed', target.recover, True)
                assert not any(a[:2] == ['systemctl', 'start'] for a in actions)
            overlays.return_value = ['k26_starter_kits.dtbo']
            for name in regs:
                if name == 'pl0':
                    continue
                changed = copy.deepcopy(recovered)
                changed['registers'][name] ^= 0x400 if name == 'power_state' else 1
                observe.return_value = changed
                actions.clear()
                case('recovery-register-fault-' + name, target.recover, True)
                assert not any(a[:2] == ['systemctl', 'start'] for a in actions)
            observe.return_value = recovered
            for dependency in [hashes, ddr]:
                dependency.side_effect = RuntimeError('injected corruption')
                case('recovery-baseline-corrupt' if dependency is hashes else 'recovery-ddr-corrupt', target.recover, True)
                dependency.side_effect = None
            def failed_dashboard(argv, *a, **kw):
                if argv[:2] == ['systemctl', 'is-active']:
                    raise RuntimeError('injected inactive dashboard')
            with patch.object(target, 'run', failed_dashboard):
                case('dashboard-restart-not-confirmed', target.recover, True)
            for field, value in [('manager', 'error'), ('overlays', ['wrong.dtbo'])]:
                changed = copy.deepcopy(recovered)
                changed[field] = value
                observe.return_value = changed
                case('recovery-' + field, target.recover, True)
            observe.return_value = copy.deepcopy(recovered)
            observe.return_value['registers']['power_state'] ^= 1
            case('linux-apu-idle-independent', target.recover)
    r = dict(power_state=0xff008f, r5_clock=0x1000200, lpd_reset=0x13,
             rpu0_cfg=4, rpu1_cfg=4, rpu_global=0x50)
    blockers = rpu_start_blockers(r)
    assert len(blockers) == 5
    cases.append('actual-RPU-off-refuses-start')
    ready = dict(r, power_state=0xff0c8f, r5_clock=0x3000200)
    assert rpu_start_blockers(ready) == blockers[2:]
    cases.append('power-on-alone-insufficient')
    assert rpu_start_blockers(ready, True, True, True) == []
    for name, mask in [('lpd_reset', 1), ('rpu0_cfg', 1), ('rpu1_cfg', 1), ('rpu_global', 8), ('r5_clock', 0x2000000)]:
        mutated = dict(ready)
        mutated[name] ^= mask
        assert rpu_start_blockers(mutated, True, True, True)
        cases.append('RPU-readiness-fault-' + name)
    sources = [Path(__file__), ROOT / 'scripts/v2/amp_probe_guard_policy.py', ROOT / 'scripts/v2/amp_probe_guarded_target.py']
    result = dict(passed=True, cases=len(cases), checks=cases, target_executed=False,
                  r5_start_implemented=False, software_fault_injection_only=True,
                  source_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    (args.out / 'receipt.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f'PASS {len(cases)} offline recovery/policy fault cases; no target mutation')


if __name__ == '__main__':
    main()
