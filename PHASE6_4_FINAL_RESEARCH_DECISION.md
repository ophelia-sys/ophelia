# PHASE 6.4 - FINAL RESEARCH DECISION

## Execution Summary
Phase 6.4 tested two completely isolated and orthogonal feature families on the strictly out-of-sample 2022-2023 5m dataset.
- **P6 (Funding / Positioning Pressure):** Represents the market's positional bias (funding rate).
- **P7 (OHLCV-Derived Volume Acceptance):** Represents standard OHLCV volume concentration and proximity to historical volume-weighted means (VWAP value area proxies).

## Results Breakdown

### P6: Funding / Positioning Pressure
- **Pooled LogLoss Difference:** -0.00510 (Universal Degradation)
- **Diebold-Mariano Significance:** p = 0.0000 (Degradation is highly significant)
- **Symbol Analysis:** 6/6 symbols demonstrated statistically significant loss in predictive power when funding data was included.
- **Conclusion:** Introducing absolute positioning cost metrics into the LightGBM model actively confuses the feature space and hurts predictions.
- **FINAL STATUS:** **REJECTED**

### P7: OHLCV Volume Acceptance Proxies
- **Pooled LogLoss Difference:** +0.00215 (Significant Improvement)
- **Diebold-Mariano Significance:** p = 0.0000 (Improvement is highly significant)
- **Symbol Analysis:** 4/6 symbols show statistically significant independent improvements (DM p < 0.05) with 95% Bootstrap CIs strictly positive. The remaining 2 symbols (SOL, ADA) are neutral but not negative.
- **Conclusion:** Contextualizing raw trades (CVD) against standard Volume-Weighted distributions acts as a powerful structural anchor for the model.
- **FINAL STATUS:** **APPROVED / RESEARCH SURVIVOR**

## State of the Experiment

As of the conclusion of Phase 6.4, the confirmed **RESEARCH SURVIVORS** are:
1. P4 (Large Trade Proxies) - Awaiting 2024 Confirmation.
2. P7 (Volume Acceptance Proxies) - Awaiting 2024 Confirmation.

**CURRENT FROZEN BENCHMARK:** `BASE + CVD + LightGBM`

Both P4 and P7 represent the final surviving families of the 2022-2023 historical sweeps. They will be carried forward to the definitive 2024 unobserved confirmation test (Phase 6.5).
