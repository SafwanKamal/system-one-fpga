# Fresh held-out R5 accuracy and latency results

First batch: **700/700 requests completed, zero runtime errors**,100 fresh test cases per dataset group. R5 controlled PL and computed classifier/slot heads; Linux stayed running and JTAG stayed stopped. The PL app, model, R5 firmware and deployed client were unchanged.

| Dataset | Label accuracy | Slot span F1 | Request p50 ms | Request p95 ms |
|---|---:|---:|---:|---:|
| atis | 98.0% (98/100) | 0.890 | 254.1 | 307.0 |
| clinc | 89.0% (89/100) | - | 188.1 | 189.0 |
| hwu | 92.0% (92/100) | 0.843 | 218.8 | 261.4 |
| msrp | 73.0% (73/100) | - | 200.2 | 211.1 |
| multi_clinc | 83.3% (255/306) | - | 210.1 | 226.0 |
| sgd | 89.0% (73/82) | 0.528 | 247.3 | 329.8 |
| sick | 80.0% (80/100) | - | 183.6 | 189.2 |

Overall observed on-board request latency: p50 **208.9ms**, p95 **277.7ms**, p99 **332.4ms**. PL encoder alone: p50 **8.54ms**, p95 **22.65ms**.

## Sample and scoring

Seed20261017 selected100 per dataset from the existing test splits, then randomized execution order. Exact encoded inputs from training/development and the previous350-case reference suite were excluded, as were previous-reference text segments and duplicate selected inputs. Label tables matched the model. These are fresh examples relative to that reference run, from existing benchmark test sets; no retraining, threshold fitting or new dataset sourcing occurred. Selection and complete input/ground-truth data are saved in selection.json and cases.json.

Accuracy is measured against dataset ground truth, not against another implementation. Multi-CLINC counts each retained segment decision, so its denominator exceeds100. Slot F1 is micro-averaged BIO entity-span F1 over retained words after128-token truncation, using the existing dataset-loader label policy. Unknown/unscored intent counts: {"sgd": 18}. These are excluded from the accuracy denominator. Each dataset has100 requests; percentages are sample estimates.

## Latency scope

On-board perf_counter_ns; end-to-end starts before tokenization and ends after R5 completion/cleanup. Includes runtime checks, TCM preparation, firmware PM, PL, R5 heads, result copy and stop. Excludes lock wait, initial loading, SSH, scoring and log writes. PL cycles separately measured; no isolated R5-head timer or WCET claim. Values are from a single sequential pass through a long-lived board process, with the tokenizer cache evolving normally. They are not cold CLI process-launch or network response measurements. Every request still prepares/starts R5 and confirms stop/resource release, as in the deployed client. Request timing includes that overhead. No hard real-time bound is inferred.

## Data and final state

Local build/v2/typed200-r5-heldout-eval-v1 contains requests.jsonl (predictions, gold labels, logit hashes, timings and R5 completion/cleanup for every request), requests.csv, summary.json, summary.csv, metadata.json and selection.json. Remote collection stage is /var/lib/sysone/r5-evaluation/fresh-test-v1.

Boot remained 6c80ec1a-e7ae-473f-b169-d54f129615d1; PL clock was199999998Hz. All700 R5 completions and resource releases were checked. The app/model and R5 module remain deployed and sysone-infer remains ready. UART was closed after collection. The finite first batch has finished; no recurring collection job was installed.

The companion validation JSON records preserved prior files and hashes for this batch. HANDOFF.md remains mutable.
