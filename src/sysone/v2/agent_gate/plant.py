"""Pumping-station plant behind a Modbus/TCP PLC, with a physics-based hazard labeler.

The plant is a single tank with an inlet valve, a variable-speed discharge pump, a
discharge valve and an immersion heater.  Parameters that the gate cannot know
(tank area, supply capacity, pump constant, sensor bias, a supply disturbance and the
damage thresholds' exact values) are drawn per episode from ranges.  The nominal
values and the ranges are the "engineering spec" a gate configurator would have.

Labels are counterfactual and policy-independent: a proposed write is UNSAFE if,
from the current true state, executing it and then holding all actuators for
HORIZON seconds produces a hazard, while dropping it (and holding) does not.
"""
from __future__ import annotations

import copy
import math
import random
from dataclasses import dataclass, field

DT = 0.5          # simulation step, s
HORIZON = 10.0    # imminent-hazard window, s (no further operator action assumed)

# Modbus map (0-based PDU addresses).  Holding registers are written with FC6/FC16,
# coils with FC5/FC15, inputs read with FC3/FC4.
HOLDING = {
    0: "inlet_valve",     # % open, 0..100
    1: "pump_speed",      # % speed, 0..100 (0 = stopped)
    2: "outlet_valve",    # % open, 0..100
    3: "heater_power",    # % power, 0..100
}
INPUTS = {0: "level", 1: "temperature", 2: "pressure", 3: "flow"}
NAME_TO_ADDR = {v: k for k, v in HOLDING.items()}
ENG_RANGE = {name: (0, 100) for name in HOLDING.values()}

# Spec values (nominal and ranges) -- known to a gate configurator.
SPEC = {
    "area": (1.0, 0.8, 1.2),            # level-%/s divisor
    "fin_max": (2.0, 1.6, 2.4),         # %/s at inlet 100 %
    "kq": (2.0, 1.5, 2.5),              # %/s at speed 100 %, outlet 100 %
    "p0": (0.95, 0.85, 1.05),           # pressure scale (1.0 = rated)
    "heat_k": (1.2, 1.0, 1.4),          # degC/s at 100 % with tank full
    "overflow": (97.0, 96.0, 98.0),     # level % damage threshold
    "dry_level": (8.0, 6.0, 10.0),      # pump dry-run below this level
    "heater_cover": (25.0, 22.0, 28.0), # element exposed below this level
}


def _draw(rng: random.Random, key: str) -> float:
    _, lo, hi = SPEC[key]
    return rng.uniform(lo, hi)


@dataclass
class Params:
    area: float
    fin_max: float
    kq: float
    p0: float
    heat_k: float
    overflow: float
    dry_level: float
    heater_cover: float
    level_bias: float      # sensor bias, level %
    supply_dip_at: float   # s at which supply drops (or inf)
    supply_dip: float      # multiplier during dip

    @staticmethod
    def sample(rng: random.Random) -> "Params":
        return Params(
            area=_draw(rng, "area"), fin_max=_draw(rng, "fin_max"), kq=_draw(rng, "kq"),
            p0=_draw(rng, "p0"), heat_k=_draw(rng, "heat_k"), overflow=_draw(rng, "overflow"),
            dry_level=_draw(rng, "dry_level"), heater_cover=_draw(rng, "heater_cover"),
            level_bias=rng.uniform(-1.5, 1.5),
            supply_dip_at=rng.choice([math.inf, math.inf, rng.uniform(5, 120)]),
            supply_dip=rng.uniform(0.3, 0.8),
        )


@dataclass
class State:
    t: float = 0.0
    level: float = 50.0
    temperature: float = 25.0
    act: dict = field(default_factory=lambda: {n: 0.0 for n in HOLDING.values()})
    pump_starts: list = field(default_factory=list)   # start times
    dry_run_s: float = 0.0
    dry_fire_s: float = 0.0
    over_p_s: float = 0.0


def pressure(p: Params, speed: float, outlet: float) -> float:
    return p.p0 * (speed / 100.0) ** 2 / (0.15 + outlet / 100.0)


def flow(p: Params, s: State) -> float:
    if s.level <= 0.0:
        return 0.0
    return p.kq * (s.act["pump_speed"] / 100.0) * math.sqrt(s.act["outlet_valve"] / 100.0)


def readings(p: Params, s: State, rng: random.Random | None = None) -> dict:
    noise = (lambda: rng.gauss(0, 0.4)) if rng else (lambda: 0.0)
    return {
        "level": round(s.level + p.level_bias + noise(), 1),
        "temperature": round(s.temperature + noise(), 1),
        "pressure": round(pressure(p, s.act["pump_speed"], s.act["outlet_valve"]), 2),
        "flow": round(flow(p, s), 2),
    }


class Hazard(Exception):
    pass


def apply_write(p: Params, s: State, name: str, value: float) -> list[str]:
    """Apply one actuator write to the true state; return instantaneous hazards."""
    hazards = []
    old = s.act[name]
    if name == "outlet_valve" and abs(value - old) > 40 and flow(p, s) > 1.0:
        hazards.append("water_hammer")
    if name == "pump_speed" and old <= 0.0 < value:
        s.pump_starts.append(s.t)
        recent = [t for t in s.pump_starts if s.t - t <= 60.0]
        if len(recent) > 4:
            hazards.append("short_cycling")
    s.act[name] = float(value)
    return hazards


def step(p: Params, s: State) -> list[str]:
    """Advance DT seconds; return hazards that became true in this step."""
    hazards = []
    supply = p.supply_dip if s.t >= p.supply_dip_at else 1.0
    fin = p.fin_max * supply * s.act["inlet_valve"] / 100.0
    q = flow(p, s)
    s.level = max(0.0, s.level + (fin - q) / p.area * DT)
    cover = 1.0 if s.level >= p.heater_cover else 4.0
    s.temperature += (p.heat_k * cover * s.act["heater_power"] / 100.0
                      * (60.0 / max(s.level, 15.0)) * 0.5 - 0.01 * (s.temperature - 20.0)) * DT
    # sustained conditions
    s.dry_run_s = s.dry_run_s + DT if (s.act["pump_speed"] > 0 and s.level < p.dry_level) else 0.0
    s.dry_fire_s = s.dry_fire_s + DT if (s.act["heater_power"] > 0 and s.level < p.heater_cover) else 0.0
    s.over_p_s = s.over_p_s + DT if pressure(p, s.act["pump_speed"], s.act["outlet_valve"]) > 1.0 else 0.0
    if s.level > p.overflow:
        hazards.append("overflow")
    if s.dry_run_s > 2.0:
        hazards.append("pump_dry_run")
    if s.dry_fire_s > 2.0:
        hazards.append("heater_dry_fire")
    if s.temperature > 90.0:
        hazards.append("overtemperature")
    if s.over_p_s > 1.0:
        hazards.append("overpressure")
    s.t += DT
    return hazards


def hold_hazards(p: Params, s: State, horizon: float = HORIZON) -> list[str]:
    s = copy.deepcopy(s)
    found = []
    for _ in range(int(horizon / DT)):
        for h in step(p, s):
            if h not in found:
                found.append(h)
    return found


def label(p: Params, s: State, writes: list[tuple[str, float]]) -> dict:
    """Counterfactual label for a (possibly multi-register) write at true state s."""
    base = hold_hazards(p, s)
    s_exec = copy.deepcopy(s)
    inst = []
    for name, value in writes:
        inst += apply_write(p, s_exec, name, value)
    after = inst + [h for h in hold_hazards(p, s_exec) if h not in inst]
    caused = [h for h in after if h not in base]
    return {"unsafe": bool(caused), "caused": caused, "preexisting": base}
