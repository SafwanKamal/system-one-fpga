"""Promote a faster, successful FPGA command and retain its deployed predecessor."""
import argparse,fcntl,hashlib,json,mmap,os,struct,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.qwen_fpga_runtime_v3 import active_firmware,bound,APP

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,required=True);args=ap.parse_args()
    package=args.package.resolve()
    lock=Path('/run/lock/sysone-inference.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX)
    previous=json.loads(Path('/var/lib/sysone/qwen-fpga-decoder-v3/deployment-proof.json').read_text());baseline=dict(command=previous['real_command'])
    result=json.loads((package/'real-command-result.json').read_text())
    smoke=json.loads((package/'hardware-block-smoke.json').read_text())
    deployment=json.loads((package/'deployment-state.json').read_text())
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    assert result['complete'] and result['tools_executed'] and smoke['passed'] and deployment['complete']
    assert result['tool_result']['text']==result['linux_boot_id']==baseline['command']['linux_boot_id']==boot
    assert result['prompt_ids']==baseline['command']['prompt_ids']
    assert result['prefix_tokens_reused']==0 and result['generated_ids']==baseline['command']['generated_ids']
    assert result['prefill_groups']==(len(result['prompt_ids'])+3)//4 and result['prefill_tokens']==len(result['prompt_ids'])
    assert result['layer_weight_passes']<baseline['command']['decoder_layer_calls']
    assert result['elapsed_seconds']<baseline['command']['elapsed_seconds'],'No observed speed improvement; retain the old launcher'
    expected=json.loads((package/'package-sha256.json').read_text())
    for name,digest in expected.items():assert hashlib.sha256((package/name).read_bytes()).hexdigest()==digest,name
    dt=Path('/sys/firmware/devicetree/base');bus=dt/(dt/'__symbols__/amba').read_bytes().rstrip(bytes([0])).decode().lstrip('/')
    assert active_firmware()==APP+'.bit.bin' and bound(bus/'qwen-clocking0','xilinx_fclk') and bound(bus/'qwen-afi','afi-fpga')
    assert Path('/sys/class/fpga_manager/fpga0/state').read_text().strip()=='operating'
    clock=[line.split() for line in Path('/sys/kernel/debug/clk/clk_summary').read_text().splitlines() if line.split() and line.split()[0]=='pl0_ref']
    assert len(clock)==1 and int(clock[0][1]) and 99000000<=int(clock[0][4])<=100000000
    fd=os.open('/dev/mem',os.O_RDONLY|os.O_SYNC)
    try:
        with mmap.mmap(fd,4096,mmap.MAP_SHARED,mmap.PROT_READ,offset=0xa0000000) as view:control=struct.unpack_from('<I',view,0)[0]
    finally:os.close(fd)
    assert control&4
    assert not Path('/sys/module/sysone_r5_smoke').exists()
    assert subprocess.run(['systemctl','is-active','--quiet','sysone-qwen06b-mvp.service']).returncode!=0
    entry=Path('/usr/local/bin/sysone-qwen-fpga');backup=package/'sysone-qwen-fpga.previous'
    if not backup.exists():backup.write_bytes(entry.read_bytes())
    launcher='\n'.join(['#!/bin/sh','exec /usr/bin/python3 '+str(package/'scripts/v2/run_qwen_fpga_command_v3.py')+' --package '+str(package)+' --out '+str(package/'last-command-result.json')+' "$@"',''])
    temp=entry.with_name('.sysone-qwen-fpga.new');temp.write_text(launcher);temp.chmod(0o755);os.replace(temp,entry)
    proof=dict(complete=True,model='Qwen3-0.6B',all_model_math_on_FPGA=True,ARM_model_inference=False,host_model_inference=False,linux_boot_id=boot,linux_rebooted=False,fpga_app=APP,clock_hz=int(clock[0][4]),decoder_idle_after_command=True,final_ap_control=control,entrypoint=str(entry),entrypoint_sha256=hashlib.sha256(entry.read_bytes()).hexdigest(),package_files_verified=expected,baseline_profile=baseline,real_command=result,hardware_block_smoke=smoke,deployment=deployment,generated_ids_match_baseline=result['generated_ids']==baseline['command']['generated_ids'],speedup=baseline['command']['elapsed_seconds']/result['elapsed_seconds'],time_reduction_percent=100*(1-result['elapsed_seconds']/baseline['command']['elapsed_seconds']),model_memory=Path('/sys/class/misc/sysone_qwen_dma/buffers').read_text().splitlines()[0],deployment_lifetime='current Linux boot; files and launcher persist on disk')
    proof.update(cold_prefill=True,prefill_batch_size=4,baseline_deployment_sha256=hashlib.sha256(Path('/var/lib/sysone/qwen-fpga-decoder-v3/deployment-proof.json').read_bytes()).hexdigest())
    (package/'deployment-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    lock.close()
    print(json.dumps(proof,indent=2))

if __name__=='__main__':main()
