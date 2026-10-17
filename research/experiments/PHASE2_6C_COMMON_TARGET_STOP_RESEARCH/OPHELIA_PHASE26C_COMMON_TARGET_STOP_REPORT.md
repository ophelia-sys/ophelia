# OPHELIA — PHASE 2.6C COMMON ABSOLUTE TARGET STOP REPORT
Generated: 2026-08-22 06:39:37

**Frozen Dev Median Stop B Risk**: 0.0876%

## 1. REQUIRED FINAL TABLE (COMMON TARGETS, ALL SPLITS)
| Direction | Target | Stop A Hit % | Stop B Hit % | Difference | Mean Return A | Mean Return B | Preferred |
|---|---|---:|---:|---:|---:|---:|---|
| LONG | 0.50% | 56.9% | 10.3% | -46.6% | -0.020% | -0.030% | **Stop A** |
| LONG | 0.75% | 50.0% | 8.6% | -41.4% | 0.016% | -0.018% | **Stop A** |
| LONG | 1.00% | 44.8% | 6.9% | -37.9% | 0.057% | -0.015% | **Stop A** |
| SHORT | 0.50% | 50.8% | 12.7% | -38.1% | -0.086% | -0.014% | **Stop B** |
| SHORT | 0.75% | 44.4% | 11.1% | -33.3% | -0.055% | 0.005% | **Stop B** |
| SHORT | 1.00% | 38.1% | 7.9% | -30.2% | -0.062% | -0.003% | **Stop B** |

## 2. SET 2 TARGETS (Median Risk Multipliers)
| Direction | Target | Stop A Hit % | Stop B Hit % | Difference | Mean Return A | Mean Return B | Preferred |
|---|---|---:|---:|---:|---:|---:|---|
| LONG | 0.13% (R-base) | 81.0% | 32.8% | -48.3% | -0.027% | -0.017% | **Stop B** |
| LONG | 0.18% (R-base) | 79.3% | 27.6% | -51.7% | -0.007% | -0.018% | **Stop A** |
| LONG | 0.26% (R-base) | 70.7% | 20.7% | -50.0% | -0.023% | -0.016% | **Stop B** |
| SHORT | 0.13% (R-base) | 79.4% | 42.9% | -36.5% | -0.047% | 0.007% | **Stop B** |
| SHORT | 0.18% (R-base) | 74.6% | 38.1% | -36.5% | -0.042% | 0.014% | **Stop B** |
| SHORT | 0.26% (R-base) | 61.9% | 22.2% | -39.7% | -0.082% | -0.009% | **Stop B** |

## 3. OOS COMMON-TARGET TABLE (0.50%, 0.75%, 1.00%)
| Split | Direction | Target | Stop A Hit % | Stop B Hit % | Mean Return A | Mean Return B | Preferred |
|---|---|---:|---:|---:|---:|---:|---|
| DEV | LONG | 0.50% | 51.6% | 6.5% | -0.120% | -0.063% | Stop B |
| DEV | LONG | 0.75% | 45.2% | 6.5% | -0.104% | -0.046% | Stop B |
| DEV | LONG | 1.00% | 35.5% | 3.2% | -0.149% | -0.065% | Stop B |
| DEV | SHORT | 0.50% | 53.7% | 17.1% | -0.088% | 0.003% | Stop B |
| DEV | SHORT | 0.75% | 48.8% | 14.6% | -0.033% | 0.026% | Stop B |
| DEV | SHORT | 1.00% | 41.5% | 9.8% | -0.055% | 0.007% | Stop B |
| VAL | LONG | 0.50% | 61.5% | 23.1% | 0.043% | 0.057% | Stop B |
| VAL | LONG | 0.75% | 61.5% | 15.4% | 0.197% | 0.052% | Stop A |
| VAL | LONG | 1.00% | 61.5% | 15.4% | 0.351% | 0.090% | Stop A |
| VAL | SHORT | 0.50% | 54.5% | 0.0% | 0.050% | -0.076% | Stop A |
| VAL | SHORT | 0.75% | 45.5% | 0.0% | 0.039% | -0.076% | Stop A |
| VAL | SHORT | 1.00% | 36.4% | 0.0% | 0.009% | -0.076% | Stop A |
| HOLDOUT | LONG | 0.50% | 64.3% | 7.1% | 0.142% | -0.040% | Stop A |
| HOLDOUT | LONG | 0.75% | 50.0% | 7.1% | 0.114% | -0.022% | Stop A |
| HOLDOUT | LONG | 1.00% | 50.0% | 7.1% | 0.239% | -0.004% | Stop A |
| HOLDOUT | SHORT | 0.50% | 36.4% | 9.1% | -0.215% | -0.017% | Stop B |
| HOLDOUT | SHORT | 0.75% | 27.3% | 9.1% | -0.230% | 0.006% | Stop B |
| HOLDOUT | SHORT | 1.00% | 27.3% | 9.1% | -0.162% | 0.029% | Stop B |

## 4. REQUIRED R VS ABSOLUTE TABLE
| Direction | Metric | Stop A | Stop B | Difference |
|---|---|---:|---:|---:|
| LONG | 1.5R WR | 39.7% | 34.5% | -5.2% |
| LONG | 2R WR | 39.7% | 27.6% | -12.1% |
| LONG | 3R WR | 29.3% | 20.7% | -8.6% |
| LONG | 0.50% target | 56.9% | 10.3% | -46.6% |
| LONG | 0.75% target | 50.0% | 8.6% | -41.4% |
| LONG | 1.00% target | 44.8% | 6.9% | -37.9% |
| SHORT | 1.5R WR | 36.5% | 49.2% | +12.7% |
| SHORT | 2R WR | 31.7% | 38.1% | +6.3% |
| SHORT | 3R WR | 25.4% | 27.0% | +1.6% |
| SHORT | 0.50% target | 50.8% | 12.7% | -38.1% |
| SHORT | 0.75% target | 44.4% | 11.1% | -33.3% |
| SHORT | 1.00% target | 38.1% | 7.9% | -30.2% |

## 5. OOS RESCUE TABLE (Target = 0.75%)
| Split | Direction | Saved Losses | Delayed Losses | Still Losses | Original Stop Valid | New ATR Losses |
|---|---|---:|---:|---:|---:|---:|
| ALL | LONG | 0 | 0 | 29 | 29 | 24 |
| ALL | SHORT | 0 | 0 | 35 | 35 | 21 |
| DEV | LONG | 0 | 0 | 17 | 17 | 12 |
| DEV | SHORT | 0 | 0 | 21 | 21 | 14 |
| VAL | LONG | 0 | 0 | 5 | 5 | 6 |
| VAL | SHORT | 0 | 0 | 6 | 6 | 5 |
| HOLDOUT | LONG | 0 | 0 | 7 | 7 | 6 |
| HOLDOUT | SHORT | 0 | 0 | 8 | 8 | 2 |
