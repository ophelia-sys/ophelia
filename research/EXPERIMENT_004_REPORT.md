# STAGE C: Feature Interactions Discovery (Exp 004)

**Locked Target**: target_60_up_10 | **Locked Horizon**: 60 | **Base Features**: ['baseline', 'volatility', 'trend', 'momentum', 'volume']

| Interactions | AUC | 95% CI | Brier | Top Dec Gross (bps) | Top Dec Net (bps) |
|---|---|---|---|---|---|
| None | 0.5832 | [0.5772, 0.5945] | 0.2209 | 1.97 | -10.03 |
| interact_trend_vol | 0.5789 | [0.5727, 0.5895] | 0.2209 | 1.62 | -10.38 |
| interact_mom_vol | 0.5840 | [0.5784, 0.5946] | 0.2207 | 1.84 | -10.16 |
| interact_volume_vol | 0.5832 | [0.5772, 0.5945] | 0.2209 | 2.00 | -10.00 |
| interact_trend_vol+interact_mom_vol+interact_volume_vol | 0.5798 | [0.5738, 0.5898] | 0.2208 | 1.69 | -10.31 |
