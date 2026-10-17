# Phase 7.4 EXP-S1: Volatility-Scaled TSMOM Report

## Executive Summary
This report summarizes the empirical evaluation of the Phase 7.4 Slow Alpha Hypothesis S1: **Volatility-Scaled Time-Series Momentum (TSMOM)**. 

The hypothesis tested whether directional momentum (scaled by inverse volatility) provides sufficient predictive value to overcome standard taker execution costs. The experiment was conducted under the strict Phase 6.2 validation framework, utilizing a pre-registered parameter grid on DEV data, followed by strict Out-of-Sample (OOS) testing using a Calendar-Time Portfolio.

**Final Status:** `REJECTED`

---

## 1. Does S1 have statistically significant OOS predictive value?
**No.** During DEV label and parameter selection, the Information Coefficient (Spearman Rank Correlation) was uniformly **negative** across all pre-registered lookbacks (1h, 4h, 24h) and forward horizons (1h, 4h). Trend continuation momentum failed entirely. 

The least-negative parameter pair (1h lookback, 4h horizon) was carried into OOS testing. It generated an expected gross OOS return of **-1.03 bps** per trade with a non-overlapping $t$-statistic of **-1.30**.

## 2. Does it survive realistic costs?
**No.** Given a conservative round-trip execution cost estimate of 12.0 bps (incorporating standard Binance/BingX taker fees and slippage), the net expectancy is **-13.03 bps**. The strategy aggressively loses money.

## 3. Is the effect stable across symbols?
**No.** The signal exhibited significant cross-sectional inconsistency. While gross expectancies were marginally positive for BTC (+0.50 bps) and SOL (+0.39 bps), they were negative for BNB (-0.43 bps) and XRP (-0.17 bps). There is no universal cross-asset alpha.

## 4. Is it stable across time (Regime Analysis)?
**No.** The performance flipped depending on the volatility regime. 
- High 24h Volatility: +0.49 bps
- Low 24h Volatility: -0.72 bps
The lack of stability across volatility environments means the strategy fails the `STABILITY_PASS` gate.

## 5. Is it robust across reasonable pre-registered horizons?
**No.** The DEV parameter grid yielded universally negative ICs:
- 1h lookback, 1h horizon: IC -0.0084
- 1h lookback, 4h horizon: IC -0.0054 (Selected)
- 4h lookback, 1h horizon: IC -0.0094
- 4h lookback, 4h horizon: IC -0.0094
- 24h lookback, 1h horizon: IC -0.0155
- 24h lookback, 4h horizon: IC -0.0148

Momentum at these specific intraday horizons proved to be weakly mean-reverting rather than trending.

## 6. Does volatility scaling improve over raw momentum?
**No.** Because the core directional premise of the signal (trend continuation based on the sign of historical returns) is empirically false at these horizons, volatility scaling is mathematically moot. It scales a negative-expectancy signal.

## 7. Does it demonstrate incremental value over the appropriate baseline?
**No.** The feature has negative expected gross value and strongly negative expected net value. It adds zero predictive utility and degrades the portfolio.

## 8. What is its exact promotion status?
**REJECTED.**
The feature failed `DEV_PASS`, `OOS_PASS`, `COST_PASS`, and `STABILITY_PASS`. The feature registry has been updated to reflect this status. S1 will not proceed to execution or machine learning experiments.

---
*Following the mandatory stop conditions laid out in the Phase 7.4 research guidelines, no subsequent experiments (S2-S5) will be automatically started until explicit authorization is received.*
