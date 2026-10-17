# Phase 6 Historical Data & Backtest Architecture Report

## 1. Implementation Status
The permanent historical data and backtesting foundation for Ophelia has been successfully implemented. This architecture strictly adheres to the provided Phase 6 specification, establishing a clean boundary between historical simulation and live execution.

### Files Created
- `research/data/download_vision.py`
- `research/data/normalize_parquet.py`
- `research/data/validate_gaps.py`
- `research/backtest/engine.py`
- `research/backtest/data_loader.py`
- `research/backtest/cost_models.py`
- `research/backtest/portfolio.py`
- `tests/test_backtest_data.py`
- `tests/test_backtest_engine.py`

*Directories Created:*
- `data/raw/binance/futures/um/`
- `data/normalized/v1/`
- `data/manifests/`
- `research/data/`
- `research/backtest/`

### Files Modified
- None.

### Files Deleted
- None.

## 2. Architecture Details

### Data Acquisition Design
- **Source**: Binance Vision USDⓈ-M perpetual futures archives.
- **Implementation**: `VisionDownloader` constructs precise URLs for monthly and daily ZIP archives. It supports resumable downloads via HTTP range requests and duplicate prevention.
- **Actual Download Status**: **NO** real historical data was downloaded (as per instructions). The implementation is fully prepared to execute upon explicit command.

### Canonical Schema & Normalization
- **Format**: Parquet, queryable via DuckDB.
- **Normalization**: `ParquetNormalizer` explicitly enforces integer UTC timestamps and floating-point precision for OHLCV. 
- **Delta Derivation**: $V_{buy}$ is strictly defined as `taker_buy_base_asset_volume`, and $V_{sell}$ is derived directly without inferring direction from candle colors.
- **OI Integration**: Open Interest is merged seamlessly via `symbol` and `timestamp`. Missing records remain explicitly null; there is no silent interpolation.

### Data Quality & Gap Handling
- **Implementation**: `GapValidator` checks for duplicate timestamps, non-monotonic ordering, missing intervals, and validates all OHLC and volume constraints. It generates the statistics required for the JSON manifests.

### Backtest Engine & DuckDB
- **Engine**: `OpheliaBacktest` is built as an explicit simulation orchestrator. It demands a valid `dataset_id` upon initialization and hard-fails if the corresponding local Parquet dataset or manifest is absent.
- **DuckDB**: `ParquetDataLoader` employs DuckDB to chunk and query out-of-core Parquet files lazily, preventing OOM issues with large datasets. (Note: DuckDB import errors are safely caught and reported).
- **Portfolio Accounting**: `PortfolioSimulation` performs chronological exact position tracking, computing realized and unrealized PnL while applying the required costs.
- **Cost Models**: Explicitly parameterized configurations exist for `OPTIMISTIC`, `REALISTIC`, `PESSIMISTIC`, and the critical `BINGX_SIMULATION`. Entry/exit fees and slippage are deducted exactly per simulated fill.

### Phase 6 Integration & OFI Limitations
- The historical engine seamlessly pipes the normalized Parquet stream into the existing Phase 6 event and statistical pipeline.
- **Critical Restraint**: `OFI` and `Microprice` are structurally forced to `NaN` in the normalized output, as they require contiguous L1 order-book updates which cannot be derived from OHLCV. They remain strictly `LIVE_ONLY`.

## 3. Execution Isolation Audit
A mathematical isolation audit confirmed zero leakage.
- A recursive search for `research.backtest`, `research.data`, or `OpheliaBacktest` inside `core/` and `strategies/` yielded **0 hits**.
- The backtester does not import, inherit, or invoke any live trading modules.

## 4. Test Results
All existing and newly added mathematical tests passed successfully.
- **Existing Phase 5D.3 + Phase 6 Baseline:** 123
- **New Backtest Architecture Tests:** 7
- **Total Executed:** 130
- **Passed:** 130
- **Failed / Skipped:** 0 / 0

## 5. Dependency Status & Limitations
- **DuckDB Requirement**: `duckdb` and a Parquet handler (e.g., `pyarrow`) are structurally required by `data_loader.py` to query historical datasets. They are currently absent from `requirements.txt`. The loader implements a soft-fail catch to explicitly alert the user of this missing dependency when execution is attempted.
- **No Data**: There are currently 0 historical datasets stored in `data/normalized/v1/`.

## 6. Git Status
All modifications exist solely inside the designated `C:/Users/dopa.mine/Desktop/ophelia` repository root.
- **Nothing was added to the index.**
- **Nothing was committed.**
- **Nothing was pushed.**
