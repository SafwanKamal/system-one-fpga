from pathlib import Path

import pytest

from sysone.v2.checkpoint_io import write_checkpoint


def save(value, path):
    path.write_text(value)


def test_checkpoint_replaces_previous_file(tmp_path):
    path = tmp_path / "new-directory" / "checkpoint.pt"
    write_checkpoint("old", path, save)
    write_checkpoint("new", path, save)
    assert path.read_text() == "new"
    assert not path.with_name(path.name + ".tmp").exists()


def test_transient_lock_retries_without_removing_previous(tmp_path, monkeypatch):
    path = tmp_path / "checkpoint.pt"
    path.write_text("old")
    replace = Path.replace
    calls = []

    def locked(candidate, target):
        calls.append(target.read_text())
        if len(calls) < 3:
            raise PermissionError("locked")
        return replace(candidate, target)

    monkeypatch.setattr(Path, "replace", locked)
    monkeypatch.setattr("sysone.v2.checkpoint_io.time.sleep", lambda _: None)
    write_checkpoint("new", path, save)
    assert calls == ["old", "old", "old"]
    assert path.read_text() == "new"


def test_persistent_lock_preserves_both_recovery_files(tmp_path, monkeypatch):
    path = tmp_path / "checkpoint.pt"
    path.write_text("old")
    def locked(*args):
        raise PermissionError("locked")
    monkeypatch.setattr(Path, "replace", locked)
    monkeypatch.setattr("sysone.v2.checkpoint_io.time.sleep", lambda _: None)
    with pytest.raises(PermissionError, match="new candidate preserved"):
        write_checkpoint("new", path, save, attempts=2)
    assert path.read_text() == "old"
    assert path.with_name(path.name + ".tmp").read_text() == "new"
