# PHASE 6.4 - P6 PRE-EXECUTION CAUSALITY AUDIT

## Purpose
Ensure that the P6 (Funding / Positioning Pressure) feature logic strictly adheres to causal boundaries before running the LightGBM OOS test.

## Component Verification

1. **Source Data Timestamping:**
   - The raw Binance funding endpoints expose `calc_time` and `fundingTime` corresponding to the *exact moment of settlement*.
   - These are mapped to a `funding_time` variable that acts as the availability barrier.

2. **Alignment Strategy (LAST-KNOWN-AVAILABLE):**
   - We enforce a `merge_asof` matching `decision_time` to `funding_time` looking *backward*.
   - If `decision_time` = 08:05, and `funding_time` = 08:00, it selects the 08:00 value.
   - If `decision_time` = 07:55, it strictly selects the 00:00 value.
   - **Conclusion:** Zero possibility of future funding rate leakage.

3. **Normalization Windows:**
   - `funding_rate_zscore_1d` uses a strictly trailing 24-hour (288-period) rolling window.
   - `funding_rate_change_8h` uses a strict `.shift(96)`.

## Regression Test Suite
- `test_phase6_4_p6_data.py`: Validated monotonic timestamps and column presence.
- `test_phase6_4_p6_causality.py`: Forward perturbation test verified that future modification of inputs mathematically cannot alter past feature values.

## Final Approval
All causality constraints passed. P6 is cleared for the ML pipeline.
STATUS: APPROVED
