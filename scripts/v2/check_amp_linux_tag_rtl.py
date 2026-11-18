"""Replay actual-ELF register transactions through the sealed AXI probe RTL."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-linux-tag-probe-v1'
RTL=ROOT/'rtl/v2/candidates/typed200_amp_probe/axi_origin_probe.v'


def main():
    out=BASE/'rtl-replay-v1';out.mkdir(exist_ok=False)
    prior=ROOT/'build/v2/typed200-amp-deployment-v1/probe-sim-v4/tb.sv'
    template=prior.read_text();prefix=template.split('initial begin\n',1)[0]
    assert 'task automatic read' in prefix
    prefix=prefix.replace("16'h8732","16'h0077")
    header=template.split('initial begin\n',1)[1].split(' repeat(4)',1)[0]
    transactions=json.loads((BASE/'firmware-check-v1/actual-elf-transactions.json').read_text())
    commands=[header,' repeat(4)@(negedge clk);reset_n=1;'," s_axi_aruser=16'h2345;s_axi_arprot=1;"]
    for cpu in range(4):
        for slot in range(16):
            value=0x41500000|(cpu<<8)|slot
            commands.append(f"fork aw({140+cpu},2,{397+cpu*32},{slot},0,{slot%3});wd({slot},32'h{value:08x},0,{(slot+1)%3},0);join response({397+cpu*32},0);")
    for event in transactions:
        address=event['address']-0xa0000000;value=event['value']
        if event['kind']=='read':commands.append(f"read({address},32'h{value:08x},0,0);")
        else:
            slot=address//4
            commands.append(f"fork aw(16'h4567,3,99,{slot},0,2);wd({slot},32'h{value:08x},0,0,0);join response(99,0);")
    for j in range(4,8):
        for offset,value in [(0,0x34567),(4,0xa0000000+j*4),(8,0x52350000+j),(12,((60+j)<<16)|99)]:
            commands.append(f"read({256+j*16+offset},32'h{value:08x},0,0);")
    commands+=['read(8,68,0,0);read(12,0,0,0);',
        '$display("PASS actual-ELF 12-transaction replay, 64 APU writes, four R5 markers and AW metadata");$finish;']
    (out/'tb.sv').write_text(prefix+'initial begin\n'+'\n'.join(commands)+'\nend\nendmodule\n')
    (out/'axi_origin_probe.v').write_bytes(RTL.read_bytes())
    wsl='/mnt/c/'+str(out.resolve())[3:].replace('\\','/')
    stage='/tmp/sysone-linux-tag-replay-v1'
    calls=[(['test','!','-e',stage],'unused.log'),(['mkdir',stage],'mkdir.log'),
        (['cp',wsl+'/tb.sv',wsl+'/axi_origin_probe.v',stage+'/'],'stage.log'),
        (['verilator','--assert','--binary','--timing','-j','2','-Wno-fatal','--Mdir',stage+'/obj','--top-module','tb',stage+'/tb.sv',stage+'/axi_origin_probe.v','-o','replay'],'compile.log'),
        ([stage+'/obj/replay'],'run.log')]
    for command,name in calls:
        run=subprocess.run(['wsl.exe','-d','Ubuntu-24.04','--',*command],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
        (out/name).write_bytes(run.stdout);assert not run.returncode,name
    (out/'receipt.json').write_text(json.dumps(dict(passed=True,rtl_sha256=hashlib.sha256(RTL.read_bytes()).hexdigest(),
        actual_elf_transaction_replay=True,pl_package_rebuilt=False,target_tags_measured=False,
        cpu_transactions=len(transactions),prior_task_template=prior.relative_to(ROOT).as_posix()),indent=2)+'\n')
    print((out/'run.log').read_text().strip())


if __name__=='__main__':main()
