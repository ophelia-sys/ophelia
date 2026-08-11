# PHASE 5F.0: PROBABILITY CALIBRATION PREFLIGHT & DATASET AUDIT

## 1. Executive Summary
This document fulfills the Phase 5F.0 preflight audit. The objective is to determine if Ophelia possesses sufficient **real, historical, leakage-free** data to calibrate a probabilistic confidence model ($P(Up | X_t)$).
**Final Gate Decision: NOT_READY.**
Ophelia is mathematically and architecturally prepared, but lacks the persisted historical dataset required for ML calibration. Key L2 and Order Flow metrics only exist transiently in runtime buffers and must be collected over time.

---

## 2. Current Real-Data Availability & Sufficiency
We audited the actual runtime lineage and evaluated historical depth.

| Feature Group | Source | Historical Availability | Sufficiency Status | Notes |
|---------------|--------|-------------------------|--------------------|-------|
| OHLCV / RV / KER | REST | High (500 bars) | **READY** | Volatility and Trend can be calculated retrospectively. |
| Funding | REST | High (100 epochs) | **READY** | Sufficient for Z-Score warm-up. |
| Open Interest | REST | Low (Current point only)| **INSUFFICIENT** | Requires accumulation during runtime. |
| CVD / TVI | WS Trades | Zero (Runtime only) | **INSUFFICIENT** | Bounded runtime buffer `_trades` starts empty. Cannot reconstruct past CVD. |
| Microstructure (L1/L2)| WS Depth | Zero (Runtime only) | **INSUFFICIENT** | `_order_books` starts empty. Queue Imbalance, Spread, Visible Impact cannot be queried historically. |
| Liquidations / OFI | N/A | Zero | **UNAVAILABLE** | Data not provided by BingX. |

**Conclusion on Sufficiency:** We cannot map $X_t \to Y_{t+k}$ retrospectively because the most predictive features (Order Flow and Microstructure) are ephemeral WebSocket events. 

---

## 3. Canonical Observation Schema & Timestamp Alignment
Refer to `CALIBRATION_DATASET_SPEC.md` for the exact schema.

### Timestamp Alignment Rules
- **Decision Timestamp ($t$):** Exactly at the 1m candle close.
- **As-Of Joining:** If constructing datasets asynchronously, all WS features (Trades, Depth) must be merged using a strictly **backward-looking as-of join** where $t_{feature} \le t_{decision}$.
- **Forward-Fill:** Prohibited across session boundaries or connection drops exceeding 5 minutes.

---

## 4. Feature Normalization Rules
To prevent look-ahead bias during probability calibration:
1. **Trailing Execution:** Features like `CVD_zscore` must be calculated inside the engine using trailing `maxlen` deques (e.g., rolling median of the last 100 observations).
2. **No Global Scaling:** We strictly prohibit using `StandardScaler.fit(entire_dataset)`. 
3. **Missing Data:** Missing features must remain `NaN` or trigger an `INSUFFICIENT_DATA` flag. We prohibit zero-filling which aliases the neutral point of a Z-score.

---

## 5. Target Definitions
The forward target $Y_t$ uses information strictly $> t$.
- **Primary:** `fwd_dir_1m` and `fwd_dir_3m` (Directional accuracy).
- **Secondary:** `vol_adj_fwd_ret_3m` (Expected value mapping).
- **Execution Assumption:** Assumes execution at $t_{close}$ price plus a pessimistic 1.5 BPS slippage penalty.

---

## 6. Overlapping Label Analysis
If the decision frequency is 1m, but the target is 3m (`fwd_dir_3m`), the labels overlap.
- $Y_t$ and $Y_{t+1}$ share $t+1$ and $t+2$ price actions.
- **Validation Methodology:** Standard K-Fold CV is mathematically invalid due to autocorrelation.
- **Solution:** We will use **Embargoed Walk-Forward Validation**. If a model is trained on month $M$, the validation set will drop a 3-bar embargo window before beginning $M+1$ testing.

---

## 7. Feature Redundancy & Dimensionality
To avoid multicollinearity in the future Logistic Regression model:
- **Volatility:** Realized Volatility replaces Parkinson and Garman-Klass.
- **Microstructure:** Spread, Visible Impact, and Book Slope are correlated. L2/Ridge regularization will be required to handle their joint distribution.
- **Order Flow:** CVD and TVI are somewhat complementary, but Volume Z-Score is often redundant with CVD extremes.

---

## 8. Interaction Readiness
The following composites are ready for ML evaluation (once data is gathered):
- **Flow Evidence:** CVD + Microprice Deviation.
- **VWAP Evidence:** VWAP Deviation + Volume Z-Score.
- **Liquidity Evidence:** Spread + Queue Imbalance.

---

## 9. Required Data Collection Implementation
Since history is insufficient, Ophelia needs a passive data collector.
1. **Missing History:** Continuous 1-minute snapshots of $X_t$.
2. **Responsible Component:** A new background job in `TradingEngine` (or dedicated logger) that dumps `MarketState` to JSONL/CSV at the exact minute boundary.
3. **Minimum Collection Period:** 7 to 14 days of continuous 24/7 logging to capture multiple regimes.
4. **Persistence:** Required. Write to disk locally.
5. **Phase:** Do not implement in Phase 5F.0. Must be implemented as a dedicated data-collection milestone.

---

## 10. Model-Readiness Gate
**Gate Result:** **NOT_READY**

**Exact Blockers:**
1. **Insufficient Historical Data:** Microstructure and Order Flow features only exist transiently in RAM. There is no saved historical dataset to train $P(Up | X_t)$.
2. **Missing Persistence Layer:** No mechanism currently writes the synchronized $X_t$ vector and $Y_{t+k}$ labels to disk for offline ML training.

Phase 5F.0 completes exactly here. We must stop and await explicit approval for implementing the data collection architecture.
