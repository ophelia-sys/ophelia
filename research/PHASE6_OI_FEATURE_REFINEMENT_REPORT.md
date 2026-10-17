# PHASE6 OI FEATURE MATHEMATICAL REFINEMENT REPORT

## 1. Problem Statement & Source-Frequency Audit
The Open Interest (OI) feature generated explosive `Z_DeltaOI` values during the initial Phase 6 run. 
A forensic audit confirmed that Binance UM metrics (the source of historical OI) update strictly every **5 minutes**, while the research decision grid operates on a **1-minute** interval.

When `DeltaOI` is calculated natively on the 1-minute grid ($OI_t - OI_{t-1}$), approximately 80% of all observations are exactly `0`. Over a 500-minute rolling window, the Median Absolute Deviation (MAD) collapses to exactly `0.0`. The `max(MAD, 1e-6)` safety guard correctly prevents division-by-zero, but forces the denominator to `1e-6`, inflating legitimate OI updates (which occur every 5th minute) into massive Z-scores (e.g. 50,000,000).

This document establishes the mathematically correct representation of a 5-minute process on a 1-minute decision grid.

## 2. Candidate Mathematical Definitions

Four candidate definitions were implemented, run against a synthetic dataset (to prove causality), and evaluated empirically on the `BTCUSDT-1m-2022-01` small sample.

**Frozen Constraint Maintained**: For all valid definitions, the current observation does NOT enter its own normalization window.

### Definition A (Native 5m Computation + Causal Mapping)
- **Formula**: Compute $DeltaOI_{5m} = OI_{t} - OI_{t-5m}$ on the strict 5m event grid. Compute Robust Z-score over W=100 (500 minutes) on the 5m grid. Causally forward-fill the Z-score to the 1m grid.
- **Semantic Meaning**: The standardized magnitude of the *latest actual OI update* relative to the last 500 minutes of updates.

### Definition B (Native 5m + Standard Deviation Normalization)
- **Formula**: Same as A, but replacing Median/MAD with Mean/StdDev.
- **Semantic Meaning**: Same as A, testing whether a non-robust normalizer handles sparse updates better.

### Definition C (Native 1m + Explicit Zero-Dispersion Policy)
- **Formula**: Compute $DeltaOI_{1m} = OI_{t} - OI_{t-1}$. Compute Robust Z-score over W=500. If `MAD == 0`, output `0.0` when `DeltaOI == 0`, and `NaN` (or `ZERO_DISPERSION`) when `DeltaOI != 0`.
- **Semantic Meaning**: The strict 1m change, failing explicitly when dispersion is unmeasurable.

### Definition D (Dense Rolling 5m on 1m Grid)
- **Formula**: Compute $DeltaOI_{roll} = OI_t - OI_{t-5}$ evaluated at every 1-minute interval. Compute Robust Z-score over W=500 natively on the 1m grid.
- **Semantic Meaning**: The trailing 5-minute change, evaluated continuously.

## 3. Empirical Comparison (BTCUSDT 2022-01)

| Metric | Def A (5m Native) | Def B (5m StdDev) | Def C (1m Strict) | Def D (Dense 1m) |
| :--- | :--- | :--- | :--- | :--- |
| **Data Frequency** | 5m mapped to 1m | 5m mapped to 1m | 1m Native | 1m Native (5m lookback) |
| **Observation Count** | 44,135 | 44,135 | 35,312 | 44,135 |
| **NaN / Unavailable Rate**| 1.13% | 1.13% | **20.90%** | 1.13% |
| **Delta Non-Zero Rate** | 100.00% | 100.00% | **0.00%** | 100.00% |
| **Zero-Dispersion Freq** | 0% | 0% | 100% | 0% |
| **Min / Max** | -27.85 / 18.47 | -16.19 / 10.41 | 0.00 / 0.00 | -27.85 / 19.07 |
| **Median / MAD** | 0.02 / 0.68 | 0.07 / 0.37 | 0.00 / 0.00 | 0.01 / 0.67 |
| **Autocorrelation (Lag 1)**| 0.8024 | 0.8022 | NaN | 0.8012 |

### Detailed Autocorrelation & Effective Sample Size Analysis

**Definition D** exhibits a massive "Repeated-Value Factor" of **80.00%**. Because the 5m change is evaluated on a 1m grid, 4 out of 5 consecutive observations contain the exact same identical mathematical information.
While this mathematically circumvents the Zero-MAD collapse, it artificially inflates the normalization Effective Sample Size ($N_{eff} = 500$) with duplicated information. 

**Definition A** utilizes a true $N_{eff} = 100$ independent 5-minute innovations. Notice that the resulting distributions (Min, Max, Autocorrelation) between A and D are mathematically isomorphic (almost identical). The median of a sequence repeated 5 times is the same as the median of the original sequence. 
However, **Definition A** is semantically honest about the underlying degrees of freedom.

**Definition C** demonstrates the diagnostic failure. Because `MAD` is 0, any time an actual non-zero OI event arrives (every 5th minute), it triggers the zero-dispersion guard and returns `NaN`. Therefore, exactly 100% of the non-zero observations are purged, leaving a 20.9% NaN rate and only `0.0` values remaining.

## 4. Causality & Synthetic Verification

All definitions were verified against a synthetic reference test sequence simulating:
1. Exact 5m interval updates.
2. Sparse updates (missing data).
3. Constant OI.

- Future leakage was strictly `0`.
- All methods cleanly isolated the $t-1$ normalization window, proving that the current 5m OI spike cannot suppress its own Z-score.

## 5. Final Classifications

1. **Definition A: MATHEMATICALLY PREFERRED**
   - It respects the native 5m data generating process.
   - It leverages the frozen Robust Z-Score math without creating zero-MAD explosions.
   - It correctly computes dispersion over actual independent innovations.
   
2. **Definition B: REJECTED**
   - While stable, dropping robust statistics (Median/MAD) for Mean/StdDev violates the Phase 6 frozen math requirements unnecessarily when Definition A already solves the problem robustly.
   
3. **Definition C: DIAGNOSTIC ONLY**
   - Useful for proving the failure mode (zero-MAD), but destroys all empirical utility by turning the actual signal events into NaNs.
   
4. **Definition D: REJECTED** (MATHEMATICALLY ACCEPTABLE but Semantically Flawed)
   - While it elegantly avoids zero-MAD without explicit extraction, it artificially repeats identical information 5 times in the normalization window. Definition A achieves the exact same Z-score distribution with semantic honesty.

## 6. Recommended Action & Fix
The codebase should be updated to implement **Definition A** for historical Open Interest normalization.

Specifically, the normalization pipeline must:
1. Extract the unique `oi_timestamp` events.
2. Calculate the robust Z-score over a window of $W_{events} = W_{minutes} / 5$ (e.g., W=100).
3. Causally merge the resulting Z-score back onto the 1m decision grid.

*This concludes the refinement audit. The dataset is ready for full reconstruction upon human approval.*
