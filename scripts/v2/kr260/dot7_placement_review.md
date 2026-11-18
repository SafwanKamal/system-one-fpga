# Dot7 H1024 placement review — October 13, 2026

All 53 frozen numerical cases, default/Nexys compatibility and synthesis
resource/fanout/pipeline/registered-URAM gates previously passed. Reverified
all 17 frozen source hashes. Placement completed without errors; reports are
Fully Placed estimates, not routed qualification.

| Clock MHz | Estimated setup slack ns |
|---:|---:|
| 125 | +2.921 |
| 150 | +1.588 |
| 200 | -0.079 |
| 250 | -1.079 |
| 300 | -1.746 |

Placed resources: 90278 LUTs, 64513 FF, 59 BRAM, 36 URAM, 610 DSP. Compared with
failed dot5 placement: LUTs 102217 -> 90278 (-11.7%), FF 112939 -> 64513 (-42.9%),
CLB sites 14609 -> 14374, leaving occupancy at 98.18%. Level-5 congestion remains
in attention/shared dot/linear regions. LUT relief has not eliminated routing
risk or site packing pressure. Highest fanout includes embedding beat-address
nets at 1391 loads and attention score/exponent RAM controls.

The actual 300MHz worst path is now linear accumulator BRAM -> lane selection
-> DSP operand input, 4.344ns data (1.742 logic, 2.602 estimated route), four
logic levels. See linear_drain_timing_review.md; embedding bias optimization
alone is insufficient. No production RTL change made during the frozen build.

Decision: One conservative 125MHz attempt after all 53 frozen numerical cases and synthesis/URAM/pipeline gates. Placed LUTs reduced 11.7% and registers 42.9% versus failed dot5, but CLB occupancy remains 98.18% and congestion level 5. Use 2.921ns placement margin instead of repeating the failed 150MHz strategy. Legal routing is uncertain; require fully routed positive setup/hold before export and hardware validation before replacement. 300MHz placed WNS is -1.746ns; no closure claim.

Native place_design summary reports CPU 1h04m20s, elapsed 2h31m45s. Script
stopwatch reports opt 192.811s and placement 8908.472s; retain both measurements
rather than treating them as interchangeable. Elapsed includes about two hours
of confirmed host Modern Standby, not two hours of active Vivado computation.
No package/deployment yet. Existing validated 125MHz app remains untouched.
The recorded route-review.json is tied to placement artifact SHA256 hashes.
