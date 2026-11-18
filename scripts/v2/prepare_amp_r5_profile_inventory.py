"""Prepare bounded read-only Linux health/provenance inventory, no raw MMIO."""
from pathlib import Path
import json,shlex
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-r5-profile-filter-v1'

def main():
    source='''from pathlib import Path
import json,subprocess
def read(p):
 try:return Path(p).read_text().strip()
 except OSError as e:return 'unavailable:'+type(e).__name__
def command(args):
 p=subprocess.run(args,capture_output=True,text=True,timeout=15)
 return dict(exit=p.returncode,stdout=p.stdout,stderr=p.stderr)
d=dict(boot_id=read('/proc/sys/kernel/random/boot_id'),taint=read('/proc/sys/kernel/tainted'),
       cpus_online=read('/sys/devices/system/cpu/online'),uptime=read('/proc/uptime'),
       manager=read('/sys/class/fpga_manager/fpga0/state'),
       remoteproc=[p.name for p in Path('/sys/class/remoteproc').glob('*')],
       r5_module_present=Path('/sys/module/sysone_r5_smoke').exists(),
       iommu_groups=[p.name for p in Path('/sys/kernel/iommu_groups').glob('*')],
       smmu_bound_devices=[p.name for p in Path('/sys/bus/platform/drivers/arm-smmu').glob('*') if p.is_symlink() and p.name not in ['module','subsystem']],
       clock=[line for line in read('/sys/kernel/debug/clk/clk_summary').splitlines() if 'pl0_ref' in line],
       xmutil=command(['xmutil','listapps']),
       dashboard=command(['systemctl','is-active','snap.kria-dashboard.service.service']),
       dmesg=command(['dmesg','--level=err,warn']))
print(json.dumps(d,indent=2))
'''
    plan=dict(commands=[dict(name='health',root=True,timeout=35,command='python3 -c '+shlex.quote(source))])
    out=BASE/'inventory-plan-v1.json';assert not out.exists()
    out.write_text(json.dumps(plan,indent=2)+'\n')
    print(out)

if __name__=='__main__':main()
