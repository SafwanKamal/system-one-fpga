"""Render the final report from corrected V2 results, without policy changes."""
import json
import numpy as np
import pilot


def read(name):
    return json.loads((pilot.OUT / name).read_text())


summary = read("summary.json")
selection = read("selection.json")
primary = selection["selected_candidate"]
names = {"adaptive_segments": "Adaptive means", "reservoir": "Uniform reservoir",
         "balanced_codec": "Balanced compression", "hybrid_reservoir": "Uniform hybrid",
         "hybrid_change": "Change-priority hybrid", "hybrid_bundle": "Linked-pair hybrid"}


def cell(method, budget=65536, panel="all"):
    return next(r for r in summary if r["method"] == method and r["budget"] == budget and r["panel"] == panel)


def interval(file, budget, metric="nmae"):
    r = next(r for r in read(file) if r["budget"] == budget and r["panel"] == "all" and r["metric"] == metric)
    return f"{r['delta']:+.5f}, 95% interval [{r['ci95'][0]:+.5f}, {r['ci95'][1]:+.5f}]"


rows = []
for budget in pilot.BUDGETS:
    baseline = selection["strongest_simple_by_budget"][str(budget)]
    base = cell(baseline, budget)
    rows.append(f"| {budget//1024} KiB | {base['participants']} | {names[baseline]} | {base['nmae']:.4f} | {cell('hybrid_reservoir',budget)['nmae']:.4f} | {cell('hybrid_change',budget)['nmae']:.4f} | {cell('hybrid_bundle',budget)['nmae']:.4f} |")
error_table = "\n".join(rows)
rows = []
for method in ["balanced_codec", "hybrid_reservoir", "hybrid_change", "hybrid_bundle"]:
    c = cell(method)
    rows.append(f"| {names[method]} | {100*c['exact']:.1f}% | {100*c['positive_exact']:.1f}% | {100*cell(method,panel='continuous_shift')['exact']:.1f}% |")
agreement_table = "\n".join(rows)
numeric = read("exploratory_numeric_summary.json")
numeric_rows = []
for method in ["balanced_codec", "hybrid_reservoir", "hybrid_change", "hybrid_bundle"]:
    c = next(r for r in numeric if r["method"] == method and r["budget"] == 65536)
    numeric_rows.append(f"| {names[method]} | {c['nmae']:.4f} | {100*c['exact']:.1f}% |")
numeric_table = "\n".join(numeric_rows)
quantization = cell("quantization_floor", 0)
image_prefix = "../../results/research/future_sensor_memory/pilot_v2"
body = f"""# Future-question sensor memory: first experiment

**Decision: the tested retention heuristics do not justify an FPGA implementation.** Their small local improvements do not establish a useful frontier beyond the strongest simple alternatives. This is a negative result for the tested mechanisms and feature representation, not a rejection of all future-query memory problems.

Completed November 8, 2026, America/Chicago. This report uses **corrected V2 results**. A seed-handling bug discovered in the final V1 audit was corrected, and every validation and test evaluation was rerun. V1 is preserved and superseded. The correction is explained below.

## What ran

The official [ExtraSensory dataset](https://extrasensory.ucsd.edu/) supplied 377,346 observations from 60 people. We used 36 training participants, 12 for validation, and 12 held out for testing. The test histories contain **82,553 observations**. Recording order, gaps, and missing channel values were preserved.

Every memory received the same compact stream: eight activity-classifier scores and four normalized sensor features, encoded in twelve bytes per observation with a missing-value code. The numerical channels describe phone acceleration variability, watch acceleration variability, gyroscope variability, and audio magnitude. The classifiers and feature normalization were fitted on training people. This is a feature-history experiment; it does not test continuous raw-waveform retention or reproduce SensorQA scores.

The primary panel contains **6,912 distinct structured questions**, 576 per test participant, reused across policies. Questions cover observed-session counts used as duration proxies, episode onsets, simultaneous conditions, directed onset-following, conjunction episodes, changed thresholds, and arbitrary thresholds from 0.2 to 0.8. Questions are hidden from ingestion. A following relation counts an A start with a later B start within 30 minutes, with no intervening recording gap over 90 seconds. These are observational relationships, not causal claims. We do not extrapolate through unobserved time.

Thirteen policies or variants were evaluated at 8, 16, 32, and 64 KiB/person: a recent ring, uniform reservoir, change-priority sampling, dyadic means, adaptive piecewise-constant means, lossless eight-bit block compression, oldest-first progressive compression, balanced progressive compression, compressed one-bit event states, two-bit coarse states, a uniform hybrid, a change-priority hybrid, and a linked-pair hybrid.

The hybrids combine a coarse state history with full feature records. Their decoder refines each channel using nearby retained records with the same coarse state. The change-priority version favors simultaneous changes across channels. The pair version retains fixed, nonoverlapping adjacent record pairs. Arbitrary overlapping or long-range bundles and joint soft-value decoding are outside this pilot. These are cheap heuristics, not newly trained task-reward models or SVMemAgent reproductions.

Validation selected **{names[primary]}** as the primary candidate. All three hybrids used a two-bit base. The change-priority version selected full weight on its multi-channel cue; the linked-pair version selected zero weight on that cue and used ordinary mean change. Both versions remain visible in the results. Simple methods were selected separately by budget using validation loss.

## Main result

The primary error is the participant-average mean of `abs(answer - reference) / max(reference, 1)`. Lower is better. It is unbounded: false events when the reference is zero can be expensive. Exact agreement and agreement on nonzero answers provide separate checks.

| Cap | Feasible people | Validation-selected simple | Simple error | Uniform hybrid | Change-priority | Linked-pair |
|---|---:|---|---:|---:|---:|---:|
{error_table}

At 32 KiB the primary candidate improves the point estimate over the selected adaptive means, but its error difference is {interval('paired.json',32768)}. Its difference from the ordinary uniform hybrid is {interval('paired_uniform_hybrid.json',32768)}. Neither comparison establishes a clear advantage with this participant sample.

At 64 KiB, balanced compression is substantially stronger. The primary candidate-minus-balanced error difference is {interval('paired.json',65536)}. The primary candidate also does not improve the uniform hybrid on this loss: {interval('paired_uniform_hybrid.json',65536)}.

The linked-pair mechanism does not rescue the result. Against the uniform hybrid its error difference is {interval('paired_linked_uniform.json',32768)} at 32 KiB and {interval('paired_linked_uniform.json',65536)} at 64 KiB. These are participant-cluster bootstrap intervals, not multiple-comparison-corrected significance claims. Random seeds and questions were averaged within participants rather than treated as independent people.

At 64 KiB:

| Method | Exact answers, all questions | Exact when reference is nonzero | Exact, arbitrary thresholds |
|---|---:|---:|---:|
{agreement_table}

These percentages describe agreement with complete canonical feature history. They are not accuracy against human activity truth. There is no demonstrated roughly 20% storage-efficiency advantage or repeatable cross-budget improvement over the simple frontier.

## What this says about the proposed niche

The compressed one-bit event table answered **100% of familiar and held-out-composition questions at 32 KiB**, on all twelve participants. Those questions use threshold 0.5. Retaining the event-state history already retains order and temporal relationships. A new combination of known predicates does not necessarily require a special relational memory.

Changing predicate thresholds is harder because coarse states discard information needed for reinterpretation. Balanced numerical compression retains that information much more effectively at the larger budget than these selection heuristics. The immediate tradeoff is precision and history coverage. The tested pair mechanism does not create a defensible new capability.

Some small-cap block archives evict older history and use the same fixed training prior for uncovered rows. Thresholding that prior can create many false events; this explains several large normalized errors. Adaptive means spreads its approximation over history and avoids those failures. The outcome depends on the metric: a method can answer many zero-valued queries exactly while making expensive errors on a few other queries. Both views are reported.

## Check without activity-recognition errors

The upstream activity models were weak for several classes. Test participant-average F1 was approximately 0.807 for lying, 0.759 for sitting, 0.353 for walking, 0.073 for running, and zero for eating. The complete-history semantic pipeline therefore does not establish useful human activity QA.

We ran an **explicitly exploratory sensor-only panel after memory creation**: 320 questions per participant, using only the four directly observed normalized numerical channels. It includes conjunctions and onset-following at fixed and arbitrary thresholds. Every answer used the same frozen archives; no policy, parameter, or model was changed for this panel.

At 64 KiB:

| Method | Sensor-only normalized error | Sensor-only exact agreement |
|---|---:|---:|
{numeric_table}

The qualitative result survives without activity classifiers. There are some local gains over the uniform hybrid, but balanced compression remains stronger at the larger cap. This is a sensitivity check on the same dataset, not an independently collected second domain or a confirmatory sample. Full per-budget results and comparison intervals are retained.

## Verification and limits

**924 feasible test archives** were reloaded from bytes, checked against their hashes and caps, and used to reproduce all logged answers. An independent loop-based query implementation agreed with all 6,912 primary reference answers. **21 harness tests** passed, including codec losslessness, missingness, epoch precision, gaps, onset boundaries, causal prefixes, archive limits, and repeated calls to a parallel worker.

The archive cap includes timeline and gap encoding, compression framing, values, indices, priorities, and a 64-byte ingestion-state allowance. Four people could not fit their exact timeline at 8 KiB and are explicit infeasible cases. Tables show the feasible count per cap. The plot holds the same eight-person eligible cohort fixed across budgets:

![Common-cohort comparison]({image_prefix}/frontier_common_cohort.png)

The fixed input chunk is 2 KiB. Shared models, Python object overhead, and query-time decode workspace are outside the archive cap. The shared classifier artifact is about 203 MB. No whole-RAM, power, embedded latency, or FPGA advantage is claimed. Ingestion decisions occur at boundaries of up to 128 observed records; immediate mid-chunk querying is not tested.

Other limits are material. The twelve retained channels are fixed before collection, so new concepts requiring a different encoder are untested. About 63% of primary reference answers are zero; nonzero-answer scores and the sensor-only panel guard against a trivial always-zero interpretation. Quantization alone gives {100*quantization['exact']:.1f}% exact agreement with unquantized feature answers but only {quantization['nmae']:.5f} normalized error, showing why exact agreement should be read with an error metric. Questions are generated and structured on one public feature dataset. Human-authored questions, raw high-rate relationships, stronger learned policies, and optimal timeline codecs remain outside the evidence.

## Corrections and reproducibility

Before the initial held-out evaluation, validation exposed extra codec rounding and a capacity edge case; both were corrected, and arbitrary thresholds were added to avoid a quantization-grid coincidence. The protocol records those amendments.

The final V1 audit then found that reused worker processes accumulated participant seed offsets. This changed some generated question sets. We corrected the worker to reset from an immutable base seed and reran **all validation and test evaluations** in V2. The data split, retention algorithms, parameter search, loss, budgets, and selection rule were unchanged. Shared training artifacts were reused. V1 results had been inspected, so V2 is an implementation correction on the same participants, not a new independent confirmatory experiment. V1 is preserved and superseded.

The corrected audit checks every test question set against the serial seed formula. Validation question sets are checked independently as well. The fixed pilot code matches its V2 freeze and validation selection. V2 logs completed without interrupted recovery.

## Decision

I would stop these retention heuristics before FPGA implementation. They do not establish a contribution beyond strong simple alternatives. The experiment also shows why the original argument was insufficient: relational questions over already-computed event states can be cheap to preserve.

A sharper follow-up would need future concepts or measurements absent from the collection-time representation, evidence of irreversible signal loss, and a second domain. It would then need to beat a compact numerical archive and a simple hybrid. This pilot does not supply that evidence.

## Artifacts

- [Protocol and reproduction instructions](../../experiments/future_sensor_memory/README.md), [frozen protocol](../../experiments/future_sensor_memory/PROTOCOL.md).
- [Primary summary]({image_prefix}/summary.json), [selected-simple comparison]({image_prefix}/paired.json), [uniform-hybrid comparison]({image_prefix}/paired_uniform_hybrid.json), and [linked-pair comparison]({image_prefix}/paired_linked_uniform.json).
- [Sensor-only summary]({image_prefix}/exploratory_numeric_summary.json), [its primary-candidate intervals]({image_prefix}/exploratory_numeric_paired_uniform.json), and [its linked-pair intervals]({image_prefix}/exploratory_numeric_linked_uniform.json).
- [Training/data manifest]({image_prefix}/manifest.json), [V2 revision]({image_prefix}/revision.json), [freeze]({image_prefix}/protocol_freeze.json), [selection]({image_prefix}/selection.json), [completed receipt]({image_prefix}/completed.json), [21-test receipt]({image_prefix}/tests.xml), and [archive/oracle audit]({image_prefix}/audit.json).
- Participant questions, logged answers, serialized memories, and the fixed-cohort plot data are saved alongside these receipts.
"""
path = pilot.ROOT / "docs/research/2026-11-08-future-sensor-memory-pilot.md"
path.write_text(body, encoding="utf-8")
print(path)
