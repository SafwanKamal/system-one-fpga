"""Checkpoint replacement that preserves the previous file during transient locks."""
from pathlib import Path
import time


def write_checkpoint(payload, path: Path, save, attempts: int = 6):
    if attempts < 1:
        raise ValueError("attempts must be positive")
    path.parent.mkdir(parents=True, exist_ok=True)
    candidate = path.with_name(path.name + ".tmp")
    save(payload, candidate)
    for attempt in range(attempts):
        try:
            candidate.replace(path)
            return
        except PermissionError as error:
            if attempt + 1 == attempts:
                raise PermissionError(
                    f"Checkpoint replacement remained locked; previous checkpoint is intact, "
                    f"new candidate preserved at {candidate}. Use a checkpoint directory outside "
                    "cloud-synced folders."
                ) from error
            time.sleep(0.2 * (attempt + 1))
