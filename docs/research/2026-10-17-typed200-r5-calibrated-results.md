# R5 classifier calibration: paired hardware results

**PROMOTED: the calibrated R5 classifier is deployed and sysone-infer uses it.**

The original55,261-case remaining-set benchmark completed first with zero runtime errors. Its baseline artifacts are preserved. Then the R5 fixed image was replaced through the existing Linux PM/module path; PL and model weights were reused. Linux stayed running and JTAG stayed stopped.

| Dataset | Paired requests | Baseline accuracy | Calibrated accuracy | Gain pp | Median ms before / after | p95 ms before / after |
|---|---:|---:|---:|---:|---:|---:|
| clinc | 5,269 | 86.83% | 90.97% | +4.14 | 188.5 / 188.3 | 189.5 / 189.5 |
| multi_clinc | 1,311 | 84.84% | 89.98% | +5.14 | 210.0 / 214.5 | 227.4 / 231.0 |

## Concrete change

R5 now applies a calibrated CLINC rejection rule: a top softmax probability below0.36 selects the existing out-of-scope class. This also applies separately to Multi-CLINC segments. Scaled logits, probability normalization and the decision execute on R5; Linux still only tokenizes/transports/formats. Every integer logit and every other head is unchanged. This is a classifier calibration improvement; encoder and classifier weights were not retrained.

The missing older0.48 rule improved OOS recall but lost3 correct examples on development. The new0.36 threshold maximizes total accuracy on the existing3,100-example development split under at most1 percentage point in-scope loss:2965/3100(95.65%) to2977/3100(96.03%); OOS recall52% to73%, in-scope accuracy97.1% to96.8%. Current held-out labels were not used to fit the threshold. Cached first3,000 dev probabilities were checked against fresh computations at5 positions; the missing100 were computed from the deployed integer image. The old failed candidate artifacts are preserved.

Native C matched NumPy decisions on all3,100 development examples; exponential absolute error was at most2.23e-16 on20,004 grid/extreme inputs. Native heads matched191,401 integer logits on350 frozen requests; actual Cortex-R5F emulation exercised changed OOS rejection. Hardware then independently checked all350 requests and191,401 logits before the paired evaluation.

## Paired evaluation and promotion

The6580 inputs are exactly the CLINC and Multi-CLINC requests in the first700 plus the remaining55,261 baseline. The candidate evaluated each once, in a new deterministic shuffled order. Labels/inputs are identical within each comparison. CLINC counts one decision per request; Multi-CLINC counts retained segments. The promotion gate requires no accuracy regression in either dataset and a strictly positive combined gain; otherwise the prior fixed-image module is restored while idle. No threshold was refit after this test.

On-board perf_counter_ns; end-to-end starts before tokenization and ends after R5 completion/cleanup. Includes runtime checks, TCM preparation, firmware PM, PL, R5 heads, result copy and stop. Excludes lock wait, initial loading, SSH, scoring and log writes. PL cycles separately measured; no isolated R5-head timer or WCET claim. Sequential passes were at different times/cache states, so latency changes are observations rather than a controlled speedup claim.

## Deployment and artifacts

Current R5 ELF SHA256: 1ff1f09d422492f7e3d3af3632ed9ffb1e3268ff5d1bfd699d57486e6eee3b95. Same Linux boot, CPUs0-3 and199999998Hz PL clocks. All6580 R5 completions/resource releases verified. Model, PL, tokenizer and CLI client remain unchanged; R5 module stays loaded, R5 is idle between requests, dashboard stays stopped. This remains a current-boot CLI deployment.

build/v2/typed200-linux-r5-calibrated-v1 contains paired-summary.csv, paired-requests.csv, paired-comparison.json, calibration-dev-fit.json, hardware-results/requests.jsonl, summary.json, metadata.json, hardware-validation.json, promotion.json, kernel module, native/emulator receipts, UART and target logs.
