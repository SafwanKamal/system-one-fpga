"""Fresh read-only Linux/RPU inventory; password stays in terminal/process memory.

Run interactively from a local terminal. No reset, clock, power, PL programming,
remoteproc bind, DDR write, or boot changes. Prior receipts are never overwritten.
"""
import argparse
import base64
import getpass
import hashlib
import json
from pathlib import Path
import re
import shlex
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'build/v2/typed200-amp-rpu-diagnostic-v1'
sys.path[:0] = [str(ROOT / 'build/v2/typed200-amp-candidate-v1/auth-deps'),
               str(ROOT / 'build/v2/board-auth-tools')]
import paramiko

FINGERPRINT = 'EGYkdZirFAYH1XOF2uPZYSzmLMOj7obcj/xAeHIW/Qc'
CODE = '''from pathlib import Path
import hashlib,json,mmap,os,struct,subprocess,time
dt=Path('/sys/firmware/devicetree/base')
assert (dt/'model').read_bytes().rstrip(b'\\0')==b'ZynqMP KR260 revB'
reserved=dt/'reserved-memory/sysone@60000000'
base,size=struct.unpack('>QQ',(reserved/'reg').read_bytes())
assert (reserved/'no-map').exists() and base<=0x63f00000 and 0x63f10000<=base+size
addresses=dict(power_state=0xffd80100,rpu_global=0xff9a0000,rpu0_cfg=0xff9a0100,
 rpu1_cfg=0xff9a0200,r5_clock=0xff5e0090,lpd_reset=0xff5e023c,pl0=0xff5e00c0,afi=0xfd615000)
fd=os.open('/dev/mem',os.O_RDONLY|os.O_SYNC)
registers={}
for name,address in addresses.items():
 with mmap.mmap(fd,4096,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ,offset=address&~4095) as m:
  registers[name]=struct.unpack_from('<I',m,address&4095)[0]
assert registers['lpd_reset']&3==3
with mmap.mmap(fd,65536,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ,offset=0x63f00000) as m:
 ddr_hash=hashlib.sha256(m[:]).hexdigest()
os.close(fd)
remoteproc=[dict(path=str(p),name=(p/'name').read_text(),state=(p/'state').read_text())
 for p in Path('/sys/class/remoteproc').glob('remoteproc*')]
drivers=[]
for p in Path('/sys/bus/platform/devices').iterdir():
 if any(s in p.name.lower() for s in ['r5','rpu','remoteproc']):
  drivers.append(dict(path=str(p),driver=str((p/'driver').resolve()) if (p/'driver').exists() else None))
rpu_nodes=[]
for p in dt.rglob('*'):
 if p.is_dir() and ('r5f' in p.name.lower() or 'rpu' in p.name.lower()):
  rpu_nodes.append(dict(path=str(p),status=(p/'status').read_bytes().rstrip(b'\\0').decode() if (p/'status').exists() else 'okay (default)'))
def command(argv):
 p=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20)
 return dict(exit=p.returncode,stdout=p.stdout.decode(errors='replace'),stderr=p.stderr.decode(errors='replace'))
files={}
for app,stem in [('k26-starter-kits','k26_starter_kits'),('sysone-v2-attention-context-capture','sysone-v2-attention-context-capture')]:
 for name in [stem+'.bit.bin',stem+'.dtbo','shell.json']:
  p=Path('/lib/firmware/xilinx')/app/name
  files[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
probe=Path('/lib/firmware/xilinx/sysone-amp-origin-probe')
probe_files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in probe.iterdir() if p.is_file()}
print(json.dumps(dict(registers=registers,remoteproc=remoteproc,rpu_platform_devices=drivers,rpu_dt_nodes=rpu_nodes,
 no_map=dict(base=base,size=size),reserved_ddr_sha256=ddr_hash,recovery_files_sha256=files,
 installed_probe_sha256=probe_files,apps=command(['xmutil','listapps']),
 clock_summary=Path('/sys/kernel/debug/clk/clk_summary').read_text(),
 cpu_online=Path('/sys/devices/system/cpu/online').read_text(),
 overlays=sorted(p.read_text().strip() for p in Path('/sys/kernel/config/device-tree/overlays').glob('*/path')),
 observed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))))
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--attempt', required=True)
    ap.add_argument('--host', default='192.168.0.239')
    args = ap.parse_args()
    if not re.fullmatch(r'inventory-v[0-9]+', args.attempt):
        ap.error('attempt must be inventory-vN')
    out = BASE / args.attempt
    out.mkdir(exist_ok=False)
    (out / 'read-only-command.py').write_text(CODE)
    client = paramiko.SSHClient()
    client.load_host_keys(str(Path.home() / '.ssh/known_hosts'))
    # Check the saved entry itself before any authentication, then use the
    # default RejectPolicy so the connection cannot enroll a different key.
    keys = client.get_host_keys().lookup(args.host)
    if not keys or 'ssh-ed25519' not in keys:
        raise RuntimeError('saved Ed25519 host key absent; do not autoaccept')
    finger = base64.b64encode(hashlib.sha256(keys['ssh-ed25519'].asbytes()).digest()).decode().rstrip('=')
    if finger != FINGERPRINT:
        raise RuntimeError('saved host key differs from pinned board identity')

    def transport(sock, **kwargs):
        t = paramiko.Transport(sock, **kwargs)
        options = t.get_security_options()
        options.kex = ('curve25519-sha256@libssh.org',)
        options.key_types = ('ssh-ed25519',)
        options.ciphers = ('aes128-ctr',)
        options.digests = ('hmac-sha2-256',)
        return t

    password = getpass.getpass('KR260 SSH/sudo password (memory only, not recorded): ')
    try:
        client.connect(args.host, username='ubuntu', password=password, look_for_keys=False, allow_agent=False,
                       timeout=15, auth_timeout=15, banner_timeout=10, transport_factory=transport)
        remote_key = client.get_transport().get_remote_server_key()
        if remote_key.asbytes() != keys['ssh-ed25519'].asbytes():
            raise RuntimeError('remote key differs from saved key')
        stdin, stdout, stderr = client.exec_command('sudo -S -p "" python3 -c ' + shlex.quote(CODE), timeout=60)
        stdin.write(password + '\n')
        stdin.flush()
        data, error = stdout.read(), stderr.read()
        code = stdout.channel.recv_exit_status()
        (out / 'stdout.json').write_bytes(data)
        (out / 'stderr.txt').write_bytes(error)
        if code:
            raise RuntimeError('read-only inventory command failed; see attempt logs')
        observed = json.loads(data)
        baseline = json.loads((ROOT / 'build/v2/typed200-amp-deployment-v1/board-readiness-v4/receipt.json').read_text())
        if observed['recovery_files_sha256'] != baseline['recovery_files_sha256']:
            raise RuntimeError('stock/qualified application identities differ from sealed baseline')
        sys.path.insert(0, str(ROOT / 'scripts/v2'))
        from amp_probe_guard_policy import APP, package_files, rpu_start_blockers
        expected = package_files(ROOT / 'build/v2/typed200-amp-deployment-v1/probe-package-v1' / APP)
        if any(observed['installed_probe_sha256'].get(n) != h for n, h in expected.items()):
            raise RuntimeError('installed diagnostic package differs from reviewed package')
        receipt = dict(passed=True, read_only=True, host_key_sha256=FINGERPRINT,
                       observed_utc=observed['observed_utc'], recovery_files_sha256=observed['recovery_files_sha256'],
                       reserved_ddr_sha256=observed['reserved_ddr_sha256'],
                       rpu_start_blockers=rpu_start_blockers(observed['registers']),
                       r5_run_ready=False, target_modified=False)
        (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print('PASS read-only inventory; R5 startup remains gated. Evidence: ' + str(out))
    except Exception as exc:
        (out / 'failure.json').write_text(json.dumps(dict(passed=False, error_type=type(exc).__name__,
                                            observed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())), indent=2) + '\n')
        raise
    finally:
        password = None
        client.close()


if __name__ == '__main__':
    main()
