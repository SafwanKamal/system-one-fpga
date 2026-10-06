"""Clone the v2 corpora into data/v2/ at pinned commits (see data/v2/PROVENANCE.md).

    uv run python scripts/v2/fetch_v2_data.py

Needs git. Shallow clones; SGD is ~600 MB.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPOS = {
    "sgd": ("https://github.com/google-research-datasets/dstc8-schema-guided-dialogue",
            "e852981ae34990f4358979625854259302feaa78"),
    "slu": ("https://github.com/MiuLab/SlotGated-SLU", "61f0307c729b1fad479ef1de94aa5ac5dee601b0"),
    "sts": ("https://github.com/brmson/dataset-sts", "e1d3375f5b3bc24f21aa4e46f96eb379e9fc1081"),
}


def main() -> None:
    base = ROOT / "data" / "v2"
    base.mkdir(parents=True, exist_ok=True)
    for name, (url, commit) in REPOS.items():
        d = base / name
        if not d.exists():
            subprocess.run(["git", "clone", "--depth", "1", url, str(d)], check=True)
        head = subprocess.run(["git", "-C", str(d), "rev-parse", "HEAD"], check=True,
                              capture_output=True, text=True).stdout.strip()
        note = "" if head == commit else f"  (pinned {commit[:8]}; upstream has moved)"
        print(f"{name}: {head[:8]}{note}")


if __name__ == "__main__":
    main()
