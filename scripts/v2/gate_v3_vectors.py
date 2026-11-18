"""Test vectors for gate_core_v3: frames plus expected decision and state signature from frames_v3.GateV3Model.

Line format (all hex):  dir t fcs len  fwd rule class  sig[0..16]  patch[0..6]  byte0 byte1 ...
Sources: (A) traffic recorded from closed-loop episodes with a pass-through gate (real polls, echoes, exceptions,
retransmits, bad checksums, reconnects); (B) directed fuzz around the table edges.
"""
from __future__ import annotations

import argparse
import collections
import random
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sysone.v2.agent_gate import closed_loop as C  # noqa: E402
from sysone.v2.agent_gate import frames as F  # noqa: E402
from sysone.v2.agent_gate import gate_v2 as G  # noqa: E402
from sysone.v2.agent_gate.frames_v3 import GateV3Model  # noqa: E402
from sysone.v2.agent_gate.frames import IP_A, IP_B, MAC_A, MAC_B, mbap, pdu_read, pdu_write6, pdu_write16  # noqa: E402

PATCHES = collections.Counter()
ETH_C2P = MAC_B + MAC_A
ETH_P2C = MAC_A + MAC_B


def eth(base, vlan):
    return base + (b"\x81\x00\x00\x05" if vlan else b"") + b"\x08\x00"


def emit(model, d, t, ok, f, out, cov):
    fwd, rule, cls = model.process(d, f, t, ok)
    cov[(d, rule)] += 1
    sig = model.signature()
    pf = model.patch_fields()
    PATCHES[pf[0]] += 1
    out.append(" ".join(f"{v:x}" for v in (d, t & 0xFFFFFFFF, int(ok), len(f), int(fwd), rule, cls, *sig, *pf)) +
               " " + " ".join(f"{b:02x}" for b in f))
    return model.patch is not None and model.patch["kind"] == 1


def recorded(model, out, cov, episodes):
    n = 0
    for sc in C.SCENARIOS:
        for k, task in enumerate(C.TASKS):
            for e in range(episodes):
                frames = []
                C.run_episode("none", 9000 + 17 * n + e, sc, task, careless=True,
                              poll_ms=(1000, 10000)[(k + e) % 2], tap=lambda d, f, t: frames.append((d, f, t)))
                for d, f, t in frames:
                    emit(model, d, t, True, f, out, cov)
                n += 1


def fuzz(model, out, cov, n, rng):
    port, seq = 40001, {}
    outstanding = []            # (port, txid, kind, addr, vals, fc, start, qty)
    t = rng.randint(0, 2**32 - 1) if rng.random() < 0.3 else 1000
    txid = 1

    def cframe(payload, bad_csum=False, vlan=False, p=None, flags=0x18):
        pp = p or port
        s = seq.setdefault(pp, 1000)
        return G.build(eth(ETH_C2P, vlan), IP_A, IP_B, pp, 502, s, 0, payload, flags=flags, corrupt_tcp=bad_csum)

    def pframe(payload, bad_csum=False, vlan=False, p=None, sport=502):
        return G.build(eth(ETH_P2C, vlan), IP_B, IP_A, sport, p or port, 5000, 0, payload, corrupt_tcp=bad_csum)

    def fix_ip_csum(f, vlan):
        b = bytearray(f)
        l3 = 18 if vlan else 14
        b[l3 + 10] ^= 0x5A                       # corrupt the IPv4 header checksum
        return bytes(b)

    def regs_for(kind):
        if kind == "lvl":
            return [rng.choice([-30, 0, 100, 149, 150, 349, 350, 399, 400, 749, 750, 850, rng.randint(0, 1000)]) & 0xFFFF,
                    rng.randint(200, 800), rng.randint(0, 150), rng.randint(0, 250)]
        return [rng.choice([0, 0, 15, 30, 50, 51, 60, 100, rng.randint(0, 65535)]) for _ in range(4)]

    for i in range(n):
        vlan = rng.random() < 0.08
        bad = rng.random() < 0.03
        t = (t + rng.choice([5, 10, 40, 120, 300, 900, 1999, 2000, 2001, 2002, 5000, 61000])) & 0xFFFFFFFF
        r = rng.random()
        if r < 0.03:
            port += 1                                           # a new client connection
            seq[port] = 1000
            emit(model, 0, t, True, cframe(b"", flags=0x10), out, cov)
            continue
        if r < 0.40:                                            # a write
            txid = (txid + 1) & 0xFFFF
            kind = rng.random()
            if kind < 0.6:
                addr = rng.choice([0, 1, 2, 3, 3, 4, 7])
                val = rng.choice([0, 0, 0, 10, 20, 30, 50, 60, 80, 100, 101, 65535, rng.randint(0, 120)])
                pdu, vals, fc = pdu_write6(addr, val), [val], 6
            else:
                qty = rng.choice([1, 2, 3, 4, 4, 5])
                addr = rng.choice([0, 0, 1, 2, 3])
                vals = [rng.choice([0, 0, 25, 50, 75, 100, 120]) for _ in range(qty)]
                pdu, fc = pdu_write16(addr, vals), 16
            adj = rng.random()
            if adj < 0.02:
                pdu = pdu_write16(addr, vals, bytecount_adjust=2) if fc == 16 else pdu
            f = cframe(mbap(txid, pdu), bad_csum=bad, vlan=vlan)
            if rng.random() < 0.02:
                f = fix_ip_csum(f, vlan)
            refused = emit(model, 0, t, rng.random() > 0.02, f, out, cov)
            if not bad:
                seq[port] = seq.get(port, 1000)
            outstanding.append((port, txid, "w", addr, vals, fc, refused))
            continue
        if r < 0.55:                                            # a read
            txid = (txid + 1) & 0xFFFF
            fc = rng.choice([3, 4])
            start, qty = rng.choice([(0, 4), (0, 4), (0, 4), (0, 1), (1, 2), (2, 2), (0, 8), (3, 1)])
            f = cframe(mbap(txid, pdu_read(fc, start, qty)), bad_csum=bad, vlan=vlan)
            emit(model, 0, t, True, f, out, cov)
            outstanding.append((port, txid, "r", start, [qty], fc, False))
            continue
        if r < 0.85 and outstanding:                            # a response to something outstanding
            k = rng.randrange(len(outstanding)) if rng.random() < 0.7 else len(outstanding) - 1
            p_, tx, kind, a0, vals, fc, refused = outstanding.pop(k)
            if kind == "w" and refused and rng.random() < 0.85:
                # what the PLC answers to a mutated (illegal-function) request, occasionally malformed
                pdu = struct.pack("!BB", 0xFF, rng.choice([1, 1, 1, 2])) + (b"\x00" if rng.random() < 0.05 else b"")
                emit(model, 1, t, True, pframe(mbap(tx, pdu), bad_csum=bad, vlan=vlan, p=p_), out, cov)
                continue
            if kind == "w":
                x = rng.random()
                if x < 0.70:
                    pdu = pdu_write6(a0, vals[0]) if fc == 6 else struct.pack("!BHH", 16, a0, len(vals))
                elif x < 0.80:
                    pdu = struct.pack("!BB", fc | 0x80, rng.choice([2, 3, 4, 6]))
                elif x < 0.90:
                    pdu = pdu_write6((a0 + 1) & 3, (vals[0] + 1) & 0xFFFF) if fc == 6 else struct.pack("!BHH", 16, a0, len(vals) + 1)
                else:
                    pdu = struct.pack("!BHH", fc, a0, 0)[:rng.choice([3, 5])]
                f = pframe(mbap(tx, pdu), bad_csum=bad, vlan=vlan, p=p_)
            else:
                qty = vals[0]
                good = rng.random() < 0.85
                regs = regs_for("lvl" if fc == 4 else "act")
                body = b"".join(struct.pack("!H", x) for x in (regs * 3)[:qty if good else max(1, qty - 1)])
                pdu = struct.pack("!BB", fc, len(body)) + body
                f = pframe(mbap(tx, pdu), bad_csum=bad, vlan=vlan, p=p_)
            emit(model, 1, t, rng.random() > 0.01, f, out, cov)
            continue
        if r < 0.90:                                            # unsolicited / stray response
            pdu = F.pdu_read_resp(rng.choice([3, 4]), regs_for(rng.choice(["lvl", "act"])))
            if rng.random() < 0.3:
                pdu = struct.pack("!BB", 0xFF, 1)
            emit(model, 1, t, True, pframe(mbap(rng.randint(0, 65535), pdu), vlan=vlan), out, cov)
            continue
        if 0.92 <= r < 0.935:                                   # fill the pending table with risk-reducing writes
            for j in range(rng.choice([8, 9, 10])):
                txid = (txid + 1) & 0xFFFF
                a = rng.choice([0, 1, 3])
                emit(model, 0, t + j, True, cframe(mbap(txid, pdu_write6(a, 0))), out, cov)
                outstanding.append((port, txid, "w", a, [0], 6, False))
            txid = (txid + 1) & 0xFFFF
            emit(model, 0, t + 11, True, cframe(mbap(txid, pdu_write6(2, rng.choice([20, 40, 60])))), out, cov)
            continue
        if r < 0.95:                                            # other function codes
            txid = (txid + 1) & 0xFFFF
            pdu = rng.choice([struct.pack("!BHH", 5, 0, 0xFF00), struct.pack("!B", 8) + b"\0\0\0\0",
                              struct.pack("!BHH", 1, 0, 8), struct.pack("!BHH", 43, 14, 0)])
            emit(model, 0, t, True, cframe(mbap(txid, pdu), vlan=vlan), out, cov)
            continue
        for d, f, tt, ok in F.edge_frames(rng, txid, t):         # structural edge cases
            emit(model, d, tt, ok, f, out, cov)
        txid += 10


def lvl_bounds(V, lvl, inl, pump, outl, age):
    inl, pump, outl = min(inl, 100), min(pump, 100), min(outl, 100)
    age = min(age, V.AGE_MAX_MS)
    rise = -(-(inl * age * V.RISE_K) // (1 << V.RISE_SH))
    fall = (pump * V.SQRT100[outl] * age * V.FALL_K) >> V.FALL_SH
    return max(lvl - fall, -100), min(lvl + rise, 1100)


def first_age(pred, hi=70000):
    """Smallest age (ms) for which pred(age) is true, or None (pred monotone in age)."""
    if not pred(hi):
        return None
    lo = 0
    while lo < hi:
        mid = (lo + hi) // 2
        if pred(mid):
            hi = mid
        else:
            lo = mid + 1
    return lo


def boundary_probes(model, out, cov, rng, n):
    """Directed vectors: writes 1 ms either side of the exact age at which the level interval crosses a rule
    threshold, so the integer interval arithmetic and the age clamp are pinned down bit for bit."""
    from sysone.v2.agent_gate import gate_v3 as V
    t = 5000
    txid = 100

    def send(d, payload, ok=True, base_t=None):
        pass

    def cf(payload, port=40001):
        return G.build(eth(ETH_C2P, False), IP_A, IP_B, port, 502, 1000, 0, payload)

    def pf(payload, port=40001):
        return G.build(eth(ETH_P2C, False), IP_B, IP_A, 502, port, 5000, 0, payload)

    def setup(lvl, acts, t0):
        nonlocal txid
        txid += 1
        emit(model, 0, t0, True, cf(mbap(txid, pdu_read(4, 0, 4))), out, cov)
        emit(model, 1, t0, True, pf(mbap(txid, F.pdu_read_resp(4, [lvl & 0xFFFF, 250, 0, 0]))), out, cov)
        txid += 1
        emit(model, 0, t0, True, cf(mbap(txid, pdu_read(3, 0, 4))), out, cov)
        emit(model, 1, t0, True, pf(mbap(txid, F.pdu_read_resp(3, acts))), out, cov)

    def probe(addr, val, t0, age):
        nonlocal txid
        txid += 1
        tw = (t0 + age) & 0xFFFFFFFF
        emit(model, 0, tw, True, cf(mbap(txid, pdu_write6(addr, val))), out, cov)
        # if it was forwarded, release the pending entry with an exception so state stays comparable
        emit(model, 1, tw, True, pf(mbap(txid, struct.pack("!BB", 6 | 0x80, 4))), out, cov)

    cases = []
    for _ in range(n):
        kind = rng.choice(["heater", "r1", "r7", "inlet", "heater_clamp", "r1_clamp"])
        if kind == "heater":      # R4_LOW: heater write when the lower level bound drops below 35.0 %
            pump = rng.choice([20, 40, 60, 80, 100]); outl = rng.randint(max(15, pump), 100)
            lvl = rng.randint(352, 900)
            cases.append((kind, lvl, [0, pump, outl, 0], 3, 40,
                          lambda age, lvl=lvl, pump=pump, outl=outl: lvl_bounds(V, lvl, 0, pump, outl, age)[0] < 350))
        elif kind == "r1":        # R1: pump increase at a running pump when the lower bound drops below 15.0 %
            pump = rng.choice([20, 30, 40]); outl = rng.randint(15, 100)
            lvl = rng.randint(152, 500)
            cases.append((kind, lvl, [0, pump, outl, 0], 1, pump + 5,
                          lambda age, lvl=lvl, pump=pump, outl=outl: lvl_bounds(V, lvl, 0, pump, outl, age)[0] < 150))
        elif kind == "r7":        # R7: fast pump (>50 %) when the lower bound drops below 40.0 %
            pump = rng.choice([55, 60, 70]); outl = rng.randint(80, 100)
            lvl = rng.randint(402, 700)
            cases.append((kind, lvl, [0, pump, outl, 0], 1, 80,
                          lambda age, lvl=lvl, pump=pump, outl=outl: lvl_bounds(V, lvl, 0, pump, outl, age)[0] < 400))
        elif kind == "inlet":     # R5: inlet >= 50 when the upper bound reaches 75.0 %
            inl = rng.choice([10, 20, 30, 40]); lvl = rng.randint(600, 745)
            cases.append((kind, lvl, [inl, 0, 0, 0], 0, 60,
                          lambda age, lvl=lvl, inl=inl: lvl_bounds(V, lvl, inl, 0, 0, age)[1] >= 750))
        elif kind == "heater_clamp":   # age clamp: crossing exactly at the 60 s clamp
            for _try in range(4000):
                pump = rng.choice([20, 30, 40, 60]); outl = rng.randint(max(15, pump), 100); lvl = rng.randint(352, 1100)
                if (lvl_bounds(V, lvl, 0, pump, outl, 59999)[0] >= 350) and (lvl_bounds(V, lvl, 0, pump, outl, 60000)[0] < 350):
                    cases.append((kind, lvl, [0, pump, outl, 0], 3, 40,
                                  lambda age, lvl=lvl, pump=pump, outl=outl: lvl_bounds(V, lvl, 0, pump, outl, age)[0] < 350))
                    break
        else:                          # r1_clamp
            for _try in range(4000):
                pump = rng.choice([20, 30, 40]); outl = rng.randint(15, 100); lvl = rng.randint(152, 400)
                if (lvl_bounds(V, lvl, 0, pump, outl, 59999)[0] >= 150) and (lvl_bounds(V, lvl, 0, pump, outl, 60000)[0] < 150):
                    cases.append((kind, lvl, [0, pump, outl, 0], 1, pump + 5,
                                  lambda age, lvl=lvl, pump=pump, outl=outl: lvl_bounds(V, lvl, 0, pump, outl, age)[0] < 150))
                    break
    for kind, lvl, acts, addr, val, pred in cases:
        a = first_age(pred)
        if a is None:
            continue
        t0 = (t + rng.randint(0, 1000)) & 0xFFFFFFFF
        t = (t + 70000 + 5000) & 0xFFFFFFFF
        setup(lvl, acts, t0)
        for age in sorted({max(0, a - 2), max(0, a - 1), a, a + 1, a + 2, 59999, 60000, 60001}):
            probe(addr, val, t0, age)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "simulation/v2/gate/vectors/gate_v3_frames.txt"))
    ap.add_argument("--episodes", type=int, default=1)
    ap.add_argument("--fuzz", type=int, default=60000)
    ap.add_argument("--probes", type=int, default=400)
    args = ap.parse_args()
    out, cov, fz = [], collections.Counter(), []
    recorded(GateV3Model(), out, cov, args.episodes)
    fuzz(GateV3Model(), fz, cov, args.fuzz, random.Random(31))
    base = Path(args.out)
    base.parent.mkdir(parents=True, exist_ok=True)
    # two files: each simulation starts from reset, like the fresh model it was generated with
    base.with_name(base.stem + "_rec.txt").write_text("\n".join(out) + "\n")
    base.with_name(base.stem + "_fuzz.txt").write_text("\n".join(fz) + "\n")
    pr = []
    boundary_probes(GateV3Model(), pr, cov, random.Random(77), args.probes)
    base.with_name(base.stem + "_probe.txt").write_text("\n".join(pr) + "\n")
    from sysone.v2.agent_gate.gate_v2 import NAMES
    print(f"{len(out)} recorded + {len(fz)} fuzz + {len(pr)} probe frames")
    rules = collections.Counter()
    for (d, rule), c in cov.items():
        rules[rule] += c
    print("rule coverage:", {NAMES.get(k, k): v for k, v in sorted(rules.items())})
    print("patches (0 none, 1 request mutated, 2 response restored):", dict(PATCHES))


if __name__ == "__main__":
    main()
