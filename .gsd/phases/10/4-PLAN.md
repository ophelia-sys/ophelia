---
phase: 10
plan: 4
wave: 3
---

# Plan 10.4: Candidate-Specific TimesFM Redesign & Forecast Trade Compatibility Engine

## Objective
Redesign TimesFM 3.0 from a generic periodic forecaster into a candidate-specific future distribution and path forecaster:
- `CandidateForecastContext`: Captures candidate state at `ENTRY_READY`, including `candidate_id`, `canonical_instrument_id`, `direction`, `candidate_timestamp`, `entry`, `sl`, `tp1`, `tp2`, `expected_holding_horizon`, `regime`, and `structure_state`.
- Structured TimesFM output: Path (+15m, +30m, +45m, +60m), quantiles ($q_{10}, q_{50}, q_{90}$), dispersion, expected return.
- `ForecastTradeCompatibilityEngine`: Translates forecast distribution into transparent trade evidence:
  - `forecast_median_vs_entry`, `forecast_return_to_15m/30m/45m/60m`, `forecast_expected_range`, `forecast_dispersion`
  - Quantile distances: $q_{10}/q_{50}/q_{90}$ to entry, SL, TP1
  - Directional alignment, horizon alignment, trade geometry compatibility (`COMPATIBLE`, `INCOMPATIBLE`, `NEUTRAL`, `NOT_AVAILABLE`)
- Expose three distinct dimensions: `FORECAST_DIRECTION`, `FORECAST_DISPERSION`, and `TRADE_COMPATIBILITY`. Zero single uncalibrated AI confidence score.
- Adversarial future-data leakage tests proving forecast frozen at timestamp $T$ cannot be influenced by future price/volume/basis shocks.

## Context
- `control_plane/timesfm_candidate.py`
- `control_plane/trade_compatibility.py`
- `control_plane/forecast_service.py`
- `control_plane/timesfm_adapter.py`
- `control_plane/opportunity_bus.py`

## Tasks

<task type="auto">
  <name>Implement CandidateForecastContext and TimesFM Candidate Forecaster</name>
  <files>control_plane/timesfm_candidate.py</files>
  <action>
    - Create `control_plane/timesfm_candidate.py` with:
      - `CandidateForecastContext`: Dataclass capturing candidate at $T$ (`candidate_id`, `symbol`, `direction`, `entry_price`, `sl_price`, `tp1_price`, `tp2_price`, `regime`, `horizon`, `timestamp_ms`).
      - `CandidateForecastResult`: Dataclass holding `forecast_id`, `candidate_id`, `path_15m`, `path_30m`, `path_45m`, `path_60m`, `q10`, `q50`, `q90`, `dispersion_pct`, `direction_pred`, `status`, `schema_version`.
      - `freeze_candidate_forecast(context, historical_5m_candles)`:
        - Strict cutoff: Context truncates all bars at `ts <= context.timestamp_ms`.
        - Calls TimesFM model (or deterministic mock if PyTorch unavailable).
        - Enforces monotonic quantiles ($q_{10} \le q_{50} \le q_{90}$).
        - Persists immutable candidate forecast record in SQLite table `candidate_forecasts`.
  </action>
  <verify>python -c "from control_plane.timesfm_candidate import CandidateForecastContext, CandidateForecastResult; ctx = CandidateForecastContext('CAND-1', 'BTC', 'LONG', 86000, 85000, 88000, None, 'TREND', '1H', 100000); assert ctx.candidate_id == 'CAND-1'"</verify>
  <done>CandidateForecastContext and TimesFM candidate forecasting pipeline operational with context freeze.</done>
</task>

<task type="auto">
  <name>Implement ForecastTradeCompatibilityEngine</name>
  <files>control_plane/trade_compatibility.py</files>
  <action>
    - Create `control_plane/trade_compatibility.py` with:
      - `ForecastCompatibilityResult`: Exposes three transparent dimensions:
        1. `forecast_direction` (`BULLISH`, `BEARISH`, `NEUTRAL`)
        2. `forecast_dispersion` (`LOW`, `MODERATE`, `HIGH`)
        3. `trade_compatibility` (`COMPATIBLE`, `INCOMPATIBLE`, `NEUTRAL`, `NOT_AVAILABLE`)
        - Quantile distances: $q_{10}$ to SL, $q_{50}$ to Entry, $q_{90}$ to TP1.
        - Path trajectory alignment across 15m, 30m, 45m, 60m horizons.
      - `evaluate_compatibility(candidate_ctx, forecast_result) -> ForecastCompatibilityResult`:
        - Directional check: Does forecast drift align with candidate direction?
        - Geometry check: Is median return towards TP1 rather than SL?
        - Uncertainty check: Does wide dispersion warn of high tail risk ($q_{10}$ breaching SL)?
        - Preserves explicit states: `UNCALIBRATED`, `PRELIMINARY`, `SHADOW`. Zero false precision.
  </action>
  <verify>python -c "from control_plane.timesfm_candidate import CandidateForecastContext, CandidateForecastResult; from control_plane.trade_compatibility import evaluate_compatibility; ctx = CandidateForecastContext('C1', 'BTC', 'LONG', 100, 95, 110, None, 'TREND', '1H', 1000); fc = CandidateForecastResult('F1', 'C1', 'BTC', 1000, 102, 105, 107, 109, 98, 105, 112, 14.0, 'BULLISH', 'SUCCESS', 'V1'); res = evaluate_compatibility(ctx, fc); assert res.trade_compatibility == 'COMPATIBLE'; assert res.forecast_direction == 'BULLISH'"</verify>
  <done>ForecastTradeCompatibilityEngine deterministically evaluates distribution against trade structure.</done>
</task>

<task type="auto">
  <name>Author Unit and Adversarial Future-Leakage Tests</name>
  <files>tests/test_timesfm_trade_compatibility.py</files>
  <action>
    - Test CandidateForecastContext freeze at timestamp $T$.
    - Test ForecastTradeCompatibilityEngine across LONG and SHORT candidates.
    - Test three distinct dimensions exposure (no single uncalibrated AI score).
    - Adversarial future-leakage test:
      - Inject extreme future price (+50%), volume (+1000%), and basis dislocation at $t > T$.
      - Verify that candidate forecast at $T$ is mathematically identical to baseline.
  </action>
  <verify>pytest tests/test_timesfm_trade_compatibility.py -v</verify>
  <done>All candidate forecasting and adversarial leakage tests pass with 100% causal integrity.</done>
</task>

## Success Criteria
- [ ] TimesFM forecasts bound directly to candidate lifecycle at `ENTRY_READY`.
- [ ] ForecastTradeCompatibilityEngine computes path/quantile alignment against trade geometry.
- [ ] Adversarial tests prove zero future data leakage into candidate forecasts.
