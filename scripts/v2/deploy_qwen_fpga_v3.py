"""Load the Qwen decoder through Linux FPGA manager, retaining baseline rollback."""
import argparse,fcntl,hashlib,json,mmap,os,shutil,struct,subprocess,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.qwen_fpga_runtime_v3 import bound,active_firmware

APP='sysone-qwen-decoder-batch'
BASELINE='sysone-qwen-decoder-fast'
DT=Path('/sys/firmware/devicetree/base')
R5=Path('/sys/class/misc/sysone_r5_smoke/status')
ROLLBACK_MODULE=Path('/var/lib/sysone/r5-inference/calibrated-v1/source/sysone_r5_smoke.ko')

def run(argv):
    result=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=90)
    print(result.stdout.decode(errors='replace'),flush=True)
    result.check_returncode()

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,required=True);args=ap.parse_args()
    if os.geteuid()!=0:raise RuntimeError('Root required')
    package=args.package.resolve();app=package/APP
    hashes=json.loads((package/'package-sha256.json').read_text())
    for name,digest in hashes.items():
        path=(package/name).resolve()
        if not path.is_relative_to(package) or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise RuntimeError('Package differs: '+name)
    manifest=json.loads((app/'build.json').read_text())
    if manifest['app_name']!=APP or manifest['timing_qualified'] is not True or manifest['clock_timing_max_hz']!=100000000:raise RuntimeError('Unqualified hardware package')
    run(['dtc','-@','-I','dts','-O','dtb','-o',str(app/(APP+'.dtbo')),str(app/(APP+'.dts'))])
    target=Path('/lib/firmware/xilinx')/APP
    if target.exists():
        for name in [APP+'.bit.bin',APP+'.dtbo','shell.json']:
            if (target/name).read_bytes()!=(app/name).read_bytes():raise RuntimeError('Existing Qwen app differs; preserve it before replacement')
    else:
        target.mkdir()
        for name in [APP+'.bit.bin',APP+'.dtbo','shell.json','build.json']:shutil.copyfile(app/name,target/name)
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    lock=Path('/run/lock/sysone-inference.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX)
    firmware=active_firmware(DT)
    if firmware!=BASELINE+'.bit.bin':raise RuntimeError('Unexpected current FPGA image: '+firmware)
    bus=DT/(DT/'__symbols__/amba').read_bytes().rstrip(bytes([0])).decode().lstrip('/')
    if not bound(bus/'qwen-clocking0','xilinx_fclk') or not bound(bus/'qwen-afi','afi-fpga'):raise RuntimeError('Baseline clock/AXI drivers absent')
    fd=os.open('/dev/mem',os.O_RDONLY|os.O_SYNC)
    try:
        with mmap.mmap(fd,4096,mmap.MAP_SHARED,mmap.PROT_READ,offset=0xa0000000) as regs:old_control=struct.unpack_from('<I',regs,0)[0]
    finally:os.close(fd)
    if not old_control&4:raise RuntimeError('Baseline decoder not idle; do not reprogram')

    state=dict(linux_boot_id=boot,baseline=BASELINE,new_app=APP,old_r5_loaded=R5.exists(),unload_started=False,complete=False)
    out=package/'deployment-state.json'
    def save():out.write_text(json.dumps(state,indent=2)+'\n')
    save()
    # Stop only clients of the displaced encoder; Linux and network stay live.
    run(['systemctl','stop','sysone-qwen06b-mvp.service','snap.kria-dashboard.service.service'])
    if R5.exists():
        status=dict(item.split('=',1) for item in R5.read_text().split())
        for key in ['pinned','reserved','lease_pending','mapped','may_run','loaded','quarantine','r0','r1','usage','usage1']:
            if int(status.get(key,'-1'),0)!=0:raise RuntimeError('R5 not safely idle: '+key)
        if not ROLLBACK_MODULE.is_file():raise RuntimeError('R5 rollback module missing')
        state['r5_before']=status;save();run(['rmmod','sysone_r5_smoke'])
    for maps in Path('/proc').glob('[0-9]*/maps'):
        try:
            for line in maps.read_text().splitlines():
                fields=line.split()
                if len(fields)>=6 and fields[-1]=='/dev/mem' and 0xa0000000<=int(fields[2],16)<0xb0000000:raise RuntimeError('Live PL MMIO client: '+str(maps))
        except (FileNotFoundError,ProcessLookupError):pass
    try:
        time.sleep(2);state['unload_started']=True;save()
        run(['xmutil','unloadapp']);run(['xmutil','loadapp',APP])
        if Path('/sys/class/fpga_manager/fpga0/state').read_text().strip()!='operating':raise RuntimeError('FPGA manager did not enter operating state')
        bus=DT/(DT/'__symbols__/amba').read_bytes().rstrip(b'\0').decode().lstrip('/')
        if not bound(bus/'qwen-clocking0','xilinx_fclk') or not bound(bus/'qwen-afi','afi-fpga'):raise RuntimeError('Clock or AXI driver not bound')
        if active_firmware(DT)!=APP+'.bit.bin':raise RuntimeError('Wrong loaded image')
        clocks=[line.split() for line in Path('/sys/kernel/debug/clk/clk_summary').read_text().splitlines() if line.split() and line.split()[0]=='pl0_ref']
        if len(clocks)!=1 or not 99000000<=int(clocks[0][4])<=100000000 or not int(clocks[0][1]) or not int(clocks[0][2]):raise RuntimeError('Wrong live fabric clock')
        # No decoder request has been launched yet, so any failure above/below
        # can safely restore the old app without an in-flight DMA transfer.
        fd=os.open('/dev/mem',os.O_RDONLY|os.O_SYNC)
        try:
            with mmap.mmap(fd,4096,mmap.MAP_SHARED,mmap.PROT_READ,offset=0xa0000000) as regs:control=struct.unpack_from('<I',regs,0)[0]
        finally:os.close(fd)
        if not control&4:raise RuntimeError('New decoder is not idle')
        if Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=boot:raise RuntimeError('Linux boot changed')
        state.update(complete=True,clock_hz=int(clocks[0][4]),control=control,R5_unloaded=True,ARM_generator_stopped=True);save()
    except Exception as exc:
        state['error']=str(exc);save()
        run(['xmutil','unloadapp']);run(['xmutil','loadapp',BASELINE])
        if state['old_r5_loaded']:run(['insmod',str(ROLLBACK_MODULE)])
        state['baseline_restored']=True;save();raise
    finally:lock.close()
    helper=Path('/var/lib/sysone/qwen-fpga-decoder-v1/runtime/qwen_vocab')
    shutil.copyfile(helper,package/'qwen_vocab');os.chmod(package/'qwen_vocab',0o755)
    print(json.dumps(state,indent=2))

if __name__=='__main__':main()
