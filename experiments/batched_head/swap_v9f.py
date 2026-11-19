"""Swap the active FPGA app between v9e (RC1) and the v9f pilot image, with rollback.

Same procedure as scripts/v2/deploy_qwen_fpga_v9e.py (xmutil unloadapp/loadapp).
  --direction candidate   v9e -> v9f (installs /lib/firmware/xilinx/sysone-qwen-decoder-v9f from --app)
  --direction restore     v9f -> v9e
Requires sysone-rc1.service stopped (the inference lock is taken non-blocking), the decoder
idle, no live PL MMIO client, and an unchanged DMA residency table. Linux, the sealed model
and all RC1 files are not changed. A failed load reloads the source image.
"""
import argparse, fcntl, hashlib, json, mmap, os, shutil, struct, subprocess
from pathlib import Path

V9E, V9F = 'sysone-qwen-decoder-v9e', 'sysone-qwen-decoder-v9f'
DT = Path('/sys/firmware/devicetree/base')
LOCK = Path('/run/lock/sysone-inference.lock')
FIRMWARE = Path('/lib/firmware/xilinx')


def run(argv):
    r = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)
    text = r.stdout.decode(errors='replace'); print(text, flush=True)
    r.check_returncode(); return text


def active_firmware():
    try:
        region = DT / (DT / '__symbols__/fpga_full').read_bytes().rstrip(b'\0').decode().lstrip('/')
        return (region / 'firmware-name').read_bytes().rstrip(b'\0').decode()
    except FileNotFoundError:
        return None


def bound(node, driver):
    for device in Path('/sys/bus/platform/devices').iterdir():
        of_node = device / 'of_node'; binding = device / 'driver'
        if of_node.exists() and of_node.resolve() == node.resolve():
            return binding.exists() and binding.resolve().name == driver
    return False


def control():
    fd = os.open('/dev/mem', os.O_RDONLY | os.O_SYNC)
    try:
        with mmap.mmap(fd, 4096, mmap.MAP_SHARED, mmap.PROT_READ, offset=0xa0000000) as regs:
            return struct.unpack_from('<I', regs, 0)[0]
    finally:
        os.close(fd)


def clock(name):
    rows = [l.split() for l in Path('/sys/kernel/debug/clk/clk_summary').read_text().splitlines() if l.split() and l.split()[0] == name]
    if len(rows) != 1 or not int(rows[0][1]):
        raise RuntimeError('Clock unavailable: ' + name)
    return int(rows[0][4])


def verify_loaded(app):
    if Path('/sys/class/fpga_manager/fpga0/state').read_text().strip() != 'operating':
        raise RuntimeError('FPGA manager not operating')
    if active_firmware() != app + '.bit.bin':
        raise RuntimeError('Wrong loaded image: ' + str(active_firmware()))
    bus = DT / (DT / '__symbols__/amba').read_bytes().rstrip(b'\0').decode().lstrip('/')
    if not all(bound(bus / n, d) for n, d in (('qwen-clocking0', 'xilinx_fclk'), ('qwen-clocking1', 'xilinx_fclk'), ('qwen-afi', 'afi-fpga'))):
        raise RuntimeError('Clock or AXI driver not bound')
    dec, mem = clock('pl0_ref'), clock('pl1_ref')
    if not 124000000 <= dec <= 125000000 or not 249000000 <= mem <= 250000000:
        raise RuntimeError('Clocks outside routed profile')
    c = control()
    if not c & 4:
        raise RuntimeError('Loaded decoder is not idle')
    return dict(decoder_clock_hz=dec, memory_clock_hz=mem, control=c, firmware=active_firmware())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--direction', choices=['candidate', 'restore'], required=True)
    ap.add_argument('--app', type=Path, help='unpacked pilot app directory (candidate only)')
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    if os.geteuid() != 0:
        raise RuntimeError('Root required')
    source, target = (V9E, V9F) if a.direction == 'candidate' else (V9F, V9E)
    if not (FIRMWARE / V9E / (V9E + '.bit.bin')).is_file():
        raise RuntimeError('v9e image not installed')
    if a.direction == 'candidate':
        hashes = json.loads((a.app.parent / 'pilot-sha256.json').read_text())
        for name, digest in hashes.items():
            if name.startswith(V9F + '/') and hashlib.sha256((a.app.parent / name).read_bytes()).hexdigest() != digest:
                raise RuntimeError('Pilot app differs: ' + name)
        dtbo = a.out.with_suffix('.dtbo')
        run(['dtc', '-@', '-I', 'dts', '-O', 'dtb', '-o', str(dtbo), str(a.app / (V9F + '.dts'))])
        installed = FIRMWARE / V9F
        files = [(V9F + '.bit.bin', a.app / (V9F + '.bit.bin')), (V9F + '.dtbo', dtbo), ('shell.json', a.app / 'shell.json')]
        if installed.exists():
            for name, local in files:
                if (installed / name).read_bytes() != local.read_bytes():
                    raise RuntimeError('Installed v9f app differs; preserve it')
        else:
            installed.mkdir()
            for name, local in files:
                shutil.copyfile(local, installed / name)
            shutil.copyfile(a.app / 'build.json', installed / 'build.json')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    lock = LOCK.open('a'); fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    state = dict(direction=a.direction, source=source, target=target, linux_boot_id=boot, complete=False)
    save = lambda: a.out.write_text(json.dumps(state, indent=2) + '\n')
    try:
        if active_firmware() != source + '.bit.bin':
            raise RuntimeError('Unexpected current FPGA image: ' + str(active_firmware()))
        if not control() & 4:
            raise RuntimeError('Current decoder not idle; do not reprogram')
        for maps in Path('/proc').glob('[0-9]*/maps'):
            try:
                for line in maps.read_text().splitlines():
                    f = line.split()
                    if len(f) >= 6 and f[-1] == '/dev/mem' and 0xa0000000 <= int(f[2], 16) < 0xb0000000:
                        raise RuntimeError('Live PL MMIO client: ' + str(maps))
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                pass
        before = Path('/sys/class/misc/sysone_qwen_dma/buffers').read_text()
        state['dma_buffers_sha256_before'] = hashlib.sha256(before.encode()).hexdigest(); save()
        try:
            run(['xmutil', 'unloadapp']); run(['xmutil', 'loadapp', target])
            state['loaded'] = verify_loaded(target)
        except Exception as exc:
            state['error'] = str(exc); save()
            run(['xmutil', 'unloadapp']); run(['xmutil', 'loadapp', source])
            state['rolled_back'] = verify_loaded(source); save(); raise
        if Path('/proc/sys/kernel/random/boot_id').read_text().strip() != boot:
            raise RuntimeError('Linux boot changed')
        after = Path('/sys/class/misc/sysone_qwen_dma/buffers').read_text()
        state['dma_buffers_sha256_after'] = hashlib.sha256(after.encode()).hexdigest()
        if after != before:
            raise RuntimeError('DMA residency table changed')
        state['complete'] = True; save()
    finally:
        lock.close()
    print(json.dumps(state, indent=2))
    print('SWAP ' + a.direction.upper() + ': OK', flush=True)


if __name__ == '__main__':
    main()
