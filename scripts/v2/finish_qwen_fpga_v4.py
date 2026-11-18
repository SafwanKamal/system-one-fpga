"""Promote a successful faster compact typed call on the existing batch FPGA."""
import argparse,fcntl,hashlib,json,mmap,os,struct,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.qwen_fpga_runtime_v3 import APP,active_firmware,bound
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,required=True);args=ap.parse_args()
    package=args.package.resolve();lock=Path('/run/lock/sysone-inference.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX)
    baseline_path=Path('/var/lib/sysone/qwen-fpga-decoder-v4/deployment-proof.json')
    baseline=json.loads(baseline_path.read_text());old=baseline['real_command']
    r=json.loads((package/'real-command-result.json').read_text());boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    assert r['complete'] and r['tools_executed'] and r['resident_weights_verified']
    assert r['query']==old['query'] and r['call']==old['call'] and r['tool_result']==old['tool_result']
    assert r['linux_boot_id']==boot==baseline['linux_boot_id']
    assert r['model_sha256']==old['model_sha256'] and not r['ARM_model_inference'] and not r['host_model_inference']
    assert r['prefix_tokens_reused']==0 and r['finish_reason']=='typed_json_complete'
    assert r['vocabulary_rows_projected']==len(r['generated_ids'])*151936
    assert r['elapsed_seconds']<old['elapsed_seconds'],'No observed speed improvement; retain launcher'
    expected=json.loads((package/'package-sha256.json').read_text())
    for name,digest in expected.items():assert hashlib.sha256((package/name).read_bytes()).hexdigest()==digest,name
    installed=Path('/lib/firmware/xilinx')/APP
    assert (installed/'build.json').read_bytes()==(package/APP/'build.json').read_bytes()
    assert active_firmware()==APP+'.bit.bin'
    dt=Path('/sys/firmware/devicetree/base');bus=dt/(dt/'__symbols__/amba').read_bytes().rstrip(bytes([0])).decode().lstrip('/')
    assert bound(bus/'qwen-clocking0','xilinx_fclk') and bound(bus/'qwen-afi','afi-fpga')
    assert Path('/sys/class/fpga_manager/fpga0/state').read_text().strip()=='operating'
    clock=[s.split() for s in Path('/sys/kernel/debug/clk/clk_summary').read_text().splitlines() if s.split() and s.split()[0]=='pl0_ref']
    assert len(clock)==1 and int(clock[0][1]) and 99000000<=int(clock[0][4])<=100000000
    fd=os.open('/dev/mem',os.O_RDONLY|os.O_SYNC)
    try:
        with mmap.mmap(fd,4096,mmap.MAP_SHARED,mmap.PROT_READ,offset=0xa0000000) as view:control=struct.unpack_from('<I',view,0)[0]
    finally:os.close(fd)
    assert control&4 and not Path('/sys/module/sysone_r5_smoke').exists()
    assert subprocess.run(['systemctl','is-active','--quiet','sysone-qwen06b-mvp.service']).returncode!=0
    entry=Path('/usr/local/bin/sysone-qwen-fpga');backup=package/'sysone-qwen-fpga.previous'
    if not backup.exists():backup.write_bytes(entry.read_bytes())
    launcher='#!/bin/sh\nexec /usr/bin/python3 '+str(package/'scripts/v2/run_qwen_fpga_command_v4.py')+' --package '+str(package)+' --out '+str(package/'last-command-result.json')+' "$@"\n'
    temp=entry.with_name('.sysone-qwen-fpga.new');temp.write_text(launcher);temp.chmod(0o755);os.replace(temp,entry)
    proof=dict(complete=True,model='Qwen3-0.6B',all_model_math_on_FPGA=True,ARM_model_inference=False,host_model_inference=False,FPGA_image_changed=False,fpga_app=APP,clock_hz=int(clock[0][4]),linux_boot_id=boot,linux_rebooted=False,decoder_idle_after_command=True,final_ap_control=control,entrypoint=str(entry),entrypoint_sha256=hashlib.sha256(entry.read_bytes()).hexdigest(),vocabulary_helper_sha256=hashlib.sha256((package/'qwen_vocab_session').read_bytes()).hexdigest(),package_files_verified=expected,baseline_command=old,baseline_deployment_sha256=hashlib.sha256(baseline_path.read_bytes()).hexdigest(),real_command=r,semantic_call_matches_baseline=True,generated_ids_comparable=False,comparison='Same query/model/tool result; compact prompt and output format, syntax completion instead of EOS',speedup=old['elapsed_seconds']/r['elapsed_seconds'],time_reduction_percent=100*(1-r['elapsed_seconds']/old['elapsed_seconds']),deployment_lifetime='current Linux boot; files and launcher persist on disk')
    (package/'deployment-proof.json').write_text(json.dumps(proof,indent=2)+'\n');lock.close();print(json.dumps(proof,indent=2))
if __name__=='__main__':main()
