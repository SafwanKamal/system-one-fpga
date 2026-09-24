# CLINC150 — provenance and license

## Source

Vendored from the official repository accompanying the paper, not from a
third-party mirror:

- Repo: `https://github.com/clinc/oos-eval`
- Commit: `828f8093932c8fe6ca7936c3d2e52903b1c523de`
- Retrieved: 2026-09-20

## License

Creative Commons Attribution 3.0 Unported (CC BY 3.0). Full text in `LICENSE`.
CC BY 3.0 permits commercial and non-commercial use, redistribution and
derivative works, provided attribution is given. Redistribution of the vendored
copy inside this repository is therefore permitted; this file is the attribution.

## Citation

```
@inproceedings{larson-etal-2019-evaluation,
    title = "An Evaluation Dataset for Intent Classification and Out-of-Scope Prediction",
    author = "Larson, Stefan and Mahendran, Anish and Peper, Joseph J. and
              Clarke, Christopher and Lee, Andrew and Hill, Parker and
              Kummerfeld, Jonathan K. and Leach, Kevin and Laurenzano, Michael A. and
              Tang, Lingjia and Mars, Jason",
    booktitle = "Proceedings of the 2019 Conference on Empirical Methods in Natural
                 Language Processing and the 9th International Joint Conference on
                 Natural Language Processing (EMNLP-IJCNLP)",
    year = "2019",
    url = "https://www.aclweb.org/anthology/D19-1131",
}
```

## Label provenance — why this dataset was chosen

Every label here is **human-assigned**. The queries were produced by crowd workers
who either paraphrased seed phrases or responded to scenario prompts, and the
intent label comes from the prompt the worker was answering, not from a model.

This matters for the project plan's caution about teacher-generated labels
(the 0.735 agreement ceiling on scraped typed-decision data). CLINC150 has no such
ceiling: it is gold, so it can serve both as student training data and as the
evaluation set against which a distilled student and its teacher are *both* scored.

## Splits in `data_full.json`

| Key | n | Contents |
|---|---|---|
| `train` | 15,000 | 150 in-scope intents x 100 |
| `val` | 3,000 | 150 in-scope intents x 20 |
| `test` | 4,500 | 150 in-scope intents x 30 |
| `oos_train` | 100 | out-of-scope |
| `oos_val` | 100 | out-of-scope |
| `oos_test` | 1,000 | out-of-scope |

Each record is `[utterance, intent_label]`. The in-scope splits are exactly
balanced, which fixes the majority-class floor for in-scope-only evaluation at
1/150 = 0.667%. On the combined `test + oos_test` set (5,500 records) the majority
class is `oos` at 1000/5500 = 18.18%, and that is the floor any combined-set
accuracy number must be reported against.

Other files (`data_small.json`, `data_imbalanced.json`, `data_oos_plus.json`)
carry the same 150 intents under different train-set sizes / OOS ratios and are
kept for later robustness runs. `domains.json` maps the 150 intents to 10 domains.
