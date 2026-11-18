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

DDR and encoder operations passed hardware checks at 1/12/64/128 tokens on
2026-10-09. A Linux preflight now rejects an absent runtime before MMIO and the
client verifies DDR contents before RUN. These guards passed the 300-request
bert-mini hardware evaluation after recovery on 2026-10-09.
Simulated counterpart:
simulation/v2/kr260_encoder_tb.sv (`make kr260`).
"""

from __future__ import annotations

import mmap
import os
import struct
import time

from . import memory_protocol as mp
from .kr260_runtime import check_runtime

CONTROL, STATUS, ENCODER_CLOCKS, REQUEST_CLOCKS, STOPPED_AT, ID, BUILD = 0x00, 0x04, 0x08, 0x0C, 0x10, 0x14, 0x18
PROGRAM, SHAPE, IDS, RESULT = 0x20, 0x24, 0x28, 0x2C
ID_VALUE = 0x53595332            # "SYS2"


class Kr260Link:
    def __init__(self, registers: int = 0xA000_0000, memory: tuple[int, int] = (0x6000_0000, 64 << 20),
                 device: str = "/dev/mem"):
        page = mmap.PAGESIZE
        base, size = memory
        if registers < 0 or registers % page or base < 0 or base % page or size <= 0 or size % page:
            raise ValueError("registers and memory must be page-aligned, with a positive region size")
        if base + size > 1 << 32:
            raise ValueError("RUN descriptors address memory below 4 GiB")
        self.fd = None
        self.regs = self.mem = None
        self.reg_base = registers
        self.mem_base, self.mem_size = memory
        # The first MMIO read itself can stall a CPU if the PL slave is absent.
        # A Python polling timeout cannot recover that bus transaction.
        self.runtime = check_runtime(registers, memory)
        self.clock_hz = self.runtime["clock_hz"]
        try:
            self.fd = os.open(device, os.O_RDWR | os.O_SYNC)
            self.regs = mmap.mmap(self.fd, page, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE,
                                  offset=registers)
            ident = self._r(ID)
            if ident != ID_VALUE:
                raise IOError(f"no kr260_encoder at {registers:#x} (ID reads {ident:#x})")
            b = self._r(BUILD)
            if self.runtime.get("expected_build") is not None and b != self.runtime["expected_build"]:
                raise IOError(f"encoder BUILD {b:#x} differs from the loaded app profile")
            expected = self.runtime.get("expected_capabilities")
            if expected is not None and self._r(0x1C) != expected:
                raise IOError("encoder feature word differs from the loaded app profile; DDR not mapped")
            self.mem = mmap.mmap(self.fd, self.mem_size, mmap.MAP_SHARED,
                                 mmap.PROT_READ | mmap.PROT_WRITE, offset=self.mem_base)
        except Exception:
            self.close()
            raise
        self.build = {"tile_out": b >> 24, "max_tokens": (b >> 16) & 0xFF,
                      "max_hidden": 16 * ((b >> 8) & 0xFF), "drain_lanes": b & 0xFF}

    def close(self) -> None:
        for name in ("regs", "mem"):
            mapping = getattr(self, name)
            if mapping is not None:
                mapping.close()
                setattr(self, name, None)
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def _r(self, offset: int) -> int:
        return struct.unpack_from("<I", self.regs, offset)[0]

    def _w(self, offset: int, value: int) -> None:
        struct.pack_into("<I", self.regs, offset, value & 0xFFFFFFFF)

    def performance_counters(self) -> dict[str, int] | None:
        """Latest completed RUN diagnostics, or None for firmware without counters.

        Counts can overlap and wrap at 2**32; callers must serialize RUN/readout.
        These measurements do not establish a worst-case memory service bound.
        """
        capabilities = self._r(0x1C)
        known_layout = capabilities & 0xFFFFFF00 == 0x53590100 or capabilities in (0x535907FF, 0x53591FFF, 0x53597FFF, 0x535AFFFF, 0x5363FFFF, 0x5377FFFF)
        if not known_layout or not capabilities & 1:
            return None
        if self._r(CONTROL) & 1:
            raise RuntimeError("performance counters require an idle encoder")
        names = ("axi_read_beats", "axi_read_service_wait", "read_backpressure",
                 "linear_mac_issues", "attention_mac_issues", "linear_weight_wait",
                 "linear_drain_wait", "axi_write_beats", "axi_read_bursts", "result_source_wait")
        return {name: self._r(0x30 + 4 * i) for i, name in enumerate(names)}

    def _span(self, address: int, length: int) -> slice:
        off = address - self.mem_base
        if length < 0 or off < 0 or off + length > self.mem_size:
            raise ValueError(f"{address:#x}+{length} outside the reserved region")
        return slice(off, off + length)

    def validate_image(self, header: dict, image_bytes: int, layout) -> None:
        """Reject a mismatched image before writing any PS memory."""
        if header["tile_in"] != 16 or header["tile_out"] != self.build["tile_out"]:
            raise ValueError(f"image tile does not match KR260 BUILD {self.build}")
        if header["max_tokens"] > self.build["max_tokens"] or header["hidden"] > self.build["max_hidden"]:
            raise ValueError(f"image dimensions exceed KR260 BUILD {self.build}")
        if header.get("head_dim", 64) > 64 or header.get("ffn", 0) > 4 * self.build["max_hidden"]:
            raise ValueError(f"image attention/FFN dimensions exceed KR260 BUILD {self.build}")
        self._span(header["base"], image_bytes)
        self._span(layout.ids, (2 * layout.max_tokens + 15) // 16 * 16)
        self._span(layout.result, layout.max_tokens * layout.hidden)

    def write(self, address: int, data: bytes) -> None:
        self.mem[self._span(address, len(data))] = data

    def read(self, address: int, length: int) -> bytes:
        return bytes(self.mem[self._span(address, length)])

    def verify_loaded_image(self, address: int, image: bytes) -> None:
        """Refuse RUN when DDR lost its model after reboot or holds a different image."""
        if self.read(address, len(image)) != image:
            raise IOError("KR260 DDR image differs or is not loaded; run the client's load command before RUN")

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
