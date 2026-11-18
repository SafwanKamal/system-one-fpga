# Remaining held-out R5 accuracy and latency

Completed **55,261/55,261 new requests with zero runtime errors**. The previous700 were excluded by encoded-input hash, including duplicate copies of those inputs. R5 controlled PL inference and computed classifier/slot heads, Linux stayed running, and JTAG stayed stopped. Model, PL, firmware, tokenizer and deployed client were unchanged.

| Dataset | Requests | Classification accuracy | Slot span F1 | Request p50 ms | Request p95 ms |
|---|---:|---:|---:|---:|---:|
| atis | 690 | 97.1% (670/690) | 0.888 | 255.2 | 306.7 |
| clinc | 5,169 | 86.8% (4486/5169) | - | 188.5 | 189.5 |
| hwu | 2,354 | 91.2% (2148/2354) | 0.748 | 219.7 | 260.6 |
| msrp | 1,574 | 68.1% (1072/1574) | - | 196.0 | 207.0 |
| multi_clinc | 1,211 | 85.0% (3047/3586) | - | 209.9 | 227.6 |
| sgd | 39,747 | 85.9% (29221/34003) | 0.537 | 244.9 | 330.8 |
| sick | 4,516 | 76.7% (3466/4516) | - | 184.0 | 189.8 |

## What improved compared with previous runs

Earlier350-case reference runs established numerical correctness against a frozen implementation. The first700 fresh cases added ground-truth accuracy and on-board latency. This run exhausts the remaining eligible existing test inputs, making each dataset estimate substantially less dependent on a100-example sample and checking sustained runtime stability. Journals retain predictions, gold labels, hashes, timings and R5 cleanup evidence. Collection now streams detailed records, keeps only compact statistics in memory, checkpoints every250 requests, transfers an archive, and runs under a bounded independent systemd job. These are evaluation/collection improvements; no model accuracy or inference speed optimization was applied.

| Dataset | First100 accuracy | Remaining accuracy | Difference pp | First100 p50 ms | Remaining p50 ms |
|---|---:|---:|---:|---:|---:|
| atis | 98.0% | 97.1% | -0.90 | 254.1 | 255.2 |
| clinc | 89.0% | 86.8% | -2.21 | 188.1 | 188.5 |
| hwu | 92.0% | 91.2% | -0.75 | 218.8 | 219.7 |
| msrp | 73.0% | 68.1% | -4.89 | 200.2 | 196.0 |
| multi_clinc | 83.3% | 85.0% | +1.64 | 210.1 | 209.9 |
| sgd | 89.0% | 85.9% | -3.09 | 247.3 | 244.9 |
| sick | 80.0% | 76.7% | -3.25 | 183.6 | 184.0 |

Differences above compare disjoint examples, not before/after model versions. They do not demonstrate an optimization gain. The combined-summary.json pools this run and the original700 with exact percentile recomputation. SGD unknown intents remain outside the classification denominator; counts are in summary.csv. Multi-CLINC accuracy counts retained segment decisions. Slot F1 uses existing BIO entity spans and labels over retained words after128-token truncation.

## Coverage and timing

All eligible remaining examples from the seven existing test groups were selected with seed20261018 and randomized execution order. As in the first batch, encoded train/dev overlap, previous350 reference inputs/text segments, duplicate selected inputs and unsupported request shapes were excluded; selection.json records every exclusion category by dataset. This is coverage of the filtered test pools, not every raw test row. No labels were used for selection or tuning.

On-board perf_counter_ns; end-to-end starts before tokenization and ends after R5 completion/cleanup. Includes runtime checks, TCM preparation, firmware PM, PL, R5 heads, result copy and stop. Excludes lock wait, initial loading, SSH, scoring and log writes. PL cycles separately measured; no isolated R5-head timer or WCET claim. Single sequential long-lived process; no cold CLI/network timing or isolated R5-head timer.

## Artifacts and final state

build/v2/typed200-r5-heldout-remaining-v1 contains cases.json, selection.json, requests.jsonl, requests.csv, summary.json, summary.csv, combined-summary.json, metadata.json, UART and target execution logs. Same Linux boot and200MHz PL clocks checked after completion; all per-request R5 resource releases checked. App/model and R5 module stay deployed; dashboard stays stopped. No auto-reboot or recurring job.
