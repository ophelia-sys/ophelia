# PHASE 5.3 CVD ML EXPERIMENT PROTOCOL

## 1. EXPERIMENT OBJECTIVE
To determine whether the predefined CVD (aggressor order flow) feature families provide statistically significant incremental out-of-sample predictive information beyond the existing BASE feature set.

## 2. DATA
- **Dataset:** 5-minute OHLCV dataset and 5-minute CVD dataset.
- **Symbols:** BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, ADAUSDT.
- **Period:** 2022-01-01 through 2023-12-31.
- **Frozen Feature Registry:** `PHASE5_3_CVD_FEATURE_REGISTRY.md`

## 3. CAUSAL TIMESTAMP CONTRACT
- $T_{decision} = OHLCV.open\_time + 5m$.
- CVD rows represent $[open\_time, open\_time + 5m)$ and are valid at $T_{decision}$.
- No feature uses `transact_time >= T_{decision}`.

## 4. TARGET DEFINITION
- **Target Variable:** `target_60_up_10` (Cost-Adjusted Triple Barrier, Upper/Take Profit, Lower/Stop Loss).
- **Horizon:** 60 periods (5 hours).
- **Classification:** Binary Classification (`P(Hits Upper Barrier First | Time < T and Return > Net Cost Hurdle)`).

## 5. MATCHED-SAMPLE POLICY
**A. PRIMARY GLOBAL CONTROL**
- `MODEL A_MATCHED_G` vs `MODEL G`. Both models evaluate on the exact timestamps where ALL frozen CVD features are non-NaN.

**B. FAMILY-SPECIFIC CONTROLS**
- For each sub-family model (B through F), a dedicated `BASE_MATCHED_X` control must be created using identical timestamps available to that specific model.
- Rows missing due to genuine source gaps (e.g. SOL 2023-11/12) are strictly excluded from MATCHED samples. No imputation is permitted.

## 6. ABLATION MODELS
- **MODEL A:** BASE (Full eligible sample).
- **MODEL A_MATCHED_G:** BASE evaluated only on the exact timestamps available to MODEL G.
- **MODEL B:** BASE + CVD DELTA (`cvd_delta_5m`, `cvd_delta_15m`, `cvd_delta_1h`).
- **MODEL C:** BASE + CVD IMBALANCE (`cvd_imbalance_5m`, `cvd_imbalance_15m`, `cvd_imbalance_1h`).
- **MODEL D:** BASE + CVD Z-SCORE (`cvd_zscore_5m`, `cvd_zscore_15m`, `cvd_zscore_1h`).
- **MODEL E:** BASE + CVD ACCELERATION (`cvd_acceleration_15m`, `cvd_acceleration_1h`).
- **MODEL F:** BASE + NORMALIZED CVD (Imbalance + Z-Score + Acceleration).
- **MODEL G:** BASE + ALL FROZEN CVD FEATURES (All 11).

*Note: LSR features are explicitly excluded from Models A-G in Phase 5.3.*

## 7. SYMBOL TRAINING POLICY
- **Primary Analysis:** Trained independently per symbol (BTC->BTC, ETH->ETH, etc.). No cross-symbol pooling for the primary model fitting.
- **Secondary Analysis:** Cross-symbol generalization (e.g., Train BTC -> Test ETH) may be tested but does not determine primary acceptance criteria.

## 8. MODEL ARCHITECTURE
- **Primary Model:** Regularized Logistic Regression (as locked in Exp 006).
  - Recovered Config: `LogisticRegression(C=1.0, solver='lbfgs', max_iter=1000, penalty='l2')`.
- **Secondary Model:** LightGBM (Robustness only, does not override primary analysis).

## 9. TRAIN / VALIDATION / OOS DESIGN
- **Splits:** 3-fold Purged Walk-Forward (strictly chronological).
- **Purge / Embargo Check:** 
  - `Target Horizon = 60`
  - `Purge = 60` (Protects test set from overlapping with prior training labels).
  - Embargo is not separately required for this expanding walk-forward architecture. The effective protection is provided by chronological train-before-test construction plus the 60-bar purge.
  - `Maximum Feature Lookback = 288` (Causal historical lookback, no future leakage).
  - *Verification:* The `PHASE5_3_WALK_FORWARD_BOUNDARY_AUDIT.md` proves that `max(label_end(train)) < min(test_start)` is strictly enforced.
- **Pre-processing:** All scaling/normalization fitted only on training data.

## 10. METRICS & COST SWEEP
- **Metrics:** LogLoss, Brier Score, Expected Net Return (bps).
- **Cost Sweep:** Frozen at `[0, 5, 10, 15, 20, 25]` bps.
- **Regime Analysis:** Evaluated separately for 2022 and 2023.

## 11. STATISTICAL FRAMEWORK
- **Block Bootstrap:** 
  - 1000 Replications.
  - Primary Block Length: **60 observations** (Target Horizon).
  - Sensitivity Analysis: 30, 60, 120 bars.
  - Statistic: $\Delta LogLoss$, $\Delta Brier$.
- **Block Permutation Test:** 
  - 1000 Permutations. Primary Block Length: **60 observations**.
  - Null Hypothesis: Adding CVD provides no incremental predictive info beyond BASE. Permutes CVD augmentation while preserving BASE.
- **Diebold-Mariano Test:**
  - $\Delta Loss = Loss_{BASE} - Loss_{CVD}$.
  - Variance Estimator: HAC/Newey-West.
  - HAC Max Lag: **59**.
- **Multiple Comparison Policy:** 
  - Benjamini-Hochberg FDR control ($q = 0.05$).
  - Primary Alpha: $0.05$.
  - Families: Model G vs BASE_G across symbols; Ablations B-F across symbols.

## 12. DECISION FRAMEWORK
- **RETAIN:** Model G improves aggregate matched OOS LogLoss, Brier does not deteriorate, $q \le 0.05$ on statistics, improvement spans multiple symbols/folds, robust to costs.
- **INCONCLUSIVE:** Mixed evidence, minimal aggregate improvement, localized to a single fold/symbol, or high regime dependence.
- **REMOVE:** Fails to improve aggregate LogLoss, deteriorates performance, or improvement disappears under statistical robustness testing.

## 13. RANDOMNESS & REPRODUCIBILITY
- **Master Seed:** 42. All child randomness is deterministically seeded from 42.
- OOS predictions and configuration saved via JSON manifest.
