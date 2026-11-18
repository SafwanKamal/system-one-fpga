# Measured dot7 L12 memory and scheduling profile

350 frozen cases, live clock 124999999 Hz. Report SHA256 `0428840b95911a1b01d4fc444a3daffe42ee595d66a868ef9dcae4671369faca`.

| Tokens | Cases | Mean request ms | Observed max ms | Read MB/request | Weight-wait cycles/request cycles | Read backpressure | MAC issue cycles/request cycles |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1–8 | 44 | 11.859 | 11.993 | 21.670 | 0.696 | 0.002 | 0.195 |
| 9–16 | 116 | 12.493 | 12.926 | 21.674 | 0.517 | 0.002 | 0.331 |
| 17–32 | 77 | 13.817 | 15.407 | 21.683 | 0.211 | 0.006 | 0.564 |
| 33–64 | 81 | 21.902 | 29.695 | 21.701 | 0.004 | 0.231 | 0.728 |
| 65–128 | 32 | 38.718 | 58.022 | 21.728 | 0.001 | 0.435 | 0.738 |

Across the suite, mean request time is17.280ms, effective reads1.255GB/s,
weight-wait0.222cycles/request-cycle, read-backpressure0.159, AXIservice-wait0.00693,
and MACissues0.560. Ratios overlap and are not partitions or causal attribution.

The existing linear engine requests up to two output tiles ahead, loads two
weight banks, and reuses each16×32weight tile across every token. For short
chains, loading32beats per tile can dominate a short token pass. For longer
chains, compute consumes more cycles while the next tile loads. Deeper buffering
may absorb service variation but cannot by itself increase sustained DDR beat
rate. Investigate measured loader starvation/occupancy and request gaps before
spending area on more banks. Read-backpressure can also be intentional when
both weight banks are full. No production RTL was changed.

Next evidence needed: matched candidate hardware counters after200MHz closure,
per-token repeat measurements and loader-bank occupancy/request-gap instrumentation.
Any new instrumentation must be isolated and simulated before a frozen build.
A model/context timing guarantee also requires bounded DDR arbitration, MMIO
response and scheduling; these observed maxima do not establish a hard bound.
