# PHASE 6.5 STATISTICS FREEZE

**Status: AUTHORIZED**
**Date: 2026-08-16**

The Phase 6.5 statistical evaluation framework has been fully reconstructed, audited, and independently verified against historical OOS prediction artifacts.

The methodology frozen in Phase 5.3 is now permanently restored and mathematically verified to produce identical results to the previously reported historical audits.

## 1. Frozen DM / HAC Specification
**VERIFIED**
- **Definition:** `loss1 - loss2` where loss is the sample-wise LogLoss. A positive DM means the augmented model is superior (lower loss).
- **HAC Estimator:** Standard Newey-West variance via `statsmodels.api.OLS` `fit(cov_type='HAC')`.
- **Lags:** `maxlags = 59` (60 periods total).
- **Sign Convention:** Positive t-stat = Augmented Model is better.

## 2. Frozen Bootstrap Specification
**VERIFIED**
- **Methodology:** Standard, Fixed-length Non-Overlapping Block Bootstrap.
- **Block Length:** 60 periods.
- **Replications:** 1000.
- **Seed:** 42.
- **Statistic:** Mean difference in sample-wise LogLoss.

## 3. Frozen Permutation Specification
**VERIFIED**
- **Methodology:** Non-overlapping Block Permutation.
- **Block Length:** 60 periods.
- **Iterations:** 1000.
- **Seed:** 42.
- **Action:** Shuffles the blocks of the *Augmented* model's predictions while holding the target `y` and `Base` predictions constant.
- **p-value formula:** Exact empirical probability: `(better_count + 1) / (iterations + 1)`.

## 4. Frozen BH-FDR Specification
**VERIFIED**
- **Methodology:** Benjamini-Hochberg False Discovery Rate via `statsmodels.stats.multitest.multipletests(method='fdr_bh')`.
- **Input:** Diebold-Mariano p-values.

## 5. Summary Report

- **STATISTICAL RECONSTRUCTION:** PASS
- **HISTORICAL REPRODUCTION:** PASS
- **FROZEN DM:** VERIFIED
- **FROZEN BOOTSTRAP:** VERIFIED
- **FROZEN PERMUTATION:** VERIFIED
- **FROZEN BH-FDR:** VERIFIED
- **PHASE 6.5:** AUTHORIZED
- **CURRENT BENCHMARK:** BASE + CVD + LightGBM
- **PRODUCTION:** NOT AUTHORIZED

Phase 6.5 is now unlocked. Execution of the 2024 confirmation phase may proceed under the strict constraints of `statistics_frozen.py`.
