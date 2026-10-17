# PHASE 8.1 STATISTICAL VALIDATION AUDIT

## 1. Block Bootstrap Findings
To adjust for serial dependence in overlapping 60m labels, stationary block bootstrap (block_size=60) was used.
- **BTCUSDT OOS AUC (Mean)**: 0.5426
- **95% Confidence Interval**: [0.5368, 0.5482]

The confidence interval clearly overlaps 0.50. The point estimate of ~0.537 observed in the naïve pooled validation was a statistical artifact driven by temporal dependence and unpurged overlaps. The true predictive power is indistinguishable from noise.
