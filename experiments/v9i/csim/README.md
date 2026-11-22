# v9i decode C-sim and synthesis evidence

The prior decode C-sim was stopped at its 90-minute cap. It produced no
completed v9h/v9i exactness comparison. The v9h driver logged positions
0 through 15 before the launcher exited at 5,094.173 seconds with status
4294967295. The v9i decode leg did not start. Claude?s batch-8 prefill C-sim
supersedes it because batch-8 prefill exercises the multi-pass P=2 attention
schedule. See [prefill exactness](../exactness.md).

The decode audit compares `build/v2/v9i/src` with v9h at
`build/v2/dual-port-study/src-s2`. It uses Gemini's testbench and raw-word
comparator with the Qwen3-0.6B Q8_0 model and the schedule-invariance fixtures.
The dual-port call passes the same model buffer to `model` and `model_b`.

The test starts with a NaN-poisoned K/V cache and exercises positions 0–23
in single-token decode mode across all 28 layers, with tile crossing disabled.
The token and logit fields contain the winner and its FP32 bits over the first
8,192 vocabulary rows, as configured by Gemini's harness.

## HLS synthesis

Vitis HLS 2025.2 completed `csynth_design` in 222 seconds in Claude's v9i
routed build from coordinator run 2d94b549f8e6. The values below were
confirmed directly from that build?s XML reports and console log. The synthesis source matches
`build/v2/v9i/src` byte for byte. The configuration used top `qwen_decoder`,
part `xck26-sfvc784-2LV-c`, an 8 ns target clock, 1 ns clock uncertainty,
and `config_compile -pipeline_loops 0`.

| Scope | LUT | FF | DSP | BRAM_18K |
| --- | ---: | ---: | ---: | ---: |
| Total | 138,765 | 238,179 | 666 | 234 |
| Attention | 27,499 | 27,795 | 135 | 12 |
| Matvec | 63,447 | 179,512 | 396 | 0 |

The [synthesis verdict](csynth-verdict.json) records the source hash and hashes
of the Tcl, Vitis log, and three XML reports. The original build reports are under
`build/v2/v9i/impl/hls/solution/syn/report/`, with the Tcl and console log
under `build/v2/v9i/impl/`.

## Reproduce

From the assigned worktree, point `$source` at the source checkout containing
the model, fixtures and generated decoder sources. Use the Gemini harness
published under `experiments/attn_reclaim/audit`. This run used the preserved
copy at `$source/build/v2/attn-reclaim/gemini-preserved/experiments/attn_reclaim/audit`.

```powershell
$harness = "$source/build/v2/attn-reclaim/gemini-preserved/experiments/attn_reclaim/audit"
python experiments/v9i/csim/run.py decode --source $source --harness $harness --drive T
python experiments/v9i/csim/run.py csynth --source $source --harness $harness --drive T
```

Use a free drive letter. Each command prints its scratch checkout and puts
logs, reports or completed dumps, and a verdict under `build/v2/v9i/csim/`
inside it. Decode uses fresh runs for both sources and a 90-minute wall clock
limit per Vitis process tree, including build time. The C-sim wall times include
compiler and launcher overhead. The verdict records the testbench's loop time
for completed runs and the logged positions for a timeout.
