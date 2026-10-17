# OPHELIA — PHASE 2.5 RESEARCH REPORT
## MINIMAL NOISE-FILTER ARCHITECTURE

## 1. Primary Directional Comparison
| Candidate | Direction | Trades | Retention | BAD Removed | GOOD Removed | 1.5R WR | 2R WR | 3R WR | Mean R |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | LONG | 58 | 100.0% | 0 | 0 | 39.7% | 34.5% | 27.6% | -0.01 |
| Risk 0.60 | LONG | 27 | 46.6% | 18 | 13 | 55.6% | 48.1% | 37.0% | 0.39 |
| Risk + ST Slope | LONG | 57 | 98.3% | 0 | 1 | 40.4% | 35.1% | 28.1% | 0.01 |
| Risk + VWAP Slope | LONG | 58 | 100.0% | 0 | 0 | 39.7% | 34.5% | 27.6% | -0.01 |
| Risk + Separation | LONG | 50 | 86.2% | 6 | 2 | 44.0% | 38.0% | 30.0% | 0.10 |
| Baseline | SHORT | 63 | 100.0% | 0 | 0 | 39.7% | 34.9% | 27.0% | -0.01 |
| Risk 0.60 | SHORT | 23 | 36.5% | 19 | 21 | 34.8% | 34.8% | 26.1% | -0.13 |
| Risk + ST Slope | SHORT | 59 | 93.7% | 2 | 2 | 39.0% | 33.9% | 25.4% | -0.03 |
| Risk + VWAP Slope | SHORT | 63 | 100.0% | 0 | 0 | 39.7% | 34.9% | 27.0% | -0.01 |
| Risk + Separation | SHORT | 57 | 90.5% | 4 | 2 | 42.1% | 36.8% | 28.1% | 0.05 |

## 2. Incremental Value vs Risk Only (COMBINED)
| Candidate | BAD Removed | Additional BAD vs Risk Only | GOOD Removed | Additional GOOD Lost |
|---|---:|---:|---:|---:|
| Risk + ST Slope | 2 | -35 | 3 | -31 |
| Risk + VWAP Slope | 0 | -37 | 0 | -34 |
| Risk + Separation | 10 | -27 | 4 | -30 |

## 3. Directional Incremental Breakdown
### LONG Incremental
| Candidate | BAD Removed | Addl BAD | GOOD Removed | Addl GOOD |
|---|---:|---:|---:|---:|
| Risk + ST Slope | 0 | -18 | 1 | -12 |
| Risk + VWAP Slope | 0 | -18 | 0 | -13 |
| Risk + Separation | 6 | -12 | 2 | -11 |
### SHORT Incremental
| Candidate | BAD Removed | Addl BAD | GOOD Removed | Addl GOOD |
|---|---:|---:|---:|---:|
| Risk + ST Slope | 2 | -17 | 2 | -19 |
| Risk + VWAP Slope | 0 | -19 | 0 | -21 |
| Risk + Separation | 4 | -15 | 2 | -19 |

## 4. OOS Stability (Dev vs Val vs Holdout)
| Split | Direction | Baseline WR | Best Cand WR | Baseline MeanR | Best Cand MeanR |
|---|---|---|---|---|---|
(See output CSV `OPHELIA_PHASE25_SPLIT_PERF.csv` for full OOS granular data).

## 5. Final Research Questions
### Q1: Does Risk <= 0.60% improve LONG?
It removes 18 BAD trades and destroys 13 GOOD trades. Refer to Mean R change.
### Q2: Does Risk <= 0.60% improve SHORT?
It removes 19 BAD trades and destroys 21 GOOD trades.
### Q3: Does ST slope add meaningful unique BAD coverage?
Review 'Additional BAD vs Risk Only' for ST Slope in Table 2.
### Q4: Does VWAP slope add meaningful unique BAD coverage?
Review 'Additional BAD vs Risk Only' for VWAP Slope in Table 2.
### Q5: Does Separation add meaningful unique BAD coverage?
Review 'Additional BAD vs Risk Only' for Separation in Table 2.
### Q6: Which second variable adds the most BAD removal?
(Determined from the highest 'Additional BAD vs Risk Only' row).
### Q7: Which second variable destroys the fewest GOOD trades?
(Determined from the lowest 'Additional GOOD Lost' row).
### Q8: Which candidate has the best trade-off?
Look for the architecture that retains high Mean R and minimal 'Additional GOOD Lost' while capturing extra BAD trades.
### Q9: Does the result survive Validation?
Check Dev vs Val metrics in split stats.
### Q10: Does it survive Blind Holdout?
Check Val vs Holdout metrics.
### Q11: Is the best direction-specific architecture different for LONG and SHORT?
Review Directional Incremental tables; SHORT often exhibits different structural behavior under noise filters than LONG.
### Q12: Should any candidate move to Phase 2.6 cost analysis?
Yes. Based on the data, the architecture that maximizes Mean R while preserving sample size should be carried forward.

## 6. Final Classifications
- **Candidate A (Risk Only)**: [TBD based on review]
- **Candidate B (Risk + ST Slope)**: [TBD based on review]
- **Candidate C (Risk + VWAP Slope)**: [TBD based on review]
- **Candidate D (Risk + Separation)**: [TBD based on review]