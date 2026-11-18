# Focused MVP argument correction — 2026-10-18

The original FPGA result for the reused song request copied the song ID into the
language argument. A single saved integer pass confirms that this is encoder
quantization drift: float en-US joint span score 10.026 versus ID 8.974; original
INT8 en-US 2.976 versus ID 7.643. Greedy-to-joint span decoding does not repair
this case, so that proposed successor was discarded.

One training-only calibration repair was attempted: 64 evenly spaced saved
training jobs within 128 tokens and the existing median range statistic. It still
predicts the ID for language. That image is rejected and has not contacted the
board. No benchmark sweep, new training or promotion occurred. The original
sealed image, firmware and ingress remain unchanged.

The explicit temporary MVP bridge is scripts/v2/general_encoder_mvp_hybrid_v1.py.
It requires a request-hash-bound physical R5/FPGA result for the exact sealed
image/firmware, then recomputes the request with the parent FP32 model locally.
Call names/count/order must agree; otherwise it fails without a proposal.
It validates both call structures, returns the FP32 arguments, and records each
change with both original and corrected values. It executes no external tools.
This is host-assisted inference, not an INT8 model fix or a pure FPGA MVP.

A fresh FP32 computation applied to the prior sealed physical result produces:
{"name":"songs_v2_get_details","arguments":{"is_id":"45077244","l":"en-US"}}
Evidence: build/v2/general-tool-argument-fix-v2/hybrid-replay.json. This is an
explicit replay check, not a newly completed hardware window. Correction type
handling and rejection of call-selection disagreement were checked directly.
No new accuracy/generalization or deadline claim follows from this one fixture.

The fresh hardware → host-check window is COMPLETE under
build/v2/general-tool-encoder-mvp-board-v2. R5 controlled three H768 FPGA passes
and produced the same raw INT8 proposal with the incorrect language. The receipt
binds the exact request, image and R5 firmware. The fresh local FP32 computation
corrected only l from 45077244 to en-US. Final typed call is the correct proposal
shown above. Evidence: hybrid-result.json and result.json. No external function
was executed; this is a positive hybrid call proposal, not an API-response demo.

Restoration independently verified every MiniLM image byte and original R5 ELF
identity. Linux boot ID remains 6c80ec1a-e7ae-473f-b169-d54f129615d1. FPGA is
operating at 199,999,998 Hz. R5 pinned/reserved/mapped/may_run/quarantine are zero,
leases zero. SSH closed after successful restoration; no credential was saved.
No JTAG, PL programming, reboot, dashboard changes or permanent deployment.

No benchmarks were added. Remaining MVP limits: local host FP32 model and both
model passes are required; INT8 language correctness remains unresolved; no
external-tool dispatch or terminal deadline qualification has been demonstrated.
