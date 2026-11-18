# Executable pilot specification, before final evaluation

November 16, 2026. Supplements PROTOCOL.md; all choices below are frozen with
the executable source before test generation. These are synthetic mechanisms,
not measurements of a physical robot. The study is a feasibility screen.

## Fixed population and observations

- 50 Hz unicycle; first 4 seconds healthy commissioning, potential change at
  second 4, passive observation through second 8, then up to two one-second
  probes. A separate passive comparator continues ordinary commands through
  second 10. Healthy cases have no fault at the change opportunity.
- Train configurations 1100–1111; validation 2100–2107; final 3100–3119.
  Configurations specify chassis gains, path frequency/phase, noise scales and
  noise correlation. Replicates vary initial conditions and fault severity.
  Configuration seeds are disjoint. Faults share paired initial conditions and
  disturbances; cluster uncertainty by configuration.
- Ten replicates per healthy/known/unknown mechanism per configuration: 480
  known training episodes; 320 known validation episodes plus 96 proxy-unknown
  episodes; 1,400 final episodes (200 per each of seven mechanism classes).
- Normal chassis gains 0.95–1.05; gains are estimated from the healthy prefix,
  never supplied from the evaluator. Noise correlation is 0, 0.6 or 0.9 with
  XY standard deviations 0.008–0.012 m and yaw 0.012–0.020 rad. Prefix and
  suffix noise share their proper temporal state. Noise, severity and initial
  state do not depend on the selected probe or the decoder.
- One fifth of configuration IDs start near a workspace corner, heading inward.
  A common measured-pose supervisor stops translation if its 0.2-second
  extrapolation would exceed ±2.8 m. True-state violations of ±3 m are scored
  only by the evaluator. This is not a guarantee for arbitrary unknown dynamics.

## Mechanisms and probes

Known library: healthy, 20–40% effectiveness loss in either command axis,
±0.08–0.16 rad/s turning-command bias, or ±0.06–0.14 m offset in one position
axis. Offset begins after commissioning, making it distinguishable from an
unknown initial coordinate origin. Final unknowns are the proposed actuator lag
(0.08–0.20 s), translational dead zone (0.03–0.07 m/s), and pose-reporting latency
(0.10–0.30 s). No final unknown episode fits baseline parameters or thresholds.

Validation proxies, equally available to baseline selection, are position
quantization (0.04–0.07 m) and periodically held measurements (0.12–0.24 s).
They select fixed probes and rejection operating points, not new fault templates.
Held measurements are not fixed latency; possible transfer between these two
timing corruptions is a limitation, disclosed rather than treated as a blind
claim about arbitrary unknown mechanisms.

The nine probe targets are `(v, omega)` = `(0,0)`, `(0.04,0)`, `(0.25,0)`,
`(0.15,±0.5)`, `(0.04,±0.5)`, `(0.25,±0.5)`. Ramp over the first 0.1 s of a
slot. Exhaustively search all 81 pairs and all nine one-slot choices on source
validation. Do not pick a fixed probe using final unknown labels. The fixed
persistent-excitation control uses `(0.25,+0.5)` then `(0.04,-0.5)`.

## Conventional decoders and selection

The gray-box profile least-squares bank estimates healthy kinematic gains and
fits known gain, turning-bias and position-offset deviations. Fault parameters
have minimum nonzero magnitudes; the healthy model is not nested without a
model-selection cost. Calibrate a healthy-versus-fault fit-improvement margin at
the 97.5th percentile of healthy validation cases. This protects the physical
baseline against selecting a larger fitted model solely because it fits noise.

Broad response features add residual shapes, recent/whole-history fits, block
increment summaries and generic input/response cross-correlations. These are
not extra templates for the final unknown mechanisms. ExtraTrees (128 trees,
minimum leaf 2, feature fraction 0.8) supplies a second known-class decoder.
Compare absolute model-fit rejection and standardized five-nearest-neighbor
distance rejection. Train at most 3,000 feature rows per class and use at most
600 class-balanced rows per class for the distance reference; use deterministic
subsampling and a minimum feature scale of 0.02. Decoders are fitted separately
for 8, 9 and 10 seconds so prefix and longer-window features are not conflated.

Choose among source-validation rejection quantiles 0.90, 0.95, 0.975, 0.99,
0.995, 1.0. Use class-conditional thresholds, and maximize proxy-unknown
rejection among choices meeting known-fault recall ≥0.90 and healthy false
alarms ≤0.05. If none meets the source constraints, save the fallback and mark
the failure; never retune on the final panel. Select optimized fixed probes
under the same source operating constraints. Also retain every fixed-pair curve
on the final panel as a descriptive, explicitly hindsight-only comparison.

Adaptive baselines are approximate Gaussian-mixture expected information gain
(four fitted hypotheses, 32 fixed Monte Carlo samples per hypothesis) and
finite-menu output-box overlap minimization. They receive only observed command
and pose history. Their forecast noise is estimated from source healthy fit
residuals. They do not use a sibling branch, true pose, fault label or hidden
parameter. The overlap baseline is an adaptation of a conventional principle,
not a reproduction or formal guarantee of the upstream reachability optimizer.
Three independent random action seeds provide matched-slot random controls.

Factor the same selected evidence across all three decoders. The same-decoder
action ceiling can choose any of the 81 probe pairs or no probe using evaluator
labels; it is a nondeployable upper bound. Unknown rejection under reject-all
does not pass the known-fault/healthy operating constraints. A ceiling gap may
also exploit observation noise and does not by itself establish learnability.

## Identifiability reference and decisions

The separate, unfair reference obtains all mechanism families in source
training and an eight-slot sequence (8 s probing, total 16 s). It observes only
measured responses, never test labels. Select ExtraTrees or standardized RBF
SVM and a binary known/unknown operating threshold using source validation.
Include block-response traces in addition to the broad features. This is a
feasibility reference, not proof of information-theoretic identifiability. A
failure of this reference does not prove an impossibility theorem.

Use the original protocol's gates: 90% identifiability-reference accuracy;
90% known-fault macro recall and ≤5% healthy false alarms for usable policies;
intervention must beat passive observation at matched time; a ≥10-point
same-decoder action-ceiling opportunity across at least two unknown families
before considering a new policy; ≤3 points to a simple policy closes adaptive
selection. Anything else is inconclusive, not automatic permission to train or
implement a method. Report results per unknown mechanism and configuration.

Runtime and byte figures are software measurements or serialized model sizes,
not FPGA, power or embedded real-time measurements. No physical hardware is used.
Source changes made during development qualification are permitted before the
freeze; after the freeze, preserve parameters and disclose any necessary bug fix
as a new revision rather than tuning against final results.
