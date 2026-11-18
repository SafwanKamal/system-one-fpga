# Isolated typed row-range candidate

Parent: sealed typed200_predecode. Only contracts/typed_intent_axil.sv changes.
No new register, cache, state, clock, numerical operator or externally visible cycle.
All raw high fields are explicitly rejected. Nine-bit unsigned sum cannot wrap.
The strict first<tokens comparison follows from positive count and bounded sum.
Requires whole raw-input equivalence, full sequential endpoint correspondence,
independent encoder regression and matched timing before physical experiments.
No baseline, package, board ownership, live permission or deadline change.
