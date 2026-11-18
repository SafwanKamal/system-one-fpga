# Diagnostic probe baseline experiment

Completed November 16, 2026. See the [result and decision](../../docs/research/2026-11-16-diagnostic-probe-pilot.md).

This is a synthetic unicycle study, not a robot trial or a new diagnostic method.
The original [proposal](PROTOCOL.md), [executable specification](RUN_SPEC.md),
`simulator.py`, `diagnosis.py`, `study.py` and `oracle.py` are hash-frozen before
final evaluation. Later audits and report generation are separate files.

The existing `build/research/future_sensor_memory/.venv/Scripts/python.exe`
ran the primary study on CPU. Exact packages are recorded in the results'
`environment.json`; a copy of the environment lock is saved here. Paths below
are relative to the repository root; substitute the environment's Python.

```powershell
python -m pytest experiments/catalog_validation/test_study.py
python experiments/catalog_validation/study.py --stage prepare --workers 4
python experiments/catalog_validation/study.py --stage fit
python experiments/catalog_validation/study.py --stage freeze
python experiments/catalog_validation/study.py --stage evaluate --workers 4
python experiments/catalog_validation/oracle.py --workers 2
python experiments/catalog_validation/study.py --stage summarize
python experiments/catalog_validation/analyze.py
python experiments/catalog_validation/audit.py
```

Use a new output/work revision for reproduction. Source development and frozen
test panels must never be overwritten. The generator refuses to overwrite
existing panel files, and final generation requires the freeze. Results and
selection contain every decoder, fixed probe and rejection setting, not just a
headline winner. Large counterfactual traces stay under ignored `build/` and
are pinned by the data manifest. Small prediction arrays remain in results.

The primary panel is `build/research/catalog_validation/panel_v1`. Earlier
development-only files under `build/research/catalog_validation/data` predate
qualification fixes; they are not the frozen experiment and contain no final
test panel. Qualification separated the disturbance RNG from severity generation
so extending a trajectory preserves its underlying world; it also added proper
one-slot cost accounting and a calibrated healthy-model margin. These changes
preceded the final test freeze. No primary source, model, threshold or fixed
probe changed after final generation.

## Reference example

Author repository: https://github.com/gtfactslab/Ni_RAL2026 ; commit
`19ef5d0032b866330ac998f0096cebedee671315`.

The pinned `immrax==0.1.0` is unavailable on PyPI. An isolated reference
environment used the author's immrax source commit
`3c452fa260980a16ba53b9a7dad8df20f478ca92` (version 0.1.0), the pinned JAX
0.4.34/equinox 0.11.7, and compatible diffrax 0.5.1. Full installed versions
are in `reference/*demo.json`. Do not install these into the primary environment.

With the two source checkouts under the work directory:

```powershell
build/research/catalog_validation/reference-env/Scripts/python.exe experiments/catalog_validation/reference.py --example multistep_unrefined_demo.py
```

`reference.py` supplies Windows process-memory reporting in place of the Unix
`resource` module. It does not change the upstream numerical source. The default
two-second multistep example returned zero pairwise output-box overlap. The
shorter 1.2-second refined example retained nonzero overlap; both are recorded.
The original receipts' `source_unmodified=false` flag includes untracked Python
cache files. `reference/tracked_source_audit.json` independently confirms the
tracked upstream source was unchanged. This is an example execution, not a
reproduction of the paper's robot experiments or timing claims.

## Supplemental checks

These were added after inspecting the primary results and are explicitly
exploratory; they are not silently folded into the preregistered comparison:

```powershell
python experiments/catalog_validation/supplement.py
python experiments/catalog_validation/supplement.py --noise --workers 4
python experiments/catalog_validation/margin_audit.py
```

Recent/worst-window residual baselines choose thresholds and fixed probes on
source validation only and save a separate freeze before their final-panel
evaluation. Noise-transfer checks change only disturbances after second 8,
preserving the world and the observed prefix. First-success, margin-based and
two-noise outcome-informed choices are oracle sensitivity checks, not deployable
selectors. No new learned adaptive policy was built.

The true-state evaluator, hidden mechanisms and counterfactual siblings are
outside the selector API, which takes only observed commands and poses. Audits
check source/model freezes, label-independent commissioning prefixes, branch
causality, actual bounded interventions, serial reproduction of saved traces,
selected-action replay and independently reconstructed metrics. This is
procedural separation on one researcher's machine, not secure third-party blinding.
