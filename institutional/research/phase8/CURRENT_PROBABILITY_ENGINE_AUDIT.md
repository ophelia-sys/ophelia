# CURRENT PROBABILITY ENGINE AUDIT

## 1. Lineage of the Current Decision Pipeline

The existing codebase produces entry decisions via the following pipeline:

1. **BingX / External Data** → Gathered via `InstitutionalRESTAdapter` and `InstitutionalWebSocketManager`.
2. **Raw Data** → Stored in caches (`_order_books`, `_trades`, etc.).
3. **Validated Snapshot** → `InstitutionalDataEngine.get_snapshot()` constructs a `MarketDataSnapshot` validating timestamps and bounds.
4. **Institutional Mathematics** → `InstitutionalMathEngine.analyze(snapshot)` applies math logic (volatility, momentum, VWAP) in two paths (Fast Path and Slow Path).
5. **Features** → Extracted into intermediate Pandas DataFrames or primitive floats (e.g., `calculate_realized_volatility`, `calculate_standardized_momentum`).
6. **Feature Normalization** → `institutional/normalization.py` applies `calculate_rolling_percentile` and `calculate_robust_z_score`.
7. **Probability Model** → **MISSING**. Currently, the `DecisionEngine._calculate_overall_market_score` uses a naive additive heuristic (neutral score 5.0 + volatility + trend + momentum + Kronos).
8. **Calibration** → **MISSING**. No calibration layer exists.
9. **Expected-Value Gate** → **MISSING**. Replaced by heuristic hard-coded logic in `DecisionEngine.evaluate()`.
10. **Opportunity** → Formed as a `MarketAnalysis` dataclass with an `approved` boolean.
11. **Entry / SL / T1 / T2 / T3** → **MISSING**. Handled currently via static user settings or naive overrides in execution, not dynamically tailored.
12. **Telegram** → `core/trading_engine.py` / `bot_adapter.py` formats signals and dispatches them to the user.
13. **User Approval/Modification** → User accepts or rejects the signal via Telegram inline buttons.
14. **DecisionEngine** → Resolves the final state of the trigger.
15. **Execution** → **DISABLED**. Handled in `TradingEngine`, but guarded by `LIVE_TRADING=False`.

## 2. Infrastructure Inventory

- **MarketDataSnapshot:** Defined in `institutional/data/models.py`. Produced by `institutional/data/engine.py`.
- **InstitutionalMathEngine:** Located in `institutional/institutional_math.py`.
- **MarketState:** Defined in `institutional/types.py`. Stores the structured features.
- **DecisionEngine:** Located in `core/decision_engine.py`. Consumes `MarketState` and `Kronos` data.
- **Shadow Telemetry:** Handled by `institutional/data/s3_shadow_engine.py` logging to `s3_shadow_log.sqlite`.
- **Outcome Tracker:** `institutional/data/s3_outcome_tracker.py` populates the `shadow_outcome` table.
- **OI History:** `institutional/data/archive/oi_poller.py` logs to `bingx_oi.sqlite`.
- **OHLCV Infrastructure:** Lightweight wrappers exist (`fetch_kline_history`), but no large-scale normalized HDF5/Parquet backend.
- **Normalization Infrastructure:** Present in `institutional/normalization.py` (percentiles, Z-scores).
- **ML Dependencies:** `scikit-learn` and `lightgbm` exist in `research-requirements.txt`, alongside older Phase 7 code (`research/phase7/ml_pipeline.py`).
- **Kronos Integration:** `external/Kronos/provider.py` provides directional signals but lacks calibrated confidence.
- **Unavailable Handling:** Handled via `DataQuality.UNAVAILABLE` / `np.nan` fallback logic (e.g., canonical OFI is marked missing by design).

## 3. Vulnerabilities in Current Design

- **Heuristic Scoring:** `DecisionEngine` uses an uncalibrated point system (`base_score = 5.0 + ...`) rather than predicting a real-world probability.
- **Missing Trade Geometry:** Stop loss, entry price, and TP are not calculated dynamically from ATR/volatility by a trade geometry module.
- **No Expected Value (EV):** The engine evaluates 'Is this bullish/bearish?' instead of calculating mathematically expected PnL after costs.
