# OPHELIA — INSTITUTIONAL AUDIT STATE
**Last Full Audit Date:** 2026-08-11
**Latest Verified Test Count:** 102/102 Passing

## Current Architectural Invariants (NON-NEGOTIABLE)
1. **Institutional Math is Observational:** V3 logic does not place, modify, or cancel orders. It has no execution capabilities.
2. **Data Lineage:** Data flows strictly: `BingX -> BingXClient/WebSocket -> InstitutionalDataEngine -> MarketDataSnapshot -> InstitutionalMathEngine -> MarketState -> DecisionEngine -> TradingEngine`.
3. **Canonical OFI Prohibition:** True Order Flow Imbalance is `UNAVAILABLE`. No proxy metric (like depth imbalance or CVD) may be semantically aliased to OFI.
4. **Liquidation Data Prohibition:** Liquidation features remain `UNAVAILABLE` because they cannot be reliably reconstructed from standard volume spikes or OI changes.
5. **No Arbitrary Scoring:** Eventual system will use calibrated directional probability and expected return. Simple additive scoring (A+B+C) is treated as a shadow diagnostic.
6. **No Look-Ahead Bias:** Calculation relies strictly on information available at or before the decision timestamp.
7. **Shadow-First Deployment:** New features must undergo statistical validation in shadow mode before acquiring live decision authority.

---

## Phase 5D.3: BingX WebSocket Capture Integrity Audit & Repair
Status: **IMPLEMENTED — Pending Controlled Live Verification**

### Completed Work
- Discovered and verified correct BingX Perpetual Swap WebSocket endpoint (`wss://open-api-swap.bingx.com/swap-market`)
- Implemented Ping/Pong heartbeat handling (intercept before JSON parse)
- Verified subscription payloads: `@trade`, `@depth20`, `@ticker`
- Confirmed BingX Swap API provides **snapshot-only depth** (@depth20/@depth100), NOT incremental updates
- Confirmed BingX Swap API provides **no sequence numbers** on depth updates
- Canonical OFI classified as `UNAVAILABLE` (no incremental queue data)
- Backpressure-aware async persistence via `queue.Queue(maxsize=100000)` + `_writer_thread`
- Runtime observability counters on WebSocket manager (trades, depth, ticker, pong, reconnects, parse errors)
- Data Quality State Machine verified (VALID → DEGRADED → INSUFFICIENT_DATA transitions)
- Reconnect resilience verified (trade dedup by trade_id survives reconnect replay)
- CVD/TVI derivation verified from real trade aggressor semantics
- Microstructure metrics (mid, spread, queue imbalance, depth imbalance, microprice) verified
- Historical X_t collection path verified (`DecisionEngine.evaluate()` → `PassiveDataCollector.record_state()`)
- OI/Funding integration verified (60s REST cache, dedup by timestamp)

### Blocking Condition
> **BingX API WAF/Rate-Limit Block**
> The execution environment's IP is currently throttled by BingX (`[WinError 10060]`).
> When the API is available, ONE controlled live capture run must verify all subsystems end-to-end.
> Per directive: DO NOT hammer BingX during this condition.

### Test Coverage: 102/102
| Test File | Tests | Status |
|-----------|-------|--------|
| test_decision_engine.py | 15 | ✅ |
| test_institutional_data.py | 4 | ✅ |
| test_institutional_features_5d.py | 5 | ✅ |
| test_institutional_historical_collector.py | 4 | ✅ |
| test_institutional_integration_audit.py | 1 | ✅ |
| test_institutional_label_builder.py | 5 | ✅ |
| test_institutional_math.py | 3 | ✅ |
| test_institutional_math_v3.py | 8 | ✅ |
| test_institutional_microstructure.py | 15 | ✅ |
| test_institutional_orderbook_verification.py | 5 | ✅ |
| test_institutional_trade_aggregation.py | 14 | ✅ |
| test_ofi_lineage_integrity.py | 3 | ✅ |
| test_v3_real_data_bridge.py | 6 | ✅ |
| test_v3_shadow_mode.py | 5 | ✅ |
| test_ws_resilience_and_quality.py | 9 | ✅ |

---

### Phase 5D: BingX Data Acquisition Audit & Feature Foundation
Status: **COMPLETED**

### Phase 5E: Feature Evidence, Statistical Validation & Confidence Foundation
Status: **COMPLETED (RESEARCH)**
- Established forward target definitions (Fwd Dir, Vol-Adj Ret).
- Documented Feature Evidence Registry.
- Validated individual feature evidence (CVD, Microprice, Queue Imbalance, RV).
- Prohibited arbitrary additive scoring and formulated Logistic Regression/XGBoost architectural plan.
- FGV/CISD classified as Research Only.

### Phase 5F.0: Probability Calibration Preflight & Historical Dataset Audit
Status: **COMPLETED (AUDIT ONLY)**
- Designed canonical observation schema (`CALIBRATION_DATASET_SPEC.md`).
- Established that the repository lacks persisted historical WebSocket data (L2, CVD).
- Evaluated overlapping labels and established Embargoed Walk-Forward Validation.
- Declared Model-Readiness Gate: **NOT_READY** (Blocker: No historical ML dataset).

### Phase 5F.1: Passive Historical Evidence Collection & Offline Dataset Builder
Status: **COMPLETED (IMPLEMENTATION)**
- Created `PassiveDataCollector` using SQLite for $X_t$ immutability and JSONL for raw events.
- Enforced zero-execution isolation and deduplication logic.
- Implemented `OfflineLabelBuilder` for strict look-ahead safe $Y_{t+k}$ generation.
- Validated offline leakage boundaries and dataset integrity via deterministic tests.

### Phase 5F.2: Live Historical Data Accumulation & Dataset Readiness Audit
Status: **COMPLETED (AUDIT ONLY)**
- Validated `PassiveDataCollector` integration with live V3 math flow.
- Established rigorous execution-isolation boundaries (zero execution authority).
- Verified data immutability and no future feature contamination.
- Output formal readiness classification: **NOT_READY**. The system must run over WebSocket continuously to build a statistically significant, fully populated calibration dataset.

---

## Audited Files (Phase 5C)
- `core/institutional_math.py` (Legacy Math Engine)
- `institutional/institutional_math.py` (V3 Math Engine)
- `institutional/types.py`
- `institutional/volatility.py`
- `institutional/trend.py`
- `institutional/momentum.py`
- `institutional/normalization.py`
- `institutional/liquidity.py`
- `institutional/order_flow.py`
- `institutional/regime.py`, `institutional/structural_break.py`
- `institutional/open_interest.py`, `institutional/funding.py`, `institutional/liquidation.py`

## Audited Files (Phase 5D.3)
- `institutional/data/websocket_manager.py` (WS endpoint, Ping/Pong, payload parsing, observability)
- `institutional/data/engine.py` (Data consolidation, trade dedup, quality transitions)
- `institutional/data/rest_adapter.py` (REST fallback via BingXClient)
- `institutional/data/models.py` (Typed data models)
- `institutional/historical/collector.py` (Async persistence, backpressure)
- `core/decision_engine.py` (Shadow mode, V3 integration, collector wiring)

## Pending Research Questions
1. Optimal weighting and interactions of composite evidence (e.g. CVD + Visible Impact + Microprice).
2. Proper regime classification implementation (HMM vs. non-parametric clustering) given the compute cost of real-time execution.
3. Calibration methodology for translating momentum/trend structural states into true probabilities (e.g. Logistic Regression vs. XGBoost on MarketState variables).

## Next Audit Scope
**Phase 5D.3 Live Verification:**
When BingX API access is restored, execute ONE controlled live capture (`scripts/phase5d3_live_capture.py`) to verify WebSocket connectivity, real event receipt, and end-to-end feature derivation. Then close Phase 5D.3 and proceed to probability calibration.

---

## Handoff Record
**Date:** 2026-08-11
**Event:** Cross-platform handoff generated for Cline environment.
**Document:** `institutional/OPHELIA_HANDOFF_CLINE.md`
**Next Agent Action:** Refer to handoff document. Do not start new implementation until Phase 5D.3 live capture is complete.
