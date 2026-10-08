"""Clone the v2 corpora into data/v2/ at pinned commits (see data/v2/PROVENANCE.md).

    uv run python scripts/v2/fetch_v2_data.py

Needs git. Shallow clones; SGD is ~600 MB. HWU64, Banking77 and SNIPS (v3 models and
the few-shot evaluation) are single files from raw.githubusercontent.com, checked by sha256.
"""

from __future__ import annotations

import hashlib
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPOS = {
    "sgd": ("https://github.com/google-research-datasets/dstc8-schema-guided-dialogue",
            "e852981ae34990f4358979625854259302feaa78"),
    "slu": ("https://github.com/MiuLab/SlotGated-SLU", "61f0307c729b1fad479ef1de94aa5ac5dee601b0"),
    "sts": ("https://github.com/brmson/dataset-sts", "e1d3375f5b3bc24f21aa4e46f96eb379e9fc1081"),
}

RAW = "https://raw.githubusercontent.com/"
FILES = {
    "banking77/LICENSE": ("PolyAI-LDN/task-specific-datasets/master/LICENSE",
            "7e7170e3cebf88a9f60c7b8421418323c09304da1af4d5e90f4da1dc1c8a2661"),
    "banking77/categories.json": ("PolyAI-LDN/task-specific-datasets/master/banking_data/categories.json",
            "53261da888122daf2d120d925458631d9619e15d82e56052e7a42e535ce32b63"),
    "banking77/test.csv": ("PolyAI-LDN/task-specific-datasets/master/banking_data/test.csv",
            "d12d6e3bc4c3103966ae786dc435913c0c563dfa328f5a3646d0e62cfeeb474d"),
    "banking77/train.csv": ("PolyAI-LDN/task-specific-datasets/master/banking_data/train.csv",
            "b06e26ac675513959a63135f11b94ea7786ed02da65db93a5650d8838cbc664b"),
    "hwu/LICENSE": ("xliuhw/NLU-Evaluation-Data/master/LICENSE",
            "9ba9550ad48438d0836ddab3da480b3b69ffa0aac7b7878b5a0039e7ab429411"),
    "hwu/NLU-Data-Home-Domain-Annotated-All.csv": ("xliuhw/NLU-Evaluation-Data/master/AnnotatedData/NLU-Data-Home-Domain-Annotated-All.csv",
            "5f6dbf6d38fc111217924945ac59c554e0b926d5aa836ecdd0d089d2ca48e1d9"),
    "snips/LICENSE": ("sonos/nlu-benchmark/master/LICENSE",
            "36ffd9dc085d529a7e60e1276d73ae5a030b020313e6c5408593a6ae2af39673"),
    "snips/train_AddToPlaylist.json": ("sonos/nlu-benchmark/master/2017-06-custom-intent-engines/AddToPlaylist/train_AddToPlaylist_full.json",
            "fee1b4645352e70ed8a40f1f87c3b53fc3bf75f8ebc82252a22b82c107e75b01"),
    "snips/train_BookRestaurant.json": ("sonos/nlu-benchmark/master/2017-06-custom-intent-engines/BookRestaurant/train_BookRestaurant_full.json",
            "7677e82cd6e9a8191f0a4502568c786278c984900b4796d3628e46f1abf73ef4"),
    "snips/train_GetWeather.json": ("sonos/nlu-benchmark/master/2017-06-custom-intent-engines/GetWeather/train_GetWeather_full.json",
            "86f414b2ad8a993134d85d16e25e5d337beae47cef993c0af2a5f440405c60f6"),
    "snips/train_PlayMusic.json": ("sonos/nlu-benchmark/master/2017-06-custom-intent-engines/PlayMusic/train_PlayMusic_full.json",
            "901ddbe9781d1fdb8196e789c543f80df3d29ca6e237da64947905adcc0312e4"),
    "snips/train_RateBook.json": ("sonos/nlu-benchmark/master/2017-06-custom-intent-engines/RateBook/train_RateBook_full.json",
            "bb43e4b74134300d5766f6b420d0357a63402987a225f6dc92c806c9c040ce04"),
    "snips/train_SearchCreativeWork.json": ("sonos/nlu-benchmark/master/2017-06-custom-intent-engines/SearchCreativeWork/train_SearchCreativeWork_full.json",
            "87b3432de48c71c205aa5238b41d9e3f2d70bdfcd0bea2427544fb9e4bd5e5bb"),
    "snips/train_SearchScreeningEvent.json": ("sonos/nlu-benchmark/master/2017-06-custom-intent-engines/SearchScreeningEvent/train_SearchScreeningEvent_full.json",
            "5447e9440c02e2fb08c3ae16b9f58a4d1332b4bc77fd34691402b02aa4399765"),
    "snips/validate_AddToPlaylist.json": ("sonos/nlu-benchmark/master/2017-06-custom-intent-engines/AddToPlaylist/validate_AddToPlaylist.json",
            "14cc9ee49ae477b1452632a6e835498cf4c32da397b16967c82abb3e50403e83"),
    "snips/validate_BookRestaurant.json": ("sonos/nlu-benchmark/master/2017-06-custom-intent-engines/BookRestaurant/validate_BookRestaurant.json",
            "4f7258ccc768b777b2eb8916532db9aa50dbd058ddf1ffb0dc59218963e7442a"),
    "snips/validate_GetWeather.json": ("sonos/nlu-benchmark/master/2017-06-custom-intent-engines/GetWeather/validate_GetWeather.json",
            "60c095e193655d6ca92be220fed3926ca25e18cd70c85664145efe25d80993af"),
    "snips/validate_PlayMusic.json": ("sonos/nlu-benchmark/master/2017-06-custom-intent-engines/PlayMusic/validate_PlayMusic.json",
            "922212775e26259d5bffeaf79b6048d070ca017d229df00b2cc9800f71c75d20"),
    "snips/validate_RateBook.json": ("sonos/nlu-benchmark/master/2017-06-custom-intent-engines/RateBook/validate_RateBook.json",
            "c1f8b4114da0bb5e8afd78a8062766e18b2eabb0e717539598db01b09d04619b"),
    "snips/validate_SearchCreativeWork.json": ("sonos/nlu-benchmark/master/2017-06-custom-intent-engines/SearchCreativeWork/validate_SearchCreativeWork.json",
            "8a5e830eddb185d3e4a9d27ded140a145d04766bdce0e58834676ede32d13e77"),
    "snips/validate_SearchScreeningEvent.json": ("sonos/nlu-benchmark/master/2017-06-custom-intent-engines/SearchScreeningEvent/validate_SearchScreeningEvent.json",
            "81e1445713e03c7c3e615353c5f3fee05f369fe9834100b9b9735900a96b9498"),
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
    for rel, (path, sha) in FILES.items():
        f = base / rel
        if not f.exists():
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(urllib.request.urlopen(RAW + path).read())
        ok = hashlib.sha256(f.read_bytes()).hexdigest() == sha
        print(f"{rel}: {'ok' if ok else 'sha256 differs from the pinned copy'}")


if __name__ == "__main__":
    main()
