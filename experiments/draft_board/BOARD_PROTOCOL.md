# Cost-aware drafter board check on v9g

Written 2026-11-19, before the board run. Follows the held-out PASS in
`experiments/draft_research/PROTOCOL.md` (candidate / RC1.1 = 1.174 modelled, odd split).

## What runs

`draft_pilot.py` on the KR260 with the v9g image loaded (`swap_v9g.py` from the v9g pilot
tar, unchanged) and the RC1 service stopped. It runs the 181-case qualification workload in
its original order. Each case gets one prefill, then two speculative decodes from the same
prefill. Both use v9g's batched head (one cmd 11 + cmd 12 scan per verify pass):

- `rc11`: RC1.1's drafter and 0.25 gate, history fed with the output;
- `candidate`: the frozen candidate, `CostAwareDrafter(VoteDrafter(prompts=True,
  ns=(6,4,3,2,1)), coef_dev, prior=0.5, prior_w=2.0, P=4)`, no gate, history fed with
  prompt + output.

The two modes alternate in order from case to case. `drafters.py` is a byte copy of
`experiments/draft_research/drafters.py`, and `spec_decode.py` is a byte copy of
`experiments/spec_service/spec_decode.py`. `coef_dev` and the expected per-case statistics
come from `expected.json`, which `prepare.py` writes from the exact replay. The host dry run
(`dry_run.py`) reproduces every expected statistic using the pilot's own loop.

## Checks per case

1. **Exactness:** for both modes, tokens, head logit bits and the SHA-256 of the committed
   K/V rows equal the v9e `ar` record. In those records, `ar` equals `adaptive` on all 181
   cases.
2. **Replay agreement:** for both modes, all seven draft statistics equal `expected.json`.
3. **Timing:** each mode's decode seconds. Prefill is shared and is not counted.

## Decision rule

Let R = (sum of `rc11` decode seconds) / (sum of `candidate` decode seconds), over all 181
cases. The model predicts R = 1.134 for the whole workload and 1.174 for the odd split.

| Outcome | Condition |
|---|---|
| **PASS** | 181/181 exact in both modes, 181/181 replay agreement in both modes, and R ≥ 1.10 |
| **EXACT, NOT FASTER** | 181/181 exact, but R < 1.10 or some statistic differs from the replay |
| **FAIL** | any case not exact |

Also reported, without affecting the decision:
- R on the odd split;
- R by domain;
- measured vs modelled seconds for each mode.

A PASS supports making the candidate the drafter of a v9g speculative service. That needs a
separate service change and qualification, and is not part of this check.

## Board handling

These follow the v9g pilot procedure, unchanged:
- health gate `00-zhealth`;
- drain the RC1 service;
- swap to v9g, run, swap back, then restore RC1 and check one speculative request;
- `BOARD_STATUS.json` reservation, owner Claude;
- the image swap needs the user's approval.
