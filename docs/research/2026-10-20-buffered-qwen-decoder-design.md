# Buffered Qwen FPGA decoder candidate

The 10-second MVP request continues from the sealed v6 27.430389467-second
cold-prefill command. This candidate keeps the Q8_0 model, FP32 arithmetic order,
62 prompt tokens, full 151936-entry head, four-token batches and typed output.
No prefix reuse or CPU model arithmetic is introduced.

The v7 hardware burst-loads attention/FFN normalization vectors and Q/K head
normalization vectors into local FPGA buffers once per decoder batch. Each token
loads its 512-byte RoPE table row once; all Q/K heads reuse it. Model vector reads
split at the owned 16 MiB DMA boundaries. Buffer sizes derive from the existing
model profile; runtime checks tensor alignment before launching NN commands.

In-place normalization reads/writes only element i in iteration i. RoPE iteration
(head,i) owns the pair {head*128+i, head*128+i+64}, for i in [0,63]. No pair overlaps
another iteration. Explicit HLS dependence declarations remove false pointer
recurrences without changing floating-point sums or their order. Real-weight
causal C simulation and one board fixture gate the single real command.

The new command runner overlaps vocabulary-only helper startup and complete
resident-weight SHA verification under the global inference lock. Both remain
inside the cold-call timer. All bytes are still checked on each command. Two native copy workers stage
uncached DMA reads into four bounded 4 MiB buffers; SHA consumes their bytes in
file order and checks the total extent. Mappings outlive every worker, including
exception cleanup. This copy/hash work is byte verification, not model math. The
command poll sleep is reduced from 500 to 50 microseconds to reduce completion
rounding across 1221 launches; this is host control work, not NN arithmetic. The
helper performs tokenization only; the FPGA performs every NN operation.

On arrival the board had already rebooted to Linux boot
e9728928-307d-485b-b40b-63fa29d9296d, with the starter image and no model DMA module.
The session restored the existing DMA module, the same source/resident SHA and
sealed v6 image while keeping this Linux boot running. Recovery evidence is in a
new directory; previous deployment proofs remain intact. The v6 timing comparison
therefore spans Linux boots and is not a same-boot controlled benchmark.

A static traffic calculation in traffic-bound.json explains the next limit.
The unchanged command streams all seven layer matrices for 868 layer passes
and projects 2430976 vocabulary rows. Even perfect utilization of the present
128-bit, 100 MHz weight interface puts matrix traffic alone above ten seconds.
These buffers and startup overlap advance the MVP, but reaching ten seconds for
the same workload also requires more weight bandwidth or fewer weight passes.
This is a theoretical bound, not a timing measurement or a larger-model fit claim.

Deployed: 18.928106882s cold-prefill real command; prefill 8.122159s, decode 7.417084s. Same prompt/generated IDs and full vocabulary; current Linux boot retained. Target10 not yet met. See build/v2/qwen-fpga-decoder-v7/{README.md,deployment-proof.json,seal.json}.
