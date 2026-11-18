import pytest
from sysone.v2.memory_window import MemoryWindow

def test_high_ddr_and_boundary_splits():
    w = MemoryWindow(0x800000000, 1 << 30)
    assert w.address(0x1230, 16) == 0x800001230
    assert w.bursts(4080, 8192) == [(0x800000ff0, 1), (0x800001000, 256), (0x800002000, 255)]
    assert MemoryWindow.from_descriptor(w.descriptor()) == w

@pytest.mark.parametrize('base,size', [(1,4096),(-1024,4096),(0,0),(0,(1<<32)+1),((1<<40)-1024,2048)])
def test_invalid_windows(base,size):
    with pytest.raises(ValueError): MemoryWindow(base,size)

@pytest.mark.parametrize('offset,size', [(-16,16),(4096,16),(4080,32),(1,16),(0,15),(0,-16),(1<<32,0)])
def test_rejected_transfers(offset,size):
    with pytest.raises(ValueError): MemoryWindow(0x800000000,4096).bursts(offset,size)

def test_end_of_window_and_unknown_version():
    w=MemoryWindow(0x800000000,4096)
    assert w.bursts(4080,16)==[(0x800000ff0,1)]
    bad=bytearray(w.descriptor());bad[4]=4
    with pytest.raises(ValueError): MemoryWindow.from_descriptor(bad)

def test_relative_request_chunking_preserves_full_four_gib_window():
    w=MemoryWindow(0x800000000,1<<32)
    position=0;requests=0
    for offset,length in w.request_descriptors(0,1<<32):
        assert offset==position and length%16==0 and 0<length//16<=65535
        assert w.address(offset,length)==w.base+position
        position+=length;requests+=1
    assert position==1<<32 and requests==4097

def test_request_limit_and_small_beat_count_match_adapter_contract():
    w=MemoryWindow(0x800000000,1<<24)
    assert list(w.request_descriptors(16,1048576))==[(16,1048560),(1048576,16)]
    assert list(w.request_descriptors(0,4096,beats_width=8))==[(0,4080),(4080,16)]

@pytest.mark.parametrize('offset,length,width',[(0,0,16),(1,16,16),(0,15,16),
    (0,16,0),(0,16,29),(0,16,True),(True,16,16),(0,16.5,16)])
def test_rejects_invalid_relative_request_descriptors(offset,length,width):
    with pytest.raises(ValueError):list(MemoryWindow(0x800000000,4096).request_descriptors(offset,length,beats_width=width))

@pytest.mark.parametrize('base,size',[(0,True),(True,4096),(0,4096.0),('0',4096)])
def test_window_contract_requires_integer_fields(base,size):
    with pytest.raises(ValueError):MemoryWindow(base,size)


def test_streamed_full_window_keeps_page_boundaries_and_total_coverage():
    window=MemoryWindow(0x800000400,1<<32)
    expected=window.base;count=0
    for address,beats in window.iter_bursts(0,1<<32):
        assert address==expected and 0<beats<=256
        assert address//4096==(address+beats*16-1)//4096
        expected+=beats*16;count+=1
    assert expected==window.base+(1<<32) and count==1048577


def test_streamed_physical_endpoint_and_zero_length():
    window=MemoryWindow((1<<40)-1024,1024)
    assert list(window.iter_bursts(0,1024))==[((1<<40)-1024,64)]
    assert list(window.iter_bursts(0,0))==[]


@pytest.mark.parametrize('offset,length',[(1,16),(0,15),(4096,16),(4080,32)])
def test_streamed_bursts_reject_before_first_output(offset,length):
    stream=MemoryWindow(0x800000000,4096).iter_bursts(offset,length)
    with pytest.raises(ValueError):next(stream)
