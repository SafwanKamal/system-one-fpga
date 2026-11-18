"""Gate v3 decision core: the hardware-exact specification of acceptance tracking.

`gate_v2.AcceptanceCore` is the behavioural reference (unbounded sets, float level rates, periodic timers).  This
module restricts it to what fits in fabric, with integer arithmetic, so that rtl/v2/gate/gate_core_v3.sv can match it
bit for bit.  Differences from v2 (each is a restriction, validated in the closed loop in experiment 5):

  * pending-write table: PEND = 8 entries; a write arriving with the table full is refused (PENDING_FULL);
  * possible values per register: at most 2 ({committed, alternative}); a third distinct value marks the register
    WILD, and every non-exempt write is refused with STATE_UNKNOWN until a read-back resolves it;
  * read-transaction table: READS = 8 entries, round-robin replacement;
  * timeouts are evaluated when a frame arrives (the core has no timer), not every 100 ms;
  * pump-start times: the last 4 times at which a start was *forwarded* are kept and never removed (v2 drops a start
    that the PLC rejects), which is more conservative;
  * level interval in integers: rise = ceil(max_inlet * age_ms * 315 / 2^20),
    fall = floor(max_pump * SQRT100[max_outlet] * age_ms * 53 / 2^24), age clamped to 60 s,
    SQRT100[o] = round(100 * sqrt(o / 100)); bounds lo = max(lvl - fall, -100), hi = min(lvl + rise, 1100);
    with no level reading yet the bounds are (0, 1000);
  * the risk-reducing exemption (ExemptReducing) is part of decide().

Decision order: range/mapping checks, exemption, pending-full, wild check, then every combination of possible actuator
values (register 0 slowest, each register's values ascending) crossed with the level bounds (lo then hi); the first
non-PASS rule is returned.
"""
from __future__ import annotations

import math
import struct

from . import intspec as S

PEND, READS, KSET = 8, 8, 2
T_ACK_MS = 2000
AGE_MAX_MS = 60_000
# Level-rate constants (power-of-two scaling so the fabric needs no divider).  True worst-case rates from the spec
# ranges: rise 0.30 and fall 0.03125 level*10 per (% x ms) respectively; both constants round up.
RISE_K, RISE_SH = 315, 20        # 315 / 2^20 = 3.004e-4  (>= 3.0e-4)
FALL_K, FALL_SH = 53, 24         # 53 / 2^24  = 3.159e-6  (>= 3.125e-6)
SQRT100 = [round(100 * math.sqrt(o / 100)) for o in range(101)]
PENDING_FULL, STATE_UNKNOWN = 18, 19
MALFORMED = 13


def _signed(r):
    return r - 0x10000 if r & 0x8000 else r


def write_fields(a):
    """(addr, vals, over) for a well-formed FC6/FC16 request, else None.  Mirrors gate_v2._write_fields."""
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


class V3Core:
    name = "v3"

    def __init__(self):
        self.pend = [None] * PEND            # dict(conn, txid, addr, vals, t, start)
        self.reads = [None] * READS          # (conn, txid, fc, start, qty)
        self.rptr = 0
        self.v0 = [0, 0, 0, 0]
        self.v1 = [0, 0, 0, 0]
        self.unc = [False] * 4
        self.wild = [False] * 4
        self.lvl10, self.lvl_t, self.lvl_ok = 0, 0, False
        self.starts = []                     # last 4 forwarded start times

    # ---------------------------------------------------------------- helpers
    def _poss(self, r):
        """Possible values of register r from the committed set only (ascending)."""
        return sorted({self.v0[r], self.v1[r]}) if self.unc[r] else [self.v0[r]]

    def possible(self):
        """Possible values per register including pending writes (2 values max; WILD -> all)."""
        P = [self._poss(r) for r in range(4)]
        W = list(self.wild)
        for p in self.pend:
            if p:
                for i, v in enumerate(p["vals"]):
                    r = p["addr"] + i
                    if v not in P[r]:
                        if len(P[r]) >= KSET:
                            W[r] = True
                        else:
                            P[r] = sorted(P[r] + [v])
        return P, W

    def _make_uncertain(self, p):
        for i, v in enumerate(p["vals"]):
            r = p["addr"] + i
            cur = self._poss(r)
            if v in cur:
                continue
            if len(cur) >= KSET:
                self.wild[r] = True
            else:
                self.unc[r] = True
                self.v0[r], self.v1[r] = sorted(cur + [v])

    def _scan(self, t):
        for k, p in enumerate(self.pend):
            if p and ((t - p["t"]) & 0xFFFFFFFF) > T_ACK_MS:
                self._make_uncertain(p)
                self.pend[k] = None

    def level_bounds(self, t, P, W):
        if not self.lvl_ok:
            return 0, 1000
        age = min((t - self.lvl_t) & 0xFFFFFFFF, AGE_MAX_MS)
        mx = [100 if W[r] else min(100, max(P[r])) for r in range(4)]     # >100 % saturates physically
        rise = -(-(mx[S.INLET] * age * RISE_K) // (1 << RISE_SH))
        fall = (mx[S.PUMP] * SQRT100[mx[S.OUTLET]] * age * FALL_K) >> FALL_SH
        return max(self.lvl10 - fall, -100), min(self.lvl10 + rise, 1100)

    def _starts4(self):
        s = self.starts[-4:]
        return s + [S.NO_START] * (4 - len(s))

    # ---------------------------------------------------------------- decision
    def decide(self, conn, a, t):
        self._scan(t)
        fc = a["fc"]
        if fc in (3, 4) or fc not in (6, 16):
            return S.decide(fc, 0, [], 0, [0, 0, 0, 0], t, self._starts4())
        w = write_fields(a)
        if w is None:
            return MALFORMED
        addr, vals, over = w
        if over:
            return S.UNMAPPED
        if not vals or addr + len(vals) > 4:
            return S.UNMAPPED
        if any(v > 100 for v in vals):
            return S.RANGE
        P, W = self.possible()
        regs = [addr + i for i in range(len(vals))]
        # risk-reducing exemption: only inlet/pump/heater, every value <= every possible current value
        if S.OUTLET not in regs and all(v <= (0 if W[r] else min(P[r])) for r, v in zip(regs, vals)):
            return S.PASS
        if sum(1 for p in self.pend if p) >= PEND:
            return PENDING_FULL
        if any(W):
            return STATE_UNKNOWN
        lo, hi = self.level_bounds(t, P, W)
        st = self._starts4()
        for a0 in P[0]:
            for a1 in P[1]:
                for a2 in P[2]:
                    for a3 in P[3]:
                        for lvl in (lo, hi):
                            r = S.decide(fc, addr, vals, lvl, [a0, a1, a2, a3], t, st)
                            if r != S.PASS:
                                return r
        return S.PASS

    # ---------------------------------------------------------------- events
    def on_forward(self, conn, a, t, order):
        fc = a["fc"]
        if fc in (3, 4):
            if len(a["pdu"]) == 5:
                start, qty = struct.unpack("!HH", a["pdu"][1:5])
                self.reads[self.rptr] = (conn, a["txid"], fc, start, qty)
                self.rptr = (self.rptr + 1) % READS
            return
        w = write_fields(a)
        if not w:
            return
        addr, vals, _ = w
        P, _W = self.possible()
        start = S.PUMP in range(addr, addr + len(vals)) and vals[S.PUMP - addr] > 0 and 0 in P[S.PUMP]
        k = next((i for i, p in enumerate(self.pend) if p is None), None)
        if k is None:
            return                              # unreachable: decide() refuses when full
        self.pend[k] = dict(conn=conn, txid=a["txid"], addr=addr, vals=list(vals), t=t, start=start)
        if start:
            self.starts = (self.starts + [t])[-4:]

    def _commit(self, p):
        for i, v in enumerate(p["vals"]):
            r = p["addr"] + i
            self.v0[r], self.unc[r], self.wild[r] = v, False, False

    def on_response(self, conn, a, t):
        self._scan(t)
        fc, pdu = a["fc"], a["pdu"]
        for k, p in enumerate(self.pend):
            if p and p["conn"] == conn and p["txid"] == a["txid"]:
                self.pend[k] = None
                if fc & 0x80:
                    return                          # rejected: not applied
                ok = False
                if fc == 6 and len(pdu) == 5:
                    ad, v = struct.unpack("!HH", pdu[1:5])
                    ok = ad == p["addr"] and [v] == p["vals"]
                elif fc == 16 and len(pdu) == 5:
                    ad, qty = struct.unpack("!HH", pdu[1:5])
                    ok = ad == p["addr"] and qty == len(p["vals"])
                if ok:
                    self._commit(p)
                else:
                    self._make_uncertain(p)
                return
        for k, rd in enumerate(self.reads):
            if rd and rd[0] == conn and rd[1] == a["txid"] and fc in (3, 4):
                self.reads[k] = None
                _c, _x, rfc, start, qty = rd
                if rfc != fc or len(pdu) < 2 or pdu[1] != 2 * qty or len(pdu) != 2 + 2 * qty:
                    return
                regs = [struct.unpack("!H", pdu[2 + 2 * i:4 + 2 * i])[0] for i in range(qty)]
                if fc == 4 and start == 0 and qty >= 1:
                    self.lvl10, self.lvl_t, self.lvl_ok = _signed(regs[0]), t, True
                if fc == 3:
                    for i, v in enumerate(regs):
                        r = start + i
                        if r < 4:
                            self.v0[r], self.unc[r], self.wild[r] = v, False, False
                return

    def on_conn_lost(self, conn, t):
        for k, p in enumerate(self.pend):
            if p and p["conn"] == conn:
                self._make_uncertain(p)
                self.pend[k] = None
        for k, rd in enumerate(self.reads):
            if rd and rd[0] == conn:
                self.reads[k] = None

    def tick(self, t):
        pass

    def uncertain(self):
        return any(self.unc) or any(self.wild)

    def possible_values(self):
        return self.possible()[0]
