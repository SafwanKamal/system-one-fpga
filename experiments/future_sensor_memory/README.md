# Future-question sensor memory pilot

Standalone software experiment; no board access. Read [PROTOCOL.md](PROTOCOL.md) for the frozen data split, information boundary, baselines, question families, and rejection criteria.

The input is a compact feature stream derived from the **official ExtraSensory dataset**, not continuously sampled raw sensor signals. The experiment separates retention error against complete feature history from upstream recognition error against the supplied activity labels. Questions are structured and seeded, not the original SensorQA annotations. No language model is needed for this first discriminator.

## Reproduce

From the repository root, on Windows PowerShell:

```powershell
uv venv build/research/future_sensor_memory/.venv
uv pip install --python build/research/future_sensor_memory/.venv/Scripts/python.exe -r experiments/future_sensor_memory/requirements-lock.txt
build/research/future_sensor_memory/.venv/Scripts/python.exe -m pytest experiments/future_sensor_memory/test_pilot.py -q
build/research/future_sensor_memory/.venv/Scripts/python.exe experiments/future_sensor_memory/pilot.py --stage prepare
build/research/future_sensor_memory/.venv/Scripts/python.exe experiments/future_sensor_memory/pilot.py --stage validate
build/research/future_sensor_memory/.venv/Scripts/python.exe experiments/future_sensor_memory/pilot.py --stage test
build/research/future_sensor_memory/.venv/Scripts/python.exe experiments/future_sensor_memory/pilot.py --stage summarize
build/research/future_sensor_memory/.venv/Scripts/python.exe experiments/future_sensor_memory/audit.py
build/research/future_sensor_memory/.venv/Scripts/python.exe experiments/future_sensor_memory/analyze.py
build/research/future_sensor_memory/.venv/Scripts/python.exe experiments/future_sensor_memory/report.py
```

Preparation downloads the official 225 MB feature archive if absent, checks its SHA-256, and caches parsed streams and a training-only fitted classifier under `build/research/future_sensor_memory/`. Validation must finish before test; it produces a frozen `selection.json`. Re-running stages overwrites their own generated results. Use a different output directory in the source for a separately named research revision.

Results are written under `results/research/future_sensor_memory/pilot_v2/`: provenance, participant split and inventory, recognition quality, per-participant metrics, query definitions and reference answers, compressed per-query answers, and the serialized test memories used to answer those queries. All memory answers are decoded from the same bytes saved as `.bin` files. The archive cap includes timelines, gaps, missingness, sample indices, retained priorities, and a 64-byte RNG/previous-record ingestion-state allowance. Python object overhead, fixed input-chunk scratch, frozen shared models, and query decode workspace are outside that cap.

The two candidate versions are simple change-priority and adjacent-pair retention heuristics in the same coarse-table/residual format as the uniform hybrid baseline. They are not SVMemAgent reproductions or newly trained task-reward policies. A failure to beat the simple baselines is a reason to stop this implementation direction; it is not a theorem about all possible future-query memory algorithms.

For faster execution, `run_parallel.py --stage validation --workers 4` and `run_parallel.py --stage test --workers 4` substitute for the corresponding serial stages; they preserve participant query seeds. V2 corrects a worker-seed accumulation bug discovered during the V1 audit. All validation and test evaluations were rerun with the original split, policies, parameter search and selection rule. V1 artifacts, including its interrupted-log recovery records, are preserved under `pilot_v1/`; they are superseded. V2 logs require no recovery. `frontier_common_cohort.png` is the comparison plot to use: it holds the participant cohort fixed across budgets. The initial `frontier.png` from the generic summarizer uses all eligible participants at each budget, so its cohort varies.

`analyze.py` also reports a clearly labeled exploratory sensor-only question panel, generated after memory creation. It uses the same frozen archives and selections, with no retraining or policy change. This checks whether poor activity recognition explains the retention result.

## Attribution

Yonatan Vaizman, Katherine Ellis, and Gert Lanckriet, *Recognizing Detailed Human Context In-the-Wild from Smartphones and Smartwatches*, IEEE Pervasive Computing, 2017. Dataset and original publication: https://extrasensory.ucsd.edu/ . Source archive: https://extrasensory.ucsd.edu/data/primary_data_files/ExtraSensory.per_uuid_features_labels.zip . Cite this original work when using the data.

SensorQA (Reichman et al., 2025) motivated the application and dataset selection: https://arxiv.org/abs/2501.04974 . This pilot does not report SensorQA benchmark scores.
