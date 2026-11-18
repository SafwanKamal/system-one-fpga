# Host-only speculative decoding pilot on RC1 (board)

Written 2026-11-17, before the run. Unchanged RC1 bitstream (v9e), package
`/var/lib/sysone/hardware-consolidated-rc1-20261108`; no programming, no new
package, no change to the installed service or launcher. The RC1 service is
stopped for the run and restarted afterwards.

## Question

1. On the real board, does lossless greedy speculation (8-token batch
   verification, then a head scan per lane) emit exactly the tokens, head logit
   bits and K/V rows that ordinary one-token decoding emits?
2. How much decode wall time does it save on the current bitstream, and does the
   replay cost model predict it?

The C-simulation audit (`experiments/schedule_invariance/`) passed on one
24-token prompt. This pilot checks the routed hardware, longer contexts
(219–867 prompt tokens) and the actual draft/rollback pattern.

## Workload (fixed by `select_workload.py`, `build/v2/spec-pilot/workload.json`)

- 24 prompts from the saved Qwen3-0.6B runs (`qwen06-q4`), 12 `general` and 12
  `maintenance`, distinct, chosen by SHA-256 order, interleaved; 96 new tokens
  maximum, stopping at EOS. Only the prompt ids are used: the saved outputs come
  from another quantization and are not a reference.
- 3 RC1 tool-call queries (`/proc/sys/kernel/random/boot_id`, `/proc/uptime`,
  `/proc/version`) with the service prompt; 32 new tokens maximum.
- Every case decodes twice from position 0, no prefix reuse. The order alternates
  (`ar` first on even cases, `spec` first on odd) so neither mode always inherits
  the other's stale cache rows.

## Modes

- `ar`: the service path, i.e. prefill in groups of 8, then `cmd 1/2` single-token steps
  with a full head scan.
- `spec`: same prefill. Each step drafts up to 7 tokens by the longest n-gram match
  (n = 6, 4, 3, 2) in prompt + output, then in outputs of earlier cases (causal).
  The draft is verified in one 8-token `cmd 7/8` pass, followed by one full head scan
  per lane (`cmd 9` lane copy, `cmd 3/4`) until the first mismatch. With no draft, it
  takes an ordinary `cmd 1/2` step. Rejected K/V rows are left in place and overwritten
  later.

## Decision rules

- **Correctness pass:** for every one of the 27 cases, identical token lists,
  identical head logit bits for every emitted token, and identical SHA-256 over
  all K/V rows of the committed sequence (all layers, K and V, all heads).
  Any difference is a fail. Report the first case and token, and make no speed claim.
- **Speed (reported only if correctness passes):** decode-phase wall time `ar` / `spec`,
  per domain and overall. It is compared with the replay cost model applied after
  the run to the board's own `ar` outputs. The constants are fixed now:
  T_AR = 170 ms, T_PASS8 = 181 ms, T_HEAD = 44 ms per lane checked.
- **Kill rule for the host-only route:** if the maintenance-domain decode speedup
  is below 1.10x, host-only speculation on this bitstream is not worth
  productizing. The question then becomes the batched-head/second-port
  bitstream, or stopping.

## Limits fixed in advance

- One board, one session, one boot. Greedy only. 27 cases, so this is not a reliability sweep.
- Prefill time is identical by construction and excluded from the speedup.
- The drafter's cross-case history depends on case order; the order is fixed in the workload.
- The full benchmark sweep stays stopped.
