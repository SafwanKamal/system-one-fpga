"""Compile and dry-apply the candidate overlay locally; preserve live DT properties."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-linux-r5-v1'
sys.path.insert(0,str(ROOT/'scripts/v2/kr260'))
from prepare_reserved_fit import parse


def wsl(p):
    return '/mnt/c/'+str(p.resolve())[3:].replace('\\','/')


def flatten(node,path=''):
    path=path+'/'+node['name'] if node['name'] else '/'
    result={path:node['props']}
    for child in node['children']:
        result.update(flatten(child,path.rstrip('/')))
    return result


def main():
    out=BASE/'overlay-check-v1';out.mkdir(exist_ok=False)
    src=ROOT/'firmware/typed200_amp_linux_r5/smoke-overlay.dts'
    live=BASE/'board-inventory-v1/devicetree.stdout'
    commands=[['/usr/bin/dtc','-@','-I','dts','-O','dtb','-o',wsl(out/'smoke.dtbo'),wsl(src)],
              ['/usr/bin/dtc','-I','dts','-O','dtb','-o',wsl(out/'live.dtb'),wsl(live)],
              ['/usr/bin/fdtoverlay','-i',wsl(out/'live.dtb'),'-o',wsl(out/'candidate.dtb'),wsl(out/'smoke.dtbo')]]
    for index,cmd in enumerate(commands):
        r=subprocess.run(['wsl.exe','-d','Ubuntu-24.04','--',*cmd],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
        (out/f'step-{index}.log').write_bytes(r.stdout)
        assert not r.returncode,index
    before=flatten(parse((out/'live.dtb').read_bytes())[0])
    after=flatten(parse((out/'candidate.dtb').read_bytes())[0])
    for path,props in before.items():
        assert path in after
        for name,value in props.items():assert after[path][name]==value,(path,name)
    added=set(after)-set(before)
    assert added=={'/sysone-smoke-tcm@ffe00000','/r5fss@ff9a0000','/r5fss@ff9a0000/r5f_0'},added
    for path in before:
        extra=set(after[path])-set(before[path])
        assert not extra or path=='/__symbols__' and extra=={'sysone_smoke_tcm','sysone_smoke_rpu'},(path,extra)
    tcm=after['/sysone-smoke-tcm@ffe00000']
    core=after['/r5fss@ff9a0000/r5f_0']
    fw=after['/firmware/zynqmp-firmware']['phandle']
    assert tcm['reg']==struct.pack('>4I',0,0xffe00000,0,0x10000)
    assert tcm['power-domains']==fw+struct.pack('>I',15)
    assert core['power-domains']==fw+struct.pack('>I',7)
    assert 'memory-region' not in core and 'mboxes' not in core and 'xlnx,rsc-tbl' not in core
    receipt=dict(passed=True,local_dry_apply_only=True,existing_nodes=len(before),
        all_existing_properties_unchanged=True,added_nodes=sorted(added),
        pm_nodes=[7,15],ddr_or_ocm_allocation=False,target_applied=False,live_startup_admitted=False,
        overlay_sha256=hashlib.sha256((out/'smoke.dtbo').read_bytes()).hexdigest(),
        source_sha256=hashlib.sha256(src.read_bytes()).hexdigest())
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS overlay dry-apply; every existing DT property retained, only RPU0/TCM0A nodes added locally')


if __name__=='__main__':main()
