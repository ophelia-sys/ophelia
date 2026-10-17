# STAGE D: Nonlinear Model Discovery (Exp 005)

**Locked Config**: Target=target_60_up_10 | Horizon=60 | Features=['baseline', 'volatility', 'trend', 'momentum', 'volume'] | Interactions=['interact_volume_vol']

| Model | AUC | 95% CI | Brier | Top Dec Gross (bps) | Top Dec Net (bps) |
|---|---|---|---|---|---|
| baseline | 0.5135 | [0.5093, 0.5236] | 0.2261 | 0.08 | -11.92 |
| persistence | 0.4977 | [0.4966, 0.4991] | 0.2500 | -0.14 | -12.14 |
| logistic | 0.5832 | [0.5772, 0.5945] | 0.2209 | 2.00 | -10.00 |
| lightgbm | 0.5992 | [0.5946, 0.6113] | 0.2181 | 1.11 | -10.89 |
| xgboost | 0.5971 | [0.5925, 0.6091] | 0.2183 | 0.61 | -11.39 |
