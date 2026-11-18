# v8 protocol v2 qualification

This is a separate benchmark version. It does not change the v8 model, bitstream,
runtime, tokenizer or launcher. The v1 campaign and its 44 development traces
remain preserved. No full campaign is launched by this qualification package.

## Protocol changes

- Explicit valid JSON array instructions instead of loosely typed placeholders.
- Separate enum instructions and a real EOS-aware terminal record parser.
- A streaming enum record is incomplete until newline or actual EOS: `0 A 4`
  cannot terminate early if the next generated digit would make it `0 A 42`.
- Explicit input schema: count and status fields, or count/status-digit entries.
- Plain instructions and a one-example demonstration compared on development
  only. The demonstration uses a different set-counter problem, not the answer
  to the evaluated request. No grammar constraints or vocabulary masks.

## Selection and qualification

CPU backend: the pinned Qwen3-0.6B Q8_0 GGUF using local llama.cpp, greedy decoding,
no conversation-template rewriting, explicit disabled-thinking prompt and 32
output-token allowance. This is a software quality control, not a reproduction
of the FPGA's INT8 activation arithmetic or an on-board CPU speed baseline.

Development: six cases (set/add/copy/conditional/missing/error), six context/output
arms, two prompt variants: 72 CPU generations. Select the variant by complete
correct responses, then format-valid responses; ties retain plain. The selected
variant and all qualification inputs/expected outputs are then frozen.

Qualification: 12 fresh cases, two per task family, across six arms: 72 CPU and
72 paired FPGA requests. These are single-step protocol controls. H and J have
identical initial state content here; this is not yet a dependent-chain comparison.
The model receives only the prompt and state. Expected results are scorer data,
never inserted into the model prompt or substituted for observed outputs.

Gate declared before qualification: each arm must have 12 completed cases,
at least 11 format-valid records and at least 9 exact semantic matches. FPGA
qualification also requires matching pinned input token IDs, causal fixtures
before/after, and unchanged deployment identity. This is an experimental
benchmark admission gate, not a production-reliability guarantee.

All cases run even if the qualification gate fails, to compare CPU and FPGA on
the same finite inputs. The gate blocks a full sweep; it does not hide failures.
No prompt changes are made in response to qualification results.

## FPGA isolation

The frozen snapshot is installed only under
`/var/lib/sysone/benchmarks/v8-protocol-v2`. It reads the original deployment from
`/var/lib/sysone/qwen-fpga-decoder-v8-startup-v2`. It takes the exclusive inference
lock, reprefills every prompt at position zero, disables prefix reuse and never
commits prefix files. All result writes are to the new benchmark directory.
Normal scratch/KV writes are required for inference. No tool actions execute.

The FPGA runner checks its frozen source/manifest hashes and requires the board's
tokenizer IDs to match the frozen CPU-side pinned-tokenizer inputs exactly.
Its output parser accepts only the declared finite fields and types. Formatting
and semantic accuracy are scored separately.

A final, separately labeled original boot-ID command-generation control checks
the unchanged MVP prompt. It is not a tool-execution or latency benchmark.

## Evidence and disposition

Completed result: CPU 69/72 format-valid and 44/72 exact semantic matches; FPGA
65/72 format-valid and 40/72 exact semantic matches. Both overall gates failed.
The H/J JSON-array arms each met the experimental per-arm thresholds (12/12
format, 9/12 semantic), while compact state and enum arms did not all meet them.
This does not qualify the six-arm dependent-workflow comparison.

All 72 paired inputs matched the frozen tokenizer IDs. Twenty-four repeated-input
H/J checks produced identical FPGA output IDs (zero repeat mismatches). There
were 61 matching valid parsed records among the 64 cases valid on both backends;
two further cases were invalid on both, and six differed in format validity.
CPU/FPGA arithmetic is different, so output disagreement is retained rather than
silently corrected or described as bit-exact parity.

Pre/post causal fixtures passed, deployment identities matched, and all 269
sealed local v8 artifacts verified unchanged. A final original-MVP generation
control reproduced the sealed 62 prompt IDs and 16 output IDs exactly; no tool
was executed. Full sweep was not restarted. The authenticated session was closed
after collection, so no qualification or background benchmark jobs remain.

Local artifacts are under `build/v2/v8-protocol-v2/`: CPU raw stdout/stderr and
prompts, frozen qualification manifest and source snapshot, board job receipts,
collected FPGA traces, paired comparisons and admission summary. The final
`qualification-summary.json` is authoritative for pass/fail and restart status.

Full sweep remains stopped unless all declared admission checks pass. Qualification
failure is retained rather than weakening thresholds or retrying favorable cases.
