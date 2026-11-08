"""Verify/program RC1 and initialize sealed resident weights under the board lock."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import struct
import subprocess
import sys
import time

BUNDLE = Path(__file__).resolve().parent
STATE = Path('/run/sysone-rc1-init/state.json')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_files(root, hashes):
    root = root.resolve()
    for name, digest in hashes.items():
        path = (root/name).resolve()
        if not path.is_relative_to(root) or sha(path) != digest:
            raise RuntimeError('Pinned file differs: '+str(name))


def run(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    print(json.dumps(dict(command=args, returncode=result.returncode,
                          stdout=result.stdout, stderr=result.stderr)), flush=True)
    result.check_returncode()


def main():
    if os.geteuid() != 0:
        raise RuntimeError('RC1 boot initialization requires root')
    config = json.loads((BUNDLE/'config.json').read_text(encoding='utf-8'))
    package = Path(config['package'])
    state = dict(passed=False, boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                 package=str(package), app=config['app'])
    STATE.parent.mkdir(parents=True, exist_ok=True)
    def save():
        temp = STATE.with_suffix('.new')
        temp.write_text(json.dumps(state, indent=2)+'\n', encoding='utf-8')
        temp.replace(STATE)
    started = time.monotonic()
    with Path('/run/lock/sysone-inference.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            save()
            if platform.release() != config['kernel']:
                raise RuntimeError('Kernel differs from qualified ABI2 module; review/rebuild required')
            verify_files(BUNDLE, json.loads((BUNDLE/'bundle-sha256.json').read_text()))
            if sha(package/'package-sha256.json') != config['package_manifest_sha256']:
                raise RuntimeError('RC1 package manifest differs')
            verify_files(package, json.loads((package/'package-sha256.json').read_text()))
            firmware = Path('/lib/firmware/xilinx')/config['app']
            verify_files(firmware, config['firmware_sha256'])
            if sha(BUNDLE/config['module']) != config['module_sha256']:
                raise RuntimeError('Qualified ABI2 module differs')
            dt = Path('/sys/firmware/devicetree/base')
            reservations = list((dt/'reserved-memory').glob('sysone@*'))
            if len(reservations) != 1 or not (reservations[0]/'no-map').exists():
                raise RuntimeError('Boot scratch reservation absent')
            base, size = struct.unpack('>QQ', (reservations[0]/'reg').read_bytes())
            if base != 0x60000000 or size != 0x10000000:
                raise RuntimeError('Boot scratch reservation differs')
            sys.path.insert(0, str(package/'src'))
            from sysone.v2.qwen_fpga_runtime_candidate import active_firmware, bound, dma_segments
            from sysone.v2.qwen_dma_ownership_v16 import ownership, claim_inference
            from sysone.v2.qwen_weight_verification_v16 import verify_weights
            from load_model import load, assert_idle
            try:
                current = active_firmware()
            except FileNotFoundError:
                current = None
            state['initial_firmware'] = current
            status = Path('/sys/class/misc/sysone_qwen_dma/ownership')
            if status.exists():
                owned = ownership()
                if owned['owner_tgid'] or owned['vmas'] or owned['loading']:
                    raise RuntimeError('Existing DMA owner/mappings; initialization refused')
            if Path('/sys/class/misc/sysone_r5_smoke/status').exists():
                raise RuntimeError('R5 client loaded; initialization refused')
            expected = config['app']+'.bit.bin'
            if current != expected:
                if current not in (None, 'k26-starter-kits.bit.bin'):
                    raise RuntimeError('Unexpected active firmware; operator reconciliation required')
                if current:
                    run(['xmutil', 'unloadapp'])
                run(['xmutil', 'loadapp', config['app']])
            if active_firmware() != expected or Path('/sys/class/fpga_manager/fpga0/state').read_text().strip() != 'operating':
                raise RuntimeError('RC1 FPGA image is not operating')
            bus = dt/(dt/'__symbols__/amba').read_bytes().rstrip(b'\0').decode().lstrip('/')
            for name, driver in [('qwen-clocking0', 'xilinx_fclk'), ('qwen-clocking1', 'xilinx_fclk'), ('qwen-afi', 'afi-fpga')]:
                if not bound(bus/name, driver):
                    raise RuntimeError('Required clock/AXI driver absent: '+name)
            clocks = {p[0]: (int(p[1]), int(p[4])) for line in Path('/sys/kernel/debug/clk/clk_summary').read_text().splitlines()
                      if (p := line.split()) and p[0] in ('pl0_ref', 'pl1_ref')}
            for name, low, high in [('pl0_ref', 124000000, 125000000), ('pl1_ref', 249000000, 250000000)]:
                enabled, hz = clocks.get(name, (0, 0))
                if not enabled or not low <= hz <= high:
                    raise RuntimeError('Clock outside routed profile: '+name)
            state['clocks'] = clocks
            assert_idle()
            if not status.exists():
                if Path('/sys/class/misc/sysone_qwen_dma/buffers').exists():
                    raise RuntimeError('Legacy DMA driver present; initialization refused')
                run(['insmod', str(BUNDLE/config['module']), 'model_bytes=639446688'])
            manifest = json.loads((package/'model-manifest.json').read_text())
            if ownership()['sealed']:
                fd = os.open('/dev/sysone_qwen_dma', os.O_RDWR|os.O_SYNC)
                try:
                    claim_inference(fd)
                    state['weights'] = verify_weights(fd, manifest, *dma_segments())
                    state['model_action'] = 'verified existing sealed model'
                finally:
                    os.close(fd)
            else:
                state['weights'] = load(package, Path(config['model']))
                state['model_action'] = 'loaded, sealed and verified pinned model'
            state['ownership'] = ownership()
            if state['ownership']['owner_tgid'] or state['ownership']['vmas'] or not state['ownership']['sealed']:
                raise RuntimeError('Initialization did not release sealed weights')
            state.update(passed=True, elapsed_seconds=time.monotonic()-started)
            save()
        except BaseException as exc:
            state.update(error=type(exc).__name__+': '+str(exc), elapsed_seconds=time.monotonic()-started)
            save()
            raise
    print(json.dumps(state), flush=True)


if __name__ == '__main__':
    main()
