# Cost-aware drafting for lossless speculation on v9g: held-out evaluation

Written 2026-11-19, after development on the even-index cases and before any metric on the
odd-index cases was computed.

## Why

On v9g, a verify pass costs about as much as a single step. The board fit gives:
- pass = 150 ms + 7.7 ms per token, plus position terms;
- step = 174 ms, plus a position term.

RC1.1's drafter and gate were tuned for v9e, where every verified lane needed its own head
scan. Decoding is greedy, so `replay.py` reproduces any drafter's run exactly from the
recorded plain-decode tokens. Replaying the RC1.1 policy matches all seven per-case
speculation statistics of the v9g board run (181/181). `cost.py` fits v9g decode time to the
replayed command logs: R² 0.99998, median per-case error 0.2%.

## Development findings (even split, 90 cases)

| Policy | Modelled speedup vs plain decode |
|---|---|
| RC1.1 (drafter + 0.25 gate) | 2.448 |
| RC1.1 drafter, no gate | 2.477 |
| + earlier prompts in cross-case history | 2.587 |
| + cost-aware truncation (below), with a 1-token fallback match | **2.703** |
| Upper bound: perfect drafts (true continuation) | 5.551 |
| Upper bound: RC1.1 drafts with perfect truncation | 2.795 |

Other heuristics added less than 2%, or nothing:
- voting among matches;
- chaining drafts;
- longer suffixes;
- ranking sources (this reply, then history, then prompt).

## Candidate (frozen)

`CostAwareDrafter(VoteDrafter(prompts=True, ns=(6, 4, 3, 2, 1)), coef_dev, prior=0.5,
prior_w=2.0, P=4)` from `drafters.py`:
- **Base drafter:** the RC1.1 longest-suffix drafter, plus a 1-token suffix. Earlier prompts
  go into the history along with earlier replies.
- **Acceptance estimates:** for each suffix length and draft index, a causal estimate of
  P(token right | earlier tokens right). It comes from earlier full drafts, checked once the
  reply reveals the true tokens.
- **Length choice:** the draft length L (0 to 7) that maximises expected emitted tokens per
  unit of modelled time. L = 0 is a plain step. There is no separate gate.
- **Cost coefficients:** `coef_dev` is the cost model fitted on the even-split cases only.

Exactness does not depend on the drafter: every emitted token is the engine's own greedy
token.

## Held-out test (odd split, 91 cases)

`evaluate.py` replays the whole workload in order, so drafter state carries across cases as
on the board. It reports, on the odd split:
- modelled speedup vs plain decode, for the RC1.1 policy and for the candidate;
- the ratio candidate / RC1.1;
- the same by domain.

The evaluation model is `cost.py` fitted on all 362 measured runs; this is the measurement
model, not something the drafter uses.

**Decision rule.**
- **PASS:** candidate / RC1.1 ≥ 1.05 on the odd split. The development gain was 1.104.
- **FAIL:** anything else.

PASS allows a pre-registered board check: speculation with the candidate drafter on v9g, the
181 cases, exactness against the v9e records, and a measured speed threshold set from this
model. That check needs user approval for the image swap.

## Limits

- One workload of 181 cases. The splits interleave in one drafter history, so the held-out
  cases are not independent of the development cases' outputs. The board check measures real
  time.
- Times are modelled, not measured, until the board check.

## Amendment 1 (before any held-out metric was seen)

The first run of `evaluate.py` stopped with a division by zero, before printing anything:
the odd split has no `long` cases. The fix skips empty domains; the decision metric is
unchanged.

The parity split is unbalanced by domain:

| Split | general | maintenance | long | tool |
|---|---|---|---|---|
| Even (development) | 21 | 49 | 20 | 1 |
| Odd (held-out) | 49 | 21 | 0 | 20 |

The held-out test is therefore weighted toward the hardest domain (general), and the
development "tool" figure is one case. The decision rule stays as written.
