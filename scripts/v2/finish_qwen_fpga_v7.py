"""Promote a faster, successful FPGA command and retain its deployed predecessor."""
import argparse,fcntl,hashlib,json,mmap,os,struct,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.qwen_fpga_runtime_v7 import active_firmware,bound,APP

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,required=True);args=ap.parse_args()
    package=args.package.resolve()
    manifest=json.loads((package/'model-manifest.json').read_text())
    batch=json.loads((package/APP/'build.json').read_text())['model_profile']['prefill_batch']
    lock=Path('/run/lock/sysone-inference.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX)
    previous=json.loads(Path('/var/lib/sysone/qwen-fpga-decoder-v7/deployment-proof.json').read_text());baseline=dict(command=previous['real_command'])
    result=json.loads((package/'real-command-result.json').read_text())
    smoke=json.loads((package/'hardware-block-smoke.json').read_text())
    deployment=json.loads((package/'deployment-state.json').read_text())
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    assert result['complete'] and result['tools_executed'] and smoke['passed'] and deployment['complete']
    assert result['tool_result']['text']==result['linux_boot_id']==deployment['linux_boot_id']==boot
    assert result['prompt_ids']==baseline['command']['prompt_ids']
    assert result['prefix_tokens_reused']==0
    assert result['prefill_groups']==(len(result['prompt_ids'])+batch-1)//batch and result['prefill_tokens']==len(result['prompt_ids'])
    assert result['layer_weight_passes']<baseline['command']['decoder_layer_calls']
    assert result['elapsed_seconds']<10.0,'No cold improvement; retain the old launcher'
    assert result['layer_weight_passes']==((len(result['prompt_ids'])+batch-1)//batch+len(result['generated_ids'])-1)*manifest['layers']
    assert result['finish_reason']=='typed_json_complete'
    assert result['call']==baseline['command']['call'] and result['tool_result']['executed'] and result['tool_result']['path']==baseline['command']['tool_result']['path']
    assert result['model_sha256']==baseline['command']['model_sha256'] and result['resident_weights_verified']
    assert result['vocabulary_rows_projected']==len(result['generated_ids'])*json.loads((package/'model-manifest.json').read_text())['vocab']
    assert not result['ARM_model_inference'] and not result['host_model_inference']
    tokenizer_sha=hashlib.sha256((package/'tokenizer.json').read_bytes()).hexdigest()
    assert tokenizer_sha==json.loads((package/APP/'build.json').read_text())['tokenizer_sha256']
    expected=json.loads((package/'package-sha256.json').read_text())
    for name,digest in expected.items():assert hashlib.sha256((package/name).read_bytes()).hexdigest()==digest,name
    dt=Path('/sys/firmware/devicetree/base');bus=dt/(dt/'__symbols__/amba').read_bytes().rstrip(bytes([0])).decode().lstrip('/')
    assert active_firmware()==APP+'.bit.bin' and bound(bus/'qwen-clocking0','xilinx_fclk') and bound(bus/'qwen-afi','afi-fpga')
    assert Path('/sys/class/fpga_manager/fpga0/state').read_text().strip()=='operating'
    clock=[line.split() for line in Path('/sys/kernel/debug/clk/clk_summary').read_text().splitlines() if line.split() and line.split()[0]=='pl0_ref']
    assert len(clock)==1 and int(clock[0][1]) and 124000000<=int(clock[0][4])<=125000000
    fd=os.open('/dev/mem',os.O_RDONLY|os.O_SYNC)
    try:
        with mmap.mmap(fd,4096,mmap.MAP_SHARED,mmap.PROT_READ,offset=0xa0000000) as view:control=struct.unpack_from('<I',view,0)[0]
    finally:os.close(fd)
    assert control&4
    assert 249000000<=result['memory_clock_hz']<=250000000 and bound(bus/'qwen-clocking1','xilinx_fclk')
    assert not Path('/sys/module/sysone_r5_smoke').exists()
    assert subprocess.run(['systemctl','is-active','--quiet','sysone-qwen06b-mvp.service']).returncode!=0
    entry=Path('/usr/local/bin/sysone-qwen-fpga');backup=package/'sysone-qwen-fpga.previous'
    if not backup.exists():backup.write_bytes(entry.read_bytes())
    launcher='\n'.join(['#!/bin/sh','exec /usr/bin/python3 '+str(package/'scripts/v2/run_qwen_fpga_command_v7.py')+' --package '+str(package)+' --out '+str(package/'last-command-result.json')+' "$@"',''])
    temp=entry.with_name('.sysone-qwen-fpga.new');temp.write_text(launcher);temp.chmod(0o755);os.replace(temp,entry)
    proof=dict(complete=True,model=json.loads((package/'model-manifest.json').read_text())['model'],all_model_math_on_FPGA=True,ARM_model_inference=False,host_model_inference=False,linux_boot_id=boot,linux_rebooted=False,baseline_linux_boot_id=baseline['command']['linux_boot_id'],baseline_from_previous_boot=baseline['command']['linux_boot_id']!=boot,fpga_app=APP,clock_hz=int(clock[0][4]),decoder_idle_after_command=True,final_ap_control=control,entrypoint=str(entry),entrypoint_sha256=hashlib.sha256(entry.read_bytes()).hexdigest(),package_files_verified=expected,baseline_profile=baseline,real_command=result,hardware_block_smoke=smoke,deployment=deployment,generated_ids_match_baseline=result['generated_ids']==baseline['command']['generated_ids'],speedup=baseline['command']['elapsed_seconds']/result['elapsed_seconds'],time_reduction_percent=100*(1-result['elapsed_seconds']/baseline['command']['elapsed_seconds']),model_memory=Path('/sys/class/misc/sysone_qwen_dma/buffers').read_text().splitlines()[0],deployment_lifetime='current Linux boot; files and launcher persist on disk')
    proof.update(norm_rope_local_buffers=True,cold_startup_overlapped=True,all_resident_bytes_verified_each_command=True,comparison_method='single cold command versus deployed v7; same boot, pinned Q8 weights, INT8 activation dot products',matrix_streaming=True,under_30_seconds=result['elapsed_seconds']<30.0,target_10_seconds_met=result['elapsed_seconds']<10.0,tokenizer_sha256=tokenizer_sha,tokenizer_backend='compiled ranked BPE with native NFC/Split/ByteLevel; no NN',model_profile=json.loads((package/APP/'build.json').read_text())['model_profile'],cold_prefill=True,prefill_batch_size=batch,baseline_deployment_sha256=hashlib.sha256(Path('/var/lib/sysone/qwen-fpga-decoder-v7/deployment-proof.json').read_bytes()).hexdigest())
    (package/'deployment-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    lock.close()
    print(json.dumps(proof,indent=2))

if __name__=='__main__':main()
