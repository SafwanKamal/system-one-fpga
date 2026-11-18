"""Independent query witness, saved-archive audit, and resumed-log repair."""
import argparse
import bisect
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pilot


def key(r):
    return tuple(r[n] for n in ["user", "method", "budget", "seed", "base_bits", "mixing"])


def read_lines(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def repair_validation_log():
    out = pilot.OUT
    records = json.loads((out / "validation_records.json").read_text())
    records = [r for r in records if "ingestion_seconds" in r]
    available = {}
    paths = [out / "validation_serial_completed_answers.jsonl.gz"]
    paths += list((out / "workers/validation").glob("*/validation_answers.jsonl.gz"))
    for path in paths:
        if path.exists():
            for row in read_lines(path):
                available[key(row)] = row
    repaired = 0
    for r in records:
        k = key(r)
        if k in available:
            continue
        source = np.load(pilot.WORK / "streams" / f"{r['user']}.npz")
        t, q = source["t"], source["q"]
        memory = pilot.Memory(r["method"], r["budget"], r["seed"], r["base_bits"], r["mixing"])
        for a in range(0, len(q), pilot.CHUNK):
            memory.ingest(t[a:a + pilot.CHUNK], q[a:a + pilot.CHUNK])
        blob = memory.serialize()
        assert hashlib.sha256(blob).hexdigest() == r["archive_sha256"], k
        prior = json.loads((out / "frontend.json").read_text())["prior"]
        rt, restored, _ = pilot.decode(blob, prior)
        questions = json.loads((out / "questions" / f"validation_{r['user']}.json").read_text())["queries"]
        available[k] = dict(**{n: r[n] for n in ["user", "method", "budget", "seed", "base_bits", "mixing"]},
                           answers=pilot.answers(restored, rt, questions).tolist())
        repaired += 1
    with gzip.open(out / "validation_answers.jsonl.gz", "wt", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(available[key(r)]) + "\n")
    pilot.dump(out / "validation_log_repair.json", dict(
        expected_rows=len(records), recovered_rows=len(records) - repaired,
        regenerated_rows=repaired, regenerated_archive_hashes_all_match=True,
        explanation="Serial run stopped for participant-parallel execution. Interrupted gzip buffers were regenerated from the same frozen inputs and checked against previously recorded archive hashes."))


def independent_answer(x, t, q):
    """Separate list/loop implementation; does not call pilot.answer/starts."""
    a, b, threshold = q["a"], q["b"], q["threshold"]
    m = [bool(v >= threshold) for v in x[:, q["d"]]]
    other = [bool(v >= threshold) for v in x[:, q["e"]]]

    def onsets(mask):
        return [i for i, present in enumerate(mask)
                if present and (i == 0 or not mask[i - 1] or int(t[i]) - int(t[i - 1]) > 90)]

    if q["op"] == "duration":
        return sum(m[a:b])
    if q["op"] == "episodes":
        return sum(a <= i < b for i in onsets(m))
    joint = [v and w for v, w in zip(m, other)]
    if q["op"] == "co_duration":
        return sum(joint[a:b])
    if q["op"] == "co_episodes":
        return sum(a <= i < b for i in onsets(joint))
    aa = [i for i in onsets(m) if a <= i < b]
    bb = [i for i in onsets(other) if a <= i < b]
    result = 0
    for i in aa:
        k = bisect.bisect_right(bb, i)
        if k == len(bb):
            continue
        j = bb[k]
        if int(t[j]) - int(t[i]) <= 1800 and all(int(t[k]) - int(t[k - 1]) <= 90 for k in range(i + 1, j + 1)):
            result += 1
    return result


def audit_test():
    out = pilot.OUT
    records = json.loads((out / "test_records.json").read_text())
    records = [r for r in records if "ingestion_seconds" in r]
    prior = json.loads((out / "frontend.json").read_text())["prior"]
    log = read_lines(out / "test_answers.jsonl.gz")
    assert len(log) == len(records)
    assert max(Counter(key(r) for r in log).values()) == 1
    logged = {key(r): r for r in log}
    split = json.loads((out / "split.json").read_text())
    independent_checks = 0
    by_user = {}
    for original_index, user in enumerate(split["test"]):
        source = dict(np.load(pilot.WORK / "streams" / f"{user}.npz"))
        queries = json.loads((out / "questions" / f"test_{user}.json").read_text())
        assert queries["queries"] == pilot.queries(len(source["t"]), pilot.SEED + original_index + 1000)
        independent = [independent_answer(pilot.floats(source["q"]), source["t"], q) for q in queries["queries"]]
        assert independent == queries["reference"], user
        independent_checks += len(independent)
        by_user[user] = (source, queries)
    count = 0
    for r in records:
        user = r["user"]
        source, questions = by_user[user]
        path = out / "archives" / f"{user}_{r['method']}_{r['budget']}_{r['seed']}.bin"
        blob = path.read_bytes()
        assert len(blob) == r["archive_bytes"] <= r["budget"]
        assert r["peak_archive_bytes"] <= r["budget"]
        assert hashlib.sha256(blob).hexdigest() == r["archive_sha256"]
        t, x, _ = pilot.decode(blob, prior)
        assert np.array_equal(t, source["t"])
        pred = pilot.answers(x, t, questions["queries"]).tolist()
        assert pred == logged[key(r)]["answers"]
        count += 1
    frozen = json.loads((out / "protocol_freeze.json").read_text())
    selection = json.loads((out / "selection.json").read_text())
    assert frozen["code_sha256"] == pilot.sha(pilot.__file__) == selection["code_sha256"]
    pilot.dump(out / "audit.json", dict(
        audited_archives=count, serialized_budget_checks_passed=count,
        saved_answer_replays_passed=count, independent_reference_answers=independent_checks,
        query_log_has_no_duplicate_configurations=True,
        code_matches_pretest_freeze_and_selection=True,
        all_test_query_seeds_match_serial=True,
        audit_code_sha256=pilot.sha(__file__)))
    print("audited", count, "archives; independent reference answers", independent_checks, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repair-validation", action="store_true")
    args = parser.parse_args()
    if args.repair_validation:
        repair_validation_log()
    else:
        audit_test()
