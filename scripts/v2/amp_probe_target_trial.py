"""Board-local diagnostic trial; stock restoration also runs as ExecStopPost.

Only the reviewed origin probe is allowed. No inference or boot-chain writes.
"""
from pathlib import Path
import argparse,hashlib,json,mmap,os,struct,subprocess,time

HERE=Path(__file__).resolve().parent
APP='sysone-amp-origin-probe'
STOCK='k26-starter-kits'
SERVICE='snap.kria-dashboard.service.service'
DT=Path('/sys/firmware/devicetree/base')

def save(name,data):
    (HERE/name).write_text(json.dumps(data,indent=2)+'\n')

def run(args,name,timeout=30,check=True):
    r=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
    (HERE/name).write_bytes(r.stdout)
    if check:assert r.returncode==0,(args,r.returncode,r.stdout[-2000:])
    return r

def reg(address):
    fd=os.open('/dev/mem',os.O_RDONLY|os.O_SYNC)
    try:
        with mmap.mmap(fd,4096,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ,offset=address&~4095) as m:
            return struct.unpack_from('<I',m,address&4095)[0]
    finally:os.close(fd)

def clock():
    lines=[s.split() for s in Path('/sys/kernel/debug/clk/clk_summary').read_text().splitlines() if s.split() and s.split()[0]=='pl0_ref']
    assert len(lines)==1
    return dict(enable=int(lines[0][1]),prepare=int(lines[0][2]),hz=int(lines[0][4]))

def overlays():
    return sorted(p.read_text().strip() for p in Path('/sys/kernel/config/device-tree/overlays').glob('*/path'))

def hashes():
    record=json.loads((HERE/'readiness.json').read_text())
    for name,h in record['recovery_files_sha256'].items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h,name

def recover():
    state=HERE/'state.json'
    if not state.exists():return
    s=json.loads(state.read_text())
    if s.get('recovered'):return
    # Called locally by systemd even when the SSH client disconnects or trial fails.
    if s.get('unload_started'):
        run(['xmutil','unloadapp'],'recovery-unload.log',check=False)
        run(['xmutil','loadapp',STOCK],'recovery-load.log',timeout=45)
    assert overlays()==['k26_starter_kits.dtbo'],overlays()
    assert Path('/sys/class/fpga_manager/fpga0/state').read_text().strip()=='operating'
    assert reg(0xfd615000)==s['afi_before']
    assert reg(0xff5e00c0)==s['pl0_before']
    assert clock()['hz']==s['clock_before']['hz']
    hashes()
    # This APU-only trial never writes DDR; check the reserved snapshot unchanged.
    fd=os.open('/dev/mem',os.O_RDONLY|os.O_SYNC)
    try:
        with mmap.mmap(fd,65536,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ,offset=0x63f00000) as m:
            assert hashlib.sha256(m[:]).hexdigest()==json.loads((HERE/'readiness.json').read_text())['reserved_ddr_sha256']
    finally:os.close(fd)
    if s['dashboard_active']:run(['systemctl','start',SERVICE],'recovery-dashboard.log')
    s['recovered']=True;save('state.json',s)
    save('recovery.json',dict(passed=True,stock_restored=True,baseline_files_unchanged=True,reserved_ddr_unchanged=True,clock=clock(),overlays=overlays()))

def trial():
    assert os.geteuid()==0
    assert (DT/'model').read_bytes().rstrip(b'\0')==b'ZynqMP KR260 revB'
    assert overlays()==['k26_starter_kits.dtbo']
    assert not list(Path('/sys/class/remoteproc').glob('remoteproc*'))
    hashes()
    manifest=json.loads((HERE/APP/'build.json').read_text())
    assert manifest['app_name']==APP and manifest['diagnostic_only'] and manifest['no_pl_ddr_master'] and manifest['no_encoder']
    expected={APP+'.bit.bin',APP+'.dtbo','shell.json'}
    assert set(manifest['files_sha256'])==expected
    for name,h in manifest['files_sha256'].items():assert hashlib.sha256((HERE/APP/name).read_bytes()).hexdigest()==h
    c=clock();assert 95000000<c['hz']<=100000000,c
    active=subprocess.run(['systemctl','is-active','--quiet',SERVICE]).returncode==0
    s=dict(dashboard_active=active,afi_before=reg(0xfd615000),pl0_before=reg(0xff5e00c0),clock_before=c,unload_started=False,recovered=False)
    # Already matching stock AFI means restoration does not require any raw PS write.
    assert s['afi_before']==0xa00,s
    assert reg(0xff5e023c)&3==3 # both R5s remain reset, no diagnostic R5 execution here
    save('state.json',s)
    run(['systemctl','stop',SERVICE],'dashboard-stop.log')
    # Reject active userspace mappings of the PL aperture after dashboard quiescence.
    busy=[]
    for maps in Path('/proc').glob('[0-9]*/maps'):
        try:
            for line in maps.read_text().splitlines():
                parts=line.split()
                if len(parts)>=6 and parts[-1]=='/dev/mem' and 0xa0000000<=int(parts[2],16)<0xb0000000:busy.append(str(maps))
        except (FileNotFoundError,ProcessLookupError):pass
    assert not busy,busy
    target=Path('/lib/firmware/xilinx')/APP
    target.mkdir(exist_ok=False)
    for name in expected|{'build.json'}:
        data=(HERE/APP/name).read_bytes();(target/name).write_bytes(data)
        assert hashlib.sha256((target/name).read_bytes()).digest()==hashlib.sha256(data).digest()
    # Allow inotify processing, then prove the manager has discovered this exact app.
    time.sleep(2)
    apps=run(['xmutil','listapps'],'apps-before.log').stdout.decode()
    assert APP in apps
    s['unload_started']=True;save('state.json',s)
    run(['xmutil','unloadapp'],'probe-unload.log')
    run(['xmutil','loadapp',APP],'probe-load.log',timeout=45)
    assert Path('/sys/class/fpga_manager/fpga0/state').read_text().strip()=='operating'
    assert overlays()==[APP+'.dtbo'],overlays()
    amba=(DT/'__symbols__/amba').read_bytes().rstrip(b'\0').decode()
    bus=DT/amba.lstrip('/')
    for node,driver in [('amp-probe-clock','xilinx_fclk'),('amp-probe-afi','afi-fpga')]:
        matches=[p for p in Path('/sys/bus/platform/devices').iterdir() if (p/'of_node').exists() and (p/'of_node').resolve()==(bus/node).resolve()]
        assert len(matches)==1 and (matches[0]/'driver').resolve().name==driver,(node,matches)
    after=clock()
    assert after['hz']==c['hz'] and after['enable']>0 and after['prepare']>0,after
    assert reg(0xfd615000)==s['afi_before'] and reg(0xff5e00c0)==s['pl0_before']
    run([str(HERE/'apu_probe')],'apu-observations.json',timeout=15)
    observations=json.loads((HERE/'apu-observations.json').read_text())
    assert observations['passed'] and observations['writes']==64 and observations['errors']==0
    save('trial.json',dict(passed=True,diagnostic_only=True,clock=after,observations=observations,inference_deployed=False,r5_executed=False))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--recover',action='store_true');args=ap.parse_args()
    if args.recover:recover()
    else:
        try:trial()
        finally:recover()
