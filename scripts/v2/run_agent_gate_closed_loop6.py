"""Experiment 6 (pre-registered): is refusal-by-byte-mutation equivalent to spliced refusal?

Same decisions (gate_v3 core), different delivery: v3_splice_x injects an exception frame and rewrites sequence
numbers; v3_mutate_x changes the refused request's function code to 0x7F (same length) so the PLC answers 'illegal
function', and restores the response's function code and exception code on the way back.  Fresh seeds.
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
          "src/sysone/v2/agent_gate/gate_mutate.py", "src/sysone/v2/agent_gate/closed_loop.py",
          "src/sysone/v2/agent_gate/intspec.py", "src/sysone/v2/agent_gate/plant.py",
          "src/sysone/v2/agent_gate/sources.py", "src/sysone/v2/agent_gate/frames.py",
          "scripts/v2/run_agent_gate_closed_loop.py", "scripts/v2/run_agent_gate_closed_loop6.py"]
GATES = ["none", "v3_splice_x", "v3_mutate_x", "oracle_state_x"]
POLLS = [1000, 10000]
N_SEEDS, SEED0 = 30, 7000
ALL = list(C.SCENARIOS)

PREREG = {
    "question": "Does delivering a refusal as a one-byte mutation (PLC answers illegal function; gate restores the "
                "response) behave like a spliced exception?",
    "design": {"n_seeds": N_SEEDS, "seed0": SEED0, "gates": GATES, "client_poll_ms": POLLS,
               "everything_else": "as experiments 1-5"},
    "hypotheses": {
        "T1_equivalent": "v3_mutate_x - v3_splice_x, pooled over all scenarios at each client poll rate: "
                         "unsafe_applied/episode CI upper < +0.02, hazard-episode CI upper < +0.03, task completion "
                         "CI lower > -0.03, timeouts/episode CI upper < +0.5.  PASS needs all four at both rates.",
        "T2_descriptive": "mutated (illegal-function) requests reaching the PLC per episode.",
    },
    "analysis": "paired by (scenario, task, seed); bootstrap 5000, seed 0.",
    "caveats": ["the simulated PLC answers any unknown function code with exception 01, as the Modbus spec requires; "
                "real PLCs must be checked", "PLC-side logging/alarming of illegal requests is not modelled"],
}


def pooled(by, g, poll):
    return [by[(sc, g, poll)][k] for sc in ALL for k in sorted(by[(sc, g, poll)])]


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
        refused = sum(v for r in rs for k, v in r["rules"].items() if k != "pass")
        return {"n": n, "unsafe_applied_per_ep": round(sum(r["unsafe_applied"] for r in rs) / n, 4),
                "hazard_episode_rate": wilson(sum(r["any_hazard"] for r in rs), n),
                "task_completion": wilson(sum(r["task_done"] for r in rs), n),
                "timeouts_per_ep": round(sum(r["timeouts"] for r in rs) / n, 3),
                "exceptions_per_ep": round(sum(r["exceptions"] for r in rs) / n, 2),
                "refusals_per_ep": round(refused / n, 2)}

    S = {"pooled_all": {}, "tests": {}}
    for poll in POLLS:
        for g in GATES:
            S["pooled_all"][f"{poll}|{g}"] = stats(pooled(by, g, poll))

    def d(ga, gb, poll, key):
        return boot_diff([float(r[key]) for r in pooled(by, ga, poll)], [float(r[key]) for r in pooled(by, gb, poll)])

    t, ok = S["tests"], True
    for poll in POLLS:
        k = f"@{poll}"
        for key, nm in (("unsafe_applied", "unsafe"), ("any_hazard", "hazard_ep"), ("task_done", "completion"),
                        ("timeouts", "timeouts")):
            t[f"T1_mutate_minus_splice_{nm}{k}"] = d("v3_mutate_x", "v3_splice_x", poll, key)
        ok &= (t[f"T1_mutate_minus_splice_unsafe{k}"]["ci95"][1] < 0.02 and t[f"T1_mutate_minus_splice_hazard_ep{k}"]["ci95"][1] < 0.03
               and t[f"T1_mutate_minus_splice_completion{k}"]["ci95"][0] > -0.03
               and t[f"T1_mutate_minus_splice_timeouts{k}"]["ci95"][1] < 0.5)
    S["verdict"] = {"T1": "PASS" if ok else "NOT SUPPORTED"}
    (out / "summary.json").write_text(json.dumps(S, indent=1) + "\n")
    L = ["# Experiment 6", ""]
    for poll in POLLS:
        L += [f"All scenarios, client poll {poll} ms:", "",
              "| gate | unsafe / ep | hazard-episode rate | task completion | timeouts / ep | exceptions / ep | refusals / ep |",
              "|---|---|---|---|---|---|---|"]
        for g in GATES:
            s = S["pooled_all"][f"{poll}|{g}"]
            L.append(f"| {g} | {s['unsafe_applied_per_ep']} | {s['hazard_episode_rate'][0]} | {s['task_completion'][0]} | "
                     f"{s['timeouts_per_ep']} | {s['exceptions_per_ep']} | {s['refusals_per_ep']} |")
        L.append("")
    L += ["Paired differences (bootstrap 95% CI):", ""]
    L += [f"- {k}: {x['mean_diff']} {x['ci95']} (n={x['n_units']})" for k, x in t.items()]
    L += ["", "Pre-registered verdict: " + json.dumps(S["verdict"])]
    (out / "report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
