"""The KR260's ARM side of a request: the same write / read / run interface as the
Ethernet memory link (scripts/v2/memory_link_client.py Link), on /dev/mem.

    link = Kr260Link(registers=0xA000_0000, memory=(0x6000_0000, 64 << 20))
    board = EncoderBoard(link, image)           # src/sysone/v2/encoder_client.py

`registers` is where the block design puts kr260_encoder's AXI4-Lite slave
(rtl/v2/platform/kr260/kr260_encoder.sv; M_AXI_HPM0_FPD starts at 0xA000_0000);
`memory` is a region of the PS DDR4 that Linux leaves alone (a reserved-memory node
in the device tree, no-map) holding the image and the request area. Both are mapped
through /dev/mem with O_SYNC, i.e. uncached, which is what the PL's non-coherent
S_AXI_HP ports need. Needs root (or a UIO / u-dma-buf driver exposing the same).

Not yet run on hardware: the KR260 has not arrived. Simulated counterpart:
simulation/v2/kr260_encoder_tb.sv (`make kr260`).
"""

from __future__ import annotations

import mmap
import os
import struct
import time

from . import memory_protocol as mp

CONTROL, STATUS, ENCODER_CLOCKS, REQUEST_CLOCKS, STOPPED_AT, ID, BUILD = 0x00, 0x04, 0x08, 0x0C, 0x10, 0x14, 0x18
PROGRAM, SHAPE, IDS, RESULT = 0x20, 0x24, 0x28, 0x2C
ID_VALUE = 0x53595332            # "SYS2"


class Kr260Link:
    def __init__(self, registers: int = 0xA000_0000, memory: tuple[int, int] = (0x6000_0000, 64 << 20),
                 device: str = "/dev/mem"):
        self.fd = os.open(device, os.O_RDWR | os.O_SYNC)
        page = mmap.PAGESIZE
        self.reg_base = registers
        self.regs = mmap.mmap(self.fd, page, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE,
                              offset=registers)
        self.mem_base, self.mem_size = memory
        self.mem = mmap.mmap(self.fd, self.mem_size, mmap.MAP_SHARED,
                             mmap.PROT_READ | mmap.PROT_WRITE, offset=self.mem_base)
        if self._r(ID) != ID_VALUE:
            raise IOError(f"no kr260_encoder at {registers:#x} (ID reads {self._r(ID):#x})")
        b = self._r(BUILD)
        self.build = {"tile_out": b >> 24, "max_tokens": (b >> 16) & 0xFF,
                      "max_hidden": 16 * ((b >> 8) & 0xFF), "drain_lanes": b & 0xFF}

    def close(self) -> None:
        self.regs.close()
        self.mem.close()
        os.close(self.fd)

    def _r(self, offset: int) -> int:
        return struct.unpack_from("<I", self.regs, offset)[0]

    def _w(self, offset: int, value: int) -> None:
        struct.pack_into("<I", self.regs, offset, value & 0xFFFFFFFF)

    def _span(self, address: int, length: int) -> slice:
        off = address - self.mem_base
        if off < 0 or off + length > self.mem_size:
            raise ValueError(f"{address:#x}+{length} outside the reserved region")
        return slice(off, off + length)

    def write(self, address: int, data: bytes) -> None:
        self.mem[self._span(address, len(data))] = data

    def read(self, address: int, length: int) -> bytes:
        return bytes(self.mem[self._span(address, length)])

    def run(self, descriptor: bytes, timeout: float = 5.0) -> mp.RunResult:
        program, n, hidden, ids, result = struct.unpack("<IHHII", descriptor)
        if self._r(CONTROL) & 1:
            raise IOError("the encoder is busy")
        self._w(PROGRAM, program)
        self._w(SHAPE, (hidden << 16) | n)
        self._w(IDS, ids)
        self._w(RESULT, result)
        self._w(CONTROL, 1)
        t0 = time.perf_counter()
        while not self._r(CONTROL) & 2:
            if time.perf_counter() - t0 > timeout:
                raise TimeoutError("the encoder did not finish")
            time.sleep(0.0002)
        res = mp.RunResult(self._r(ENCODER_CLOCKS), self._r(REQUEST_CLOCKS), self._r(STATUS),
                           self._r(STOPPED_AT))
        self._w(CONTROL, 2)
        return res
