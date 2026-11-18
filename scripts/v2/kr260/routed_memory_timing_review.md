# Routed activation-memory bottleneck — October 13, 2026

Final dot7 timing at 125MHz is legally routed and passes setup +0.401ns and
hold +0.010ns. Its worst setup path changed from the placed linear drain path
to activation buffer 6 UltraRAM -> shared port_data_reg[0][71] replica.
Data delay is 7.250ns: logic 1.987ns, routing 5.263ns. Four logic levels include
three UltraRAM cascade arcs and one LUT6. This is actual routed evidence,
not an isolated timing estimate or a 300MHz qualification.

The reported path traverses URAM288_X0Y8..Y11 CAS_OUT_DOUT_A/CAS_IN_DOUT_A,
with zero reported net delay on the dedicated cascade links. The final DOUT_A
net has fanout24 and 5.167ns routed delay to the selection LUT near X29Y125.
That long shared output distribution is the dominant contribution; cascade
arithmetic alone is not the whole bottleneck. Synthesized OREG_A/OREG_B are
TRUE for all36 UltraRAM cells, but that inventory did not prove a short routed
path from the active cascade/output to every consuming port register.

Next investigation: inspect actual cascade/register topology and the physical
shared read-data mux/distribution. Compare local per-buffer fabric capture or
localized consumer replicas with an explicitly aligned extra read stage,
and consider bank/cascade layout only with measured inference/placement.
Do not assume a ram_style attribute or OREG count is enough for 300MHz.
Avoid duplicating full memory banks just to shorten routing; compare CLB-site
packing, enable/reset fanout, extra FFs and all dependent read latency/tags.
Current placed CLB occupancy98.18% makes packing as important as LUT totals.

Before integrating: prove masked-byte writes, read-during-write behavior,
deep-bank boundaries, all buffers/ports, stalls and engine read/tag alignment;
preserve default/Nexys behavior; then inspect isolated inference and numerical
regressions before another full grouped build. The linear selector and embedding
arithmetic prototypes are useful prerequisites, but neither by itself removes
this newly measured routed memory-distribution bottleneck. No production RTL
change or additional speedup is established by this review.
