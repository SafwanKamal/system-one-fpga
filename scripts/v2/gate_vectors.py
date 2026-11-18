"""Write RTL test vectors for the agent gate from recorded go/no-go decisions.

  gate_rules_vectors.txt : one line per decision, integer inputs + expected rule code
  plus extra randomized vectors near rule thresholds.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sysone.v2.agent_gate import intspec as S  # noqa: E402

RUNS = ["agent-gate-gonogo-20261108", "agent-gate-gonogo-4b-20261108"]


def line(x: dict, rule: int) -> str:
    vals = (x["vals"] + [0, 0, 0, 0])[:4]
    f = [x["fc"], x["addr"], min(len(x["vals"]), 4), int(x["nvals_raw"] > 4), *vals,
         x["lvl10"] & 0xFFFF, *x["act"], x["t_ms"], *x["starts"], rule]
    return " ".join(f"{v:x}" for v in f)


def random_vector(rng: random.Random) -> dict:
    fc = rng.choice([1, 2, 3, 4, 5, 6, 6, 6, 8, 15, 16, 16, 43])
    n = rng.choice([1, 1, 1, 2, 3, 4]) if fc in (6, 16) else 1
    if fc == 6:
        n = 1
    addr = rng.choice([0, 1, 2, 3, 3, 4, 7, 65535])
    edge = [0, 1, 14, 15, 16, 29, 30, 31, 49, 50, 51, 99, 100, 101, 65535]
    vals = [rng.choice(edge + [rng.randint(0, 100)]) for _ in range(n)]
    lvl = rng.choice([-20, 0, 149, 150, 151, 349, 350, 399, 400, 749, 750, 849, 850, rng.randint(-20, 1000)])
    act = [rng.choice([0, 0, 15, 30, 50, 51, 60, 100]) for _ in range(4)]
    t = rng.randint(0, 2**32 - 1)
    starts = sorted((t - rng.choice([0, 1, 59999, 60000, 60001, 120000])) & 0xFFFFFFFF
                    for _ in range(rng.randint(0, 4)))
    starts = starts + [S.NO_START] * (4 - len(starts))
    return {"fc": fc, "addr": addr, "vals": vals, "nvals_raw": n + (1 if rng.random() < 0.02 else 0),
            "lvl10": lvl, "act": act, "t_ms": t, "starts": starts}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "simulation/v2/gate/vectors"))
    ap.add_argument("--random", type=int, default=50000)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    lines, n_rec = [], 0
    for run in RUNS:
        for l in open(ROOT / "build/v2" / run / "decisions.jsonl"):
            r = json.loads(l)
            x = S.vector_from_record(r)
            rule = S.decide_vector(x)
            assert (rule == S.PASS) == r["decisions"]["stateful_rules"]["allow"]
            lines.append(line(x, rule))
            n_rec += 1
    rng = random.Random(8)
    for _ in range(args.random):
        x = random_vector(rng)
        lines.append(line(x, S.decide_vector(x)))
    (out / "gate_rules_vectors.txt").write_text("\n".join(lines) + "\n")

    # frame-level traffic for gate_core, with expected decisions from the reference model
    from sysone.v2.agent_gate import frames as F
    model = F.GateModel()
    frng = random.Random(9)
    flines, stats = [], {"frames": 0, "forward": 0, "writes": 0, "write_denied": 0}
    for run in RUNS:
        recs = [json.loads(l) for l in open(ROOT / "build/v2" / run / "decisions.jsonl")]
        recs = [r for r in recs if r["source"] in ("llm", "operator")]
        for d, fr, t, ok in F.episode_traffic(recs, frng):
            fwd, rule, cls = model.process(d, fr, t, ok)
            flines.append(" ".join(f"{v:x}" for v in (d, t, int(ok), len(fr), int(fwd), rule, cls)) +
                          " " + " ".join(f"{b:02x}" for b in fr))
            stats["frames"] += 1
            stats["forward"] += int(fwd)
            if cls == F.CLASS_WRITE:
                stats["writes"] += 1
                stats["write_denied"] += int(not fwd)
    (out / "gate_frames.txt").write_text("\n".join(flines) + "\n")

    # board-level bridge traffic: the bridge uses its own millisecond clock, which stays at
    # 0 in simulation (MS_DIV set huge), so expectations are recomputed with t = 0.
    bmodel = F.GateModel()
    brng = random.Random(10)
    blines = []
    recs = [json.loads(l) for l in open(ROOT / "build/v2" / RUNS[1] / "decisions.jsonl")]
    recs = [r for r in recs if r["source"] == "llm"][:700]
    for d, fr, t, ok in F.episode_traffic(recs, brng):
        fwd, rule, cls = bmodel.process(d, fr, 0, ok)
        blines.append(" ".join(f"{v:x}" for v in (d, 0, int(ok), len(fr), int(fwd), rule, cls)) +
                      " " + " ".join(f"{b:02x}" for b in fr))
    (out / "gate_bridge_frames.txt").write_text("\n".join(blines) + "\n")
    stats["bridge_frames"] = len(blines)
    print(json.dumps({"recorded": n_rec, "random": args.random, "total": len(lines), **stats}))


if __name__ == "__main__":
    main()
