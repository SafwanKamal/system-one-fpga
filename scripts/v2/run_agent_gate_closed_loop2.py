"""Experiment 2 (pre-registered follow-up to run_agent_gate_closed_loop.py).

Motivation, both from experiment 1 (build/v2/agent-gate-closedloop-20261108, frozen):
  * v2_splice did not beat readback_splice (H2 not supported) while the client polled every second.
  * v2_splice had more overflow episodes without applying any unsafe write: the frozen rules refuse
    partial *reductions* (e.g. inlet 80 -> 60 at high level) because they judge the post-write state.

Changes tested here: (a) the risk-reducing exemption (gate_v2.ExemptReducing) and (b) sparse evidence
(client polls every 10 s instead of 1 s).  Fresh seeds; pre-registration and code hashes written first.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_agent_gate_closed_loop import boot_diff, sha, wilson  # noqa: E402
from sysone.v2.agent_gate import closed_loop as C  # noqa: E402

HASHED = ["src/sysone/v2/agent_gate/gate_v2.py", "src/sysone/v2/agent_gate/closed_loop.py",
          "src/sysone/v2/agent_gate/intspec.py", "src/sysone/v2/agent_gate/plant.py",
          "src/sysone/v2/agent_gate/sources.py", "src/sysone/v2/agent_gate/frames.py",
          "scripts/v2/run_agent_gate_closed_loop.py", "scripts/v2/run_agent_gate_closed_loop2.py"]
GATES = ["none", "readback_splice", "v2_splice", "oracle_state",
         "readback_splice_x", "v2_splice_x", "oracle_state_x"]
POLLS = [1000, 10000]
N_SEEDS, SEED0 = 30, 2000
STRESSED = ["lossy", "outage", "plc_local", "combined"]

PREREG = {
    "question": "Does exempting risk-reducing writes remove the corrective-action blocking seen in experiment 1, "
                "and does acceptance tracking (v2) beat read-back-only state once evidence is sparse?",
    "design": {"episode_s": C.EPISODE_S, "n_seeds": N_SEEDS, "seed0": SEED0, "tasks": C.TASKS,
               "scenarios": list(C.SCENARIOS), "gates": GATES, "poll_ms": POLLS,
               "rule_sets": {"R": "frozen intspec rules", "R+exempt": "gates ending _x: writes touching only "
                             "inlet/pump/heater whose values are <= every possible current value are not blocked"},
               "everything_else": "as experiment 1 (same sources, plant, faults, ground truth, analysis)"},
    "hypotheses": {
        "E1_exemption": "Pooled over all scenarios at poll 1000: v2_splice_x vs v2_splice. PASS if ALL of: "
                        "hazard-episode rate difference has 95% CI upper < 0; unsafe_applied/episode difference "
                        "CI upper < +0.02; task completion difference CI lower > -0.03.",
        "E2_sparse_evidence": "Pooled over stressed scenarios at poll 10000: v2_splice_x vs readback_splice_x on "
                              "unsafe_applied/episode. PASS if the 95% CI of (v2 - readback) is < 0.",
        "E2b_same_at_1000": "Same comparison at poll 1000 (report either way).",
        "E3_gap_to_ideal": "v2_splice_x vs oracle_state_x at poll 1000, all scenarios. Non-inferiority PASS if "
                           "hazard-episode CI upper < +0.03 AND unsafe_applied CI upper < +0.02.",
        "E4_cost_of_sparse_evidence": "descriptive: each gate's metrics at poll 10000 vs 1000.",
    },
    "analysis": "paired by (scenario, task, seed); bootstrap 5000, seed 0; all cells reported.",
    "caveats": ["E1 is a response to a failure observed in experiment 1: it is a design iteration, "
                "not an untouched confirmation of the original design", "scripted sources, one plant model"],
}


def pooled(by, scs, gate, poll):
    return [by[(sc, gate, poll)][k] for sc in scs for k in sorted(by[(sc, gate, poll)])]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    out = ROOT / ap.parse_args().out
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
    t0 = time.time()
    with rp.open("a") as f:
        for poll in POLLS:
            for sc in C.SCENARIOS:
                for task in C.TASKS:
                    for i in range(N_SEEDS):
                        for g in GATES:
                            if (g, sc, task, SEED0 + i, poll) not in done:
                                f.write(json.dumps(C.run_episode(g, SEED0 + i, sc, task, careless=True, poll_ms=poll)) + "\n")
                f.flush()
                print(f"poll {poll} scenario {sc} done, {time.time() - t0:.0f}s", flush=True)
    summarize(out)


def summarize(out):
    rows = [json.loads(l) for l in (out / "results.jsonl").read_text().splitlines()]
    by = {}
    for r in rows:
        by.setdefault((r["scenario"], r["gate"], r["poll_ms"]), {})[(r["task"], r["seed"])] = r
    allsc = list(C.SCENARIOS)

    def stats(rs):
        n = len(rs)
        wr = sum(r["write_requests"] for r in rs)
        return {"n": n, "unsafe_applied_per_ep": round(sum(r["unsafe_applied"] for r in rs) / n, 4),
                "hazard_episode_rate": wilson(sum(r["any_hazard"] for r in rs), n),
                "task_completion": wilson(sum(r["task_done"] for r in rs), n),
                "write_availability": round(sum(r["write_ok"] for r in rs) / wr, 4) if wr else None,
                "timeouts_per_ep": round(sum(r["timeouts"] for r in rs) / n, 4)}

    S = {"pooled_all": {}, "pooled_stressed": {}, "tests": {}}
    for poll in POLLS:
        for g in GATES:
            S["pooled_all"][f"{poll}|{g}"] = stats(pooled(by, allsc, g, poll))
            S["pooled_stressed"][f"{poll}|{g}"] = stats(pooled(by, STRESSED, g, poll))

    def diff(scs, ga, gb, poll, key):
        a = [float(r[key]) for r in pooled(by, scs, ga, poll)]
        b = [float(r[key]) for r in pooled(by, scs, gb, poll)]
        return boot_diff(a, b)

    t = S["tests"]
    t["E1_hazard_ep"] = diff(allsc, "v2_splice_x", "v2_splice", 1000, "any_hazard")
    t["E1_unsafe"] = diff(allsc, "v2_splice_x", "v2_splice", 1000, "unsafe_applied")
    t["E1_completion"] = diff(allsc, "v2_splice_x", "v2_splice", 1000, "task_done")
    t["E2_unsafe_poll10000_stressed"] = diff(STRESSED, "v2_splice_x", "readback_splice_x", 10000, "unsafe_applied")
    t["E2_hazard_ep_poll10000_stressed"] = diff(STRESSED, "v2_splice_x", "readback_splice_x", 10000, "any_hazard")
    t["E2b_unsafe_poll1000_stressed"] = diff(STRESSED, "v2_splice_x", "readback_splice_x", 1000, "unsafe_applied")
    t["E2c_unsafe_poll10000_stressed_frozen_rules"] = diff(STRESSED, "v2_splice", "readback_splice", 10000, "unsafe_applied")
    t["E3_hazard_ep_vs_oracle"] = diff(allsc, "v2_splice_x", "oracle_state_x", 1000, "any_hazard")
    t["E3_unsafe_vs_oracle"] = diff(allsc, "v2_splice_x", "oracle_state_x", 1000, "unsafe_applied")
    t["E3_completion_vs_oracle"] = diff(allsc, "v2_splice_x", "oracle_state_x", 1000, "task_done")
    t["extra_readback_x_vs_oracle_x_unsafe_poll10000_stressed"] = diff(STRESSED, "readback_splice_x", "oracle_state_x", 10000, "unsafe_applied")

    S["verdict"] = {
        "E1": "PASS" if (t["E1_hazard_ep"]["ci95"][1] < 0 and t["E1_unsafe"]["ci95"][1] < 0.02
                         and t["E1_completion"]["ci95"][0] > -0.03) else "NOT SUPPORTED",
        "E2": "PASS" if t["E2_unsafe_poll10000_stressed"]["ci95"][1] < 0 else "NOT SUPPORTED",
        "E3": "PASS" if (t["E3_hazard_ep_vs_oracle"]["ci95"][1] < 0.03 and t["E3_unsafe_vs_oracle"]["ci95"][1] < 0.02)
        else "NOT SUPPORTED",
    }
    (out / "summary.json").write_text(json.dumps(S, indent=1) + "\n")
    L = ["# Experiment 2", ""]
    for poll in POLLS:
        L += [f"Pooled over all scenarios, client poll every {poll} ms:", "",
              "| gate | unsafe applied/ep | hazard-episode rate | task completion | write availability |", "|---|---|---|---|---|"]
        for g in GATES:
            s = S["pooled_all"][f"{poll}|{g}"]
            L.append(f"| {g} | {s['unsafe_applied_per_ep']} | {s['hazard_episode_rate'][0]} | {s['task_completion'][0]} | {s['write_availability']} |")
        L += ["", f"Stressed scenarios only, poll {poll} ms:", "", "| gate | unsafe applied/ep | hazard-episode rate |", "|---|---|---|"]
        for g in GATES:
            s = S["pooled_stressed"][f"{poll}|{g}"]
            L.append(f"| {g} | {s['unsafe_applied_per_ep']} | {s['hazard_episode_rate'][0]} |")
        L.append("")
    L += ["Paired differences (bootstrap 95% CI):", ""]
    L += [f"- {k}: {v['mean_diff']} {v['ci95']} (n={v['n_units']})" for k, v in t.items()]
    L += ["", "Pre-registered verdicts: " + json.dumps(S["verdict"])]
    (out / "report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
