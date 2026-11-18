"""Finish this qualified build and queue one focused, Linux-live deployment.

Runs only in the active authenticated board window. No scheduler or autostart.
The board runner stops the sequence on any failed job; no automatic retry of NN
commands and no unload after a potentially in-flight hardware request.
"""
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / 'build/v2/qwen-fpga-decoder-v8'
PACKAGE = '/var/lib/sysone/qwen-fpga-decoder-v8'
BOOT = 'e9728928-307d-485b-b40b-63fa29d9296d'


def main():
    state = BUILD / 'completion-queue.json'
    if state.exists():
        raise RuntimeError('Deployment jobs already prepared; inspect receipts before continuing')
    deadline = time.monotonic() + 7200
    log = BUILD / 'vivado-console.log'
    print('Waiting for the routed hardware export; existing decoder stays loaded.', flush=True)
    while True:
        text = log.read_text(errors='replace') if log.exists() else ''
        if 'ERROR:' in text:
            raise RuntimeError('Physical build failed; do not prepare board deployment')
        if 'QWEN_FPGA_ROUTED_READY' in text:
            break
        if time.monotonic() > deadline:
            raise TimeoutError('Physical build deadline; no deployment queued')
        time.sleep(2)
    check = [sys.executable, 'scripts/v2/check_qwen_hls_export_v2.py',
             '--solution', str(BUILD/'hls-release/solution'),
             '--archive', str(BUILD/'qwen_decoder_ip.zip'),
             '--out', str(BUILD/'ip-rtl-consistency.json'),
             '--vivado', str(BUILD/'vivado')]
    subprocess.run(check, cwd=ROOT, check=True)
    with (BUILD/'package-console.log').open('w') as output:
        subprocess.run([sys.executable, 'scripts/v2/package_qwen_fpga_v7.py'],
                       cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, check=True)
    archive = BUILD / 'qwen-fpga-deployment.tar'
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    queue = BUILD / 'board/queue'

    def job(name, value):
        path = queue / (name+'.json')
        if path.exists():
            raise RuntimeError('Existing queue job: '+name)
        temporary = path.with_suffix('.new')
        temporary.write_text(json.dumps(value)+'\n', encoding='utf-8')
        temporary.replace(path)

    def python(name, source, timeout=60):
        job(name, dict(root=True, command='python3 -c '+shlex.quote(source), timeout=timeout))

    python('05-refresh-qualified-baseline', f'''
from pathlib import Path
import sys,mmap,os,struct,json
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=={BOOT!r}
sys.path.insert(0,'/var/lib/sysone/qwen-fpga-decoder-v7/src')
from sysone.v2.qwen_fpga_runtime_v6 import active_firmware
assert active_firmware()=='sysone-qwen-decoder-buffered.bit.bin'
assert Path('/sys/class/fpga_manager/fpga0/state').read_text().strip()=='operating'
clock=[l.split() for l in Path('/sys/kernel/debug/clk/clk_summary').read_text().splitlines() if l.split() and l.split()[0]=='pl0_ref']
assert len(clock)==1 and int(clock[0][1]) and 99000000<=int(clock[0][4])<=100000000
fd=os.open('/dev/mem',os.O_RDONLY|os.O_SYNC)
with mmap.mmap(fd,4096,mmap.MAP_SHARED,mmap.PROT_READ,offset=0xa0000000) as view:control=struct.unpack_from('<I',view,0)[0]
os.close(fd);assert control&4
assert Path('/sys/class/misc/sysone_qwen_dma/buffers').read_text().splitlines()[0]=='model_bytes=639446688 chunk_bytes=16777216 segments=39'
print(json.dumps(dict(linux_boot_id={BOOT!r},firmware=active_firmware(),control=control,clock_hz=int(clock[0][4]))))
''')
    remote = '/home/ubuntu/sysone-qwen-fpga-decoder-v8.tar'
    job('06-upload-qualified-wide-int8', dict(upload=str(archive.resolve()), remote=remote))
    python('07-extract-qualified-wide-int8', f'''
import hashlib,tarfile
from pathlib import Path
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=={BOOT!r}
a=Path({remote!r});assert hashlib.sha256(a.read_bytes()).hexdigest()=={digest!r}
p=Path({PACKAGE!r});p.mkdir(exist_ok=False)
with tarfile.open(a) as archive:archive.extractall(p,filter='data')
print('Verified and extracted timing-qualified buffered decoder')
''')
    for name, script, timeout in [
        ('08-deploy-wide-int8', 'deploy_qwen_fpga_v7.py', 180),
        ('09-causal-hardware-smoke', 'smoke_qwen_fpga_v7.py', 180),
    ]:
        job(name, dict(root=True, command=f'python3 -X faulthandler {PACKAGE}/scripts/v2/{script} --package {PACKAGE}', timeout=timeout))
    query = "Read the Linux boot ID from '/proc/sys/kernel/random/boot_id'."
    job('10-one-cold-real-command', dict(root=True, command=f'python3 -X faulthandler {PACKAGE}/scripts/v2/run_qwen_fpga_command_v7.py --package {PACKAGE} --no-prefix-cache --query '+shlex.quote(query)+f' --out {PACKAGE}/real-command-result.json', timeout=300))
    job('11-promote-faster-deployment', dict(root=True, command=f'python3 {PACKAGE}/scripts/v2/finish_qwen_fpga_v7.py --package {PACKAGE}', timeout=60))
    python('12-collect-deployment-evidence', f'''
from pathlib import Path
import json
p=Path({PACKAGE!r})
names=['deployment-proof.json','real-command-result.json','hardware-block-smoke.json','deployment-state.json']
data={{name:json.loads((p/name).read_text()) for name in names}}
data['residency_reused']=True
data['linux_boot_id_now']=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
print(json.dumps(data))
''')
    state.write_text(json.dumps(dict(queued=True,archive_sha256=digest,linux_boot_id=BOOT,
                                    real_commands_requested=1,benchmark_sweep=False),indent=2)+'\n')
    print('Qualified deployment, one hardware fixture and one real cold command queued.', flush=True)


if __name__ == '__main__':
    main()
