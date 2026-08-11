# PHASE 5C: MATHEMATICAL SPECIFICATION AUDIT

## 1. Executive Summary
This document constitutes the formal Mathematical Specification Audit for the Institutional Evidence Engine (Phase 5C). The objective is to rigorously determine which mathematically sound indicators are implementable on Ophelia's verified data pipeline, which proposed features require empirical validation, and how to safely architect the confidence engine. 

**Key conclusions:**
- The repository natively supports advanced microstructure metrics (Spread, Imbalances, Microprice, CVD). 
- Simple additive scoring must be replaced with a strict probability calibration model (e.g., Logistic Regression on standardized Z-scores).
- Canonical OFI, Liquidation data, and Open Interest feeds are strictly UNAVAILABLE and will not be synthetically manufactured.
- Look-ahead bias is rigorously filtered. All observations are temporally ordered.
- We recommend a phased batching implementation moving from Robust Normalizations (Batch A) -> Order Flow / Volume Composites (Batch B) -> Probability Calibration (Batch C).

---

## 2. Current Implementation Inventory
A full feature list resides in [FEATURE_REGISTRY.md](FEATURE_REGISTRY.md).

**Foundation (Verified & Implemented):**
- **Volatility:** Realized Volatility, Parkinson, Garman-Klass, ATR.
- **Trend/Momentum:** KER, Directional Persistence, Robust Z-Score, Momentum Acceleration.
- **Microstructure:** Relative Spread, Queue/Depth Imbalance, Book Slope, Visible Impact, Microprice.
- **Order Flow:** CVD, TVI.

**Stubs (Pending Advanced Implementation):**
- HMM Regime, Structural Break (PELT).

**Unavailable (No Valid Data Source):**
- True OFI (requires non-gapped L1 feed).
- Open Interest / Funding / Liquidations (requires specific WebSocket APIs not currently piped).

---

## 3. Gemini Proposal Audit
*Note: Any numerical thresholds, weights, or mutual information claims found in the Gemini research proposal are treated strictly as HYPOTHESES pending empirical calibration on Ophelia's data.*

- **A. Liquidity / Displacement Gaps:** Validated math. Depends on true Book Impact calculations. Can be measured via `visible_impact_bps`.
- **B. Structural Change / CISD:** Statistically sound. Should utilize PELT / CUSUM instead of arbitrary retail concepts.
- **C. Order-Book Liquidity:** Existing Ophelia data supports Book Slope, Queue/Depth imbalances. Good quality.
- **D. Advanced Volume:** Viable. Requires normalization to filter normal volume profiles from anomalies.
- **E. VWAP:** Standard implementation available. Risk of look-ahead bias if anchored improperly.
- **F. Aggressive Order Flow:** CVD is validated and present.
- **G. Liquidity Sweeps:** Hypothesized via anomaly detection on CVD coupled with high Visible Impact.
- **H. Market Structure / Compression:** Realized Volatility / KER handles this perfectly.
- **I. OI / Funding / Liquidations:** **REJECTED/UNAVAILABLE**. The data is not in the `InstitutionalDataEngine` pipeline.

---

## 4. Mathematical Validity Classification

**A. VERIFIED IN OPHELIA CODE:** CVD, Depth Imbalance, Microprice, Realized Volatility, KER, Momentum Z-Score.
**B. MATHEMATICALLY VALID BUT NOT EMPIRICALLY VALIDATED:** Liquidity sweeps, FVG (Fair Value Gaps), HMM Regimes.
**C. RESEARCH HYPOTHESIS:** Proposed interaction weights, specific mutual information thresholds (e.g., thresholding CVD against VWAP deviations).
**D. REQUIRES HISTORICAL DATA VALIDATION:** Logistic Regression coefficients, Amihud illiquidity decay.
**E. UNAVAILABLE:** Canonical OFI, Liquidations.
**F. REJECTED / PROHIBITED:** Additive composite scores ($score = A + B + C$) attempting to represent uncalibrated confidence.

---

## 5. Data Provenance Classification
- **REAL INSTITUTIONAL DATA:** `depth_imbalance`, `queue_imbalance`, `microprice`, `book_slope`, `visible_impact_bps`, `cvd`, `tvi`. Derived strictly from BingX top-K and trade feeds.
- **SYNTHETIC / DERIVED DATA:** `trend_persistence`, `ker`, `volatility_z_scores`.
- **UNAVAILABLE:** `ofi`, `liquidations`, `open_interest`, `funding`.

---

## 6. Composite Evidence Analysis
*Combinations are candidate feature constructions, NOT guaranteed structural rules. All composites require statistical validation.*

1. **Sweep + CVD + Microprice:** Extremely complementary. Measures whether aggressive volume (CVD) absorbs liquidity (Sweep) causing true mid-price movement (Microprice). 
2. **FVG/Displacement + Sweep + CVD:** Mathematical interaction term between liquidity voids and aggressively marketed volume. 
3. **VWAP deviation + volume anomaly + CVD divergence:** Powerful, but VWAP anchoring introduces severe look-ahead risk. Must use strictly backward-looking VWAP.
4. **Spread + Depth + Impact/Liquidity stress:** Evaluates market resilience. Highly complementary (Spread = L1, Depth = L2 volume, Impact = L2 elasticity).
5. **Volatility family (Parkinson + GK + ATR):** High redundancy. A PCA or feature selection is required to prevent multicollinearity.
6. **Price + OI + Funding + CVD:** Rejected. OI/Funding unavailable.

---

## 7. Redundancy Analysis
To prevent multiple counting of the same information in the final Confidence Engine:
- **Validated Redundancy:** Parkinson vs. Garman-Klass vs. RV. Highly correlated. Must select ONE leading volatility estimator per regime.
- **Proposed (Needs Calibration):** Correlation between CVD and Depth Imbalance. Conditional Mutual Information (CMI) must be run on historical datasets to establish if Depth Imbalance provides *incremental predictive power* beyond CVD.
- **Strict Rule:** Never add features into the final probability model unless their Variance Inflation Factor (VIF) is bounded or handled implicitly via L1/L2 regularization (Ridge/Lasso).

---

## 8. Confidence Architecture
The architecture transitions from additive arbitrary scoring to strict expected value statistics.

1. **Input Feature Vector:** $X_t = [ Z_{cvd}, Z_{depth}, KER, RV_{percentile}, \dots ]$
2. **Normalization:** Rolling Robust Median Absolute Deviation (MAD) Z-Scores mapping into $\Phi^{-1}(Rank)$ when strictly required. No future data allowed in normalization.
3. **Missing Data Handling:** If a feature (e.g. microstructure) is missing, value is imputed to neutral $Z = 0$, with a dummy indicator $I_{missing} = 1$.
4. **Probability Calibration:** Logistic Regression (or equivalent GLM) outputting $P(Success | X_t, Regime)$.
5. **Expected Return Calculation:** $E[R_{net}] = (P_{success} \times R_{win}) - (P_{fail} \times R_{loss}) - Fees - Slippage$.
6. **Output:** The system only acts if $E[R_{net}] > \tau_{barrier}$.

---

## 9. Look-Ahead Audit
- **Calculation Timestamp:** Must ALWAYS occur at the completion of candle $T-1$ or exactly at tick $T$.
- **Normalization Windows:** `calculate_rolling_percentile` and `calculate_robust_z_score` are strictly trailing windows (`series.rolling()`).
- **Rejected Formulations:** Any VWAP calculated over the *entire day* used to evaluate a morning trade. Centered rolling averages.
- **Status:** All current verified metrics pass the look-ahead audit.

---

## 10. OFI / Liquidation / CISD Decisions
- **OFI:** UNAVAILABLE. Will not alias `depth_imbalance` or `queue_imbalance` to OFI.
- **Liquidations:** UNAVAILABLE. Do not invent liquidations from long upper wicks or volume anomalies.
- **CISD:** Replaced formally with structural break statistics (`institutional.structural_break.detect_structural_break` using PELT).

---

## 11. Final Priority Matrix

| Metric / Composite | Mathematical Validity | Data Availability | Current Status | Incremental Information | Empirical Validation Required | Priority | Action |
|--------------------|-----------------------|-------------------|----------------|-------------------------|-------------------------------|----------|--------|
| Realized Vol Z-Score | Sound | REAL (OHLCV) | VERIFIED | High | No (Established) | **P0** | Baseline |
| KER (Efficiency) | Sound | REAL (OHLCV) | VERIFIED | High | No (Established) | **P0** | Baseline |
| CVD | Sound | REAL (Trades) | VERIFIED | Very High | No (Established) | **P0** | Core Input |
| Microprice / Spread | Sound | REAL (L1) | VERIFIED | High | No | **P0** | Core Input |
| Visible Impact | Sound | REAL (L2) | VERIFIED | High | No | **P1** | Add to composites |
| Volume Anomaly (Z) | Sound | REAL (OHLCV) | VERIFIED | Moderate | Yes (Thresholds) | **P1** | Add to composites |
| Depth Imbalance | Sound | REAL (L2) | VERIFIED | High (if orthogonal) | Yes (Check VIF vs CVD) | **P1** | Add to composites |
| FVG / Displacement | Hypothesis | REAL (OHLCV) | RESEARCH | Unknown | Yes | **P2** | Shadow |
| Liquidity Sweep | Hypothesis | REAL (Trades/L2) | RESEARCH | High | Yes | **P2** | Shadow |
| HMM Regimes | Sound | REAL | STUBBED | High | Yes (Compute cost?) | **P2** | Shadow/Slow |
| True OFI | Sound | UNAVAILABLE | UNAVAILABLE | - | - | **REJECT** | Do Not Build |
| Liquidations | - | UNAVAILABLE | UNAVAILABLE | - | - | **REJECT** | Do Not Build |

---

## 12. Recommended Implementation Batches
*No actual decision authority is granted until Batch D/E.*

**BATCH A: Robust Normalization & Core Matrices**
- Finalize robust Z-Scores and MAD normalization for CVD, Spread, Impact.
- Focused test: Assert normalizations strictly obey trailing isolation.

**BATCH B: Composite Feature Construction**
- Combine Volume Anomaly + CVD + Visible Impact into mathematical factors.
- Focused test: Calculate correlations (VIF/Pearson) to ensure orthogonality.

**BATCH C: Regimes & Structural Breaks (SLOW PATH)**
- Implement robust PELT / CUSUM changes for structural break tracking.

**BATCH D: Probability Calibration Architecture**
- Implement Logistic Regression (Stubbed in `score.py`) mapping factors to $P(Success)$.

**BATCH E: Expected Net Return & Cost Barrier**
- Combine Probability + Target Ratios minus Slippage and Fees.

---

## 13. Unresolved Research Questions
- What is the computation limit for real-time HMM on Python without Cython optimizations in the trading engine loop?
- Does Depth Imbalance provide unique Mutual Information when CVD is already present?
- At what decay factor does Amihud Illiquidity become a stale metric for cryptocurrency momentum?

---

## 14. DO NOT IMPLEMENT YET
- **DO NOT** begin Batch A without explicit approval.
- **DO NOT** remove the legacy `InstitutionalMathEngine` from `DecisionEngine`.
- **DO NOT** change live leverage or risk approvals based on any V3 scores.
- **DO NOT** build actual ML prediction endpoints (Logistic Regression is currently a design concept).
