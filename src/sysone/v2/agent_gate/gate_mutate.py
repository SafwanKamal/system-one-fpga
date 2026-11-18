"""Refusal by byte mutation: the stream-length-preserving alternative to TCP splicing.

A refused request is not removed from the client's byte stream.  Instead its Modbus function code is replaced by an
illegal value (0x7F) and the segment is forwarded with a corrected TCP checksum.  The PLC answers with an 'illegal
function' exception (every Modbus server must), and on the way back the gate restores the function code to the
client's original with the exception bit set and sets the exception code to 0x03.  Sequence and acknowledgement
numbers are never touched, nothing is injected, retransmissions behave like any other segment.

Cost: the PLC sees one illegal-function request per refused write, and the exception reaches the client after a PLC
round trip rather than immediately.
"""
from __future__ import annotations

import struct

from . import intspec as S
from .frames import FCS_BAD, MALFORMED, NON_MODBUS
from .gate_v2 import CSUM_BAD, csum16, parse, parse_adu

ILLEGAL_FC = 0x7F
EXC_CODE = 0x03
DENIED_TTL_MS = 10_000


def _set_tcp_csum(f: bytes, s) -> bytes:
    b = bytearray(f)
    struct.pack_into("!H", b, s.t + 16, 0)
    tcp = bytes(b[s.t:s.l3 + s.total])
    struct.pack_into("!H", b, s.t + 16, csum16(s.src + s.dst + struct.pack("!BBH", 0, 6, len(tcp)) + tcp))
    return bytes(b)


class MutateShell:
    def __init__(self, core):
        self.core = core
        self.cur_conn = None
        self.denied = {}            # (client port, txid) -> (original fc, time)
        self.order = 0
        self.counts = {}
        self.mutated = 0

    def _count(self, rule):
        self.counts[rule] = self.counts.get(rule, 0) + 1

    def process(self, direction: int, f: bytes, t: int, fcs_ok: bool = True):
        if not fcs_ok:
            return FCS_BAD, []
        s, err = parse(f)
        if err is not None:
            self._count(err)
            return err, []
        if not (s.ip_ok and s.tcp_ok):
            self._count(CSUM_BAD)
            return CSUM_BAD, []
        for k in [k for k, (_, ts) in self.denied.items() if ((t - ts) & 0xFFFFFFFF) > DENIED_TTL_MS]:
            del self.denied[k]
        if direction == 0:
            if s.dport != 502:
                return NON_MODBUS, []
            if self.cur_conn is not None and self.cur_conn != s.sport:
                self.core.on_conn_lost(self.cur_conn, t)
                for k in [k for k in self.denied if k[0] == self.cur_conn]:
                    del self.denied[k]
            self.cur_conn = s.sport
            if not s.payload:
                return S.PASS, [(1, f)]
            a = parse_adu(s.payload)
            if a is None:
                self._count(MALFORMED)
                return MALFORMED, []
            rule = self.core.decide(s.sport, a, t)
            self._count(rule)
            if rule == S.PASS:
                self.order += 1
                self.core.on_forward(s.sport, a, t, self.order)
                return rule, [(1, f)]
            # refused: same length, illegal function code, PLC will answer with an exception
            b = bytearray(f)
            b[s.t + s.doff + 7] = ILLEGAL_FC
            self.denied[(s.sport, a["txid"])] = (a["fc"], t)
            self.mutated += 1
            return rule, [(1, _set_tcp_csum(bytes(b), s))]
        if s.sport != 502:
            return NON_MODBUS, []
        if s.payload:
            a = parse_adu(s.payload)
            if a is not None:
                key = (s.dport, a["txid"])
                if key in self.denied and a["fc"] == (ILLEGAL_FC | 0x80) and len(s.payload) == 9:
                    orig_fc, _ = self.denied.pop(key)
                    b = bytearray(f)
                    b[s.t + s.doff + 7] = orig_fc | 0x80
                    b[s.t + s.doff + 8] = EXC_CODE
                    return S.PASS, [(0, _set_tcp_csum(bytes(b), s))]
                self.core.on_response(s.dport, a, t)
        return S.PASS, [(0, f)]

    def tick(self, t):
        self.core.tick(t)
