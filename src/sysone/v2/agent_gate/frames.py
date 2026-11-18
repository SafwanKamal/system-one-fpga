"""Frame-level reference model of the gate core (what rtl/v2/gate/gate_core.sv implements)
and a Modbus/TCP traffic generator.

Frames are Ethernet frames without preamble/SFD/FCS (the MAC strips them and reports
fcs_ok).  Direction 0 = from the agent-side port (A), 1 = from the plant-side port (B).

Frame policy (phase 1):
  bad FCS                          -> drop  (FCS_BAD)
  ARP (either direction)           -> forward
  IPv4 fragment (MF or offset != 0)-> drop  (MALFORMED)
  A: TCP dst 502, empty payload    -> forward (TCP control)
  A: TCP dst 502, Modbus ADU       -> must be one well-formed ADU, else drop (MALFORMED);
                                      reads FC3/FC4 forward and are recorded by txid;
                                      everything else goes through intspec.decide()
  B: TCP src 502                   -> forward; a matching FC4 response updates level
  anything else                    -> drop  (NON_MODBUS)
"""
from __future__ import annotations

import random
import struct

from . import intspec as S

MALFORMED, NON_MODBUS, FCS_BAD = 13, 14, 15
CAPTURE = 128   # the core inspects only the first 128 bytes; Modbus fields beyond -> MALFORMED
CLASS_OTHER, CLASS_ARP, CLASS_TCPCTL, CLASS_READ, CLASS_WRITE, CLASS_RESP, CLASS_OTHERFC = 0, 1, 2, 3, 4, 5, 6

MAC_A = bytes.fromhex("02000000000a")
MAC_B = bytes.fromhex("02000000000b")
IP_A = bytes([192, 168, 50, 10])
IP_B = bytes([192, 168, 50, 20])


def _csum(b: bytes) -> int:
    if len(b) % 2:
        b += b"\0"
    s = sum(struct.unpack(f"!{len(b)//2}H", b))
    while s >> 16:
        s = (s & 0xFFFF) + (s >> 16)
    return (~s) & 0xFFFF


def tcp_frame(direction: int, payload: bytes, vlan: bool = False, frag: bool = False,
              sport: int | None = None, dport: int | None = None, proto: int = 6) -> bytes:
    src_mac, dst_mac = (MAC_A, MAC_B) if direction == 0 else (MAC_B, MAC_A)
    src_ip, dst_ip = (IP_A, IP_B) if direction == 0 else (IP_B, IP_A)
    if sport is None:
        sport = 40000 if direction == 0 else 502
    if dport is None:
        dport = 502 if direction == 0 else 40000
    tcp = struct.pack("!HHIIBBHHH", sport, dport, 1000, 2000, 5 << 4, 0x18, 8192, 0, 0) + payload
    pseudo = src_ip + dst_ip + struct.pack("!BBH", 0, proto, len(tcp))
    tcp = tcp[:16] + struct.pack("!H", _csum(pseudo + tcp)) + tcp[18:]
    flags_frag = 0x2000 if frag else 0x4000
    ip = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(tcp), 1, flags_frag, 64, proto, 0, src_ip, dst_ip)
    ip = ip[:10] + struct.pack("!H", _csum(ip)) + ip[12:]
    eth = dst_mac + src_mac + ((b"\x81\x00" + struct.pack("!H", 5)) if vlan else b"") + b"\x08\x00"
    f = eth + ip + tcp
    return f + b"\0" * max(0, 60 - len(f))


def arp_frame(direction: int) -> bytes:
    src = MAC_A if direction == 0 else MAC_B
    body = struct.pack("!HHBBH", 1, 0x0800, 6, 4, 1) + src + (IP_A if direction == 0 else IP_B) + b"\0" * 6 + (IP_B if direction == 0 else IP_A)
    f = b"\xff" * 6 + src + b"\x08\x06" + body
    return f + b"\0" * (60 - len(f))


def mbap(txid: int, pdu: bytes, unit: int = 1, length_adjust: int = 0) -> bytes:
    return struct.pack("!HHHB", txid & 0xFFFF, 0, len(pdu) + 1 + length_adjust, unit) + pdu


def pdu_read(fc: int, start: int, qty: int) -> bytes:
    return struct.pack("!BHH", fc, start, qty)


def pdu_write6(addr: int, value: int) -> bytes:
    return struct.pack("!BHH", 6, addr & 0xFFFF, value & 0xFFFF)


def pdu_write16(addr: int, values: list[int], bytecount_adjust: int = 0) -> bytes:
    return struct.pack("!BHHB", 16, addr & 0xFFFF, len(values), 2 * len(values) + bytecount_adjust) + \
        b"".join(struct.pack("!H", v & 0xFFFF) for v in values)


def pdu_read_resp(fc: int, regs: list[int]) -> bytes:
    return struct.pack("!BB", fc, 2 * len(regs)) + b"".join(struct.pack("!H", r & 0xFFFF) for r in regs)


# ------------------------------------------------------------------ reference model

class GateModel:
    def __init__(self) -> None:
        self.lvl10 = 500
        self.act = [0, 0, 0, 0]
        self.starts: list[int] = []
        self.table = [None] * 4      # (txid, fc, start, qty)
        self.ptr = 0

    def _starts_padded(self):
        return self.starts + [S.NO_START] * (4 - len(self.starts))

    def process(self, direction: int, f: bytes, t_ms: int, fcs_ok: bool):
        """Return (forward, rule, cls)."""
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
        pl = f[p:p + plen]
        if direction == 0:
            if dport != 502:
                return False, NON_MODBUS, CLASS_OTHER
            if plen == 0:
                return True, S.PASS, CLASS_TCPCTL
            if plen < 8 or p + min(plen, 21) > CAPTURE:
                return False, MALFORMED, CLASS_OTHER
            txid, pid, mlen, unit, fc = struct.unpack("!HHHBB", pl[:8])
            if pid != 0 or mlen != plen - 6:
                return False, MALFORMED, CLASS_OTHER
            if fc in (3, 4):
                if plen != 12:
                    return False, MALFORMED, CLASS_OTHER
                start, qty = struct.unpack("!HH", pl[8:12])
                self.table[self.ptr] = (txid, fc, start, qty)
                self.ptr = (self.ptr + 1) % 4
                return True, S.PASS, CLASS_READ
            if fc == 6:
                if plen != 12:
                    return False, MALFORMED, CLASS_OTHER
                addr, v = struct.unpack("!HH", pl[8:12])
                vals, n_over = [v], False
            elif fc == 16:
                if plen < 13:
                    return False, MALFORMED, CLASS_OTHER
                addr, qty, bc = struct.unpack("!HHB", pl[8:13])
                if bc != 2 * qty or plen != 13 + bc:
                    return False, MALFORMED, CLASS_OTHER
                vals = [struct.unpack("!H", pl[13 + 2 * i:15 + 2 * i])[0] for i in range(min(qty, 4))]
                n_over = qty > 4
            else:
                rule = S.decide(fc, 0, [], self.lvl10, self.act, t_ms, self._starts_padded())
                return rule == S.PASS, rule, CLASS_OTHERFC
            rule = S.UNMAPPED if n_over else S.decide(fc, addr, vals, self.lvl10, self.act, t_ms,
                                                      self._starts_padded())
            if rule == S.PASS:
                old_pump = self.act[S.PUMP]
                for i, v in enumerate(vals):
                    self.act[addr + i] = v
                if old_pump == 0 and self.act[S.PUMP] > 0:
                    self.starts = (self.starts + [t_ms])[-4:]
            return rule == S.PASS, rule, CLASS_WRITE
        # direction 1: plant side
        if sport != 502:
            return False, NON_MODBUS, CLASS_OTHER
        if plen >= 11 and p + 11 <= CAPTURE:
            txid, pid, mlen, unit, fc, bc = struct.unpack("!HHHBBB", pl[:9])
            if fc == 4 and pid == 0 and mlen == plen - 6 and bc >= 2 and plen >= 11:
                for i, e in enumerate(self.table):
                    if e and e[0] == txid and e[1] == 4:
                        if e[2] == 0 and e[3] >= 1:
                            r0 = struct.unpack("!H", pl[9:11])[0]
                            self.lvl10 = r0 - 0x10000 if r0 & 0x8000 else r0
                        self.table[i] = None
                        break
        return True, S.PASS, CLASS_RESP


# ------------------------------------------------------------------ traffic from episodes

def episode_traffic(records: list[dict], rng: random.Random):
    """Yield (direction, frame, t_ms, fcs_ok) replaying recorded agent/operator writes,
    each preceded by an FC4 poll and its response; interleaves edge-case frames."""
    txid = 1
    for r in records:
        t_ms = int(round(r["view"]["t"] * 1000)) & 0xFFFFFFFF
        obs = r["view"]["obs"]
        regs = [int(round(obs["level"] * 10)), int(round(obs["temperature"] * 10)),
                int(round(obs["pressure"] * 100)), int(round(obs["flow"] * 100))]
        vlan = rng.random() < 0.1
        yield 0, tcp_frame(0, mbap(txid, pdu_read(4, 0, 4)), vlan=vlan), t_ms, True
        yield 1, tcp_frame(1, mbap(txid, pdu_read_resp(4, regs)), vlan=vlan), t_ms, True
        txid += 1
        q = r["req"]
        vals = [S.u16(v) for v in q["values"]]
        if q["fc"] == 6 and len(vals) == 1:
            pdu = pdu_write6(q["addr"], vals[0])
        elif q["fc"] in (6, 16):
            pdu = pdu_write16(q["addr"], vals)
        else:
            pdu = struct.pack("!BHH", q["fc"] & 0xFF, q["addr"] & 0xFFFF, vals[0] if vals else 0)
        yield 0, tcp_frame(0, mbap(txid, pdu), vlan=vlan), t_ms, True
        txid += 1
        if rng.random() < 0.08:
            yield from edge_frames(rng, txid, t_ms)
            txid += 10


def edge_frames(rng: random.Random, txid: int, t_ms: int):
    yield 0, arp_frame(0), t_ms, True
    yield 1, arp_frame(1), t_ms, True
    yield 0, tcp_frame(0, b""), t_ms, True                                   # pure ACK
    yield 0, tcp_frame(0, mbap(txid, pdu_write6(1, 50))), t_ms, False         # bad FCS
    yield 0, tcp_frame(0, mbap(txid, pdu_write6(1, 50)), frag=True), t_ms, True
    yield 0, tcp_frame(0, mbap(txid, pdu_write6(1, 50), length_adjust=3)), t_ms, True
    yield 0, tcp_frame(0, mbap(txid, pdu_write16(0, [10, 20], bytecount_adjust=2))), t_ms, True
    yield 0, tcp_frame(0, mbap(txid, pdu_write16(0, [1, 2, 3, 4, 5]))), t_ms, True
    yield 0, tcp_frame(0, mbap(txid, pdu_write6(1, 50)) + mbap(txid + 1, pdu_write6(2, 0))), t_ms, True
    yield 0, tcp_frame(0, mbap(txid, pdu_write6(1, 50)), dport=503), t_ms, True
    yield 0, tcp_frame(0, b"\x00" * 20, proto=17, dport=502), t_ms, True     # UDP
    yield 0, tcp_frame(0, mbap(txid, struct.pack("!BHH", 5, 0, 0xFF00))), t_ms, True  # FC5 coil
    yield 0, tcp_frame(0, mbap(txid, struct.pack("!B", 8) + b"\0\0\0\0")), t_ms, True  # FC8
    yield 1, tcp_frame(1, mbap(txid + 5, pdu_read_resp(4, [999, 0, 0, 0]))), t_ms, True  # unsolicited resp
    yield 1, tcp_frame(1, b"", sport=80), t_ms, True                          # non-502 from plant
