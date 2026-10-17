# STAGE A: Target & Horizon Discovery (Exp 002)

## Hypothesis
Does altering the prediction horizon or using fixed threshold targets provide an economically viable edge?

| Horizon | Target | Balance | AUC | 95% CI | Brier | Top Dec Gross (bps) | Top Dec Net (bps) |
|---|---|---|---|---|---|---|---|
| 12 | target_12_up_10 | 0.2087 | 0.6578 | [0.6561, 0.6647] | 0.1602 | 0.18 | -11.82 |
| 12 | target_12_up_15 | 0.1368 | 0.7072 | [0.7035, 0.7135] | 0.1130 | 0.29 | -11.71 |
| 12 | target_12_up_20 | 0.0935 | 0.7381 | [0.7347, 0.7446] | 0.0807 | 0.38 | -11.62 |
| 60 | target_60_up_10 | 0.3348 | 0.5832 | [0.5772, 0.5945] | 0.2209 | 1.97 | -10.03 |
| 60 | target_60_up_15 | 0.2705 | 0.6102 | [0.6043, 0.6214] | 0.1946 | 1.63 | -10.37 |
| 60 | target_60_up_20 | 0.2195 | 0.6338 | [0.6281, 0.6438] | 0.1680 | 1.37 | -10.63 |
