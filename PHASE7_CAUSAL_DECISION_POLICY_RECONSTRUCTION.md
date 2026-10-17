# PHASE 7 CAUSAL DECISION POLICY RECONSTRUCTION

**Status:** `RECONSTRUCTED`
**Date:** 2026-08-16

## 1. The Look-Ahead Bias Problem
Historically, the research evaluation scripts (`exp_phase5_3_ml_ablation.py`, etc.) calculated a decision threshold dynamically using `p90 = np.percentile(preds, 90)` **directly on the out-of-sample prediction array**. This constitutes future look-ahead bias if deployed in a live, causal system, as the 90th percentile of 2024 predictions cannot be known on January 1st, 2024.

## 2. Methodology A: Train-Only Fixed Quantile
To reconstruct a strictly causal policy that perfectly aligns with the historical intent (trading the top 10% highest-confidence signals), we calculate the 90th percentile of the prediction distribution over the **strictly frozen training set (2022-2023)**. These static thresholds are then frozen for 2024 out-of-sample forward execution.

## 3. Reconstructed Thresholds
| Symbol | Train Samples | Mean Train Prob | Reconstructed p90 Threshold |
|--------|---------------|-----------------|-----------------------------|
| BTCUSDT | 209086 | 0.4287 | **0.4864** |
| ETHUSDT | 209076 | 0.4457 | **0.4984** |
| SOLUSDT | 191508 | 0.4617 | **0.4862** |
| XRPUSDT | 209078 | 0.4571 | **0.5021** |
| BNBUSDT | 209652 | 0.4532 | **0.5016** |
| ADAUSDT | 209074 | 0.4612 | **0.5029** |

## 4. Architectural Directive
These static thresholds are saved to `PHASE7_DECISION_THRESHOLDS.json`. The production `DecisionEngine` must load this file and apply a strict `probability >= p90_threshold` causal rule for signal generation.
Short logic remains strictly unauthorized (Ophelia remains LONG only).
