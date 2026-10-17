# PHASE 6.5 DATA REQUIREMENTS CHECKPOINT

## 2024 Blind Confirmation Objective
Evaluate P4 and P7 out-of-sample on 2024 data.

### Signal Window
`2024-01-01 00:00:00 UTC` through `2024-12-31 23:55:00 UTC`

### Label Support Requirements
To support `target_60_up_10` (a 60-bar forward horizon) for the final 2024 signal, market data must be continuously available until at least `2025-01-01 04:55:00 UTC`.

### Historical Padding Requirements (2023 Data)
Do NOT count padding observations as 2024 test observations.
Padding must be loaded from exactly `< 2024-01-01 00:00:00 UTC` to preserve causality.

- **P4 Padding:** Requires a strict 288-bar (24h) causal history. This requires 288 previous observations from 2023 to evaluate the `2024-01-01 00:00:00 UTC` bar.
- **P7 Padding:** VWAP_1d requires exactly 288 bars (24h) of history.
- **BASE Padding:** Requires 20 bars (100m) for `realized_vol_20`.
- **CVD Padding:** Requires up to 12 bars (1h) for `cvd_zscore_1h`.
