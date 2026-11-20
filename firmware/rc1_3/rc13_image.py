"""RC1.3 FPGA image switch: `up` makes v9h active (from v9e), `down` makes v9e active (from v9h).

Idempotent: if the target image is already active it only verifies it. Run as root with the
inference lock free (systemd ExecStartPre / ExecStopPost of sysone-rc1.service). Linux, the
sealed model and the DMA residency table are not changed; a failed load reloads the source.
The boot initializer still loads v9e and seals the model; RC1.3 switches to v9h on service
start and back to v9e on service stop, so v9e stays the resting image for all other tools.
"""
import fcntl, hashlib, json, mmap, os, struct, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
V9E, V9H = 'sysone-qwen-decoder-v9e', 'sysone-qwen-decoder-v9h'
DT = Path('/sys/firmware/devicetree/base')
FIRMWARE = Path('/lib/firmware/xilinx')
LOG = Path('/var/lib/sysone/qualifications/rc1-3/image.jsonl')


def run(argv):
    r = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)
    print(r.stdout.decode(errors='replace'), flush=True)
    r.check_returncode()


def active():
    try:
        region = DT / (DT / '__symbols__/fpga_full').read_bytes().rstrip(b'\0').decode().lstrip('/')
        return (region / 'firmware-name').read_bytes().rstrip(b'\0').decode()
    except FileNotFoundError:
        return None


def idle():
    fd = os.open('/dev/mem', os.O_RDONLY | os.O_SYNC)
    try:
        with mmap.mmap(fd, 4096, mmap.MAP_SHARED, mmap.PROT_READ, offset=0xa0000000) as regs:
            return bool(struct.unpack_from('<I', regs, 0)[0] & 4)
    finally:
        os.close(fd)


def verify(app):
    if Path('/sys/class/fpga_manager/fpga0/state').read_text().strip() != 'operating' or active() != app + '.bit.bin':
        raise RuntimeError('Image not operating: ' + str(active()))
    if not idle():
        raise RuntimeError('Decoder not idle after load')


def main():
    direction = sys.argv[1]
    source, target = (V9E, V9H) if direction == 'up' else (V9H, V9E)
    cfg = json.loads((HERE / 'config.json').read_text())
    if direction == 'up':
        for name, digest in cfg['v9h_firmware_sha256'].items():
            if hashlib.sha256((FIRMWARE / V9H / name).read_bytes()).hexdigest() != digest:
                raise RuntimeError('Installed v9h firmware differs: ' + name)
    rec = dict(direction=direction, utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), before=active())
    with open('/run/lock/sysone-inference.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if active() == target + '.bit.bin':
            verify(target); rec['action'] = 'already active'
        else:
            if active() != source + '.bit.bin':
                raise RuntimeError('Unexpected image: ' + str(active()))
            if not idle():
                raise RuntimeError('Decoder busy; not reprogramming')
            before = Path('/sys/class/misc/sysone_qwen_dma/buffers').read_text()
            try:
                run(['xmutil', 'unloadapp']); run(['xmutil', 'loadapp', target]); verify(target)
            except Exception:
                run(['xmutil', 'unloadapp']); run(['xmutil', 'loadapp', source]); verify(source)
                raise
            if Path('/sys/class/misc/sysone_qwen_dma/buffers').read_text() != before:
                raise RuntimeError('DMA residency table changed')
            rec['action'] = 'switched'
    rec['after'] = active()
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open('a') as f:
        f.write(json.dumps(rec) + '\n')
    print(json.dumps(rec), flush=True)


if __name__ == '__main__':
    main()
