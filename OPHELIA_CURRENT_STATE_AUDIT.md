# OPHELIA CURRENT STATE AUDIT

## 1. Actual Current Architecture
Ophelia implements a strict, layered architecture isolating real-time data acquisition from execution logic:
- **Data Layer (`institutional/data`)**: Synchronously normalizes BingX WebSocket and REST data into `MarketDataSnapshot` objects.
- **Math Layer (`institutional`)**: Calculates pure microstructure and flow metrics (CVD, TVI, Spread, Microprice, Slope) entirely decoupled from execution, outputting a `MarketState`.
- **Decision/Execution Layer (`core`, `risk`)**: `DecisionEngine` evaluates math outputs and external signals (Kronos) to formulate direction. `RiskManager` applies risk constraints. `TradingEngine` orchestrates execution.

## 2. Completed Phases
Based on repository inspection and test results:
- **Phase 4.1**: Real Data Verification (Completed)
- **Phase 4.2**: CVD / TVI Validation (Completed)
- **Phase 4.3**: Order-Book Verification (Completed)
- **Phase 4.4**: Microstructure Implementation (Completed)
- **Phase 4.5**: Integration Audit (Completed)
- **Phase 4.5.1**: OFI Lineage Audit (Completed)

## 3. Verified Functionality
- **Microstructure**: Mid price, absolute/relative spread, queue/depth imbalance, microprice, visible-book price impact, book concentration, book slope.
- **Order Flow**: Bounded rolling CVD, TVI, proper handling of `m` (isBuyerMaker) flag.
- **OFI Lineage**: True separation of Depth Imbalance and Queue Imbalance from OFI. No semantic aliasing exists.

## 4. Tested Functionality
- The institutional test suite comprises 49 tests.
- **Result**: `49 passed in ~9.00s`
- **Coverage**: Trade aggregation, microstructure generation, math v3 evaluation, orderbook verification, and OFI lineage integrity.

## 5. Real-Data Verified Functionality
- Verified BingX WebSocket data streams (`@trade`, `@depth20`).
- Proven derivation of the aggressor side.
- Verified sequence gaps in BingX limit order books, demonstrating canonical continuous limit order tracking is impossible without fabricated data.

## 6. Unavailable Functionality
- **Canonical OFI**: Unavailable (BingX sequence gaps).
- **Event-Based OFI**: Unavailable.
- **Liquidations**: Unavailable (BingX endpoint is non-functional/undocumented based on tests).

## 7. Research-Only Functionality
- ML pipeline, feature generation, backtesting infrastructure, and historical empirical validation (all residing in `research/`).
- Kronos market regime analysis (currently evaluated asynchronously).

## 8. Kronos Current State
- **Location**: Completely self-contained within `external/Kronos`.
- **Integration**: `DecisionEngine` imports `KronosProvider`, which passively reads a JSON artifact (`kronos_market_regime.json`) produced asynchronously by Kronos.
- **Role**: Kronos is queried for `direction`, `score`, and `confidence`. It is currently used explicitly as a high-confidence *override* (score > 0.77) for oversized 1m and 5m candles.
- **Status**: The ML model is disjoint from the core synchronous loop. The system will gracefully default to a `NEUTRAL` direction if the Kronos output file is missing or stale.

## 9. Existing ML Infrastructure
- A foundation for data processing, validation, and historical analysis resides in `research/phase6/` and `research/data/`.
- Features, labels, statistics, power analysis, and cost modeling structures exist.
- Empirical validation (Phase 6) has been initiated but halted due to a timestamp parsing anomaly.

## 10. Existing Backtesting Infrastructure
- A custom backtesting engine resides in `research/backtest/`, containing `engine.py`, `data_loader.py`, `cost_models.py`, and `portfolio.py`.

## 11. Existing Data Storage Infrastructure
- Planned storage directories for historical Binance UM data include `data/raw/`, `data/normalized/`, and `data/manifests/`.
- `normalize_parquet.py` handles parsing Binance Vision CSVs into standard Parquet format.

## 12. Existing Telegram Infrastructure
- Present in the `telegram/` module. Used to provide notifications, manual intervention checks, and debug reports.

## 13. Existing Execution Architecture
- Managed primarily by `core/trading_engine.py` and `risk/risk_manager.py`. Kept strictly separated from historical ML components and the Institutional Math Engine.

## 14. Remaining Technical Debt
- An extreme timestamp anomaly exists in `research/data/normalize_parquet.py`:
  `df['timestamp'] = pd.to_datetime(df['create_time']).astype('int64') // 10**6`
  This truncates microseconds to seconds, whilst OHLCV data exists in milliseconds. This introduces a 50+ year lag during OI merges.
- The historical dataset expansion is corrupt due to this bug and must be regenerated.

## 15. Dependency Issues
- Python dependencies `websocket-client`, `scipy`, `pandas`, `requests`, and `numpy` were missing from the immediate environment or `requirements.txt` but were resolved to run tests. No blocking native dependency conflicts exist.

## 16. VPS/Resource Constraints
- Not directly discoverable, but the batch prediction functionality in Kronos and large dataset generation dictates memory-conscious sequential processing. Asynchronous Kronos evaluation correctly prevents the main loop from blocking due to resource contention.

## 17. Documentation/Code Discrepancies
- **OFI**: Code exactly matches the `PHASE4_5_1_OFI_LINEAGE_AUDIT.md`. OFI is strictly coded as `np.nan`. No semantic aliases are found.
- **Phase 6 Data**: `PHASE6_RESUME_STATE.md` accurately describes the critical timestamp bug discovered in `normalize_parquet.py` which remains uncorrected in the code.

## 18. Recommended Next Phase
1. Correct the timestamp bug in `research/data/normalize_parquet.py`.
2. Write targeted forensic tests to verify the timestamp resolution (ms), OI `asof` backwards merge logic, and correct representation of `DeltaOI`.
3. Generate a small normalized dataset sample and verify output distributions.
4. Fully rebuild the historical expanded dataset.
5. Resume empirical validation of features against the clean dataset.

## 19. Risks
- Rebuilding the dataset without strict millisecond timestamp validation will repeatedly corrupt the downstream empirical evaluations, yielding invalid alpha conclusions.
- Kronos is currently used as an override in the `DecisionEngine`. If Kronos cannot prove out-of-sample incremental value, its override logic could be a net negative to the trading system.

## 20. Explicit "DO NOT IMPLEMENT YET" list
- DO NOT execute large historical data downloads or complete dataset regeneration.
- DO NOT modify the `DecisionEngine` or `TradingEngine` to depend synchronously on ML execution.
- DO NOT hallucinate OFI or Liquidations.
- DO NOT integrate Kronos further into core math models without an OOS validation report.
