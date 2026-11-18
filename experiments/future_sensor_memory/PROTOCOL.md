# Future-question sensor memory: pilot protocol and V2 correction

Frozen before held-out memory evaluation, November 8, 2026. This is a falsification pilot, not a SensorQA reproduction or an FPGA benchmark.

## Data and split

Use the official ExtraSensory per-user feature/label archive (60 people; original recordings have gaps and roughly minute-spaced observation sessions). Preserve recorded order, gaps, and missing sensor features. Use a seeded permutation of sorted UUIDs: 36 training, 12 validation, 12 test participants. The dataset's supplied feature extraction is upstream of this experiment. No claim about continuous raw-signal retention follows from these feature streams.

Train independent activity classifiers for lying, sitting, standing, walking, running, bicycling, eating, and computer work using training participants only. Evaluate recognition against the supplied labels separately. A common query engine over full-history predictions isolates retention error from recognition error. Add four sensor features (phone acceleration variability, watch acceleration variability, gyroscope variability, audio magnitude) mapped by training-set quantiles. Missing values have a distinct code. All memory methods receive the same 12-channel, byte-quantized feature stream. Report quantization error separately against the unquantized stream.

The canonical retained input is already compact: eight predicted probabilities and four normalized features per observation. This deliberately gives simple compression a strong chance to defeat a new policy. New event semantics requiring another sensor encoder are outside this pilot.

## Information boundary and storage

Memories receive chronological chunks of at most 128 observations and no query objects, evaluation answers, labels, or future chunks. Decisions at a chunk boundary may use that entire observed chunk. Questions arrive after ingestion. This does not test immediate mid-chunk querying. Timestamps and gaps are encoded in every archive and charged. Store opaque serialized archives, then answer using only their decoded contents and a fixed training prior.

Budgets are 8, 16, 32, and 64 KiB per participant. Count serialized headers, timeline, compression framing, sample indices, ingestion priorities, and values. Check the bound after every chunk and reload every final archive from bytes. Report fixed chunk scratch separately; shared frozen classifier weights, Python runtime/object overhead, and query-time decode workspace are outside the archive cap. This experiment makes an archive-size claim, not a whole-RAM bound. An archive unable to fit its timeline is an explicit infeasible result.

## Baselines and candidate

- Recent feature ring; uniform reservoir; local-change-priority sampling.
- Dyadic multiresolution means and adaptive piecewise-constant approximation.
- Block-compressed 8-bit archive, with FIFO eviction if necessary.
- Progressive block compression, reducing old blocks from 8 to 4 to 2 to 1 bit before eviction. A balanced version reduces the highest-precision block first, distributing precision more evenly across history.
- Compressed event table: one-bit threshold state per channel with exact missingness/timeline. Coarse uncertainty: two-bit state table.
- Strong hybrid: complete coarse event table plus a uniform reservoir of full-precision feature records; reconstruct soft values using samples of the same coarse state. Sweep 1- and 2-bit base tables on validation participants.
- Candidate: same hybrid format, with linked neighboring records selected around changes in multiple channels. Compare both local-change and explicit two-record bundle versions. This is a cheap relational-retention heuristic, not a reproduction of SVMemAgent or a claimed new learning algorithm.

Use three seeds for random policies. Choose hybrid base precision and change-score mixing on validation participants using familiar operators (duration, episodes, co-duration), with threshold probes at 0.25/0.5/0.75 and numerical-channel probes. Test threshold values 0.3/0.7 and the two composition operators are withheld. The sensor-shift panel increases the weight of numerical-channel queries; it does not introduce an unseen encoder. Freeze selection before test evaluation. Keep deterministic policies deterministic; identical repeats are not independent evidence.

Choose the strongest simple method separately at each budget on validation participants. Hybrid hyperparameters and the candidate family are selected globally across the budgets. This gives the simple comparator the benefit of budget-specific method selection. Report every baseline as well as this frozen selection.

## Questions, scoring, and rejection

Use machine-readable, seeded questions. Familiar mix: duration at threshold 0.5, episode counts, and simultaneous duration. Held-out compositions: directed onset-following counts and conjunction episode counts. Shifted panels: different thresholds (0.3/0.7), arbitrary thresholds uniformly drawn from 0.2 to 0.8, and questions involving the four numerical sensor channels. The arbitrary-threshold panel prevents accidental alignment with a four-bit quantization grid. Query generation uses only participant length and the experiment seed; it does not search for queries favorable to a method. Score nonzero-answer questions separately to expose zero-answer dominance. For onset-following, each A episode start counts once if a B start follows within 30 minutes and all intervening observation gaps are at most 90 seconds. Co-occurrence is observational, not causal.

Report exact answer agreement, normalized absolute error, positive-answer agreement, all-zero answer rate, and errors by family. Duration means number of observed sessions satisfying the predicate, reported in observed minutes; do not extrapolate into missing time. Episode continuity breaks at gaps over 90 seconds. Report participant-clustered uncertainty and per-participant paired differences. Questions, random seeds, and budgets are repeated measures, not independent participants.

A candidate deserves continuation only if a validation-selected version improves over the validation-selected strongest simple baseline on unseen people and changed questions, across multiple budgets, without a material familiar-query regression. A planning target is approximately 20% fewer bytes at matched quality, or a clear repeatable reduction of relational-query error. This target is not a publication rule. If a simple compressed feature/event archive fits and preserves the queries, or the hybrid matches the candidate, do not start FPGA work for this proposal.

The confirmatory follow-up would require human-authored questions, a second independently collected domain, and a learned task-reward selector. A positive synthetic stress test alone cannot justify that follow-up.

## Pre-test amendments

Before any held-out memory results: added budget-specific simple-baseline selection and a 64-byte ingestion-state charge; corrected an unnecessary extra quantization in the eight-bit codec so its input-byte roundtrip is exact; added the arbitrary-threshold panel after noticing analytically that 0.3/0.7 align with four-bit bin boundaries. Four partial validation participants from before the codec fix are preserved with a `pre_codec_fix_` prefix and excluded from selection and results. Validation is rerun completely. No test memory metric was inspected to make these amendments.

During corrected validation, fixed a capacity edge case: a timeline can fit while even one 32-byte mean record cannot. Summary methods now discard that final mean and use the common prior for uncovered history. Earlier successfully completed archives are unaffected. Participant-level parallel execution and recovery of interrupted validation logs change orchestration only; recovered serial memories are checked against their original archive hashes. These changes precede held-out evaluation.

## V2 evaluation correction

The final V1 audit found that reused parallel worker processes accumulated participant seed offsets, rather than resetting to the base seed for each participant. This changed generated question sets for later tasks in those processes. V1 metrics had already been inspected. V2 fixes the seed assignment and reruns all validation and held-out evaluations with the same split, methods, parameter search, losses, budgets, and selection rule. V1 artifacts are preserved. This is a methodological correction on the same participants, not a fresh independent confirmatory sample. A regression test exercises repeated calls in one worker, and the final audit checks every question set against the serial seed formula. Shared training artifacts are reused because model fitting and input features were unaffected.
