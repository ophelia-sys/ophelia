# Exp 013: Cross-Asset Validation

## Data Quality Matrix
| Asset | Rows | Nulls | Start | End | Schema OK |
|---|---|---|---|---|---|
| ETHUSDT | 1051200 | 2102401 | 2022-01-01 | 2023-12-31 | True |
| SOLUSDT | 1044000 | 2088001 | 2022-01-01 | 2023-12-31 | True |
| XRPUSDT | 1044000 | 2088001 | 2022-01-01 | 2023-12-31 | True |
| BNBUSDT | 1051200 | 2102401 | 2022-01-01 | 2023-12-31 | True |

## Evaluation
| Asset | AUC | Gross (bps) | Net (bps) | Classification |
|---|---|---|---|---|
| ETHUSDT | 0.5679 | 2.10 | -9.90 | ASSET_SPECIFIC |
| SOLUSDT | 0.5316 | -0.13 | -12.13 | ASSET_SPECIFIC |
| XRPUSDT | 0.5484 | -0.15 | -12.15 | ASSET_SPECIFIC |
| BNBUSDT | 0.5613 | 0.59 | -11.41 | ASSET_SPECIFIC |
