"""Experiment 3 (pre-registered): is acceptance tracking still useful against a read-back gate that
polls the PLC itself?

Experiment 2 showed v2 (acceptance tracking) beats a *passive* read-back gate when the client polls every
10 s, but a gate can also issue its own FC3/FC4 reads. This adds that baseline.  Fresh seeds.
Active polling costs the PLC two extra requests per poll (counted in `gate_polls`).
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
          "scripts/v2/run_agent_gate_closed_loop.py", "scripts/v2/run_agent_gate_closed_loop3.py"]
GATES = ["none", "readback_splice_x", "v2_splice_x", "readback_poll1_x", "readback_poll5_x", "v2_poll1_x",
         "oracle_state_x"]
POLLS = [1000, 10000, 30000]
N_SEEDS, SEED0 = 30, 3000
STRESSED = ["lossy", "outage", "plc_local", "combined"]

PREREG = {
    "question": "Does acceptance tracking add value over a read-back gate that polls the PLC itself, and "
                "what does each cost in PLC traffic?",
    "design": {"n_seeds": N_SEEDS, "seed0": SEED0, "gates": GATES, "client_poll_ms": POLLS,
               "gate_polling": "readback_poll1_x / v2_poll1_x issue FC4+FC3 reads every 1 s, readback_poll5_x "
                               "every 5 s, over the same path as client traffic (subject to loss and outages)",
               "rule_set": "frozen rules + risk-reducing exemption (all gates here are *_x)",
               "everything_else": "as experiments 1 and 2"},
    "hypotheses": {
        "B1_polling_helps": "At client poll 10000, stressed: readback_poll1_x vs readback_splice_x on "
                            "unsafe_applied/episode. PASS if 95% CI < 0.",
        "B2_tracking_substitutes_for_polling": "At client poll 10000, stressed: v2_splice_x (passive) vs "
                            "readback_poll1_x. NON-INFERIOR if unsafe_applied CI upper < +0.02 and hazard-episode "
                            "CI upper < +0.03. SUPERIOR (extra claim) if unsafe_applied CI upper < 0.",
        "B3_tracking_adds_to_polling": "At client poll 10000, stressed: v2_poll1_x vs readback_poll1_x on "
                            "unsafe_applied/episode. PASS if 95% CI < 0.",
        "B4_30s": "B1-B3 repeated at client poll 30000 (reported; same decision rules).",
        "B5_cost": "descriptive: gate_polls per episode versus client requests per episode.",
    },
    "analysis": "paired by (scenario, task, seed); bootstrap 5000, seed 0.",
    "caveats": ["scripted sources", "one plant model", "the gate's own reads are assumed always parsed correctly "
                "and do not load the PLC beyond counting", "no latency model"],
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
    allsc = list(C.SCENARIOS)

    def stats(rs):
        n = len(rs)
        return {"n": n, "unsafe_applied_per_ep": round(sum(r["unsafe_applied"] for r in rs) / n, 4),
                "hazard_episode_rate": wilson(sum(r["any_hazard"] for r in rs), n),
                "task_completion": wilson(sum(r["task_done"] for r in rs), n),
                "gate_polls_per_ep": round(sum(r["gate_polls"] for r in rs) / n, 1),
                "client_requests_per_ep": round(sum(r["requests"] for r in rs) / n, 1)}

    S = {"pooled_stressed": {}, "pooled_all": {}, "tests": {}}
    for poll in POLLS:
        for g in GATES:
            S["pooled_stressed"][f"{poll}|{g}"] = stats(pooled(by, STRESSED, g, poll))
            S["pooled_all"][f"{poll}|{g}"] = stats(pooled(by, allsc, g, poll))

    def d(ga, gb, poll, key, scs=STRESSED):
        return boot_diff([float(r[key]) for r in pooled(by, scs, ga, poll)],
                         [float(r[key]) for r in pooled(by, scs, gb, poll)])

    t = S["tests"]
    for poll in (10000, 30000):
        k = f"@{poll}"
        t["B1_poll1_vs_passive_unsafe" + k] = d("readback_poll1_x", "readback_splice_x", poll, "unsafe_applied")
        t["B2_v2passive_vs_poll1_unsafe" + k] = d("v2_splice_x", "readback_poll1_x", poll, "unsafe_applied")
        t["B2_v2passive_vs_poll1_hazard_ep" + k] = d("v2_splice_x", "readback_poll1_x", poll, "any_hazard")
        t["B3_v2poll1_vs_poll1_unsafe" + k] = d("v2_poll1_x", "readback_poll1_x", poll, "unsafe_applied")
        t["extra_poll5_vs_poll1_unsafe" + k] = d("readback_poll5_x", "readback_poll1_x", poll, "unsafe_applied")
        t["extra_v2passive_vs_poll5_unsafe" + k] = d("v2_splice_x", "readback_poll5_x", poll, "unsafe_applied")
        t["extra_v2passive_vs_oracle_unsafe" + k] = d("v2_splice_x", "oracle_state_x", poll, "unsafe_applied")
    v = {}
    for poll in (10000, 30000):
        k = f"@{poll}"
        v["B1" + k] = "PASS" if t["B1_poll1_vs_passive_unsafe" + k]["ci95"][1] < 0 else "NOT SUPPORTED"
        ni = (t["B2_v2passive_vs_poll1_unsafe" + k]["ci95"][1] < 0.02
              and t["B2_v2passive_vs_poll1_hazard_ep" + k]["ci95"][1] < 0.03)
        sup = t["B2_v2passive_vs_poll1_unsafe" + k]["ci95"][1] < 0
        v["B2" + k] = ("SUPERIOR" if sup else "NON-INFERIOR" if ni else "NOT SUPPORTED")
        v["B3" + k] = "PASS" if t["B3_v2poll1_vs_poll1_unsafe" + k]["ci95"][1] < 0 else "NOT SUPPORTED"
    S["verdict"] = v
    (out / "summary.json").write_text(json.dumps(S, indent=1) + "\n")
    L = ["# Experiment 3", ""]
    for poll in POLLS:
        L += [f"Stressed scenarios, client poll {poll} ms:", "",
              "| gate | unsafe / ep | hazard-episode rate | task completion | gate reads / ep |", "|---|---|---|---|---|"]
        for g in GATES:
            s = S["pooled_stressed"][f"{poll}|{g}"]
            L.append(f"| {g} | {s['unsafe_applied_per_ep']} | {s['hazard_episode_rate'][0]} | "
                     f"{s['task_completion'][0]} | {s['gate_polls_per_ep']} |")
        L.append("")
    L += ["Paired differences (bootstrap 95% CI):", ""]
    L += [f"- {k}: {x['mean_diff']} {x['ci95']} (n={x['n_units']})" for k, x in t.items()]
    L += ["", "Pre-registered verdicts: " + json.dumps(v)]
    (out / "report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
