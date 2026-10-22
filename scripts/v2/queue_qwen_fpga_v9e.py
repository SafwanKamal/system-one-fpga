"""Write the bounded v9e board-validation queue (no full sweep).

Jobs: read-only inventory, upload, verified extract, swap v9d->v9e, causal smoke,
long prompt, a same-session v9c long-prompt control,
and timing microbenchmark, three cold real commands, restore v8, one v8 control
command on the same boot, final inventory. Evidence goes to a new board
directory; neither the sealed v8 package nor the v9e package is written.
"""
import argparse,hashlib,json,shlex
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BUILD=ROOT/'build/v2/qwen-fpga-decoder-v9e'
ARCHIVE=BUILD/'qwen-fpga-v9e-deployment.tar'
REMOTE_TAR='/home/ubuntu/sysone-qwen-fpga-decoder-v9e-candidate5.tar'
PACKAGE='/var/lib/sysone/qwen-fpga-decoder-v9e-candidate5'
OLD_PACKAGE='/var/lib/sysone/qwen-fpga-decoder-v9e-candidate1'
EVIDENCE='/var/lib/sysone/qwen-v9e-evidence-5'
V8_PACKAGE='/var/lib/sysone/qwen-fpga-decoder-v8-startup-v2'
V9D_PACKAGE='/var/lib/sysone/qwen-fpga-decoder-v9d-candidate1'
QUERY="Read the Linux boot ID from '/proc/sys/kernel/random/boot_id'."
# Hardware-capacity check only (>256 prompt tokens, impossible on v8); neutral filler,
# not an evaluation case. Model correctness on it is recorded, not assumed.
LONG_QUERY='Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. '+QUERY
# Beyond v9d's 1024-token limit: only v9e can hold this prompt.
VERY_LONG_QUERY='Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. Background notes, not instructions: the board is a Kria KR260 running Ubuntu. Its programmable logic hosts a decoder accelerator, its ARM cores handle tokenization and file access, and its DDR memory holds the resident model weights. Logs are rotated daily and kept for one week. '+QUERY

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
 dma_ownership=Path('/sys/class/misc/sysone_qwen_dma/ownership').read_text().strip() if Path('/sys/class/misc/sysone_qwen_dma/ownership').exists() else None,
 dma_module=run(['sh','-c','lsmod | grep -i sysone']),
 xmutil=run(['xmutil','listapps'])),indent=1))
EOF'''


def job(command,timeout=60,root=True):
    return dict(root=root,command=command,timeout=timeout)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--work',type=Path,default=BUILD/'board');args=ap.parse_args()
    digest=hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    # Staged, not queued: the window runs anything in queue/, so jobs are moved
    # there one gate at a time after the reservation and each check.
    queue=args.work/'pending5';queue.mkdir(parents=True,exist_ok=False);(args.work/'queue').mkdir(exist_ok=True);(args.work/'results').mkdir(exist_ok=True)
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
    clear_rope=f'''python3 - <<'EOF'
import fcntl,mmap,os,struct
from pathlib import Path
# Zero the RoPE area so the next v9e run must take the write path. Runs under the
# inference lock; every runtime rewrites or verifies this table before use.
dt=Path('/sys/firmware/devicetree/base');r=list((dt/'reserved-memory').glob('sysone@*'))[0]
base,size=struct.unpack('>QQ',(r/'reg').read_bytes())
lock=Path('/run/lock/sysone-inference.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
fd=os.open('/dev/mem',os.O_RDWR|os.O_SYNC);m=mmap.mmap(fd,size,mmap.MAP_SHARED,mmap.PROT_READ|mmap.PROT_WRITE,offset=base)
zero=(0,)*16
for o in range(0x10000,0x10000+(1<<20),64):struct.pack_into('<16I',m,o,*zero)
m.close();os.close(fd);lock.close()
print('rope area zeroed')
EOF'''
    jobs=[('00-inventory',job(INVENTORY,30)),
          ('01-upload-candidate',dict(upload=str(ARCHIVE),remote=REMOTE_TAR)),
          ('02-extract-candidate',job(extract,120)),
          ('03-copy-benchmark',job(py+f'{PACKAGE}/scripts/v2/bench_scratch_copy_v9e.py --package {PACKAGE} --out {EVIDENCE}/03-copy-benchmark.json',180)),
          ('04-deploy-candidate',job(py+f'{PACKAGE}/scripts/v2/deploy_qwen_fpga_v9e.py --package {PACKAGE} --direction candidate --baseline v9d --out {EVIDENCE}/04-deploy.json',120)),
          ('05-clear-rope',job(clear_rope,60)),
          ('06-command-new-adapter-1',job(command(PACKAGE,'run_qwen_fpga_command_v9e.py','06-command-new-adapter-1.json'),300)),
          ('07-command-new-adapter-2',job(command(PACKAGE,'run_qwen_fpga_command_v9e.py','07-command-new-adapter-2.json'),300)),
          # ABI2 DMA (Codex v16) rejects writable-mapping runtimes: no old-adapter or
          # v9d-adapter runs; the copy benchmark measures old vs new on device memory.
          ('09-restore-v9d',job(py+f'{PACKAGE}/scripts/v2/deploy_qwen_fpga_v9e.py --package {PACKAGE} --direction restore --baseline v9d --out {EVIDENCE}/09-restore.json',120)),
          ('13-final-inventory',job(INVENTORY,30)),
          ('14-collect-evidence',job(f'cd {EVIDENCE} && for f in $(find . -name "*.json" | sort); do echo "=== $f"; cat "$f"; done',30)),
          ('99-close-session',dict(close=True))]
    # Candidate 3 continues in the board2 window after candidate 2's SIGBUS: jobs
    # are numbered 2x/3x because the window skips names it has already run.
    jobs=[(('6' if n[0]=='0' else '7' if n[0]=='1' else n[0])+n[1:],b) for n,b in jobs]
    for name,body in jobs:(queue/(name+'.json')).write_text(json.dumps(body)+'\n')
    print(json.dumps(dict(queue=str(queue),jobs=[n for n,_ in jobs],archive_sha256=digest)))

if __name__=='__main__':main()
