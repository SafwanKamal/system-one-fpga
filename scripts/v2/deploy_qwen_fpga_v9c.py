"""Swap the active FPGA app between sealed v8 and the v9c candidate, with rollback.

--direction candidate: v8 (sysone-qwen-decoder-wide-int8) -> v9c.
--direction restore:   v9c -> v8. Restores the image the v8 launcher expects.
Linux, DMA model residency, services and the launcher are not changed. The
inference lock is taken non-blocking; any MMIO client or busy decoder aborts.
The state record is written to --out, never into a package directory.
"""
import argparse,fcntl,hashlib,json,mmap,os,shutil,struct,subprocess,time
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.qwen_fpga_runtime_v9c import active_firmware as _active_firmware,bound

V8='sysone-qwen-decoder-wide-int8'
V9A='sysone-qwen-decoder-v9c'
DT=Path('/sys/firmware/devicetree/base')
LOCK=Path('/run/lock/sysone-inference.lock')


def run(argv):
    result=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=90)
    text=result.stdout.decode(errors='replace');print(text,flush=True)
    result.check_returncode();return text


def active_firmware():
    try:return _active_firmware(DT)
    except FileNotFoundError:return None


def decoder_idle():
    fd=os.open('/dev/mem',os.O_RDONLY|os.O_SYNC)
    try:
        with mmap.mmap(fd,4096,mmap.MAP_SHARED,mmap.PROT_READ,offset=0xa0000000) as regs:return struct.unpack_from('<I',regs,0)[0]
    finally:os.close(fd)


def clock(name):
    rows=[line.split() for line in Path('/sys/kernel/debug/clk/clk_summary').read_text().splitlines() if line.split() and line.split()[0]==name]
    if len(rows)!=1 or not int(rows[0][1]):raise RuntimeError('Clock unavailable: '+name)
    return int(rows[0][4])


def verify_loaded(app):
    if Path('/sys/class/fpga_manager/fpga0/state').read_text().strip()!='operating':raise RuntimeError('FPGA manager not operating')
    if active_firmware()!=app+'.bit.bin':raise RuntimeError('Wrong loaded image: '+str(active_firmware()))
    bus=DT/(DT/'__symbols__/amba').read_bytes().rstrip(b'\0').decode().lstrip('/')
    if not bound(bus/'qwen-clocking0','xilinx_fclk') or not bound(bus/'qwen-clocking1','xilinx_fclk') or not bound(bus/'qwen-afi','afi-fpga'):
        raise RuntimeError('Clock or AXI driver not bound')
    decoder=clock('pl0_ref');memory=clock('pl1_ref')
    if not 124000000<=decoder<=125000000 or not 249000000<=memory<=250000000:raise RuntimeError('Clocks outside routed profile')
    control=decoder_idle()
    if not control&4:raise RuntimeError('Loaded decoder is not idle')
    return dict(decoder_clock_hz=decoder,memory_clock_hz=memory,control=control,firmware=active_firmware())


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package',type=Path,required=True,help='v9c package directory')
    ap.add_argument('--direction',choices=['candidate','restore'],required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    if os.geteuid()!=0:raise RuntimeError('Root required')
    source,target=(V8,V9A) if args.direction=='candidate' else (V9A,V8)
    package=args.package.resolve();app=package/V9A
    hashes=json.loads((package/'package-sha256.json').read_text())
    for name,digest in hashes.items():
        path=(package/name).resolve()
        if not path.is_relative_to(package) or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise RuntimeError('Package differs: '+name)
    build=json.loads((app/'build.json').read_text())
    if build['app_name']!=V9A or build['timing_qualified'] is not True or build['clock_timing_max_hz']!=125000000:raise RuntimeError('Unqualified candidate package')
    firmware=Path('/lib/firmware/xilinx')
    if not (firmware/V8/(V8+'.bit.bin')).is_file():raise RuntimeError('v8 rollback image is not installed')
    if args.direction=='candidate':
        run(['dtc','-@','-I','dts','-O','dtb','-o',str(args.out.with_suffix('.dtbo')),str(app/(V9A+'.dts'))])
        installed=firmware/V9A
        if installed.exists():
            for name,local in [(V9A+'.bit.bin',app/(V9A+'.bit.bin')),(V9A+'.dtbo',args.out.with_suffix('.dtbo')),('shell.json',app/'shell.json')]:
                if (installed/name).read_bytes()!=local.read_bytes():raise RuntimeError('Installed v9c app differs; preserve it')
        else:
            installed.mkdir()
            shutil.copyfile(app/(V9A+'.bit.bin'),installed/(V9A+'.bit.bin'));shutil.copyfile(args.out.with_suffix('.dtbo'),installed/(V9A+'.dtbo'))
            shutil.copyfile(app/'shell.json',installed/'shell.json');shutil.copyfile(app/'build.json',installed/'build.json')
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    lock=LOCK.open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    state=dict(direction=args.direction,source=source,target=target,linux_boot_id=boot,unload_started=False,complete=False)
    def save():args.out.write_text(json.dumps(state,indent=2)+'\n')
    try:
        if active_firmware()!=source+'.bit.bin':raise RuntimeError('Unexpected current FPGA image: '+str(active_firmware()))
        if not decoder_idle()&4:raise RuntimeError('Current decoder not idle; do not reprogram')
        if Path('/sys/class/misc/sysone_r5_smoke/status').exists():raise RuntimeError('R5 module loaded; not part of this swap')
        for maps in Path('/proc').glob('[0-9]*/maps'):
            try:
                for line in maps.read_text().splitlines():
                    fields=line.split()
                    if len(fields)>=6 and fields[-1]=='/dev/mem' and 0xa0000000<=int(fields[2],16)<0xb0000000:raise RuntimeError('Live PL MMIO client: '+str(maps))
            except (FileNotFoundError,ProcessLookupError,PermissionError):pass
        dma_before=Path('/sys/class/misc/sysone_qwen_dma/buffers').read_text()
        state['dma_buffers_sha256_before']=hashlib.sha256(dma_before.encode()).hexdigest();save()
        state['unload_started']=True;save()
        try:
            run(['xmutil','unloadapp']);run(['xmutil','loadapp',target])
            state['loaded']=verify_loaded(target)
        except Exception as exc:
            state['error']=str(exc);save()
            run(['xmutil','unloadapp']);run(['xmutil','loadapp',source])
            state['rolled_back']=verify_loaded(source);save();raise
        if Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=boot:raise RuntimeError('Linux boot changed')
        dma_after=Path('/sys/class/misc/sysone_qwen_dma/buffers').read_text()
        state['dma_buffers_sha256_after']=hashlib.sha256(dma_after.encode()).hexdigest()
        if dma_after!=dma_before:raise RuntimeError('DMA residency table changed')
        state['complete']=True;save()
    finally:lock.close()
    print(json.dumps(state,indent=2))

if __name__=='__main__':main()
