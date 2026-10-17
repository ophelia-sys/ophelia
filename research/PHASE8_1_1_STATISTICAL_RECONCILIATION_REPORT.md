# PHASE 8.1.1 STATISTICAL RECONCILIATION REPORT

## 1. Contradiction Resolution
The prior report incorrectly stated that a CI of [0.5368, 0.5482] included 0.50. This mathematical contradiction has been resolved by re-running the predictions, saving them to disk (`phase8_oos_predictions.parquet`), and strictly re-evaluating the confidence intervals.

## 2. Block Bootstrap CI & Hypothesis Test (BTCUSDT)
The null distribution was modeled assuming standard error derived from the stationary block bootstrap (block size = 60 to match label horizon).
- **Observed AUC**: 0.5425
- **Bootstrap 95% CI**: [0.5367, 0.5475]
- **Standard Error**: 0.0028
- **P-value (H0: AUC=0.50)**: 0.0000e+00

## 3. Decile / Economic Analysis
To evaluate economic utility, predictions were bucketed into deciles. Execution cost remains exactly 4 bps taker + 2 bps slippage per side (12 bps round-trip).
| Decile | Mean Prob | Realized % | Mean Fwd Ret (bps) | Net Ret (bps) |
|--------|-----------|------------|--------------------|---------------|
| 0 | 0.4330 | 0.4463 | 0.88 | -12.88 |
| 1 | 0.4599 | 0.4677 | 1.23 | -13.23 |
| 2 | 0.4740 | 0.4757 | 0.37 | -12.37 |
| 3 | 0.4854 | 0.4855 | 0.17 | -12.17 |
| 4 | 0.4938 | 0.4888 | 0.24 | -12.24 |
| 5 | 0.5064 | 0.5026 | 0.26 | -11.74 |
| 6 | 0.5192 | 0.5210 | 0.70 | -11.30 |
| 7 | 0.5341 | 0.5397 | 1.05 | -10.95 |
| 8 | 0.5513 | 0.5568 | 1.53 | -10.47 |
| 9 | 0.5803 | 0.5610 | 0.00 | -12.00 |

## 4. Final Conclusion
While the p-value confirms the signal is statistically significant (CI strictly excludes 0.50), the net returns in the highest probability deciles are severely negative due to execution costs. The signal exists, but it is not tradable.
**CLASSIFICATION**: PHASE8_WEAK_SIGNAL_NOT_ECONOMIC
