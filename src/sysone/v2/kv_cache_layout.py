"""Experimental packed INT8 KV address layout; no decoder or DMA integration.

Each layer holds a complete K matrix followed by V, with 16-byte padded rows.
Addresses remain relative offsets in a validated SYS3 memory window. Planning
does not allocate payloads, reserve Linux DDR or establish service-time bounds.
"""
from dataclasses import dataclass

from .memory_window import MemoryWindow


@dataclass(frozen=True)
class KvCacheLayout:
    window: MemoryWindow
    offset: int
    layers: int
    kv_heads: int
    head_dim: int
    capacity: int
    excluded_spans: tuple[tuple[int, int], ...] = ()

    def __post_init__(self):
        if not isinstance(self.window, MemoryWindow):
            raise ValueError('A validated memory window is required')
        if type(self.offset) is not int or self.offset < 0 or self.offset % 16:
            raise ValueError('KV offset must be a nonnegative aligned integer')
        if any(type(value) is not int or value <= 0 for value in
               (self.layers, self.kv_heads, self.head_dim, self.capacity)):
            raise ValueError('Positive integer KV dimensions required')
        self.window.address(self.offset, self.bytes)
        if type(self.excluded_spans) is not tuple or any(
                type(span) is not tuple or len(span) != 2 for span in self.excluded_spans):
            raise ValueError('Excluded spans must be immutable offset/length pairs')
        for start, length in self.excluded_spans:
            self.window.address(start, length)
            if length and self.offset < start + length and start < self.offset + self.bytes:
                raise ValueError('KV cache overlaps an excluded model or scratch span')

    @property
    def row_bytes(self):
        return self.kv_heads * self.head_dim

    @property
    def row_stride(self):
        return (self.row_bytes + 15) // 16 * 16

    @property
    def matrix_bytes(self):
        return self.capacity * self.row_stride

    @property
    def bytes(self):
        return self.layers * 2 * self.matrix_bytes

    def _matrix(self, layer, kind):
        if type(layer) is not int or not 0 <= layer < self.layers:
            raise ValueError('KV layer is outside the layout')
        if kind not in ('key', 'value'):
            raise ValueError('KV matrix must be key or value')
        return self.offset + (layer * 2 + int(kind == 'value')) * self.matrix_bytes

    def token_span(self, layer, kind, token):
        """Return one padded row (relative offset, bytes), without issuing it."""
        start = self._matrix(layer, kind)
        if type(token) is not int or not 0 <= token < self.capacity:
            raise ValueError('KV token is outside the layout')
        start += token * self.row_stride
        self.window.address(start, self.row_stride)
        return start, self.row_stride

    def prefix_requests(self, layer, kind, tokens, *, beats_width=16):
        """Stream whole-prefix descriptors using the finite-width RTL contract.

        Empty prefixes have no requests. Validate even the empty case's beat
        width so an invalid executor configuration is never silently accepted.
        """
        start = self._matrix(layer, kind)
        if type(tokens) is not int or not 0 <= tokens <= self.capacity:
            raise ValueError('KV prefix is outside the layout')
        if type(beats_width) is not int or not 1 <= beats_width <= 28:
            raise ValueError('Beat count width must fit the 33-bit byte contract')
        if tokens == 0:
            return iter(())
        return self.window.request_descriptors(start, tokens * self.row_stride,
                                              beats_width=beats_width)

    def range_requests(self, layer, kind, first_token, tokens, *, beats_width=16):
        """Plan a bounded cache slice; no transfer or cache mutation is issued.

        Validate the complete range before exposing a lazy descriptor iterator.
        An empty range may start at capacity, including the 4 GiB window end.
        """
        start = self._matrix(layer, kind)
        if (type(first_token) is not int or type(tokens) is not int
                or first_token < 0 or tokens < 0
                or first_token > self.capacity or tokens > self.capacity - first_token):
            raise ValueError('KV token range is outside the layout')
        if type(beats_width) is not int or not 1 <= beats_width <= 28:
            raise ValueError('Beat count width must fit the 33-bit byte contract')
        if tokens == 0:
            return iter(())
        start += first_token * self.row_stride
        return self.window.request_descriptors(start, tokens * self.row_stride,
                                              beats_width=beats_width)
