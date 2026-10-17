# OPHELIA — POWER OF STOCKS 5 EMA
## GROSS STRUCTURAL BACKTEST REPORT
### DATASET: BINGX_SOLUSDT.P, 5m (approx 50 days)
### NOTE: No Volume Data available in the dataset. Volume tests have been skipped.

## 1. PURE BASELINE (MODE A - EVERY ALERT)
### STOP B (+1 Tick) Targets
| Target | LONG Trades | LONG WR | LONG Mean R | SHORT Trades | SHORT WR | SHORT Mean R |
|---|---|---|---|---|---|---|
| hit_1R | 314 | 28.7% | -0.43 | 1342 | 17.5% | -0.65 |
| hit_2R | 314 | 28.7% | -0.14 | 1342 | 17.5% | -0.47 |
| hit_3R | 314 | 28.7% | 0.15 | 1342 | 17.5% | -0.30 |
| hit_4R | 314 | 28.7% | 0.43 | 1342 | 17.5% | -0.12 |
| hit_5R | 314 | 28.7% | 0.72 | 1340 | 17.4% | 0.04 |

## 2. STOP-BUFFER COMPARISON (Target 2R)
| Stop Config | LONG Trades | LONG WR | LONG Mean R | SHORT Trades | SHORT WR | SHORT Mean R |
|---|---|---|---|---|---|---|
| STOP_A | 314 | 28.7% | -0.14 | 1342 | 16.8% | -0.50 |
| STOP_B | 314 | 28.7% | -0.14 | 1342 | 17.5% | -0.47 |
| STOP_C1 | 314 | 26.8% | -0.20 | 1342 | 17.9% | -0.46 |
| STOP_C2 | 314 | 26.4% | -0.21 | 1341 | 18.0% | -0.46 |
| STOP_C3 | 314 | 24.8% | -0.25 | 1340 | 17.2% | -0.49 |

## 3. RSI FILTER (STOP B, Target 2R)
| Filter | LONG Trades | LONG WR | LONG Mean R | SHORT Trades | SHORT WR | SHORT Mean R |
|---|---|---|---|---|---|---|
| Unfiltered | 314 | 28.7% | -0.14 | 1342 | 17.5% | -0.47 |
| RSI Standard | 159 | 29.6% | -0.11 | 639 | 16.4% | -0.51 |
| RSI Strict | 85 | 30.6% | -0.08 | 355 | 16.1% | -0.52 |

## 4. EVERY-ALERT VS ALERT-REPLACEMENT (Mode A vs Mode B, STOP B, Target 2R)
| Mode | LONG Trades | LONG WR | LONG Mean R | SHORT Trades | SHORT WR | SHORT Mean R |
|---|---|---|---|---|---|---|
| Mode A (All Alerts) | 314 | 28.7% | -0.14 | 1342 | 17.5% | -0.47 |
| Mode B (Replacement) | 234 | 29.9% | -0.10 | 1009 | 18.7% | -0.44 |

## 5. INTRABAR AMBIGUITY SENSITIVITY (STOP B, Target 2R)
| Exit Model | LONG Trades | LONG WR | LONG Mean R | SHORT Trades | SHORT WR | SHORT Mean R |
|---|---|---|---|---|---|---|
| Conservative (STOP FIRST) | 314 | 28.7% | -0.14 | 1342 | 17.5% | -0.47 |
| Diagnostic (TARGET FIRST) | 314 | 28.7% | -0.14 | 1342 | 19.2% | -0.43 |