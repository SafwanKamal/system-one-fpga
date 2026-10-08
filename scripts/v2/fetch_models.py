"""Download the pretrained encoders the v2 chain models start from into models/.

    uv run --group train python scripts/v2/fetch_models.py            # all-MiniLM-L6-v2
    uv run --group train python scripts/v2/fetch_models.py bert-mini  # also bert-mini

Public Hugging Face repositories, no account or token needed. models/ is not in git.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPOS = {
    "all-MiniLM-L6-v2": "sentence-transformers/all-MiniLM-L6-v2",   # Apache 2.0
    "bert-mini": "prajjwal1/bert-mini",                              # MIT
}
FILES = ["config.json", "*.safetensors", "pytorch_model.bin", "tokenizer.json",
         "tokenizer_config.json", "vocab.txt", "special_tokens_map.json"]


def main() -> int:
    from huggingface_hub import snapshot_download
    from transformers import AutoTokenizer
    names = ["all-MiniLM-L6-v2"] + [n for n in sys.argv[1:] if n != "all-MiniLM-L6-v2"]
    for name in names:
        if name not in REPOS:
            raise SystemExit(f"unknown model {name}; known: {', '.join(REPOS)}")
        out = ROOT / "models" / name
        snapshot_download(REPOS[name], local_dir=out, allow_patterns=FILES)
        # a fast-tokenizer file is what the host client's WordPiece reads
        if not (out / "tokenizer.json").exists():
            AutoTokenizer.from_pretrained(out).save_pretrained(out)
        print(f"{name}: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
