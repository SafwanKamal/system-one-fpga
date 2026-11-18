# Hardware review of Claude's November 8 niche selection

Prepared November 8, 2026 from the requested review, the gate plans and step-1 evidence, RC1 qualification, HLS source, runtime source and primary web sources. This is an independent source audit. No board access, build or implementation change was performed.

## Judgment

Claude's value review correctly asks what the FPGA contributes beyond a portable policy or decoding algorithm. Its broad rejection of all fabric LLM work goes beyond the available comparison. RC1 has a usable prefill advantage, and restricted vocabulary projection can be prototyped with the existing bitstream. T1 remains a useful, bounded optimization study. The broad mechanism has extensive software precedent, including sparse projection work missing from Claude's corpus. Its 1.5–2.3× figure is a hypothesis requiring measured mask density, forced-run lengths and host overhead.

The industrial gate currently offers a stronger structural fit for the board because enforcement can sit on a physically separate I/O path. Its current evidence establishes a small implementation of a simulated plant policy. The major research result would be agreement with the endpoint's accepted byte stream and causal plant-state history under adversarial transport and uncertain state, coupled to an enforceable approval and isolation boundary. Simple interlocks and a new proposer type give a thin novelty margin by themselves.

## Current baseline and exactness

RC1 combines the existing v9e BF16/context-2048 image with the ownership-aware service. Its November 8 qualification records 18/18 persistent outputs matching cold prompt IDs, output IDs, text and calls, and a 1,454-token prompt with repeat reuse. Two causal sweeps total 8,224 observed cases with worst absolute numerical error zero. The report explicitly limits those fixtures to layer 0 and distinguishes them from full-model generations. [RC1 qualification](../../hardware/candidates/consolidated-rc1/BOARD_QUALIFICATION.md).

The source validators compare floating-point numerical differences against a 2e-5 threshold. An observed difference of zero is stronger than merely passing that threshold, but it does not establish byte equality for signed zero. The block/long fixtures exercise particular B1, B8 and partial schedules, with selected sequential decode positions. They do not establish all-layer, all-input invariance for arbitrary alternations between one-token generation and variable known-token batches. Reference use of the vendor hls::expf oracle is appropriate to qualify this arithmetic profile. It leaves portable reproduction of the transcendental implementation as a separate task. [Testbench](../../hls/qwen_decoder_v9e/testbench.cpp), [board checker](../../scripts/v2/smoke_qwen_fpga_v9e.py).

The same-board A53 result is valuable but narrow. The saved 170.929 ms/token is one short H-bridge response using a particular llama.cpp server, 33 predicted tokens and a 2,048 context configuration. It motivates a current paired experiment. Comparing this figure to the fabric's approximately 169 ms/token does not establish workload-wide parity, and says little about full-call latency when prefill differs. [Saved CPU result](../../build/v2/eval/kr260-generation-q8.json).

The suggested 100× energy loss to TeLLMe v2 is unsupported. Its reported 5 W and 25 tokens/s imply 0.2 J/token at that operating point. RC1 has no matched energy measurement. Platform power boundary, model precision, workload and phases also differ. [TeLLMe v2](https://arxiv.org/abs/2510.15926).

## T1 novelty after another search

| Primary source | What it already establishes | Consequence for T1 |
|---|---|---|
| SGLang, 2024 | Compressed finite-state execution skips repeated model decisions along constrained paths. | Forced-span batching has clear precedent. [Paper](https://arxiv.org/abs/2312.07104) |
| XGrammar, MLSys 2025, and current author API | Efficient vocabulary masks and parser state, plus a documented token-ID jump-forward method that accepts returned IDs and prefills them before further sampling. | Returning token IDs already has precedent. This API greedily tokenizes the forced bytes and explicitly allows different tokenization from the model tokenizer. Exact masked-greedy ID preservation still requires singleton legal-token checks or a separate equivalence argument. Date the API claim to the checked implementation. [Paper](https://arxiv.org/abs/2411.15100), [API](https://xgrammar.mlc.ai/docs/latest/api/python/grammar_matcher.html) |
| DOMINO, ICML 2024 | Subword alignment avoids quality changes from overly restrictive grammar/token matching. | The benchmark must define the exact constrained token language. [Paper](https://arxiv.org/abs/2403.06988) |
| LLGuidance author documentation | Explains how byte-forced spans can change token segmentation and subsequent output, with canonical-token boundary handling. | A deterministic byte string alone does not prove a unique masked-greedy token sequence. [Documentation](https://github.com/guidance-ai/llguidance/blob/main/docs/fast_forward.md) |
| Gram2Token, ICML 2026 | Preprocesses grammar/tokenizer relations into token transitions and masks on GPU, with runtime category tables and an amortization study. | Grammar-to-token compilation and minimizing host interaction have recent prior art. Its published result is GPU continuous batching. [Paper](https://proceedings.mlr.press/v306/hua26b.html) |
| Murali, CUDA study, 2025 author report | Demonstrates slicing the output projection to allowed rows and block/thread filtering during the projection. Discusses forcing and the effects of scattered allowed tokens. | Skipping illegal head rows predates this proposal. This is a public implementation report, with a narrower evidence basis than a reviewed paper. [Report](https://gitlostmurali.com/blog/structured-generation-optimizations/) |
| Grammar-Conditioned Sparse Projection, 2026 public prototype and draft | Provides sparse row projection, grammar-aware batched block GEMM and dense fallback. Author tests target legal support and greedy output parity, while allowing floating-point reduction differences. | An exact masked sparse-head path with an adaptive density choice has direct implementation precedent. Its reported GPU results require independent reproduction. [Author repository](https://github.com/StealthEyeLLC/grammar-sparse-projection), [draft](https://raw.githubusercontent.com/StealthEyeLLC/grammar-sparse-projection/main/paper/draft.md) |
| Graphsignal author engineering report, October 2026 | Describes a restricted row-set head plus forced spans and measures component and integrated effects. With its speculative pipeline, their combined grammar mechanism loses end-to-end despite head-traffic savings. | The combined optimization already exists outside FPGA, and composition needs a measured ablation. The report uses byte-identity semantics for its forced spans. [Report](https://graphsignal.com/blog/understanding-inference-for-systems-engineers/) |
| JSONSchemaBench, 2025 | Separates schema coverage, generation efficiency and semantic quality across a large real-world schema collection. | A few compact JSON examples cannot establish a general structured-output advantage. [Paper](https://arxiv.org/abs/2501.10868) |

Targeted searches for FPGA-specific constrained LLM decoding returned no verified implementation of this precise combination. That search result leaves a potentially narrow hardware mapping contribution. It supplies insufficient evidence for a universal first claim.

## RC1 can test sparse projection without a new routed image

The HLS head accepts a physical/logical model byte offset, row count up to 8,192 and a token label base. For this profile each Q8 row occupies 1,088 bytes, and the vocabulary contains 151,936 rows. The full head therefore reads 165,306,368 logical weight bytes. The reduction returns both the winning token ID and its FP32 logit in the first eight output bytes. The current Python selector reads only the token. [HLS head branch](../../hls/qwen_decoder_v9e/qwen_decoder.cpp:539), [reduction](../../hls/qwen_decoder_v9e/matrix_q8.hpp:86), [profile](../../hls/qwen_decoder_v9e/model_profile.hpp).

An easily missed interface detail is that the head resets its persistent maximum only when token_base equals zero. An arbitrary first interval expressed using its absolute token label can inherit a previous call's maximum. A reset enhancement would make the absolute-label interface convenient.

There is an existing-image experiment that avoids that dependency. For each exact allowed interval [s, s+n), split n into chunks of at most 8,192, use page=head_offset+s*1088, rows=n and token_base=0. Each command resets the reduction and returns a local winner j plus its logit. The host converts the winner to s+j and combines interval winners using the same larger-logit, lower-absolute-token-ID tie rule as the HLS. Finite FP32 values can be compared exactly on A53. This needs qualification for ties, signed zero and the defined nonfinite policy.

This proposal requires a host experiment and reference checks, and it issues the same underlying scalar head arithmetic. The page extent check alone does not bind a request to the intended output-head region, so the host must validate the actual interval against the manifest and vocabulary. The setup should perform final RMS normalization once, preserve the chosen hidden lane and reuse it across interval calls.

A mask's contiguous interval count and its admitted row fraction are independent. Sixteen intervals can contain almost the whole vocabulary. Conversely, a small allowed set may have thousands of isolated rows. Record allowed rows, interval count after 8,192-row splitting, bytes transferred, DDR burst efficiency, register calls, repeated activation quantization and host/parser time. A full dense fallback must preserve the exact allowed set. Merging intervals across disallowed holes requires a mask-aware reduction, since an illegal row could otherwise win.

## What 1.5–2.3× would require

Using Claude's own approximate 125 ms layer path and 44 ms dense head, eliminating every head read alone gives at most 169/125 = 1.35× decode speedup. The normal transformer step remains.

A planning model is

`T_new/N ≈ (1-f)*(125 + 44*r) + f*t_known + overhead`

where f is the fraction handled in known-token runs, r is the head fraction actually read at the remaining decisions and t_known is measured processing time per token within those runs. The model is approximate and context dependent. It must use the actual scheduling of the last processed token and the final generated token.

For illustration, assume f=0.30 and an optimistic t_known=22 ms from well-filled short prefill batches. With all remaining branch-head work eliminated, the predicted time is 94.1 ms/token, or 1.80× decode. If those known tokens occur as isolated single-token runs and cost about 125 ms each, the result is 1.35×. Under the optimistic 22 ms assumption, a 2.3× decode target requires about half the output tokens to lie in useful known-token runs, plus very sparse remaining heads and little overhead. Request wall speedup is smaller when unchanged prefill/startup/tool work is substantial.

Thus a forced fraction around 0.30 and p95 interval count below 16 are useful screening metrics, but they cannot establish the proposed upper speed range. Measure the full run-length distribution and token-weighted work. A syntax-constant string can permit multiple alternative tokenizations or whitespace choices. To promise identical IDs to ordinary masked greedy, emit only a token whose permitted set is a singleton, or prove an equivalent token-language rule.

## Recommended low-cost T1 gate

1. Freeze a scalar RC1 arithmetic reference plus grammar, tokenizer bytes, legal EOS rules, greedy ties and token budget. Compare constrained accuracy with the original task protocol separately.
2. Collect independent public schemas with enums, free strings, escaped Unicode, numeric fields, nested structures, differing key order and broad-vocabulary controls. Run a pinned existing grammar engine and validate its masks.
3. Profile every decision's legal row count, intervals and provably unique token runs. Predict end-to-end cost from measured RC1 phase costs. Select the dense/sparse crossover before the evaluation split.
4. In software/C simulation, compare scalar dense masked greedy against relative-range sparse selection and mixed known-token batches. Check each relevant layer's hidden bytes and retained BF16 KV bytes, exact generated IDs and grammar state. Include context/tile boundaries and near-tie head rows.
5. If the predicted useful gain survives, qualify a small host-only RC1 experiment under the normal board process. Compare dense constrained, sparse constrained, forcing-only, combined and a current resident A53 constrained implementation with the same task information. Report fresh and reused-prefix calls.

This gate does not require first implementing a batched vocabulary head or adding more hardware to a 96% occupied placement. A speculative extension would be a distinct experiment because verification, accepted lengths, model-state updates and head batching change the economics.

## Strongest direction after considering the gate

The gate is the preferred next structural research question if its protocol and isolation prerequisites can be met. Its current OOC result is useful feasibility evidence, with 3,456 LUTs or 2.95% of device LUT capacity and ideal stream input. The step-1 prose's “far below 1%” should be corrected. Its 88 ns is processing after the received frame's final byte. A store-and-forward bridge needs approximately 12.1 microseconds to receive an ordinary maximum Ethernet frame at 1 Gb/s, plus forwarding and queue effects. Define whether the proposed 10 microsecond bound measures ingress-to-egress start, added latency relative to a wire, or post-frame decision.

Two independent 1 Gb/s receive ports can finish frames simultaneously. Their per-port interframe gaps supply no global arbitration gap. The bridge needs an explicit concurrent-arrival queue and service bound. A four-entry transaction-ID table and passive learned state need scoped behavior for stale observations, reconnects, retransmissions and transaction-ID reuse. These are substantive systems questions that could justify the hardware and replay contract.

The research claim should compare identical stateful policies across a host, an independent MCU and the PL/R5 path, using an independent endpoint/parser and plant scenario. FPGA enforcement matters only if root on the PS cannot alter the egress, configuration, state or approvals after deployment. The current RC1 boot/overlay path and offline gate prove no such root-resistance property.

My current ranking is gate protocol consistency and enforceable isolation first, a short host-only T1 gate as a bounded optimization opportunity, then fault/recovery characterization if it exposes a real boundary improvement. The available evidence does not justify numerical publication probabilities.

## Further source check by the coordinating reviewer

SILK's full text describes verification after untrusted DRAM, DMA and prefetch logic, immediately before its trusted compute buffer. Its statement that a verified byte may be reused without another check applies to reuse inside that trusted region. It is stronger than a model-load-only hash. A wide weight-authentication engine would need a distinct contribution in cost, traffic, arithmetic preservation or integration. It should compare the same protected boundary and forgery model, with address/version binding, keys and withheld output included. The reported one-byte-per-cycle design also discusses widening. [SILK §§3, 4.1, 4.8–4.9 and 5.5](https://arxiv.org/html/2608.26402)

The new preprint *The Blind Spots of Detection* attacks activation-watchdog tolerances by steering EOS while evading or confusing attribution. This directly overlaps the proposed experiment of finding damaging perturbations that approximate verification accepts. Full exact replay can still be an engineering comparator, but the attack idea is already public. A cryptographic hash of a claimed activation proves equality only after a trusted reference recomputes that activation, or after the execution is bound to a trusted attester. [Preprint](https://arxiv.org/abs/2611.01097)
