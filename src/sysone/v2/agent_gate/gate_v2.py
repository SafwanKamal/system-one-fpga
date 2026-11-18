"""Gate v2 reference: enforcement under uncertain command acceptance and stale observations.

v1 (frames.GateModel, rtl/v2/gate/gate_core.sv) assumes every write it forwards was applied
and uses the last level reading regardless of age.  It also never checks IPv4/TCP
checksums, so a write the PLC's TCP stack discards still updates the gate's state.

This module separates two layers so the alternatives can be compared on the same traffic:

GateShell  - Modbus/TCP transport handling for one agent<->PLC path:
             * optional IPv4 header + TCP checksum verification,
             * optional per-connection sequence tracking (retransmissions are re-forwarded
               without a second decision; out-of-window segments are dropped),
             * what happens to a blocked request: "drop" (what v1 does; the PLC's TCP stream
               then has a hole and the session wedges until the client reconnects) or
               "splice" (remove the request from the client->PLC byte stream, inject a Modbus
               exception 0x03 to the client and rewrite seq/ack numbers so both TCP stacks
               stay consistent).
Cores      - the decision state:
             * NoneCore            forward everything
             * CommitOnForwardCore v1 semantics (state updated when a write is forwarded)
             * ReadbackCore        state only from FC3/FC4 read responses (a state-invariant
                                   gate that does not track commands; SAIN-style approximation)
             * AcceptanceCore      v2: a write is *pending* until the PLC's matching echo;
                                   an exception discards it; a timeout or lost connection
                                   makes the register *uncertain* ({old, new}); FC3 readback
                                   resolves uncertainty; the level is an interval that widens
                                   with observation age at the plant's worst-case rates; a
                                   write passes only if intspec.decide() passes for every
                                   possible actuator state and both level bounds.

Frames are Ethernet II frames without preamble/FCS, one Modbus ADU per TCP segment
(as v1).  Direction 0 = agent side, 1 = plant side.
"""
from __future__ import annotations

import itertools
import struct

from . import intspec as S
from .frames import FCS_BAD, MALFORMED, NON_MODBUS

CSUM_BAD, TCP_OOW, PENDING_FULL = 16, 17, 18
NAMES = dict(S.NAMES)
NAMES.update({13: "malformed", 14: "non_modbus", 15: "fcs_bad", 16: "checksum_bad",
              17: "tcp_out_of_window", 18: "pending_table_full", 19: "state_unknown",
              20: "interlock_active"})

FORWARD, DROP, DENY = "forward", "drop", "deny"
EXC_CODE = 0x03

# worst-case level rates from the configurator's spec ranges (plant.SPEC), in level*10 per s
RISE_MAX = 10 * 2.4 / 0.8      # fin_max_hi / area_lo
FALL_MAX = 10 * 2.5 / 0.8      # kq_hi / area_lo
T_ACK_MS = 2000
PENDING_CAP = 8


# ------------------------------------------------------------------ frame helpers

def csum16(b: bytes) -> int:
    if len(b) % 2:
        b += b"\0"
    s = sum(struct.unpack(f"!{len(b) // 2}H", b))
    while s >> 16:
        s = (s & 0xFFFF) + (s >> 16)
    return (~s) & 0xFFFF


class Seg:
    """Parsed IPv4/TCP segment (fields needed by the gate)."""
    __slots__ = ("l3", "ihl", "t", "doff", "src", "dst", "sport", "dport", "seq", "ack", "flags",
                 "payload", "total", "ip_ok", "tcp_ok")


def parse(f: bytes):
    """Return (Seg, None) or (None, rule)."""
    if len(f) < 14:
        return None, NON_MODBUS
    et = struct.unpack("!H", f[12:14])[0]
    l3 = 14
    if et == 0x8100:
        if len(f) < 18:
            return None, NON_MODBUS
        et, l3 = struct.unpack("!H", f[16:18])[0], 18
    if et != 0x0800 or len(f) < l3 + 20:
        return None, NON_MODBUS
    vihl = f[l3]
    if vihl >> 4 != 4 or (vihl & 15) < 5:
        return None, MALFORMED
    s = Seg()
    s.l3, s.ihl = l3, 4 * (vihl & 15)
    s.total = struct.unpack("!H", f[l3 + 2:l3 + 4])[0]
    if struct.unpack("!H", f[l3 + 6:l3 + 8])[0] & 0x3FFF:
        return None, MALFORMED
    if f[l3 + 9] != 6:
        return None, NON_MODBUS
    if s.total < s.ihl + 20 or len(f) < l3 + s.total:
        return None, MALFORMED
    s.t = l3 + s.ihl
    s.src, s.dst = f[l3 + 12:l3 + 16], f[l3 + 16:l3 + 20]
    s.sport, s.dport, s.seq, s.ack = struct.unpack("!HHII", f[s.t:s.t + 12])
    s.doff = 4 * (f[s.t + 12] >> 4)
    s.flags = f[s.t + 13]
    if s.doff < 20 or s.ihl + s.doff > s.total:
        return None, MALFORMED
    s.payload = f[s.t + s.doff:l3 + s.total]
    s.ip_ok = csum16(f[l3:l3 + s.ihl]) == 0
    tcp = f[s.t:l3 + s.total]
    s.tcp_ok = csum16(s.src + s.dst + struct.pack("!BBH", 0, 6, len(tcp)) + tcp) == 0
    return s, None


def build(eth_hdr: bytes, src: bytes, dst: bytes, sport: int, dport: int, seq: int, ack: int,
          payload: bytes, flags: int = 0x18, ip_id: int = 1, corrupt_tcp: bool = False) -> bytes:
    tcp = struct.pack("!HHIIBBHHH", sport, dport, seq & 0xFFFFFFFF, ack & 0xFFFFFFFF, 5 << 4, flags,
                      8192, 0, 0) + payload
    c = csum16(src + dst + struct.pack("!BBH", 0, 6, len(tcp)) + tcp)
    if corrupt_tcp:
        c ^= 0x5A5A
    tcp = tcp[:16] + struct.pack("!H", c) + tcp[18:]
    ip = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(tcp), ip_id & 0xFFFF, 0x4000, 64, 6, 0, src, dst)
    ip = ip[:10] + struct.pack("!H", csum16(ip)) + ip[12:]
    f = eth_hdr + ip + tcp
    return f + b"\0" * max(0, 60 - len(f))


def rewrite(f: bytes, s: Seg, seq: int, ack: int) -> bytes:
    """Same frame with new seq/ack and a recomputed TCP checksum (the RTL can do this
    incrementally, RFC 1624)."""
    b = bytearray(f)
    struct.pack_into("!II", b, s.t + 4, seq & 0xFFFFFFFF, ack & 0xFFFFFFFF)
    struct.pack_into("!H", b, s.t + 16, 0)
    tcp = bytes(b[s.t:s.l3 + s.total])
    struct.pack_into("!H", b, s.t + 16, csum16(s.src + s.dst + struct.pack("!BBH", 0, 6, len(tcp)) + tcp))
    return bytes(b)


def parse_adu(pl: bytes):
    """Return dict for exactly one well-formed ADU, or None."""
    if len(pl) < 8:
        return None
    txid, pid, mlen, unit, fc = struct.unpack("!HHHBB", pl[:8])
    if pid != 0 or mlen != len(pl) - 6:
        return None
    a = {"txid": txid, "unit": unit, "fc": fc, "pdu": pl[7:]}
    return a


# ------------------------------------------------------------------ decision cores

class NoneCore:
    name = "none"

    def decide(self, conn, a, t):
        return S.PASS

    def on_forward(self, conn, a, t, order):
        pass

    def on_response(self, conn, a, t):
        pass

    def on_conn_lost(self, conn, t):
        pass

    def tick(self, t):
        pass

    def uncertain(self):
        return False


def _write_fields(a):
    """(addr, vals, over) for FC6/FC16 requests, or None if malformed."""
    pdu = a["pdu"]
    if a["fc"] == 6:
        if len(pdu) != 5:
            return None
        addr, v = struct.unpack("!HH", pdu[1:5])
        return addr, [v], False
    if a["fc"] == 16:
        if len(pdu) < 6:
            return None
        addr, qty, bc = struct.unpack("!HHB", pdu[1:6])
        if bc != 2 * qty or len(pdu) != 6 + bc:
            return None
        return addr, [struct.unpack("!H", pdu[6 + 2 * i:8 + 2 * i])[0] for i in range(min(qty, 4))], qty > 4
    return None


def _read_fields(a):
    pdu = a["pdu"]
    if a["fc"] in (3, 4) and len(pdu) == 5:
        return struct.unpack("!HH", pdu[1:5])
    return None


class _ReadTracking:
    """Shared FC3/FC4 request->response matching (by connection and txid)."""

    def __init__(self):
        self.reads = {}            # (conn, txid) -> (fc, start, qty, order)

    def note_read(self, conn, a, order):
        rf = _read_fields(a)
        if rf:
            self.reads[(conn, a["txid"])] = (a["fc"], rf[0], rf[1], order)

    def match_read(self, conn, a):
        """Return (fc, start, regs, order) for a read response, else None."""
        key = (conn, a["txid"])
        if key not in self.reads or a["fc"] not in (3, 4):
            return None
        fc, start, qty, order = self.reads.pop(key)
        pdu = a["pdu"]
        if len(pdu) < 2 or pdu[1] != 2 * qty or len(pdu) != 2 + 2 * qty:
            return None
        regs = [struct.unpack("!H", pdu[2 + 2 * i:4 + 2 * i])[0] for i in range(qty)]
        return fc, start, regs, order

    def drop_conn(self, conn):
        for k in [k for k in self.reads if k[0] == conn]:
            del self.reads[k]


def _signed(r):
    return r - 0x10000 if r & 0x8000 else r


class CommitOnForwardCore(_ReadTracking):
    """v1: what the RTL implements (state committed when a write is forwarded)."""
    name = "commit_on_forward"

    def __init__(self):
        super().__init__()
        self.lvl10, self.act, self.starts = 500, [0, 0, 0, 0], []

    def _starts(self):
        return (self.starts + [S.NO_START] * 4)[:4]

    def decide(self, conn, a, t):
        fc = a["fc"]
        if fc in (3, 4) or fc not in (6, 16):
            return S.decide(fc, 0, [], self.lvl10, self.act, t, self._starts())
        w = _write_fields(a)
        if w is None:
            return MALFORMED
        addr, vals, over = w
        return S.UNMAPPED if over else S.decide(fc, addr, vals, self.lvl10, self.act, t, self._starts())

    def on_forward(self, conn, a, t, order):
        if a["fc"] in (3, 4):
            self.note_read(conn, a, order)
            return
        w = _write_fields(a)
        if w:
            old = self.act[S.PUMP]
            for i, v in enumerate(w[1]):
                self.act[w[0] + i] = v
            if old == 0 and self.act[S.PUMP] > 0:
                self.starts = (self.starts + [t])[-4:]

    def on_response(self, conn, a, t):
        r = self.match_read(conn, a)
        if r and r[0] == 4 and r[1] == 0:
            self.lvl10 = _signed(r[2][0])

    def on_conn_lost(self, conn, t):
        self.drop_conn(conn)

    def tick(self, t):
        pass

    def uncertain(self):
        return False

    def possible_values(self):
        return [{x} for x in self.act]


class ReadbackCore(CommitOnForwardCore):
    """State only from read responses: actuators from FC3, level from FC4."""
    name = "readback_only"

    def on_forward(self, conn, a, t, order):
        if a["fc"] in (3, 4):
            self.note_read(conn, a, order)

    def on_response(self, conn, a, t):
        r = self.match_read(conn, a)
        if not r:
            return
        fc, start, regs, _ = r
        if fc == 4 and start == 0:
            self.lvl10 = _signed(regs[0])
        if fc == 3:
            for i, v in enumerate(regs):
                if start + i < 4:
                    if start + i == S.PUMP and self.act[S.PUMP] == 0 and v > 0:
                        self.starts = (self.starts + [t])[-4:]
                    self.act[start + i] = v


class ReadbackProvCore(ReadbackCore):
    """Read-back state plus provisional commit: a forwarded write is assumed applied (as in v1) until
    the next FC3 response overwrites it.  Isolates the 'a read-back gate cannot see its own writes'
    mechanism from the rest of acceptance tracking (no echo matching, no uncertainty, no level interval)."""
    name = "readback_provisional"

    def on_forward(self, conn, a, t, order):
        if a["fc"] in (3, 4):
            self.note_read(conn, a, order)
        else:
            CommitOnForwardCore.on_forward(self, conn, a, t, order)


class AcceptanceCore(_ReadTracking):
    """v2: acceptance-tracked actuator state, age-aware level interval, worst-case decisions."""
    name = "acceptance"

    def __init__(self, t_ack_ms: int = T_ACK_MS, cap: int = PENDING_CAP):
        super().__init__()
        self.t_ack, self.cap = t_ack_ms, cap
        self.known = [{0}, {0}, {0}, {0}]     # possible committed values per register
        self.pending = {}                     # (conn, txid) -> dict(addr, vals, t, order, start)
        self.lvl10, self.lvl_t = None, None
        self.starts = []                      # confirmed pump-start times
        self.uncertain_starts = []            # starts that may have happened
        self.unc_since = None

    # possible states ------------------------------------------------
    def possible(self):
        P = [set(k) for k in self.known]
        for p in self.pending.values():
            for i, v in enumerate(p["vals"]):
                P[p["addr"] + i].add(v)
        return P

    def level_bounds(self, t, P):
        if self.lvl10 is None:
            return 0, 1000
        age = max(0, (t - self.lvl_t)) / 1000.0
        rise = max(P[S.INLET]) / 100.0 * RISE_MAX
        fall = max(P[S.PUMP]) / 100.0 * (max(P[S.OUTLET]) / 100.0) ** 0.5 * FALL_MAX
        return max(-100, int(self.lvl10 - fall * age)), min(1100, int(self.lvl10 + rise * age + 0.999))

    def _starts(self):
        s = sorted(self.starts + self.uncertain_starts +
                   [p["t"] for p in self.pending.values() if p["start"]])[-4:]
        return s + [S.NO_START] * (4 - len(s))

    def decide(self, conn, a, t):
        fc = a["fc"]
        if fc in (3, 4) or fc not in (6, 16):
            return S.decide(fc, 0, [], 0, [0, 0, 0, 0], t, self._starts())
        w = _write_fields(a)
        if w is None:
            return MALFORMED
        addr, vals, over = w
        if over:
            return S.UNMAPPED
        if len(self.pending) >= self.cap:
            return PENDING_FULL
        P = self.possible()
        lo, hi = self.level_bounds(t, P)
        st = self._starts()
        for act in itertools.product(*[sorted(x) for x in P]):
            for lvl in (lo, hi):
                r = S.decide(fc, addr, vals, lvl, list(act), t, st)
                if r != S.PASS:
                    return r
        return S.PASS

    def on_forward(self, conn, a, t, order):
        if a["fc"] in (3, 4):
            self.note_read(conn, a, order)
            return
        w = _write_fields(a)
        if w:
            addr, vals, _ = w
            start = S.PUMP in range(addr, addr + len(vals)) and vals[S.PUMP - addr] > 0 and \
                0 in self.possible()[S.PUMP]
            self.pending[(conn, a["txid"])] = dict(addr=addr, vals=vals, t=t, order=order, start=start)

    def _commit(self, p, t):
        for i, v in enumerate(p["vals"]):
            self.known[p["addr"] + i] = {v}
        if p["start"]:
            self.starts = (self.starts + [p["t"]])[-4:]

    def _make_uncertain(self, p):
        for i, v in enumerate(p["vals"]):
            self.known[p["addr"] + i].add(v)
        if p["start"]:
            self.uncertain_starts = (self.uncertain_starts + [p["t"]])[-4:]

    def on_response(self, conn, a, t):
        key = (conn, a["txid"])
        if key in self.pending:
            p = self.pending.pop(key)
            fc = a["fc"]
            pdu = a["pdu"]
            if fc & 0x80:
                return                                   # rejected: not applied
            ok = False
            if fc == 6 and len(pdu) == 5:
                addr, v = struct.unpack("!HH", pdu[1:5])
                ok = addr == p["addr"] and [v] == p["vals"]
            elif fc == 16 and len(pdu) == 5:
                addr, qty = struct.unpack("!HH", pdu[1:5])
                ok = addr == p["addr"] and qty == len(p["vals"])
            if ok:
                self._commit(p, t)
            else:
                self._make_uncertain(p)
            return
        r = self.match_read(conn, a)
        if not r:
            return
        fc, start, regs, order = r
        if fc == 4 and start == 0:
            self.lvl10, self.lvl_t = _signed(regs[0]), t
        if fc == 3:
            for i, v in enumerate(regs):
                reg = start + i
                if reg >= 4:
                    continue
                # the PLC answers in order, so the readback reflects every write forwarded
                # before the read; later writes stay in the pending table (see possible())
                self.known[reg] = {v}

    def on_conn_lost(self, conn, t):
        for k in [k for k in self.pending if k[0] == conn]:
            self._make_uncertain(self.pending.pop(k))
        self.drop_conn(conn)

    def tick(self, t):
        for k in [k for k, p in self.pending.items() if t - p["t"] > self.t_ack]:
            self._make_uncertain(self.pending.pop(k))
        u = self.uncertain()
        if u and self.unc_since is None:
            self.unc_since = t
        if not u:
            self.unc_since = None

    def uncertain(self):
        return any(len(k) > 1 for k in self.known)

    def possible_values(self):
        return self.possible()


# ------------------------------------------------------------------ transport shell

class _Conn:
    """Byte accounting for one spliced Modbus/TCP connection.

    removals: client-stream ranges [P, P+L) taken out (client numbering).
    injections: (Q, M) M bytes inserted toward the client before PLC-stream offset Q."""

    def __init__(self, cseq):
        self.c_next = cseq
        self.s_next = None
        self.removals = []
        self.injections = []
        self.seen = {}              # client seq -> ("fwd", None) | ("deny", injected_frame)

    @staticmethod
    def _ge(a, b):
        return not ((a - b) & 0x80000000)

    def c2p(self, cseq):            # client seq/ack-of-client-stream -> PLC numbering
        return (cseq - sum(L for P, L in self.removals if self._ge(cseq, P + L))) & 0xFFFFFFFF

    def p2c_ack(self, pack):        # PLC's ack of the client stream -> client numbering
        out, before = pack, 0
        for P, L in self.removals:          # appended in stream order
            if self._ge(pack, (P - before) & 0xFFFFFFFF):
                out += L
            before += L
        return out & 0xFFFFFFFF

    def s2c(self, pseq):            # PLC seq -> client numbering
        return (pseq + sum(M for Q, M in self.injections if self._ge(pseq, Q))) & 0xFFFFFFFF

    def c_ack2p(self, cack):        # client's ack of the PLC stream -> PLC numbering
        out, before = cack, 0
        for Q, M in self.injections:        # appended in stream order
            qc = (Q + before) & 0xFFFFFFFF  # injection start in client numbering
            if self._ge(cack, qc + M):
                out -= M
            elif self._ge(cack, qc):
                out -= (cack - qc) & 0xFFFFFFFF
            before += M
        return out & 0xFFFFFFFF


class GateShell:
    def __init__(self, core, check_csum: bool, track_seq: bool, on_block: str):
        assert on_block in (DROP, DENY)
        if on_block == DENY:
            assert track_seq, "splicing needs sequence tracking"
        self.core, self.check_csum, self.track_seq, self.on_block = core, check_csum, track_seq, on_block
        self.conns = {}             # client port -> _Conn
        self.order = 0
        self.counts = {}
        self._t = 0

    def _count(self, rule):
        self.counts[rule] = self.counts.get(rule, 0) + 1

    def _new_conn(self, port, seq):
        for old in list(self.conns):
            self.core.on_conn_lost(old, self._t)
            del self.conns[old]
        c = self.conns[port] = _Conn(seq)
        return c

    def _to_plc(self, f, s, c):
        return rewrite(f, s, c.c2p(s.seq), c.c_ack2p(s.ack)) if self.track_seq else f

    def process(self, direction: int, f: bytes, t: int, fcs_ok: bool = True):
        """Return (rule, [(out_direction, frame)]).  out_direction 1 = toward the PLC."""
        self._t = t
        if not fcs_ok:
            return FCS_BAD, []
        s, err = parse(f)
        if err is not None:
            self._count(err)
            return err, []
        if self.check_csum and not (s.ip_ok and s.tcp_ok):
            self._count(CSUM_BAD)
            return CSUM_BAD, []
        if direction == 0:
            if s.dport != 502:
                return NON_MODBUS, []
            port = s.sport
            c = self.conns.get(port) or self._new_conn(port, s.seq)
            if self.track_seq and s.seq != c.c_next:
                if (s.seq - c.c_next) & 0x80000000:          # retransmission (seq < next)
                    kind = c.seen.get(s.seq)
                    if kind and kind[0] == "deny":
                        return S.PASS, [(0, kind[1])]
                    return S.PASS, [(1, self._to_plc(f, s, c))]
                self._count(TCP_OOW)
                return TCP_OOW, []
            if not s.payload:
                return S.PASS, [(1, self._to_plc(f, s, c))]
            a = parse_adu(s.payload)
            if a is None:
                self._count(MALFORMED)
                return MALFORMED, []
            rule = self.core.decide(port, a, t)
            self._count(rule)
            if rule == S.PASS:
                self.order += 1
                self.core.on_forward(port, a, t, self.order)
                out = self._to_plc(f, s, c)
                if self.track_seq:
                    c.seen[s.seq] = ("fwd", None)
                    c.c_next = (s.seq + len(s.payload)) & 0xFFFFFFFF
                return rule, [(1, out)]
            if self.on_block == DROP or c.s_next is None:
                return rule, []
            # splice: answer the client with an exception, remove the bytes from the stream
            exc = struct.pack("!HHHBBB", a["txid"], 0, 3, a["unit"], a["fc"] | 0x80, EXC_CODE)
            eth = f[6:12] + f[0:6] + f[12:s.l3]
            inj = build(eth, s.dst, s.src, s.dport, s.sport, c.s2c(c.s_next),
                        (s.seq + len(s.payload)) & 0xFFFFFFFF, exc)
            c.removals.append((s.seq, len(s.payload)))
            c.injections.append((c.s_next, len(exc)))
            c.seen[s.seq] = ("deny", inj)
            c.c_next = (s.seq + len(s.payload)) & 0xFFFFFFFF
            return rule, [(0, inj)]
        # plant side
        if s.sport != 502:
            return NON_MODBUS, []
        c = self.conns.get(s.dport)
        if c is None:
            return S.PASS, ([] if self.track_seq else [(0, f)])
        if self.track_seq:
            if c.s_next is None:
                c.s_next = s.seq
            if s.payload and s.seq == c.s_next:
                c.s_next = (s.seq + len(s.payload)) & 0xFFFFFFFF
            out_f = rewrite(f, s, c.s2c(s.seq), c.p2c_ack(s.ack))
        else:
            out_f = f
        if s.payload:
            a = parse_adu(s.payload)
            if a is not None:
                self.core.on_response(s.dport, a, t)
        return S.PASS, [(0, out_f)]

    def tick(self, t):
        self.core.tick(t)


class ExemptReducing:
    """Rule-set variant: a write that can only lower inlet, pump or heater is never blocked.

    Experiment 1 showed the frozen rules judge the post-write state, so they also refuse partial
    reductions (e.g. inlet 80 -> 60 at high level), which are corrective.  The exemption applies when
    every touched register is inlet/pump/heater and the new value is <= every value the register may
    currently hold; range and mapping checks still apply.  Outlet writes are never exempt (slew and
    deadhead rules concern both directions).
    """

    def __init__(self, core):
        self.core = core
        self.name = core.name + "+exempt"

    def __getattr__(self, n):
        return getattr(self.core, n)

    def decide(self, conn, a, t):
        if a["fc"] in (6, 16):
            w = _write_fields(a)
            if w is not None:
                addr, vals, over = w
                if not over and vals and addr + len(vals) <= 4 and all(v <= 100 for v in vals):
                    regs = [addr + i for i in range(len(vals))]
                    P = self.core.possible_values()
                    if S.OUTLET not in regs and all(v <= min(P[r]) for r, v in zip(regs, vals)):
                        return S.PASS
        return self.core.decide(conn, a, t)


def make_gate(kind: str) -> GateShell:
    """Named configurations used by the closed-loop experiment."""
    return {
        "none":               lambda: GateShell(NoneCore(), False, False, DROP),
        "v1_rtl":             lambda: GateShell(CommitOnForwardCore(), False, False, DROP),
        "v1_csum":            lambda: GateShell(CommitOnForwardCore(), True, True, DROP),
        "readback_splice":    lambda: GateShell(ReadbackCore(), True, True, DENY),
        "v2_drop":            lambda: GateShell(AcceptanceCore(), True, True, DROP),
        "v2_splice":          lambda: GateShell(AcceptanceCore(), True, True, DENY),
        "v1_csum_splice":     lambda: GateShell(CommitOnForwardCore(), True, True, DENY),
        "readback_splice_x":  lambda: GateShell(ExemptReducing(ReadbackCore()), True, True, DENY),
        "v2_splice_x":        lambda: GateShell(ExemptReducing(AcceptanceCore()), True, True, DENY),
        # active polling: the harness makes the gate issue its own FC3/FC4 reads (see closed_loop)
        "v3_splice_x":        lambda: GateShell(__import__("sysone.v2.agent_gate.gate_v3", fromlist=["V3Core"]).V3Core(), True, True, DENY),
        "v3_mutate_x":        lambda: __import__("sysone.v2.agent_gate.gate_mutate", fromlist=["MutateShell"]).MutateShell(
            __import__("sysone.v2.agent_gate.gate_v3", fromlist=["V3Core"]).V3Core()),
        "v3_mutate_il":       lambda: __import__("sysone.v2.agent_gate.gate_mutate", fromlist=["MutateShell"]).MutateShell(
            __import__("sysone.v2.agent_gate.interlock", fromlist=["GateInterlockCore"]).GateInterlockCore(
                __import__("sysone.v2.agent_gate.gate_v3", fromlist=["V3Core"]).V3Core())),
        "v3_mutate_il2":      lambda: __import__("sysone.v2.agent_gate.gate_mutate", fromlist=["MutateShell"]).MutateShell(
            __import__("sysone.v2.agent_gate.interlock", fromlist=["GateInterlockCore"]).GateInterlockCore(
                __import__("sysone.v2.agent_gate.gate_v3", fromlist=["V3Core"]).V3Core(), v2=True)),
        "readback_prov_x":    lambda: GateShell(ExemptReducing(ReadbackProvCore()), True, True, DENY),
        "readback_poll1_x":   lambda: GateShell(ExemptReducing(ReadbackCore()), True, True, DENY),
        "readback_poll5_x":   lambda: GateShell(ExemptReducing(ReadbackCore()), True, True, DENY),
        "v2_poll1_x":         lambda: GateShell(ExemptReducing(AcceptanceCore()), True, True, DENY),
    }[kind]()


def gate_poll_ms(kind: str) -> int:
    """Interval at which a gate issues its own reads (0 = passive)."""
    if "_poll" not in kind:
        return 0
    return 1000 * int(kind.split("_poll")[1].split("_")[0])


GATES = ["none", "v1_rtl", "v1_csum", "v1_csum_splice", "readback_splice", "v2_drop", "v2_splice"]
ALL_GATES = GATES + ["oracle_state"]
