# Cost-aware drafting on v9g: 1.13–1.17x more decode speed, same output (2026-11-19)

## Result

The held-out test PASSED: on the 90 held-out cases, the candidate drafter is **1.174x** faster
than RC1.1's drafter and gate. The threshold was 1.05 and the development split gave 1.102.
Over the whole workload the modelled gain is 1.134x, which would take v9g speculative decode
from **2.27x** to about **2.57x** faster than plain v9e decoding.

**The board check PASSED** (2026-11-20, below): measured gain **1.138x** on the whole
workload and 1.173x on the held-out half, with all 181 cases bit-identical.

## Board check (v9g, 2026-11-20)

Protocol: `experiments/draft_board/BOARD_PROTOCOL.md`, with hashes recorded before the run in
`build/v2/draft-board/prereg-sha256.txt`. Results: `build/v2/draft-board/{pilot.json,
analysis.json}`. Boot 62097330, run 05:27–06:42Z. Each case was prefilled once, then decoded
with both policies from that prefill; the order alternated by case.

- **Exactness:** 181/181 cases in both modes matched the v9e records: tokens, head logit bits
  and K/V hash.
- **Replay:** 181/181 cases in both modes matched the offline replay on all seven draft
  statistics, so the replay is exact on hardware for a new drafter as well.
- **Speed:** RC1.1 policy 787.3 s against candidate 692.0 s, so **R = 1.138**. The threshold
  was 1.10 and the model predicted 1.134. Measured time is within 0.4% of the model for both
  policies.

| Domain | n | Measured R | Modelled R | Tokens per pass |
|---|---|---|---|---|
| general | 70 | 1.189 | 1.194 | 1.99 → 2.30 |
| maintenance | 70 | 1.094 | 1.091 | 3.76 → 4.10 |
| long | 20 | 1.124 | 1.100 | 2.58 → 2.80 |
| tool | 21 | 1.271 | 1.278 | 3.50 → 4.63 |
| **all** | 181 | **1.138** | 1.134 | 2.85 → 3.21 |
| odd split (held-out) | 90 | 1.173 | 1.174 | 2.55 → 2.96 |

Next: make the candidate the drafter of a v9g speculative service. That is a separate service
change with its own qualification.

The protocol is `experiments/draft_research/PROTOCOL.md`, with Amendment 1. Its hashes were recorded before the run in
`build/v2/draft-research/prereg-sha256.txt`, and the results are in `heldout.json`.

## Method

- **Exact replay (`replay.py`).** With greedy decoding, every token a verify pass emits is the
  engine's own greedy token, so it is one of the recorded plain-decode tokens. A fake engine
  that serves them runs the unchanged `spec_decode.decode` exactly as on the board. Replaying
  RC1.1's drafter and gate reproduces all seven speculation statistics of the v9g board run
  on all 181 cases.
- **Tool-call prompts.** The 21 tool cases are tokenized with the pinned BPE and a stdlib
  stand-in for its aarch64 pre-tokenizer. The stand-in is validated by round-tripping all 160
  stored prompts and matching all 21 recorded prompt lengths.
- **Cost model (`cost.py`).** Least squares on the 362 measured v9g decode times (both modes)
  with hardware-shaped features:
  - single step: 174 ms + 0.096 ms × position;
  - verify pass of k tokens: 150 ms + 7.7 ms × k + position × (0.067 + 0.051 × ceil(k/4)) ms.

  R² is 0.99998 and the median per-case error is 0.2%. On v9g a verify pass costs about as
  much as a step, which is why RC1.1's v9e-era gate is too cautious.

## What limits speculation

On the development split:

| Policy | Speedup vs plain decode |
|---|---|
| RC1.1 | 2.448 |
| RC1.1 drafts, no gate | 2.477 |
| RC1.1 drafts, perfectly truncated (bound) | 2.795 |
| Candidate | 2.703 |
| Perfect drafts (bound) | **5.551** |

The drafts themselves are the limit. RC1.1 emits about 3.2 tokens per weight pass; perfect
drafts would emit 7.6. In the general (function-calling) domain, the n-gram drafter latches
onto the tool schema in the prompt ("description": …) when the reply's structure
("arguments": {…) lives in earlier replies. These heuristics all gained less than 2% each:
- voting among matches;
- chaining;
- longer suffixes;
- source ranking.

## Candidate

`CostAwareDrafter(VoteDrafter(prompts=True, ns=(6,4,3,2,1)))` in
`experiments/draft_research/drafters.py`:
1. **Cross-case history** also holds earlier prompts, not only earlier replies.
2. **A 1-token suffix fallback** is used when no longer match exists.
3. **Cost-aware length.** For each suffix length and draft index, a causal estimate of
   P(token right | earlier tokens right) is kept. It comes from full drafts checked against
   the reply once it is known. The verified length L (0–7, where 0 is a plain step) maximises
   expected tokens per modelled second. This replaces the gate.

Held-out (odd split) results:

| Domain | n | RC1.1 | Candidate | Ratio | Tokens per pass |
|---|---|---|---|---|---|
| general | 49 | 1.668 | 2.014 | **1.207** | 2.05 → 2.41 |
| maintenance | 21 | 2.733 | 3.005 | 1.099 | 3.42 → 3.76 |
| tool | 20 | 2.904 | 3.713 | **1.279** | 3.50 → 4.63 |
| **all** | 90 | 2.070 | 2.430 | **1.174** | 2.55 → 2.96 |

Output cannot change: every emitted token is still the engine's greedy token.

## Limits and next

- **Split balance.** The parity split is unbalanced by domain: the odd split has no long
  cases and most of the general ones (Amendment 1). Both splits share one drafter history.
- **Service integration.** The board check ran the drafter in a pilot harness, not in the
  RC1 service. RC1 itself still runs v9e with RC1.1's policy.
- **The larger headroom (5.5x bound) needs a better draft source than n-grams.** Options:
  - a small learned drafter on the ARM cores, which are idle while the FPGA verifies;
  - a draft table built from the model's own replies to a large disjoint prompt set.

  Both need a corpus of Qwen3-0.6B outputs.
