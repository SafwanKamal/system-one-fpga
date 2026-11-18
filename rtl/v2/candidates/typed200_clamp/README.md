# Separate typed200_clamp candidate

Parent: frozen typed200_profile_cache. Only ADD_SKIP clamp logic changes.
Explicit sign-extension/zero reductions implement both asymmetric signed
[-32767,32767] clamps. Product, finite-width rounding, shift, residual addition,
all registers, reset, valid/address/control and cycle boundaries are unchanged.
Requires whole-domain arithmetic proof, whole-engine correspondence, independent
parent arithmetic in full regression, and a matched mapped timing probe before
full physical work. No hardware or WCET qualification. Parent and qualified
sources, packages, recovery, numerical and evidence artifacts remain frozen.
