# EXPERIMENT 001: Baseline BTCUSDT (5m) Ablation

## Hypothesis
Does the incremental addition of Volatility, Trend, Momentum, and Volume features improve OOS predictive and economic metrics beyond simple returns?

## Validation
- **Method**: Purged Walk-Forward (3 folds)
- **Embargo**: 60 periods
- **Target**: target_60 (Directional return over next 60 periods, i.e., 5 hours)
- **Cost Assumption**: 12 bps round-trip

## Results (Logistic Regression)

### Features: baseline
- **AUC**: 0.5289
- **Brier Score**: 0.2496
- **95% CI**: [0.5246, 0.5325]
- **Top Decile (9) Gross Ret (bps)**: 1.46
- **Top Decile (9) Net Ret (bps)**: -10.54

### Features: baseline+volatility
- **AUC**: 0.5202
- **Brier Score**: 0.2497
- **95% CI**: [0.5155, 0.5245]
- **Top Decile (9) Gross Ret (bps)**: 1.20
- **Top Decile (9) Net Ret (bps)**: -10.80

### Features: baseline+volatility+trend
- **AUC**: 0.5188
- **Brier Score**: 0.2497
- **95% CI**: [0.5142, 0.5235]
- **Top Decile (9) Gross Ret (bps)**: 1.44
- **Top Decile (9) Net Ret (bps)**: -10.56

### Features: baseline+volatility+trend+momentum
- **AUC**: 0.5340
- **Brier Score**: 0.2493
- **95% CI**: [0.5280, 0.5391]
- **Top Decile (9) Gross Ret (bps)**: 1.71
- **Top Decile (9) Net Ret (bps)**: -10.29

### Features: baseline+volatility+trend+momentum+volume
- **AUC**: 0.5333
- **Brier Score**: 0.2493
- **95% CI**: [0.5276, 0.5382]
- **Top Decile (9) Gross Ret (bps)**: 1.68
- **Top Decile (9) Net Ret (bps)**: -10.32

## Conclusion
We observe the incremental changes in AUC and net economic returns. If the net economic return does not rise above 0, the model remains statistically significant but economically useless (STATISTICALLY_SIGNIFICANT_NOT_ECONOMIC).
