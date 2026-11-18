"""Read-only live identity inventory. No MMIO, programming or service changes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

PACKAGE='/var/lib/sysone/qwen-fpga-decoder-v9d-candidate1'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def inventory(package=Path(PACKAGE)):
    from sysone.v2.qwen_fpga_runtime_v9d import active_firmware
    clocks={}
    for line in Path('/sys/kernel/debug/clk/clk_summary').read_text().splitlines():
        parts=line.split()
        if parts and parts[0] in ('pl0_ref','pl1_ref'):clocks[parts[0]]=dict(enable=int(parts[1]),rate_hz=int(parts[4]))
    processes=[];ancestors={os.getpid()};pid=os.getppid()
    while pid and pid not in ancestors:
        ancestors.add(pid)
        try:pid=int(next(x.split()[1] for x in Path(f'/proc/{pid}/status').read_text().splitlines() if x.startswith('PPid:')))
        except (OSError,StopIteration):break
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit() or int(entry.name) in ancestors:continue
        try:args=entry.joinpath('cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace').strip()
        except OSError:continue
        # Ignore inline inventory's shell ancestors; retain other inference jobs.
        if any(x in args for x in ('run_v8_benchmark.py','run_v8_chain_pilot','run_qwen_fpga_command',
                                   'qualify_v8_','run_retention_comparison_v13.py','sysone-qwen-fpga --')):
            processes.append(dict(pid=int(entry.name),command=args))
    services={}
    for name in ('sysone-qwen06b-mvp.service','sysone-v8-baseline-v1.service'):
        p=subprocess.run(['systemctl','show',name,'--property=ActiveState,SubState'],capture_output=True,text=True)
        services[name]=p.stdout.strip().splitlines()
    dma=Path('/sys/class/misc/sysone_qwen_dma/buffers').read_bytes()
    return dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        active_package=str(package),active_fpga_app=active_firmware().removesuffix('.bit.bin'),
        fpga_manager_state=Path('/sys/class/fpga_manager/fpga0/state').read_text().strip(),
        launcher_sha256=sha(Path('/usr/local/bin/sysone-qwen-fpga')),
        package_manifest_sha256=sha(package/'package-sha256.json'),
        dma_header=dma.decode().splitlines()[0],dma_table_sha256=hashlib.sha256(dma).hexdigest(),
        clocks=clocks,services=services,benchmark_processes=processes,
        r5_loaded=Path('/sys/class/remoteproc/remoteproc0/state').read_text().strip()=='running'
            if Path('/sys/class/remoteproc/remoteproc0/state').exists() else False)


def validate(data):
    if data['active_package']!=PACKAGE or data['active_fpga_app']!='sysone-qwen-decoder-v9d':raise RuntimeError('Live deployment is not v9d')
    if data['fpga_manager_state']!='operating' or data['benchmark_processes'] or data['r5_loaded']:raise RuntimeError('Board is not idle/operating')
    if data['launcher_sha256']!='97e1d2bb60df803f6c5ac327647b6911ddb7040a8cb85185449c7ff59aed7792':raise RuntimeError('Launcher differs')
    if data['package_manifest_sha256']!='c6621bf4940c6f0018731aef2bcaca53aefc266051cbb2cc8af9c73975efef58':raise RuntimeError('v9d package manifest differs')
    if data['dma_table_sha256']!='ff11f582bc6375c7387e356ecec285610c4f3fd10bf884eec784374bc8cfb043':raise RuntimeError('DMA layout differs')
    if data['clocks'].get('pl0_ref',{}).get('rate_hz')!=124999999 or data['clocks'].get('pl1_ref',{}).get('rate_hz')!=249999998:
        raise RuntimeError('v8 clocks differ')
    if any(any(x in lines for x in ('ActiveState=active','ActiveState=activating','ActiveState=deactivating'))
           for lines in data['services'].values()):raise RuntimeError('MVP/full sweep service active')


if __name__=='__main__':
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
    data=inventory();validate(data);print(json.dumps(data,indent=2))
