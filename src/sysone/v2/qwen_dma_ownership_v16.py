"""ABI2 DMA ownership: one open owner, explicit load/seal and inference leases."""
from pathlib import Path
import os

SYNC_COMMAND = 0x515701
BEGIN_LOAD = 0x515702
SEAL_MODEL = 0x515703
CLAIM_INFERENCE = 0x515704
STATUS = Path('/sys/class/misc/sysone_qwen_dma/ownership')


def ownership():
    values = {k: int(v, 0) for k, v in
              (item.split('=') for item in STATUS.read_text().split())}
    if values['abi'] != 2:
        raise RuntimeError('Ownership-capable DMA ABI2 required')
    return values


def claim_inference(fd):
    import fcntl
    fcntl.ioctl(fd, CLAIM_INFERENCE, 0)
    state = ownership()
    if not state['sealed'] or state['loading'] or state['owner_tgid'] != os.getpid():
        raise RuntimeError('Exclusive sealed inference lease was not acquired')
    return state
