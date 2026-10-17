# STAGE B: Feature Family Discovery (Exp 003)

**Locked Target**: target_60_up_10 | **Locked Horizon**: 60

| Features | AUC | 95% CI | Brier | Top Dec Gross (bps) | Top Dec Net (bps) |
|---|---|---|---|---|---|
| baseline | 0.5313 | [0.5263, 0.5343] | 0.2257 | 0.38 | -11.62 |
| baseline+volatility | 0.5818 | [0.5756, 0.5934] | 0.2211 | 1.10 | -10.90 |
| baseline+trend | 0.5279 | [0.5250, 0.5333] | 0.2256 | 0.64 | -11.36 |
| baseline+momentum | 0.5415 | [0.5399, 0.5460] | 0.2254 | 1.79 | -10.21 |
| baseline+volume | 0.5298 | [0.5271, 0.5342] | 0.2257 | 0.42 | -11.58 |
| baseline+volatility+trend | 0.5794 | [0.5734, 0.5908] | 0.2211 | 1.41 | -10.59 |
| baseline+volatility+momentum | 0.5852 | [0.5792, 0.5972] | 0.2209 | 1.47 | -10.53 |
| baseline+trend+momentum | 0.5326 | [0.5308, 0.5378] | 0.2253 | 1.87 | -10.13 |
| baseline+trend+volume | 0.5281 | [0.5252, 0.5334] | 0.2256 | 0.58 | -11.42 |
| baseline+volatility+trend+momentum+volume | 0.5832 | [0.5772, 0.5945] | 0.2209 | 1.97 | -10.03 |
