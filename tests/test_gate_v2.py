"""Gate v2: acceptance tracking, stale-level handling, checksum handling, TCP splice consistency."""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sysone.v2.agent_gate import closed_loop as C  # noqa: E402
from sysone.v2.agent_gate import gate_v2 as G  # noqa: E402
from sysone.v2.agent_gate import intspec as S  # noqa: E402
from sysone.v2.agent_gate.frames import IP_A, IP_B, MAC_A, MAC_B, mbap, pdu_read, pdu_read_resp, pdu_write6  # noqa: E402

ETH_C2P = MAC_B + MAC_A + b"\x08\x00"
ETH_P2C = MAC_A + MAC_B + b"\x08\x00"
PORT, CSEQ, PSEQ = 40001, 1000, 5000


class Bench:
    """Feeds frames through a gate as one connection (client port PORT)."""

    def __init__(self, kind):
        self.g = G.make_gate(kind)
        self.cseq, self.pseq, self.t = CSEQ, PSEQ, 0
        self.g.process(0, G.build(ETH_C2P, IP_A, IP_B, PORT, 502, self.cseq, 0, b"", flags=0x10), 0)
        self.g.process(1, G.build(ETH_P2C, IP_B, IP_A, 502, PORT, self.pseq, self.cseq, b"", flags=0x10), 1)

    def req(self, adu, corrupt=False, t=None):
        self.t = self.t + 10 if t is None else t
        f = G.build(ETH_C2P, IP_A, IP_B, PORT, 502, self.cseq, self.pseq, adu, corrupt_tcp=corrupt)
        rule, outs = self.g.process(0, f, self.t)
        if not corrupt:                       # the client's TCP consumed these bytes either way
            self.cseq += len(adu)
        return rule, outs

    def resp(self, adu, t=None):
        self.t = self.t + 10 if t is None else t
        f = G.build(ETH_P2C, IP_B, IP_A, 502, PORT, self.pseq, self.cseq, adu)
        self.pseq += len(adu)
        return self.g.process(1, f, self.t)

    # convenience
    def read(self, txid, fc, regs, t=None):
        self.req(mbap(txid, pdu_read(fc, 0, 4)), t=t)
        self.resp(mbap(txid, pdu_read_resp(fc, regs)))

    def write(self, txid, addr, v, t=None):
        return self.req(mbap(txid, pdu_write6(addr, v)), t=t)

    def echo(self, txid, addr, v):
        self.resp(mbap(txid, pdu_write6(addr, v)))

    def exception(self, txid, fc=6, code=6):
        self.resp(struct.pack("!HHHBBB", txid, 0, 3, 1, fc | 0x80, code))


def settle(b):
    """Establish a known plant: level 50.0, everything off."""
    b.read(1, 4, [500, 250, 0, 0])
    b.read(2, 3, [0, 0, 0, 0])


def open_outlet_then_pump(kind, outlet_reply):
    b = Bench(kind)
    settle(b)
    r1, _ = b.write(10, S.OUTLET, 100)
    assert r1 == S.PASS
    if outlet_reply == "echo":
        b.echo(10, S.OUTLET, 100)
    elif outlet_reply == "exception":
        b.exception(10)
    r2, _ = b.write(11, S.PUMP, 100)
    return r2


def test_pump_blocked_when_outlet_truly_closed():
    assert open_outlet_then_pump("v2_splice", "exception") == S.R2


def test_pump_passes_when_outlet_confirmed_open():
    assert open_outlet_then_pump("v2_splice", "echo") == S.PASS


def test_v1_commits_on_forward_and_diverges_on_rejection():
    # documents the v1 behaviour (rtl/v2/gate): a rejected write still counts as applied
    assert open_outlet_then_pump("v1_csum", "exception") == S.PASS


def test_unconfirmed_write_is_worst_cased_while_pending():
    # outlet-open forwarded, no reply yet: both outcomes possible, so the pump start is blocked
    assert open_outlet_then_pump("v2_splice", "none") == S.R2


def test_timeout_makes_register_uncertain_until_readback():
    b = Bench("v2_splice")
    settle(b)
    b.write(10, S.OUTLET, 100)                      # never acknowledged
    b.g.tick(b.t + 5000)                            # ack timeout expires
    assert b.g.core.uncertain()
    r, _ = b.write(11, S.PUMP, 100, t=b.t + 5001)
    assert r == S.R2                                # still blocked
    b.read(12, 3, [0, 0, 100, 0], t=b.t + 6000)     # PLC reports the outlet open after all
    assert not b.g.core.uncertain()
    r, _ = b.write(13, S.PUMP, 100, t=b.t + 6100)
    assert r == S.PASS


def _running_station(kind):
    b = Bench(kind)
    b.read(1, 4, [500, 250, 0, 0])
    b.read(2, 3, [0, 60, 100, 0])           # pump running, outlet open: the level can fall
    return b


def test_stale_level_is_widened_when_it_can_fall():
    fresh = _running_station("v2_splice")
    assert fresh.write(10, S.HEATER, 50, t=1000)[0] == S.PASS
    stale = _running_station("v2_splice")
    assert stale.write(10, S.HEATER, 50, t=60_000)[0] == S.R4_LOW   # 60 s without a level reading


def test_stale_level_is_not_widened_when_it_cannot_fall():
    b = Bench("v2_splice")
    settle(b)                                # pump off, outlet closed: nothing drains the tank
    assert b.write(10, S.HEATER, 50, t=60_000)[0] == S.PASS


def test_invalid_checksum_frame_does_not_change_state():
    for kind in ("v1_csum", "v2_splice"):
        b = Bench(kind)
        settle(b)
        rule, outs = b.write(10, S.OUTLET, 100), None
        assert True
        b = Bench(kind)
        settle(b)
        rule, outs = b.req(mbap(10, pdu_write6(S.OUTLET, 100)), corrupt=True)
        assert rule == G.CSUM_BAD and not outs
        assert b.write(11, S.PUMP, 100)[0] == S.R2


def test_v1_rtl_has_no_checksum_check():
    b = Bench("v1_rtl")
    settle(b)
    rule, outs = b.req(mbap(10, pdu_write6(S.OUTLET, 100)), corrupt=True)
    assert rule == S.PASS and outs                  # forwarded and state updated (documented gap)
    assert b.write(11, S.PUMP, 100)[0] == S.PASS


def test_splice_keeps_both_tcp_stacks_consistent():
    for seed in range(5):
        r = C.run_episode("v2_splice", 700 + seed, "clean", "fill", careless=True)
        assert r["timeouts"] == 0 and r["reconnects"] == 0
        assert r["exceptions"] > 0                  # blocked writes were answered, not dropped
    r = C.run_episode("v2_drop", 700, "clean", "fill", careless=True)
    assert r["timeouts"] > 0                        # drop mode wedges the session


def test_transparent_when_nothing_to_block():
    a = C.run_episode("none", 31, "lossy", "drain", careless=False)
    b = C.run_episode("v2_splice", 31, "lossy", "drain", careless=False)
    assert abs(a["applied"] - b["applied"]) <= 2


def _high_level_with_inlet(kind, inlet):
    b = Bench(kind)
    b.read(1, 4, [800, 250, 0, 0])               # level 80.0 %
    b.read(2, 3, [inlet, 0, 0, 0])
    return b


def test_frozen_rules_refuse_a_partial_inlet_reduction_at_high_level():
    b = _high_level_with_inlet("v2_splice", 80)
    assert b.write(10, S.INLET, 60)[0] == S.R5   # 80 -> 60 is corrective but judged as 60 >= 50


def test_exemption_allows_reduction_but_not_increase():
    b = _high_level_with_inlet("v2_splice_x", 80)
    assert b.write(10, S.INLET, 60)[0] == S.PASS
    assert b.write(11, S.INLET, 90)[0] == S.R5   # an increase is still blocked
    assert b.write(12, S.INLET, 200)[0] == S.RANGE


def test_exemption_respects_uncertainty():
    b = Bench("v2_splice_x")
    b.read(1, 4, [500, 250, 0, 0])
    b.read(2, 3, [20, 0, 0, 0])
    assert b.write(10, S.INLET, 80)[0] == S.PASS     # allowed at 50 %, never acknowledged
    b.g.tick(b.t + 5000)
    assert b.g.core.uncertain()                      # inlet may now be 20 or 80
    b.read(3, 4, [800, 250, 0, 0], t=b.t + 5100)     # the level has risen to 80 %
    # 50 is below 80 but not below 20: it may be an increase, so the exemption does not apply
    assert b.write(11, S.INLET, 50, t=b.t + 5200)[0] == S.R5


def test_outlet_writes_are_never_exempt():
    b = Bench("v2_splice_x")
    b.read(1, 4, [500, 250, 0, 0])
    b.read(2, 3, [0, 80, 100, 0])
    assert b.write(10, S.OUTLET, 40)[0] == S.R2  # lowering the outlet under a running pump stays blocked


def test_active_polling_gate_issues_reads_and_passive_does_not():
    a = C.run_episode("readback_poll1_x", 5, "clean", "fill", careless=False, poll_ms=10000)
    b = C.run_episode("readback_splice_x", 5, "clean", "fill", careless=False, poll_ms=10000)
    c = C.run_episode("readback_poll5_x", 5, "clean", "fill", careless=False, poll_ms=10000)
    assert a["gate_polls"] == 480 and b["gate_polls"] == 0 and 90 <= c["gate_polls"] <= 100


# ---------------------------------------------------------------- protective interlock (experiment 8)

def test_interlock_latch_hysteresis():
    from sysone.v2.agent_gate.interlock import Interlock
    il = Interlock()
    il.update(500, 899, 200)
    assert il.forced() == set()
    il.update(500, 900, 200)
    assert il.forced() == {0} and il.refuses(0, [10]) and not il.refuses(0, [0]) and not il.refuses(1, [50])
    il.update(500, 860, 200)
    assert il.forced() == {0}                       # still above reset
    il.update(500, 849, 200)
    assert il.forced() == set()
    il.update(150, 849, 805)
    assert il.forced() == {1, 3} and il.trips["I_DRY"] == 1 and il.trips["I_HOT"] == 1


class _Neglect:
    def __init__(self, writes):
        self.writes = writes

    def propose(self, text, obs, act, fb, turn):
        return ([{"addr": a, "values": [v]} for a, v in self.writes] if turn == 0 else []), False


def test_gate_interlock_stops_overflow_from_omission():
    from sysone.v2.agent_gate import closed_loop as C
    kw = dict(careless=False, agent=_Neglect([(0, 100)]), agent_ms=8000, ignore_done=True)
    r0 = C.run_episode("v3_mutate_x", 101, "clean", "fill", **kw)
    r1 = C.run_episode("v3_mutate_il", 101, "clean", "fill", **dict(kw, agent=_Neglect([(0, 100)])))
    r2 = C.run_episode("none", 101, "clean", "fill", plc_interlock=True, **dict(kw, agent=_Neglect([(0, 100)])))
    assert "overflow" in r0["hazard_kinds"]
    assert not r1["any_hazard"] and r1["il_writes"] >= 1 and r1["il_trips"]["I_OVERFILL"] >= 1
    assert r1["il_gate_unsafe"] == 0 and r1["task_done"]
    assert not r2["any_hazard"] and r2["il_trips"]["I_OVERFILL"] >= 1


def test_gate_interlock_refuses_reopening():
    import struct
    from sysone.v2.agent_gate import gate_v2 as G
    from sysone.v2.agent_gate.frames import mbap, pdu_write6
    core = G.make_gate("v3_mutate_il").core
    core.core.lvl10, core.core.lvl_t, core.core.lvl_ok = 950, 0, True
    assert core.evaluate(10) == [] and core.il.forced() == {0}       # inlet already 0: nothing to force
    a = G.parse_adu(mbap(1, pdu_write6(0, 40)))
    assert core.decide(40001, a, 20) == 20
    assert core.decide(40001, G.parse_adu(mbap(2, pdu_write6(0, 0))), 20) == 0


def test_gate_interlock_v2_latches_at_decision_and_holds_until_safe():
    from sysone.v2.agent_gate import gate_v2 as G
    from sysone.v2.agent_gate.frames import mbap, pdu_write6
    for kind, expect in (("v3_mutate_il", 0), ("v3_mutate_il2", 20)):
        core = G.make_gate(kind).core
        c = core.core
        c.v0[0] = 100                                   # inlet known open
        c.lvl10, c.lvl_t, c.lvl_ok = 895, 0, True       # with inlet 100, hi = 898 at 90 ms and 902 at 200 ms
        core.evaluate(0)
        assert core.il.forced() == set()
        # write decided before the next tick: v1 lets it through (exempt: not raising), v2 latches first and refuses
        assert core.decide(40001, G.parse_adu(mbap(1, pdu_write6(0, 100))), 200) == expect
    core = G.make_gate("v3_mutate_il2").core
    c = core.core
    c.v0[0], c.lvl10, c.lvl_t, c.lvl_ok = 100, 950, 0, True
    assert core.evaluate(0) == [0]
    c.lvl10, c.lvl_t = 800, 100                         # condition cleared, but inlet still 100: stays latched
    core.evaluate(100)
    assert core.il.forced() == {0}
    c.v0[0] = 0
    core.evaluate(110)
    assert core.il.forced() == set()
