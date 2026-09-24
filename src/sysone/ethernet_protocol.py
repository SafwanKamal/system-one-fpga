"""Raw-Ethernet request/result protocol between a host and the board.

Same transport as Genome-Classifier's result packets: raw Ethernet II frames with
the IEEE local-experimental EtherType 0x88B5, a locally administered FPGA MAC
address, and a small versioned payload. No IP, UDP or ARP, so the FPGA side is a
MAC filter and a byte parser. Message types are distinct from Genome's
(MESSAGE_RESULT = 1) so both designs can share a host.

Request payload (host -> FPGA), big-endian:
    0      version            1
    1      message type       0x10 (classify request)
    2..5   sequence number    echoed in the result
    6..7   text length        bytes of text that follow (the rest is padding)
    8..    text               raw UTF-8; the board case-folds and tokenises it

Result payload (FPGA -> host), big-endian:
    0      version            1
    1      message type       0x11 (classify result)
    2..5   sequence number    from the request
    6      class              argmax, 0..150 (150 = out of scope)
    7      flags              bit 0: the message overflowed the 2 KiB word buffer
    8..9   feature count      table rows pooled (<= 256)
    10..11 top logit          int16
    12..13 second logit       int16
    14..   logits             151 x int16, class order

Probabilities on the host are softmax(logits * s_out); s_out is in the export
manifest. The temperature is already inside the integer logits.

This module is pure Python so the testbench vectors and the host tool
(scripts/sysone_ethernet_client.py) use exactly the same encoder and decoder.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

ETHERTYPE = 0x88B5
PROTOCOL_VERSION = 1
MESSAGE_CLASSIFY_REQUEST = 0x10
MESSAGE_CLASSIFY_RESULT = 0x11

FPGA_MAC = bytes.fromhex("020000000002")      # locally administered; Genome uses ...01
BROADCAST_MAC = bytes.fromhex("ffffffffffff")

CLASS_NUMBER = 151
REQUEST_HEADER_BYTES = 8
RESULT_HEADER_BYTES = 14
RESULT_PAYLOAD_BYTES = RESULT_HEADER_BYTES + 2 * CLASS_NUMBER
MAXIMUM_PAYLOAD_BYTES = 1500
MAXIMUM_TEXT_BYTES = MAXIMUM_PAYLOAD_BYTES - REQUEST_HEADER_BYTES
MINIMUM_FRAME_BYTES = 60                       # before the FCS


def mac_bytes(mac: str | bytes) -> bytes:
    if isinstance(mac, bytes):
        if len(mac) != 6:
            raise ValueError("a MAC address is 6 bytes")
        return mac
    parts = mac.replace("-", ":").split(":")
    if len(parts) != 6:
        raise ValueError(f"not a MAC address: {mac!r}")
    return bytes(int(p, 16) for p in parts)


def mac_string(mac: bytes) -> str:
    return ":".join(f"{b:02x}" for b in mac)


def frame_check_sequence(frame: bytes) -> bytes:
    """Ethernet FCS: CRC-32 (IEEE 802.3), transmitted least significant byte first."""
    return struct.pack("<I", zlib.crc32(frame) & 0xFFFFFFFF)


def build_frame(destination: bytes, source: bytes, payload: bytes, with_fcs: bool = True) -> bytes:
    """Ethernet II frame, padded to the 60-byte minimum, optionally with its FCS."""
    frame = destination + source + struct.pack(">H", ETHERTYPE) + payload
    if len(frame) < MINIMUM_FRAME_BYTES:
        frame += bytes(MINIMUM_FRAME_BYTES - len(frame))
    return frame + frame_check_sequence(frame) if with_fcs else frame


def encode_request_payload(text: str | bytes, sequence_number: int) -> bytes:
    data = text.encode("utf-8") if isinstance(text, str) else bytes(text)
    if len(data) > MAXIMUM_TEXT_BYTES:
        raise ValueError(f"text is {len(data)} bytes; at most {MAXIMUM_TEXT_BYTES} fit in one frame")
    return struct.pack(">BBIH", PROTOCOL_VERSION, MESSAGE_CLASSIFY_REQUEST,
                       sequence_number & 0xFFFFFFFF, len(data)) + data


def encode_request_frame(text: str | bytes, sequence_number: int, host_mac: str | bytes,
                         fpga_mac: str | bytes = FPGA_MAC, with_fcs: bool = True) -> bytes:
    return build_frame(mac_bytes(fpga_mac), mac_bytes(host_mac),
                       encode_request_payload(text, sequence_number), with_fcs)


@dataclass
class ClassifyResult:
    source_mac: str
    destination_mac: str
    sequence_number: int
    class_index: int
    overflow: bool
    feature_count: int
    top_logit: int
    second_logit: int
    logits: list[int]

    @property
    def margin(self) -> int:
        return self.top_logit - self.second_logit


class ProtocolError(ValueError):
    pass


def decode_result_frame(frame: bytes, has_fcs: bool = True) -> ClassifyResult:
    """Decode one FPGA result frame. Raises ProtocolError on anything malformed."""
    if has_fcs:
        if len(frame) < MINIMUM_FRAME_BYTES + 4:
            raise ProtocolError(f"frame too short: {len(frame)} bytes")
        body, fcs = frame[:-4], frame[-4:]
        if frame_check_sequence(body) != fcs:
            raise ProtocolError("bad frame check sequence")
    else:
        body = frame

    if len(body) < 14 + RESULT_PAYLOAD_BYTES:
        raise ProtocolError(f"result frame too short: {len(body)} bytes")
    destination, source = body[0:6], body[6:12]
    (ethertype,) = struct.unpack(">H", body[12:14])
    if ethertype != ETHERTYPE:
        raise ProtocolError(f"unexpected EtherType 0x{ethertype:04x}")

    payload = body[14:14 + RESULT_PAYLOAD_BYTES]
    version, message_type, sequence_number, class_index, flags, feature_count, top, second = \
        struct.unpack(">BBIBBHhh", payload[:RESULT_HEADER_BYTES])
    if version != PROTOCOL_VERSION:
        raise ProtocolError(f"unsupported protocol version {version}")
    if message_type != MESSAGE_CLASSIFY_RESULT:
        raise ProtocolError(f"unexpected message type 0x{message_type:02x}")
    if class_index >= CLASS_NUMBER:
        raise ProtocolError(f"class {class_index} out of range")
    if flags & ~0x01:
        raise ProtocolError(f"reserved flag bits set: 0x{flags:02x}")

    logits = list(struct.unpack(f">{CLASS_NUMBER}h", payload[RESULT_HEADER_BYTES:]))
    return ClassifyResult(source_mac=mac_string(source), destination_mac=mac_string(destination),
                          sequence_number=sequence_number, class_index=class_index,
                          overflow=bool(flags & 0x01), feature_count=feature_count,
                          top_logit=top, second_logit=second, logits=logits)
