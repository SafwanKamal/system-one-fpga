"""Participant-parallel orchestration of the unchanged frozen pilot.

Each process writes a separate workspace. Seeds match the serial runner exactly.
Completed participant records can be resumed; methods/queries are never split.
"""
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import time

import pilot
BASE_SEED = pilot.SEED


def worker(stage, user, original_index, selection, frontend, split, destination):
    pilot.OUT = Path(destination)
    pilot.OUT.mkdir(parents=True, exist_ok=True)
    # The serial runner uses base_seed + participant_index for query generation.
    # One participant per worker therefore needs the original index added here.
    pilot.SEED = BASE_SEED + original_index
    local_split = dict(split)
    local_split[stage] = [user]
    pilot.dump(pilot.OUT / "split.json", local_split)
    pilot.dump(pilot.OUT / "frontend.json", frontend)
    if selection is not None:
        pilot.dump(pilot.OUT / "selection.json", selection)
    if stage == "validation":
        # Selection is across ALL validation participants in the parent. A
        # single worker can have no feasible archive at the smallest cap.
        pilot.select = lambda records: None
    pilot.run(stage)
    return str(pilot.OUT)


def main(stage, workers):
    out = pilot.OUT
    split = json.loads((out / "split.json").read_text())
    frontend = json.loads((out / "frontend.json").read_text())
    selection = json.loads((out / "selection.json").read_text()) if stage == "test" else None
    records_path = out / f"{stage}_records.json"
    records = json.loads(records_path.read_text()) if records_path.exists() else []
    done = {r["user"] for r in records}

    def collect(directory, user):
        nonlocal records
        new = json.loads((directory / f"{stage}_records.json").read_text())
        records.extend(new)
        for folder in ["questions", "archives"]:
            source = directory / folder
            if source.exists():
                (out / folder).mkdir(exist_ok=True)
                for f in source.iterdir():
                    shutil.copyfile(f, out / folder / f.name)
        with (out / f"{stage}_answers.jsonl.gz").open("ab") as dst:
            dst.write((directory / f"{stage}_answers.jsonl.gz").read_bytes())
        pilot.dump(records_path, records)
        done.add(user)
        print("completed", stage, len(done), "/", len(split[stage]), flush=True)

    for user in split[stage]:
        directory = out / "workers" / stage / user
        if user not in done and (directory / f"{stage}_records.json").exists():
            collect(directory, user)
    incoming = [(i, user) for i, user in enumerate(split[stage]) if user not in done]
    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        tasks = {pool.submit(worker, stage, user, i, selection, frontend, split,
                             str(out / "workers" / stage / user)): user for i, user in incoming}
        for task in as_completed(tasks):
            user = tasks[task]
            directory = Path(task.result())
            collect(directory, user)
    if stage == "validation":
        pilot.select(records)
    pilot.dump(out / f"{stage}_orchestration.json", dict(
        workers=workers, wall_seconds=time.perf_counter() - start,
        participant_count=len(done), resumed_participants=len(split[stage]) - len(incoming),
        pilot_code_sha256=pilot.sha(pilot.__file__), orchestrator_sha256=pilot.sha(__file__),
        per_participant_query_seed="20261108 + original participant index + stage offset",
        timings_note="Concurrent host wall times; not isolated latency benchmarks"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["validation", "test"], required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    main(args.stage, args.workers)
