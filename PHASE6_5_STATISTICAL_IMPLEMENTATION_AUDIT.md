# PHASE 6.5 STATISTICAL IMPLEMENTATION AUDIT

## 1. Current Repository Implementations
The current implementations present in `research/phase6/statistics.py` are:
- `calendar_newey_west_se`: A custom HAC standard error estimator applied explicitly to an equal-weighted uniform chronological calendar-time portfolio.
- `calendar_block_bootstrap`: A stationary block bootstrap on a calendar grid using geometric distribution block lengths.
- (Missing) `diebold_mariano_test` and Block Permutation.

## 2. Historical Implementations
The actual statistical framework frozen in Phase 5.3 (and carried through Phase 6.1 - 6.4) was found in `research/experiments/exp_phase5_3_ml_stats.py`:
- `dm_test`: Diebold-Mariano test wrapping `statsmodels.api.OLS` fit with `cov_type='HAC'` and `cov_kwds={'maxlags': 59}` applied to `(loss_base - loss_aug)`. 
- `block_bootstrap`: Pure non-overlapping block bootstrap (NumPy slicing/concatenation) using a fixed block length of 60.
- `block_permutation`: Non-overlapping block permutation of only the Augmented model's predictions, tested explicitly using empirical `(better_count + 1) / (iterations + 1)` against `log_loss`.

## 3. Mathematical Comparison

### A. Newey-West / HAC
- **Historical**: Standard HAC variance wrapper using Statsmodels `OLS(d, const).fit(cov_type='HAC')`. Estimates variance of the mean of `d` (difference in LogLoss) handling overlaps properly when indices are chronologically uniform 5m bars.
- **Current (`calendar_newey_west_se`)**: Custom matrix math calculating autocovariances directly on a grouped Calendar Time Portfolio grid.
- **Verdict: DIFFERENT IMPLEMENTATION BUT SAME STATISTIC** (The underlying math is both standard Newey-West, but the data structures they operate on—raw chronological arrays vs Calendar portfolios—are vastly different).

### B. Block Bootstrap
- **Historical**: Fixed-length (60), non-overlapping block resampling.
- **Current (`calendar_block_bootstrap`)**: Stationary block bootstrap (random length via geometric distribution).
- **Verdict: NOT EQUIVALENT**.

### C. Block Permutation
- **Historical**: Permutes non-overlapping blocks (length 60) of the test probabilities.
- **Current**: Missing entirely from `phase6/statistics.py`.
- **Verdict: NOT EQUIVALENT** (Missing).

### D. Diebold-Mariano
- **Historical**: Explicit `dm_test` computing `loss1 - loss2` with `OLS` HAC.
- **Current**: Missing. (Often developers manually implemented `mean/se` using `newey_west_se` in older scripts, but `exp_phase5_3_ml_stats.py` shows it was centralized).
- **Verdict: NOT EQUIVALENT**.

## 4. Numerical Reproduction Comparison
We executed the historical statistical functions exactly as defined in `exp_phase5_3_ml_stats.py` over the saved OOS artifacts:
- `phase6_1_stage_b_ffd_oos_preds.pkl` (Phase 6.1 FFD)

**Results (BTCUSDT Example):**
- LogLoss: Base 0.617761 (Frozen: 0.617761) -> **EXACT MATCH**
- Brier: Base 0.214122 (Frozen: 0.214122) -> **EXACT MATCH**
- DM t-stat: -11.1918 (Frozen: -11.1918) -> **EXACT MATCH**
- DM p-val: 4.4715e-29 (Frozen: 4.4715e-29) -> **EXACT MATCH**
- Boot Mean: -0.002730 (Frozen: -0.002730) -> **EXACT MATCH**
- Perm p-val: 0.0010 (Frozen: 0.0010) -> **EXACT MATCH**
- BH-FDR: 2.6829e-28 (Frozen: 2.6829e-28) -> **EXACT MATCH**

All 6 symbols for the Phase 6.1 FFD experiment reproduced mathematically to 6 decimal places for every single metric.

## 5. Equivalence Verdict
The current `calendar_*` implementations in `research/phase6/statistics.py` are **NOT EQUIVALENT** to the historical frozen pipeline. They represent a specialized event-study methodology rather than the standard chronological time-series evaluation required for the frozen LightGBM predictions.

## 6. Required Corrective Action
- Do not delete `calendar_*` functions from `statistics.py` as they may be valid for Phase 6.1's specific event study requirements.
- Create `research/phase6/statistics_frozen.py` containing the exact mathematical code extracted from `exp_phase5_3_ml_stats.py`.
- Ensure all future Phase 6.5 independent audits and scripts use `statistics_frozen.py` exclusively.
