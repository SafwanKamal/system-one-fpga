"""Write the bounded v9d board-validation queue (no full sweep).

Jobs: read-only inventory, upload, verified extract, swap v8->v9d, causal smoke,
long prompt, a same-session v9c long-prompt control,
and timing microbenchmark, three cold real commands, restore v8, one v8 control
command on the same boot, final inventory. Evidence goes to a new board
directory; neither the sealed v8 package nor the v9d package is written.
"""
import argparse,hashlib,json,shlex
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BUILD=ROOT/'build/v2/qwen-fpga-decoder-v9d'
ARCHIVE=BUILD/'qwen-fpga-v9d-deployment.tar'
REMOTE_TAR='/home/ubuntu/sysone-qwen-fpga-decoder-v9d-candidate1.tar'
PACKAGE='/var/lib/sysone/qwen-fpga-decoder-v9d-candidate1'
EVIDENCE='/var/lib/sysone/qwen-v9d-evidence-1'
V8_PACKAGE='/var/lib/sysone/qwen-fpga-decoder-v8-startup-v2'
V9C_PACKAGE='/var/lib/sysone/qwen-fpga-decoder-v9c-candidate1'
QUERY="Read the Linux boot ID from '/proc/sys/kernel/random/boot_id'."
# Hardware-capacity check only (>256 prompt tokens, impossible on v8); neutral filler,
# not an evaluation case. Model correctness on it is recorded, not assumed.
LONG_QUERY='Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. '+QUERY

INVENTORY=r'''python3 - <<'EOF'
import hashlib,json,subprocess,sys
from pathlib import Path
sys.path.insert(0,'/var/lib/sysone/qwen-fpga-decoder-v8-startup-v2/src')
from sysone.v2.qwen_fpga_runtime_v7 import active_firmware
dt=Path('/sys/firmware/devicetree/base')
clk=[s.split() for s in Path('/sys/kernel/debug/clk/clk_summary').read_text().splitlines() if s.split() and s.split()[0] in ('pl0_ref','pl1_ref')]
dma=Path('/sys/class/misc/sysone_qwen_dma/buffers')
reserved=list((dt/'reserved-memory').glob('sysone@*'))
import struct
mem=[struct.unpack('>QQ',(r/'reg').read_bytes()) for r in reserved]
launcher=Path('/usr/local/bin/sysone-qwen-fpga')
def run(a):
    try:return subprocess.run(a,capture_output=True,text=True,timeout=20).stdout
    except Exception as e:return repr(e)
print(json.dumps(dict(
 boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
 firmware=active_firmware(),fpga_state=Path('/sys/class/fpga_manager/fpga0/state').read_text().strip(),
 clocks={c[0]:dict(enable=int(c[1]),rate_hz=int(c[4])) for c in clk},
 dma_header=dma.read_text().splitlines()[0] if dma.exists() else None,
 dma_table_sha256=hashlib.sha256(dma.read_bytes()).hexdigest() if dma.exists() else None,
 scratch_reservation=[dict(base=hex(b),size=s) for b,s in mem],
 launcher_sha256=hashlib.sha256(launcher.read_bytes()).hexdigest() if launcher.exists() else None,
 v8_package_present=Path('/var/lib/sysone/qwen-fpga-decoder-v8-startup-v2/package-sha256.json').exists(),
 installed_apps=sorted(p.name for p in Path('/lib/firmware/xilinx').iterdir()),
 lock_holders=run(['fuser','-v','/run/lock/sysone-inference.lock']),
 python_processes=[l for l in run(['ps','-eo','pid,etimes,args']).splitlines() if 'python' in l and 'ps -eo' not in l],
 mvp_service=run(['systemctl','show','-p','ActiveState','-p','SubState','sysone-qwen06b-mvp.service']).split(),
 r5_loaded=Path('/sys/class/misc/sysone_r5_smoke/status').exists(),
 xmutil=run(['xmutil','listapps'])),indent=1))
EOF'''


def job(command,timeout=60,root=True):
    return dict(root=root,command=command,timeout=timeout)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--work',type=Path,default=BUILD/'board');args=ap.parse_args()
    digest=hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    # Staged, not queued: the window runs anything in queue/, so jobs are moved
    # there one gate at a time after the reservation and each check.
    queue=args.work/'pending';queue.mkdir(parents=True,exist_ok=False);(args.work/'queue').mkdir(exist_ok=True);(args.work/'results').mkdir(exist_ok=True)
    py='python3 -X faulthandler '
    extract=f'''python3 - <<'EOF'
import hashlib,json,tarfile
from pathlib import Path
a=Path({REMOTE_TAR!r});assert hashlib.sha256(a.read_bytes()).hexdigest()=={digest!r}
p=Path({PACKAGE!r});p.mkdir(exist_ok=False);Path({EVIDENCE!r}).mkdir(exist_ok=False)
with tarfile.open(a) as archive:archive.extractall(p,filter='data')
hashes=json.loads((p/'package-sha256.json').read_text())
for name,d in hashes.items():assert hashlib.sha256((p/name).read_bytes()).hexdigest()==d,name
print(json.dumps(dict(extracted=str(p),files=len(hashes),archive_sha256={digest!r})))
EOF'''
    command=lambda package,runner,out:(py+f'{package}/scripts/v2/{runner} --package {package} --no-prefix-cache '
                                       f'--query {shlex.quote(QUERY)} --out {EVIDENCE}/{out}')
    jobs=[('00-inventory',job(INVENTORY,30)),
          ('01-upload-candidate',dict(upload=str(ARCHIVE),remote=REMOTE_TAR)),
          ('02-extract-candidate',job(extract,90)),
          ('03-deploy-candidate',job(py+f'{PACKAGE}/scripts/v2/deploy_qwen_fpga_v9d.py --package {PACKAGE} --direction candidate --out {EVIDENCE}/03-deploy.json',120)),
          ('04-causal-smoke',job(py+f'{PACKAGE}/scripts/v2/smoke_qwen_fpga_v9d.py --package {PACKAGE} --out {EVIDENCE}/04-smoke',300)),
          ('05-command-v9d-1',job(command(PACKAGE,'run_qwen_fpga_command_v9d.py','05-command-v9d-1.json'),300)),
          ('06-command-v9d-2',job(command(PACKAGE,'run_qwen_fpga_command_v9d.py','06-command-v9d-2.json'),300)),
          ('07-long-prompt-v9d',job(py+f'{PACKAGE}/scripts/v2/run_qwen_fpga_command_v9d.py --package {PACKAGE} --no-prefix-cache '
                                    f'--query {shlex.quote(LONG_QUERY)} --out {EVIDENCE}/07-long-prompt-v9d.json',300)),
          ('08-restore-v8',job(py+f'{PACKAGE}/scripts/v2/deploy_qwen_fpga_v9d.py --package {PACKAGE} --direction restore --out {EVIDENCE}/08-restore.json',120)),
          ('09-command-v8-control',job(command(V8_PACKAGE,'run_qwen_fpga_command_v7.py','09-command-v8-control.json'),300)),
          # Same-session v9c control for the long prompt (v9c package already installed).
          ('10-deploy-v9c-control',job(py+f'{V9C_PACKAGE}/scripts/v2/deploy_qwen_fpga_v9c.py --package {V9C_PACKAGE} --direction candidate --out {EVIDENCE}/10-deploy-v9c.json',120)),
          ('11-long-prompt-v9c-control',job(py+f'{V9C_PACKAGE}/scripts/v2/run_qwen_fpga_command_v9c.py --package {V9C_PACKAGE} --no-prefix-cache '
                                    f'--query {shlex.quote(LONG_QUERY)} --out {EVIDENCE}/11-long-prompt-v9c-control.json',300)),
          ('12-restore-v8-from-v9c',job(py+f'{V9C_PACKAGE}/scripts/v2/deploy_qwen_fpga_v9c.py --package {V9C_PACKAGE} --direction restore --out {EVIDENCE}/12-restore.json',120)),
          ('13-final-inventory',job(INVENTORY,30)),
          ('14-collect-evidence',job(f'cd {EVIDENCE} && for f in $(find . -name "*.json" | sort); do echo "=== $f"; cat "$f"; done',30)),
          ('99-close-session',dict(close=True))]
    # Build-3 jobs are numbered 2x/3x so a still-open board window (which skips
    # completed names) runs them without a restart.
    for name,body in jobs:(queue/(name+'.json')).write_text(json.dumps(body)+'\n')
    print(json.dumps(dict(queue=str(queue),jobs=[n for n,_ in jobs],archive_sha256=digest)))

if __name__=='__main__':main()
