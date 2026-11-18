# Separate typed200_predecode candidate

Parent: frozen typed200_stage_clamp. Only encoder_layer and ADD_SKIP change.
Encoder_layer predecodes signed26 rounding bias on exactly the instruction word0
capture edge that stores shift bits101:96. The cached bias is a function of the
current stored shift, not a cached live permission. Like the instruction bank,
it has no reset; word0 must be captured before dispatch. ADD_SKIP consumes it
before the unchanged arithmetic shift and first clamp at the existing L+2 edge.
No request or arithmetic cycle added; exact26bit overflow and zero-shift behavior.
Requires actual-source sequencer/cache invariant and dispatch freshness proof,
whole-engine equivalence under the discharged bias relation, independent parent
arithmetic regression and all-stage matched timing against profile_cache.
No arbitrary untrusted-bias standalone equivalence or hardware/WCET claim.
All prior candidates, qualified package/recovery and numerical baselines frozen.
