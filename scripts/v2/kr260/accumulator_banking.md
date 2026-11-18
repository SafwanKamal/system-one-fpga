# Local accumulator controls: next congestion candidate

Batch2 synthesis identified attention `s_word[P]` bits with 35,329 loads each
and `s_v[P]` with 23,554 loads. Query write controls were already localized:
all 1,024 copies retained, sixteen loads each. The accumulator shared controls
therefore take priority before another full implementation.

Optional `LOCAL_ACCUMULATOR_CONTROLS=1` divides P.V storage into two-dimension
banks per attention lane. Each bank has its own registered read index, first-key
flag, decoded write enables and output index. The adders remain shared across
head words; replicating an adder per stored word would increase LUT pressure.

Read/write/first-key controls capture tags from P-1 alongside the existing P
pipeline registers. The output selector captures word_next alongside word_reg.
This preserves existing product/tag alignment and output-read latency. There
is no intentional extra arithmetic pipeline stage. Default zero preserves the
established accumulator path and Nexys profile. Capabilities bit4 identifies
the option, without changing BUILD capacity or the counter map.

Qualification includes existing H768 and trained L12 vectors, matched controls,
H1024/F4096 boundaries, Nexys intermediate/final outputs and independent one-word
head vectors (H768/A48/HD16, lengths1,2,3,31,33). The last cases cover consecutive
updates and partial query-lane groups. Evidence belongs in rtl-batch3-check;
frozen batch2/memory projects remain unchanged.

After simulation, batch3 synthesis captures actual local accumulator register
loads. Gate write/first-key loads at64 and local index loads at256, in addition
to query enables<=16, device fit and UltraRAM output registers. RTL attributes
are requests until those measurements confirm replication.

No routed timing or turnaround improvement is established yet. The global
sources feeding the local stage still have loads: inspect their fanout and the
remaining shared cones before deciding whether to implement. Synthesis-only
qualification does not automatically start placement or routing.
