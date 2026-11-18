"""Run a batch of real-text routing probes; save complete output for review."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
CASES = [
    ("flight", "show me flights from boston to denver tomorrow morning", False),
    ("flight_return", "find a round trip flight from dallas to seattle next friday", False),
    ("lights_off", "turn off the lights in the kitchen", False),
    ("lights_on", "turn on the bedroom lights", False),
    ("restaurant", "book me a table for two at an italian restaurant tomorrow evening", False),
    ("hotel", "book a hotel in chicago for two nights", False),
    ("alarm", "set an alarm for seven tomorrow morning", False),
    ("weather", "what will the weather be in boston tomorrow", False),
    ("electronics_oos", "how should I build a h-bridge circuit?", False),
    ("technical_oos", "explain metastability in a clock domain crossing", False),
    ("ambiguous", "cancel it", False),
    ("negation", "do not turn off the kitchen lights", False),
    ("custom_build", "synthesize the fpga encoder and generate a bitstream", True),
    ("custom_timing", "show the worst setup slack for this design", True),
    ("custom_electronics", "help me choose a motor driver for an h bridge", True),
    ("custom_inventory", "add ten breadboards to the lab shopping list", True),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--image", default="minilm-l6-v3b-kr260")
    ap.add_argument("--out", type=Path, default=ROOT / "build/v2/eval/kr260-routing-batch.json")
    ap.add_argument("--list", action="store_true", help="show probes without accessing hardware")
    args = ap.parse_args()
    if args.list:
        for name, query, custom in CASES:
            print(f"{name} ({'custom' if custom else 'auto'}): {query}")
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    report = {"image": args.image, "complete": False, "cases": [],
              "note": "Routing probes for human review; no aggregate accuracy claim. Negation and ambiguity may expose limitations."}
    log = args.out.with_suffix(".txt")
    log.write_text("", encoding="utf-8")
    for index, (name, query, custom) in enumerate(CASES, 1):
        cmd = [sys.executable, str(ROOT / "scripts/v2/sysone_v2_client.py"),
               "--kr260", "--image", args.image, "run", "--dataset", "auto"]
        if custom:
            cmd += ["--intents", str(ROOT / "examples/v2/custom_intents.json")]
        cmd.append(query)
        title = f"[{index}/{len(CASES)}] {name}: {query}"
        print(title, flush=True)
        start = time.perf_counter()
        try:
            result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=120)
            output, code = result.stdout + result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            output, code = "Client did not finish within 120 seconds; batch stopped.\n", 124
        print(output, end="", flush=True)
        report["cases"].append({"name": name, "query": query, "custom": custom,
                                "returncode": code, "host_process_seconds": time.perf_counter() - start,
                                "output": output})
        with log.open("a", encoding="utf-8") as handle:
            handle.write(title + "\n" + output + "\n")
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if code:
            return code
    report["complete"] = True
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {args.out} and {log}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
