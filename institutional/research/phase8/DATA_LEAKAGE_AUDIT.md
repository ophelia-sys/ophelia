# DATA LEAKAGE AUDIT

Strict causality tests are required to ensure no future information leaks into feature computation or normalization.

## 1. Rolling Window Causality
Features computing over a lookback window $W$ (e.g., `calculate_realized_volatility(df, window=20)`) at index $T$ must exclusively use data where $index \le T$.
- **Test:** Verify that shifting a single value at $T+1$ does not alter the output at $T$.

## 2. Normalization Causality
The historical dataset will inevitably contain large macro regimes (e.g., bull runs, crashes).
- **Prohibited:** Computing a global Z-score `(x - global_mean) / global_std`. This leaks future volatility into past timestamps.
- **Mandated:** Use causal rolling normalizations: `calculate_robust_z_score(df, window=500)` or `calculate_rolling_percentile(df, window=500)`.

## 3. Train/Validation/Test Split Leakage
- Any scaler or calibration model fit on the `Train` split must be frozen and applied to `Validation` and `OOS Test`.
- If an expanding window approach is used, the scaling state must only expand strictly temporally.

## 4. Barrier Labeling Leakage
- When defining entry conditions for Triple-Barrier labeling, the `Entry Price` must be exactly the `Close` price of the candle at $T$ (where features were computed).
- The forward search for the barrier hit starts at $T+1$ (the next candle).
