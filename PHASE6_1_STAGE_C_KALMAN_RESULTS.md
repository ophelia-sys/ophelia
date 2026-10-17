# PHASE 6.1 STAGE C — KALMAN ML EXPERIMENT RESULTS

## 1. Executive Summary

This report documents the Out-of-Sample (OOS) performance of the causal Local Linear Trend Kalman Filter feature family against the frozen `BASE + CVD + LightGBM` benchmark.

**DECISION:** INCONCLUSIVE / REMOVE
The addition of the Kalman features (`kalman_slope`, `kalman_innovation`, `kalman_uncertainty`) yielded mixed, statistically insignificant results. While minor LogLoss improvements were observed on 4 out of 6 symbols, the aggregate Brier score deteriorated, and the only statistically significant symbol (ETH) experienced severe degradation.

## 2. Experimental Parameters

- **Baseline:** `BASE_FEATS + CVD_FEATS_G`
- **Test:** `BASE_FEATS + CVD_FEATS_G + [kalman_slope, kalman_innovation, kalman_uncertainty]`
- **Target:** `target_60_up_10`
- **Observation Period:** 2022-2023 (Chronological Walk-Forward, 3 Folds)
- **Q/R Parameter Selection:** Selected deterministically from a compact grid using training-data-only Mean Squared Innovation per fold. (The optimizer universally favored the "Fast" adaptability profile: `R=1.0, Q_level=0.1, Q_slope=0.01` across all folds).
- **Total Valid OOS Observations:** 927,882 (Exactly matching the Baseline sample size on all folds).

## 3. Pooled Aggregate Metrics

| Metric | BASELINE | TEST (KALMAN) | DELTA (Positive = Improvement) |
|---|---|---|---|
| **Pooled LogLoss** | 0.6857485 | 0.6857481 | **+0.0000004** |
| **Pooled Brier** | 0.2463025 | 0.2463048 | **-0.0000023** |
| **DM Test (p-val)** | - | - | **0.9933** |
| **ENR (0 bps)** | 5.96 bps | 6.37 bps | **+0.41 bps** |

- The pooled Delta LogLoss is microscopically positive, but the pooled Delta Brier is strictly negative (deteriorated).
- The Diebold-Mariano test p-value of 0.99 demonstrates complete failure to statistically differentiate the Test model from the Baseline model in the pooled aggregate.

## 4. Per-Symbol Analysis

| Symbol | Base LL | Test LL | Delta LL | DM p-val |
|---|---|---|---|---|
| **BTCUSDT** | 0.676412 | 0.676397 | **+0.000015** | 0.8881 |
| **ETHUSDT** | 0.683223 | 0.683548 | **-0.000325** | 0.0005 (Sig. Negative) |
| **SOLUSDT** | 0.691856 | 0.691879 | **-0.000023** | 0.8188 |
| **XRPUSDT** | 0.688099 | 0.688043 | **+0.000056** | 0.5317 |
| **BNBUSDT** | 0.686628 | 0.686512 | **+0.000116** | 0.1510 |
| **ADAUSDT** | 0.688780 | 0.688619 | **+0.000161** | 0.1025 |

- **4 out of 6 symbols** posted positive Delta LogLoss.
- However, **none** of the positive deltas reached statistical significance (all DM p-values > 0.05).
- The only symbol to cross the significance threshold (ETHUSDT) did so entirely in the wrong direction, indicating structural degradation caused by the Kalman features.

## 5. Economic & Calibration Analysis

**Calibration:**
- Base: Slope = 0.6914, Intercept = -0.0557
- Test: Slope = 0.6903, Intercept = -0.0563
*The Kalman features slightly worsened probability calibration slope.*

**Economic Net Return (ENR):**
- While top-decile ENR increased marginally (+0.4 bps at 0 cost), the lack of predictive statistical significance indicates this may be random sampling variance (noise) at the tails rather than robust structural alpha.

## 6. Conclusion & Recommendation

The causal implementation successfully protected against information leakage, allowing an accurate evaluation of the Kalman Filter's true predictive value on 5-minute futures data. 

However, the evidence is definitively **mixed and economically weak**. The structural addition of causal Kalman features does not reliably improve predictive accuracy across the universe, and it actively harmed predictions on highly liquid pairs like Ethereum. 

**Recommendation:** Do NOT promote the Kalman features to the production/live probability engine. Reject the ML4T Kalman State-Estimation approach for the primary directional model.
