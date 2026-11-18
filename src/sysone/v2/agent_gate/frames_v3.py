"""Frame-level reference model of gate_core_v3.sv.

Parsing is `frames.GateModel` (verified against the v1 RTL) with three additions: IPv4 header and TCP checksum
verification, single-connection tracking (a frame from a new client port makes every pending write of the old
connection uncertain), and the v3 decision core (`gate_v3.V3Core`).  Frames are Ethernet frames without
preamble/FCS; direction 0 = agent side, 1 = plant side.
"""
from __future__ import annotations

import struct

from . import gate_v3 as V
from . import intspec as S
from .frames import (CAPTURE, CLASS_ARP, CLASS_OTHER, CLASS_OTHERFC, CLASS_READ, CLASS_RESP, CLASS_TCPCTL,
                     CLASS_WRITE, FCS_BAD, MALFORMED, NON_MODBUS)
from .gate_v2 import csum16

CSUM_BAD = 16
DENIED, DENIED_TTL_MS = 8, 10_000
ILLEGAL_FC, EXC_CODE = 0x7F, 0x03


def csum_update(hc: int, m: int, m2: int) -> int:
    """RFC 1624 eqn. 3: new checksum after a 16-bit word changes from m to m2."""
    x = (~hc & 0xFFFF) + (~m & 0xFFFF) + (m2 & 0xFFFF)
    x = (x & 0xFFFF) + (x >> 16)
    x = (x & 0xFFFF) + (x >> 16)
    return ~x & 0xFFFF


class GateV3Model:
    def __init__(self) -> None:
        self.core = V.V3Core()
        self.cur_conn = None
        self.order = 0
        self.den = [None] * DENIED           # (conn, txid, original fc, time)
        self.dptr = 0
        self.patch = None                    # description of the last frame's mutation, or None
        self.out = b""                       # frame as transmitted if it is transmitted

    # ------------------------------------------------------------ state signature (compared by the RTL testbench)
    def signature(self):
        c = self.core
        bits = lambda xs: sum(int(bool(x)) << i for i, x in enumerate(xs))
        return [c.lvl10 & 0xFFFF, int(c.lvl_ok), *[x & 0xFFFF for x in c.v0],
                *[(c.v1[r] if c.unc[r] else 0) & 0xFFFF for r in range(4)],
                bits(c.unc), bits(c.wild), sum(1 for p in c.pend if p), sum(1 for r in c.reads if r),
                len(c.starts), (c.starts[-1] if c.starts else 0), sum(1 for d in self.den if d)]

    def patch_fields(self):
        """[kind, new_fc, new_code, new_csum, off_fc, off_code, off_csum] (zeros when the frame is not patched)."""
        p = self.patch
        if not p:
            return [0, 0, 0, 0, 0, 0, 0]
        return [p["kind"], p["fc"], p["code"], p["csum"], p["off_fc"], p["off_code"], p["off_csum"]]

    # ------------------------------------------------------------ helpers
    def _lost(self, conn, t):
        self.core.on_conn_lost(conn, t)

    def process(self, direction: int, f: bytes, t_ms: int, fcs_ok: bool):
        """Return (forward, rule, class).  `self.patch` / `self.out` describe any mutation of the frame."""
        self.patch, self.out = None, f
        return self._process(direction, f, t_ms, fcs_ok)

    def _purge(self, tm):
        for k, d in enumerate(self.den):
            if d and ((tm - d[3]) & 0xFFFFFFFF) > DENIED_TTL_MS:
                self.den[k] = None

    def _mutate_request(self, f, sport, a, tm, t, p):
        """Refused request: illegal function code, same length, corrected checksum; remember it for the response."""
        key = next((k for k, d in enumerate(self.den) if d and d[0] == sport and d[1] == a["txid"]), None)
        if key is None:
            key = self.dptr
            self.dptr = (self.dptr + 1) % DENIED
        self.den[key] = (sport, a["txid"], a["fc"], tm)
        oc = struct.unpack("!H", f[t + 16:t + 18])[0]
        m = (f[p + 6] << 8) | f[p + 7]
        nc = csum_update(oc, m, (f[p + 6] << 8) | ILLEGAL_FC)
        b = bytearray(f)
        b[p + 7] = ILLEGAL_FC
        struct.pack_into("!H", b, t + 16, nc)
        self.out = bytes(b)
        self.patch = dict(kind=1, fc=ILLEGAL_FC, code=0, csum=nc, off_fc=p + 7, off_code=0, off_csum=t + 16)

    def _restore_response(self, f, k, t, p):
        ofc = self.den[k][2]
        self.den[k] = None
        oc = struct.unpack("!H", f[t + 16:t + 18])[0]
        nfc = ofc | 0x80
        nc = csum_update(oc, (f[p + 6] << 8) | f[p + 7], (f[p + 6] << 8) | nfc)
        nc = csum_update(nc, f[p + 8] << 8, EXC_CODE << 8)
        b = bytearray(f)
        b[p + 7] = nfc
        b[p + 8] = EXC_CODE
        struct.pack_into("!H", b, t + 16, nc)
        self.out = bytes(b)
        self.patch = dict(kind=2, fc=nfc, code=EXC_CODE, csum=nc, off_fc=p + 7, off_code=p + 8, off_csum=t + 16)

    def _process(self, direction: int, f: bytes, t_ms: int, fcs_ok: bool):
        if not fcs_ok:
            return False, FCS_BAD, CLASS_OTHER
        if len(f) < 14:
            return False, NON_MODBUS, CLASS_OTHER
        l3 = 14
        et = struct.unpack("!H", f[12:14])[0]
        if et == 0x8100:
            if len(f) < 18:
                return False, NON_MODBUS, CLASS_OTHER
            et = struct.unpack("!H", f[16:18])[0]
            l3 = 18
        if et == 0x0806:
            return True, S.PASS, CLASS_ARP
        if et != 0x0800 or len(f) < l3 + 20:
            return False, NON_MODBUS, CLASS_OTHER
        vihl = f[l3]
        ihl = vihl & 0xF
        if vihl >> 4 != 4 or ihl < 5:
            return False, MALFORMED, CLASS_OTHER
        total = struct.unpack("!H", f[l3 + 2:l3 + 4])[0]
        ff = struct.unpack("!H", f[l3 + 6:l3 + 8])[0]
        proto = f[l3 + 9]
        if ff & 0x3FFF:
            return False, MALFORMED, CLASS_OTHER
        if proto != 6:
            return False, NON_MODBUS, CLASS_OTHER
        t = l3 + 4 * ihl
        if len(f) < t + 20:
            return False, MALFORMED, CLASS_OTHER
        sport, dport = struct.unpack("!HH", f[t:t + 4])
        doff = f[t + 12] >> 4
        p = t + 4 * doff
        plen = total - 4 * ihl - 4 * doff
        if doff < 5 or plen < 0 or len(f) < p + plen:
            return False, MALFORMED, CLASS_OTHER
        # --- v3: checksums (IPv4 header; TCP over pseudo-header and the IP-delimited segment)
        tcp = f[t:l3 + total]
        pseudo = f[l3 + 12:l3 + 20] + struct.pack("!BBH", 0, 6, len(tcp))
        if csum16(f[l3:l3 + 4 * ihl]) != 0 or csum16(pseudo + tcp) != 0:
            return False, CSUM_BAD, CLASS_OTHER
        pl = f[p:p + plen]
        tm = t_ms & 0xFFFFFFFF
        self._purge(tm)
        if direction == 0:
            if dport != 502:
                return False, NON_MODBUS, CLASS_OTHER
            if self.cur_conn is not None and self.cur_conn != sport:
                self._lost(self.cur_conn, tm)
                self.den = [None if (d and d[0] == self.cur_conn) else d for d in self.den]
            self.cur_conn = sport
            if plen == 0:
                return True, S.PASS, CLASS_TCPCTL
            if plen < 8 or p + min(plen, 21) > CAPTURE:
                return False, MALFORMED, CLASS_OTHER
            txid, pid, mlen, unit, fc = struct.unpack("!HHHBB", pl[:8])
            if pid != 0 or mlen != plen - 6:
                return False, MALFORMED, CLASS_OTHER
            a = {"txid": txid, "unit": unit, "fc": fc, "pdu": pl[7:]}
            if fc in (3, 4):
                if plen != 12:
                    return False, MALFORMED, CLASS_OTHER
                self.order += 1
                self.core.on_forward(sport, a, tm, self.order)
                return True, S.PASS, CLASS_READ
            if fc == 6:
                if plen != 12:
                    return False, MALFORMED, CLASS_OTHER
            elif fc == 16:
                if plen < 13:
                    return False, MALFORMED, CLASS_OTHER
                addr, qty, bc = struct.unpack("!HHB", pl[8:13])
                if bc != 2 * qty or plen != 13 + bc:
                    return False, MALFORMED, CLASS_OTHER
            else:
                rule = self.core.decide(sport, a, tm)
                if rule != S.PASS:
                    self._mutate_request(f, sport, a, tm, t, p)
                return rule == S.PASS, rule, CLASS_OTHERFC
            rule = self.core.decide(sport, a, tm)
            if rule == S.PASS:
                self.order += 1
                self.core.on_forward(sport, a, tm, self.order)
            else:
                self._mutate_request(f, sport, a, tm, t, p)
            return rule == S.PASS, rule, CLASS_WRITE
        # direction 1: plant side
        if sport != 502:
            return False, NON_MODBUS, CLASS_OTHER
        if plen >= 8 and p + min(plen, 21) <= CAPTURE:
            txid, pid, mlen, unit, fc = struct.unpack("!HHHBB", pl[:8])
            if pid == 0 and mlen == plen - 6:
                k = next((i for i, d in enumerate(self.den) if d and d[0] == dport and d[1] == txid), None)
                if k is not None and fc == (ILLEGAL_FC | 0x80) and plen == 9:
                    self._restore_response(f, k, t, p)
                else:
                    self.core.on_response(dport, {"txid": txid, "unit": unit, "fc": fc, "pdu": pl[7:]}, tm)
        return True, S.PASS, CLASS_RESP
