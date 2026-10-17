# OPHELIA — PHASE 2.6B STOP A vs ATR 0.50 VALIDATION
## DIRECT A/B VALIDATION REPORT
Generated: 2026-08-22 06:25:00

## 1. PRIMARY COMPARISON
| Metric | Stop A (ST ±1bps) | Stop B (ATR 0.50) | Difference |
|---|---:|---:|---:|
### LONG
| Total trades | 58 | 58 | 0 |
| Avg risk % | 0.727% | 0.090% | -0.637% |
| Median risk % | 0.617% | 0.076% | -0.540% |
| 1.5R WR | 39.7% | 34.5% | -5.2% |
| 2R WR | 39.7% | 27.6% | -12.1% |
| 3R WR | 29.3% | 20.7% | -8.6% |
| Mean R | 0.474 | 0.207 | -0.267 |
| Median R | -1.000 | -1.000 | 0.000 |
| Avg holding time | 357.8m | 3.8m | -354.1m |
| Avg MFE R | 1.543 | 1.607 | 0.064 |
| Avg MAE R | 0.904 | 1.430 | 0.525 |

### SHORT
| Total trades | 63 | 63 | 0 |
| Avg risk % | 0.747% | 0.092% | -0.655% |
| Median risk % | 0.711% | 0.082% | -0.629% |
| 1.5R WR | 36.5% | 49.2% | 12.7% |
| 2R WR | 31.7% | 38.1% | 6.3% |
| 3R WR | 25.4% | 27.0% | 1.6% |
| Mean R | 0.325 | 0.690 | 0.365 |
| Median R | -1.000 | -1.000 | 0.000 |
| Avg holding time | 301.2m | 3.5m | -297.7m |
| Avg MFE R | 1.364 | 1.844 | 0.480 |
| Avg MAE R | 0.993 | 1.506 | 0.513 |

### COMBINED
| Total trades | 121 | 121 | 0 |
| Avg risk % | 0.737% | 0.091% | -0.646% |
| Median risk % | 0.651% | 0.078% | -0.573% |
| 1.5R WR | 38.0% | 42.1% | 4.1% |
| 2R WR | 35.5% | 33.1% | -2.5% |
| 3R WR | 27.3% | 24.0% | -3.3% |
| Mean R | 0.397 | 0.459 | 0.062 |
| Median R | -1.000 | -1.000 | 0.000 |
| Avg holding time | 328.3m | 3.6m | -324.7m |
| Avg MFE R | 1.450 | 1.730 | 0.281 |
| Avg MAE R | 0.950 | 1.470 | 0.519 |

## 2. SAVED LOSS ANALYSIS
| Category | LONG | SHORT | COMBINED |
|---|---:|---:|---:|
| Saved Loss | 6 | 19 | 25 |
| Delayed Loss | 0 | 0 | 0 |
| Still Loss | 29 | 21 | 50 |
| Original Stop Valid | 29 | 21 | 50 |
| New ATR Loss | 9 | 11 | 20 |

## 3. OOS REPORTING
### DEV
| Stop | Direction | Trades | 1.5R WR | 2R WR | 3R WR | Mean R | Max DD R | Max Streak | Saved | Delayed | New Loss |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | LONG | 31 | 29.0% | 29.0% | 19.4% | 0.065 | 10.00 | 10 | - | - | - |
| B | LONG | 31 | 22.6% | 16.1% | 12.9% | -0.226 | 13.50 | 6 | 3 | 0 | 5 |
| A | SHORT | 41 | 41.5% | 34.1% | 26.8% | 0.476 | 8.00 | 8 | - | - | - |
| B | SHORT | 41 | 53.7% | 43.9% | 34.1% | 0.902 | 5.00 | 5 | 12 | 0 | 7 |

### VAL
| Stop | Direction | Trades | 1.5R WR | 2R WR | 3R WR | Mean R | Max DD R | Max Streak | Saved | Delayed | New Loss |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | LONG | 13 | 53.8% | 53.8% | 38.5% | 1.000 | 6.00 | 6 | - | - | - |
| B | LONG | 13 | 46.2% | 38.5% | 38.5% | 0.731 | 4.50 | 4 | 1 | 0 | 2 |
| A | SHORT | 11 | 27.3% | 27.3% | 18.2% | 0.000 | 5.00 | 4 | - | - | - |
| B | SHORT | 11 | 36.4% | 18.2% | 9.1% | 0.091 | 4.00 | 5 | 3 | 0 | 2 |

### HOLDOUT
| Stop | Direction | Trades | 1.5R WR | 2R WR | 3R WR | Mean R | Max DD R | Max Streak | Saved | Delayed | New Loss |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | LONG | 14 | 50.0% | 50.0% | 42.9% | 0.893 | 4.00 | 5 | - | - | - |
| B | LONG | 14 | 50.0% | 42.9% | 21.4% | 0.679 | 4.00 | 5 | 2 | 0 | 2 |
| A | SHORT | 11 | 27.3% | 27.3% | 27.3% | 0.091 | 3.00 | 4 | - | - | - |
| B | SHORT | 11 | 45.5% | 36.4% | 18.2% | 0.500 | 3.00 | 3 | 4 | 0 | 2 |
