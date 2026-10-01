---
phase: 5
plan: 1
wave: 1
---

# Plan 5.1: TimesFM 3.0 Forecasting Subsystem Integration

## Objective
Integrate TimesFM 3.0 (`google/timesfm-3.0-pytorch` from `google-research/timesfm`) as a pluggable, strictly causal forecasting subsystem (`control_plane/forecast_service.py`). Implement the architecture: Market Data -> Feature Builder -> Forecast Service -> Forecast Distribution -> ML Intelligence -> Deterministic Risk -> Execution. Maintain TimesFM strictly in SHADOW mode, benchmarking out-of-sample against naive persistence and VWAP baselines.

## Context
- [.gsd/SPEC.md](file:///c:/Users/dopa.mine/Desktop/ophelia/.gsd/SPEC.md)
- [OPHELIA_CURRENT_STATE.md](file:///c:/Users/dopa.mine/Desktop/ophelia/OPHELIA_CURRENT_STATE.md)
- `control_plane/db.py`
- `control_plane/intelligence.py`

## Tasks

<task type="auto">
  <name>Task 5.1: Implement ForecastService and TimesFMProvider</name>
  <files>control_plane/forecast_service.py, control_plane/db.py</files>
  <action>
    - In `control_plane/db.py`:
      * Create table `model_forecasts`:
        `forecast_id`, `model_name`, `model_version`, `checkpoint`, `symbol`, `timeframe`, `forecast_ts`, `context_len`, `horizon`, `forecast_json`, `quantiles_json`, `actual_json`, `mae`, `rmse`, `direction_correct`, `runtime_ms`, `hardware`, `created_ms`.
      * Add helper methods: `save_forecast`, `update_forecast_actuals`, `get_recent_forecasts`.
    - Create `control_plane/forecast_service.py`:
      * Define abstract base class `ForecastProvider`.
      * Implement `TimesFMProvider`:
        - Pinned checkpoint: `google/timesfm-3.0-pytorch` (330M parameter transformer).
        - Handles zero-shot forecasting on CPU (VPS 4 vCPUs) or GPU if available.
        - Provides `forecast(context_series, horizon=10, freq="1m")`.
        - Generates future return trajectory, price trajectory, volatility, and quantiles ($q_{10}, q_{20}, \dots, q_{90}$).
      * Implement `StatisticalBaselineProvider`:
        - Computes naive persistence baseline, EMA baseline, and VWAP baseline.
      * Implement `ForecastService`:
        - Orchestrates feature preparation, provider execution, quantile validation ($q_{10} \le q_{50} \le q_{90}$), and shadow evaluation logging.
        - Strictly operates in `SHADOW` mode. Forecasts inform market intelligence/context; they cannot directly trigger live BingX orders.
  </action>
  <verify>python -m pytest tests/test_forecast_service.py -v</verify>
  <done>ForecastService produces multi-quantile distributions, logs governance metadata, and validates zero lookahead.</done>
</task>

<task type="auto">
  <name>Task 5.2: Build causal feature builder and benchmark harness</name>
  <files>control_plane/forecast_service.py, tests/test_forecast_service.py</files>
  <action>
    - In `control_plane/forecast_service.py`:
      * Build `TimesFMFeatureBuilder`:
        - Input: Historical OHLCV, session state, VWAP.
        - Covariates: Past-only historical volume and volatility; future-known session calendar.
        - Invariant: Zero future data leakage. Candle $N$ cannot access information past timestamp $T_N$.
    - Create `tests/test_forecast_service.py`:
      * Test input schema validation.
      * Test quantile ordering: $q_{10} \le q_{20} \le \dots \le q_{90}$.
      * Test timestamp causality (no future leakage).
      * Test graceful fallback when model or dependency is loading.
      * Measure and report inference latency on 100 historical bars.
  </action>
  <verify>python -m pytest tests/test_forecast_service.py -v</verify>
  <done>Benchmark test confirms valid quantiles, zero future leakage, and tracks latency within VPS budget.</done>
</task>

## Success Criteria
- [ ] TimesFM 3.0 pinned to exact source (`google/timesfm-3.0-pytorch`).
- [ ] Forecast outputs measurable future returns, prices, and 9 quantiles ($q_{10}-q_{90}$).
- [ ] Zero future data leakage proven by causality tests.
- [ ] Shadow mode records forecasts and evaluates out-of-sample accuracy against baselines.
- [ ] Full governance metadata persisted per forecast.
