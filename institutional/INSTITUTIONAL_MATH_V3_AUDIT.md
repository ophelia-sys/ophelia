# INSTITUTIONAL MATH ENGINE V3 — MATHEMATICAL AUDIT REPORT

## EXECUTIVE VERDICT
The Institutional Math Engine v3 architecture effectively separates structural market analysis from trading logic. The core mathematical implementations (Volatility, Trend, Momentum) strictly follow canonical definitions. 

However, several advanced models remain in a "Stubbed" state and require proper dependency management (e.g., `scipy`, `hmmlearn`). Furthermore, semantic issues in the `MarketState` data classes risk leaking "False" or "0.0" values downstream, which could be misinterpreted as confident negative readings rather than "Unavailable."

---

## 1. IMPLEMENTED COMPONENTS
- **Realized Volatility**: Canonical $\sqrt{\sum r_i^2}$.
- **Parkinson Volatility**: High/Low estimator, continuous trading assumption.
- **Garman-Klass Volatility**: OHLC estimator.
- **Average True Range (ATR)**: Max of high/low distances.
- **Kaufman Efficiency Ratio (ER)**: Directional noise measurement.
- **ATR-Scaled Trend Distance**: SMA normalized by ATR.
- **Directional Persistence**: Ratio of positive returns.
- **Standardized Momentum**: MAD Z-Score of log returns.
- **Order Flow Imbalance (OFI)**: Cont-Kukanov-Stoikov formula.
- **Cumulative Volume Delta (CVD)**: Trade-by-trade signed volume.
- **Taker Volume Imbalance (TVI)**: Buy vs. Sell aggressor volume.
- **Relative Quoted Spread**: $(Ask - Bid) / Mid$.
- **Amihud Illiquidity**: $|R_t| / V_{USD}$.
- **Order Book Depth Imbalance**: $(V_{Bid} - V_{Ask}) / (V_{Bid} + V_{Ask})$.
- **Information Entropy**: $-\sum p_i \log_2(p_i)$.

## 2. PARTIAL COMPONENTS
- **MAD Z-Score Anomaly Detection**: Implemented but threshold extraction requires calibration.
- **Factor Rank Normalization**: Implementation exists but relies on `scipy.stats.norm`, which is currently **missing** from the environment.

## 3. STUBS
- **Kyle Lambda**: Currently returns `NaN`. 
  - *Requires*: Minute-by-minute delta price and synchronized CVD regression.
- **HMM Regime Classification**: Currently returns static 0.33 probabilities.
  - *Requires*: `hmmlearn` or `pomegranate` library.
- **PELT Structural Break**: Currently returns `False`.
  - *Requires*: `ruptures` package or a highly optimized C/Cython local extension.
- **Cross-Asset Beta**: Currently returns `NaN`.
  - *Requires*: Ingestion of a benchmark (e.g., BTC-USDT) time series into the single-asset engine.
- **Logistic Regression Probability**: Returns hardcoded `0.5`.
  - *Requires*: Calibrated coefficients from out-of-sample offline training.

## 4. UNAVAILABLE DATA (GRACEFUL DEGRADATION)
- **Order Flow (OFI, CVD, TVI)**: The engine requires tick-level trade events and L1/L2 order book streams. The current exchange layer only passes `None`, gracefully forcing these metrics to evaluate to `NaN` (or `UNAVAILABLE`).
- **Open Interest, Funding, Liquidations**: Functions exist but immediately return `UNAVAILABLE` feature states, preventing OHLCV hallucination.

---

## 5. FORMULA-BY-FORMULA REFERENCE TESTS

Manual reference tests were computed externally to verify the mathematical logic.

| Metric | Input | Expected Result | Actual Engine Result | Status |
|---|---|---|---|---|
| **Realized Volatility** | `[0.01, -0.02, 0.015, -0.005, 0.008]` | `0.02853` | `0.02853` | PASS |
| **Parkinson** | H: `[101, 102, 101.5]`, L: `[100, 100, 99.5]` | `0.01788` | `0.01788` | PASS |
| **Garman-Klass** | O/H/L/C above | `0.01980` | `0.01980` | PASS |
| **ATR** | TR Arrays | `4.33333` | `4.33333` | PASS |
| **Kaufman ER** | `[100, 102, 101, 105]` | `0.71428` | `0.71428` | PASS |
| **MAD Z-Score** | `[1, 2, 3, 4, 100]` -> val=100 | `65.4256` | `65.4256` | PASS |
| **ECDF** | `[10, 20, 30, 40, 50]` -> val=40 | `60.0%` | `60.0%` | PASS |
| **Depth Imbalance** | Bid: `150`, Ask: `50` | `0.5` | `0.5` | PASS |
| **Entropy** | `[0.5, 0.25, 0.25]` | `1.5` | `1.5` | PASS |

---

## 6. PROPERTY & NUMERICAL ISSUES
- **Zero Variance Protection**: Division by zero is avoided across the pipeline using pandas `.replace(0, np.nan)` prior to division, outputting `NaN` gracefully (verified via `flat_df` test).
- **Missing Dependencies**: `scipy` is required for `factor_rank_normalization`. Code will crash if this function is invoked.

## 7. SEMANTIC ISSUES (MARKETSTATE DEFAULTS)
**CRITICAL**: `MarketState` (in `institutional/types.py`) has misleading default values:
- `direction_probability: float = 0.0`
- `regime_probability: float = 0.0`
- `structural_break: bool = False`

*Finding*: If PELT is stubbed, returning `False` implies certainty that a break did NOT occur. If Logistic Regression is stubbed, returning `0.0` implies a 0% probability of an upward move. These should be typed as `Optional[float]` and `Optional[bool]`, defaulting to `None`.

## 8. LOOK-AHEAD AUDIT
**NO VIOLATIONS FOUND.** 
- All rolling structures use trailing windows (e.g., `df['close'] - df['close'].shift(window)`). 
- ECDF calculates bounds strictly using past data relative to the final timestamp in the window (`iloc[-1]`).
- MAD Z-score relies on trailing rolling apply functions.

## 9. DATA CONTRACT FINDINGS
- The engine explicitly expects `l1_book_updates` (DataFrame of Bid/Ask sizes) and `trades` (DataFrame of individual trades with aggressor flags).
- The orchestrator (`institutional_math.py`) explicitly passes `None` when this data is absent, and the underlying functions safely abort, returning `NaN`. No metrics are fabricated from OHLCV.

## 10. COMPOSITE SCORE AUDIT
Arbitrary thresholds were identified in `institutional_math.py`:
```python
direction = "BULLISH" if direction_prob > 0.6 else "BEARISH" if direction_prob < 0.4 else "UNCERTAIN"
```
*Finding*: While the logistic stub outputs `0.5`, making this inert, the 0.6 / 0.4 thresholds represent arbitrary logic residing in the Institutional Math Engine rather than the Decision Engine.

## 11. PERFORMANCE FINDINGS
- **Fast Path (O(N))**: Volatility, Momentum, and Trend estimators utilize vectorized `pandas`/`numpy` rolling operations. Highly efficient for 1m execution.
- **Slow Path (O(N^2) or worse)**: MAD calculations inside `rolling.apply` are unoptimized and could bottleneck large windows. `hmmlearn` and `ruptures` (PELT) are computationally heavy and strictly require asynchronous / background thread processing.

## 12. PROVENANCE FINDINGS
- The `Provenance` object exists but is currently not fully populated or attached to the individual `FeatureResult` objects within the `MarketState`.

## 13. EXECUTION SAFETY
**SAFE**. The Institutional Math Engine does not import, reference, or instantiate any exchange clients, brokers, order requests, or portfolio managers. Dependencies flow strictly downwards from data objects.

---

## REQUIRED CORRECTIONS (FOR NEXT PHASE)
1. **Fix Semantics**: Update `MarketState` in `types.py` to use `Optional` fields and default to `None` for uncalculated probabilities and boolean states.
2. **Remove Arbitrary Logic**: Remove the `0.6 / 0.4` threshold check in `institutional_math.py` and pass the raw `direction_prob` upstream.
3. **Handle Dependencies**: Either install `scipy` or implement an approximation for `ndtri` to fix the `calculate_factor_rank_normalization` capability.
4. **Optimize MAD**: Replace `rolling.apply(np.median)` with a more optimized sliding window median/MAD algorithm if rolling window sizes scale above 1000.
