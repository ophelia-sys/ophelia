# PHASE 5E: FEATURE EVIDENCE AUDIT

## 1. Executive Summary
This document fulfills the Phase 5E architectural requirement to evaluate the institutional features for predictive evidence, interactions, and probability modeling.
**Conclusion:** We establish that CVD, Microprice, Queue Imbalance, and Realized Volatility are the strongest individual candidates. We prohibit arbitrary additive scoring and propose a Logistic Regression / XGBoost probability architecture. FGV and CISD remain research concepts pending mathematical isolation.

---

## 2. Target Definitions
To empirically validate a feature, a forward prediction target must be defined.
- **Horizon Selection:** For a 1-minute to 5-minute trading engine, targets exceeding 15 minutes introduce excessive noise.
- **Target Candidates:**
  1. **Fwd Dir (1m/3m):** $Sign(Close_{t+k} - Close_{t})$. Useful for microstructure classification.
  2. **Vol-Adj Fwd Ret (3m):** $(Close_{t+k} - Close_{t}) / (RV_{t} \times \sqrt{k})$. Normalizes returns across volatility regimes.
  3. **Maximum Favorable Excursion (MFE):** Max forward high over 5m minus current execution price. Useful for stop-loss and trailing take-profit tuning.
- **Selected Baseline Target:** **Vol-Adj Fwd Ret (1m, 3m)** and **Fwd Dir (1m, 3m)**.

---

## 3. Feature Inventory & Normalization Decisions
Direct comparison of raw features (e.g., raw CVD volume vs spread bps) is mathematically invalid in a GLM model. 
- **Robust Z-Score (Median/MAD):**
  - **Applied To:** CVD, VWAP Deviation, Momentum, Visible Impact.
  - **Why:** Protects the scaling factor from extreme crypto volatility spikes.
- **Empirical Percentile (0 to 1):**
  - **Applied To:** Realized Volatility, Book Concentration.
  - **Why:** Volatility exhibits fat tails. Percentile ranking handles this smoothly.
- **Raw Bounded Ratios (-1 to 1 or 0 to 1):**
  - **Applied To:** Queue Imbalance, KER, Directional Persistence, TVI.
  - **Why:** Naturally bounded by definition.
- **Strict Look-Ahead Rule:** All rolling medians/MADs MUST use strictly trailing windows (`min_periods=N`). Centered windows are strictly prohibited.

---

## 4. Individual Feature Evidence

| Group | Strongest Single Features | Predictive Thesis | Status |
|-------|---------------------------|-------------------|--------|
| **Order Flow** | **CVD (Diff Z-Score)** | Aggressor flow precedes structural price movement. | **VALIDATED** |
| **Microstructure** | **Queue Imbalance** | Top-of-book pressure resolves in the direction of the heavy side. | **VALIDATED** |
| | **Microprice (vs Mid)** | Imbalanced volume-weighted mid leads the true mid. | **VALIDATED** |
| **Volatility** | **Realized Volatility** | Predicts the magnitude (not direction) of the next move. Critical regime filter. | **VALIDATED** |
| **Trend** | **KER** | Differentiates chop from directional flow. | **VALIDATED** |

---

## 5. Feature Interaction & Complementarity (Composites)
Composite evidence groups provide orthogonal dimensions of market state:

1. **Flow Evidence (CVD + Microprice)**
   - **Thesis:** Aggressive market orders (CVD) moving the liquidity-weighted mid (Microprice). 
   - **Interaction:** Positive CVD *without* positive Microprice drift indicates passive absorption (iceberg/limit selling). This interaction yields higher mutual information than either alone.
2. **Liquidity Evidence (Spread + Queue Imbalance + Visible Impact)**
   - **Thesis:** Narrow spread + high queue imbalance = high conviction breakout. Wide spread + high impact = illiquid void.
3. **VWAP Evidence (VWAP Dev + Volume Z-Score)**
   - **Thesis:** Extreme deviation from trailing VWAP on high relative volume implies exhaustion or institutional capitulation.
4. **Positioning Evidence (OI Delta + CVD) (Currently INSUFFICIENT_DATA)**
   - **Thesis:** Positive CVD + rising OI = new longs. Negative CVD + dropping OI = long liquidations.

---

## 6. Regime Observations
Feature predictiveness is conditionally dependent on the volatility regime.
- **Low Volatility (Chop):** Trend features (KER, Momentum) generate false positives. Microstructure (Queue Imbalance) mean-reverts.
- **High Volatility (Expansion):** Flow features (CVD) dominate. Spread widens; Visible Impact becomes the primary risk metric.
- **Current Approach:** Without HMM (which is computationally heavy), Realized Volatility percentiles serve as the proxy for regime state.

---

## 7. FGV & CISD Feasibility
- **Fair Value Gaps (FGV):**
  - **Classification:** **RESEARCH_ONLY**.
  - **Reason:** Requires a strict definition of overlapping wicks (e.g., $Low_t > High_{t-2}$). Look-ahead risk is high if the gap is identified before the close of $t$.
- **Change in State of Delivery (CISD):**
  - **Classification:** **RESEARCH_ONLY**.
  - **Reason:** Redundant with existing mathematical structural breaks (PELT / CUSUM). Will use PELT for objective break detection rather than subjective CISD patterns.

---

## 8. Data Sufficiency & Leakage Audit
- **Data Sufficiency:**
  - **OHLCV/L1/L2/Trades:** High sufficiency. Buffers populate within minutes.
  - **Open Interest / Funding:** **INSUFFICIENT_DATA**. The historical WS/REST endpoints provide data, but robust Z-score calculation requires a minimum history (e.g. 50+ periods) which must accumulate during runtime.
- **Leakage Audit:**
  - `window_start <= t.timestamp <= now` ensures no future trades are grouped.
  - `vwap` utilizes `rolling().sum().iloc[-1]`. Look-ahead safe.
  - Normalization must guarantee trailing constraints (confirmed).

---

## 9. Recommended Future Probability Architecture
**Objective:** Estimate $P(\text{Up} | X_t)$ and $E[\text{Return} | X_t]$.
**Prohibited:** Arbitrary scoring ($0.2 \times CVD + 0.3 \times VWAP$).

**Recommendation: L2-Regularized Logistic Regression (or Calibrated XGBoost)**
1. **Architecture:**
   - Map normalized features ($Z_{CVD}, \text{KER}, \text{QueueImb}$) into a Logistic Regression model.
   - Use L2 (Ridge) regularization to handle collinearity (e.g. between Spread and Visible Impact).
   - Use Platt Scaling or Isotonic Regression if moving to XGBoost/LightGBM.
2. **Advantages:**
   - Naturally produces bounded probabilities (0 to 1).
   - Interpretable coefficients.
   - Low computational latency (matrix multiplication in real-time).
3. **Execution Logic:**
   - $E[R] = (P_{up} \times R_{win}) - (P_{down} \times R_{loss}) - \text{Fees} - \text{Slippage}$
   - Execute only if $E[R] > \text{Threshold}$.

---

## 10. Conclusion & Stop Condition
Phase 5E research and feature audits are complete. No live decision authority has been granted to V3. The legacy DecisionEngine is intact. 

**Next Steps:** Wait for explicit approval to begin probability calibration (Phase 5F) or further data accumulation.
