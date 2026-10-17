# PHASE 6.4 - P6 RESULT INTEGRITY AUDIT

## 1. Experiment Overview
- **Feature Family:** P6 (Funding / Positioning Pressure)
- **Target:** 60-period (5-hour) triple-barrier label (TP=2.0 ATR, SL=1.0 ATR).
- **Evaluation:** Purged Walk-Forward (3 folds, 60-period embargo) on strictly Out-of-Sample 2022-2023 data.
- **Baseline Model:** `BASE + CVD` (LightGBM).
- **Test Model:** `BASE + CVD + P6` (LightGBM).

## 2. Statistical Suite Results

### A. Information Edge (LogLoss)
| Symbol | Base LL | Test LL | Diff (Base - Test) |
| :--- | :--- | :--- | :--- |
| BTCUSDT | 0.67657 | 0.68134 | -0.00476 |
| ETHUSDT | 0.68339 | 0.68563 | -0.00223 |
| SOLUSDT | 0.69172 | 0.69943 | -0.00771 |
| XRPUSDT | 0.68803 | 0.69538 | -0.00735 |
| BNBUSDT | 0.68648 | 0.69185 | -0.00538 |
| ADAUSDT | 0.68886 | 0.69226 | -0.00340 |
| **POOLED** | **0.68576** | **0.69086** | **-0.00510** |

### B. Statistical Significance
- **Pooled DM Test (lag=59):** p-value = 0.0000
- **Interpretation:** The degradation in LogLoss is highly statistically significant.

### C. Block Bootstrap Confidence Intervals (LogLoss Diff)
- **BTCUSDT:** [-0.00701, -0.00238]
- **ETHUSDT:** [-0.00417, -0.00019]
- **SOLUSDT:** [-0.01080, -0.00443]
- **XRPUSDT:** [-0.01027, -0.00448]
- **BNBUSDT:** [-0.00811, -0.00238]
- **ADAUSDT:** [-0.00621, -0.00071]
- **Conclusion:** 100% of symbols show strict 95% confidence intervals entirely below zero.

## 3. Conclusion
The addition of P6 (Funding/Positioning Pressure) universally and significantly degrades the predictive capability of the model across all assets.
**STATUS:** REJECTED
