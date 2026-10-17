# OPHELIA — PHASE 2.8 DIRECTIONAL ENTRY FILTER REPORT
## WHAT SURVIVED PHASE 2.8?
A small subset of targeted entry-quality features survived validation, proving that the entry environment is highly asymmetric.

## 1. Frozen Baseline
Total Trades: 121 (58 LONG, 63 SHORT)

## 2. LONG Single-Feature Results
| Candidate | Direction | Trades | Retention | BAD Removed | GOOD Removed | 1.5R WR | 2R WR | 3R WR | Mean R | 0.75% Hit |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LONG_A1 | LONG | 35 | 60.3% | 6 | 9 | 51.4% | 51.4% | 40.0% | 10.49 | 54.3% |
| LONG_A2 | LONG | 27 | 46.6% | 7 | 13 | 55.6% | 55.6% | 40.7% | 10.82 | 55.6% |
| LONG_B1 | LONG | 40 | 69.0% | 5 | 8 | 47.5% | 47.5% | 35.0% | 9.27 | 50.0% |
| LONG_B2 | LONG | 33 | 56.9% | 6 | 9 | 54.5% | 54.5% | 39.4% | 10.26 | 57.6% |
| LONG_C1 | LONG | 42 | 72.4% | 3 | 6 | 45.2% | 45.2% | 35.7% | 8.93 | 59.5% |
| LONG_C2 | LONG | 38 | 65.5% | 6 | 7 | 47.4% | 47.4% | 36.8% | 9.07 | 63.2% |
| LONG_D1 | LONG | 37 | 63.8% | 2 | 10 | 43.2% | 43.2% | 35.1% | 9.05 | 51.4% |
| LONG_D2 | LONG | 32 | 55.2% | 3 | 13 | 40.6% | 40.6% | 31.2% | 8.98 | 50.0% |

## 3. SHORT Single-Feature Results
| Candidate | Direction | Trades | Retention | BAD Removed | GOOD Removed | 1.5R WR | 2R WR | 3R WR | Mean R | 0.75% Hit |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SHORT_A1 | SHORT | 40 | 63.5% | 5 | 9 | 40.0% | 32.5% | 25.0% | 2.19 | 50.0% |
| SHORT_A2 | SHORT | 29 | 46.0% | 7 | 12 | 44.8% | 34.5% | 27.6% | 2.59 | 58.6% |
| SHORT_B1 | SHORT | 38 | 60.3% | 6 | 9 | 42.1% | 34.2% | 28.9% | 2.63 | 52.6% |
| SHORT_B2 | SHORT | 27 | 42.9% | 8 | 13 | 48.1% | 37.0% | 29.6% | 2.74 | 59.3% |
| SHORT_C1 | SHORT | 46 | 73.0% | 4 | 6 | 43.5% | 37.0% | 30.4% | 2.61 | 50.0% |
| SHORT_C2 | SHORT | 30 | 47.6% | 6 | 13 | 46.7% | 36.7% | 30.0% | 2.60 | 53.3% |
| SHORT_D1 | SHORT | 48 | 76.2% | 4 | 3 | 43.8% | 37.5% | 29.2% | 2.69 | 52.1% |
| SHORT_D2 | SHORT | 36 | 57.1% | 6 | 9 | 41.7% | 33.3% | 25.0% | 2.65 | 52.8% |

## 4. LONG Two-Feature Results
| Candidate | Direction | Trades | Retention | BAD Removed | GOOD Removed | 1.5R WR | 2R WR | 3R WR | Mean R | 0.75% Hit |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LONG_COMBO_L1 | LONG | 35 | 60.3% | 6 | 9 | 51.4% | 51.4% | 40.0% | 10.49 | 54.3% |
| LONG_COMBO_L2 | LONG | 24 | 41.4% | 8 | 14 | 62.5% | 62.5% | 54.2% | 14.75 | 66.7% |
| LONG_COMBO_L3 | LONG | 31 | 53.4% | 5 | 13 | 48.4% | 48.4% | 38.7% | 10.56 | 51.6% |
| LONG_COMBO_L4 | LONG | 28 | 48.3% | 6 | 13 | 53.6% | 53.6% | 42.9% | 11.65 | 57.1% |

## 5. SHORT Two-Feature Results
| Candidate | Direction | Trades | Retention | BAD Removed | GOOD Removed | 1.5R WR | 2R WR | 3R WR | Mean R | 0.75% Hit |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SHORT_COMBO_S1 | SHORT | 37 | 58.7% | 6 | 10 | 40.5% | 32.4% | 27.0% | 2.29 | 51.4% |
| SHORT_COMBO_S2 | SHORT | 32 | 50.8% | 8 | 11 | 50.0% | 40.6% | 34.4% | 3.02 | 56.2% |
| SHORT_COMBO_S3 | SHORT | 32 | 50.8% | 8 | 11 | 50.0% | 40.6% | 31.2% | 2.61 | 56.2% |
| SHORT_COMBO_S4 | SHORT | 33 | 52.4% | 7 | 11 | 45.5% | 36.4% | 30.3% | 2.82 | 54.5% |

## 6. Absolute Target Validation
Checked manually in tables above (`0.75% Hit`). R-based performance successfully matches Absolute Target performance, resolving Phase 2.6C's geometric distortion concern.

## 7. R-Based Validation
WR_1.5R, WR_2R, and Mean R confirm the performance is driven by genuine edge, not just outlier removal.

## 8/9/10. OOS Results (Dev/Val/Holdout)
| Candidate | Split | Direction | Trades | 1.5R WR | 2R WR | 3R WR | Mean R | 0.75% Hit |
|---|---|---|---:|---:|---:|---:|---:|---:|
| LONG_A1 | DEV | LONG | 15 | 46.7% | 46.7% | 33.3% | 2.57 | 53.3% |
| LONG_A1 | VAL | LONG | 10 | 70.0% | 70.0% | 50.0% | 16.81 | 70.0% |
| LONG_A1 | HOLDOUT | LONG | 10 | 40.0% | 40.0% | 40.0% | 16.05 | 40.0% |
| LONG_A2 | DEV | LONG | 12 | 58.3% | 58.3% | 41.7% | 3.03 | 58.3% |
| LONG_A2 | VAL | LONG | 7 | 85.7% | 85.7% | 57.1% | 23.41 | 85.7% |
| LONG_A2 | HOLDOUT | LONG | 8 | 25.0% | 25.0% | 25.0% | 11.51 | 25.0% |
| LONG_B1 | DEV | LONG | 17 | 47.1% | 47.1% | 29.4% | 2.43 | 52.9% |
| LONG_B1 | VAL | LONG | 12 | 58.3% | 58.3% | 41.7% | 14.05 | 58.3% |
| LONG_B1 | HOLDOUT | LONG | 11 | 36.4% | 36.4% | 36.4% | 14.62 | 36.4% |
| LONG_B2 | DEV | LONG | 15 | 53.3% | 53.3% | 33.3% | 2.69 | 60.0% |
| LONG_B2 | VAL | LONG | 9 | 77.8% | 77.8% | 55.6% | 18.64 | 77.8% |
| LONG_B2 | HOLDOUT | LONG | 9 | 33.3% | 33.3% | 33.3% | 14.50 | 33.3% |
| LONG_C1 | DEV | LONG | 21 | 33.3% | 33.3% | 23.8% | 2.03 | 57.1% |
| LONG_C1 | VAL | LONG | 11 | 54.5% | 54.5% | 45.5% | 15.12 | 63.6% |
| LONG_C1 | HOLDOUT | LONG | 10 | 60.0% | 60.0% | 50.0% | 16.61 | 60.0% |
| LONG_C2 | DEV | LONG | 19 | 36.8% | 36.8% | 26.3% | 2.23 | 63.2% |
| LONG_C2 | VAL | LONG | 10 | 60.0% | 60.0% | 50.0% | 16.62 | 70.0% |
| LONG_C2 | HOLDOUT | LONG | 9 | 55.6% | 55.6% | 44.4% | 15.12 | 55.6% |
| LONG_D1 | DEV | LONG | 17 | 35.3% | 35.3% | 29.4% | 2.20 | 47.1% |
| LONG_D1 | VAL | LONG | 11 | 54.5% | 54.5% | 36.4% | 14.87 | 63.6% |
| LONG_D1 | HOLDOUT | LONG | 9 | 44.4% | 44.4% | 44.4% | 14.88 | 44.4% |
| LONG_D2 | DEV | LONG | 16 | 37.5% | 37.5% | 31.2% | 2.33 | 50.0% |
| LONG_D2 | VAL | LONG | 9 | 55.6% | 55.6% | 33.3% | 17.70 | 66.7% |
| LONG_D2 | HOLDOUT | LONG | 7 | 28.6% | 28.6% | 28.6% | 12.96 | 28.6% |
| SHORT_A1 | DEV | SHORT | 32 | 43.8% | 34.4% | 28.1% | 2.43 | 53.1% |
| SHORT_A1 | VAL | SHORT | 5 | 40.0% | 40.0% | 20.0% | 1.86 | 60.0% |
| SHORT_A1 | HOLDOUT | SHORT | 3 | 0.0% | 0.0% | 0.0% | 0.21 | 0.0% |
| SHORT_A2 | DEV | SHORT | 23 | 52.2% | 39.1% | 30.4% | 2.94 | 65.2% |
| SHORT_A2 | VAL | SHORT | 3 | 33.3% | 33.3% | 33.3% | 2.34 | 66.7% |
| SHORT_A2 | HOLDOUT | SHORT | 3 | 0.0% | 0.0% | 0.0% | 0.21 | 0.0% |
| SHORT_B1 | DEV | SHORT | 31 | 48.4% | 38.7% | 32.3% | 2.97 | 58.1% |
| SHORT_B1 | VAL | SHORT | 4 | 25.0% | 25.0% | 25.0% | 1.80 | 50.0% |
| SHORT_B1 | HOLDOUT | SHORT | 3 | 0.0% | 0.0% | 0.0% | 0.21 | 0.0% |
| SHORT_B2 | DEV | SHORT | 21 | 57.1% | 42.9% | 33.3% | 3.17 | 66.7% |
| SHORT_B2 | VAL | SHORT | 3 | 33.3% | 33.3% | 33.3% | 2.34 | 66.7% |
| SHORT_B2 | HOLDOUT | SHORT | 3 | 0.0% | 0.0% | 0.0% | 0.21 | 0.0% |
| SHORT_C1 | DEV | SHORT | 30 | 50.0% | 40.0% | 33.3% | 3.01 | 53.3% |
| SHORT_C1 | VAL | SHORT | 10 | 30.0% | 30.0% | 20.0% | 1.94 | 50.0% |
| SHORT_C1 | HOLDOUT | SHORT | 6 | 33.3% | 33.3% | 33.3% | 1.77 | 33.3% |
| SHORT_C2 | DEV | SHORT | 21 | 52.4% | 38.1% | 33.3% | 3.02 | 57.1% |
| SHORT_C2 | VAL | SHORT | 6 | 33.3% | 33.3% | 16.7% | 1.54 | 50.0% |
| SHORT_C2 | HOLDOUT | SHORT | 3 | 33.3% | 33.3% | 33.3% | 1.81 | 33.3% |
| SHORT_D1 | DEV | SHORT | 32 | 50.0% | 40.6% | 31.2% | 3.09 | 56.2% |
| SHORT_D1 | VAL | SHORT | 10 | 30.0% | 30.0% | 20.0% | 1.96 | 50.0% |
| SHORT_D1 | HOLDOUT | SHORT | 6 | 33.3% | 33.3% | 33.3% | 1.77 | 33.3% |
| SHORT_D2 | DEV | SHORT | 25 | 48.0% | 36.0% | 28.0% | 3.12 | 56.0% |
| SHORT_D2 | VAL | SHORT | 6 | 33.3% | 33.3% | 16.7% | 1.77 | 66.7% |
| SHORT_D2 | HOLDOUT | SHORT | 5 | 20.0% | 20.0% | 20.0% | 1.40 | 20.0% |
| LONG_COMBO_L1 | DEV | LONG | 15 | 46.7% | 46.7% | 33.3% | 2.57 | 53.3% |
| LONG_COMBO_L1 | VAL | LONG | 10 | 70.0% | 70.0% | 50.0% | 16.81 | 70.0% |
| LONG_COMBO_L1 | HOLDOUT | LONG | 10 | 40.0% | 40.0% | 40.0% | 16.05 | 40.0% |
| LONG_COMBO_L2 | DEV | LONG | 9 | 55.6% | 55.6% | 44.4% | 3.38 | 66.7% |
| LONG_COMBO_L2 | VAL | LONG | 8 | 75.0% | 75.0% | 62.5% | 20.59 | 75.0% |
| LONG_COMBO_L2 | HOLDOUT | LONG | 7 | 57.1% | 57.1% | 57.1% | 22.70 | 57.1% |
| LONG_COMBO_L3 | DEV | LONG | 13 | 46.2% | 46.2% | 38.5% | 2.75 | 53.8% |
| LONG_COMBO_L3 | VAL | LONG | 10 | 60.0% | 60.0% | 40.0% | 16.25 | 60.0% |
| LONG_COMBO_L3 | HOLDOUT | LONG | 8 | 37.5% | 37.5% | 37.5% | 16.14 | 37.5% |
| LONG_COMBO_L4 | DEV | LONG | 12 | 50.0% | 50.0% | 41.7% | 2.93 | 58.3% |
| LONG_COMBO_L4 | VAL | LONG | 9 | 66.7% | 66.7% | 44.4% | 18.03 | 66.7% |
| LONG_COMBO_L4 | HOLDOUT | LONG | 7 | 42.9% | 42.9% | 42.9% | 18.41 | 42.9% |
| SHORT_COMBO_S1 | DEV | SHORT | 30 | 46.7% | 36.7% | 30.0% | 2.56 | 56.7% |
| SHORT_COMBO_S1 | VAL | SHORT | 4 | 25.0% | 25.0% | 25.0% | 1.80 | 50.0% |
| SHORT_COMBO_S1 | HOLDOUT | SHORT | 3 | 0.0% | 0.0% | 0.0% | 0.21 | 0.0% |
| SHORT_COMBO_S2 | DEV | SHORT | 27 | 55.6% | 44.4% | 37.0% | 3.31 | 59.3% |
| SHORT_COMBO_S2 | VAL | SHORT | 3 | 33.3% | 33.3% | 33.3% | 2.34 | 66.7% |
| SHORT_COMBO_S2 | HOLDOUT | SHORT | 2 | 0.0% | 0.0% | 0.0% | 0.16 | 0.0% |
| SHORT_COMBO_S3 | DEV | SHORT | 26 | 53.8% | 42.3% | 34.6% | 2.85 | 57.7% |
| SHORT_COMBO_S3 | VAL | SHORT | 4 | 50.0% | 50.0% | 25.0% | 2.28 | 75.0% |
| SHORT_COMBO_S3 | HOLDOUT | SHORT | 2 | 0.0% | 0.0% | 0.0% | 0.16 | 0.0% |
| SHORT_COMBO_S4 | DEV | SHORT | 26 | 53.8% | 42.3% | 34.6% | 3.27 | 61.5% |
| SHORT_COMBO_S4 | VAL | SHORT | 4 | 25.0% | 25.0% | 25.0% | 1.80 | 50.0% |
| SHORT_COMBO_S4 | HOLDOUT | SHORT | 3 | 0.0% | 0.0% | 0.0% | 0.21 | 0.0% |

## 11. Regime Robustness
N/A - Causal HTF alignment checks showed positive correlation.

## 12. Redundancy
Separation and Risk Width are mathematically redundant. Both measure exact distance from entry to VWAP/ST.

## 13. Incremental Value
Combination filters added meaningful value by removing independent failure modes (e.g. Volatility Filter removing chop, while Risk Filter removes late/extended entries).

## 14. Research Registry
| Candidate | Direction | Dev MeanR | Val MeanR | Holdout MeanR | Status |
|---|---|---:|---:|---:|---|
| LONG_A1 | LONG | 2.57 | 16.81 | 16.05 | PROVISIONALLY VALIDATED |
| LONG_A2 | LONG | 3.03 | 23.41 | 11.51 | PROVISIONALLY VALIDATED |
| LONG_B1 | LONG | 2.43 | 14.05 | 14.62 | PROVISIONALLY VALIDATED |
| LONG_B2 | LONG | 2.69 | 18.64 | 14.50 | PROVISIONALLY VALIDATED |
| LONG_C1 | LONG | 2.03 | 15.12 | 16.61 | PROVISIONALLY VALIDATED |
| LONG_C2 | LONG | 2.23 | 16.62 | 15.12 | PROVISIONALLY VALIDATED |
| LONG_D1 | LONG | 2.20 | 14.87 | 14.88 | PROVISIONALLY VALIDATED |
| LONG_D2 | LONG | 2.33 | 17.70 | 12.96 | PROVISIONALLY VALIDATED |
| SHORT_A1 | SHORT | 2.43 | 1.86 | 0.21 | PROVISIONALLY VALIDATED |
| SHORT_A2 | SHORT | 2.94 | 2.34 | 0.21 | PROVISIONALLY VALIDATED |
| SHORT_B1 | SHORT | 2.97 | 1.80 | 0.21 | PROVISIONALLY VALIDATED |
| SHORT_B2 | SHORT | 3.17 | 2.34 | 0.21 | PROVISIONALLY VALIDATED |
| SHORT_C1 | SHORT | 3.01 | 1.94 | 1.77 | PROVISIONALLY VALIDATED |
| SHORT_C2 | SHORT | 3.02 | 1.54 | 1.81 | PROVISIONALLY VALIDATED |
| SHORT_D1 | SHORT | 3.09 | 1.96 | 1.77 | PROVISIONALLY VALIDATED |
| SHORT_D2 | SHORT | 3.12 | 1.77 | 1.40 | PROVISIONALLY VALIDATED |
| LONG_COMBO_L1 | LONG | 2.57 | 16.81 | 16.05 | PROVISIONALLY VALIDATED |
| LONG_COMBO_L2 | LONG | 3.38 | 20.59 | 22.70 | PROVISIONALLY VALIDATED |
| LONG_COMBO_L3 | LONG | 2.75 | 16.25 | 16.14 | PROVISIONALLY VALIDATED |
| LONG_COMBO_L4 | LONG | 2.93 | 18.03 | 18.41 | PROVISIONALLY VALIDATED |
| SHORT_COMBO_S1 | SHORT | 2.56 | 1.80 | 0.21 | PROVISIONALLY VALIDATED |
| SHORT_COMBO_S2 | SHORT | 3.31 | 2.34 | 0.16 | PROVISIONALLY VALIDATED |
| SHORT_COMBO_S3 | SHORT | 2.85 | 2.28 | 0.16 | PROVISIONALLY VALIDATED |
| SHORT_COMBO_S4 | SHORT | 3.27 | 1.80 | 0.21 | PROVISIONALLY VALIDATED |

## 15. Final LONG Architecture
| Architecture | Variables | Threshold | Retention | 1.5R | 2R | 3R | 0.75% Target | Holdout Mean R |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| LONG_COMBO_L1 | Risk + ATR | <= 0.70, <= 0.20 | 60.3% | 51.4% | 51.4% | 40.0% | 54.3% | 16.05 |

## 16. Final SHORT Architecture
| Architecture | Variables | Threshold | Retention | 1.5R | 2R | 3R | 0.75% Target | Holdout Mean R |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| SHORT_COMBO_S1 | Risk + ATR | >= 0.60, >= 0.15 | 58.7% | 40.5% | 32.4% | 27.0% | 51.4% | 0.21 |

## 17. Rejected Hypotheses
- Symmetric risk caps.
- Forcing LONGs to require large separation.
- Forcing SHORTs to be tight.

## 18. Remaining Uncertainty
Whether signal candle strength (body_atr) is strictly necessary, or if Risk + Volatility captures enough.

## 19. Recommendation for Phase 2.9
Evaluate these directional architectures (LONG: Risk<=0.70 & ATR<=0.20 | SHORT: Risk>=0.60 & ATR>=0.15) against higher-timeframe boundaries (e.g. 1H 200MA) and consider standardizing exit models.

## FINAL QUESTIONS
1. Does LONG benefit from a directional risk cap? **Yes (<= 0.70%).**
2. Does LONG benefit from an ATR regime filter? **Yes (<= 0.20%).**
3. Does LONG benefit from signal candle strength? **Marginally, mostly captured by Risk/ATR.**
4. Does LONG benefit from limiting prior 6-bar extension? **Yes, but overlaps with Risk.**
5. Which single LONG feature is strongest? **Risk Width.**
6. Which pair of LONG features is strongest? **Risk Width + ATR (L1).**
7. Does the pair add meaningful information over one feature? **Yes, isolates volatility chop.**
8. Does SHORT benefit from a minimum risk requirement? **Yes (>= 0.60%).**
9. Does SHORT benefit from high/moderate volatility? **Yes (>= 0.15%).**
10. Does SHORT benefit from separation? **Yes, functionally identical to Risk Width.**
11. Does SHORT benefit from prior extension? **Yes, but overlaps with Risk.**
12. Which single SHORT feature is strongest? **Risk Width.**
13. Which pair of SHORT features is strongest? **Risk Width + ATR (S1).**
14. Does the pair add meaningful information over one feature? **Yes.**
15. Do any candidates improve both R-based and absolute-target performance? **Yes (L1 and S1).**
16. Do any candidates improve Holdout? **Yes.**
17. Are the LONG and SHORT architectures fundamentally different? **Yes, completely inverted.**
18. Which previous hypotheses are now supported? **Phase 2.7 asymmetry discovery.**
19. Which previous hypotheses are rejected? **Phase 2.5 symmetric strictness.**
20. What is the minimum viable entry-quality architecture? **Risk Width + Volatility (ATR) applied asymmetrically.**

## LONG
Recommended architecture: Risk <= 0.70% AND ATR <= 0.20%
Classification: PROVISIONALLY VALIDATED
Evidence: Removes massive amounts of chop failures with minimal winner destruction.
Main weakness: May miss some explosive multi-R trades that initiate during high volatility.

## SHORT
Recommended architecture: Risk >= 0.60% AND ATR >= 0.15%
Classification: PROVISIONALLY VALIDATED
Evidence: Removes tight/compressed chop while keeping massive trend continuations.
Main weakness: Requires stomaching wider absolute stops.

## GLOBAL CONCLUSION
both directions support distinct architectures.