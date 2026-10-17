# PHASE 5.1 RESEARCH SUMMARY

**Objective**: Determine whether machine learning can extract genuine incremental predictive AND economic value from the validated BTCUSDT dataset using nonlinear models, feature interactions, and dynamic target horizons.

## 1. STAGE A: Target & Horizon Discovery
Evaluated horizons [12, 60] against dynamic up/down targets [10, 15, 20 bps]. 
- **Winner**: Horizon 60, Target `target_60_up_10`
- **Reasoning**: This configuration achieved a statistically significant AUC (0.5832) on the Discovery set and the highest Top Decile Gross Return (+1.97 bps) among configurations with meaningful label density.

## 2. STAGE B: Feature Family Discovery
Tested 10 combinations of predefined feature families on the locked Target/Horizon configuration using Logistic Regression.
- **Winner**: `baseline + volatility + trend + momentum + volume`
- **Reasoning**: Achieved the highest Top Decile Gross Return (+1.97 bps) and high AUC (0.5832). This indicates that the complete suite of features synergizes better than sub-combinations.

## 3. STAGE C: Feature Interactions Discovery
Evaluated combinations of mathematically derived non-linear interaction features (`ker * vol`, `mom * vol`, `vol_z * vol`).
- **Winner**: `interact_volume_vol`
- **Reasoning**: The inclusion of `interact_volume_vol` to the base features marginally improved the extreme right tail of the predictions, nudging the Top Decile Gross Return to +2.00 bps.

## 4. STAGE D: Nonlinear Model Discovery
Benchmarked Baseline, Persistence, Logistic Regression, LightGBM, and XGBoost against the locked features and targets.
- **Winner**: `logistic`
- **Reasoning**: While tree-based ensembles (LightGBM/XGBoost) achieved higher raw AUCs (~0.597 to 0.599), Logistic Regression captured the most economically meaningful tail events, returning the highest Top Decile Gross Return (+2.00 bps). 

## 5. STAGE G: Locked OOS Evaluation
A final candidate model (Logistic Regression with the full feature suite + volume interaction on `target_60_up_10`) was locked and evaluated one time against the strict Out-Of-Sample (OOS) dataset, encompassing all data from September 1, 2023, forward.

### Final Strict OOS Results
- **AUC**: 0.5909
- **95% Confidence Interval**: [0.5768, 0.6038]
- **Brier Score**: 0.2224
- **Top Decile Gross Return**: +4.21 bps
- **Top Decile Net Return**: -7.79 bps (assuming 12 bps execution cost)

## CONCLUSION
**STATISTICAL SIGNAL != TRADABLE SIGNAL.**

The research pipeline identified a statistically significant edge (AUC 0.5909). The reported 95% confidence interval [0.5768, 0.6038] excludes AUC = 0.50, therefore the null hypothesis of chance-level ranking ability is rejected at the corresponding significance level, assuming the interval construction is valid. 

We were able to optimize the gross return from ~1 bps up to +4.21 bps in the out-of-sample data.

However, statistical significance does not imply economic viability. Based on the conservative 12 bps execution assumption (4 bps taker fee + 4 bps slip * 2 sides), the final net return remains deeply negative at **-7.79 bps**. 

As per Ophelia's empirical research rules, since this strategy candidate produces a negative net return and does not demonstrate a robust cost-adjusted edge, it is **REJECTED** for production.

**Summary**:
- STATISTICAL EDGE = YES
- ECONOMIC EDGE = NO
- PRODUCTION = REJECTED
