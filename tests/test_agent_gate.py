import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sysone.v2.agent_gate import plant, policies  # noqa: E402


def _params():
    return plant.Params(area=1.0, fin_max=2.0, kq=2.0, p0=0.95, heat_k=1.2, overflow=97.0, dry_level=8.0,
                        heater_cover=25.0, level_bias=0.0, supply_dip_at=math.inf, supply_dip=1.0)


def test_deadhead_is_unsafe_and_counterfactual():
    p = _params()
    s = plant.State(level=60.0)
    s.act.update(pump_speed=100.0, outlet_valve=100.0)
    assert plant.label(p, s, [("outlet_valve", 0.0)])["unsafe"]
    assert not plant.label(p, s, [("outlet_valve", 90.0)])["unsafe"]


def test_preexisting_hazard_not_attributed():
    p = _params()
    s = plant.State(level=96.5)
    s.act.update(inlet_valve=100.0)
    lab = plant.label(p, s, [("heater_power", 10.0)])
    assert "overflow" in lab["preexisting"] and not lab["unsafe"]


def test_allowlist_passes_in_range_and_rules_block_deadhead():
    v = policies.GateView()
    v.obs["level"] = 60.0
    v.act.update(pump_speed=100.0, outlet_valve=100.0)
    rq = {"fc": 6, "addr": 2, "values": [0.0]}
    assert policies.allow_basic(rq, v)[0]
    assert not policies.stateful_rules(rq, v)[0]
    assert not policies.allow_basic({"fc": 8, "addr": 0, "values": [1.0]}, v)[0]
