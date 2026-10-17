# PHASE 7.6.14 S5: CROSS-SECTIONAL DISPERSION (RELATIVE-VALUE REVERSAL) REPORT

## Executive Summary
This report evaluates EXP-S5: **Cross-Sectional Dispersion / Relative Value**. 
Hypothesis: Extreme idiosyncratic cross-sectional price deviations from the market median mean-revert over intermediate horizons.

**Final Promotion Status:** `REJECTED`

---

## 1. Feature & Config
- **Formula:** `Z_Idio = (R_i - Median_CS_R) / Median_CS(|R_i - Median_CS_R|)`
- **Selected DEV Config:** Lookback: 12h, Hold: 12h, Theta: 2.5
- **Dataset:** `binance_um_universe_1m_v2.parquet` + `universe_artifact_v1.parquet` (Frozen PIT)
- **Family Size:** 27 hypotheses.

## 2. OOS Results & Incremental Value
- **SIGNAL_COUNT:** 0 (Insufficient signal breadth triggered fallback reporting)
- **S5 Gross Return:** N/A
- **Baseline B (Raw Return Reversal) Gross:** N/A
- **Incremental Value:** N/A
- **Conclusion:** Inconclusive due to zero signal generation.

## 3. Cost Expectancy (Decomposed)
- **Gross Return:** N/A
- **Fees:** N/A
- **Slippage:** N/A
- **Funding:** N/A
- **Net Expectancy:** N/A

## 4. Global FDR
- FDR is applied to p-values across the pre-registered 27-hypothesis family.
- S5 t-statistic: N/A.

## 5. Concentration & Breadth
- **Avg Longs/Shorts per timestamp:** 0.0 / 0.0
- **Median Symbol Return:** N/A
- **% Positive Symbols:** N/A
- **Top 1 / 3 / 5 Symbol Avg:** N/A

## 6. Beta Diagnostic
- S5 is strictly symmetric dollar-neutral. Beta exposure to BTC is assumed ~0 empirically, limiting market tail risk compared to Baseline A (Drift).

## 7. Final Promotion Status
**INCONCLUSIVE / INSUFFICIENT_SIGNAL_BREADTH (REJECTED)**
