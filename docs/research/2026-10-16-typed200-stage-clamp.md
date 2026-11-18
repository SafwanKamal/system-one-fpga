# First saturation moved into the existing rounding stage

Separate candidate `rtl/v2/candidates/typed200_stage_clamp` starts from frozen
`typed200_profile_cache`, not the rejected Boolean-clamp sibling. Only ADD_SKIP
changes. The existing L+2 register now stores signed INT16 saturated skip rather
than signed INT26 rounded skip. The rounding expression retains exact26-bit
finite-width overflow and all64 shift encodings before saturation. The output
stage retains the original signed17-bit residual addition and final asymmetric
[-32767,32767] clamp. No stage, valid/address/control/reset or external cycle
is added. `skip_clamped` is renamed to avoid assuming equal raw register meaning.

## Formal evidence

`build/v2/typed200-stage-clamp-formal-v1/receipt.json` passes:

- Actual-source arithmetic equality for all26-bit product values, all64 shift
  encodings and all16-bit residuals, including finite-width rounding overflow.
- **886 full-engine equivalence points / zero unproven**, with explicit proof-only
  observation of the relation
  `new.skip_clamped[e] == clamp32767(old.rounded[e])` on the same L+2 edge.
  Proof copies expose that relationship; candidate ports are unchanged.

Assumptions are one sampled clock, two-state semantics and corresponding initial
state, with the changed stage initially related by the stated clamp relation.
There are no protocol, shape, multiplier, shift or data constraints. Original
unreset datapath state is not an analog reset guarantee. Default tested formal
parameters are READ_LATENCY=3, MAX_TOKENS=128, BUFFER_ADDRESS_WIDTH=14. Both
actual source hashes and all proof copies/logs are recorded. Formal does not
establish physical timing or target WCET.

## Both-stage probe and full regression

`check_typed200_stage_clamp_ooc.py` compares full engines using identical input
register shells at5ns. These shell registers model upstream instruction/data
launch points, including shift/multiplier controls; they are not candidate
pipeline additions. This improves the probe boundary over the earlier standalone
engine probe, which lacked registered incoming controls. Compare this candidate
with its matched new control, not with earlier differently bounded OOC numbers.

The probe reports register-to-rounding-stage and clamped-stage-to-output paths,
plus full probe worst setup, logic/carry structure and resources. Board clock
skew, final placement and routing remain separate evidence. Overall mapped gain
must be at least0.050ns before full physical spending; the existing+0.500ns
full-placement routing gate is unchanged.

The independent full-model runner copies and renames the frozen parent
ADD_SKIP and encoder_layer on the reference side, retaining exact AXI/output/
busy/done/raw-counter comparisons and all normal/fault scenarios. It runs once
under `typed200-stage-clamp-integration-v1`.

One local foreground pipeline waits for that existing regression and probe,
then either records a held decision or runs full synthesis/source-clock review,
placement/native audit and, only after the preserved margin gate passes,
timing-only routing/review. It creates no bitstream/package, programs no board
and creates no recurring automation. An initial helper-generation assertion
expected close_project where the preserved audit actually uses close_design;
the preparation failure/generator were preserved and resumed by checking
identical already-written files. No native job or RTL was changed by that repair.

## Completed both-stage result: reject the direct stage move

The [probe receipt](../../build/v2/typed200-stage-clamp-ooc-v1/receipt.json)
shows that moving the first clamp improves the output stage but worsens the
rounding stage enough to make the engine slower overall. **Do not promote this
candidate or spend a full synthesis/placement run on it.**

| Matched registered-input 5 ns probe | Parent | Stage move | Delta |
|---|---:|---:|---:|
| Rounding-stage slack, ns | +2.159 | +1.259 | **-0.900** |
| Rounding-stage data delay, ns | 2.838 | 3.738 | +0.900 |
| Rounding-stage levels / CARRY8 | 10 / 4 | 13 / 6 | +3 / +2 |
| Output-stage slack, ns | +1.872 | +2.840 | **+0.968** |
| Output-stage data delay, ns | 2.964 | 1.996 | -0.968 |
| Output-stage levels / CARRY8 | 10 / 6 | 7 / 4 | -3 / -2 |
| Whole-probe worst setup slack, ns | +1.872 | +1.259 | **-0.613** |
| Stage flip-flops | 208 | 128 | -80 |
| Whole-probe LUT / FF | 2,866 / 1,177 | 2,938 / 1,096 | +72 / -81 |
| Whole-probe CARRY8 cells | 192 | 192 | 0 |

The [new rounding path](../../build/v2/typed200-stage-clamp-ooc-v1/stage/rounding-stage-paths.rpt)
starts at `in_shift_reg[3]` and ends at `engine/skip_clamped_reg[0][0]/D`:
3.738 ns data = 1.691 ns logic + 2.047 ns estimated wire, 13 levels and six
CARRY8s. The matched parent rounding path also starts at shift bit3 but takes
2.838 ns with 1.338 ns logic / 1.500 ns estimated wire. This is direct evidence
that the original rounding-stage spare margin was insufficient for this clamp.

The [improved output path](../../build/v2/typed200-stage-clamp-ooc-v1/stage/output-stage-paths.rpt)
is clamped skip bit0 to output bit0/S: 1.996 ns = 0.954 ns logic + 1.042 ns
estimated wire. Its gain does not compensate for the other stage. Both-stage
measurement prevents claiming the output-stage improvement as whole-design gain.

The full independent regression **completed successfully**: **5,400 golden words,
14 paired completions and14 launches**, including normal T1/2/3/4/5/12/64/128,
delayed B, early proposal, B/R errors, timeout/late response, stale-session and
shape cases. Every sampled raw counter and output/AXI/busy/done cycle matches.
T128 retains7,961,537 encoder cycles /7,966,029 request cycles and emulated
publication age7,966,096. Simulation took443.939s after120.786s compilation;
these host runtimes are not target latency or WCET evidence.

The single pipeline completed with `physical_build_admitted=false`; no full
physical directory exists. Prepared full-flow helpers were not executed natively
and have syntax checks only. No full physical job, bitstream, package or board
I/O occurred. The original probe and physical margin gates were not relaxed.

Final immutable `2026-10-16-typed200-stage-clamp-validation.json` binds actual
sources, proof886points, independent regression and actual staged-input rehash,
both-stage probe/checkpoints, held pipeline decision, preparation failure,
this report and the conditional MVP-readiness note, after checking every prior
sealed artifact. HANDOFF files remain editable. Candidate/helper/report/evidence
files in that record are frozen; do not amend a completed experiment in place.

## Next architectural decision

A plausible next zero-cycle experiment is **instruction-local predecoding** of
the shift/rounding controls before the existing data stages. The
[actual sequencer](../../rtl/v2/candidates/typed200_profile_cache/encoder/encoder_layer.sv)
writes instruction_reg only in FETCH_RECEIVE, dispatches ADD_SKIP, then stays in
EXECUTE until engine_done; ADD_SKIP shift is instruction bits[101:96]. That is a
potential stable-control window, not yet a complete compositional proof.

A predecode candidate must prove that its captured controls represent the
instruction used by every valid output, including reset/abort/next-instruction
boundaries. It cannot claim arbitrary changing-shift standalone engine equivalence
if it relies on instruction stability. Prove the sequencer/engine composition or
an explicitly discharged stability property, and distinguish invalid datapath
cycles from externally observable writes. No live deadline/quiet/error/identity
permission may be cached. Probe the predecode and all arithmetic stages together;
no improvement is assumed here. This refinement is not implemented in this task.

If same-cycle retiming cannot balance the cones, an extra arithmetic stage is a
different candidate with explicitly changed valid/address/done/counts and new
native/deadline budgets. Do not silently relax the unchanged-cycle requirement.
The qualified200MHz baseline and all previous sealed artifacts remain frozen.

## MVP planning

The [MVP readiness record](2026-10-16-typed200-mvp-readiness.md) gives a conditional,
low-confidence planning estimate of5–10 focused engineering days for a supervised
board MVP. Typed image closure, R5 startup, ownership, target numerics/fault tests
and a recoverable client demo remain. Useful-success WCET and externally
delivered wall time are stronger, currently unbounded claims; neither is inferred
from this local timing experiment or the diagnostic ELF.
