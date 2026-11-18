"""Gate policies.  A gate sees only what an inline device sees: the Modbus request
(function code, address, values), the readings in recent read responses (biased,
noisy), the actuator values it has itself forwarded, and its own clock.

Policies never import the plant's hidden parameters.  `stateful_predictive` uses the
engineering SPEC ranges (what a configurator would know) and is reported as a
model-aware upper reference; `stateful_rules` is the headline stateful arm: plain
interlock rules a controls engineer would write from the spec sheet.
"""
from __future__ import annotations

import copy
import math

from . import plant

WRITE_FCS = {5, 6, 15, 16}
READ_FCS = {1, 2, 3, 4}


class GateView:
    """What the gate has observed so far."""

    def __init__(self) -> None:
        self.obs = {"level": 50.0, "temperature": 25.0, "pressure": 0.0, "flow": 0.0}
        self.act = {n: 0.0 for n in plant.HOLDING.values()}
        self.pump_starts: list[float] = []
        self.t = 0.0

    def forwarded(self, writes: list[tuple[str, float]]) -> None:
        for name, value in writes:
            if name == "pump_speed" and self.act[name] <= 0.0 < value:
                self.pump_starts.append(self.t)
            self.act[name] = float(value)


def decode(req: dict) -> tuple[str | None, list[tuple[str, float]]]:
    """Map a request to (error, writes).  error is set for malformed/unmapped writes."""
    fc, addr, vals = req["fc"], req["addr"], req["values"]
    if fc in READ_FCS:
        return None, []
    if fc not in (6, 16):
        return "fc_not_holding_write", []
    writes = []
    for i, v in enumerate(vals):
        name = plant.HOLDING.get(addr + i)
        if name is None:
            return "unmapped_address", []
        writes.append((name, v))
    return None, writes


# ---------------------------------------------------------------- policies

def policy_none(req, view):
    return True, "pass"


def make_allowlist(allowed_fcs, ranges):
    """Tofino/Claroty-style per-packet enforcement: FC + address + value range."""
    def policy(req, view):
        if req["fc"] not in allowed_fcs:
            return False, "fc_denied"
        err, writes = decode(req)
        if err:
            return False, err
        for name, v in writes:
            lo, hi = ranges.get(name, (None, None))
            if lo is None:
                return False, "register_denied"
            if not (lo <= v <= hi):
                return False, "value_out_of_range"
        return True, "pass"
    return policy


allow_basic = make_allowlist({1, 2, 3, 4, 5, 6, 15, 16}, dict(plant.ENG_RANGE))


def _merged(view, writes):
    a = dict(view.act)
    for n, v in writes:
        a[n] = float(v)
    return a


def stateful_rules(req, view):
    ok, why = allow_basic(req, view)
    if not ok:
        return ok, why
    _, writes = decode(req)
    if not writes:
        return True, "pass"
    a = _merged(view, writes)
    lvl = view.obs["level"]
    names = {n for n, _ in writes}
    # R1/R7 pump vs level
    if a["pump_speed"] > 0 and ("pump_speed" in names or "outlet_valve" in names):
        if lvl < 15:
            return False, "R1_pump_low_level"
        if a["pump_speed"] > 50 and lvl < 40:
            return False, "R7_pump_fast_low_level"
    # R2 deadhead
    if a["pump_speed"] > 0:
        need = a["pump_speed"] if a["pump_speed"] > 50 else 15
        if a["outlet_valve"] < need:
            return False, "R2_deadhead"
    # R3 valve slew while pumping
    if "outlet_valve" in names and view.act["pump_speed"] > 0:
        if abs(a["outlet_valve"] - view.act["outlet_valve"]) > 30:
            return False, "R3_valve_slew"
    # R4 heater coverage
    if a["heater_power"] > 0:
        if lvl < 35:
            return False, "R4_heater_low_level"
        if lvl < 40 and ("pump_speed" in names or "outlet_valve" in names) and \
                (a["pump_speed"] > view.act["pump_speed"] or a["outlet_valve"] > view.act["outlet_valve"]):
            return False, "R4_drain_with_heater"
    # R5 overfill
    if "inlet_valve" in names:
        if a["inlet_valve"] > 0 and lvl >= 85:
            return False, "R5_overfill"
        if a["inlet_valve"] >= 50 and lvl >= 75:
            return False, "R5_overfill"
    # R6 short cycling
    if "pump_speed" in names and view.act["pump_speed"] <= 0 < a["pump_speed"]:
        if len([t for t in view.pump_starts if view.t - t <= 60.0]) >= 3:
            return False, "R6_short_cycle"
    return True, "pass"


def _corners():
    S = plant.SPEC
    for area in (S["area"][1], S["area"][2]):
        for fin in (S["fin_max"][1], S["fin_max"][2]):
            for kq in (S["kq"][1], S["kq"][2]):
                for lvl_off in (-2.5, 2.5):
                    yield area, fin, kq, lvl_off


def stateful_predictive(req, view):
    """Worst-case envelope over the spec ranges (model-aware reference arm)."""
    ok, why = allow_basic(req, view)
    if not ok:
        return ok, why
    _, writes = decode(req)
    if not writes:
        return True, "pass"
    S = plant.SPEC
    for area, fin, kq, off in _corners():
        p = plant.Params(area=area, fin_max=fin, kq=kq, p0=S["p0"][2], heat_k=S["heat_k"][2],
                         overflow=S["overflow"][1] - 1.0, dry_level=S["dry_level"][2] + 1.0,
                         heater_cover=S["heater_cover"][2] + 2.0, level_bias=0.0,
                         supply_dip_at=math.inf, supply_dip=1.0)
        s = plant.State(t=view.t, level=max(0.0, view.obs["level"] + off),
                        temperature=view.obs["temperature"], act=dict(view.act),
                        pump_starts=list(view.pump_starts))
        lab = plant.label(p, s, writes)
        if lab["unsafe"]:
            return False, "P_" + lab["caused"][0]
        # also refuse to *worsen* an already-hazardous envelope
        if lab["preexisting"]:
            s2 = copy.deepcopy(s)
            for n, v in writes:
                plant.apply_write(p, s2, n, v)
            if len(plant.hold_hazards(p, s2)) > len(lab["preexisting"]):
                return False, "P_worsen"
    return True, "pass"


def tuned_allowlist_from(traces):
    """Learn the strongest per-packet allow-list from legitimate traffic."""
    fcs, ranges = set(), {}
    for req in traces:
        fcs.add(req["fc"])
        err, writes = decode(req)
        for n, v in writes:
            lo, hi = ranges.get(n, (v, v))
            ranges[n] = (min(lo, v), max(hi, v))
    fcs |= READ_FCS & {3, 4}
    return make_allowlist(fcs, ranges)
