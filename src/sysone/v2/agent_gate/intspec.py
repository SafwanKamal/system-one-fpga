"""Canonical integer specification of the gate rules (what the RTL implements).

It is the frozen `policies.stateful_rules` (allow_basic + R1..R7) in fixed point:
  * register values are Modbus uint16 (agent floats are rounded half-away-from-zero by
    the tool layer; negatives wrap as uint16 and therefore fail the range check);
  * observed level is level*10 as an integer (readings carry one decimal);
  * time is a 32-bit millisecond counter; the gate keeps the last 4 pump-start times.

Rule codes (also the RTL `rule_id` output):
"""
from __future__ import annotations

import math

PASS, FC_DENIED, FC_NOT_HOLDING_WRITE, UNMAPPED, RANGE = 0, 1, 2, 3, 4
R1, R7, R2, R3, R4_LOW, R4_DRAIN, R5, R6 = 5, 6, 7, 8, 9, 10, 11, 12
NAMES = {0: "pass", 1: "fc_denied", 2: "fc_not_holding_write", 3: "unmapped_address",
         4: "value_out_of_range", 5: "R1_pump_low_level", 6: "R7_pump_fast_low_level",
         7: "R2_deadhead", 8: "R3_valve_slew", 9: "R4_heater_low_level",
         10: "R4_drain_with_heater", 11: "R5_overfill", 12: "R6_short_cycle"}
ALLOWED_FCS = {1, 2, 3, 4, 5, 6, 15, 16}
READ_FCS = {1, 2, 3, 4}
INLET, PUMP, OUTLET, HEATER = 0, 1, 2, 3
N_STARTS = 4
NO_START = 0xFFFFFFFF


def u16(v: float) -> int:
    r = int(math.floor(abs(v) + 0.5)) * (1 if v >= 0 else -1)
    return r & 0xFFFF


def decide(fc: int, addr: int, vals: list[int], lvl10: int, act: list[int], t_ms: int,
           starts: list[int]) -> int:
    """Return a rule code; PASS means forward."""
    if fc not in ALLOWED_FCS:
        return FC_DENIED
    if fc in READ_FCS:
        return PASS
    if fc not in (6, 16):
        return FC_NOT_HOLDING_WRITE
    if not vals or addr + len(vals) > 4:
        return UNMAPPED
    for v in vals:
        if v > 100:
            return RANGE
    a = list(act)
    names = set()
    for i, v in enumerate(vals):
        a[addr + i] = v
        names.add(addr + i)
    if a[PUMP] > 0 and (PUMP in names or OUTLET in names):
        if lvl10 < 150:
            return R1
        if a[PUMP] > 50 and lvl10 < 400:
            return R7
    if a[PUMP] > 0:
        need = a[PUMP] if a[PUMP] > 50 else 15
        if a[OUTLET] < need:
            return R2
    if OUTLET in names and act[PUMP] > 0:
        if abs(a[OUTLET] - act[OUTLET]) > 30:
            return R3
    if a[HEATER] > 0:
        if lvl10 < 350:
            return R4_LOW
        if lvl10 < 400 and (PUMP in names or OUTLET in names) and \
                (a[PUMP] > act[PUMP] or a[OUTLET] > act[OUTLET]):
            return R4_DRAIN
    if INLET in names:
        if a[INLET] > 0 and lvl10 >= 850:
            return R5
        if a[INLET] >= 50 and lvl10 >= 750:
            return R5
    if PUMP in names and act[PUMP] == 0 and a[PUMP] > 0:
        recent = sum(1 for s in starts if s != NO_START and (t_ms - s) & 0xFFFFFFFF <= 60000)
        if recent >= 3:
            return R6
    return PASS


def vector_from_record(r: dict) -> dict:
    """Map a recorded go/no-go decision to integer inputs."""
    q = r["req"]
    v = r["view"]
    t_ms = int(round(v["t"] * 1000)) & 0xFFFFFFFF
    starts = sorted(int(round(s * 1000)) & 0xFFFFFFFF for s in v["pump_starts"])[-N_STARTS:]
    starts = starts + [NO_START] * (N_STARTS - len(starts))
    order = ["inlet_valve", "pump_speed", "outlet_valve", "heater_power"]
    return {
        "fc": int(q["fc"]) & 0xFF, "addr": int(q["addr"]) & 0xFFFF,
        "vals": [u16(x) for x in q["values"]][:4],
        "nvals_raw": len(q["values"]),
        "lvl10": int(round(v["obs"]["level"] * 10)),
        "act": [u16(v["act"][n]) for n in order],
        "t_ms": t_ms, "starts": starts,
    }


def decide_vector(x: dict) -> int:
    if x["nvals_raw"] > 4:
        return UNMAPPED
    return decide(x["fc"], x["addr"], x["vals"], x["lvl10"], x["act"], x["t_ms"], x["starts"])
