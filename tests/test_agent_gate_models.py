"""The ADU-level software gate (Linux baseline) and the frame-level reference model (what
the RTL implements) must make identical decisions on the same Modbus traffic."""
import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sysone.v2.agent_gate import frames as F  # noqa: E402
from sysone.v2.agent_gate import modbus as M  # noqa: E402

RUN = ROOT / "build/v2/agent-gate-gonogo-4b-20261108/decisions.jsonl"


@pytest.mark.skipif(not RUN.exists(), reason="go/no-go run not present")
def test_software_gate_matches_frame_model(monkeypatch):
    recs = [json.loads(l) for l in open(RUN)]
    recs = [r for r in recs if r["source"] == "llm"][:800]
    fm = F.GateModel()
    sg = M.SoftwareGate()
    monkeypatch.setattr(sg, "t_ms", lambda: 0)
    n = 0
    for d, fr, t, ok in F.episode_traffic(recs, random.Random(3)):
        if not ok:
            continue
        fwd, rule, cls = fm.process(d, fr, 0, ok)
        if cls not in (F.CLASS_READ, F.CLASS_WRITE, F.CLASS_RESP, F.CLASS_OTHERFC):
            continue                        # framing/IP-level classes have no ADU-level twin
        l3 = 18 if fr[12:14] == b"\x81\x00" else 14
        ihl = (fr[l3] & 15) * 4
        tcp = l3 + ihl
        p = tcp + (fr[tcp + 12] >> 4) * 4
        total = int.from_bytes(fr[l3 + 2:l3 + 4], "big")
        adu = fr[p:l3 + total]
        if d == 0:
            assert sg.request(adu) == rule, (n, rule)
        else:
            sg.response(adu)
        n += 1
    assert n > 1000
    assert sg.act == fm.act and sg.lvl10 == fm.lvl10
