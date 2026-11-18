# Experimental attention width and score-distance mapping

The existing ATTENTION_LANES parameter counts parallel query tokens, not heads.
A private KR260 wrapper selects 16 query lanes while keeping TILE_OUT32 and
MAX_HIDDEN1024. All 32 frozen model cases and six partial-tile cases remain
bit-exact. Their encoder cycle changes range from0% to+5.32013%; the additional
H1024/head32 fixture changes0% to+2.39688% across1/3/12/128tokens. This is a
measured simulation scheduling tradeoff, not a hardware speedup. Default Nexys
proof was reused only after byte-identical default dependency hash validation.

The separate score-distance prototype preserves e_distance FFs in fabric to
avoid their absorption into the exponential-product DSP AREG. Pipeline equations
and cycles are unchanged. Actual BRAM/subtract/32DSP composition gained0.698ns
estimated slack at3.333ns for+704fabricFF, unchanged704LUT/10BRAM/32DSP. Eleven
focused engine control/address/MAC/output profiles passed. Whole-engine resource
comparison of32 lanes/default distance mapping versus16 lanes/fabric distance is
running in attention16-distance-ooc; inspect existing controller before action.

Do not integrate until full engine inference/resource/timing and numerical/cycle
tradeoff review pass. Public integration should add default-off
FABRIC_SCORE_DISTANCE and expose ATTENTION_LANES=TILE_OUT through KR260 wrapper
and testbench while preserving existing encoder_system/layer defaults. Use a
separate exact candidate/app/feature schema for16querylanes+fabric distance;
partial or stale words must be rejected before DDR mapping. A new production
parameterized full-hierarchy regression, explicit default proof and source/fixture
hashes are required before another full build. Do not reuse the old0x53597fff
feature word for a packaged variant. Private copies still report that old word.

Verify exponential DSP AREG0/PREG1 and22*16=352externaldistanceFF, all probability
DSP input/PREG stages, narrowed query/accumulator controls and actual memory cost.
Do not expect prior32lane inventory counts on this changed architecture. Require
positive resource relief and measured new placement timing/congestion, with the
same0.5ns setup admission and final legal positive routed setup/hold. Preserve
all five rejected candidates and the qualified125MHz app/recovery/bootreservation.
