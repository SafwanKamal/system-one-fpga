"""Recompute reported metrics from saved test predictions and revealed labels."""
import numpy as np
from sklearn.metrics import balanced_accuracy_score, f1_score
import study as s


def main():
    assert (s.OUT / "label_reveal.json").exists()
    results = s.load(s.OUT / "results.json")
    all_labels, people = [], []
    for person in s.TEST:
        data = np.load(s.WORK / "vault" / f"s{person}.npz")
        labels = data["y"][data["eligible"]]
        all_labels.extend(labels)
        people.extend([person] * len(labels))
    all_labels, people = np.array(all_labels), np.array(people)
    pairs = 0
    for row in results:
        data = np.load(s.OUT / "predictions" / f"{row['view']}_{row['task']}.npz")
        assert np.array_equal(data["y"], all_labels == row["task"])
        assert np.array_equal(data["subject"], people)
        assert np.array_equal(data["pred"], data["score"] >= row["selected"]["threshold"])
        assert row["selected"] == max(row["cv_trials"], key=lambda trial: trial["cv_f1"])
        for person in row["per_person"]:
            take = people == person["subject"]
            y, predicted = data["y"][take], data["pred"][take]
            assert abs(f1_score(y, predicted, zero_division=0) - person["f1"]) < 1e-12
            assert abs(balanced_accuracy_score(y, predicted) - person["balanced_accuracy"]) < 1e-12
            pairs += 1
    s.dump(s.OUT / "metric_audit.json", dict(
        checked_utc=s.utc(), evaluations_checked=len(results),
        per_person_metric_pairs_checked=pairs, predictions_match_label_vault=True,
        thresholds_and_cv_selection_verified=True, audit_source_sha256=s.sha(__file__)))
    print(f"Verified {len(results)} evaluations and {pairs} person-level metric pairs")


if __name__ == "__main__":
    main()
