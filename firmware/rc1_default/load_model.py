"""Explicit idle model transition: exclusive load, close all VMAs, seal, full SHA.

Inference services must drain/stop first. No automatic hardware reset or reload.
"""
import argparse
import fcntl
import hashlib
import json
import mmap
import os
from pathlib import Path
import struct
import sys
import time

ROOT=Path('/var/lib/sysone/hardware-consolidated-rc1-20261108')
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.qwen_dma_ownership_v16 import BEGIN_LOAD, SEAL_MODEL, SYNC_COMMAND, ownership
from sysone.v2.qwen_fpga_runtime_candidate import dma_segments
from sysone.v2.qwen_weight_verification_v16 import verify_weights


def assert_idle():
    fd=os.open('/dev/mem',os.O_RDONLY|os.O_SYNC)
    try:
        with mmap.mmap(fd,4096,mmap.MAP_SHARED,mmap.PROT_READ,offset=0xa0000000) as regs:
            if not struct.unpack_from('<I',regs,0)[0]&4:
                raise RuntimeError('Decoder not idle; transition forbidden')
    finally:
        os.close(fd)


def load(package, source, *, legacy_rollback=False):
    manifest=json.loads((Path(package)/'model-manifest.json').read_text())
    tick=time.monotonic()
    with Path(source).open('rb') as model:
        if Path(source).stat().st_size!=manifest['bytes'] or hashlib.file_digest(model,'sha256').hexdigest()!=manifest['sha256']:
            raise RuntimeError('Source model differs from pinned manifest')
        model.seek(0)
        assert_idle()
        fd=os.open('/dev/sysone_qwen_dma',os.O_RDWR|os.O_SYNC)
        try:
            if not legacy_rollback:
                fcntl.ioctl(fd,BEGIN_LOAD,0)
            header,regions=dma_segments()
            if header['model_bytes']!=manifest['bytes']:
                raise RuntimeError('Allocated extent differs')
            for i,r in enumerate(regions):
                payload=min(1<<24,manifest['bytes']-i*(1<<24))
                if r['index']!=i or not 0<payload<=r['bytes']:
                    raise RuntimeError('DMA segment coverage differs')
                with mmap.mmap(fd,r['bytes'],mmap.MAP_SHARED,mmap.PROT_READ|mmap.PROT_WRITE,offset=i*(1<<24)) as view:
                    for offset in range(0,payload,4<<20):
                        data=model.read(min(4<<20,payload-offset))
                        if len(data)!=min(4<<20,payload-offset):raise RuntimeError('Short model read')
                        view[offset:offset+len(data)]=data
            if model.read(1):raise RuntimeError('Trailing model bytes')
            fcntl.ioctl(fd,SYNC_COMMAND,0)
            if not legacy_rollback:
                fcntl.ioctl(fd,SEAL_MODEL,0)
            proof=verify_weights(fd,manifest,header,regions)
            proof.update(transition_seconds=time.monotonic()-tick,
                         ownership=None if legacy_rollback else ownership())
            return proof
        finally:
            os.close(fd)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package',type=Path,required=True)
    ap.add_argument('--model',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    with Path('/run/lock/sysone-inference.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        proof=load(a.package,a.model)
        a.out.write_text(json.dumps(proof,indent=2)+'\n')
        print(json.dumps(proof))


if __name__=='__main__':main()
