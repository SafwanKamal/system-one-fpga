# Attention routing audit while synthesis runs

This is a source/netlist review queue, not a claim of improved routed timing.
Keep the current synthesis snapshot fixed until its fanout reports are ready.

## Measured failure addressed by batch2

The previous worst path ends at a query write clock enable. Its final decode
net has 128 loads and 10.860 ns routing delay, spanning widely separated slices.
The complete path has 12.263 ns routing out of 12.841 ns data-path delay.
Batch2 registers predecoded lane/word enables, uses static query destinations
and requests eight enable copies for each 128-bit word. Synthesis must confirm
sixteen loads per copy before implementation. Equivalent FF merging remains
an explicit gate, rather than assuming RTL attributes prove locality.

## Remaining shared cones to measure

| Signal/cone | Source-level consumers | Candidate action after measurement |
|---|---|---|
| `s_word[L]` query read selector | Query word selection for every MAC lane and byte | Local select copies captured from the preceding tag stage; maintain operand/tag alignment |
| `s_v[L]` score/value mode | Probability/query operand muxes across lanes and K/V muxes | Register local mode copies with operand/control tags; inspect physical replication |
| K/V word data | One shared 128-bit word broadcast across all MAC lanes | Reuse existing MAC operand registers; inspect placement before adding another stage |
| Partial sum word/last tags | Score accumulation and P.V update controls | Check fanout and timing before widening or adding local stages |
| Reset/query capture enables | New control FFs and existing data distribution | Inspect control-set count and actual reset fanout; avoid broad preserve constraints |

Global source fanout is not the sole metric: a modest-fanout decode can create a
long local net when its sinks are scattered. Review source-to-sink routing and
congestion regions alongside high-fanout reports. Blanket DONT_TOUCH constraints
can restrict useful optimization; apply targeted preservation only if merging
is measured and prevents the intended localization.

## Build-cost evidence

`analyze_build.py` writes `build-diagnostics.json` beside each build, including
major command wall/CPU times, routing share, peak memory, overlap counts,
congestion warnings, resources, clock sweep and critical setup path.

```powershell
.\.venv\Scripts\python.exe scripts/v2/kr260/analyze_build.py build/v2/kr260-opt-wide build/v2/kr260-opt-memory build/v2/kr260-opt-batch
```

Observed placement/routing respectively:

- Wide candidate: 19m31s / 23m45s.
- Memory candidate: 21m50s / 75m04s.
- First batch: 20m49s / 310m48s.

All three reported maximum congestion level 6. Therefore a level threshold
alone cannot determine whether a candidate will route quickly. Compare region
extent, overlap convergence, reuse rate and critical-net geometry. Stage sums
exclude report/startup overhead and are not total elapsed build estimates.

Do not add another RTL stage solely from this queue. Select it from actual
synthesis/placement evidence, test alignment independently, then include it
with the other qualified changes in the next implementation.
