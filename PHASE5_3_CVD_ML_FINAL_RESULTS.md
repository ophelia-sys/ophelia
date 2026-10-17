# PHASE 5.3 CVD ML EXPERIMENT - FINAL RESULTS

## 1. Primary Analysis: MODEL G vs BASE_MATCHED_G
### Pooled Aggregate Metrics (All 6 Symbols)
- **Pooled LogLoss (Base):** 0.66490
- **Pooled LogLoss (CVD):** 0.65596
- **Pooled Delta LogLoss:** 0.00894
- **Pooled Brier (Base):** 0.23607
- **Pooled Brier (CVD):** 0.23183
- **Pooled Delta Brier:** 0.00425
- **Pooled DM Test (t-stat):** 53.26 (p=0.0000)

### Per-Symbol Evidence (Including Regimes)
| Symbol | Base LL | CVD LL | Delta LL | Base Brier | CVD Brier | Delta Brier | DM p-val | BH q-val | Delta LL (2022) | Delta LL (2023) |
|---|---|---|---|---|---|---|---|---|---|---|
| BTCUSDT | 0.63686 | 0.62615 | 0.01070 | 0.22246 | 0.21763 | 0.00483 | 0.0000 | 0.0000 | 0.01020 | 0.01095 |
| ETHUSDT | 0.65594 | 0.64501 | 0.01093 | 0.23166 | 0.22658 | 0.00508 | 0.0000 | 0.0000 | 0.01298 | 0.00992 |
| SOLUSDT | 0.68181 | 0.67268 | 0.00912 | 0.24435 | 0.23980 | 0.00455 | 0.0000 | 0.0000 | 0.00796 | 0.00985 |
| XRPUSDT | 0.67778 | 0.66973 | 0.00804 | 0.24235 | 0.23841 | 0.00394 | 0.0000 | 0.0000 | 0.00579 | 0.00913 |
| BNBUSDT | 0.66063 | 0.65309 | 0.00754 | 0.23393 | 0.23034 | 0.00359 | 0.0000 | 0.0000 | 0.00885 | 0.00689 |
| ADAUSDT | 0.67802 | 0.67069 | 0.00733 | 0.24248 | 0.23896 | 0.00353 | 0.0000 | 0.0000 | 0.00734 | 0.00733 |

### Pre-Execution Decision Rule Checklist (MODEL G)
- **Brier Deterioration <= 0.0005:** PASS (Actual: -0.00425)
- **Multi-Symbol Evidence (>=4/6):** PASS (Actual: 6/6)
- **Cost Robustness (>0 at 0, 5, 10 bps):** PASS
  - dENR(0): 17.41 bps
  - dENR(5): 17.41 bps
  - dENR(10): 17.41 bps
- **Statistical Acceptance (Pooled p <= 0.05):** PASS (Actual: 0.0000)

### FINAL DECISION CLASSIFICATION
**CLASSIFICATION: RETAIN**
All frozen decision rules mathematically passed.

## 2. Fold Boundaries
Extracted from MODEL G strict chronology:
| Fold | Train Start | Train End | Test Start | Test End | Train N | Test N |
|---|---|---|---|---|---|---|
| 0 | 2022-01-02T00:50:00.000 | 2022-07-02T07:25:00.000 | 2022-07-02T12:30:00.000 | 2023-01-02T23:25:00.000 | 52208 | 52268 |
| 1 | 2022-01-02T00:50:00.000 | 2023-01-02T18:25:00.000 | 2023-01-02T23:30:00.000 | 2023-07-03T11:05:00.000 | 104476 | 52268 |
| 2 | 2022-01-02T00:50:00.000 | 2023-07-03T06:05:00.000 | 2023-07-03T11:10:00.000 | 2023-12-31T22:55:00.000 | 156744 | 52270 |

## 3. Ablation Analysis (Models B-F)
A full ablation breakdown is serialized in the accompanying JSON artifact.