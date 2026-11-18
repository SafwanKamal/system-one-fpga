"""Proposed v3 relative-address contract; not accepted by the deployed v2 RTL."""
from dataclasses import dataclass
import struct

_DESCRIPTOR = struct.Struct('<4sHHQQ')

@dataclass(frozen=True)
class MemoryWindow:
    base: int
    size: int

    def __post_init__(self):
        if type(self.base) is not int or type(self.size) is not int or self.base < 0 or self.base % 1024 or not 0 < self.size <= 1 << 32:
            raise ValueError('Aligned base and 1..4GiB window required')
        if self.base + self.size > 1 << 40:
            raise ValueError('Window exceeds the 40-bit AXI address space')

    def address(self, offset: int, length: int) -> int:
        if type(offset) is not int or type(length) is not int or not 0 <= offset < 1 << 32 or length < 0 or offset + length > self.size:
            raise ValueError('Transfer outside model window')
        return self.base + offset

    def iter_bursts(self, offset: int, length: int):
        """Stream 128-bit AXI bursts without allocating a full-window schedule.

        Transfers stay within physical4KiB pages and256beats. This describes
        protocol planning only, not a reserved allocation or DMA execution.
        """
        address = self.address(offset, length)
        if address % 16 or length % 16:
            raise ValueError('AXI transfers must be whole aligned 128-bit beats')
        while length:
            count = min(length, 4096 - (address % 4096), 256 * 16)
            yield address, count // 16
            address += count
            length -= count

    def bursts(self, offset: int, length: int):
        """Compatibility list API; use iter_bursts for large windows."""
        return list(self.iter_bursts(offset, length))

    def request_descriptors(self, offset: int, length: int, *, beats_width: int = 16):
        """Yield relative (offset, bytes) tuples for the experimental RTL adapter.

        The AXI port splits each accepted descriptor at physical 4KiB pages.
        Chunk here first so its finite-width beat count never truncates. This
        iterator does not allocate model data or establish a reserved region.
        """
        address = self.address(offset, length)
        if type(beats_width) is not int or not 1 <= beats_width <= 28:
            raise ValueError('Beat count width must fit the 33-bit byte contract')
        if address % 16 or length <= 0 or length % 16:
            raise ValueError('Request must contain positive aligned 128-bit beats')
        limit = ((1 << beats_width) - 1) * 16
        while length:
            count = min(length, limit)
            yield offset, count
            offset += count
            length -= count

    def descriptor(self) -> bytes:
        return _DESCRIPTOR.pack(b'SYS3', 3, 0, self.base, self.size)

    @classmethod
    def from_descriptor(cls, data: bytes):
        magic, version, flags, base, size = _DESCRIPTOR.unpack(data)
        if (magic, version, flags) != (b'SYS3', 3, 0):
            raise ValueError('Unsupported memory contract')
        return cls(base, size)
