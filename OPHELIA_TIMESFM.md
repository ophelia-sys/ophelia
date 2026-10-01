# OPHELIA — TIMESFM 3.0 FORECASTING SUBSYSTEM
**Phase 5: Real Runtime Verified Integration Specification & Benchmark Report**
**Mode:** `SHADOW_ONLY` | **Direct Trading Authority:** `DISABLED (Fail-Closed)`

---

## 1. System Mission & Boundaries

TimesFM 3.0 is integrated as a **purely advisory, first-class time-series forecasting subsystem** inside Ophelia.
Under the Ophelia architecture, TimesFM has **zero direct execution authority**.

### Non-Negotiable Invariants
1. **Advisory Only**: TimesFM outputs time-series forecasts and uncertainty quantiles. It cannot place orders, close positions, reserve execution slots, adjust leverage, or modify stops/targets.
2. **Deterministic Precedence**: All trade signals require 5/7 deterministic confirmations, structural retest validation, directional regime alignment, and risk manager approval. TimesFM cannot override these rules.
3. **Causal Integrity (Zero Lookahead)**: Market features at forecast timestamp $T$ strictly forbid information generated after $T$.
4. **Failure Isolation**: A crash, timeout, or OOM event in TimesFM sets its status to `NOT_AVAILABLE` or `MODEL_ERROR` without impacting `ophelia-api`, `ophelia-control`, or slot management.

---

## 2. Pinned Environment & Source of Truth

- **Official Repository**: `https://github.com/google-research/timesfm`
- **Pinned Checkpoint**: `google/timesfm-3.0-pytorch`
- **Package Version**: `timesfm-3.0.2`
- **PyTorch Version**: `torch==2.14.1+cpu` (Linux x86_64) / `torch==2.6.0+cpu` (Win32)
- **Model Parameters**: 330M parameters
- **Hardware Profile**: 4 vCPU, ~7.6 GB RAM + 4.0 GB swap active on Ubuntu 26.04 LTS (x86_64)

---

## 3. Architecture & Service Flow

```text
MARKET DATA (SQLite 1m candles)
        ↓
TimesFMFeatureBuilder (Causal cutoff at T, past-only features)
        ↓
ForecastService (Singleton, Cache, Lock governance)
   ┌────┴──────────────────────────┐
   ▼                               ▼
TimesFMProvider          StatisticalBaselineProvider
(PyTorch Checkpoint)     (Naive, EMA, VWAP)
   └────┬──────────────────────────┘
        ▼
ForecastResult (Persisted to SQLite `model_forecasts`)
        ↓
REST API (`/api/timesfm/forecasts`, `/api/timesfm/diagnostics`)
        ↓
Ophelia Intelligence / Android Admin & User UIs (SHADOW Badge)
```

---

## 4. Empirical VPS Performance Benchmark

Measured on live production VPS (`15.235.193.47`):

| Metric | Measured Telemetry |
| :--- | :--- |
| **Model Load Time (from cached weights)** | **7.22 seconds** |
| **Process RAM Before Load** | **247.05 MB** |
| **Process RAM After Load** | **1,519.26 MB** (+1,272.20 MB checkpoint footprint) |
| **Peak RAM During Inference** | **1,530.40 MB** |
| **Cold Inference Latency (batch=1, H=10)** | **1,217.11 ms** |
| **Warm p50 Inference Latency (batch=1, H=10)** | **1,342.52 ms** |
| **Warm p95 Inference Latency (batch=1, H=10)** | **1,406.27 ms** |
| **Average Warm Latency** | **1,329.46 ms** |
| **Batch=2 Inference Latency** | **1,350.14 ms** (**675.07 ms / series**) |
| **CPU Utilization During Inference** | **99.3%** across 4 vCPUs |
| **Quantile Monotonicity ($q_{10} \le q_{50} \le q_{90}$)** | **TRUE (100% verified)** |
| **Output Shape (H=10, 9 quantiles)** | Forecast: `(10,)`, Quantiles: `(10, 9)` |

---

## 5. Input Pipeline & Causal Feature Schema

### Feature Schema: `TIMESFM_FEATURE_SCHEMA_V1`
- **Context Length**: 128 candles (minimum 32 required; returns `INSUFFICIENT_DATA` if $< 32$)
- **Horizon**: 10 steps
- **Past-Only Channels**:
  - `close` price trajectory
  - `volume`
  - `returns` ($r_t = \ln(p_t / p_{t-1})$)
  - `volatility` (rolling 20-period standard deviation of returns)
  - `vwap`
- **Future-Known Covariates**:
  - `minute_of_day` ($[0, 1439]$)
  - `day_of_week` ($[0, 6]$)
- **Strictly Prohibited**: Future prices, future returns, realized CVD, future news, future order flow.

---

## 6. Persisted Database Schema

### Table: `model_forecasts`
```sql
CREATE TABLE IF NOT EXISTS model_forecasts(
    forecast_id TEXT PRIMARY KEY,
    user_id INTEGER,
    instrument TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    forecast_timestamp INTEGER NOT NULL,
    data_timestamp INTEGER NOT NULL,
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    checkpoint TEXT NOT NULL,
    context_length INTEGER NOT NULL,
    horizon INTEGER NOT NULL,
    input_schema_version TEXT NOT NULL,
    forecast_values TEXT NOT NULL,
    quantiles TEXT,
    forecast_generation_ms REAL NOT NULL,
    latency_ms REAL NOT NULL,
    status TEXT NOT NULL,
    data_freshness TEXT NOT NULL,
    error TEXT,
    mode TEXT NOT NULL DEFAULT 'SHADOW',
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_model_forecasts_inst_tf ON model_forecasts(instrument, timeframe, forecast_timestamp);
CREATE INDEX IF NOT EXISTS ix_model_forecasts_status ON model_forecasts(status, mode);
```

### Table: `model_forecast_evaluations`
```sql
CREATE TABLE IF NOT EXISTS model_forecast_evaluations(
    evaluation_id TEXT PRIMARY KEY,
    forecast_id TEXT NOT NULL,
    instrument TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    forecast_timestamp INTEGER NOT NULL,
    evaluation_timestamp INTEGER NOT NULL,
    actual_values TEXT NOT NULL,
    mae REAL NOT NULL,
    rmse REAL NOT NULL,
    direction_correct INTEGER NOT NULL,
    absolute_error REAL NOT NULL,
    signed_error REAL NOT NULL,
    quantile_hit INTEGER,
    coverage REAL,
    regime TEXT,
    created_at INTEGER NOT NULL,
    FOREIGN KEY(forecast_id) REFERENCES model_forecasts(forecast_id)
);
CREATE INDEX IF NOT EXISTS ix_model_forecast_evaluations_inst_tf ON model_forecast_evaluations(instrument, timeframe, evaluation_timestamp);
```

---

## 7. REST API Endpoints

1. **`GET /api/timesfm/diagnostics`** (Admin scoped)
   - Reports model initialization status, checkpoint, hardware RAM/CPU, queue depth, and trading authority (`False`).
2. **`GET /api/timesfm/forecasts?instrument=BTC-USDT&timeframe=5m`**
   - Retrieves latest cached forecast result, direction, return %, uncertainty spread, and quantiles. Triggers asynchronous background refresh if cache is expired.
3. **`GET /api/timesfm/evaluations`**
   - Returns aggregated forensic tracking: evaluation count, MAE, RMSE, directional accuracy %, and quantile coverage.

---

## 8. Android App Integration

- **Admin App (`com.ophelia.admin` v2.8.1 / code 29)**:
  - Added "TIMESFM 3.0 DIAGNOSTICS (SHADOW)" expandable panel in `AutonomousTradingScreen.kt`. Exposes model status, checkpoint, device, average latency, and resource metrics.
  - Added "SYSTEM MAX CONCURRENT CAPACITY: 4" banner and clarified slot terminology: `CONFIGURED`, `AVAILABLE`, `OCCUPIED`, `AUTHORIZED`, `ALLOCATED`.
- **User App (`com.ophelia.user` v1.2.1 / code 4)**:
  - Added "TIMESFM 3.0 FORECAST (SHADOW)" card in `MlScreen.kt`. Displays projected return %, direction badge, uncertainty spread ($\pm X\%$), and $q_{10}, q_{50}, q_{90}$ price levels.
- Both APKs compiled, installed on emulator `emulator-5554`, and verified via screencap.

---

## 9. Test Verification Summary

### Phase 5 Test Suites (`tests/`):
- `tests/test_timesfm_provider.py`: Baseline models, insufficient context, and quantile monotonicity fallback. (4 tests, **PASSED**)
- `tests/test_timesfm_no_lookahead.py`: Strict synthetic timeline zero-lookahead audit, verifying future prices never enter context. (2 tests, **PASSED**)
- `tests/test_timesfm_forecast_contract.py`: Full schema validation, allowed status codes (`SUCCESS`, `INSUFFICIENT_DATA`, `MODEL_ERROR`, `STALE_INPUT`), and DB persistence. (2 tests, **PASSED**)
- `tests/test_timesfm_failure_isolation.py`: Verified that model crash, timeout, or OOM does NOT abort slot allocation or engine operations. (3 tests, **PASSED**)
- `tests/test_timesfm_scheduler.py`: TTL caching, deduplication locks, and worker loop lifecycle. (3 tests, **PASSED**)
- `tests/test_timesfm_evaluation.py`: Realized price matching, MAE/RMSE calculations, and causal baseline comparisons. (2 tests, **PASSED**)
- **Local pytest run**: **16 PASSED in 0.60s**
- **VPS pytest run**: **16 PASSED in 0.68s**

### Phase 1–4 Regression Test Suites:
- `tests/test_phase1_identity_security.py`: **7 PASSED**
- `tests/test_phase2_3_slot_pipeline.py`: **6 PASSED**
- `tests/test_phase4_reconciliation_identity.py`: **9 PASSED**
- `tests/test_phase4_candidate_lifecycle.py`: **7 PASSED**
- **VPS Phase 1–4 pytest run**: **29 PASSED in 1.71s**

---

## 10. Verification State Sign-off

```python
PHASE_5 = "REAL_RUNTIME_VERIFIED"
```
Exact Local / VPS Git Commit Parity: `7965a6f946a3add4e29e2923ca9940c0e1c6ee42`.
