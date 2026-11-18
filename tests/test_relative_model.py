import numpy as np
import pytest
from test_ddr_image import _tiny
from sysone.v2 import ddr_image as di
from sysone.v2.memory_window import MemoryWindow
from sysone.v2.relative_model import RelativeModel

def test_high_ddr_bundle_keeps_offsets_and_integer_reference(tmp_path):
    encoder,_=_tiny(L=1,P=128)
    model=RelativeModel.compile(encoder,'relative-test',MemoryWindow(0x800000000,1<<22))
    h=di.verify_image(model.image)
    assert h['base']==0
    manifest=model.manifest()
    assert model.window.address(manifest['program_offset'],16)>1<<32
    ids=np.array([1,2,3],dtype=np.int64)
    np.testing.assert_array_equal(di.ImageMachine(model.image).hidden(ids),encoder.hidden(ids))
    families = (0x53590100,0x53590400,0x53590500,0x53590600,0x53590700,
                *(0x53591000 | (bits << 8) for bits in range(16)))
    for old_caps in [0,0xdeadbeff,0x53590300] + [family | flags for family in families for flags in range(256)]:
        with pytest.raises(ValueError):model.require_executor(old_caps)
    for malformed in [True,False,-1,1<<32,0x53590301+0.0,'0x53590301',None]:
        with pytest.raises(ValueError):model.require_executor(malformed)
    model.require_executor(0x53590301)
    assert manifest['required_executor_abi']==0x53590300
    assert manifest['required_executor_abi_mask']==0xffffff00
    assert manifest['required_capability_bit']==0
    model.write(tmp_path/'bundle')
    assert (tmp_path/'bundle'/'image.bin').read_bytes()==model.image
    assert MemoryWindow.from_descriptor((tmp_path/'bundle'/'memory-window.bin').read_bytes())==model.window
    with pytest.raises(FileExistsError):model.write(tmp_path/'bundle')

def test_rejects_small_region_and_absolute_payload():
    encoder,_=_tiny(L=1,P=128)
    with pytest.raises(ValueError):RelativeModel.compile(encoder,'small',MemoryWindow(0x800000000,1024))
    image,_=di.compile_image(encoder,'absolute',base=0x60000000)
    with pytest.raises(ValueError,match='compiled at zero'):RelativeModel(image,MemoryWindow(0x800000000,1<<20))
