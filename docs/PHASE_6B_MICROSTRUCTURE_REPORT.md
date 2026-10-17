# Ophelia — Phase 6B Microstructure Research Gate Report
## Order-Book Imbalance & Spread/Liquidity Stress (Modules 3 & 4)

**Date**: 2026-10-02  
**Venue**: BingX Perpetual Swap Futures (`BTC-USDT`)  
**Status**: ACCEPTED  
**Mode**: `RESEARCH`  
**Execution Location**: Local Research Runner & VPS Production Mirror (`15.235.193.47`)  

---

### Strict Validity Governance

| Dimension | Status | Definition / Description |
| :--- | :--- | :--- |
| **RESEARCH_VALIDITY** | **IMPLEMENTATION_VALIDATED** | Mathematical derivations, data pipelines, schema contracts, and boundary conditions verified across 25 focused unit & integration tests. |
| **RUNTIME_VALIDITY** | **VALIDATED** | Real live market depth ingested from BingX `/openApi/swap/v2/quote/depth`, calculated, persisted to SQLite, and exposed over authenticated HTTPS API with zero latency regression. |
| **EMPIRICAL_VALIDITY** | **UNVALIDATED** | Metrics are research variables capturing current order-book depth and spread geometry. They are NOT empirically validated trading signals. |
| **PREDICTIVE_VALIDITY** | **UNCALIBRATED** | No probability calibration or directional predictive claim made. Zero machine-learning confidence scoring. |
| **TRADING_AUTHORITY** | **DISABLED** | Microstructure metrics possess zero direct execution authority. No orders placed, no slots reserved, no risk parameters modified. |

---

### Executive Summary

Phase 6B introduces **Module 3 (Visible Order-Book Imbalance)** and **Module 4 (Spread & Liquidity Stress)** to the Ophelia Microstructure Research subsystem. It builds upon Phase 6A without altering any trade-flow or trade-duration calculations.

All calculations execute with strict non-directional research safety:
1. **Module 3 (Order-Book Imbalance)** computes visible liquidity skew across multiple depth horizons (Top/L1, L5, L10, and Depth $N$). It provides stable zero-denominator handling (`NOT_AVAILABLE`), lag-1 autocorrelation persistence, and explicit depth requested/available/used tracking.
2. **Module 4 (Spread & Liquidity Stress)** quantifies structural spread and depth deterioration against rolling historical baselines ($Z$-scores, percentiles, book thinning, liquidity stress, and recovery state machine). Crossed books ($P_b \ge P_a$) are strictly classified as `DEGRADED`.
3. **Hidden Liquidity Safety**: Hidden liquidity is not directly observable in snapshot data and is hard-coded to `NOT_AVAILABLE`. Cancellation/addition flow is also marked `NOT_AVAILABLE` because the feed provides periodic snapshots rather than event-level queue dynamics.
4. **Zero Trading Authority**: Research code operates purely as descriptive evidence. TimesFM remains permanently retained in `SHADOW_ONLY`.

---

### Acceptance Matrix

| Acceptance Item | Status | Empirical Evidence / Verification Details |
| :--- | :--- | :--- |
| **ORDER_BOOK_IMBALANCE** | **REAL_RUNTIME_PASS** | Real BingX depth ingested for `BTC-USDT` (20 levels available, 10 used). `obi_top = 0.9764`, `obi_depth_N = 0.9811`, bid depth = 204.03, ask depth = 1.95. |
| **SPREAD_STRESS** | **REAL_RUNTIME_PASS** | Real spread measured ($0.50), relative spread ($6 \times 10^{-6}$), mid price ($84,911.35), recovery state `NORMAL`. Non-directional stress evaluated. |
| **HIDDEN_LIQUIDITY_SAFETY**| **PASS** | Hard invariant verified: `hidden_liquidity = "NOT_AVAILABLE"`. No fabricated queue data. |
| **CANCELLATION_SAFETY** | **PASS** | Snapshot semantics enforced: `cancellation_flow = "NOT_AVAILABLE"`. |
| **DATA_QUALITY** | **PASS** | Full quality states handled: `VALID`, `STALE`, `MISSING`, `INSUFFICIENT_SAMPLE`, `OUT_OF_ORDER`, `DUPLICATE`, `NOT_AVAILABLE`, `DEGRADED`. |
| **NO_LOOKAHEAD** | **PASS** | `test_25_temporal_causality_no_lookahead` proves future extreme book collapses/spread blowouts do not affect earlier historical cutoffs. |
| **PROVENANCE** | **PASS** | Full provenance persisted on every record: `instrument`, `venue`, `event_timestamp`, `received_timestamp`, `feature_version`, `schema_version`, `source_data_type="SNAPSHOT_DATA"`, `sample_count`, `quality_state`, `freshness_state`, `missingness_state`, `mode="RESEARCH"`. |
| **RESEARCH_ISOLATION** | **PASS** | Isolated SQLite tables (`microstructure_order_book`, `microstructure_liquidity_stress`) with check constraints and `mode='RESEARCH'` invariant. |
| **API_AUTH** | **PASS** | Endpoints (`/api/microstructure/order-book`, `/api/microstructure/liquidity-stress`, `/api/microstructure/summary`) return HTTP 401 when unauthenticated; HTTP 200 with valid JWT. |
| **VPS_RESOURCE_IMPACT** | **ACCEPTABLE** | VPS CPU = 8.5%, RAM = 43.3% (3.28 GB / 7.56 GB). Depth ingestion latency = 41.11 ms. API query latency < 10 ms. |
| **LOCAL_VPS_PARITY** | **PASS** | 25/25 test cases pass on Windows local runner and Ubuntu 24.04 VPS. |
| **FULL_PHASE_1_5_REGRESSION**| **PASS** | Manual order count unchanged (30), zero slot mutation, zero position interference. |
| **FULL_TIMESFM_REGRESSION** | **PASS** | 26/26 TimesFM regression tests pass in 16.78s on VPS. TimesFM retained in `SHADOW_ONLY`. |
| **PHASE_6A_REGRESSION** | **PASS** | 21/21 Phase 6A tests pass on VPS. Composite `/api/microstructure/summary` returns Modules 1–4 seamlessly. |
| **ANDROID_BUILD** | **PASS** | Both `app-admin-debug.apk` and `app-user-debug.apk` compile cleanly. Admin UI features dedicated Phase 6A & 6B research collapsible with explicit `RESEARCH ONLY • ZERO TRADING AUTHORITY` badge. |
| **LIVE_TRADING_AUTHORITY** | **DISABLED** | Master switch remains permanently `DISABLED`. Research is descriptive only. |

---

### Empirical Telemetry Evidence (Live VPS Capture)

```json
{
  "instrument": "BTC-USDT",
  "venue": "BINGX",
  "event_timestamp": 1790907538034,
  "received_timestamp": 1790907538038,
  "feature_version": "1.0.0",
  "schema_version": "v1",
  "source_data_type": "SNAPSHOT_DATA",
  "quality_state": "VALID",
  "freshness_state": "FRESH",
  "missingness_state": "COMPLETE",
  "mode": "RESEARCH",
  "order_book": {
    "depth_requested": 10,
    "depth_available": 20,
    "depth_used": 10,
    "obi_top": 0.9764,
    "obi_depth_N": 0.9811,
    "bid_depth": 204.0318,
    "ask_depth": 1.9499,
    "imbalance_direction": 1,
    "imbalance_persistence": 0.0,
    "obi_level_1": 0.9764,
    "obi_level_5": 0.9736,
    "obi_level_10": 0.9811,
    "cancellation_flow": "NOT_AVAILABLE",
    "hidden_liquidity": "NOT_AVAILABLE",
    "book_snapshot_age_ms": 4,
    "sequence_state": "NOT_AVAILABLE"
  },
  "liquidity_stress": {
    "spread": 0.50,
    "mid_price": 84911.35,
    "relative_spread": 0.000006,
    "expected_spread": 0.50,
    "spread_zscore": 0.0,
    "spread_percentile": 50.0,
    "spread_stress": 0.0,
    "depth_stress": 0.0,
    "book_thinning": false,
    "liquidity_stress": 0.0,
    "liquidity_recovery_state": "NORMAL"
  }
}
```

---

### Test Suite Execution Summary

#### 1. Phase 6B Test Suite (`tests/test_microstructure_phase6b.py`) — 25/25 PASSED
- `test_01_empty_book`: PASS
- `test_02_one_sided_book`: PASS
- `test_03_normal_two_sided_book`: PASS
- `test_04_zero_denominator`: PASS (returns `None` / `NOT_AVAILABLE`, no fake zero)
- `test_05_missing_levels`: PASS
- `test_06_insufficient_depth`: PASS (flags `INSUFFICIENT_SAMPLE`)
- `test_07_crossed_book`: PASS (flags `DEGRADED`, spread is `None`)
- `test_08_wide_spread`: PASS (z-score and spread percentile elevated)
- `test_09_spread_compression`: PASS
- `test_10_depth_collapse`: PASS (triggers `book_thinning` and elevated `depth_stress`)
- `test_11_depth_recovery`: PASS (transitions to `RECOVERING`)
- `test_12_duplicate_snapshot`: PASS (flags `DUPLICATE`)
- `test_13_out_of_order_snapshot`: PASS (flags `OUT_OF_ORDER`)
- `test_14_stale_snapshot`: PASS (flags `STALE`)
- `test_15_sequence_gap`: PASS (flags `sequence_state="GAP_DETECTED"`)
- `test_16_future_update_rejection`: PASS (rejects events > 5s in future)
- `test_17_hidden_liquidity_safety`: PASS (guaranteed `NOT_AVAILABLE`)
- `test_18_cancellation_unavailable_from_snapshot`: PASS (guaranteed `NOT_AVAILABLE`)
- `test_19_provenance_persistence`: PASS
- `test_20_research_isolation`: PASS
- `test_21_no_slot_mutation`: PASS
- `test_22_no_order_submission`: PASS
- `test_23_api_authorization`: PASS (401 unauthenticated, 200 authenticated)
- `test_24_restart_and_recovery`: PASS (history restoration from SQLite)
- `test_25_temporal_causality_no_lookahead`: PASS (strict causal isolation verified)

#### 2. Phase 6A Regression Suite (`tests/test_microstructure_phase6a.py`, `tests/test_microstructure_api.py`) — 21/21 PASSED
- All 21 Trade-Flow Innovation & Trade-Duration tests pass with 0 regressions.

#### 3. TimesFM Regression Suite (`tests/test_timesfm*.py`) — 26/26 PASSED
- 26 tests across auth, cache causality, model crash isolation, quantile monotonicity, and scheduler lifecycle pass in 16.78s.

---

### Android Verification

1. **Compilation**: `assembleAdminDebug` (BUILD SUCCESSFUL in 1m 16s) and `assembleUserDebug` (BUILD SUCCESSFUL in 44s) verified.
2. **UI Implementation**:
   - `AutonomousTradingScreen.kt`: Collapsible 4 expanded to **"MICROSTRUCTURE RESEARCH (PHASE 6A & 6B)"**.
   - Explicit subtitle: **"BTC-USDT • RESEARCH ONLY • ZERO TRADING AUTHORITY"**.
   - Displays Module 3 (Bid Depth, Ask Depth, OBI Top, OBI L10, Persistence, Freshness, Quality).
   - Displays Module 4 (Spread, Relative Spread, Spread Stress, Depth Stress, Book Thinning, Recovery State, Freshness, Quality).
   - Does NOT display BUY/SELL signals or trade confidence based on microstructure.
3. **Deployment**: APKs deployed to `/opt/ophelia/control_data/apk/` and exposed via `/download/{channel}`.

---

### Boundary Rules & Next Steps

1. **Stop Condition**: Phase 6B is complete. Do NOT proceed to Hasbrouck VAR, VECM, price impact, or toxicity modeling without explicit user instruction.
2. **Model Safety**: TimesFM permanently retained in `SHADOW_ONLY`.
3. **Execution Safety**: `LIVE_TRADING_AUTHORITY = DISABLED`.
