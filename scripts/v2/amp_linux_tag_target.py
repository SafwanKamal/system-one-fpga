"""Root-local fixed PL/R5 tag trial with independent, fail-closed recovery.

No PS/RPU /dev/mem access. The two native helpers access only the fixed PL
probe page; RPU power, reset, TCM and clock lifetime are owned by the module.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from amp_linux_tag_policy import require,idle,restore_allowed,parse_trace,check_apu,check_r5

HERE=Path(__file__).resolve().parent
R5=Path('/sys/class/misc/sysone_r5_smoke')
STATE=HERE/'state.json'
DASH='snap.kria-dashboard.service.service'
APP='sysone-amp-origin-probe'
STOCK='k26-starter-kits'


def save(name,data):
    path=HERE/name;temp=HERE/(name+'.tmp')
    with temp.open('w') as stream:
        json.dump(data,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    os.replace(temp,path)
    fd=os.open(HERE,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def run(args,name,timeout=45,check=True):
    result=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
    with (HERE/name).open('ab') as stream:stream.write(result.stdout)
    print(name+': '+str(result.returncode),flush=True)
    if check:require(result.returncode==0,'Command failed: '+str(args))
    return result


def clock():
    rows=[line.split() for line in Path('/sys/kernel/debug/clk/clk_summary').read_text().splitlines()
          if line.split() and line.split()[0]=='pl0_ref']
    require(len(rows)==1,'Ambiguous PL0 clock')
    return dict(enable=int(rows[0][1]),prepare=int(rows[0][2]),hz=int(rows[0][4]))


def overlays():
    return sorted(p.read_text().strip() for p in Path('/sys/kernel/config/device-tree/overlays').glob('*/path'))


def observe():
    return dict(clock=clock(),overlays=overlays(),manager=Path('/sys/class/fpga_manager/fpga0/state').read_text().strip(),
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        taint=int(Path('/proc/sys/kernel/tainted').read_text()))


def status():
    if not R5.exists():
        require(not Path('/sys/module/sysone_r5_smoke').exists(),'Module exists without control device')
        return dict.fromkeys(['pinned','reserved','lease_pending','mapped','may_run','loaded','quarantine'],'0')
    return dict(field.split('=',1) for field in (R5/'status').read_text().split())


def command(text):
    (R5/'command').write_text(text+'\n')


def verify_files(expected):
    for name,digest in expected.items():
        require(hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest,'File changed: '+name)


def stop_r5():
    if R5.exists():
        command('stop');current=status();save('stopped-status.json',current)
        require(idle(current),'R5 cleanup uncertain; retain PL and module')
        command('audit');save('rpu-post-audit.json',status())
        require(status()['audit']=='0','Post-stop ownership audit failed')
        run(['/usr/sbin/rmmod','sysone_r5_smoke'],'module-unload.log')
    require(idle(status()),'R5 resource retention blocks PL restore')


def recover():
    if not STATE.exists():return
    state=json.loads(STATE.read_text())
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==state['before']['boot_id'],'Refuse stale recovery across reboot')
    try:stop_r5()
    except Exception as exc:
        save('recovery-held.json',dict(reason=type(exc).__name__,status=status(),pl_retained=True))
        raise
    if state['pl_changed']:
        if not restore_allowed(state,status()):
            save('recovery-held.json',dict(reason='No positive APU/R5 AXI drain evidence',status=status(),pl_retained=True))
            raise RuntimeError('PL retained: incomplete APU/R5 access; do not unload blindly')
        if overlays()!=['k26_starter_kits.dtbo']:
            run(['xmutil','unloadapp'],'restore-unload.log',check=False)
            run(['xmutil','loadapp',STOCK],'restore-stock.log',timeout=60)
    after=observe();save('recovery-observation.json',after)
    require(after['overlays']==['k26_starter_kits.dtbo'] and after['manager']=='operating','Stock PL not restored')
    require(after['clock']==state['before']['clock'],'Linux clock rate/reference baseline not restored')
    require(after['taint'] & ~((1<<12)|(1<<13))==0,'Unexpected kernel taint')
    verify_files(state['baseline_files'])
    if state['dashboard_active']:
        run(['systemctl','start',DASH],'dashboard-restore.log')
        run(['systemctl','is-active','--quiet',DASH],'dashboard-active.log')
    save('recovery.json',dict(passed=True,stock_restored=True,r5_released=True,baseline_hashes_unchanged=True,
        linux_clock_restored=True,raw_ps_register_equality_claim=False))


def trial(config):
    require(os.geteuid()==0 and os.environ.get('INVOCATION_ID'),'Root-local systemd service required')
    require(HERE.parent==Path('/var/lib/sysone/linux-tag-probe'),'Unexpected root stage')
    require(not os.statvfs(HERE).f_flag & os.ST_NOEXEC,'Native-helper stage is mounted noexec')
    for path in [HERE,*HERE.parents,HERE/'amp_linux_tag_target.py',HERE/'amp_linux_tag_policy.py',HERE/'config.json',HERE/'sysone_r5_smoke.ko',HERE/'apu_probe',HERE/'pl_snapshot']:
        st=path.stat();require(st.st_uid==0 and not st.st_mode & 0o022 and not path.is_symlink(),'Untrusted root stage: '+str(path))
    require(not STATE.exists(),'Existing attempt may only be recovered/collected')
    props=run(['systemctl','show',config['unit'],'-p','ExecStopPost','-p','TimeoutStartUSec','-p','TimeoutStopUSec'],'armed-unit.log').stdout.decode()
    require(str(HERE/'amp_linux_tag_target.py')+' recover' in props,'Independent recovery missing')
    require('TimeoutStartUSec=2min' in props and 'TimeoutStopUSec=2min' in props,'Bounded manager recovery missing')
    verify_files({str(HERE/name):digest for name,digest in config['local_sha256'].items()})
    verify_files(config['probe_sha256']);verify_files(config['stock_sha256'])
    require(not list(Path('/sys/class/remoteproc').iterdir()),'Remoteproc owner present')
    require(not Path('/sys/module/zynqmp_r5_remoteproc').exists() and not R5.exists(),'R5 driver already present')
    require(Path('/sys/firmware/devicetree/base/model').read_bytes().rstrip(b'\0')==b'ZynqMP KR260 revB','Wrong board')
    before=observe();require(before['overlays']==['k26_starter_kits.dtbo'] and before['manager']=='operating','Stock required')
    require(before['boot_id']==config['boot_id'] and before['taint'] & ~12288==0,'Boot/taint changed')
    require(before['clock']['enable']==before['clock']['prepare']==0 and 95000000<before['clock']['hz']<=100000000,'Unexpected clock baseline')
    # Preserve all runtime application file hashes, including qualified apps.
    baseline={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in Path('/lib/firmware/xilinx').glob('*/*') if p.is_file()}
    active=run(['systemctl','is-active','--quiet',DASH],'dashboard-before.log',check=False).returncode==0
    state=dict(before=before,baseline_files=baseline,dashboard_active=active,pl_changed=False,
               r5_start_attempted=False,r5_quiet_proved=False,apu_access_attempted=False,apu_quiet_proved=False)
    save('state.json',state)
    run(['systemctl','stop',DASH],'dashboard-stop.log')
    for maps in Path('/proc').glob('[0-9]*/maps'):
        try:
            for line in maps.read_text().splitlines():
                words=line.split()
                require(not (len(words)>=6 and words[-1]=='/dev/mem' and 0xa0000000<=int(words[2],16)<0xb0000000),'PL mapping already active: '+str(maps))
        except (FileNotFoundError,ProcessLookupError):pass
    state['pl_changed']=True;save('state.json',state)
    run(['xmutil','unloadapp'],'stock-unload.log')
    run(['xmutil','loadapp',APP],'probe-load.log',timeout=60)
    after=observe();save('probe-observation.json',after)
    require(after['overlays']==[APP+'.dtbo'] and after['manager']=='operating','Probe not operating')
    require(after['clock']['hz']==before['clock']['hz'] and after['clock']['enable']>0 and after['clock']['prepare']>0,'Probe clock consumer missing')
    dt=Path('/sys/firmware/devicetree/base');amba=(dt/'__symbols__/amba').read_bytes().rstrip(b'\0').decode()
    for node,driver in [('amp-probe-clock','xilinx_fclk'),('amp-probe-afi','afi-fpga')]:
        found=[p for p in Path('/sys/bus/platform/devices').iterdir() if (p/'of_node').exists() and (p/'of_node').resolve()==(dt/amba.lstrip('/')/node).resolve()]
        require(len(found)==1 and (found[0]/'driver').resolve().name==driver,'Linux probe driver not bound: '+node)
    state['apu_access_attempted']=True;save('state.json',state)
    apu=json.loads(run([str(HERE/'apu_probe')],'apu-observations.json',timeout=15).stdout);check_apu(apu)
    state['apu_quiet_proved']=True;save('state.json',state)
    run(['/usr/sbin/insmod',str(HERE/'sysone_r5_smoke.ko')],'module-load.log')
    loaded=status();require(loaded['image_sha256']==config['elf_sha256'] and loaded['live_enabled']=='1' and loaded['prepare_enabled']=='1','Unexpected module image/admission')
    command('audit');require(status()['audit']=='0','RPU/TCM ownership changed')
    command('prepare');prepared=status();save('prepared-status.json',prepared)
    require(prepared['loaded']=='1' and prepared['may_run']=='0' and prepared['lease_pending']=='3','Private halted image not ready')
    held=clock();save('held-clock.json',held)
    require(held['hz']==after['clock']['hz'] and held['enable']>after['clock']['enable'] and held['prepare']>after['clock']['prepare'],'Module clock reference missing')
    require((R5/'trace').read_text().startswith('R5: WAIT'),'Stale R5 trace')
    state['r5_start_attempted']=True;save('state.json',state)
    command('start')
    trace='';deadline=time.monotonic()+2
    while time.monotonic()<deadline:
        trace=(R5/'trace').read_text()
        if 'PASS' in trace or 'FAIL' in trace:break
        time.sleep(.02)
    (HERE/'r5-trace.txt').write_text(trace);parse_trace(trace)
    # The exact fixed firmware emits PASS only after all four DSB-completed
    # PL writes and counter/error readback, then has only TCM/WFI instructions.
    state['r5_quiet_proved']=True;save('state.json',state)
    deadline=time.monotonic()+9
    while not idle(status()) and time.monotonic()<deadline:time.sleep(.2)
    require(idle(status()),'Kernel recovery did not release R5 resources')
    command('audit');save('post-watchdog-status.json',status());require(status()['audit']=='0','RPU/TCM not idle')
    require(clock()==after['clock'],'Module clock reference not released')
    state['apu_quiet_proved']=False;save('state.json',state)
    snapshot=json.loads(run([str(HERE/'pl_snapshot')],'pl-snapshot.json',timeout=10).stdout)
    state['apu_quiet_proved']=True;save('state.json',state)
    result=check_r5(snapshot,trace,apu)
    save('tag-results.json',dict(passed=True,diagnostic_only=True,measured=result,inference_deployed=False,
        filter_bound=False,hard_timing_claim=False))
    print('PASS R5/APU AXI identities measured; watchdog released clock/TCM leases',flush=True)


def main():
    config=json.loads((HERE/'config.json').read_text())
    with (HERE/'controller.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if sys.argv[1]=='recover':recover()
        else:
            try:trial(config)
            finally:recover()


if __name__=='__main__':main()
