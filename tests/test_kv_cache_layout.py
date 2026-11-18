"""Planning must preserve packed GQA rows, boundaries and model exclusion."""
import pytest

from sysone.v2.kv_cache_layout import KvCacheLayout
from sysone.v2.memory_window import MemoryWindow


def test_gqa_layout_excludes_weights_and_has_disjoint_layer_matrices():
    window = MemoryWindow(0x800000000, 1 << 30)
    cache = KvCacheLayout(window, 256 << 20, 32, 4, 64, 4096,
                          excluded_spans=((0, 256 << 20),))
    assert cache.row_bytes == cache.row_stride == 256
    assert cache.bytes == 64 << 20
    spans = []
    for layer in range(32):
        for kind in ('key', 'value'):
            first, length = cache.token_span(layer, kind, 0)
            last, _ = cache.token_span(layer, kind, 4095)
            assert last + length == first + cache.matrix_bytes
            spans.append((first, last + length))
    assert spans[0][0] == 256 << 20
    assert all(a[1] == b[0] for a, b in zip(spans, spans[1:]))
    assert spans[-1][1] == (256 << 20) + cache.bytes


def test_padded_row_and_last_physical_word_do_not_wrap():
    window = MemoryWindow((1 << 40) - 1024, 1024)
    cache = KvCacheLayout(window, 896, 1, 3, 7, 2)
    assert cache.row_bytes == 21 and cache.row_stride == 32
    span = cache.token_span(0, 'value', 1)
    assert span == (992, 32)
    assert window.address(*span) + span[1] == 1 << 40


def test_four_gib_layout_and_finite_beat_descriptors_without_payload_allocation():
    cache = KvCacheLayout(MemoryWindow(0x800000400, 1 << 32), 0, 1, 1, 16, 1 << 27)
    assert cache.bytes == 1 << 32
    end = 1 << 31
    count = 0
    for offset, length in cache.prefix_requests(0, 'value', cache.capacity):
        assert offset == end and 0 < length // 16 <= 65535
        end += length
        count += 1
    assert end == 1 << 32 and count == 2049
    assert cache.token_span(0, 'value', cache.capacity - 1) == ((1 << 32) - 16, 16)


@pytest.mark.parametrize('span', [(0, 32), (48, 32), (63, 1)])
def test_overlaps_are_rejected_but_adjacent_spans_are_allowed(span):
    window = MemoryWindow(0x800000000, 4096)
    with pytest.raises(ValueError, match='overlaps'):
        KvCacheLayout(window, 16, 1, 1, 16, 2, (span,))
    assert KvCacheLayout(window, 16, 1, 1, 16, 2, ((0, 16), (80, 16))).bytes == 64


@pytest.mark.parametrize('kwargs', [
    {'offset': 1}, {'offset': True}, {'layers': 0}, {'layers': True},
    {'kv_heads': -1}, {'head_dim': 1.0}, {'capacity': 0}, {'capacity': 1 << 32},
])
def test_invalid_dimensions_or_window_overflow_rejected(kwargs):
    values = dict(window=MemoryWindow(0x800000000, 4096), offset=0,
                  layers=1, kv_heads=1, head_dim=16, capacity=2)
    values.update(kwargs)
    with pytest.raises(ValueError):
        KvCacheLayout(**values)


@pytest.mark.parametrize('layer,kind,token', [(True, 'key', 0), (1, 'key', 0),
    (0, 'unknown', 0), (0, 'key', -1), (0, 'key', 2), (0, 'key', True)])
def test_invalid_row_accesses_rejected(layer, kind, token):
    cache = KvCacheLayout(MemoryWindow(0x800000000, 4096), 0, 1, 1, 16, 2)
    with pytest.raises(ValueError):
        cache.token_span(layer, kind, token)


def test_prefix_limits_empty_and_chunk_boundary():
    cache = KvCacheLayout(MemoryWindow(0x800000000, 1 << 24), 0, 1, 1, 16, 65536)
    assert list(cache.prefix_requests(0, 'key', 0)) == []
    assert list(cache.prefix_requests(0, 'key', 65536)) == [(0, 1048560), (1048560, 16)]
    for tokens, width in ((65537, 16), (True, 16), (0, True), (0, 29)):
        with pytest.raises(ValueError):
            list(cache.prefix_requests(0, 'key', tokens, beats_width=width))


@pytest.mark.parametrize('spans', [[(0, 16)], ([0, 16],), ((0,),), ((0, 1, 2),)])
def test_excluded_spans_cannot_mutate_after_validation(spans):
    with pytest.raises(ValueError, match='immutable'):
        KvCacheLayout(MemoryWindow(0x800000000, 4096), 16, 1, 1, 16, 2, spans)


def test_range_at_last_40_bit_word_and_empty_window_end():
    cache = KvCacheLayout(MemoryWindow((1 << 40) - (1 << 32), 1 << 32),
                          0, 1, 1, 16, 1 << 27)
    assert list(cache.range_requests(0, 'value', cache.capacity - 1, 1)) == [((1 << 32) - 16, 16)]
    assert list(cache.range_requests(0, 'value', cache.capacity, 0)) == []
    assert cache.window.address((1 << 32) - 16, 16) + 16 == 1 << 40


def test_range_chunking_preserves_padded_rows_and_prefix_contract():
    cache = KvCacheLayout(MemoryWindow(0x800000000, 1 << 24), 64, 2, 3, 7, 65536)
    assert list(cache.range_requests(1, 'value', 0, 65536)) == list(cache.prefix_requests(1, 'value', 65536))
    start, _ = cache.token_span(1, 'key', 3)
    chunks = list(cache.range_requests(1, 'key', 3, 32768))
    assert chunks == [(start, 1048560), (start + 1048560, 16)]


@pytest.mark.parametrize('first,tokens,width', [
    (-1, 0, 16), (3, 0, 16), (2, 1, 16), (1, 2, 16),
    (True, 0, 16), (0, True, 16), (0, -1, 16), (0, 0, True), (2, 0, 29),
])
def test_invalid_ranges_are_rejected_before_iteration(first, tokens, width):
    cache = KvCacheLayout(MemoryWindow(0x800000000, 4096), 0, 1, 1, 16, 2)
    with pytest.raises(ValueError):
        cache.range_requests(0, 'value', first, tokens, beats_width=width)
