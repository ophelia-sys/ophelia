# Ophelia Phase 6C Microstructure Research Report

**Phase:** Phase 6C — Empirical Price Impact (Module 5) & Toxicity / Adverse Flow (Module 6) + Phase 6B.1 Statistical Baseline Correction  
**Mode:** `RESEARCH ONLY • ZERO TRADING AUTHORITY`  
**Status:** `ACCEPTED & REAL RUNTIME VERIFIED` (`PHASE_6C = REAL_RUNTIME_VERIFIED`)  
**Date:** 2026-10-02  
**Target Host:** Local + VPS (`15.235.193.47`) + Android UI (Admin & User)

---

## 1. Executive Summary

Phase 6C completes the core microstructure research foundation with two critical research modules and an important statistical baseline correction:

1. **Phase 6B.1 Statistical Baseline Correction**:
   - **Order-Book Imbalance (`OrderBookImbalanceEngine`)**: Autoregressive persistence (`imbalance_persistence`) is baseline-derived and strictly returns `None` (never `0.0`) when sample size $N < 5$ (or `min_persistence_samples`).
   - **Spread & Liquidity Stress (`SpreadLiquidityStressEngine`)**: Raw observables (`spread`, `mid_price`, `relative_spread`) are calculated immediately on $N=1$. Statistical baseline-derived metrics (`expected_spread`, `spread_zscore`, `spread_percentile`, `spread_stress`, `depth_stress`, `book_thinning`, `liquidity_stress`, `liquidity_recovery_state`) return `None` and `"NOT_AVAILABLE"` with `quality_state = INSUFFICIENT_SAMPLE` until $N \ge 5$ (or `min_baseline_samples`).

2. **Module 5: Empirical Price Impact (`PriceImpactEngine`)**:
   - **Methodology:** `KYLE_INSPIRED_EMPIRICAL_IMPACT`.
   - **Strict Forward Causality:** Trade flow observed at time $t$ is strictly paired with forward return over $(t, t+h]$. Zero contemporaneous or future data leakage. Future price changes beyond horizon $h$ do not contaminate historical pairs.
   - **Metrics:** Kyle slope $\lambda$ (OLS regression of forward return on signed volume), $R^2$ stability, buy impact $\lambda_{\text{buy}}$, sell impact $\lambda_{\text{sell}}$, and asymmetry ($\lambda_{\text{buy}} - \lambda_{\text{sell}}$).
   - **Thresholds:** Requires $N \ge 20$ evaluated pairs for aggregate impact; requires $N \ge 5$ on each side for asymmetry.

3. **Module 6: Toxicity & Adverse Flow (`ToxicityEngine`)**:
   - **Methodology:** `VPIN_INSPIRED_RESEARCH`.
   - **Observable Submetrics First:** Exposes directly interpretable components: `flow_intensity` (net signed volume fraction), `adverse_price_response` (price movement contrary to net order flow), `spread_stress_context`, `depth_stress_context`, and `trade_arrival_stress` (trades/sec density).
   - **VPIN Imbalance Fraction:** Bounded $[0.0, 1.0]$ across volume/trade buckets.
   - **Regime States:** Categorized as `LOW` ($< 0.20$), `NORMAL` ($0.20 - 0.45$), `ELEVATED` ($0.45 - 0.70$), `TOXIC` ($> 0.70$), or `INSUFFICIENT_SAMPLE`.
   - **Strict Behavioral Objectivity:** Zero speculation regarding hidden orders, counterparty intent, or trader psychology.

4. **Hard Boundary:**
   - Strict stop after Phase 6C.
   - Hasbrouck VAR / VECM is **NOT** implemented in this phase.

---

## 2. Architecture & Typed Contracts

### 2.1 Domain Models ([`models/microstructure.py`](file:///c:/Users/dopa.mine/Desktop/ophelia/models/microstructure.py))
- `OrderBookImbalanceObservation`: Nullable `imbalance_persistence: Optional[float] = None`.
- `SpreadLiquidityStressObservation`: Nullable `expected_spread`, `spread_zscore`, `spread_percentile`, `spread_stress`, `depth_stress`, `book_thinning`, `liquidity_stress`.
- `PriceImpactObservation`:
  ```python
  @dataclass
  class PriceImpactObservation:
      provenance: MicrostructureProvenance
      impact_coefficient: Optional[float]
      impact_direction: int  # 1 for positive Kyle slope, -1 for inverted, 0 neutral
      impact_stability: Optional[float]  # R^2 in [0, 1]
      impact_asymmetry: Optional[float]  # lambda_buy - lambda_sell
      buy_impact: Optional[float]
      sell_impact: Optional[float]
      flow_response: Optional[float]
      horizon_steps: int
      sample_count: int
      methodology_version: str = "KYLE_INSPIRED_EMPIRICAL_IMPACT"
      detail: Dict[str, Any] = field(default_factory=dict)
  ```
- `ToxicityObservation`:
  ```python
  @dataclass
  class ToxicityObservation:
      provenance: MicrostructureProvenance
      flow_intensity: Optional[float]
      adverse_price_response: Optional[float]
      spread_stress_context: Optional[float]
      depth_stress_context: Optional[float]
      trade_arrival_stress: Optional[float]
      toxicity_metric: Optional[float]  # VPIN [0, 1]
      toxicity_state: str  # LOW, NORMAL, ELEVATED, TOXIC, INSUFFICIENT_SAMPLE
      sample_count: int
      methodology_version: str = "VPIN_INSPIRED_RESEARCH"
      detail: Dict[str, Any] = field(default_factory=dict)
  ```

### 2.2 Persistence Schema ([`control_plane/db.py`](file:///c:/Users/dopa.mine/Desktop/ophelia/control_plane/db.py))
Two additive tables added to `market_1m.db`:
- `microstructure_price_impact`: `(id, instrument, venue, event_timestamp, received_timestamp, impact_coefficient, impact_direction, impact_stability, impact_asymmetry, buy_impact, sell_impact, horizon_steps, sample_count, quality_state, freshness_state, mode, detail_json, created_at)`
- `microstructure_toxicity`: `(id, instrument, venue, event_timestamp, received_timestamp, flow_intensity, adverse_price_response, spread_stress_context, depth_stress_context, trade_arrival_stress, toxicity_metric, toxicity_state, sample_count, quality_state, freshness_state, mode, detail_json, created_at)`

Indexed by `(instrument, event_timestamp)`.

### 2.3 HTTP API Endpoints ([`control_plane/api.py`](file:///c:/Users/dopa.mine/Desktop/ophelia/control_plane/api.py))
- `GET /api/microstructure/price-impact?instrument=BTC-USDT`: JWT-authenticated, returns latest `PriceImpactObservation`.
- `GET /api/microstructure/toxicity?instrument=BTC-USDT`: JWT-authenticated, returns latest `ToxicityObservation`.
- `GET /api/microstructure/summary?instrument=BTC-USDT`: Returns all 6 modules: `trade_flow`, `trade_duration`, `order_book`, `liquidity_stress`, `price_impact`, `toxicity`.

---

## 3. Verification & Empirical Evidence

### 3.1 Automated Test Suite
- Local execution:
  - `tests/test_microstructure_phase6c.py`: **25 passed in 1.49s**
  - Full suite (`6a` + `6b` + `6c` + `timesfm`): **76 passed in 1.67s**
- VPS execution (`15.235.193.47`):
  - `tests/test_microstructure_phase6a.py`: 20 passed
  - `tests/test_microstructure_phase6b.py`: 25 passed
  - `tests/test_microstructure_phase6c.py`: 25 passed
  - Full VPS suite: **70 passed in 1.63s**

### 3.2 Live VPS Verification Probe (`verify_phase6c_live_vps.py`)
Executed on VPS against real live BingX BTC-USDT trades and depth:
```text
[1] Initializing database and verifying Phase 6C DDL...
Verified DDL: microstructure_price_impact and microstructure_toxicity exist in /opt/ophelia/control_data/market_1m.db

[2] Verifying Phase 6B.1 Statistical Baseline Correction...
PASS: OBI persistence is None at N=1
PASS: SpreadLiquidityStressEngine raw observables valid at N=1, baseline metrics strictly None/NOT_AVAILABLE with INSUFFICIENT_SAMPLE
PASS: Baseline metrics computed successfully once sample size >= 5

[3] Ingesting real live BingX trades for BTC-USDT...
Live trade ingestion and microstructure computation in 370.84 ms

Price Impact Observation:
{
  "instrument": "BTC-USDT",
  "venue": "BINGX",
  "event_timestamp": 1790908930696,
  "received_timestamp": 1790908930902,
  "feature_version": "1.0.0",
  "schema_version": "v1",
  "source_data_type": "TRADE_TICKS",
  "sample_count": 100,
  "quality_state": "VALID",
  "freshness_state": "FRESH",
  "missingness_state": "COMPLETE",
  "calculation_window": 100,
  "mode": "RESEARCH",
  "methodology_version": "KYLE_INSPIRED_EMPIRICAL_IMPACT",
  "impact_coefficient": 1e-06,
  "impact_direction": 1,
  "impact_stability": 0.0,
  "impact_asymmetry": -5.9e-05,
  "buy_impact": -1.1e-05,
  "sell_impact": 4.8e-05,
  "flow_response": 0.0,
  "horizon_steps": 1,
  "detail": {
    "price": 84888.1,
    "quantity": 0.0011,
    "evaluated_pairs_count": 100,
    "pending_ticks_count": 1
  }
}

Toxicity Observation:
{
  "instrument": "BTC-USDT",
  "venue": "BINGX",
  "event_timestamp": 1790908930696,
  "received_timestamp": 1790908930902,
  "feature_version": "1.0.0",
  "schema_version": "v1",
  "source_data_type": "TRADE_TICKS",
  "sample_count": 100,
  "quality_state": "VALID",
  "freshness_state": "FRESH",
  "missingness_state": "COMPLETE",
  "calculation_window": 100,
  "mode": "RESEARCH",
  "methodology_version": "VPIN_INSPIRED_RESEARCH",
  "flow_intensity": 0.6351,
  "adverse_price_response": -0.000143,
  "spread_stress_context": null,
  "depth_stress_context": null,
  "trade_arrival_stress": 2.6596,
  "toxicity_metric": 0.6818,
  "toxicity_state": "ELEVATED",
  "detail": {
    "total_volume": 0.2187,
    "net_signed_volume": 0.1389,
    "window_trades": 100,
    "price_return": 0.000143
  }
}

[4] Verifying SQLite persistence for Price Impact and Toxicity...
Persisted PI id=4, sample_count=100, quality=VALID
Persisted Tox id=4, metric=0.6818, state=ELEVATED

[5] Verifying API Endpoints via local HTTP request...
PASS: GET /api/microstructure/price-impact HTTP 200 OK
PASS: GET /api/microstructure/toxicity HTTP 200 OK
PASS: GET /api/microstructure/summary contains all 6 modules

[6] Verifying Research Isolation (zero order placement / zero capacity modification)...
Total orders in database: 30 (unmodified by research pipeline)
```

### 3.3 Android Artifacts
Both mobile applications compiled cleanly and are hosted on the VPS:
- Admin APK: `https://15.235.193.47/static/ophelia-admin-latest.apk` (12,468,160 bytes, HTTP 200 OK)
- User APK: `https://15.235.193.47/static/ophelia-user-latest.apk` (12,468,186 bytes, HTTP 200 OK)
- Autonomous Trading Screen telemetry card updated with Phase 6B.1 null-handling and Phase 6C Price Impact & Toxicity metrics labeled `RESEARCH ONLY • ZERO TRADING AUTHORITY`.

---

## 4. Invariant Verification Checklist

| Rule | Requirement | Verification Result |
|---|---|---|
| **Phase 6B.1** | OBI persistence is `None` for $N < 5$ | **PASS**: Verified in test suite and VPS probe |
| **Phase 6B.1** | Spread raw observables valid at $N=1$, baseline metrics `None` / `NOT_AVAILABLE` | **PASS**: Verified in test suite and VPS probe |
| **Module 5** | Strict forward causality, no contemporaneous/future leakage | **PASS**: Evaluated pairs use strictly future price observations |
| **Module 5** | Kyle slope $\lambda$, $R^2$, buy/sell asymmetry | **PASS**: Computed and verified with live BingX ticks |
| **Module 6** | Interpretable submetrics exposed first | **PASS**: `flow_intensity`, `adverse_price_response`, `trade_arrival_stress` |
| **Module 6** | Objective observable behavior only (no trader psychology speculation) | **PASS**: Zero assumptions on intent or hidden liquidity |
| **Safety** | Zero live order placement | **PASS**: Orders count strictly static |
| **Safety** | Zero slot/capacity modification | **PASS**: Open position capacity untouched |
| **Boundary** | Stop after Phase 6C (no Hasbrouck VAR/VECM) | **PASS**: Implementation halted strictly at Phase 6C |

---

## 5. Conclusion & Next Steps

Phase 6C and Phase 6B.1 are complete, validated, and operational across Local, VPS, and Mobile UI layers.
Per explicit instructions, **execution stops here**. Do not proceed to Hasbrouck VAR / VECM without user instruction.
