# Proposed first experiment: testing the adequacy of a fault catalog

Status: designed November 16, 2026; not implemented, run, or preregistered as an executed experiment. Freeze an executable revision and all remaining calibration decisions before final evaluation. No new diagnostic method or FPGA implementation is proposed in this first screen.

## Scientific questions

Does a brief additional physical test expose an unknown mechanism better than passive history? If so, does adapting the test to current evidence leave meaningful room beyond a strong fixed probe, persistent excitation and conventional model validation?

The target is known behavioral-mode recognition versus rejection as unsupported. It is not identification of an arbitrary unseen fault's semantic name. Existing model invalidation already rejects all catalog entries. Existing robust Bayesian experimental design already considers model mismatch. The intended screen tests an empirical opportunity, not whether these concepts can be invented again.

## Reference and simulator qualification

Reference: [Ni et al., nonlinear active model discrimination](https://arxiv.org/abs/2606.19590) and the [public unicycle example](https://github.com/gtfactslab/Ni_RAL2026/tree/main/unicycle). We inspected the single-step demo, model/optimizer entry points and pinned dependency file. The example has nominal, actuator-fault and sensor-fault scenarios. No reproduction has been run.

First reproduce that closed-catalog example in an isolated environment, recording the exact upstream commit, environment and output. Do not silently edit its original model or report an extension as a reproduction. A minimal independent simulator may implement the standard kinematic equations; document every difference from the reference.

For the proposed diagnostic benchmark, integrate a unicycle state `(x, y, yaw)` at 50 Hz:

```
x_dot   = actual_v * cos(yaw)
y_dot   = actual_v * sin(yaw)
yaw_dot = actual_omega
```

Actuator dynamics map commanded `(v, omega)` to actual motion. Sensor functions map the state to measured pose. Policies see commands, measured pose and acquisition times only, not simulator state, true parameters, fault flags, noise realizations or evaluator labels. The physics engine and fault generator must be separate from the inference/selection API.

Proposed development defaults: 8 seconds of passive path following, then at most two one-second probe slots. Nominal speed 0.15 m/s; speed limited to 0.25 m/s, turn rate to 0.5 rad/s. Independent pose-noise scales start at 0.01 m and 1 degree; include correlated-noise validation controls rather than assuming that 50 Hz observations are independent evidence. Choose and freeze noise correlation and integration tolerances using development cases only.

Do not hard-code a state-estimation likelihood equal to the hidden evaluator's noise or nuisance parameters. Methods receive the same public uncertainty ranges and healthy commissioning allowance. Initial states and path/controller configurations vary. Evaluation must not consist only of a selected pair known in advance to require a particular maneuver.

## Fault and nuisance partitions

Collection/development catalog: healthy behavior, actuator effectiveness loss, actuator command bias, and sensor pose offset. Include parameter ranges and severity grids selected on development data; all methods get the same known mechanisms.

Final evaluator-only mechanism families: actuator response lag, actuator dead zone and sensor reporting latency. Initial proposed ranges are 0.08–0.20 s lag, 0.03–0.07 m/s dead-zone width and 0.10–0.30 s sensor latency. These are simulation design choices, not measured fault distributions. Before the final freeze, qualify that their scales produce nontrivial behavior within the probe horizon. Do not tune scales to make a preferred policy win.

Final mechanism data must not train a classifier, likelihood, discrepancy model, selector or rejection threshold. If proxy unknowns are needed in development, specify different mechanisms (for example coarse quantization and isolated dropped measurements) and disclose that supervision. Baselines receive the same proxy examples. The main threshold calibration should use held-out known/healthy development configurations to constrain false rejection.

Benign variation includes declared robot and controller parameter variation, measurement noise and initial pose error. It must be present independently of fault identity. Do not label every unseen chassis or operating speed an unknown fault. Assign entire robot/controller configuration seeds to train, validation and test, with no overlapping episodes or windows. Proposed counts: 12 training, 8 validation and 20 final configuration seeds; at least 10 independent episodes per final configuration in each healthy/known/unknown stratum, with mechanism counts balanced and fully reported. Cluster statistical uncertainty by configuration, not by 50 Hz samples.

Include a separate observational-equivalence control such as matched kinematic gain and wheel-radius effects. Where even the full-mechanism reference cannot distinguish causes under the allowed actions/sensors, score a behavioral equivalence class or mark the distinction unidentifiable. Do not demand a unique physical-component label.

## Available probes and episode semantics

Use a common finite action menu built from straight-speed increase/decrease, left/right turns, and a zero-input/coast slot, with declared ramps and shared amplitude/effort limits. Freeze exact waveforms before test generation. At most two one-second slots are allowed; all policies receive the same menu, observations and total horizon. Report a continuous-action closest-method track separately if an upstream optimizer is permitted a larger action space.

An episode is continuous. There is no reset between probes, no simultaneous queries of counterfactual branches and no access to an unchosen action's response. Record requested and actually executed commands separately. The evaluator must verify that a nonzero intervention was actually applied before charging it as evidence. Exhausted or invalid actions produce explicit outcomes, not silently returned nominal observations.

Use conservative command and workspace limits drawn from a public physical envelope, not a shield constructed with the hidden true fault. Include boundary states without selecting only cases favorable to adaptivity. A common supervisor may clip or stop commands using the same available measurements for every method. Charge clipping and termination. The evaluator can use true state to score a violation, but must not feed a true-state feasibility mask to a policy. Safety in the simulated cases does not prove safety under arbitrary unknown physics.

## Strong simple baselines

1. **Passive model bank with absolute rejection.** Fit conventional observer/residual models for each known behavior, marginalize or bound benign nuisance variation, and reject if no model meets a calibration-selected absolute-fit threshold. A forced-choice posterior is an additional weak control, not the main baseline.
2. **Optimized fixed probe.** Select the best one- and two-slot waveforms on development configurations, allowing the same state-dependent amplitude clipping as other policies. Do not use a deliberately weak arbitrary turn as the only fixed comparator.
3. **Random matched-cost probes.** Match number of slots, energy envelope and execution restrictions; repeat action randomness independently.
4. **Persistent excitation plus ordinary identification.** A short ramped step/alternating-turn or multisine sequence, selected on development data, followed by ARX/state-space prediction and conventional residual/model validation.
5. **Greedy Bayesian information gain.** Select from the same menu using the known-model posterior; diagnose with the same absolute-fit rejection as baseline 1. Posterior concentration alone must not imply validity.
6. **Reachable-output overlap plus invalidation.** Apply the closest conventional separating-input principle to the common action menu with matched nuisance bounds. Label any finite-menu adaptation correctly; do not call it an unchanged reproduction of the continuous upstream optimizer.
7. **Broad features plus a compact classifier.** ExtraTrees or gradient boosting on command/response features. Give it the same chosen evidence, source configurations, proxy unknowns if used and validation budget. This tests whether explicit physics adds anything beyond cheap response features.

Factor probe selection and diagnosis when possible: run the same decoder across several selectors, and several decoders on the same fixed evidence. No selector may receive the hidden mechanism through an inference cache or model enumeration.

Before claiming a novel method, add the closest full robust-design competitors: Forster et al.'s model-correctness/auxiliary-model criterion, maximin robust BED, and a faithful nonlinear discrimination comparison. The first baseline-only screen need not implement a new robust policy to establish whether a cheap fixed probe already closes the opportunity. A positive screen without these competitors is insufficient for algorithmic novelty.

## Two distinct ceilings

**Action-selection ceiling:** Offline, branch the simulator at each allowed decision and enumerate every valid one- and two-slot response. Keep the same incomplete catalog, the same observation channels and the same fixed decoder as the compared method. An oracle may choose the sequence with best ground-truth evaluation outcome. This is a nondeployable upper bound on action allocation, not a reported policy. Score each branch at its own time/effort cost; maintain state and disturbances consistently within that branch.

**Identifiability reference:** Separately allow access to all mechanism templates and extensive lawful probing to test whether the proposed labels are observable at all. Its extra physical knowledge and possibly larger budget make it an unfair method baseline; never use that difference as evidence for an adaptive selector's performance.

Common random numbers should couple exogenous noise across policy replays without giving policies the noise seed. Counterfactual simulations must not flow into deployable-policy training or test-time observations.

## Metrics and gates

Report unknown-mechanism rejection recall, false specific diagnoses on unknown mechanisms, known-fault macro recall, healthy false alarms, abstention/coverage, calibration, diagnostic time, probe effort, tracking deviation, safety terminations, selection CPU time and model state bytes. Include per-mechanism and per-configuration results. No sample-wise point adjustment or label-informed threshold selection.

Proposed advancement gates, to freeze before final runs:

- Identifiability reference achieves at least 90% known/unknown decision accuracy on the identifiable panel. Otherwise the task is inconclusive for method development.
- Evaluate unknown rejection while requiring at least 90% known-fault macro recall and at most 5% healthy false alarms. Reject-all and diagnose-everything policies cannot pass this operating constraint.
- Intervention must improve on the strongest passive comparator at matched decision time, including its option to simply observe longer.
- Under the practical two-second probe budget, the same-decoder action ceiling must exceed the strongest feasible simple selector by at least 10 percentage points in unknown rejection, without breaking the known/healthy operating constraints. Require the direction on at least two of the three unknown families and multiple held-out configurations. This demonstrates opportunity only; it is not evidence that a new method achieves it.
- If any simple selector is within 3 points of the action ceiling, close the adaptive-selection branch. Between 3 and 10 points is inconclusive; do not scale implementation. If a nearest existing robust-design method closes a later gap, do not rename it as our method.
- No FPGA implementation follows a positive simulator screen. First reproduce the effect in another physical domain or an independently validated rig and show that compute is a material bottleneck.

Analysis must disclose if no common operating threshold satisfies all constraints. Do not remove difficult configurations or change noise, cap, severity, unknown families or metric after seeing final results to create a gap. A useful outcome is a conventional fixed test and no new research method.

## Deliverables and boundary of this proposal

Freeze simulator/decoder source, fault partitions, probe menu, noise model, configuration seeds, hyperparameters, source provenance and metrics before final generation. Save observations/commands, all selections, thresholds and predictions; independently recompute metrics and verify observation permissions. Unit checks must test actual intervention effects and known observational-equivalence cases, motivated in part by published benchmark-engine problems.

The next deliverable is a reproducible baseline/ceiling report and a go/no-go decision. This document contains no measured result, no trained selector and no hardware claim. The original sensor-memory data and frozen experiment hashes remain unchanged.
