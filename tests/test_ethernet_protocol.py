"""Checks for src/sysone/ethernet_protocol.py.

The FCS residue test pins the constant ethernet_RX compares against: CRC-32 over a
frame and its own FCS is always 0x2144DF1C after the final complement.
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sysone import ethernet_protocol as ep      # noqa: E402

HOST = "02:00:00:00:00:aa"


def test_crc_check_value():
    # the standard CRC-32 check value
    assert zlib.crc32(b"123456789") == 0xCBF43926


def test_fcs_residue_matches_rtl_constant():
    for text in [b"", b"x", b"what is my credit score", bytes(range(256))]:
        frame = ep.encode_request_frame(text, 7, HOST)
        assert zlib.crc32(frame) == 0x2144DF1C


def test_request_layout():
    frame = ep.encode_request_frame("book a flight", 0x01020304, HOST, with_fcs=False)
    assert frame[0:6] == ep.FPGA_MAC
    assert frame[6:12] == ep.mac_bytes(HOST)
    assert frame[12:14] == b"\x88\xb5"
    assert frame[14:22] == bytes([1, 0x10, 1, 2, 3, 4, 0, 13])
    assert frame[22:35] == b"book a flight"
    assert len(frame) == 60                     # padded to the minimum


def test_result_round_trip():
    logits = [(-1) ** k * (37 * k) for k in range(ep.CLASS_NUMBER)]
    payload = struct.pack(">BBIBBHhh", 1, 0x11, 99, 42, 1, 96, 5402, 5328)
    payload += struct.pack(f">{ep.CLASS_NUMBER}h", *logits)
    frame = ep.build_frame(ep.mac_bytes(HOST), ep.FPGA_MAC, payload)
    result = ep.decode_result_frame(frame)
    assert result.sequence_number == 99 and result.class_index == 42
    assert result.overflow and result.feature_count == 96
    assert result.margin == 74 and result.logits == logits


def test_bad_fcs_is_rejected():
    payload = struct.pack(">BBIBBHhh", 1, 0x11, 1, 0, 0, 1, 0, 0) + bytes(2 * ep.CLASS_NUMBER)
    frame = bytearray(ep.build_frame(ep.mac_bytes(HOST), ep.FPGA_MAC, payload))
    frame[20] ^= 0x80
    try:
        ep.decode_result_frame(bytes(frame))
    except ep.ProtocolError:
        return
    raise AssertionError("corrupted frame was accepted")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
