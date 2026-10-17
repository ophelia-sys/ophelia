# PHASE 8.1: PROBABILITY ENGINE SPECIFICATION

## 1. Objective
To rigorously determine whether a calibrated probability model improves execution decisions relative to the purely deterministic S3 signal (`S3_CONDITIONAL_VOL_V1`). The Probability Engine is justified only if it demonstrates meaningful incremental out-of-sample value over deterministic S3.

## 2. Model Structure

The probability engine operates in two strictly decoupled layers:

### Layer 1: The Probability Model (Alpha Features)
Outputs the raw probability of the primary target occurring.

**Primary Probability Target:** `P(R_1h > 0)`
**Primary Economic Target:** `E[R_1h | X]`

**Inputs (Ablation Ladder):**
- A. S3 State (deterministic logic)
- B. S3 State + Volatility Context (ATR, regime)
- C. S3 State + Volatility + OI/Funding Context
- D. S3 State + All Validated Context

### Layer 2: The Economic Decision Layer
Transforms the probability and expected magnitude into an expected net return. 

**Calculation:**
`E[Net Return | X] = E[Gross Return | X] - E[Execution Cost | X] + E[Funding | X]`

**Inputs (Economic & Quality Context):**
- Expected Slippage
- Spread
- Institutional Fees (12 bps hurdle logic)
- Funding Rate
- Data Quality (Freshness, Missingness)

## 3. Model Complexity Ladder
Models will be built sequentially. Promotion to the next complexity level requires a meaningful increment in OOS metrics.

0. **Historical Conditional Base Rate:** `P(Up | S3_Long)`
1. **Regularized Logistic / Ridge:** Linear probability model.
2. **Calibrated Logistic:** Using Sigmoid Calibration (Platt Scaling).
3. **Calibrated Simple Tree:** Using Sigmoid Calibration (HistGradientBoosting or similar shallow tree).

*Note: Isotonic calibration will be explored only if the calibration sample size is demonstrably sufficient.*

## 4. Temporal Calibration & Validation
Validation will strictly enforce chronological separation:
1. **TRAIN:** Used to fit the underlying model (Logistic, Tree).
2. **CALIBRATION:** A chronologically subsequent hold-out set used exclusively for Platt Scaling / Isotonic regression. No overlap with TRAIN.
3. **VALIDATION (OOS):** The final chronological out-of-sample dataset for evaluating Brier Score, Log Loss, and Net Expectancy. 

*No future observations may enter model fitting or calibration.*

## 5. Evaluation Metrics (Proper Scoring Rules)
We do not rely primarily on AUC. Primary success criteria:
- **Brier Score:** Mean squared difference between predicted probability and actual outcome.
- **Log Loss:** Cross-entropy.
- **Calibration Curve & Error:** Visual and quantitative reliability.
- **Selective Precision / False Positive Rate:** Does the probability filter out bad S3 signals?
- **Expected Net Return & Drawdown:** Cost-adjusted trading expectancy.

## 6. S3 Freeze
The Phase 7 `S3_CONDITIONAL_VOL_V1` feature remains mathematically frozen. Any required adjustments to S3 itself constitute a separate research track, not a Phase 8.1 tuning mechanism.

## 7. Promotion Gates
The engine must pass the following gates to become a production candidate:
1. `LEAKAGE_PASS`
2. `CALIBRATION_PASS`
3. `DEV_PASS`
4. `OOS_PASS`
5. `INCREMENTAL_VALUE_PASS`
6. `STABILITY_PASS`
7. `DISTRIBUTION_SHIFT_PASS`
