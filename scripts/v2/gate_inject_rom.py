"""Build the loopback-test injector ROM and the exact status counters it must produce.

In the loopback test build both PHYs are in MII loopback.  A frame injected on port P
returns on P's receiver (direction 0 for A, 1 for B), is judged by the gate, and if
forwarded leaves through the other port, loops back and is judged again in the other
direction.  Frames whose second pass would be forwarded again (ARP) would circulate
forever, so ARP is excluded.  All injections happen within milliseconds, so every
decision uses t = 0 (the R6 window is 60 s).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sysone.v2.agent_gate import frames as F  # noqa: E402

ROM_BYTES = 32768


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "build/v2/agent-gate-bridge/inject"))
    ap.add_argument("--run", default="agent-gate-gonogo-4b-20261108")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    recs = [json.loads(l) for l in open(ROOT / "build/v2" / args.run / "decisions.jsonl")]
    recs = [r for r in recs if r["source"] == "llm"]
    rng = random.Random(11)
    rom = bytearray()
    frames = []
    for d, fr, t, ok in F.episode_traffic(recs, rng):
        if fr[12:14] == b"\x08\x06":
            continue                        # ARP would circulate forever in loopback
        need = 4 + len(fr)
        if len(rom) + need + 1 > ROM_BYTES:
            break
        rom += bytes([d | (2 if ok else 0), len(fr) >> 8, len(fr) & 0xFF, 0]) + fr
        frames.append((d, fr, ok))
    rom += b"\xff"
    rom += b"\x00" * (ROM_BYTES - len(rom))
    (out / "gate_inject_rom.hex").write_text("\n".join(f"{b:02x}" for b in rom) + "\n")

    # expected counters
    m = F.GateModel()
    rule = [0] * 16
    loaded, fwd, drop, tx = [0, 0], [0, 0], [0, 0], [0, 0]
    rx_frames, rx_bad = [0, 0], [0, 0]
    for d, fr, ok in frames:
        rx_frames[d] += 1
        rx_bad[d] += int(not ok)
        f1, r1, _ = m.process(d, fr, 0, ok)
        loaded[d] += 1
        rule[r1] += 1
        if not f1:
            drop[d] += 1
            continue
        fwd[d] += 1
        tx[d] += 1
        o = 1 - d                           # loops back on the other port
        rx_frames[o] += 1
        f2, r2, _ = m.process(o, fr, 0, True)
        loaded[o] += 1
        rule[r2] += 1
        if f2:
            raise SystemExit(f"frame would circulate: second pass forwarded (rule {r2})")
        drop[o] += 1
    exp = {
        "frames_injected": len(frames),
        "status": {
            "2": rx_frames[0], "3": rx_bad[0], "4": 0, "5": rx_frames[1], "6": rx_bad[1], "7": 0,
            "8": loaded[0], "9": fwd[0], "10": drop[0], "11": tx[0],
            "12": loaded[1], "13": fwd[1], "14": drop[1], "15": tx[1],
            **{str(32 + i): rule[i] for i in range(16)},
        },
        "final_lvl10": m.lvl10, "final_act": m.act,
    }
    (out / "expected.json").write_text(json.dumps(exp, indent=2))
    print(json.dumps({"frames": len(frames), "rom_used": len(rom.rstrip(b'\x00')),
                      "rule_hist": rule, "fwd": fwd, "drop": drop}))


if __name__ == "__main__":
    main()
