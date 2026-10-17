# PHASE 6.4 - P7 RESULT INTEGRITY AUDIT

## 1. Experiment Overview
- **Feature Family:** P7 (OHLCV-Derived Volume Acceptance Proxies)
- **Target:** 60-period (5-hour) triple-barrier label (TP=2.0 ATR, SL=1.0 ATR).
- **Evaluation:** Purged Walk-Forward (3 folds, 60-period embargo) on strictly Out-of-Sample 2022-2023 data.
- **Baseline Model:** `BASE + CVD` (LightGBM).
- **Test Model:** `BASE + CVD + P7` (LightGBM).

## 2. Statistical Suite Results

### A. Information Edge (LogLoss)
| Symbol | Base LL | Test LL | Diff (Base - Test) |
| :--- | :--- | :--- | :--- |
| BTCUSDT | 0.67630 | 0.67348 | +0.00282 |
| ETHUSDT | 0.68308 | 0.68096 | +0.00211 |
| SOLUSDT | 0.69201 | 0.69084 | +0.00117 |
| XRPUSDT | 0.68809 | 0.68595 | +0.00214 |
| BNBUSDT | 0.68640 | 0.68236 | +0.00404 |
| ADAUSDT | 0.68832 | 0.68782 | +0.00050 |
| **POOLED** | **0.68561** | **0.68346** | **+0.00215** |

### B. Statistical Significance
- **Pooled DM Test (lag=59):** p-value = 0.0000
- **Interpretation:** The improvement in LogLoss at the pooled level is highly statistically significant.
- **Individual Significance (DM p < 0.05):** BTCUSDT (0.0069), ETHUSDT (0.0111), XRPUSDT (0.0044), BNBUSDT (0.0002). 
- **Non-Significant / Neutral:** SOLUSDT (0.1238), ADAUSDT (0.4974).

### C. Block Bootstrap Confidence Intervals (LogLoss Diff)
- **BTCUSDT:** [0.00071, 0.00472]
- **ETHUSDT:** [0.00050, 0.00388]
- **SOLUSDT:** [-0.00022, 0.00261]
- **XRPUSDT:** [0.00066, 0.00367]
- **BNBUSDT:** [0.00181, 0.00609]
- **ADAUSDT:** [-0.00091, 0.00177]
- **Conclusion:** 4 out of 6 symbols have 95% confidence intervals strictly above zero. No symbol exhibits structural degradation.

## 3. Conclusion
The addition of P7 (Volume Acceptance Proxies) generates a robust, statistically significant predictive edge across the portfolio. The features successfully contextualize standard trade-flow (CVD) by identifying value areas and high-volume rejection zones without introducing lookahead leakage.
**STATUS:** APPROVED / RESEARCH SURVIVOR
