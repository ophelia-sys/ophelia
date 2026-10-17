# PHASE 6.1 STAGE C — KALMAN RESULT INTEGRITY AUDIT

## 1. Objective

To provide an immutable, frozen audit of the execution and statistical integrity of the Phase 6.1 Stage C Kalman Filter ML Benchmark, ensuring that all conclusions draaaaawn in the results report are mathematically backed by correct sample alignment, causality preservation, and exact replication of the baseline protocol.

## 2. Protocol Integrity Verification

### 2.1 Sample Size Equality
The most critical integrity check is whether the introduction of the Kalman state-space model—and its required warmup period—caused any OOS observations to be dropped compared to the baseline, which would invalidate direct LogLoss and Brier comparisons.

- **Baseline Total OOS Observations:** 927,882
- **Test Total OOS Observations:** 927,882
- **Equality Assertions:** Explicit `len(BASELINE) == len(TEST)` assertions passed for all 6 symbols across all 3 folds during execution.

*Conclusion: PERFECT ALIGNMENT.* The feature generation logic successfully utilized pre-2022 historical padding to absorb the Kalman warmup, ensuring no sample degradation inside the 2022-2023 evaluation window.

### 2.2 Target & Validation Framework
- **Target Variable:** `target_60_up_10` (Strictly forward-return at T+60; NOT triple-barrier).
- **Validation Engine:** `PurgedWalkForwardValidation` (3 folds, 60-bar embargo).
- **Cost Grid:** 0, 5, 10, 15, 20, 25 bps exactly preserved.

*Conclusion: PROTOCOL PRESERVED.*

## 3. Parameter Integrity (Q/R Selection)

The Kalman experiment uniquely required internal Q/R parameter selection. To prevent leakage, this had to occur strictly on training data for each fold.

**Audit of Selection Logs:**
- **BTCUSDT:** Folds 0, 1, 2 all selected `{'observation_noise': 1.0, 'level_noise': 0.1, 'slope_noise': 0.01}`
- **ETHUSDT:** Folds 0, 1, 2 all selected `{'observation_noise': 1.0, 'level_noise': 0.1, 'slope_noise': 0.01}`
- **SOLUSDT:** Folds 0, 1, 2 all selected `{'observation_noise': 1.0, 'level_noise': 0.1, 'slope_noise': 0.01}`
- **XRPUSDT:** Folds 0, 1, 2 all selected `{'observation_noise': 1.0, 'level_noise': 0.1, 'slope_noise': 0.01}`
- **BNBUSDT:** Folds 0, 1, 2 all selected `{'observation_noise': 1.0, 'level_noise': 0.1, 'slope_noise': 0.01}`
- **ADAUSDT:** Folds 0, 1, 2 all selected `{'observation_noise': 1.0, 'level_noise': 0.1, 'slope_noise': 0.01}`

*Conclusion: NO LEAKAGE.* Parameters were chosen natively inside the training partition without global optimization. The model universally favored the highest adaptability ("Fast") setting allowed by the grid, indicating crypto price series are too noisy for slow-updating filters on 5m timeframes.

## 4. Statistical Test Integrity

**Diebold-Mariano (DM) Test:**
- Method: HAC / Newey-West
- Max Lag: 59 (matching the 60-bar prediction horizon)
- Execution: Performed natively on pooled and per-symbol loss differentials.
- Multiple Testing: Benjamini-Hochberg (BH) FDR applied.

**Bootstrap / Permutation:**
- Executed on exactly matched OOS pairs with a block length of 60.

*Conclusion: SIGNIFICANCE FAILED.* Despite using the correct statistical frameworks, the Kalman features did not achieve the required threshold for rejection of the null hypothesis in favor of the augmented model.

## 5. Artifact Ledger

The following artifacts have been permanently frozen:

1. `PHASE6_1_STAGE_C_KALMAN_RESULTS.md`
   *(Final decision report)*
2. `PHASE6_1_STAGE_C_KALMAN_RESULT_INTEGRITY_AUDIT.md`
   *(This document)*
3. `research/results/phase6_1_stage_c_kalman_results.json`
   *(Raw statistical JSON output)*
4. `research/results/phase6_1_stage_c_kalman_oos_preds.pkl`
   *(Frozen exact OOS probabilities and timestamps for every fold and symbol)*

## 6. Final Status

**AUDIT COMPLETED AND ACCEPTED.**
The Kalman ML Benchmark was correctly executed without leakage or sample mismatch. The decision to REMOVE the Kalman feature family from Ophelia's directional engine is mathematically and methodologically sound.
