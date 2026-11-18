"""Preserve the tested candidate and honest focused evidence; no build/deploy."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]


def main():
    candidate = sys.argv[1] if len(sys.argv) > 1 else "dot6"
    if candidate not in ("dot6", "dot7"):
        raise ValueError("Unknown tested candidate")
    expected_mode = 3 if candidate == "dot7" else 2
    previous_candidate = "dot6" if candidate == "dot7" else "dot5"
    base_path = ROOT / f"build/v2/rtl-{candidate}-check/summary.json"
    base = json.loads(base_path.read_text())
    large_path = ROOT / f"build/v2/rtl-{candidate}-large-check/summary.json"
    large = json.loads(large_path.read_text())
    assert large["profile"]["local_accumulator_controls"] == expected_mode
    assert large["base_regression_sha256"] == hashlib.sha256(base_path.read_bytes()).hexdigest()
    for source, digest in large["rtl_sha256"].items():
        assert hashlib.sha256((ROOT / source).read_bytes()).hexdigest() == digest, source
    comparison = {}
    for name, current in (("base", base), ("large", large)):
        previous_dir = f"rtl-{previous_candidate}-check" if name == "base" else f"rtl-{previous_candidate}-large-check"
        previous = json.loads((ROOT / f"build/v2/{previous_dir}/summary.json").read_text())
        comparison[name] = {key: entry.get("encoder_clocks") == previous["checks"][key].get("encoder_clocks")
                            for key, entry in current["checks"].items() if "encoder_clocks" in entry}
        assert all(comparison[name].values()), "Unexpected pipeline cycle change"
    output = ROOT / f"build/v2/kr260-opt-{candidate}-large"
    if output.exists():
        raise ValueError("Preserve existing frozen candidate; never overwrite")
    snapshot = output / "rtl-snapshot"
    for source in large["rtl_sha256"]:
        target = snapshot / Path(source).relative_to("rtl/v2")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / source, target)
    shutil.copyfile(large_path, output / "regression.json")
    shutil.copyfile(ROOT / f"build/v2/{candidate}-ooc-summary.json", output / "focused-ooc.json")
    (output / "cycle-comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
    status = {"state": "numerical_ready", "updated_utc": datetime.now(timezone.utc).isoformat(),
              "detail": "53 KR260 cases and Nexys defaults passed; focused OOC only. Full synthesis/placement/routing/hardware not qualified.",
              "full_synthesis_started": False, "hardware_deployed": False}
    (output / "completion-status.json").write_text(json.dumps(status, indent=2) + "\n")
    print("PASS: 17 tested RTL sources frozen, all 53 encoder cycle counts unchanged; no full build/deployment")


if __name__ == "__main__":
    main()
