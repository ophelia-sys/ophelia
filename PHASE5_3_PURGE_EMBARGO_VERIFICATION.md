# PHASE 5.3 PURGE / EMBARGO VERIFICATION

**Date:** 2026-08-14

## 1. Concrete Index-Level Verification

Let's assume a dataset of `n_samples = 4000`, with `n_folds = 3`, `Target Horizon = 60`, and `embargo = 60` using the `PurgedWalkForwardValidation` splitter.

The `fold_size` evaluates to $4000 / (3 + 1) = 1000$.

### FOLD 0
- **Test Start:** 1000
- **Test End:** 2000
- **Train End:** $1000 - 60 = 940$
- **Train Indices:** `[0, ..., 939]`
- **Test Indices:** `[1000, ..., 1999]`
- **Purged Indices (Dropped):** `[940, ..., 999]` (Length = 60)

**Label Overlap Proof:**
- The final training index is `t = 939`. Its target label `y_939` evaluates the price path from `t+1 (940)` to `t+60 (999)`.
- The first test index is `t = 1000`.
- **Max Training Label End:** 999.
- **Min Validation Start:** 1000.
- `max(training_label_end) < min(validation_label_start)` -> **PASS**. No training label overlaps the validation period.

### FOLD 1
- **Test Start:** 2000
- **Test End:** 3000
- **Train End:** $2000 - 60 = 1940$
- **Train Indices:** `[0, ..., 1939]`
- **Test Indices:** `[2000, ..., 2999]`
- **Purged Indices (Dropped):** `[1940, ..., 1999]` (Length = 60)

**Label Overlap Proof:**
- The final training index is `t = 1939`. Its target label `y_1939` evaluates the price path from `1940` to `1999`.
- The first test index is `2000`.
- **Max Training Label End:** 1999.
- **Min Validation Start:** 2000.
- `max(training_label_end) < min(validation_label_start)` -> **PASS**. No training label overlaps the validation period.

*(Note: Fold 1's training set incorporates the test indices from Fold 0 [1000 to 1939], which is mathematically safe because Fold 1 is treated as a separate chronological experiment, and the target look-ahead for `t=1939` strictly ends before `t=2000`.)*

### FOLD 2
- **Test Start:** 3000
- **Test End:** 4000
- **Train End:** $3000 - 60 = 2940$
- **Train Indices:** `[0, ..., 2939]`
- **Test Indices:** `[3000, ..., 3999]`
- **Purged Indices (Dropped):** `[2940, ..., 2999]` (Length = 60)

**Label Overlap Proof:**
- The final training index is `t = 2939`. Its target label `y_2939` evaluates the price path from `2940` to `2999`.
- The first test index is `3000`.
- **Max Training Label End:** 2999.
- **Min Validation Start:** 3000.
- `max(training_label_end) < min(validation_label_start)` -> **PASS**. No training label overlaps the validation period.

## 2. Splitter Implementation Analysis
The repository class `PurgedWalkForwardValidation` (in `research/pipeline/validation.py`) enforces strict chronological expanding-window walk-forward splits.
- **Purge:** It enforces `train_end = test_start - self.embargo`, effectively executing the **Purge** requirement (dropping overlapping labels prior to the test set).
- **Embargo:** Because it uses an expanding window where the training set strictly precedes the test set, there are no training observations *after* the test set. Therefore, there is no risk of test-labels leaking into subsequent training observations within the same split. A formal "Embargo" (dropping samples after the test set) is structurally implicit and completely safe.

## 3. Maximum Historical Lookback
- **CVD Maximum Lookback:** 288 bars (from `cvd_zscore_1h` using a 1-hour/12-bar CVD delta over 24 hours).
- **Target Horizon:** 60 bars.
- **Causality:** The 288-bar lookback is strictly historical and causal at $T_{decision}$. It relies solely on `transact_time < T_{decision}`. It does not introduce future leakage and requires no additional purge.

## 4. Final Assessment
- **Purge:** 60
- **Embargo:** 60 (Implicitly safe via strictly expanding train-before-test walk-forward logic)
- **Target Horizon:** 60
- **Maximum Feature Lookback:** 288
- **Is 60/60 Sufficient?:** YES
- **Exact splitter implementation verified:** PASS
- **Label-overlap test:** PASS
- **Feature causality test:** PASS
- **Preprocessing isolation test:** PASS (Preprocessing fits are isolated inside the pipeline to the respective `train_idx` per fold).
