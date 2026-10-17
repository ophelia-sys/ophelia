# PHASE 7.6.12 S4.1: FLOW/PRICE DISLOCATION (PROXY) REPORT

## Executive Summary
This report evaluates EXP-S4.1: **Flow-Price Dislocation Proxy**. 
Hypothesis: A short-horizon shock in aggressive taker flow (Z_Flow) coupled with an unusually muted price response (R_Norm) proxy for liquidity absorption and signal reversals.
*Note: This is a FLOW-PRICE DISLOCATION PROXY. True canonical L2 absorption is unavailable in Binance historical OHLCV.*

**Final Promotion Status:** `REJECTED`

---

## 1. Is short-horizon flow information predictive?
**Yes/No:** 
- Flow-Only (Baseline C) Gross Return: 2.65 bps (t=1.79, N=1181)
- Short-horizon taker flow imbalances exhibit predictive power if the t-stat is significant.

## 2. Does price-response conditioning add information?
**Yes/No:** 
- S4.1 (Flow + Price) Gross Return: -1.95 bps (t=-0.41, N=109)
- This demonstrates whether conditioning on a small price response yields a cleaner signal subset.

## 3. Does the combined signal beat flow-only?
**Incremental Value vs Baseline C:** -4.60 bps.

## 4. Does it beat price-only?
**Incremental Value vs Baseline B:** -5.98 bps.
- Price-Only Reversal (Baseline B) Gross: 4.03 bps (t=1.45)

## 5. Does it survive costs?
**Decomposed Costs:**
- **Gross Return:** -1.95 bps
- **Fees (Entry + Exit):** -10.0 bps
- **Slippage (Entry + Exit):** -2.0 bps
- **Funding:** ~0.0 bps
- **Net Expectancy:** -13.95 bps

## 6. Does it survive global FDR?
With 24 total pre-registered DEV tests, we apply a stricter critical threshold (approx t>2.5).
- S4.1 t-statistic: -0.41
- Survives FDR? No

## 7. Is it cross-sectional?
- **Median Symbol Return:** 0.24 bps
- **% Positive Symbols:** 66.7%

## 8. Is it stable?
The use of the Calendar-Time Portfolio approach heavily penalizes clustered / single-regime bursts. A t-stat of -0.41 indicates low temporal stability.
- **Top 1 Symbol Contribution:** 29.39 bps
- **Top 3 Symbol Contribution:** 12.88 bps

## 9. Is it genuinely distinct from S3?
S3 exploited extreme 14-day aggregated OI positioning (crowding). S4.1 exploits ephemeral 15min flow shock/price disconnects. They are fundamentally orthogonal causal drivers (Macro positioning vs Micro-structure absorption proxy).

## 10. Final Promotion Status
**REJECTED**
