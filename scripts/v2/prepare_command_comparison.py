"""Prepare an auditable, synthetic-only pilot; never touches the board.

Run with .venv/Scripts/python.exe scripts/v2/prepare_command_comparison.py --out PATH
Option --download obtains pinned official model weights in the normal HF cache.
Re-running requires a new output directory so failures and earlier receipts survive.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from sysone.v2.command_task import API_ARGS, ASSETS, REASONS, canonical, evaluate

MODELS = {
    "encoder": ("google-bert/bert-base-uncased", "86b5e0934494bd15c9632b12f734a8a67f723594"),
    "generator": ("google/functiongemma-270m-it", "39eccb091651513a5dfb56892d3714c1b5b8276c"),
}


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def action(api, asset, args=None):
    return dict(api=api, asset=asset, args=args or {})


def accepted(actions, condition=None):
    return dict(outcome="Accepted", actions=actions, condition=condition)


def phrase(a, family):
    asset, args = a["asset"], a["args"]
    variants = {
        "get_status": (f"get the status of {asset}", f"report how {asset} is doing", f"show {asset}'s current status"),
        "read_temperature": (f"read {asset}'s temperature", f"measure temperature on {asset}", f"tell me how hot {asset} is"),
        "read_vibration": (f"read {asset}'s vibration", f"measure vibration on {asset}", f"show the vibration reading for {asset}"),
        "list_alarms": (f"list alarms on {asset}", f"show active alarms for {asset}", f"which alarms does {asset} have"),
        "start_asset": (f"start {asset}", f"turn {asset} on", f"begin running {asset}"),
        "stop_asset": (f"stop {asset}", f"turn {asset} off", f"halt {asset}"),
        "reset_alarm": (f"reset the alarm on {asset}", f"clear {asset}'s alarm", f"acknowledge and reset {asset}'s alarm"),
        "set_mode": (f"set {asset} to {args.get('mode')} mode", f"switch {asset} into {args.get('mode')}", f"use {args.get('mode')} mode for {asset}"),
        "set_speed": (f"set {asset} to {args.get('rpm')} rpm", f"change {asset}'s speed to {args.get('rpm')} rpm", f"run {asset} at {args.get('rpm')} rpm"),
        "create_work_order": (f"create a {args.get('priority')} priority work order for {asset}", f"open a work order for {asset} with {args.get('priority')} priority", f"file a {args.get('priority')} priority maintenance work order for {asset}"),
        "schedule_inspection": (f"schedule a {args.get('priority')} priority inspection of {asset}", f"arrange an inspection for {asset} with {args.get('priority')} priority", f"book a {args.get('priority')} priority inspection for {asset}"),
        "enable_monitor": (f"enable {args.get('sensor')} monitoring on {asset}", f"start monitoring {args.get('sensor')} for {asset}", f"activate {asset}'s {args.get('sensor')} monitor"),
    }
    return variants[a["api"]][family]


def make_pilot():
    splits = {"train": [], "dev": [], "diagnostic": []}
    for family, split in enumerate(splits):
        rows = splits[split]
        def add(text, gold, category):
            raw = canonical(gold)
            identity = hashlib.sha256((text + "\n" + raw).encode()).hexdigest()
            rows.append(dict(id=identity, text=text, gold=gold, category=category,
                             provenance="programmatic_synthetic", template_family=family,
                             human_reviewed=False, state_epoch=1))
        for i, asset in enumerate(ASSETS):
            for api, spec in API_ARGS.items():
                key = next(iter(spec), None)
                args_list = [{key: v} for v in spec[key]] if key else [{}]
                for args in args_list:
                    first = action(api, asset, args)
                    add(phrase(first, family), accepted([first]), "single")
                    # The condition scopes the entire ordered action list.
                    condition = dict(asset=asset, sensor="temperature", op="gt",
                                     value=70, unit="C")
                    add(f"if {asset}'s temperature exceeds 70 C, {phrase(first, family)}",
                        accepted([first], condition), "condition")
                    second = action("get_status" if api != "get_status" else "list_alarms",
                                    ASSETS[(i+1) % len(ASSETS)])
                    add(phrase(first, family) + "; then " + phrase(second, family),
                        accepted([first, second]), "composition")
            target = action("stop_asset", asset)
            alternative = action("get_status", asset)
            # Explicit correction, not treating negation itself as an action.
            add(f"do not {phrase(target, family)}; instead {phrase(alternative, family)}",
                accepted([alternative]), "negation")
            add(f"User: {phrase(target, family)}. User correction: cancel that; {phrase(alternative, family)}.",
                accepted([alternative]), "correction")
            add(f"start {asset} and do not start {asset}" + (" please", " now", " today")[family],
                dict(outcome="Clarify", reason="contradiction"), "contradiction")
        for text, outcome, reason, category in [
            ("start the motor", "Clarify", "missing_asset", "missing_argument"),
            ("stop it", "Clarify", "ambiguous_reference", "ambiguity"),
            ("start M99", "Reject", "unknown_asset", "unknown_asset"),
            ("send an email to the supervisor", "Reject", "unsupported_operation", "unsupported"),
            ("set M1 to 99999 rpm", "Reject", "unsupported_value", "unsupported_value"),
        ]:
            add(("Please ", "Could you ", "I need you to ")[family] + text,
                dict(outcome=outcome, reason=reason), category)
    all_text = [r["text"].casefold() for rows in splits.values() for r in rows]
    if len(all_text) != len(set(all_text)):
        raise ValueError("duplicate input across splits")
    return splits


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--download", action="store_true")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    import torch
    from huggingface_hub import hf_hub_download, snapshot_download
    inventory = dict(observed_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                     platform=platform.platform(), python=sys.version,
                     logical_cpus=os.cpu_count(), cuda_available=torch.cuda.is_available(),
                     torch_threads=torch.get_num_threads(), board_contacted=False,
                     paid_compute_used=False, models={}, packages={n: importlib.metadata.version(n)
                     for n in ("torch", "transformers", "huggingface-hub", "numpy")})
    dump(args.out / "inventory.json", inventory)
    for role, (repo, revision) in MODELS.items():
        receipt = dict(repo=repo, revision=revision, requests=[])
        inventory["models"][role] = receipt
        for filename in ("config.json", "tokenizer_config.json"):
            request = dict(filename=filename)
            receipt["requests"].append(request)
            try:
                path = Path(hf_hub_download(repo, filename, revision=revision))
                request.update(status="ok", path=str(path), sha256=sha(path))
                if filename == "config.json":
                    receipt["config"] = json.loads(path.read_text())
            except Exception as exc:
                request.update(status="failed", error_type=type(exc).__name__,
                    http_status=getattr(getattr(exc, "response", None), "status_code", None))
            dump(args.out / "inventory.json", inventory)
        if args.download and all(r["status"] == "ok" for r in receipt["requests"]):
            request = dict(operation="snapshot_download", status="started")
            receipt["requests"].append(request)
            dump(args.out / "inventory.json", inventory)
            try:
                path = Path(snapshot_download(repo, revision=revision,
                    allow_patterns=["*.json", "*.jinja", "*.safetensors", "*.model", "vocab.txt", "merges.txt"]))
                files = {p.relative_to(path).as_posix(): dict(bytes=p.stat().st_size, sha256=sha(p))
                         for p in path.rglob("*") if p.is_file()}
                request.update(status="ok", path=str(path), files=files)
            except Exception as exc:
                request.update(status="failed", error_type=type(exc).__name__)
            dump(args.out / "inventory.json", inventory)
    schema = dict(version="maintenance-pilot-v0", status="provisional_synthetic_diagnostic_only",
                  assets=ASSETS, api_arguments=API_ARGS, terminal_reasons=REASONS,
                  condition=dict(sensor="temperature", op=["gt", "lt"], value=[50,70,90], unit="C"),
                  condition_scope="entire ordered action list", max_actions=2,
                  output_boundary="software canonical JSON; no new PL ABI",
                  max_input_tokens=128, truncation="forbidden; record oversize failure",
                  generator_total_context_cap=512, generator_output_cap=256,
                  generator_cap_status="provisional; measure schema/prompt/output tokens before training",
                  state="fixed catalog only; state_epoch=1; no live telemetry or execution")
    dump(args.out / "schema.json", schema)
    splits = make_pilot()
    for split, rows in splits.items():
        with (args.out / f"{split}.jsonl").open("w", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row, sort_keys=True) + "\n")
    # An oracle is an evaluator self-check, never a learned model result.
    rows = splits["diagnostic"]
    oracle = evaluate(rows, [dict(id=r["id"], output=canonical(r["gold"])) for r in rows])
    assert oracle["full_command_accuracy"] == 1
    dump(args.out / "evaluator-self-check.json", dict(kind="gold_roundtrip_not_model_accuracy", result=oracle))
    dump(args.out / "dataset-manifest.json", dict(
        schema_sha256=sha(args.out / "schema.json"),
        splits={k: dict(count=len(v), categories=dict(Counter(r["category"] for r in v)),
                        sha256=sha(args.out / f"{k}.jsonl")) for k,v in splits.items()},
        blind_test_available=False, human_reviewed=False,
        limitations=["Shared programmatic author and semantic construction across splits",
                     "Diagnostic paraphrase families are held out; not independent human blind data",
                     "Most conditions use one threshold and one comparator; no general numeric capability claim",
                     "No trained-model accuracy, quantization, board latency or energy measured"]))
    print(json.dumps(dict(out=str(args.out), counts={k:len(v) for k,v in splits.items()},
                         model_access={k:all(r["status"]=="ok" for r in v["requests"])
                                       for k,v in inventory["models"].items()}), indent=2))


if __name__ == "__main__":
    main()
