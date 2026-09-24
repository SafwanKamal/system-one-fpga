"""CLINC150 loading.

Labels are gold (see data/clinc150/PROVENANCE.md). The only judgement call made
here is how out-of-scope is represented, and it is made explicit below.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

OOS_LABEL = "oos"

_DEFAULT = Path(__file__).resolve().parents[2] / "data" / "clinc150" / "data_full.json"


@dataclass
class Split:
    texts: list[str]
    y: np.ndarray          # int label ids, index into Dataset.labels
    is_oos: np.ndarray     # bool, True for out-of-scope records

    def __len__(self) -> int:
        return len(self.texts)


@dataclass
class Dataset:
    labels: list[str]      # labels[oos_id] == "oos"; oos_id is the last index
    train: Split
    val: Split
    test: Split

    @property
    def n_classes(self) -> int:
        return len(self.labels)

    @property
    def oos_id(self) -> int:
        return self.labels.index(OOS_LABEL)


def _mk(records: list[list[str]], label_to_id: dict[str, int]) -> Split:
    texts = [r[0] for r in records]
    y = np.asarray([label_to_id[r[1]] for r in records], dtype=np.int32)
    is_oos = np.asarray([r[1] == OOS_LABEL for r in records], dtype=bool)
    return Split(texts=texts, y=y, is_oos=is_oos)


def load_clinc150(path: Path | str = _DEFAULT, variant: str = "full") -> Dataset:
    """Load CLINC150 with out-of-scope folded in as one extra class.

    Two designs were possible. A separate binary in-scope/out-of-scope detector is
    the more common research setup, but it needs a second model and a second
    threshold, and the board has to hold both. Folding OOS in as class 150 keeps
    one forward pass and one argmax -- which is what the RTL will actually do --
    and still supports abstention, because abstention on this task is just
    "argmax lands on the oos class, or max probability is below a threshold".

    The cost is honest and must be reported with the results: the train set has
    100 OOS examples against 15,000 in-scope, a 150:1 imbalance, so the OOS class
    is badly under-trained relative to the others. That is why the eval reports
    in-scope accuracy and OOS recall separately instead of one pooled number.
    """
    path = Path(path)
    if variant != "full":
        path = path.parent / f"data_{variant}.json"
    with open(path) as f:
        raw = json.load(f)

    in_scope = sorted({r[1] for r in raw["train"] if r[1] != OOS_LABEL})
    labels = in_scope + [OOS_LABEL]
    label_to_id = {lab: i for i, lab in enumerate(labels)}

    def merged(a: str, b: str) -> list[list[str]]:
        return list(raw.get(a, [])) + list(raw.get(b, []))

    return Dataset(
        labels=labels,
        train=_mk(merged("train", "oos_train"), label_to_id),
        val=_mk(merged("val", "oos_val"), label_to_id),
        test=_mk(merged("test", "oos_test"), label_to_id),
    )


def majority_floor(split: Split, n_classes: int) -> tuple[float, int]:
    """Accuracy of always predicting the most common class, and which class that is.

    Every accuracy number in this project is reported against this. On CLINC150's
    combined test set the floor is 18.2% (always say "oos"), which is high enough
    that an unqualified accuracy figure would be misleading.
    """
    counts = np.bincount(split.y, minlength=n_classes)
    top = int(counts.argmax())
    return float(counts[top] / len(split.y)), top
