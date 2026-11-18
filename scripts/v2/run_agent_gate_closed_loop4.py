"""Experiment 4 (pre-registered): mechanism test for experiment 3's 10 s result.

Conjecture: a read-back gate loses to passive v2 because it cannot see its own just-forwarded writes until the next
read-back, so back-to-back writes in one operator round are judged against stale state.
Test: add `readback_prov_x`, a read-back gate that provisionally commits its forwarded writes (as v1 does) and lets
the next FC3 response overwrite them.  It has no echo matching, no uncertainty set and no level interval.
If it matches v2, those v2 features are not needed in this setup; if it does not, they are.  Fresh seeds.
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

HASHED = ["src/sysone/v2/agent_gate/gate_v2.py", "src/sysone/v2/agent_gate/closed_loop.py",
          "src/sysone/v2/agent_gate/intspec.py", "src/sysone/v2/agent_gate/plant.py",
          "src/sysone/v2/agent_gate/sources.py", "src/sysone/v2/agent_gate/frames.py",
          "scripts/v2/run_agent_gate_closed_loop.py", "scripts/v2/run_agent_gate_closed_loop4.py"]
GATES = ["none", "readback_splice_x", "readback_prov_x", "v2_splice_x", "oracle_state_x"]
POLLS = [1000, 10000, 30000]
N_SEEDS, SEED0 = 30, 4000
STRESSED = ["lossy", "outage", "plc_local", "combined"]

PREREG = {
    "question": "Does provisionally committing a gate's own forwarded writes explain why acceptance tracking beat "
                "a read-back gate in experiment 3, or do v2's echo matching / uncertainty / level interval matter?",
    "design": {"n_seeds": N_SEEDS, "seed0": SEED0, "gates": GATES, "client_poll_ms": POLLS,
               "rule_set": "frozen rules + risk-reducing exemption", "everything_else": "as experiments 1-3"},
    "hypotheses": {
        "M1_provisional_helps": "At client poll 10000, stressed: readback_prov_x vs readback_splice_x on "
                                "unsafe_applied/episode. PASS if 95% CI < 0.",
        "M2_explains_gap": "At client poll 10000, stressed: readback_prov_x vs v2_splice_x. If M1 passes and "
                           "unsafe_applied CI upper < +0.02 and hazard-episode CI upper < +0.03 for (prov - v2): "
                           "'provisional commit explains the gap' (v2's extra machinery not needed here).",
        "M3_v2_adds": "Same comparison, other direction: 'v2 machinery adds value beyond provisional commit' if "
                      "the CI of (v2 - prov) on unsafe_applied is < 0.",
        "M4_other_polls": "M1-M3 repeated at client poll 30000 and 1000; reported, same rules.",
    },
    "analysis": "paired by (scenario, task, seed); bootstrap 5000, seed 0.",
    "caveats": ["scripted sources", "one plant model", "mechanism inferred from outcomes, not from decision traces"],
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

    def stats(rs):
        n = len(rs)
        return {"n": n, "unsafe_applied_per_ep": round(sum(r["unsafe_applied"] for r in rs) / n, 4),
                "hazard_episode_rate": wilson(sum(r["any_hazard"] for r in rs), n),
                "task_completion": wilson(sum(r["task_done"] for r in rs), n),
                "blocked_per_ep": round(sum(r["exceptions"] for r in rs) / n, 2)}

    S = {"pooled_stressed": {}, "tests": {}}
    for poll in POLLS:
        for g in GATES:
            S["pooled_stressed"][f"{poll}|{g}"] = stats(pooled(by, STRESSED, g, poll))

    def d(ga, gb, poll, key):
        return boot_diff([float(r[key]) for r in pooled(by, STRESSED, ga, poll)],
                         [float(r[key]) for r in pooled(by, STRESSED, gb, poll)])

    t, v = S["tests"], {}
    for poll in POLLS:
        k = f"@{poll}"
        t["M1_prov_vs_passive_unsafe" + k] = d("readback_prov_x", "readback_splice_x", poll, "unsafe_applied")
        t["M2_prov_vs_v2_unsafe" + k] = d("readback_prov_x", "v2_splice_x", poll, "unsafe_applied")
        t["M2_prov_vs_v2_hazard_ep" + k] = d("readback_prov_x", "v2_splice_x", poll, "any_hazard")
        t["M3_v2_vs_prov_unsafe" + k] = d("v2_splice_x", "readback_prov_x", poll, "unsafe_applied")
        m1 = t["M1_prov_vs_passive_unsafe" + k]["ci95"][1] < 0
        expl = (m1 and t["M2_prov_vs_v2_unsafe" + k]["ci95"][1] < 0.02
                and t["M2_prov_vs_v2_hazard_ep" + k]["ci95"][1] < 0.03)
        v["M1" + k] = "PASS" if m1 else "NOT SUPPORTED"
        v["M2" + k] = "EXPLAINS GAP" if expl else "NOT SUPPORTED"
        v["M3" + k] = "V2 ADDS VALUE" if t["M3_v2_vs_prov_unsafe" + k]["ci95"][1] < 0 else "NOT SUPPORTED"
    S["verdict"] = v
    (out / "summary.json").write_text(json.dumps(S, indent=1) + "\n")
    L = ["# Experiment 4", ""]
    for poll in POLLS:
        L += [f"Stressed scenarios, client poll {poll} ms:", "",
              "| gate | unsafe / ep | hazard-episode rate | task completion | refused writes / ep |", "|---|---|---|---|---|"]
        for g in GATES:
            s = S["pooled_stressed"][f"{poll}|{g}"]
            L.append(f"| {g} | {s['unsafe_applied_per_ep']} | {s['hazard_episode_rate'][0]} | {s['task_completion'][0]} | {s['blocked_per_ep']} |")
        L.append("")
    L += ["Paired differences (bootstrap 95% CI):", ""]
    L += [f"- {k}: {x['mean_diff']} {x['ci95']} (n={x['n_units']})" for k, x in t.items()]
    L += ["", "Pre-registered verdicts: " + json.dumps(v)]
    (out / "report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
