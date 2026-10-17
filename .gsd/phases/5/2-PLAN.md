---
phase: 5
plan: 2
wave: 2
---

# Plan 5.2: Forecast Database Schema & ForecastService Subsystem Architecture

## Objective
Implement the persistent database schema for forecasts and build the modular `ForecastService` subsystem in `control_plane/forecast_service.py`. Establish the strict provider abstraction (`TimesFMProvider` and `StatisticalBaselineProvider`), singleton model governance, and the strictly causal timestamp-aware feature pipeline.

## Context
- `control_plane/db.py`
- `control_plane/forecast_service.py`
- `control_plane/intelligence.py`

## Tasks

<task type="auto">
  <name>Task 5.2.1: Implement database schema for forecasts and evaluations</name>
  <files>control_plane/db.py</files>
  <action>
    - In `control_plane/db.py`:
      * Create table `model_forecasts`:
        `forecast_id TEXT PRIMARY KEY`, `user_id INTEGER`, `instrument TEXT`, `timeframe TEXT`,
        `forecast_timestamp INTEGER`, `data_timestamp INTEGER`, `model_name TEXT`, `model_version TEXT`,
        `checkpoint TEXT`, `context_length INTEGER`, `horizon INTEGER`, `input_schema_version TEXT`,
        `forecast_values TEXT`, `quantiles TEXT`, `forecast_generation_ms REAL`, `latency_ms REAL`,
        `status TEXT`, `data_freshness TEXT`, `error TEXT`, `mode TEXT`, `created_at INTEGER`
      * Create table `model_forecast_evaluations`:
        `evaluation_id TEXT PRIMARY KEY`, `forecast_id TEXT`, `instrument TEXT`, `timeframe TEXT`,
        `forecast_timestamp INTEGER`, `evaluation_timestamp INTEGER`, `actual_values TEXT`,
        `mae REAL`, `rmse REAL`, `direction_correct INTEGER`, `absolute_error REAL`, `signed_error REAL`,
        `quantile_hit INTEGER`, `coverage REAL`, `regime TEXT`, `created_at INTEGER`
      * Implement database functions:
        - `save_model_forecast(record: dict) -> None`
        - `get_latest_model_forecast(instrument: str, timeframe: str, mode: str = "SHADOW") -> dict | None`
        - `list_model_forecasts(limit: int = 50, instrument: str = None) -> list[dict]`
        - `save_model_forecast_evaluation(record: dict) -> None`
        - `get_model_forecast_metrics(model_name: str = None, instrument: str = None) -> dict`
  </action>
  <verify>python -c "from control_plane import db; db.init_db(); print('Forecast tables initialized successfully')"</verify>
  <done>Tables `model_forecasts` and `model_forecast_evaluations` created with indices and CRUD operations.</done>
</task>

<task type="auto">
  <name>Task 5.2.2: Implement ForecastService, TimesFMProvider and StatisticalBaselineProvider</name>
  <files>control_plane/forecast_service.py</files>
  <action>
    - Create `control_plane/forecast_service.py`:
      * Define abstract base class `ForecastProvider` with method `forecast(...) -> ForecastResult`.
      * Implement `TimesFMProvider(ForecastProvider)`:
        - Checkpoint identifier pinned to: `google/timesfm-3.0-pytorch`.
        - Model loader supporting CPU inference with controlled singleton caching (`_model_instance`).
        - Handles zero-shot univariate and multivariate forecasting.
        - Produces future price trajectory, expected return, volatility, and canonical quantiles ($q_{10}, q_{20}, \dots, q_{90}$).
        - Validates quantile monotonicity: $q_{10} \le q_{50} \le q_{90}$.
      * Implement `StatisticalBaselineProvider(ForecastProvider)`:
        - Produces naive persistence baseline ($P_{t+h} = P_t$).
        - Produces previous return / momentum baseline.
        - Produces EMA and VWAP baselines.
      * Implement `ForecastService`:
        - Acts as the central facade for Ophelia intelligence.
        - Enforces singleton model lifecycle, inference queue, max concurrency = 1, timeout governance (10s), and failure isolation.
        - Status lifecycle: `UNINITIALIZED`, `LOADING`, `READY`, `DEGRADED`, `ERROR`.
  </action>
  <verify>python -c "from control_plane.forecast_service import ForecastService; print(ForecastService.get_status())"</verify>
  <done>ForecastService and providers instantiated with strict lifecycle and governance rules.</done>
</task>

<task type="auto">
  <name>Task 5.2.3: Build strictly causal market-data input pipeline</name>
  <files>control_plane/forecast_service.py</files>
  <action>
    - In `control_plane/forecast_service.py`:
      * Implement `TimesFMFeatureBuilder`:
        - Input: Historical OHLCV, VWAP, returns, volatility.
        - Feature schema version: `TIMESFM_FEATURE_SCHEMA_V1`.
        - Strict covariate classification:
          * `PAST_ONLY`: Historical close, volume, volatility, VWAP, spread, CVD.
          * `FUTURE_KNOWN`: Calendar day of week, hour of day, scheduled macro release flags.
          * `UNKNOWN_FUTURE`: Strict invariant - NEVER provided for future horizons.
        - Strict causality enforcement: at forecast timestamp $T$, no data with timestamp $> T$ is admitted into context. Missing data flagged as `NOT_AVAILABLE`, never filled with fake 0.0.
  </action>
  <verify>python -c "from control_plane.forecast_service import TimesFMFeatureBuilder; print('Feature builder loaded')"</verify>
  <done>Causal feature builder implemented with explicit covariate classification and zero future data access.</done>
</task>

## Success Criteria
- [ ] Forecast and evaluation database schema persisted with all mandatory governance fields.
- [ ] Provider architecture separates `TimesFMProvider` and `StatisticalBaselineProvider`.
- [ ] Feature builder strictly classifies past-only vs future-known covariates with zero lookahead.
- [ ] Quantile monotonicity ($q_{10} \le q_{50} \le q_{90}$) enforced.
