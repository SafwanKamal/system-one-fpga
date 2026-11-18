"""Level- and temperature-triggered protective interlock (a second mechanism beside the write gate).

A write gate can refuse a harmful command but cannot act when the agent fails to act (inlet left open, heater left on).
The interlock trips on measured conditions and drives the offending actuator to its safe value (0), with hysteresis,
and while tripped refuses writes that would raise that actuator again.

Trip / reset thresholds (integers: level*10, temperature*10), chosen from the plant spec with margin for sensor bias
(+-1.5 %), one poll period of travel at the worst-case rate, and the round trip of the forcing write:

    trip                      condition (gate: interval bound)   reset            forces
    I_OVERFILL                level hi >= 900                    hi < 850         inlet  -> 0   (overflow at 96-98 %)
    I_DRY                     level lo <= 150                    lo >= 200        pump   -> 0   (dry-run below 6-10 %)
    I_EXPOSED                 level lo <= 350                    lo >= 400        heater -> 0   (element exposed below 22-28 %)
    I_HOT                     temperature >= 800                 temp < 750       heater -> 0   (damage above 90 degC)

Two placements are modelled with the same logic:
  * in the gate (`GateInterlockCore`): inputs are the gate's own level interval (it widens with the age of the last
    reading and with the possible actuator values, exactly as the v3 decision core computes it) and the last snooped
    temperature; forcing writes go out on the gate's own Modbus connection to the PLC, so link outages and loss stop
    them, and they are tracked by the acceptance core like any other write;
  * in the PLC (`PlcInterlock`): inputs are the PLC's own sensor values (true level plus sensor bias, no noise, every
    0.5 s plant step); forcing is immediate and survives any network fault.  This is the conventional placement and is
    the comparator for the gate placement.
Rule code 20 (interlock_active) is returned for a write refused because it would raise a tripped actuator.
"""
from __future__ import annotations

import struct

from . import intspec as S

INTERLOCK = 20
TRIPS = {
    # name: (kind, trip threshold, reset threshold, register forced to 0)
    "I_OVERFILL": ("hi_ge", 900, 850, S.INLET),
    "I_DRY":      ("lo_le", 150, 200, S.PUMP),
    "I_EXPOSED":  ("lo_le", 350, 400, S.HEATER),
    "I_HOT":      ("t_ge", 800, 750, S.HEATER),
}
REASSERT_MS = 2000   # gate re-sends a forcing write at most this often per register while its effect is unconfirmed


class Interlock:
    """The latch logic shared by both placements."""

    def __init__(self):
        self.on = {k: False for k in TRIPS}
        self.trips = {k: 0 for k in TRIPS}         # number of trip events (rising edges)

    def update(self, lo, hi, temp10, safe=None):
        """`safe[r]` (v2 latch rule, experiment 8b): a trip resets only once its condition has cleared AND the forced
        actuator is known to be at 0.  Without `safe` (experiment 8) the condition alone resets it."""
        for k, (kind, trip, reset, _r) in TRIPS.items():
            if kind == "hi_ge":
                x, tripped, cleared = hi, hi is not None and hi >= trip, hi is not None and hi < reset
            elif kind == "lo_le":
                x, tripped, cleared = lo, lo is not None and lo <= trip, lo is not None and lo >= reset
            else:
                x, tripped, cleared = temp10, temp10 is not None and temp10 >= trip, temp10 is not None and temp10 < reset
            if x is None:
                continue
            if not self.on[k] and tripped:
                self.on[k] = True
                self.trips[k] += 1
            elif self.on[k] and cleared and (safe is None or safe[_r]):
                self.on[k] = False

    def forced(self):
        return {TRIPS[k][3] for k, v in self.on.items() if v}

    def refuses(self, addr, vals):
        f = self.forced()
        return any(addr + i in f and v > 0 for i, v in enumerate(vals))


class GateInterlockCore:
    """Wraps a V3Core: adds the interlock refusal ahead of the core's decision, snoops temperature, and proposes
    forcing writes for the harness to send on the gate's own connection."""

    name = "v3_il"

    def __init__(self, core, v2=False):
        """v2 (experiment 8b) fixes two defects found in experiment 8: the latches are also updated at every write
        decision (v1 updated them only on the 100 ms tick, so a write decided in the same tick as a trip could pass),
        and a trip resets only once the forced actuator is known to be at 0."""
        self.core = core
        self.v2 = v2
        self.il = Interlock()
        self.temp10 = None
        self.last_force = {}                       # register -> time of last forcing write
        self.forcing_writes = 0

    def _latch(self, t):
        core = self.core
        core._scan(t)
        P, W = core.possible()
        lo, hi = core.level_bounds(t, P, W) if core.lvl_ok else (None, None)
        safe = [not W[r] and max(P[r]) == 0 for r in range(4)] if self.v2 else None
        self.il.update(lo, hi, self.temp10, safe)
        return P, W

    # --- decision path (called by the shell)
    def decide(self, conn, a, t):
        if a["fc"] in (6, 16):
            if self.v2:
                self._latch(t)
            from .gate_v3 import write_fields
            w = write_fields(a)
            if w is not None and not w[2] and w[1] and w[0] + len(w[1]) <= 4 and self.il.refuses(w[0], w[1]):
                return INTERLOCK
        return self.core.decide(conn, a, t)

    def on_forward(self, conn, a, t, order):
        self.core.on_forward(conn, a, t, order)

    def on_response(self, conn, a, t):
        rd = next((r for r in self.core.reads if r and r[0] == conn and r[1] == a["txid"]), None)
        self.core.on_response(conn, a, t)
        pdu = a["pdu"]
        if rd and a["fc"] == 4 == rd[2] and rd[3] == 0 and rd[4] >= 2 and len(pdu) == 2 + 2 * rd[4] and pdu[1] == 2 * rd[4]:
            v = struct.unpack("!H", pdu[4:6])[0]
            self.temp10 = v - 0x10000 if v & 0x8000 else v

    def on_conn_lost(self, conn, t):
        self.core.on_conn_lost(conn, t)

    def tick(self, t):
        self.core.tick(t)

    def uncertain(self):
        return self.core.uncertain()

    def possible_values(self):
        return self.core.possible_values()

    def __getattr__(self, k):                       # reads, lvl_ok, ... for the harness
        return getattr(self.core, k)

    # --- interlock evaluation
    def evaluate(self, t):
        """Update latches from the current interval; return registers that need a forcing write now."""
        P, W = self._latch(t)
        out = []
        for r in sorted(self.il.forced()):
            if (W[r] or max(P[r]) > 0) and ((t - self.last_force.get(r, -10**9)) >= REASSERT_MS):
                self.last_force[r] = t
                out.append(r)
        return out


class PlcInterlock:
    """The same latches inside the PLC, on its own sensor values, applied every plant step."""

    def __init__(self, v2=False):
        self.il = Interlock()
        self.v2 = v2
        self.forced_steps = 0

    def step(self, p, s):
        lvl10 = int(round((s.level + p.level_bias) * 10))
        order = ["inlet_valve", "pump_speed", "outlet_valve", "heater_power"]
        safe = [s.act[n] <= 0 for n in order] if self.v2 else None
        self.il.update(lvl10, lvl10, int(round(s.temperature * 10)), safe)
        for r in self.il.forced():
            if s.act[order[r]] > 0:
                s.act[order[r]] = 0.0
                self.forced_steps += 1
