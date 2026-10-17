---
phase: 5
plan: 3
wave: 3
---

# Plan 5.3: Verification Test Suites (All 6 Mandatory Suites)

## Objective
Build and verify all 6 test suites required by Section 36 of the specification:
1. `tests/test_timesfm_provider.py`
2. `tests/test_timesfm_no_lookahead.py`
3. `tests/test_timesfm_forecast_contract.py`
4. `tests/test_timesfm_failure_isolation.py`
5. `tests/test_timesfm_scheduler.py`
6. `tests/test_timesfm_evaluation.py`

## Context
- `control_plane/forecast_service.py`
- `control_plane/db.py`

## Tasks

<task type="auto">
  <name>Task 5.3.1: Build model provider, contract, and no-lookahead test suites</name>
  <files>tests/test_timesfm_provider.py, tests/test_timesfm_forecast_contract.py, tests/test_timesfm_no_lookahead.py</files>
  <action>
    - Create `tests/test_timesfm_provider.py`:
      * Test provider initialization and warmup lifecycle (`LOADING` -> `READY`).
      * Test output shape and quantiles monotonicity: $q_{10} \le q_{50} \le q_{90}$.
      * Test univariate price and return trajectories.
      * Test missing data handling (graceful `NOT_AVAILABLE`, no crash).
    - Create `tests/test_timesfm_forecast_contract.py`:
      * Verify all required schema fields are populated: `forecast_id`, `instrument`, `timeframe`, `forecast_timestamp`, `data_timestamp`, `model_name`, `model_version`, `checkpoint`, `context_length`, `horizon`, `input_schema_version`, `forecast_values`, `quantiles`, `forecast_generation_ms`, `latency_ms`, `status`, `data_freshness`, `error`, `mode`.
      * Test status transitions: `SUCCESS`, `STALE_INPUT`, `INSUFFICIENT_DATA`, `MODEL_ERROR`, `TIMEOUT`, `NOT_AVAILABLE`.
    - Create `tests/test_timesfm_no_lookahead.py`:
      * Construct a synthetic timeline with known injected future anomalies / extreme values.
      * Verify feature builder and forecast provider strictly truncate context at time $T$.
      * Assert future values at $t > T$ never leak into inputs, context, or baseline comparisons.
  </action>
  <verify>python -m pytest tests/test_timesfm_provider.py tests/test_timesfm_forecast_contract.py tests/test_timesfm_no_lookahead.py -v</verify>
  <done>Provider, contract, and causality tests pass with 0 lookahead confirmed on synthetic timeline.</done>
</task>

<task type="auto">
  <name>Task 5.3.2: Build failure isolation, scheduler, and evaluation test suites</name>
  <files>tests/test_timesfm_failure_isolation.py, tests/test_timesfm_scheduler.py, tests/test_timesfm_evaluation.py</files>
  <action>
    - Create `tests/test_timesfm_failure_isolation.py`:
      * Simulate TimesFM model crash, timeout (>10s), OOM error, and corrupted input.
      * Assert `ForecastService` catches exceptions, records status `MODEL_ERROR` / `TIMEOUT`, and NEVER brings down `ophelia-api`, `ophelia-control`, or slot management.
      * Assert deterministic strategy validation and position management remain 100% operational when TimesFM fails.
    - Create `tests/test_timesfm_scheduler.py`:
      * Test cadence enforcement: 1m, 5m, 15m, 1h schedules.
      * Test cache validity window (`generated_at`, `valid_until`, `next_refresh_at`).
      * Test concurrency lock: prevent duplicate concurrent inference for the same instrument/timeframe.
    - Create `tests/test_timesfm_evaluation.py`:
      * Test matching historical forecasts against realized future prices.
      * Compute MAE, RMSE, directional accuracy, and quantile coverage ($q_{10}-q_{90}$).
      * Compare against naive persistence and VWAP baselines without lookahead.
  </action>
  <verify>python -m pytest tests/test_timesfm_failure_isolation.py tests/test_timesfm_scheduler.py tests/test_timesfm_evaluation.py -v</verify>
  <done>Failure isolation, scheduler, and baseline evaluation test suites pass completely.</done>
</task>

## Success Criteria
- [ ] All 6 test suites implemented and passing.
- [ ] No future data leakage mathematically verified.
- [ ] TimesFM failure proven not to impact core Ophelia execution or slot services.
- [ ] Quantile hit rate and baseline evaluation metrics verified against ground truth.
