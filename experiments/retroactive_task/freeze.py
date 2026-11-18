"""Record the protocol/source commitment before collection in a fresh run."""
from pathlib import Path
import study as s

if __name__ == "__main__":
    assert not (s.OUT / "archive_commit.json").exists(), "Use a fresh run revision."
    assert not (s.OUT / "label_reveal.json").exists()
    assert not (s.OUT / "freeze.json").exists(), "Do not overwrite an existing freeze."
    s.dump(s.OUT / "freeze.json", dict(
        frozen_utc=s.utc(), code_sha256=s.sha(s.__file__),
        protocol_sha256=s.sha(Path(s.__file__).with_name("PROTOCOL.md")),
        future_labels_revealed=False, primary_task="running",
        secondary_tasks=["cycling", "ascending_stairs"], test_subjects=s.TEST))
