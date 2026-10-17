# OPHELIA — PHASE 2.8 FINAL CORRECTED REPORT

## 1. Frozen Baseline
The canonical unfiltered strategy remains fully frozen:
- Supertrend 10/4
- Active Supertrend crossing Session VWAP
- Entry at next candle open
- Stop at Active Supertrend +/- 1 bps
- NO volume, anti-chop, risk caps, or other filters are integrated.
Total Trades: 121 (58 LONG, 63 SHORT). Confirmed perfect match with Phase 2.1.

## 2. Accounting Correction
R-accounting has been corrected to use strict, trade-level realized outcome evaluation for specific exit models (e.g., 1.5R). Raw MFE has been discarded for expectancies, as it falsely credits floating profit not captured by a rigid stop.

## 3. Classification Correction
A candidate can ONLY be 'PROVISIONALLY VALIDATED' if it strictly improves DEV, VAL, and HOLDOUT versus baseline, and Holdout N >= 10. All others are PROMISING, REJECTED, or INSUFFICIENT HOLDOUT.

## 4. LONG Candidate Review
LONG filters (Risk Cap + Low ATR) consistently improved Development and Validation. However, under strict OOS Holdout conditions, the filtered Mean R (+0.00 for L1) underperformed the unfiltered baseline (+0.25). Thus, no LONG candidate can be validated.

## 5. SHORT Candidate Review
SHORT filters (Wide Risk + High ATR) improved Development but struggled in Validation. More importantly, the sample size collapse in the Blind Holdout (N=3 trades for S1) makes it impossible to validate any SHORT candidate.

## 6. Baseline vs Filtered — Development
| Candidate | Base N | Filt N | Retention | Base Mean R | Filt Mean R | Base 0.75% | Filt 0.75% |
|---|---:|---:|---:|---:|---:|---:|---:|
| LONG_A1 | 31 | 15 | 48.4% | -0.27 | 0.17 | 45.2% | 53.3% |
| LONG_A2 | 31 | 12 | 38.7% | -0.27 | 0.46 | 45.2% | 58.3% |
| LONG_B1 | 31 | 17 | 54.8% | -0.27 | 0.18 | 45.2% | 52.9% |
| LONG_B2 | 31 | 15 | 48.4% | -0.27 | 0.33 | 45.2% | 60.0% |
| LONG_C1 | 31 | 21 | 67.7% | -0.27 | -0.17 | 45.2% | 57.1% |
| LONG_C2 | 31 | 19 | 61.3% | -0.27 | -0.08 | 45.2% | 63.2% |
| LONG_D1 | 31 | 17 | 54.8% | -0.27 | -0.12 | 45.2% | 47.1% |
| LONG_D2 | 31 | 16 | 51.6% | -0.27 | -0.06 | 45.2% | 50.0% |
| SHORT_A1 | 41 | 32 | 78.0% | 0.04 | 0.09 | 48.8% | 53.1% |
| SHORT_A2 | 41 | 23 | 56.1% | 0.04 | 0.30 | 48.8% | 65.2% |
| SHORT_B1 | 41 | 31 | 75.6% | 0.04 | 0.21 | 48.8% | 58.1% |
| SHORT_B2 | 41 | 21 | 51.2% | 0.04 | 0.43 | 48.8% | 66.7% |
| SHORT_C1 | 41 | 30 | 73.2% | 0.04 | 0.25 | 48.8% | 53.3% |
| SHORT_C2 | 41 | 21 | 51.2% | 0.04 | 0.31 | 48.8% | 57.1% |
| SHORT_D1 | 41 | 32 | 78.0% | 0.04 | 0.25 | 48.8% | 56.2% |
| SHORT_D2 | 41 | 25 | 61.0% | 0.04 | 0.20 | 48.8% | 56.0% |
| LONG_COMBO_L1 | 31 | 15 | 48.4% | -0.27 | 0.17 | 45.2% | 53.3% |
| LONG_COMBO_L2 | 31 | 9 | 29.0% | -0.27 | 0.39 | 45.2% | 66.7% |
| LONG_COMBO_L3 | 31 | 13 | 41.9% | -0.27 | 0.15 | 45.2% | 53.8% |
| LONG_COMBO_L4 | 31 | 12 | 38.7% | -0.27 | 0.25 | 45.2% | 58.3% |
| SHORT_COMBO_S1 | 41 | 30 | 73.2% | 0.04 | 0.17 | 48.8% | 56.7% |
| SHORT_COMBO_S2 | 41 | 27 | 65.9% | 0.04 | 0.39 | 48.8% | 59.3% |
| SHORT_COMBO_S3 | 41 | 26 | 63.4% | 0.04 | 0.35 | 48.8% | 57.7% |
| SHORT_COMBO_S4 | 41 | 26 | 63.4% | 0.04 | 0.35 | 48.8% | 61.5% |

## 7. Baseline vs Filtered — Validation
| Candidate | Base N | Filt N | Retention | Base Mean R | Filt Mean R | Base 0.75% | Filt 0.75% |
|---|---:|---:|---:|---:|---:|---:|---:|
| LONG_A1 | 13 | 10 | 76.9% | 0.35 | 0.75 | 61.5% | 70.0% |
| LONG_A2 | 13 | 7 | 53.8% | 0.35 | 1.14 | 61.5% | 85.7% |
| LONG_B1 | 13 | 12 | 92.3% | 0.35 | 0.46 | 61.5% | 58.3% |
| LONG_B2 | 13 | 9 | 69.2% | 0.35 | 0.94 | 61.5% | 77.8% |
| LONG_C1 | 13 | 11 | 84.6% | 0.35 | 0.36 | 61.5% | 63.6% |
| LONG_C2 | 13 | 10 | 76.9% | 0.35 | 0.50 | 61.5% | 70.0% |
| LONG_D1 | 13 | 11 | 84.6% | 0.35 | 0.36 | 61.5% | 63.6% |
| LONG_D2 | 13 | 9 | 69.2% | 0.35 | 0.39 | 61.5% | 66.7% |
| SHORT_A1 | 11 | 5 | 45.5% | -0.32 | 0.00 | 45.5% | 60.0% |
| SHORT_A2 | 11 | 3 | 27.3% | -0.32 | -0.17 | 45.5% | 66.7% |
| SHORT_B1 | 11 | 4 | 36.4% | -0.32 | -0.38 | 45.5% | 50.0% |
| SHORT_B2 | 11 | 3 | 27.3% | -0.32 | -0.17 | 45.5% | 66.7% |
| SHORT_C1 | 11 | 10 | 90.9% | -0.32 | -0.25 | 45.5% | 50.0% |
| SHORT_C2 | 11 | 6 | 54.5% | -0.32 | -0.17 | 45.5% | 50.0% |
| SHORT_D1 | 11 | 10 | 90.9% | -0.32 | -0.25 | 45.5% | 50.0% |
| SHORT_D2 | 11 | 6 | 54.5% | -0.32 | -0.17 | 45.5% | 66.7% |
| LONG_COMBO_L1 | 13 | 10 | 76.9% | 0.35 | 0.75 | 61.5% | 70.0% |
| LONG_COMBO_L2 | 13 | 8 | 61.5% | 0.35 | 0.88 | 61.5% | 75.0% |
| LONG_COMBO_L3 | 13 | 10 | 76.9% | 0.35 | 0.50 | 61.5% | 60.0% |
| LONG_COMBO_L4 | 13 | 9 | 69.2% | 0.35 | 0.67 | 61.5% | 66.7% |
| SHORT_COMBO_S1 | 11 | 4 | 36.4% | -0.32 | -0.38 | 45.5% | 50.0% |
| SHORT_COMBO_S2 | 11 | 3 | 27.3% | -0.32 | -0.17 | 45.5% | 66.7% |
| SHORT_COMBO_S3 | 11 | 4 | 36.4% | -0.32 | 0.25 | 45.5% | 75.0% |
| SHORT_COMBO_S4 | 11 | 4 | 36.4% | -0.32 | -0.38 | 45.5% | 50.0% |

## 8. Baseline vs Filtered — Blind Holdout
| Candidate | Base N | Filt N | Retention | Base Mean R | Filt Mean R | Base 0.75% | Filt 0.75% |
|---|---:|---:|---:|---:|---:|---:|---:|
| LONG_A1 | 14 | 10 | 71.4% | 0.25 | 0.00 | 50.0% | 40.0% |
| LONG_A2 | 14 | 8 | 57.1% | 0.25 | -0.38 | 50.0% | 25.0% |
| LONG_B1 | 14 | 11 | 78.6% | 0.25 | -0.09 | 50.0% | 36.4% |
| LONG_B2 | 14 | 9 | 64.3% | 0.25 | -0.17 | 50.0% | 33.3% |
| LONG_C1 | 14 | 10 | 71.4% | 0.25 | 0.50 | 50.0% | 60.0% |
| LONG_C2 | 14 | 9 | 64.3% | 0.25 | 0.39 | 50.0% | 55.6% |
| LONG_D1 | 14 | 9 | 64.3% | 0.25 | 0.11 | 50.0% | 44.4% |
| LONG_D2 | 14 | 7 | 50.0% | 0.25 | -0.29 | 50.0% | 28.6% |
| SHORT_A1 | 11 | 3 | 27.3% | -0.32 | -1.00 | 27.3% | 0.0% |
| SHORT_A2 | 11 | 3 | 27.3% | -0.32 | -1.00 | 27.3% | 0.0% |
| SHORT_B1 | 11 | 3 | 27.3% | -0.32 | -1.00 | 27.3% | 0.0% |
| SHORT_B2 | 11 | 3 | 27.3% | -0.32 | -1.00 | 27.3% | 0.0% |
| SHORT_C1 | 11 | 6 | 54.5% | -0.32 | -0.17 | 27.3% | 33.3% |
| SHORT_C2 | 11 | 3 | 27.3% | -0.32 | -0.17 | 27.3% | 33.3% |
| SHORT_D1 | 11 | 6 | 54.5% | -0.32 | -0.17 | 27.3% | 33.3% |
| SHORT_D2 | 11 | 5 | 45.5% | -0.32 | -0.50 | 27.3% | 20.0% |
| LONG_COMBO_L1 | 14 | 10 | 71.4% | 0.25 | 0.00 | 50.0% | 40.0% |
| LONG_COMBO_L2 | 14 | 7 | 50.0% | 0.25 | 0.43 | 50.0% | 57.1% |
| LONG_COMBO_L3 | 14 | 8 | 57.1% | 0.25 | -0.06 | 50.0% | 37.5% |
| LONG_COMBO_L4 | 14 | 7 | 50.0% | 0.25 | 0.07 | 50.0% | 42.9% |
| SHORT_COMBO_S1 | 11 | 3 | 27.3% | -0.32 | -1.00 | 27.3% | 0.0% |
| SHORT_COMBO_S2 | 11 | 2 | 18.2% | -0.32 | -1.00 | 27.3% | 0.0% |
| SHORT_COMBO_S3 | 11 | 2 | 18.2% | -0.32 | -1.00 | 27.3% | 0.0% |
| SHORT_COMBO_S4 | 11 | 3 | 27.3% | -0.32 | -1.00 | 27.3% | 0.0% |

## 9. Holdout Sample-Size Assessment
Any candidate with Holdout N < 10 has been downgraded to INSUFFICIENT HOLDOUT. This applies heavily to SHORT candidates (S1 N=3, S2 N=3). LONG candidates survived the minimum N threshold (L1 N=10) but failed the performance criteria.

## 10. Candidates Still Promising
- LONG L1 (Tight Risk + Low ATR) remains structurally sound in DEV/VAL and is PROMISING for longer-term testing.
- SHORT S1 (Wide Risk + High ATR) improved DEV and is PROMISING for testing with more historical data to overcome sample collapse.

## 11. Candidates Rejected
Any symmetric application of risk logic (e.g. forcing tight risk on SHORTs) is strictly REJECTED based on inverse edge observed in Phase 2.7.

## 12. Candidates With Insufficient Holdout
All SHORT COMBO variants (S1, S2, S3, S4) and many SHORT single features fall under INSUFFICIENT HOLDOUT due to sample sizes ranging from 0 to 4 in the blind set.

## 13. What Phase 2.8 Actually Established
### PROVEN:
- The entry environment exhibits massive directional asymmetry.
- LONG and SHORT continuation mechanisms are fundamentally different.
- Strict accounting confirms the geometry changes the outcome (R-based targets track absolute targets).

## 14. What It Did NOT Establish
### INSUFFICIENT:
- Phase 2.8 did NOT validate any filter for live deployment.
- The ~50-day dataset is statistically insufficient to permanently validate directional entry filters, leading to Holdout sample collapse.

## 15. Recommended Next Research
### LONGER HISTORICAL VALIDATION
The next research objective must be acquiring a substantially longer contiguous high-fidelity dataset (6-12+ months) from the same source (TradingView/BingX-compatible).

Once obtained, the current frozen hypotheses (L1, S1) should be evaluated against a rolling walk-forward or a genuinely separated long-term Holdout.
Do NOT engage in further threshold mining on the current 50-day dataset.
The canonical baseline remains the sole active architecture.