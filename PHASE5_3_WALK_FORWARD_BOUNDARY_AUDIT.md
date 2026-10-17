# PHASE 5.3 WALK-FORWARD BOUNDARY AUDIT

**Date:** 2026-08-14

## 1. Exact Splitter Implementation Verification

The current repository implementation of `PurgedWalkForwardValidation` (in `research/pipeline/validation.py`) enforces strict chronological expanding-window walk-forward cross-validation. 

The implementation logic is:
```python
test_start = (i + 1) * fold_size
test_end = (i + 2) * fold_size
train_end = test_start - self.embargo
train_idx = np.arange(0, train_end)
test_idx = np.arange(test_start, test_end)
```
*Note on Terminology:* The parameter named `self.embargo` in the code actually implements a **Purge** (dropping training observations prior to the test set whose labels overlap the test set). Because the training set is strictly expanding from index 0, there are no training observations *after* the test set. Thus, a structural **Embargo** is naturally achieved by the strictly expanding historical nature of the splits.

For a dataset of $N=4000$, $n\_folds=3$, $fold\_size=1000$, and parameter `embargo=60`:

### FOLD 0
- **Train Start:** 0
- **Train End:** $1000 - 60 - 1 = 939$
- **Purge Start:** 940
- **Purge End:** 999
- **Test Start:** 1000
- **Test End:** 1999
- **Embargo Start:** N/A (Train is strictly historical)
- **Embargo End:** N/A

### FOLD 1
- **Train Start:** 0
- **Train End:** $2000 - 60 - 1 = 1939$
- **Purge Start:** 1940
- **Purge End:** 1999
- **Test Start:** 2000
- **Test End:** 2999
- **Embargo Start:** N/A
- **Embargo End:** N/A

### FOLD 2
- **Train Start:** 0
- **Train End:** $3000 - 60 - 1 = 2939$
- **Purge Start:** 2940
- **Purge End:** 2999
- **Test Start:** 3000
- **Test End:** 3999
- **Embargo Start:** N/A
- **Embargo End:** N/A

==================================================
## A. TRAIN → TEST LABEL SAFETY

The target `target_60_up_10` evaluates the path from $t+1$ to $t+60$.
For any training observation $t$, `label_end(t) = t + 60`.
For the final training observation $t_{train\_max} = test\_start - purge - 1$.
`label_end(t_{train\_max}) = test\_start - purge - 1 + 60`.

If `purge = 60`:
`label_end(t_{train\_max}) = test\_start - 60 - 1 + 60 = test\_start - 1`.

Therefore, `max(label_end(train)) = test_start - 1`.
Since `test_start - 1 < min(test_start)`, we prove:
`max(label_end(train)) < min(test_start)`.
**RESULT: PASS**

==================================================
## B. TEST → SUBSEQUENT TRAINING SAFETY

The implementation `train_idx = np.arange(0, train_end)` strictly selects indices from $0$ up to $test\_start - purge$. 
It **never** places observations occurring *after* a test interval into a later training interval. 
- **PURGE:** Protects the test set from overlapping with prior training labels.
- **EMBARGO:** Prevents observations immediately *following* the test set from entering a later training set.
Because the training sets are strictly historical/expanding and contain NO post-test observations, an Embargo parameter is structurally unnecessary for this specific splitter. Leakage from the future is impossible.
**RESULT: PASS**

==================================================
## C. SYNTHETIC BOUNDARY TEST

Assume:
- `target_horizon = 60`
- `test_start = 1061`

If `purge = 60` (so `train_end = 1000` inclusive):
- `label(1000)` evaluates prices $1001 \dots 1060$.
- `label_end(1000) = 1060`.
- $1060 < 1061$ (test_start). **SAFE.**

**Failing Case:**
If `purge = 59` (so `train_end = 1001` inclusive):
- `label(1001)` evaluates prices $1002 \dots 1061$.
- `label_end(1001) = 1061`.
- $1061 \ge 1061$ (test_start). **LEAKAGE DETECTED. FAILS.**
**RESULT: PASS**

==================================================
## D. 288-BAR FEATURE LOOKBACK

The maximum feature lookback in the registry is 288 bars (for `cvd_zscore_1h`, which normalizes a 12-bar delta over a 288-bar rolling window).
- **Causality:** This lookback is purely historical. The rolling statistic is computed using only $[t-287, \dots, t]$ and never $[t-287, \dots, t+N]$.
- **Purge Requirement:** Because it accesses strictly prior data, it does not require an additional purge or embargo. It does not look into the future.
**RESULT: PASS**

==================================================
## E. PREPROCESSING

All standardization (`StandardScaler`), feature transformation, and hyperparameter selection fit operations `.fit()` must be executed exclusively on the `train_idx` subset. The fitted state is then applied to the validation/OOS folds via `.transform()`.
Test assertions have been updated to intercept and fail any pipeline that attempts to `.fit()` or `.fit_transform()` on the combined or test data.
**RESULT: PASS**

==================================================
## F. TARGET GENERATION

The `target_60_up_10` label definition explicitly computes returns and barrier hits on the forward price vector $P[t+1 \dots t+60]$. By definition, it evaluates strictly causal forward returns and never $t+61$ or later.
The unit tests now include a strict maximum offset boundary assertion ensuring target calculation arrays cannot overrun the $t+60$ index.
**RESULT: PASS**
