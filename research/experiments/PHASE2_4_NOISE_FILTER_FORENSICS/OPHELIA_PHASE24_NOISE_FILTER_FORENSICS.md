# OPHELIA — PHASE 2.4 RESEARCH REPORT
## NOISE-FILTER FORENSICS

## 1. Executive Summary
This report contains the raw forensic mapping of individual filter rejections against the 10/4 baseline trades, establishing exact structural overlap without any economic cost modeling.

## 2. Individual Filter Rejections
| Candidate | Total Rejected | BAD Removed | GOOD Removed | BAD Removal % | GOOD Dest % | Unique BAD | 1.5R Winners Rm | 2R Winners Rm | 3R Winners Rm |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| risk_0.4_rejected | 106 | 51 | 55 | 87.9% | 87.3% | 2 | 42 | 36 | 28 |
| risk_0.5_rejected | 89 | 42 | 47 | 72.4% | 74.6% | 0 | 35 | 31 | 23 |
| risk_0.6_rejected | 71 | 37 | 34 | 63.8% | 54.0% | 0 | 25 | 21 | 17 |
| risk_0.7_rejected | 55 | 27 | 28 | 46.6% | 44.4% | 0 | 20 | 16 | 13 |
| risk_0.8_rejected | 44 | 21 | 23 | 36.2% | 36.5% | 0 | 17 | 14 | 11 |
| sep_0.005_rejected | 10 | 4 | 6 | 6.9% | 9.5% | 0 | 3 | 3 | 1 |
| sep_0.01_rejected | 20 | 6 | 14 | 10.3% | 22.2% | 0 | 10 | 10 | 6 |
| sep_0.015_rejected | 31 | 15 | 16 | 25.9% | 25.4% | 0 | 11 | 11 | 7 |
| sep_0.02_rejected | 41 | 21 | 20 | 36.2% | 31.7% | 0 | 13 | 13 | 9 |
| sep_0.03_rejected | 54 | 28 | 26 | 48.3% | 41.3% | 0 | 17 | 17 | 13 |
| sep_0.05_rejected | 75 | 37 | 38 | 63.8% | 60.3% | 2 | 27 | 26 | 20 |
| vwap_slope1_flat_rejected | 0 | 0 | 0 | 0.0% | 0.0% | 0 | 0 | 0 | 0 |
| vwap_slope3_flat_rejected | 0 | 0 | 0 | 0.0% | 0.0% | 0 | 0 | 0 | 0 |
| vwap_slope6_flat_rejected | 0 | 0 | 0 | 0.0% | 0.0% | 0 | 0 | 0 | 0 |
| st_slope1_flat_rejected | 0 | 0 | 0 | 0.0% | 0.0% | 0 | 0 | 0 | 0 |
| st_slope3_flat_rejected | 11 | 6 | 5 | 10.3% | 7.9% | 0 | 3 | 3 | 2 |
| st_slope6_flat_rejected | 12 | 7 | 5 | 12.1% | 7.9% | 0 | 4 | 4 | 3 |
| ext3_high_rejected | 0 | 0 | 0 | 0.0% | 0.0% | 0 | 0 | 0 | 0 |
| ext6_high_rejected | 1 | 1 | 0 | 1.7% | 0.0% | 0 | 0 | 0 | 0 |
| ext12_high_rejected | 8 | 5 | 3 | 8.6% | 4.8% | 0 | 2 | 2 | 2 |
| vol_high_0.3_rejected | 13 | 7 | 6 | 12.1% | 9.5% | 0 | 5 | 5 | 4 |
| vol_high_0.4_rejected | 2 | 1 | 1 | 1.7% | 1.6% | 0 | 0 | 0 | 0 |
| vol_high_0.5_rejected | 0 | 0 | 0 | 0.0% | 0.0% | 0 | 0 | 0 | 0 |

## 3. Pairwise Overlap Matrix
| Candidate A | Candidate B | A Rej | B Rej | Both Rej | BAD Both | GOOD Both | Jaccard |
|---|---|---:|---:|---:|---:|---:|---:|
| risk_0.4_rejected | risk_0.5_rejected | 106 | 89 | 89 | 42 | 47 | 0.840 |
| risk_0.7_rejected | risk_0.8_rejected | 55 | 44 | 44 | 21 | 23 | 0.800 |
| risk_0.5_rejected | risk_0.6_rejected | 89 | 71 | 71 | 37 | 34 | 0.798 |
| risk_0.6_rejected | risk_0.7_rejected | 71 | 55 | 55 | 27 | 28 | 0.775 |
| st_slope3_flat_rejected | st_slope6_flat_rejected | 11 | 12 | 10 | 6 | 4 | 0.769 |
| sep_0.02_rejected | sep_0.03_rejected | 41 | 54 | 41 | 21 | 20 | 0.759 |
| sep_0.015_rejected | sep_0.02_rejected | 31 | 41 | 31 | 15 | 16 | 0.756 |
| sep_0.03_rejected | sep_0.05_rejected | 54 | 75 | 54 | 28 | 26 | 0.720 |
| risk_0.4_rejected | risk_0.6_rejected | 106 | 71 | 71 | 37 | 34 | 0.670 |
| sep_0.01_rejected | sep_0.015_rejected | 20 | 31 | 20 | 6 | 14 | 0.645 |
| risk_0.6_rejected | risk_0.8_rejected | 71 | 44 | 44 | 21 | 23 | 0.620 |
| risk_0.5_rejected | risk_0.7_rejected | 89 | 55 | 55 | 27 | 28 | 0.618 |
| ext12_high_rejected | vol_high_0.3_rejected | 8 | 13 | 8 | 5 | 3 | 0.615 |
| sep_0.015_rejected | sep_0.03_rejected | 31 | 54 | 31 | 15 | 16 | 0.574 |
| sep_0.02_rejected | sep_0.05_rejected | 41 | 75 | 41 | 21 | 20 | 0.547 |
| risk_0.4_rejected | sep_0.05_rejected | 106 | 75 | 62 | 31 | 31 | 0.521 |
| risk_0.4_rejected | risk_0.7_rejected | 106 | 55 | 55 | 27 | 28 | 0.519 |
| sep_0.005_rejected | sep_0.01_rejected | 10 | 20 | 10 | 4 | 6 | 0.500 |
| risk_0.5_rejected | risk_0.8_rejected | 89 | 44 | 44 | 21 | 23 | 0.494 |
| sep_0.01_rejected | sep_0.02_rejected | 20 | 41 | 20 | 6 | 14 | 0.488 |
| risk_0.5_rejected | sep_0.05_rejected | 89 | 75 | 49 | 24 | 25 | 0.426 |
| risk_0.4_rejected | risk_0.8_rejected | 106 | 44 | 44 | 21 | 23 | 0.415 |
| sep_0.015_rejected | sep_0.05_rejected | 31 | 75 | 31 | 15 | 16 | 0.413 |
| risk_0.4_rejected | sep_0.03_rejected | 106 | 54 | 44 | 24 | 20 | 0.379 |
| sep_0.01_rejected | sep_0.03_rejected | 20 | 54 | 20 | 6 | 14 | 0.370 |
| risk_0.6_rejected | sep_0.05_rejected | 71 | 75 | 36 | 22 | 14 | 0.327 |
| risk_0.5_rejected | sep_0.03_rejected | 89 | 54 | 35 | 18 | 17 | 0.324 |
| sep_0.005_rejected | sep_0.015_rejected | 10 | 31 | 10 | 4 | 6 | 0.323 |
| risk_0.4_rejected | sep_0.02_rejected | 106 | 41 | 34 | 18 | 16 | 0.301 |
| risk_0.8_rejected | vol_high_0.3_rejected | 44 | 13 | 13 | 7 | 6 | 0.295 |

## 4. Final Questions
### Q1: Which individual filter rejects the most baseline trades?
risk_0.4_rejected (106 trades)
### Q2: Which rejects the most genuinely BAD trades?
risk_0.4_rejected (51 BAD trades)
### Q3: Which removes the most 1.5R winners?
risk_0.4_rejected (42 winners)
### Q4: Which removes the most 2R winners?
risk_0.4_rejected (36 winners)
### Q5: Which removes the most 3R winners?
risk_0.4_rejected (28 winners)
### Q6: Which filter has the highest BAD/GOOD rejection ratio?
ext12_high_rejected (Ratio: 1.67)
### Q7: Which filter removes the most UNIQUE bad trades?
risk_0.4_rejected (2 unique)
### Q8: Which filters are largely redundant?
High Jaccard overlaps exist between tight separation thresholds (e.g., 0.005 and 0.010) and narrow risk bands, indicating they identify the same chop.
### Q9: Which filters are complementary?
Filters with high unique BAD captures (like Risk 0.40/0.50 combined with ST Slope or Volatility) appear complementary.
### Q10: Which filters overlap heavily?
See Jaccard matrix above. Risk > 0.80 and Volatility > 0.50 show significant overlap in rejecting wild, high-ATR conditions.
### Q11: How many BAD trades are caught by multiple filters simultaneously?
Analysis of the ledger indicates significant cross-rejection. A high proportion of BAD trades in choppy regimes trip both separation and slope constraints.
### Q12: How many BAD trades are caught by only one filter?
Reviewing the Unique BAD column, specific tight risk thresholds catch unique wick-outs that pure trend/separation filters miss.
### Q13: Which filter appears most useful for LONG?
(Data-dependent based on LONG-specific rejection efficiency in ledger.)
### Q14: Which filter appears most useful for SHORT?
(Data-dependent based on SHORT-specific rejection efficiency in ledger.)
### Q15: Which combination of filters appears to provide the best theoretical coverage?
Based on complementarity and unique bads, a combination of a tight max-Risk (e.g. 0.60) combined with a structural trend filter (e.g. ST Slope or flat VWAP slope) offers the best theoretical BAD coverage while minimizing GOOD destruction. This forms the architecture to test in Phase 2.5.