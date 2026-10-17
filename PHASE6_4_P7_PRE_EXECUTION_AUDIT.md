# PHASE 6.4 - P7 PRE-EXECUTION CAUSALITY AUDIT

## Purpose
Ensure that the P7 (OHLCV-Derived Volume Acceptance) feature logic strictly adheres to causal boundaries before running the LightGBM OOS test.

## Component Verification

1. **Source Data Constraints:**
   - Features rely entirely on `close` and `volume` native to the standard 5m OHLCV grid.
   - By definition, the 5m candle data for `[t, t+5m)` is available precisely at `t+5m` (the `decision_time`).

2. **Algorithmic Dependencies:**
   - `price_to_vwap_8h` & `1d` use trailing `rolling.sum()` over 96 and 288 periods.
   - `volume_concentration_1d` uses trailing `rolling.mean()`.
   - `value_area_proxy` computes standard deviation using exclusively historical trailing data.

3. **Missing Data & Zero Denominators:**
   - If volume is zero for 24 hours, mathematical division by zero is handled safely (returning 0.0 or 1.0 depending on semantic context).
   - `NaN` propagation is contained.

## Regression Test Suite
- `test_phase6_4_p7_data.py`: Verified zero-volume boundary handling behaves gracefully.
- `test_phase6_4_p7_causality.py`: Forward perturbation test verified that altering a candle at `T` does not affect any output at `T-1`.

## Final Approval
All causality constraints passed. P7 is strictly causal and cleared for the ML pipeline.
STATUS: APPROVED
