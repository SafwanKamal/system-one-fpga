"""Independent checks of sealed archive bytes, chronology and final predictions."""
import argparse
import json
from pathlib import Path

import numpy as np

import study as s


def audit(final=False):
    commit = s.verify_commit()
    freeze = s.load(s.OUT / "freeze.json")
    assert s.sha(Path(s.__file__)) == freeze["code_sha256"] == commit["code_sha256"]
    assert s.sha(Path(s.__file__).with_name("PROTOCOL.md")) == freeze["protocol_sha256"]
    fit = s.load(s.OUT / "collection_fit.json")
    assert not set(fit["known_classes"]) & set(s.TASKS)
    assert not set(s.TRAIN) & set(s.TEST)
    assert freeze["frozen_utc"] < commit["committed_utc"]
    for name, digest in fit["model_hashes"].items():
        assert s.sha(s.WORK / "collection_models" / name) == digest
    known = np.load(s.WORK / "known_training.npz")
    assert not np.isin(known["y"], list(s.TASKS)).any()
    assert set(np.unique(known["subject"])) == set(s.TRAIN)
    views = sorted({Path(r["path"]).parts[1] for r in commit["archives"]})
    assert len(views) == 20 and len(commit["archives"]) == 160
    frames_checked = 0
    for subject in s.SUBJECTS:
        with np.load(s.WORK / "signals" / f"s{subject}.npz") as data:
            assert set(data.files) == {"x", "start"}
            source = {key: data[key] for key in data.files}
        for view in views:
            frames = list(s.iter_archive(s.OUT / "archives" / view / f"s{subject}.bin"))
            assert len(frames) == len(source["x"])
            for i, frame in enumerate(frames):
                x, start = s.decode_frame(frame)
                assert start == source["start"][i]
                if view.startswith(("generic_", "dct_", "downsample_")):
                    assert len(frame) + 4 <= int(view.rsplit("_", 1)[1])
                if view in ["raw32", "lossless_zlib", "lossless_lzma"]:
                    assert np.array_equal(x, source["x"][i], equal_nan=True)
                if x.ndim == 1:
                    assert np.isfinite(x).all()
                else:
                    assert np.array_equal(np.isnan(x), ~np.isfinite(source["x"][i]))
                frames_checked += 1
        print("audited subject", subject, flush=True)
    receipt = dict(checked_utc=s.utc(), archive_files=160, views=20,
                   frames_checked=frames_checked, exact_lossless_roundtrips=True,
                   caps_and_missingness_checked=True, signal_files_have_no_labels=True,
                   frozen_code_and_protocol_unchanged=True, collection_model_hashes_unchanged=True,
                   training_people_disjoint_from_test=True, archive_commit_sha256=s.sha(s.OUT / "archive_commit.json"))
    if final:
        reveal = s.load(s.OUT / "label_reveal.json")
        completed = s.load(s.OUT / "evaluation_complete.json")
        assert commit["committed_utc"] < reveal["revealed_utc"] < completed["completed_utc"]
        assert reveal["archive_commit_sha256"] == receipt["archive_commit_sha256"]
        results = s.load(s.OUT / "results.json")
        assert len(results) == len(views) * len(s.TASKS)
        for task in s.TASKS:
            raw = np.load(s.OUT / "predictions" / f"raw32_{task}.npz")
            assert set(np.unique(raw["subject"])) == set(s.TEST)
            for view in ["lossless_zlib", "lossless_lzma"]:
                other = np.load(s.OUT / "predictions" / f"{view}_{task}.npz")
                for field in raw.files:
                    assert np.array_equal(raw[field], other[field]), (view, task, field)
        receipt.update(label_reveal_chronology_checked=True, evaluations=60,
                       raw_and_lossless_predictions_bit_identical=True,
                       evaluation_code_sha256=completed["code_sha256"])
    s.dump(s.OUT / ("final_audit.json" if final else "collection_audit.json"), receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--final", action="store_true")
    audit(parser.parse_args().final)
