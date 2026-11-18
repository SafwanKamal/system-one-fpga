# Carry-save typed row-range candidate

Parent: sealed typed200_predecode, independent from the direct-sum attempt.
Only typed_intent_axil changes. Explicit raw high-bit rejection and carry-save
first+count+~tokens compare; preserve both carries above bit7. No new state/cycle.
Requires actual-source all-raw-input and full endpoint proofs, independent full
regression and matched overall/shape timing gain before synthesis and placement.
No live permission cached; no hardware or timing-guarantee claim.
