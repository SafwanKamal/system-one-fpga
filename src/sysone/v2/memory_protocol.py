"""v2 memory link: read and write the board's external memory over raw Ethernet.

Used to load encoder weights into the DDR2 and to read anything back for checking.
Same EtherType as v1 (0x88B5); protocol version 2 tells the two apart.

Frame (Ethernet FCS added by the NIC / checked by the board, not part of this):

    0..5    destination MAC
    6..11   source MAC
    12..13  EtherType 0x88B5
    14      version 2
    15      type: 0x20 write, 0x21 write ack, 0x22 read, 0x23 read data
    16..19  sequence number, echoed
    20..23  byte address, big-endian, multiple of 16
    24..25  beats (16 bytes each), big-endian, 1..64 in a request; in an ack, the
            number of beats actually written
    26..    write: beats x 16 data bytes; read data: the same

Data bytes are in address order. Inside the board a beat is 128 bits with the byte
at the lowest address in bits [7:0] (AXI byte-lane order), so a file written here
reads back byte for byte on the KR260's ARM side as well.

A request the board cannot honour (unaligned address, 0 or more than 64 beats,
address outside its memory) is dropped and counted; the host notices the missing
reply. A write frame shorter than its beat count writes the whole beats it carries
and says so in the ack.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

ETHERTYPE = 0x88B5
VERSION = 2
WRITE, WRITE_ACK, READ, READ_DATA = 0x20, 0x21, 0x22, 0x23
BEAT_BYTES = 16
MAX_BEATS = 64
HEADER_BYTES = 26
FPGA_MAC = bytes.fromhex("020000000002")


class ProtocolError(ValueError):
    pass


@dataclass
class Message:
    kind: int
    sequence: int
    address: int
    beats: int
    data: bytes = b""
    source: bytes = b""


def fcs(frame: bytes) -> bytes:
    return struct.pack("<I", zlib.crc32(frame) & 0xFFFFFFFF)


def encode(kind: int, sequence: int, address: int, beats: int, data: bytes, src: bytes,
           dst: bytes = FPGA_MAC, with_fcs: bool = True) -> bytes:
    frame = (dst + src + struct.pack(">HBBIIH", ETHERTYPE, VERSION, kind, sequence & 0xFFFFFFFF,
                                     address, beats) + data)
    if len(frame) < 60:
        frame += bytes(60 - len(frame))
    return frame + fcs(frame) if with_fcs else frame


def write_frame(sequence: int, address: int, data: bytes, src: bytes, **kw) -> bytes:
    if len(data) % BEAT_BYTES or not 0 < len(data) <= MAX_BEATS * BEAT_BYTES:
        raise ProtocolError("write data must be 1..64 whole beats")
    return encode(WRITE, sequence, address, len(data) // BEAT_BYTES, data, src, **kw)


def read_frame(sequence: int, address: int, beats: int, src: bytes, **kw) -> bytes:
    return encode(READ, sequence, address, beats, b"", src, **kw)


def decode(frame: bytes, has_fcs: bool = True) -> Message:
    if has_fcs:
        if len(frame) < 64 or fcs(frame[:-4]) != frame[-4:]:
            raise ProtocolError("bad FCS")
        frame = frame[:-4]
    if len(frame) < HEADER_BYTES:
        raise ProtocolError("short frame")
    ethertype, version, kind, seq, address, beats = struct.unpack(">HBBIIH", frame[12:HEADER_BYTES])
    if ethertype != ETHERTYPE or version != VERSION:
        raise ProtocolError("not a v2 memory frame")
    data = b""
    if kind in (WRITE, READ_DATA):
        data = frame[HEADER_BYTES:HEADER_BYTES + beats * BEAT_BYTES]
        if len(data) != beats * BEAT_BYTES:
            raise ProtocolError("frame shorter than its beat count")
    return Message(kind, seq, address, beats, data, frame[6:12])
