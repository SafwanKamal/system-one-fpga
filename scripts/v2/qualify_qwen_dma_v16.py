"""Negative tests on newly allocated ABI2 weights, BEFORE model loading.

Caller holds the inference lock; no FPGA commands are issued here.
"""
import ctypes
import errno
import fcntl
import json
import mmap
import os
from pathlib import Path
import sys
from contextlib import ExitStack

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.qwen_dma_ownership_v16 import BEGIN_LOAD,SEAL_MODEL,CLAIM_INFERENCE,ownership
from sysone.v2.qwen_weight_verification_v16 import readonly_address


def qualify():
    checks=[]
    def rejected(label,operation,allowed):
        try:operation()
        except OSError as exc:
            if exc.errno not in allowed:raise
            checks.append(dict(check=label,errno=exc.errno,passed=True))
        else:raise RuntimeError(label+' unexpectedly allowed')
    fd=os.open('/dev/sysone_qwen_dma',os.O_RDWR|os.O_SYNC)
    try:
        initial=ownership()
        rejected('concurrent_open',lambda:os.open('/dev/sysone_qwen_dma',os.O_RDWR),[errno.EBUSY])
        rejected('uninitialized_inference',lambda:fcntl.ioctl(fd,CLAIM_INFERENCE,0),[errno.EPERM])
        fcntl.ioctl(fd,BEGIN_LOAD,0)
        with mmap.mmap(fd,4096,mmap.MAP_SHARED,mmap.PROT_READ|mmap.PROT_WRITE) as view:
            view[:4]=b'TEST'
            rejected('seal_with_existing_writable_vma',lambda:fcntl.ioctl(fd,SEAL_MODEL,0),[errno.EBUSY])
            rejected('load_with_existing_vma',lambda:fcntl.ioctl(fd,BEGIN_LOAD,0),[errno.EBUSY])
        fcntl.ioctl(fd,SEAL_MODEL,0)
        sealed=ownership()
        assert sealed['sealed'] and sealed['generation']>initial['generation'] and sealed['vmas']==0
        rejected('writable_mapping_after_seal',lambda:mmap.mmap(fd,4096,mmap.MAP_SHARED,mmap.PROT_READ|mmap.PROT_WRITE),[errno.EPERM,errno.EACCES])
        with ExitStack() as stack:
            view=stack.enter_context(mmap.mmap(fd,4096,mmap.MAP_SHARED,mmap.PROT_READ))
            address=readonly_address(view,stack)
            libc=ctypes.CDLL(None,use_errno=True)
            libc.mprotect.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_int]
            libc.mprotect.restype=ctypes.c_int
            assert libc.mprotect(address,4096,mmap.PROT_READ|mmap.PROT_WRITE)==-1
            assert ctypes.get_errno() in (errno.EACCES,errno.EPERM)
            checks.append(dict(check='mprotect_cannot_restore_write',passed=True))
            rejected('transition_with_readonly_vma',lambda:fcntl.ioctl(fd,BEGIN_LOAD,0),[errno.EBUSY])
        assert ownership()['vmas']==0
        fcntl.ioctl(fd,CLAIM_INFERENCE,0)
        rejected('inference_lease_cannot_unseal',lambda:fcntl.ioctl(fd,BEGIN_LOAD,0),[errno.EPERM])
        rejected('inference_lease_cannot_seal',lambda:fcntl.ioctl(fd,SEAL_MODEL,0),[errno.EPERM])
        with mmap.mmap(fd,4096,mmap.MAP_SHARED,mmap.PROT_READ) as view:
            os.close(fd);fd=None
            rejected('vma_keeps_owner_after_fd_close',lambda:os.open('/dev/sysone_qwen_dma',os.O_RDWR),[errno.EBUSY])
        assert ownership()['owner_tgid']==0 and ownership()['vmas']==0
        return dict(passed=True,checks=checks,final=ownership())
    finally:
        if fd is not None:os.close(fd)


if __name__=='__main__':print(json.dumps(qualify(),indent=2))
