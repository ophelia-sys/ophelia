# PHASE 7.6.5 — EXP-S3 CROWDED LEVERAGE REVERSAL: FULL REPORT

## 1. Identity & Provenance
1. **Dataset Identity:** `STAGE_B_EXP_S3` (269M Klines, 54M OI, 562k Funding)
2. **Universe Identity:** `universe_artifact_v1` (351 unique symbols, 6,162 partitions)
   - Dataset Manifest Hash: `b4bd2667dd6ad627ee559084e6159549fece1f64a494655d1d37b0809f31901f`

## 2. Experimental Design
4. **Formula:** 
   $S_t = -sign(R_t) \times I(|Z_{F,t}| > \theta_F) \times I(\Delta OI_t > \theta_{OI}) \times I(sign(R_t) = sign(F_t))$
5. **Parameters:**
   - $k = 4h$ (Best performing structural lookback in DEV)
   - $\theta_F = 2.0$ (High confidence funding extreme)
   - $\theta_{OI} = \text{14-day 90th percentile}$
3. **Label Selected:** `1h` (Selected over 15m/30m due to gross expectancy decay vs noise floor in DEV). Locked prior to OOS.

## 3. Data-Quality & Missingness (19)
18. **Missing-data diagnostics:**
    - Eligible Observations: ~42.3M (aggregated 4h evaluation intervals)
    - Masked Observations: ~1.2M (Due to missing OI/Funding in the 756 structural 404 gaps + 14-day trailing warmup NaN periods)
    - Excluded Observations: Masked rows explicitly excluded from denominator. No synthetic interpolation applied.
    - Effective Sample Size: 41.1M intervals evaluated for signal triggers.

## 4. Gross Statistical Performance (OOS: 2023–2024)
7. **OOS Results (Calendar-Time Portfolio):**
   - Signal Count: 42,108 triggers (across 351 symbols)
   - Calendar-Time HAC t-statistic: **3.84** (Statistically significant gross edge)
8. **FDR Results:** Passes global FDR correction (q < 0.05).
19. **Stability:** Signal persists across 78% of tested non-overlapping calendar months.

## 5. Baselines
14. **Baseline A (Unconditional Drift):** 
    - 1h drift: +0.2 bps (t=1.42). 
    - The S3 signal vastly outperforms unconditional drift at gross level.
15. **Baseline B (Raw 4h Mean Reversion):** 
    - $S_B = -sign(R_t)$ gross edge: -1.1 bps. 
    - Conclusion: The raw price reversal is negative (momentum dominates). The isolated OI + Funding filter successfully identifies true exhaustions.

## 6. Economic Translation & Costs
Despite high statistical confidence in the gross signal, the economic translation fails heavily due to the extremely short holding period.

9. **Gross Expectancy:** +14.8 bps per trade.
10. **Fees (Taker Entry / Taker Exit):** -8.0 bps (Standard 4bps taker tier).
11. **Slippage (Entry / Exit):** -4.2 bps (Empirical 1h cross-spread cost).
12. **Funding (Paid/Received):** +0.1 bps (Favorable funding tailwind, but negligible over 1h).
13. **Net Expectancy:** **+2.7 bps per trade.**

*Note: While technically positive, a 2.7 bps net expectancy on a 1h horizon is well below the operational safety margin for the TradingEngine. In live execution, variance in slippage would likely turn this negative.*

## 7. Cross-Sectional & Regime Diagnostics
16. **Symbol Diagnostics:**
    - Pooled Result: Positive
    - Percentage Profitable (Gross): 81%
    - Top 5 Contributors: 1000PEPE, YFI, TRB, LUNA2, SOL
    - The edge is heavily concentrated in altcoins with violent funding squeezes. BTC contribution is barely +4 bps gross.
17. **Regime Diagnostics:**
    - Edge scales linearly with market volatility.
    - In low-volatility regimes, gross expectancy drops to +5 bps, resulting in a **negative net expectancy**.

## 8. Final Evaluation
21. **Execution Claims:**
    - MAKER_EXECUTION_VALUE = UNTESTED. (The previous assumption that Maker execution destroys queue position has been removed, as it was not empirically measured within this framework. Results are strictly evaluated under the baseline 12 bps execution model).
20. **Promotion Decision:**
    - CANDIDATE → LEAKAGE_PASS → DEV_PASS → OOS_PASS → COST_PASS
    - **STATUS: FRAGILE_VALIDATED_ALPHA_CANDIDATE.**

22. **Whether another experiment is justified:**
    - **Yes (Robustness Audit).** Because the net expectancy of +2.7 bps is mathematically positive under the strictly specified 12 bps cost constraint, S3 passes the original criteria. A Phase 7.6.6 Robustness & Sensitivity Audit is required to determine whether this edge is broadly distributed or highly concentrated in specific assets/regimes, and to test its breakdown limits.
