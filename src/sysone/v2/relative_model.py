"""Experimental SYS3 model bundle, requiring a future relative-address executor.

The inner v2 payload is compiled at zero, so its instruction/section addresses
are offsets. The outer descriptor supplies the physical base; it is not written
ahead of the payload. Current v2 board loaders must not consume this bundle.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from . import ddr_image
from .encoder_client import RequestLayout
from .memory_window import MemoryWindow

# A separate experimental ABI prevents SYS2 capture/FIFO feature bits from
# being mistaken for relative-address support. No deployed app advertises it.
RELATIVE_EXECUTOR_ABI = 0x53590300
RELATIVE_EXECUTOR_ABI_MASK = 0xffffff00
RELATIVE_ADDRESS_CAPABILITY = 1 << 0

@dataclass(frozen=True)
class RelativeModel:
    image: bytes
    window: MemoryWindow

    def __post_init__(self):
        header=ddr_image.verify_image(self.image)
        if header['base'] != 0:
            raise ValueError('Relative payload must be compiled at zero')
        self.window.address(0,len(self.image))
        for section in header['section_table']:
            self.window.address(section['address'],section['bytes'])
        layout=RequestLayout.for_image(header,len(self.image))
        self.window.address(layout.ids,layout.max_tokens*2)
        self.window.address(layout.result,layout.max_tokens*layout.hidden)

    @classmethod
    def compile(cls, encoder, name, window, *, tile_out=32, max_tokens=128):
        image,_=ddr_image.compile_image(encoder,name,base=0,tile_out=tile_out,max_tokens=max_tokens)
        return cls(image,window)

    def require_executor(self, capabilities):
        if (type(capabilities) is not int or not 0 <= capabilities < 1 << 32
            or capabilities & RELATIVE_EXECUTOR_ABI_MASK != RELATIVE_EXECUTOR_ABI
            or not capabilities & RELATIVE_ADDRESS_CAPABILITY):
            raise ValueError('Executor does not support SYS3 relative model addresses')

    def manifest(self):
        header=ddr_image.parse_header(self.image)
        layout=RequestLayout.for_image(header,len(self.image))
        return {'format':'sysone.relative.v3','payload_format':header['format'],
                'image_sha256':hashlib.sha256(self.image).hexdigest(),
                'payload_bytes':len(self.image),'physical_base':self.window.base,
                'window_bytes':self.window.size,'required_capability_bit':0,
                'required_executor_abi':RELATIVE_EXECUTOR_ABI,
                'required_executor_abi_mask':RELATIVE_EXECUTOR_ABI_MASK,
                'program_offset':layout.program,'ids_offset':layout.ids,'result_offset':layout.result,
                'hardware_qualified':False}

    def write(self, directory):
        directory=Path(directory)
        directory.mkdir(parents=True,exist_ok=False)
        (directory/'image.bin').write_bytes(self.image)
        (directory/'memory-window.bin').write_bytes(self.window.descriptor())
        (directory/'bundle.json').write_text(json.dumps(self.manifest(),indent=2)+'\n')
