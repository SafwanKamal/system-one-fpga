"""Closed-loop gate comparison without an oracle (pre-registered).

  python scripts/v2/run_agent_gate_closed_loop.py --out build/v2/agent-gate-closedloop-20261108

Writes prereg.json first (hypotheses, decision rules, seeds, SHA-256 of the code under test).
A re-run refuses to continue if any hashed file changed after the pre-registration.
Then runs every gate on identical stimulus (same plant parameters, same client behaviour,
same fault schedule per seed) and writes results.jsonl, summary.json and report.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sysone.v2.agent_gate import closed_loop as C  # noqa: E402
from sysone.v2.agent_gate import gate_v2 as G  # noqa: E402

HASHED = ["src/sysone/v2/agent_gate/gate_v2.py", "src/sysone/v2/agent_gate/closed_loop.py",
          "src/sysone/v2/agent_gate/intspec.py", "src/sysone/v2/agent_gate/plant.py",
          "src/sysone/v2/agent_gate/sources.py", "src/sysone/v2/agent_gate/frames.py",
          "scripts/v2/run_agent_gate_closed_loop.py"]
N_SEEDS = 30
SEED0 = 1000                      # fresh: exploratory runs used seeds 100-102 only
STRESSED = ["lossy", "outage", "plc_local", "combined"]

PREREG = {
    "question": "Under uncertain command acceptance and stale observations, does tracking what the "
                "PLC accepted (v2) reduce hazards caused by applied writes, relative to gates that "
                "assume forwarded writes were applied or that track only read-back state, without "
                "making the station unusable?",
    "design": {
        "episode_s": C.EPISODE_S, "n_seeds": N_SEEDS, "seed0": SEED0, "tasks": C.TASKS,
        "scenarios": C.SCENARIOS, "gates": G.ALL_GATES, "stressed_scenarios": STRESSED,
        "sources": "scripted operator (small safe steps) + careless source (random in-range writes "
                   "every ~7 s with p=0.5); no LLM in this experiment",
        "plant_oracle": "none: the plant advances only on writes the PLC received intact and accepted",
        "ground_truth": "hazards from plant physics; each applied write is counterfactually labelled "
                        "(plant.label, 10 s hold horizon) at the moment it is applied",
    },
    "metrics": {
        "primary": "unsafe_applied per episode (writes applied that cause a hazard counterfactually)",
        "secondary": ["hazard-episode rate", "task completion rate", "write availability "
                      "(write_ok / write_requests)", "application timeouts per episode"],
    },
    "hypotheses": {
        "H1_tracking": "Pooled over stressed scenarios, v2_splice has fewer unsafe_applied/episode "
                       "than v1_csum_splice. PASS if the paired-bootstrap 95% CI of (v2 - v1) is < 0.",
        "H2_vs_readback": "Same comparison of v2_splice against readback_splice (a state-invariant "
                          "gate that does not track commands). Reported either way; no claim unless the "
                          "CI is < 0.",
        "H3_splice": "v2_splice vs v2_drop (same decisions): application timeouts per episode reduced by "
                     ">= 50% and task completion rate not lower. PASS if both hold, pooled over all scenarios.",
        "H4_usable": "Pooled over all scenarios, task completion of v2_splice is within 5 points of "
                     "'none' (no gate) and within 5 points of oracle_state.",
        "H5_deployed_v1": "v1_rtl (the RTL as built) compared with v2_splice on unsafe_applied/episode and "
                          "timeouts; descriptive.",
    },
    "attribution": "oracle_state (same rules, true plant state) bounds what the rule set achieves; "
                   "hazards under oracle_state are rule-coverage gaps, not tracking errors.",
    "analysis": "paired by (scenario, task, seed); bootstrap 5000 resamples, seed 0; "
                "Wilson intervals for rates. All gate/scenario cells are reported, including negative results.",
    "caveats": ["scripted sources, not LLM agents", "one plant model", "TCP modelled at byte level, "
                "no handshake or window dynamics", "latency not modelled (see hardware results)"],
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wilson(k, n, z=1.96):
    if n == 0:
        return [0, 0, 0]
    ph = k / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return [round(ph, 4), round(max(0, c - h), 4), round(min(1, c + h), 4)]


def boot_diff(a, b, n=5000, seed=0):
    """Paired bootstrap of mean(a - b)."""
    d = [x - y for x, y in zip(a, b)]
    rng = random.Random(seed)
    m = len(d)
    means = sorted(sum(d[rng.randrange(m)] for _ in range(m)) / m for _ in range(n))
    return {"mean_diff": round(sum(d) / m, 4), "ci95": [round(means[int(.025 * n)], 4), round(means[int(.975 * n)], 4)],
            "n_units": m}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    pre_path = out / "prereg.json"
    hashes = {f: sha(ROOT / f) for f in HASHED}
    if pre_path.exists():
        old = json.loads(pre_path.read_text())
        if old["code_sha256"] != hashes:
            raise SystemExit("code changed after pre-registration: "
                             + ", ".join(f for f in hashes if hashes[f] != old["code_sha256"].get(f)))
    else:
        pre_path.write_text(json.dumps({**PREREG, "code_sha256": hashes,
                                        "written_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
                                       indent=1) + "\n")
        print("pre-registration written:", pre_path)
    res_path = out / "results.jsonl"
    done = set()
    if res_path.exists():
        for line in res_path.read_text().splitlines():
            r = json.loads(line)
            done.add((r["gate"], r["scenario"], r["task"], r["seed"]))
    t0 = time.time()
    with res_path.open("a") as f:
        for sc in C.SCENARIOS:
            for task in C.TASKS:
                for i in range(N_SEEDS):
                    seed = SEED0 + i
                    for g in G.ALL_GATES:
                        if (g, sc, task, seed) in done:
                            continue
                        f.write(json.dumps(C.run_episode(g, seed, sc, task, careless=True)) + "\n")
            f.flush()
            print(f"scenario {sc} done, {time.time() - t0:.0f}s", flush=True)
    summarize(out)


def summarize(out: Path):
    rows = [json.loads(l) for l in (out / "results.jsonl").read_text().splitlines()]
    by = {}
    for r in rows:
        by.setdefault((r["scenario"], r["gate"]), {})[(r["task"], r["seed"])] = r
    summary = {"cells": {}, "pooled": {}, "tests": {}}

    def stats(rs):
        n = len(rs)
        wr = sum(r["write_requests"] for r in rs)
        return {"n": n,
                "unsafe_applied_per_ep": round(sum(r["unsafe_applied"] for r in rs) / n, 4),
                "hazard_episode_rate": wilson(sum(r["any_hazard"] for r in rs), n),
                "task_completion": wilson(sum(r["task_done"] for r in rs), n),
                "write_availability": round(sum(r["write_ok"] for r in rs) / wr, 4) if wr else None,
                "timeouts_per_ep": round(sum(r["timeouts"] for r in rs) / n, 4),
                "exceptions_per_ep": round(sum(r["exceptions"] for r in rs) / n, 4)}

    for (sc, g), d in by.items():
        summary["cells"][f"{sc}|{g}"] = stats(list(d.values()))

    def pooled(scs, g):
        return [by[(sc, g)][k] for sc in scs for k in sorted(by[(sc, g)])]

    for name, scs in (("stressed", STRESSED), ("all", list(C.SCENARIOS))):
        for g in G.ALL_GATES:
            summary["pooled"][f"{name}|{g}"] = stats(pooled(scs, g))

    def paired(scs, ga, gb, key):
        a = [r[key] for r in pooled(scs, ga)]
        b = [r[key] for r in pooled(scs, gb)]
        return boot_diff([float(x) for x in a], [float(x) for x in b])

    t = summary["tests"]
    t["H1_v2_splice_minus_v1_csum_splice_unsafe"] = paired(STRESSED, "v2_splice", "v1_csum_splice", "unsafe_applied")
    t["H2_v2_splice_minus_readback_splice_unsafe"] = paired(STRESSED, "v2_splice", "readback_splice", "unsafe_applied")
    t["H3_timeouts_v2_splice_minus_v2_drop"] = paired(list(C.SCENARIOS), "v2_splice", "v2_drop", "timeouts")
    t["H3_completion_v2_splice_minus_v2_drop"] = paired(list(C.SCENARIOS), "v2_splice", "v2_drop", "task_done")
    t["H4_completion_v2_splice_minus_none"] = paired(list(C.SCENARIOS), "v2_splice", "none", "task_done")
    t["H4_completion_v2_splice_minus_oracle"] = paired(list(C.SCENARIOS), "v2_splice", "oracle_state", "task_done")
    t["H5_unsafe_v2_splice_minus_v1_rtl_all"] = paired(list(C.SCENARIOS), "v2_splice", "v1_rtl", "unsafe_applied")
    t["extra_unsafe_v2_splice_minus_oracle_stressed"] = paired(STRESSED, "v2_splice", "oracle_state", "unsafe_applied")
    t["extra_unsafe_v1_csum_splice_minus_oracle_stressed"] = paired(STRESSED, "v1_csum_splice", "oracle_state", "unsafe_applied")

    p_all = summary["pooled"]
    drop_t, spl_t = p_all["all|v2_drop"]["timeouts_per_ep"], p_all["all|v2_splice"]["timeouts_per_ep"]
    verdict = {
        "H1": "PASS" if t["H1_v2_splice_minus_v1_csum_splice_unsafe"]["ci95"][1] < 0 else "NOT SUPPORTED",
        "H2": "PASS" if t["H2_v2_splice_minus_readback_splice_unsafe"]["ci95"][1] < 0 else "NOT SUPPORTED",
        "H3": "PASS" if (drop_t > 0 and spl_t <= 0.5 * drop_t and
                         t["H3_completion_v2_splice_minus_v2_drop"]["mean_diff"] >= 0) else "NOT SUPPORTED",
        "H4": "PASS" if (t["H4_completion_v2_splice_minus_none"]["ci95"][0] > -0.05 and
                         t["H4_completion_v2_splice_minus_oracle"]["ci95"][0] > -0.05) else "NOT SUPPORTED",
    }
    summary["verdict"] = verdict
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    lines = ["# Closed-loop gate comparison", "", "Pooled over all scenarios (n episodes per gate in table):", "",
             "| gate | n | unsafe applied/ep | hazard-episode rate | task completion | write availability | timeouts/ep |",
             "|---|---|---|---|---|---|---|"]
    for g in G.ALL_GATES:
        s = p_all[f"all|{g}"]
        lines.append(f"| {g} | {s['n']} | {s['unsafe_applied_per_ep']} | {s['hazard_episode_rate'][0]} "
                     f"[{s['hazard_episode_rate'][1]}, {s['hazard_episode_rate'][2]}] | "
                     f"{s['task_completion'][0]} | {s['write_availability']} | {s['timeouts_per_ep']} |")
    lines += ["", "Pooled over stressed scenarios (" + ", ".join(STRESSED) + "):", "",
              "| gate | unsafe applied/ep | hazard-episode rate | task completion |", "|---|---|---|---|"]
    for g in G.ALL_GATES:
        s = summary["pooled"][f"stressed|{g}"]
        lines.append(f"| {g} | {s['unsafe_applied_per_ep']} | {s['hazard_episode_rate'][0]} | {s['task_completion'][0]} |")
    lines += ["", "Paired differences (bootstrap 95% CI):", ""]
    for k, v in t.items():
        lines.append(f"- {k}: {v['mean_diff']} {v['ci95']} (n={v['n_units']})")
    lines += ["", "Pre-registered verdicts: " + json.dumps(verdict)]
    (out / "report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
