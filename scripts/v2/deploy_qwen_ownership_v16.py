"""Replace legacy DMA driver with sealed ABI2, preserving explicit rollback.

No FPGA programming, reboot, service enablement or existing package edits.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from load_sealed_qwen_v16 import load,assert_idle
from qualify_qwen_dma_v16 import qualify
from sysone.v2.qwen_fpga_runtime_v9d import active_firmware


def run(args):
    p=subprocess.run(args,capture_output=True,text=True,timeout=120)
    if p.returncode:raise RuntimeError(str(args)+': '+p.stdout+p.stderr)
    return p.stdout


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package',type=Path,required=True)
    ap.add_argument('--model',type=Path,required=True)
    ap.add_argument('--old-module',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    new=ROOT/'firmware/qwen_dma_v2/sysone_qwen_dma_v2.ko'
    manifest=json.loads((a.package/'model-manifest.json').read_text())
    assert new.is_file() and a.old_module.is_file()
    with a.model.open('rb') as f:
        assert a.model.stat().st_size==manifest['bytes'] and hashlib.file_digest(f,'sha256').hexdigest()==manifest['sha256']
    before=dict(boot=Path('/proc/sys/kernel/random/boot_id').read_text(),image=active_firmware(),
                old_module_sha256=hashlib.sha256(a.old_module.read_bytes()).hexdigest(),
                new_module_sha256=hashlib.sha256(new.read_bytes()).hexdigest(),
                dma=Path('/sys/class/misc/sysone_qwen_dma/buffers').read_text())
    assert before['image']=='sysone-qwen-decoder-v9d.bit.bin'
    state=dict(passed=False,before=before,legacy_removed=False)
    def save():(a.out/'deployment.json').write_text(json.dumps(state,indent=2)+'\n')
    with Path('/run/lock/sysone-inference.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        assert_idle()
        save()
        try:
            run(['rmmod','sysone_qwen_dma_v1']);state['legacy_removed']=True;save()
            run(['insmod',str(new),'model_bytes='+str(manifest['bytes'])])
            state['ownership_qualification']=qualify();save()
            state['resident_load']=load(a.package,a.model);save()
            assert before['boot']==Path('/proc/sys/kernel/random/boot_id').read_text() and before['image']==active_firmware()
            state.update(passed=True,driver='sysone_qwen_dma_v2',resident_model_sealed=True);save()
        except BaseException as exc:
            state['error']=type(exc).__name__+': '+str(exc);save()
            if state['legacy_removed']:
                # Only unload while no FPGA work is in flight. rmmod also rejects live leases/VMAs.
                assert_idle()
                if Path('/sys/module/sysone_qwen_dma_v2').exists():run(['rmmod','sysone_qwen_dma_v2'])
                run(['insmod',str(a.old_module),'model_bytes='+str(manifest['bytes'])])
                state['rollback_load']=load(a.package,a.model,legacy_rollback=True)
                from sysone.v2.qwen_fpga_runtime_v9d import QwenFpga
                e=QwenFpga(a.package);e.close()
                state['rolled_back']=True;save()
            raise
    print(json.dumps(state,indent=2))


if __name__=='__main__':main()
