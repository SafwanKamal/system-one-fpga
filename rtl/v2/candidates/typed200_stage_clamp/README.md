# Separate typed200_stage_clamp candidate

Parent: frozen typed200_profile_cache; only ADD_SKIP changes. The first clamp
moves before the existing L+2 register; the stored state is now INT16 saturated
skip rather than INT26 rounded skip. The exact finite-width INT26 rounding and
shift are preserved before saturation. Residual INT17 addition/final clamp,
all control/address/valid/reset and external cycle boundaries are unchanged.
The new register is renamed because its state meaning differs. Proof must
establish skip_clamped == clamp(old.rounded), not equality of raw state.
Requires both-stage timing probes and independent parent arithmetic regression.
No qualification or deployment. All parents/baselines/packages stay frozen.
