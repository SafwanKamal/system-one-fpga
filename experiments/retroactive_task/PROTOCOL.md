# Retroactive task learning from raw sensor archives

November 16, 2026. A bounded feasibility experiment, not a new compression method.

## Question and predetermined split

Can an archive created without a future activity category support learning and detecting that category after collection? Use official PAMAP2 protocol recordings, subjects 101–108. Subject 109 is excluded in advance because its protocol recording is short and does not provide the same activity coverage. Use 101–104 for collection-time model fitting and post-reveal training; 105–108 are unseen-person tests. Do not tune on test labels.

Primary withheld category: running (activity 5). Secondary checks: cycling (6), ascending stairs (12). Exclude all three categories from every collection-time fitted model and its normalization. Data from these activities can occur in the archives as unlabeled signals. Codec interfaces take signals and frozen collection-time parameters, not labels. Future labels are used by the experiment custodian only to remove withheld classes from collection-time fitting; the downstream learning stage receives them only after archive closure and a hash manifest.

Use nonoverlapping 512-sample windows at 100 Hz, containing acceleration (16g range) and gyroscope axes from the hand, chest and ankle: 18 raw channels. Archive every complete window, including transitions, ambiguous labels, and missing values. Interpolation of missing values is restricted to the current window; retain missingness for waveform reconstruction. No window is selected or removed on the basis of its future label. At evaluation only, use windows with at least 95% label purity, nonzero activity, and the declared timing validity criterion. Record all exclusions.

## Strong simple archives

Unbudgeted reference: full float32 signal windows. Also report standard lossless compression using zlib and LZMA, including a reversible temporal XOR/byte-shuffle transform. These reference curves use actual bytes; they are not forced into a cap they cannot meet.

For capped waveform archives, test 1, 2, 4 and 8 KiB per window. Compare existing ingredients: affine scalar quantization (4/8 bits), float16, anti-aliased uniform downsampling, and truncated DCT coefficients. A task-blind rate/distortion selector may choose among those conventional configurations using reconstruction MSE normalized by collection-training signal scales. It sees the current unlabeled window only. Report downsampling and DCT families separately as well as their best-MSE combination. No category accuracy is used to select a codec at collection time.

Feature archives: a broad, fixed statistics/spectral feature bank in float16; PCA embeddings of that bank at 16/32/64 dimensions, fitted only on known collection-time classes; and frozen known-class posterior scores. The posterior-only archive is a deliberately task-specific control, not the strongest baseline. Feature representations store no raw backing copy. A new label does not imply that a general feature bank must fail.

Count serialized frame headers, start times, rates, shapes, codec parameters, compressed missingness and values. Report actual complete history size plus shared PCA/classifier parameter storage. Payload caps are per-window limits, not a claim about total RAM. Amortized storage and standalone shared-model costs must both be visible. Decoder code and common feature-extractor code are not included as dataset payload. Preserve byte archives and check reconstruction from saved files.

## Reveal and learn

Seal all archive files and write their hashes before a reveal receipt. Only then load future category labels into downstream training. Fit a new binary classifier for each withheld category from archived 101–104 windows and test on archived 105–108 windows. Collection-time encoders stay frozen. Post-reveal classifiers may retrain to accommodate their own representation.

Full and reconstructed waveform archives support a broad statistics feature bank and a richer phase-preserving DCT feature bank computed after reveal. Feature-only archives expose their stored features only. Select among a small fixed set of ordinary classifier/feature choices with leave-one-training-person-out validation on 101–104. Use the same classifier families and tuning opportunities for all representations. Test people never select models or thresholds.

Report per-person F1, balanced accuracy, recall, precision, and average precision. Class imbalance must not permit an always-negative winner. Full raw history is a feasibility oracle, not an assumed perfect detector. A task supports a gap claim only if the raw oracle achieves at least 0.85 mean per-person F1 and balanced accuracy. If it fails, report that task as inconclusive for memory loss.

## Decision rule

At each cap compare the best task-blind simple archive with the full-history oracle. A gap potentially worth further work must exceed 0.05 absolute F1 on a learnable task, be visible across test people, and survive the broad fixed-feature and generic waveform baselines. A failure of known-class posteriors alone is expected and does not establish a contribution. If a simple archive comes within 0.03 F1 at a substantial compression ratio, close this task as lacking a useful gap. Four test people support a feasibility screen, not a strong population generalization claim.

No new retention method or FPGA implementation is authorized by a positive point estimate. A residual gap would require a second independent domain and a stronger learned-codec comparison, including CHORD where an implementation is available, before a novelty claim.

## Sources

Reiss and Stricker, PAMAP2 Physical Activity Monitoring, UCI: https://archive.ics.uci.edu/dataset/231/pamap2+physical+activity+monitoring ; DOI https://doi.org/10.24432/C5NW2H . Follow the dataset's CC BY 4.0 attribution.

Luitel et al., CHORD (November 9, 2026): https://arxiv.org/abs/2611.11913 . This feasibility run compares simple baselines; it is not a reproduction of CHORD.
