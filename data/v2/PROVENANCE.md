# v2 external corpora

Not vendored (SGD alone is ~600 MB). `uv run python scripts/v2/fetch_v2_data.py`
clones them here at the commits below; `data/v2/*/` is gitignored.

| dir | source | commit | used for | licence |
|---|---|---|---|---|
| `sgd/` | github.com/google-research-datasets/dstc8-schema-guided-dialogue | e852981a | multi-turn dialogue: intent + slots per user turn | CC BY-SA 4.0 |
| `slu/` | github.com/MiuLab/SlotGated-SLU (`data/atis`) | 61f0307c | ATIS intent + slots | ATIS is LDC-derived; this preprocessed copy is the one widely used in SLU papers. Research use. |
| `sts/` | github.com/brmson/dataset-sts (`data/sts/sick2014`, `data/para/msr`) | e1d3375f | SICK entailment, MSRP paraphrase | SICK: CC BY-NC-SA 3.0. MSRP: Microsoft Research licence (see `data/para/msr/LICENCE.html`), research use. |

CLINC150 stays vendored in `data/clinc150/` (CC BY 3.0).

The NC/research-only terms of ATIS, SICK and MSRP matter if a model trained on
them is ever distributed commercially; the dialogue model alone (SGD + CLINC150)
has no such restriction.
