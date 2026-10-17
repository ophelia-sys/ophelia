# Phase 7.4 EXP-S2: Beta-Adjusted Residual Momentum Report

## Executive Summary
This report summarizes the empirical evaluation of the Phase 7.4 Slow Alpha Hypothesis S2: **Beta-Adjusted Residual Momentum**.

The hypothesis tested whether removing BTC market beta from altcoin returns reveals idiosyncratic momentum not visible in raw time-series momentum. The experiment utilized a strict pre-registered trailing 24h covariance Beta window and evaluated the `RESEARCH_UNIVERSE` (ADA, BNB, ETH, SOL, XRP) against the `EXECUTION_UNIVERSE` (BNB, ETH, SOL, XRP).

**Final Status:** `REJECTED` (Directional) / `INCONCLUSIVE` (Market-Neutral)

---

## 1. Does residual momentum have OOS predictive value?
**Marginally, but not significantly.** In the Out-of-Sample (OOS) period, the chosen configuration (24h lookback predicting 4h forward returns) generated a positive gross expectancy of **+2.16 bps** per trade. However, the non-overlapping $t$-statistic was only **1.08**, failing the standard threshold for statistical significance.

## 2. Does it outperform raw momentum?
**Yes.** Baseline A (Raw Time-Series Momentum) generated a negative gross return of **-1.58 bps**. Applying the Beta adjustment improved the gross signal by nearly 4 bps, indicating that extracting BTC beta does filter out confounding market-wide noise. 

However, it heavily underperformed Baseline B (Market Drift), which generated **+4.79 bps** (t=1.78) simply by maintaining a constant long exposure.

## 3. Does it survive realistic costs?
**No.** Given a conservative directional round-trip execution cost estimate of 12.0 bps, the net expectancy is **-9.84 bps**. The strategy fails the `COST_PASS` gate.

## 4. Does it work across multiple symbols?
While the pooled Calendar-Time return was positive (+2.16 bps), the universe size was too small to claim broad cross-asset universality.

## 5. Does it work across time (Regime Analysis)?
It demonstrated mild stability across volatility regimes, generating +0.93 bps in High Volatility and +2.05 bps in Low Volatility environments. 

## 6. Does beta adjustment add incremental information?
**Yes.** The Beta adjustment successfully flipped the signal from negative expectancy (Raw Momentum) to positive gross expectancy (Residual Momentum). This validates the structural theory that crypto-asset idiosyncratic trends are often masked by the dominant BTC beta.

## 7. Is single-leg or market-neutral construction better?
**Inconclusive.** The Single-Leg directional variant failed the `COST_PASS`. The Market-Neutral Long/Short variant could not be properly evaluated.

## 8. Does cross-sectional breadth support the inference?
**No.** The canonical Binance 1m research dataset (`binance_um_universe_1m_v2.parquet`) contains only 6 symbols. Removing BTC leaves 5 altcoins. A true market-neutral cross-sectional ranking strategy requires significant breadth ($N \ge 30$) to diversify away idiosyncratic risk and isolate the pure cross-sectional momentum factor. A long/short portfolio built on 4-5 coins is merely a pairs-trade exposed to massive idiosyncratic variance, not a generalized market-neutral factor.

## 9. Is the result stable?
**No.** With a $t$-statistic of 1.08 and failure to beat a simple long-only drift baseline, the result is too fragile for production consideration.

## 10. Final Promotion Status
**REJECTED.**
The directional model failed `COST_PASS` and failed to generate incremental value over the market drift baseline. The market-neutral theory is marked `INCONCLUSIVE` due to data constraints. The feature registry has been updated to reflect this status. S2 will not proceed to execution or machine learning experiments.

---
*Following the mandatory stop conditions laid out in the Phase 7.4 research guidelines, no subsequent experiments (S3-S5) will be automatically started until explicit authorization is received.*
