"""Experiment 5 (pre-registered): do the hardware restrictions of gate_v3 cost anything versus gate_v2?

v3 = v2's acceptance tracking restricted to fit fabric (8-entry pending table, 2 values per register, integer level
interval, checks on frame arrival, conservative start-time ring, exemption built in).  Fresh seeds.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_agent_gate_closed_loop import boot_diff, sha, wilson  # noqa: E402
from sysone.v2.agent_gate import closed_loop as C  # noqa: E402

HASHED = ["src/sysone/v2/agent_gate/gate_v2.py", "src/sysone/v2/agent_gate/gate_v3.py",
          "src/sysone/v2/agent_gate/closed_loop.py", "src/sysone/v2/agent_gate/intspec.py",
          "src/sysone/v2/agent_gate/plant.py", "src/sysone/v2/agent_gate/sources.py",
          "src/sysone/v2/agent_gate/frames.py", "scripts/v2/run_agent_gate_closed_loop.py",
          "scripts/v2/run_agent_gate_closed_loop5.py"]
GATES = ["none", "v2_splice_x", "v3_splice_x", "oracle_state_x"]
POLLS = [1000, 10000]
N_SEEDS = 30
SEED0 = int(sys.argv[sys.argv.index("--seed0") + 1]) if "--seed0" in sys.argv else 5000
STRESSED = ["lossy", "outage", "plc_local", "combined"]
ALL = list(C.SCENARIOS)

PREREG = {
    "question": "Is the hardware-exact v3 decision core non-inferior to the behavioural v2 reference?",
    "design": {"n_seeds": N_SEEDS, "seed0": SEED0, "gates": GATES, "client_poll_ms": POLLS,
               "everything_else": "as experiments 1-4"},
    "hypotheses": {
        "V1_non_inferior": "v3_splice_x - v2_splice_x, pooled over all scenarios, at each client poll rate: "
                           "unsafe_applied/episode CI upper < +0.02 AND hazard-episode CI upper < +0.03 AND "
                           "task-completion CI lower > -0.03.  PASS needs all three at both poll rates.",
        "V2_vs_oracle": "v3_splice_x - oracle_state_x, same bounds, at poll 1000 (descriptive at 10000).",
        "V3_table_pressure": "descriptive: how often v3 refuses with pending_table_full / state_unknown "
                             "(rule counters) in stressed scenarios.",
    },
    "analysis": "paired by (scenario, task, seed); bootstrap 5000, seed 0.",
}


def pooled(by, scs, g, poll):
    return [by[(sc, g, poll)][k] for sc in scs for k in sorted(by[(sc, g, poll)])]


def main():
    out = ROOT / sys.argv[sys.argv.index("--out") + 1]
    out.mkdir(parents=True, exist_ok=True)
    hashes = {f: sha(ROOT / f) for f in HASHED}
    pre = out / "prereg.json"
    if pre.exists():
        if json.loads(pre.read_text())["code_sha256"] != hashes:
            raise SystemExit("code changed after pre-registration")
    else:
        pre.write_text(json.dumps({**PREREG, "code_sha256": hashes,
                                   "written_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=1) + "\n")
        print("pre-registration written")
    rp = out / "results.jsonl"
    done = set()
    if rp.exists():
        done = {(r["gate"], r["scenario"], r["task"], r["seed"], r["poll_ms"]) for r in map(json.loads, rp.read_text().splitlines())}
    with rp.open("a") as f:
        for poll in POLLS:
            for sc in C.SCENARIOS:
                for task in C.TASKS:
                    for i in range(N_SEEDS):
                        for g in GATES:
                            if (g, sc, task, SEED0 + i, poll) not in done:
                                f.write(json.dumps(C.run_episode(g, SEED0 + i, sc, task, careless=True, poll_ms=poll)) + "\n")
                f.flush()
    summarize(out)


def summarize(out):
    rows = [json.loads(l) for l in (out / "results.jsonl").read_text().splitlines()]
    by = {}
    for r in rows:
        by.setdefault((r["scenario"], r["gate"], r["poll_ms"]), {})[(r["task"], r["seed"])] = r

    def stats(rs):
        n = len(rs)
        rules = {}
        for r in rs:
            for k, v in r["rules"].items():
                rules[k] = rules.get(k, 0) + v
        return {"n": n, "unsafe_applied_per_ep": round(sum(r["unsafe_applied"] for r in rs) / n, 4),
                "hazard_episode_rate": wilson(sum(r["any_hazard"] for r in rs), n),
                "task_completion": wilson(sum(r["task_done"] for r in rs), n),
                "pending_full": rules.get("pending_table_full", 0), "state_unknown": rules.get("state_unknown", 0),
                "refused_total": sum(v for k, v in rules.items() if k != "pass")}

    S = {"pooled_all": {}, "pooled_stressed": {}, "tests": {}}
    for poll in POLLS:
        for g in GATES:
            S["pooled_all"][f"{poll}|{g}"] = stats(pooled(by, ALL, g, poll))
            S["pooled_stressed"][f"{poll}|{g}"] = stats(pooled(by, STRESSED, g, poll))

    def d(ga, gb, poll, key, scs=ALL):
        return boot_diff([float(r[key]) for r in pooled(by, scs, ga, poll)],
                         [float(r[key]) for r in pooled(by, scs, gb, poll)])

    t, ok = S["tests"], True
    for poll in POLLS:
        k = f"@{poll}"
        for key, nm in (("unsafe_applied", "unsafe"), ("any_hazard", "hazard_ep"), ("task_done", "completion")):
            t[f"V1_v3_minus_v2_{nm}{k}"] = d("v3_splice_x", "v2_splice_x", poll, key)
            t[f"V2_v3_minus_oracle_{nm}{k}"] = d("v3_splice_x", "oracle_state_x", poll, key)
        ok &= (t[f"V1_v3_minus_v2_unsafe{k}"]["ci95"][1] < 0.02 and t[f"V1_v3_minus_v2_hazard_ep{k}"]["ci95"][1] < 0.03
               and t[f"V1_v3_minus_v2_completion{k}"]["ci95"][0] > -0.03)
    S["verdict"] = {"V1": "PASS" if ok else "NOT SUPPORTED"}
    (out / "summary.json").write_text(json.dumps(S, indent=1) + "\n")
    L = ["# Experiment 5", ""]
    for poll in POLLS:
        L += [f"All scenarios, client poll {poll} ms:", "",
              "| gate | unsafe / ep | hazard-episode rate | task completion | refused (all) | pending_full | state_unknown |",
              "|---|---|---|---|---|---|---|"]
        for g in GATES:
            s = S["pooled_all"][f"{poll}|{g}"]
            L.append(f"| {g} | {s['unsafe_applied_per_ep']} | {s['hazard_episode_rate'][0]} | {s['task_completion'][0]} | "
                     f"{s['refused_total']} | {s['pending_full']} | {s['state_unknown']} |")
        L.append("")
    L += ["Paired differences (bootstrap 95% CI):", ""]
    L += [f"- {k}: {x['mean_diff']} {x['ci95']} (n={x['n_units']})" for k, x in t.items()]
    L += ["", "Pre-registered verdict: " + json.dumps(S["verdict"])]
    (out / "report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
