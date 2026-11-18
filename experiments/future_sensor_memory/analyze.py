"""Post-run analysis: common-cohort plot and explicitly exploratory sensor-only QA.

No memory policy is rerun or selected here. All answers use frozen test archives.
"""
from collections import defaultdict
import json

import numpy as np

import pilot


def averaged(records):
    groups = defaultdict(list)
    for r in records:
        if "scores" in r and r.get("budget", 0):
            for panel, scores in r["scores"].items():
                groups[(r["method"], r["budget"], panel, r["user"])].append(scores)
    return {k: {metric: float(np.mean([r[metric] for r in v if r[metric] is not None]))
                for metric in ["exact", "nmae", "positive_exact"]
                if any(r[metric] is not None for r in v)} for k, v in groups.items()}


def differences(values, baseline, candidate):
    rng = np.random.default_rng(1943)
    result = []
    for budget in pilot.BUDGETS:
        for panel in sorted({k[2] for k in values}):
            users = sorted({k[3] for k in values if k[:3] == (candidate, budget, panel)})
            for metric in ["exact", "positive_exact", "nmae"]:
                delta = np.array([values[(candidate, budget, panel, u)][metric] - values[(baseline, budget, panel, u)][metric]
                                  for u in users if metric in values[(candidate, budget, panel, u)] and metric in values[(baseline, budget, panel, u)]])
                boots = delta[rng.integers(0, len(delta), (10000, len(delta)))].mean(1)
                result.append(dict(budget=budget, panel=panel, metric=metric, n=len(delta),
                                   candidate=candidate, baseline=baseline, delta=float(delta.mean()),
                                   ci95=np.quantile(boots, [.025, .975]).tolist()))
    return result


def plot(values, candidate):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import NullLocator, NullFormatter
    cohort = set.intersection(*[{k[3] for k in values if k[:3] == (candidate, b, "all")} for b in pilot.BUDGETS])
    display = ["reservoir", "adaptive_segments", "balanced_codec", "event1", "hybrid_reservoir", "hybrid_change", "hybrid_bundle"]
    names = {"reservoir": "Uniform sampling", "adaptive_segments": "Adaptive means",
             "balanced_codec": "Balanced compression", "event1": "Event table",
             "hybrid_reservoir": "Uniform hybrid", "hybrid_change": "Change-priority hybrid",
             "hybrid_bundle": "Linked-pair hybrid"}
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5), layout="constrained")
    plot_data = []
    for ax, panel in zip(axes, ["familiar", "composition", "continuous_shift"]):
        for method in display:
            y = []
            for budget in pilot.BUDGETS:
                v = np.mean([values[(method, budget, panel, u)]["exact"] for u in cohort])
                y.append(v * 100)
                plot_data.append(dict(method=method, budget=budget, panel=panel, exact=float(v)))
            ax.plot(np.array(pilot.BUDGETS) / 1024, y, marker="o", label=names[method])
        ax.set_xscale("log", base=2)
        ax.set(xlabel="Archive cap (KiB/person)", ylabel="Exact answer agreement (%)", title=panel.replace("_", " "))
        ax.set_xticks([8, 16, 32, 64], labels=[8, 16, 32, 64])
        ax.xaxis.set_minor_locator(NullLocator())
        ax.xaxis.set_minor_formatter(NullFormatter())
        ax.set_ylim(0, 104)
        ax.grid(alpha=.25)
    axes[-1].legend(fontsize=8, loc="lower right")
    fig.suptitle(f"Future-question memory: fixed cohort of {len(cohort)} unseen participants eligible at every cap")
    fig.savefig(pilot.OUT / "frontier_common_cohort.png", dpi=180)
    plt.close(fig)
    pilot.dump(pilot.OUT / "frontier_common_cohort.json", dict(participants=sorted(cohort), rows=plot_data))


def numerical_queries(n, seed):
    rng = np.random.default_rng(seed)
    qq = []
    for op in ["duration", "episodes", "co_duration", "co_episodes", "follow"]:
        for j in range(64):
            d, e = rng.choice(np.arange(8, 12), size=2, replace=False)
            a = 0 if j % 3 == 0 else int(rng.integers(0, n // 2))
            b = n if j % 3 == 0 else int(rng.integers(n // 2, n + 1))
            qq.append(dict(op=op, panel="numeric_only", d=int(d), e=int(e), a=a, b=b,
                           threshold=.5 if j % 2 == 0 else float(rng.uniform(.2, .8))))
    return qq


def numeric_analysis(records, candidate):
    out = pilot.OUT
    prior = json.loads((out / "frontend.json").read_text())["prior"]
    split = json.loads((out / "split.json").read_text())
    questions = {}
    for i, user in enumerate(split["test"]):
        source = np.load(pilot.WORK / "streams" / f"{user}.npz")
        qq = numerical_queries(len(source["t"]), 57009 + i)
        ref = pilot.answers(pilot.floats(source["q"]), source["t"], qq)
        questions[user] = (qq, ref)
        pilot.dump(out / "questions" / f"exploratory_numeric_{user}.json", dict(
            exploratory=True, generated_after_memory_creation=True, queries=qq, reference=ref.tolist()))
    rows = []
    for r in records:
        if "ingestion_seconds" not in r:
            continue
        path = out / "archives" / f"{r['user']}_{r['method']}_{r['budget']}_{r['seed']}.bin"
        t, x, _ = pilot.decode(path.read_bytes(), prior)
        qq, ref = questions[r["user"]]
        pred = pilot.answers(x, t, qq)
        error = np.abs(pred - ref)
        positive = ref > 0
        rows.append(dict(user=r["user"], method=r["method"], budget=r["budget"],
                         scores={"numeric_only": dict(exact=float(np.mean(error == 0)),
                                                       positive_exact=float(np.mean(error[positive] == 0)),
                                                       nmae=float(np.mean(error / np.maximum(ref, 1))))},
                         symmetric_error=float(np.mean(error / np.maximum.reduce([pred, ref, np.ones_like(ref)]))),
                         zero_reference=float(np.mean(~positive))))
    pilot.dump(out / "exploratory_numeric_records.json", rows)
    values = averaged(rows)
    result = []
    for method in pilot.METHODS:
        for budget in pilot.BUDGETS:
            keys = [k for k in values if k[:3] == (method, budget, "numeric_only")]
            result.append(dict(method=method, budget=budget, n=len(keys),
                               **{m: float(np.mean([values[k][m] for k in keys])) for m in ["exact", "positive_exact", "nmae"]}))
    pilot.dump(out / "exploratory_numeric_summary.json", result)
    pilot.dump(out / "exploratory_numeric_paired_uniform.json", differences(values, "hybrid_reservoir", candidate))
    pilot.dump(out / "exploratory_numeric_linked_uniform.json", differences(values, "hybrid_reservoir", "hybrid_bundle"))
    pilot.dump(out / "exploratory_numeric_design.json", dict(
        exploratory=True, questions_per_person=320, participants=12,
        query_source="four directly observed normalized sensor feature channels; excludes all activity classifiers",
        no_new_memory_selection=True, no_new_ingestion=True,
        zero_reference=float(np.mean([r["zero_reference"] for r in rows]))))
    for b in pilot.BUDGETS:
        print("numeric", b // 1024, [(r["method"], round(r["exact"], 4), round(r["nmae"], 4)) for r in result
                                      if r["budget"] == b and r["method"] in ["adaptive_segments", "balanced_codec", "hybrid_reservoir", candidate]], flush=True)


if __name__ == "__main__":
    records = json.loads((pilot.OUT / "test_records.json").read_text())
    selected = json.loads((pilot.OUT / "selection.json").read_text())["selected_candidate"]
    values = averaged(records)
    pilot.dump(pilot.OUT / "paired_uniform_hybrid.json", differences(values, "hybrid_reservoir", selected))
    pilot.dump(pilot.OUT / "paired_linked_uniform.json", differences(values, "hybrid_reservoir", "hybrid_bundle"))
    plot(values, selected)
    numeric_analysis(records, selected)
    pilot.dump(pilot.OUT / "analysis_manifest.json", dict(analysis_code_sha256=pilot.sha(__file__),
                                                         frozen_pilot_code_sha256=pilot.sha(pilot.__file__),
                                                         created_utc=pilot.utc(), primary_metrics_unchanged=True))
