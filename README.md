# Tiny System One classifier on FPGA

**Phase 2 (RTL) status, 2026-09-24:** the full inference path is in
SystemVerilog under `rtl/`, with the MLP head built from Genome-Classifier's
`dense_engine` (now with `ROM_STYLE` and `PIPELINED` parameters) and the code in
that repository's conventions. It is bit-exact against the golden model below on
all 5,500 test utterances — every index, every logit, every decision — in
Verilator 5.040, both at the core and end to end through the RMII pins: raw
Ethernet requests in, result frames out, checked with the host's own decoder. In
simulation the board answers a typical request in about 75 µs wire to wire. Block
RAM, not the 94% bit count, is the tight constraint. A Vivado build script and a
host client are ready; running them on the board is next. See `rtl/README.md`.

## Phase 1

Software half of the project: a hashed embedding-bag student trained on CLINC150,
an integer-only inference path that is bit-exact against a scalar reference, and
the size / bit-width sweeps that say what will actually fit on a Nexys 4 DDR.

Everything here runs on CPU with NumPy alone. No GPU, no PyTorch, no network
access at runtime. A full sweep is minutes, not hours, which is the point: the
questions Phase 1 has to answer are about size and arithmetic, and those are
cheap to answer at this scale.

Python dependencies are managed with [uv](https://docs.astral.sh/uv/), as in
Genome-Classifier's pipeline:

```
uv sync          # creates .venv from pyproject.toml and uv.lock (NumPy pinned to 2.4.4)
uv run pytest -q # quick checks
```

NumPy is pinned exactly because training is not bit-reproducible across NumPy
versions. With the locked environment, the command below reproduces
`export/student_bram_max/model.npz` byte for byte (same SHA-256 as the manifest).

```
# the recommended model: 0.9071 in-scope, 568.9 KiB, fits in block RAM
uv run python scripts/train_student.py --buckets 16384 --dim 64 --hidden 256 \
        --bits 4 --head-bits 8 --epochs 24 --qat \
        --trigrams --char-ngrams 3-5 --max-tokens 256 \
        --out export/student_bram_max

uv run python tests/test_bitexact.py      # integer path vs scalar reference
uv run python tests/test_verify.py        # metrics vs sklearn, FNV vs published vectors
uv run python scripts/sweep.py            # size and bit-width sweeps -> results/
uv run python scripts/bram_budget.py      # best model at the block-RAM ceiling
uv run python scripts/feature_ablation.py # which features earn their reads
uv run python scripts/max_config.py       # largest useful model the board can hold
uv run python scripts/ddr2_headroom.py    # why a DDR2-scale table is worse
```

## What the model is

```
raw bytes ──FNV-1a/32──▶ indices ──lookup──▶ mean pool ──▶ Linear ──ReLU──▶ Linear ──▶ argmax
                                  (V x D)    (Q16 + gain)   (D x H)          (H x 151)
```

Features are word unigrams, bigrams and trigrams plus character 3-5 grams with
word-boundary markers, all case-folded ASCII alphanumeric runs hashed to a
power-of-two table so the index is a bit mask. 151 classes: 150 CLINC150 intents
plus out-of-scope as class 150, so abstention is one argmax rather than a second
model.

Character n-grams cost nothing in storage and are cheap in RTL — the n-grams of a
word are a sliding window over the same byte stream the word hash already walks,
so the hashing unit keeps a few extra rolling FNV registers and emits more indices.
What they do cost is memory reads per inference, 96 instead of 16.

## Headline results

All numbers are from the **integer** path on the CLINC150 test set (4,500 in-scope
+ 1,000 out-of-scope). Majority-class floor on the combined set is **0.1818**
(always predict `oos`); in-scope-only floor is 1/150 = 0.0067.

### The recommended on-chip configuration

V=16384, D=64, H=256, 4-bit embedding (QAT), 8-bit head, features = unigram +
bigram + trigram + character 3-5 grams — **568.9 KiB, 94% of block RAM**

| | float32 | integer |
|---|---|---|
| in-scope accuracy | 0.9078 | **0.9071** |
| combined accuracy | 0.8231 | 0.8235 |
| OOS recall | 0.4420 | 0.4470 |
| Brier (multiclass) | 0.2578 | 0.2575 |
| ECE, 10 equal-width bins | 0.0247 | **0.0244** |
| ECE, 10 equal-mass bins | 0.0251 | 0.0237 |
| OOS AUROC (by max prob) | 0.9211 | 0.9202 |

Temperature 1.282, fitted on validation and folded into the integer output
multiplier, so the board emits calibrated logits rather than raw scores a host has
to fix up afterwards. Compute is 13.0 µs against 146 µs of Ethernet transport.

The integer path now matches float32 to within 0.07 points and is *better*
calibrated. Reaching that took the pooled-resolution fix described below.

A near-identical alternative, V=32768 / D=32 / H=256 at 560.9 KiB, scores 0.9062
in-scope with a slightly better ECE (0.0220) but noticeably worse OOS recall
(0.387 against 0.447). Since out-of-scope detection is this model's known weak
point, the wider-row variant is the recommendation; on in-scope accuracy alone the
two are indistinguishable.

### Pooled resolution: a defect that looked like a modelling limit

Worth its own section because it invalidated an earlier headline claim.

Mean-pooling quantised rows concentrates as the feature count grows. Averaging 96
character n-gram rows whose codes live in `[-7, 7]` leaves a pooled value spanning
about **3 bits** — the first MAC was consuming an input with eight distinguishable
levels. Accuracy degraded a little; calibration degraded a lot, which is exactly
the wrong failure for this project.

The fix is one shift: scale the mean back up by `pool_gain` bits to fill the
activation width, and fold the factor into the first requantisation multiplier so
nothing downstream changes. `pool_gain` is chosen at calibration time from the
observed pooled range, since it depends on how many features an input produces.

What it was worth on the recommended configuration:

| | before | after |
|---|---|---|
| pooled width | 3 bits | 8 bits |
| in-scope (integer) | 0.8909 | **0.9071** |
| ECE (integer) | 0.0376 | **0.0244** |
| Brier (integer) | 0.2858 | 0.2575 |
| gap to float32 | −1.69 pts | −0.07 pts |

**The correction.** An earlier version of this README reported that a ternary
embedding table was catastrophic — −39 points — and concluded the table could
never go below 4 bits. That number was mostly this defect: ternary codes are
`{-1, 0, +1}`, so pooling left **2 bits** of resolution. Re-measured with the fix,
a ternary table costs about **8 points**, not 39:

| embedding | head | QAT | before fix | after fix |
|---|---|---|---|---|
| ternary | 8b | no | 0.4822 | **0.7884** |
| ternary | 8b | yes | 0.4658 | 0.7527 |
| 4b | 4b | yes | 0.8569 | **0.8747** |
| 8b | 8b | no | 0.8698 | 0.8707 |

The practical conclusion is unchanged — a ternary table still costs ~8 points and
is not worth it — but the reasoning was wrong, and the magnitude was wrong by a
factor of five. The lesson generalises: when a quantisation result looks
catastrophic rather than merely bad, suspect the arithmetic before the width.

Note also that INT4 is now *free*: `emb=4b head=4b` with QAT scores 0.8747, above
the 0.8707 of `emb=8b head=8b`, at half the storage.

### What "saturating the board" actually looks like

| resource | recommended model | available | utilisation |
|---|---|---|---|
| block RAM | 568.9 KiB | 607.5 KiB | **94%** |
| DSP48E1 | 64 lanes | 240 | 27% |
| DDR2 | 0 | 128 MiB | 0% |
| compute vs Ethernet transport | 13.0 µs | 146 µs | 8% |

Block RAM is the only resource that binds, and the model sits against it. The
other three cannot be usefully spent: the DDR2 experiment below shows extra table
rows make things worse, and extra compute has nothing to buy — the head is already
wide enough that doubling it again gains 0.4 points and overflows block RAM.

Progress from the original configuration, all of it inside the same chip:

| | original | maximum |
|---|---|---|
| in-scope accuracy | 0.8656 | **0.9071** |
| OOS recall | 0.369 | 0.447 |
| ECE | 0.0215 | 0.0244 |
| storage | 525.1 KiB | 568.9 KiB |
| compute | 2.8 µs | 13.0 µs |

For reference, a TF-IDF word(1,2) + char_wb(3,5) logistic regression — a strong
classical model with 52,137 features and no quantisation — scores **0.9211**
in-scope on the same split. The on-chip integer model is within 1.4 points of it.

### Where the accuracy came from

| features | feats/input | in-scope | no OOV | has OOV | OOS recall |
|---|---|---|---|---|---|
| unigram only | 8.4 | 0.8831 | 0.8979 | 0.8086 | 0.363 |
| uni + bigram | 15.9 | 0.8940 | 0.9099 | 0.8139 | 0.524 |
| uni + bi + trigram | 22.3 | 0.8769 | 0.8892 | 0.8153 | 0.600 |
| uni + char 3-5 | 81.8 | 0.8982 | 0.9150 | 0.8139 | 0.365 |
| uni + bi + char 3-5 | 89.2 | 0.9002 | 0.9171 | 0.8153 | 0.447 |
| **uni + bi + tri + char** | **95.6** | **0.9049** | **0.9203** | **0.8273** | 0.492 |

Character n-grams are the single biggest lever, and they cost storage nothing —
only memory reads per inference, which went from 16 to 96. That is spending the
resource the board has spare (compute and read bandwidth) to buy the one it does
not (effective vocabulary).

Trigrams *alone* hurt (0.8769), because trigram features are almost all singletons
and the model memorises them. They help only in combination with character
n-grams, which supply enough shared structure to regularise them.

The 27.7% of test inputs containing at least one unseen word still score 9.3
points below the rest (0.8273 against 0.9203), so out-of-vocabulary remains the
largest single identified weakness.

### Would a transformer be better?

Almost certainly not on this dataset, and the evidence is worth recording because
it is the obvious next thing to try with 73% of the DSPs idle.

A transformer's advantage over a bag of features is word order. Trigrams are the
cheap probe for how much order is worth here, and they *hurt* on their own. More
tellingly, the TF-IDF reference — which has no order information beyond bigrams at
all — beats every model in this repository. And a transformer trained from scratch
on 15,000 examples would be fighting the learning curve below, which shows the
model already memorising its training set at every size tried.

The remaining gap to BERT-class accuracy on CLINC150 (~96-97% in the literature)
is pretraining, not architecture or capacity. That is what the DDR2 discussion
below concludes too, from a different direction.

### Why not a DDR2-scale model?

The board has 128 MiB of DDR2 and the recommended student uses 0.4% of it. That
looks like waste, so `scripts/ddr2_headroom.py` tests it directly rather than
appealing to the saturation curve.

**There are only 31,392 distinct features in the entire training corpus** — 5,175
unigram types and 26,217 bigram types. A table with more rows than that has rows
that are never addressed, so they cannot contribute:

| V | rows ever addressed | table wasted | collision rate |
|---|---|---|---|
| 32,768 | 20,239 | 38% | 0.615 |
| 131,072 | 27,919 | 79% | 0.213 |
| 524,288 | 30,499 | 94% | 0.056 |
| 2,097,152 | 31,148 | **98.5%** | 0.015 |

Filling DDR2 (V=2²¹, D=64, INT8 = 128 MiB, 134M parameters) leaves 98.5% of the
table untouched. And it is not merely wasteful — it is **worse**:

| V | storage | in-scope (int8) | in-scope (f32) | train acc | ECE |
|---|---|---|---|---|---|
| 32,768 | 2.0 MiB | 0.8847 | 0.8867 | 0.9998 | 0.0172 |
| **131,072** | **8.0 MiB** | **0.8940** | 0.8971 | 0.9999 | 0.0335 |
| 524,288 | 32.0 MiB | 0.8796 | 0.8940 | 0.9998 | 0.0510 |
| 2,097,152 | 128.0 MiB | 0.8651 | 0.8971 | 0.9999 | 0.0975 |

Two separate things go wrong as the table grows past the feature inventory:

* **Quantisation degrades.** The float32 column is flat from 8 MiB onward, but the
  integer column falls by 2.9 points and ECE quintuples. The cause is the untrained
  rows: with 98.5% of the table still at its random initialisation, those rows
  dominate the per-dimension scale statistics, so the quantiser spends its range on
  values the model never learned. A sparsely-addressed table quantises badly, and
  this project only ships integer models.
* **Training data, not capacity, is the binding constraint.** Train accuracy is
  99.98%+ at *every* size — the model already memorises the training set
  completely. Adding parameters to a model that has perfectly fit its training data
  cannot help it generalise.

The learning curve confirms which resource is actually scarce (V=131,072, D=64):

| train fraction | n | in-scope | train acc | generalisation gap |
|---|---|---|---|---|
| 0.10 | 1,510 | 0.6256 | 0.9987 | 0.373 |
| 0.25 | 3,775 | 0.8138 | 1.0000 | 0.186 |
| 0.50 | 7,550 | 0.8604 | 1.0000 | 0.140 |
| 1.00 | 15,100 | 0.8940 | 0.9999 | 0.106 |

Accuracy is still climbing steeply at 100% of the data. Doubling the data from
7,550 to 15,100 examples bought **+3.4 points**; going from 2 MiB to 128 MiB of
parameters bought **−2.0 points**. The gap is still 10.6 points and closing slowly.

**What DDR2 is genuinely good for, then, is not capacity — it is pretraining.**
39.8% of the distinct words in the test set never appear in training at all, and no
amount of randomly-initialised table can embed a word it has never seen. A
Model2Vec table (~8 MB INT8) fits comfortably in DDR2 and brings *outside*
knowledge to exactly that 39.8%, which is a different resource from parameter
count. Character n-grams are the other candidate: they would give an unseen word a
representation built from fragments the model has seen. Both are worth trying;
"make the hash table bigger" is not.

### Calibration and the cascade

Reliability of the integer model (`results/student_report.json`), 10 equal-width bins:

| bin | n | mean conf | accuracy | gap |
|---|---|---|---|---|
| (0.2, 0.3] | 361 | 0.249 | 0.296 | +0.048 |
| (0.5, 0.6] | 284 | 0.551 | 0.549 | −0.002 |
| (0.8, 0.9] | 452 | 0.855 | 0.867 | +0.013 |
| (0.9, 1.0] | 2985 | 0.983 | 0.970 | −0.013 |

Selective accuracy on the combined test set:

| coverage | accuracy | confidence threshold |
|---|---|---|
| 0.10 | 0.9927 | 0.9992 |
| 0.30 | 0.9842 | 0.9914 |
| 0.50 | 0.9738 | 0.9377 |
| 0.70 | 0.9330 | 0.6544 |
| 1.00 | 0.7753 | — |

This is the cascade argument in one table: at 50% coverage the board answers with
97.4% accuracy, so half the traffic never needs to reach a GPU. Whether that is
economically interesting is Phase 3's question, but the curve it depends on is
real and measured on the integer path.

## Bit-exactness

`src/sysone/quant.py` is the specification the RTL implements, and it is checked
against a second implementation in scalar Python with arbitrary-precision integers
(`tests/test_bitexact.py`). NumPy is not a neutral witness — it has its own
overflow and shift semantics and its own reduction order — so agreement between a
vectorised path and a naive serial one is what makes the golden model trustworthy.

```
[OK ] 8-bit: 200/200 inputs identical    widths: pooled=8b acc1=18b acc2=19b
[OK ] 4-bit: 200/200 inputs identical    widths: pooled=4b acc1=10b acc2=15b
[OK ] 1-bit: 200/200 inputs identical    widths: pooled=2b acc1=6b  acc2=12b
```

The measured accumulator widths are the useful output: the theoretical bound
(64 tokens × 127 × 128 lanes) would have RTL provisioning 24-bit accumulators where
13 bits suffice at INT4.

Design decisions that the RTL inherits, all recorded in the export manifest:

* **One rounding rule everywhere** — `(x*m + 2^(s-1)) >> s`, arithmetic shift.
* **Mean pool by Q16 reciprocal LUT**, 65 entries, not a divider. Verified within
  1 LSB of true division across the whole input range.
* **Per-dimension embedding scales folded into W1** before W1 is quantised, so
  `pooled_q @ W1q` stays a pure integer dot product and the per-dimension scale
  costs nothing.
* **Temperature folded into the output multiplier**, so calibration is inside the
  integer arithmetic rather than a host-side correction.
* **INT4 range is [−7, 7]**, not [−8, 7], to keep the quantiser symmetric.

## Export

`scripts/train_student.py` writes `model.npz`, one `.mem` file per tensor (Vivado
hex, one value per line — packing order is an RTL decision and is deliberately not
baked in), and `manifest.json` with SHA-256 of every tensor and file, the
arithmetic constants, the hash parameters, the measured accumulator widths, and the
golden metrics. `sysone.manifest.verify()` re-hashes everything; the test suite
confirms it catches a single flipped hex word.

## Known limitations

* **OOS recall is poor (0.37).** The training split has 100 out-of-scope examples
  against 15,000 in-scope. A 10× class weight helps but does not fix a 150:1
  imbalance. Options not yet tried: much higher weighting, oversampling, or
  synthetic OOS generation. Reported separately from in-scope accuracy throughout
  precisely so it cannot hide inside a pooled number.
* **No teacher yet.** The distillation hook exists (`backward(..., soft_targets=)`)
  but every number here is from gold labels alone. Comparison against Laya /
  GLiClass and a fine-tuned DeBERTa teacher needs GPU and model-hub access that
  this environment does not have.
* **English ASCII only.** The tokenizer drops bytes ≥ 0x80. Widening the boundary
  rule is one comparator, but it is untested.
* **Latency and resource numbers are analytical.** No Vivado run, no board, no
  power meter. Treat as budgets.
* **Single seed.** The sweeps report one seed per configuration. Differences below
  roughly half a point should not be read as real; `--seeds` raises this.
* **Training is not bit-reproducible across machines.** The same command on NumPy
  2.4.4 and NumPy 2.2.6 gave 0.8656 and 0.8700 in-scope — a 0.4-point spread from
  float reduction order alone, which is more than several of the differences in
  the sweep tables. It is a second reason to treat sub-half-point gaps as noise.
  The *integer* path is unaffected: given the same weights it is bit-exact
  everywhere, which is the property Phase 2 actually depends on.

## Layout

```
data/clinc150/       vendored CLINC150 + LICENSE + PROVENANCE.md
src/sysone/
  hashing.py         FNV-1a/32, tokenizer, corpus encoding  (RTL contract)
  data.py            CLINC150 loading, splits, majority floor
  model.py           embedding bag + MLP, NumPy fwd/bwd, sparse Adam
  quant.py           integer inference path, PTQ and QAT     (RTL contract)
  train.py           training loop, temperature calibration
  metrics.py         accuracy, Brier, ECE (two binnings), selective, AUROC
  hw_estimate.py     latency and resource budgets for XC7A100T
  manifest.py        hashed export for the Phase 2 handoff
  ethernet_protocol.py  raw-Ethernet request/result codec (board <-> host)
scripts/             train_student.py, sweep.py, bram_budget.py,
                     rtl_pack.py (export -> RTL memories + vectors), rtl_metrics.py,
                     ethernet_vectors.py, sysone_ethernet_client.py (host), build_sysone.tcl
rtl/                 Phase 2 SystemVerilog -- see rtl/README.md
constraints/         Nexys 4 DDR pins and RMII timing
memory/              generated ROM images for the RTL
simulation/          testbenches, Makefile, generated vectors
tests/               test_bitexact.py, test_verify.py, test_ethernet_protocol.py
results/             sweep and report JSON
```

Data is CLINC150, CC BY 3.0 — see `data/clinc150/PROVENANCE.md` for attribution,
the exact upstream commit, and why gold labels matter for this project.
