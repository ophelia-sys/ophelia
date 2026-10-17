# OPHELIA — PHASE 2.7A RESEARCH REPORT
## FACTOR 3.5 FORENSIC REPLICATION
Generated: 2026-08-22 06:15:50

## 1. GROSS SIGNAL COUNT COMPARISON
| Supertrend | Total Trades | LONG | SHORT | Mean R | 1.5R Win Rate |
|---|---|---|---|---|---|
| Factor 3.0 | 177 | 96 | 81 | -0.025R | 39.0% |
| Factor 3.5 | 157 | 83 | 74 | -0.045R | 38.2% |
| Factor 4.0 | 121 | 58 | 63 | -0.008R | 39.7% |

## 2. SIGNAL MATCHING (Factor 3.5 vs Factor 4.0)
- **Matches found**: 100
- **Avg Delay (Factor 4 relative to 3.5)**: 12.7 mins
- **Factor 3.5 Unique Trades**: 50
- **Factor 3.5 False Flips (MFE < 1R)**: 31

## 3. NOISE-FILTER FORENSICS (Factor 3.5)
| Direction | Candidate | BAD Removed | Addl BAD vs Risk | GOOD Removed | Addl GOOD Lost vs Risk | Mean R |
|---|---|---|---|---|---|---|
| LONG | Risk + ST Slope | 0 | -19 | 3 | -12 | -0.125 |
| LONG | Risk + VWAP Slope | 0 | -19 | 0 | -15 | -0.066 |
| LONG | Risk + Separation | 3 | -16 | 1 | -14 | -0.019 |
| SHORT | Risk + ST Slope | 3 | -15 | 0 | -18 | 0.021 |
| SHORT | Risk + VWAP Slope | 0 | -18 | 0 | -18 | -0.020 |
| SHORT | Risk + Separation | 2 | -16 | 2 | -16 | -0.036 |
| COMBINED | Risk + ST Slope | 3 | -34 | 3 | -30 | -0.056 |
| COMBINED | Risk + VWAP Slope | 0 | -37 | 0 | -33 | -0.045 |
| COMBINED | Risk + Separation | 5 | -32 | 3 | -30 | -0.027 |

## 4. STOP ARCHITECTURE RESCUE (Factor 3.5)
| Direction | Stop Candidate | Saved Losses (Converted to Win) | New Losses | Mean R of Saved |
|---|---|---|---|---|
| LONG | B_0.50 | 17 | 12 | 2.294 |
| LONG | B_0.75 | 14 | 11 | 2.143 |
| LONG | B_1.00 | 12 | 10 | 2.167 |
| LONG | C_0.10 | 0 | 0 | 0.000 |
| LONG | C_0.20 | 0 | 0 | 0.000 |
| LONG | C_0.30 | 0 | 0 | 0.000 |
| LONG | D | 0 | 2 | 0.000 |
| LONG | E | 0 | 0 | 0.000 |
| SHORT | B_0.50 | 22 | 14 | 2.295 |
| SHORT | B_0.75 | 19 | 13 | 2.316 |
| SHORT | B_1.00 | 15 | 14 | 2.300 |
| SHORT | C_0.10 | 0 | 1 | 0.000 |
| SHORT | C_0.20 | 1 | 2 | 3.000 |
| SHORT | C_0.30 | 1 | 2 | 3.000 |
| SHORT | D | 2 | 4 | 3.000 |
| SHORT | E | 0 | 0 | 0.000 |

## 5. FINAL CLASSIFICATIONS
To be answered manually by the researcher based on the above tables.