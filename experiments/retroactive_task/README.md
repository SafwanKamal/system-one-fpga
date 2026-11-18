# Retroactive activity learning pilot

**Research direction closed November 16, 2026, by user decision.** Preserve this
run as negative evidence; no further retention method or FPGA implementation is
planned. See [the closure record](../../docs/research/2026-11-16-sensor-memory-closure.md).

This experiment asks whether ordinary compact sensor archives preserve the ability
to learn an activity excluded from collection-time model fitting. It implements
only baseline codecs and classifiers. The pre-reveal design is in [PROTOCOL.md](PROTOCOL.md).

## Reproduction

Python 3.12; exact installed packages are recorded in `requirements-lock.txt`.
The current run reuses `build/research/future_sensor_memory/.venv/Scripts/python.exe`.
Install the lock in a fresh environment for independent reproduction.

Download the official UCI PAMAP2 ZIP to
`build/research/retroactive_task/data/PAMAP2_Dataset.zip`:
https://archive.ics.uci.edu/ml/machine-learning-databases/00231/PAMAP2_Dataset.zip

The prepare stage verifies SHA256
`6c2282b5b52775cd0588d450d10a315260c94fa3228b9fe453f48c47fda106f4`.
Run the following from the repository root, substituting the environment's Python:

```powershell
python experiments/retroactive_task/study.py --stage prepare
python experiments/retroactive_task/study.py --stage fit
python experiments/retroactive_task/freeze.py
python experiments/retroactive_task/study.py --stage collect --workers 4
python experiments/retroactive_task/audit.py
python experiments/retroactive_task/study.py --stage reveal
python experiments/retroactive_task/study.py --stage evaluate --workers 4
python experiments/retroactive_task/study.py --stage summarize
python experiments/retroactive_task/audit.py --final
python experiments/retroactive_task/metric_audit.py
python -m pytest experiments/retroactive_task/test_study.py
```

Do not overwrite a revealed run to change encoders, splits, or tasks. Use a new
output revision and a fresh pre-reveal freeze instead. `collect` refuses to run
after its reveal receipt. The source and protocol freeze is checked by `audit.py`.
This is procedural separation on one researcher's machine, not a secure enclave
or a blinded third-party trial. The custodian knows the withheld category IDs.

Outputs are in `results/research/retroactive_task/pilot_v1`: byte manifests,
collection configuration counts, reveal receipt, per-person metrics, selected
training-only validation configurations, prediction arrays, storage/quality curves,
and audit receipts. Binary archives remain locally under `archives/`, excluded
from git to avoid adding large reproducible data. Raw data and fitted collection
models are under ignored `build/`. Shared PCA and classifier model bytes are
charged in the reported storage totals even though they are stored separately.

`test_study.py` checks lossless reconstruction, quantization bounds, future-category
minority exclusion, the signal-only codec API, caps, archive integrity, and the
reveal gate. `audit.py` checks every real frame's count, timestamp, missingness and
cap, lossless equality to source, source/model freezes, chronology and identical
raw/lossless predictions. Neither audit opens future labels before reveal.

The benchmark is closed-world one-vs-rest recognition of three previously unseen
collection categories, with labeled post-reveal training and four unseen test
people. It does not establish general open-world novelty detection, arbitrary
future queries, fault diagnosis, or hardware performance. Lossless equality refers
to the selected float32 signal input, not the original decimal source text.

PAMAP2: Reiss and Stricker, UCI, DOI https://doi.org/10.24432/C5NW2H,
CC BY 4.0. CHORD (https://arxiv.org/abs/2611.11913) is a relevant stronger learned
codec reference, not reproduced by this simple-baseline screen.
