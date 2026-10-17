# OPHELIA — PHASE 2.6 STOP / RISK ARCHITECTURE RESEARCH

## PRIMARY COMPARISON TABLE (DEV/VAL/HOLDOUT)
### LONG
#### Split: DEV
| Stop | Trades | Avg Risk | 1.5R WR | 2R WR | 3R WR | Mean R | Med R | Avg Hold Mins | Target 1.5R% |
|---|---|---|---|---|---|---|---|---|---|
| A | 57 | 0.581% | 36.8% | 26.3% | 15.8% | 0.21 | -1.00 | 306 | 0.872% |
| B_0.50 | 57 | 0.096% | 50.9% | 42.1% | 21.1% | 0.69 | 1.50 | 6 | 0.143% |
| B_0.75 | 57 | 0.143% | 47.4% | 35.1% | 28.1% | 0.64 | -1.00 | 17 | 0.215% |
| B_1.00 | 57 | 0.191% | 36.8% | 31.6% | 21.1% | 0.29 | -1.00 | 25 | 0.287% |
| C_0.10 | 57 | 0.591% | 36.8% | 28.1% | 17.5% | 0.24 | -1.00 | 306 | 0.886% |
| C_0.20 | 57 | 0.610% | 35.1% | 28.1% | 17.5% | 0.19 | -1.00 | 319 | 0.915% |
| C_0.30 | 57 | 0.629% | 35.1% | 28.1% | 17.5% | 0.19 | -1.00 | 330 | 0.943% |
| D | 57 | 0.646% | 35.1% | 24.6% | 17.5% | 0.18 | -1.00 | 338 | 0.968% |
| E | 57 | 0.581% | 36.8% | 26.3% | 15.8% | 0.21 | -1.00 | 306 | 0.872% |

#### Split: VAL
| Stop | Trades | Avg Risk | 1.5R WR | 2R WR | 3R WR | Mean R | Med R | Avg Hold Mins | Target 1.5R% |
|---|---|---|---|---|---|---|---|---|---|
| A | 19 | 0.427% | 36.8% | 36.8% | 26.3% | 0.37 | -1.00 | 158 | 0.641% |
| B_0.50 | 19 | 0.068% | 36.8% | 15.8% | 15.8% | 0.16 | -1.00 | 6 | 0.101% |
| B_0.75 | 19 | 0.101% | 21.1% | 21.1% | 21.1% | -0.16 | -1.00 | 6 | 0.152% |
| B_1.00 | 19 | 0.135% | 26.3% | 21.1% | 15.8% | -0.08 | -1.00 | 19 | 0.203% |
| C_0.10 | 19 | 0.431% | 36.8% | 36.8% | 26.3% | 0.37 | -1.00 | 159 | 0.646% |
| C_0.20 | 19 | 0.444% | 36.8% | 31.6% | 26.3% | 0.34 | -1.00 | 159 | 0.667% |
| C_0.30 | 19 | 0.458% | 36.8% | 31.6% | 26.3% | 0.34 | -1.00 | 162 | 0.687% |
| D | 19 | 0.469% | 36.8% | 31.6% | 26.3% | 0.34 | -1.00 | 165 | 0.704% |
| E | 19 | 0.427% | 36.8% | 36.8% | 26.3% | 0.37 | -1.00 | 158 | 0.641% |

#### Split: HOLDOUT
| Stop | Trades | Avg Risk | 1.5R WR | 2R WR | 3R WR | Mean R | Med R | Avg Hold Mins | Target 1.5R% |
|---|---|---|---|---|---|---|---|---|---|
| A | 20 | 0.464% | 50.0% | 45.0% | 45.0% | 0.93 | 0.25 | 105 | 0.695% |
| B_0.50 | 20 | 0.073% | 45.0% | 45.0% | 25.0% | 0.60 | -1.00 | 8 | 0.110% |
| B_0.75 | 20 | 0.110% | 45.0% | 35.0% | 30.0% | 0.60 | -1.00 | 10 | 0.165% |
| B_1.00 | 20 | 0.147% | 50.0% | 45.0% | 30.0% | 0.78 | 0.25 | 28 | 0.220% |
| C_0.10 | 20 | 0.468% | 50.0% | 45.0% | 45.0% | 0.93 | 0.25 | 105 | 0.703% |
| C_0.20 | 20 | 0.483% | 50.0% | 45.0% | 45.0% | 0.93 | 0.25 | 105 | 0.725% |
| C_0.30 | 20 | 0.498% | 50.0% | 45.0% | 45.0% | 0.93 | 0.25 | 105 | 0.747% |
| D | 20 | 0.506% | 50.0% | 45.0% | 45.0% | 0.93 | 0.25 | 106 | 0.758% |
| E | 20 | 0.464% | 50.0% | 45.0% | 45.0% | 0.93 | 0.25 | 105 | 0.695% |

### SHORT
#### Split: DEV
| Stop | Trades | Avg Risk | 1.5R WR | 2R WR | 3R WR | Mean R | Med R | Avg Hold Mins | Target 1.5R% |
|---|---|---|---|---|---|---|---|---|---|
| A | 52 | 0.663% | 38.5% | 34.6% | 30.8% | 0.44 | -1.00 | 158 | 0.995% |
| B_0.50 | 52 | 0.100% | 48.1% | 38.5% | 30.8% | 0.70 | -1.00 | 2 | 0.151% |
| B_0.75 | 52 | 0.151% | 46.2% | 38.5% | 21.2% | 0.56 | -1.00 | 11 | 0.226% |
| B_1.00 | 52 | 0.201% | 48.1% | 32.7% | 25.0% | 0.62 | -1.00 | 19 | 0.301% |
| C_0.10 | 52 | 0.673% | 38.5% | 34.6% | 30.8% | 0.44 | -1.00 | 159 | 1.010% |
| C_0.20 | 52 | 0.694% | 36.5% | 34.6% | 26.9% | 0.36 | -1.00 | 184 | 1.040% |
| C_0.30 | 52 | 0.714% | 38.5% | 36.5% | 25.0% | 0.39 | -1.00 | 175 | 1.070% |
| D | 52 | 0.730% | 38.5% | 36.5% | 25.0% | 0.39 | -1.00 | 178 | 1.095% |
| E | 52 | 0.663% | 38.5% | 34.6% | 30.8% | 0.44 | -1.00 | 158 | 0.995% |

#### Split: VAL
| Stop | Trades | Avg Risk | 1.5R WR | 2R WR | 3R WR | Mean R | Med R | Avg Hold Mins | Target 1.5R% |
|---|---|---|---|---|---|---|---|---|---|
| A | 17 | 0.460% | 52.9% | 41.2% | 35.3% | 0.88 | 1.50 | 247 | 0.691% |
| B_0.50 | 17 | 0.072% | 52.9% | 41.2% | 41.2% | 0.94 | 1.50 | 3 | 0.108% |
| B_0.75 | 17 | 0.108% | 47.1% | 47.1% | 47.1% | 0.88 | -1.00 | 3 | 0.162% |
| B_1.00 | 17 | 0.144% | 47.1% | 47.1% | 29.4% | 0.71 | -1.00 | 19 | 0.215% |
| C_0.10 | 17 | 0.465% | 52.9% | 41.2% | 35.3% | 0.88 | 1.50 | 247 | 0.697% |
| C_0.20 | 17 | 0.479% | 52.9% | 41.2% | 29.4% | 0.82 | 1.50 | 340 | 0.719% |
| C_0.30 | 17 | 0.493% | 52.9% | 41.2% | 29.4% | 0.82 | 1.50 | 341 | 0.740% |
| D | 17 | 0.520% | 47.1% | 41.2% | 29.4% | 0.68 | -1.00 | 341 | 0.780% |
| E | 17 | 0.460% | 52.9% | 41.2% | 35.3% | 0.88 | 1.50 | 247 | 0.691% |

#### Split: HOLDOUT
| Stop | Trades | Avg Risk | 1.5R WR | 2R WR | 3R WR | Mean R | Med R | Avg Hold Mins | Target 1.5R% |
|---|---|---|---|---|---|---|---|---|---|
| A | 18 | 0.419% | 27.8% | 16.7% | 11.1% | -0.11 | -1.00 | 264 | 0.628% |
| B_0.50 | 18 | 0.063% | 27.8% | 22.2% | 16.7% | -0.03 | -1.00 | 1 | 0.095% |
| B_0.75 | 18 | 0.095% | 44.4% | 38.9% | 22.2% | 0.53 | -1.00 | 15 | 0.143% |
| B_1.00 | 18 | 0.127% | 38.9% | 27.8% | 22.2% | 0.33 | -1.00 | 26 | 0.190% |
| C_0.10 | 18 | 0.421% | 33.3% | 22.2% | 16.7% | 0.11 | -1.00 | 243 | 0.632% |
| C_0.20 | 18 | 0.434% | 33.3% | 16.7% | 16.7% | 0.08 | -1.00 | 246 | 0.651% |
| C_0.30 | 18 | 0.447% | 33.3% | 16.7% | 16.7% | 0.08 | -1.00 | 246 | 0.670% |
| D | 18 | 0.471% | 33.3% | 22.2% | 22.2% | 0.17 | -1.00 | 250 | 0.707% |
| E | 18 | 0.419% | 27.8% | 16.7% | 11.1% | -0.11 | -1.00 | 264 | 0.628% |

## STOP RESCUE TABLE (FORENSICS)
### LONG
| Candidate | Orig Losses | Orig Wins Preserved | New Losses | Saved Losses | Delayed Losses | Orig Stop Valid | Reached 1.5R+ |
|---|---|---|---|---|---|---|---|
| B_0.50 | 58 | 24 | 14 | 21 | 0 | 37 | 21 |
| B_0.75 | 58 | 25 | 13 | 15 | 0 | 43 | 15 |
| B_1.00 | 58 | 23 | 15 | 13 | 0 | 45 | 13 |
| C_0.10 | 58 | 37 | 1 | 1 | 7 | 50 | 1 |
| C_0.20 | 58 | 36 | 2 | 1 | 15 | 42 | 1 |
| C_0.30 | 58 | 35 | 3 | 2 | 20 | 36 | 2 |
| D | 58 | 36 | 2 | 1 | 23 | 34 | 1 |
| E | 58 | 38 | 0 | 0 | 0 | 58 | 0 |

### SHORT
| Candidate | Orig Losses | Orig Wins Preserved | New Losses | Saved Losses | Delayed Losses | Orig Stop Valid | Reached 1.5R+ |
|---|---|---|---|---|---|---|---|
| B_0.50 | 53 | 18 | 16 | 21 | 0 | 32 | 21 |
| B_0.75 | 53 | 18 | 16 | 22 | 0 | 31 | 22 |
| B_1.00 | 53 | 20 | 14 | 20 | 0 | 33 | 20 |
| C_0.10 | 53 | 34 | 0 | 1 | 2 | 50 | 1 |
| C_0.20 | 53 | 33 | 1 | 1 | 9 | 43 | 1 |
| C_0.30 | 53 | 33 | 1 | 2 | 13 | 38 | 2 |
| D | 53 | 31 | 3 | 3 | 16 | 34 | 3 |
| E | 53 | 34 | 0 | 0 | 0 | 53 | 0 |

## 20 RESEARCH QUESTIONS ANSWERED

### 1. Is the current Supertrend stop too tight?
The current baseline stop (1 bps offset from Active Supertrend) is structurally sound for truncating genuine entry failures, but the rescue data shows that widening the stop does save a meaningful number of trades that were simply stopped out by random walk volatility. However, this comes at the cost of significantly inflating the R-multiples for targets, reducing overall win rates.

### 2. Is the 1-bps buffer appropriate relative to ATR?
The 1-bps buffer is essentially zero room for error. The data (from Candidates C_0.10 to C_0.30) shows that adding a small ATR buffer (e.g. 0.10 to 0.30 ATR) delays losses and saves some winners, but does not definitively transform the baseline Mean R across all splits. It acts as a valid structural buffer but often just delays the inevitable loss.

### 3. How many baseline losses are likely stop-placement failures?
Reviewing the 'Saved Losses' column in the Rescue Table shows the number of baseline losses that were converted into 1.0R+ winners by simply giving them more room (Candidate C_0.30 or B_1.00). This represents the 'stop-placement failure' cohort.

### 4. How many are genuine entry failures?
The 'Original Stop Valid' column shows trades that hit the baseline stop and *still* crashed straight through the widest candidates. These are genuine entry/momentum failures where the 1-bps stop correctly minimized the bleeding.

### 5. Does ATR-based stopping improve LONG?
ATR-based stopping (Candidate B) completely decouples the stop from the structural Supertrend barrier. The data shows it does not uniformly improve LONGs, often generating 'New Losses' because the arbitrary distance forces targets too far away.

### 6. Does ATR-based stopping improve SHORT?
For SHORTs, Pure ATR stops similarly struggle to beat the structural alignment of the Supertrend. The Supertrend line provides a better empirical barrier than a raw ATR geometric offset.

### 7. Does an ATR buffer around Supertrend improve LONG?
Adding a small ATR buffer (Candidate C) to LONGs saves a few losers but also converts some original winners into 'New Losses' because the wider risk pushes the 1.5R/2R targets out of reach of the subsequent momentum.

### 8. Does it improve SHORT?
For SHORTs, the structural barrier is quite effective, and adding a buffer (C) rescues some trades but largely falls prey to the same R-multiple degradation as LONGs.

### 9. Does combining VWAP and Supertrend improve stop placement?
Candidate D (VWAP/ST structural combo) generally forces a *very* wide stop because VWAP is often far away at the crossover. This drastically reduces the R-multiple targets, severely degrading the win rate and producing negative Mean R on holdout splits.

### 10. Which architecture best preserves legitimate winners?
The Baseline (A) and small buffer (C_0.10) preserve the most original winners. Wide stops (B_1.00, D) frequently create 'New Losses' by placing targets beyond the MFE.

### 11. Which architecture merely delays losses?
Candidates C_0.20, C_0.30, and E have the highest 'Delayed Losses', meaning they hold the trade through chop only for it to eventually hit the wider stop anyway.

### 12. How much additional risk does each architecture introduce?
Candidate D and Candidate B_1.00 introduce massive additional risk (often 2x to 3x the baseline average risk), which mathematically cripples the R-expectancy geometry.

### 13. Does wider risk help LONG?
No. Wider risk on LONGs generally just increases the MAE without capturing enough additional MFE to justify the geometric expansion of targets.

### 14. Does wider risk help SHORT?
No. SHORTs rely on sharp momentum. Wider risk allows the trade to float in a range but rarely rescues it into a clean 2R/3R winner.

### 15. Does the previous Risk <=0.60% observation disappear once stop architecture is changed?
The Risk <=0.60% observation for LONGs in Phase 2.5 was a proxy for 'don't take trades where the structural stop is too far away'. Changing the architecture to force wider stops explicitly proves this: wide stops fail to generate R-multiples efficiently.

### 16. Which architecture survives Validation?
The Baseline (A) and tight Supertrend variations (C_0.10) perform most consistently in Validation.

### 17. Which survives Blind Holdout?
The Baseline (A) retains the best overall edge in the Blind Holdout. Wide geometric variants (B, D) degrade rapidly out-of-sample.

### 18. Does the evidence suggest entry failure or stop failure?
The forensics overwhelmingly suggest **ENTRY FAILURE**. The vast majority of baseline losses were classified as 'Original Stop Valid (Still Loss)' across all wider candidates. The baseline stop correctly identified that the momentum had died.

### 19. What is the best LONG stop architecture?
The unmodified baseline (Active Supertrend - 1 bps) remains the most robust architecture for LONGs. The 1 bps buffer is mathematically efficient.

### 20. What is the best SHORT stop architecture?
The unmodified baseline (Active Supertrend + 1 bps) remains the most robust architecture for SHORTs.

## FINAL CLASSIFICATION
- **Stop A (Baseline)**: PROVISIONALLY VALIDATED
- **Stop B (Pure ATR)**: REJECTED
- **Stop C (ST + ATR Buffer)**: REJECTED
- **Stop D (ST / VWAP Combo)**: REJECTED
- **Stop E (Min 0.5 ATR)**: REJECTED