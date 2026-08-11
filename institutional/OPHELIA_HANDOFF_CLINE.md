# OPHELIA — CLINE HANDOFF DOCUMENT
**Target Phase:** Phase 5D.3 (Verification) / Phase 5F (Calibration Prep)
**Current Status:** STRUCTURALLY VERIFIED (Pending Live Runtime Verification)

READ THIS DOCUMENT FIRST before resuming implementation on the Ophelia project. This document is the single source of context for the repository state, architectural boundaries, and immediate next actions.

## 1. PROJECT IDENTITY
Ophelia is a production-grade algorithmic cryptocurrency trading system built for BingX Perpetual Swap Futures. The current development focus is the **Institutional V3 Subsystem**, which replaces simple heuristic indicators with verifiable, evidence-based institutional microstructure metrics (e.g., volume-weighted microprice, queue imbalance, CVD, and structural breaks) to eventually generate statistically calibrated predictive probabilities.

## 2. CURRENT ARCHITECTURE
Data flows strictly downwards in a read-only observability pipeline. V3 operates in a "shadow" mode for validation.

```text
BingX
  ->
BingXClient / WebSocket (Transport Layer)
  ->
InstitutionalDataEngine (Ingestion, Deduplication, Aggregation)
  ->
MarketDataSnapshot (Typed immutable state at timestamp T)
  ->
InstitutionalMathEngine (Feature extraction & normalization)
  ->
MarketState (Final composite feature vector)
  ->
DecisionEngine (Evaluates signal against MarketState; persists to SQLite)
  ->
TradingEngine (Executes legacy strategy logic)
```

**Execution Authority:**
- The legacy `DecisionEngine` retains all execution approval authority.
- The entire `institutional/` module (V3) is strictly **observational**.

## 3. NON-NEGOTIABLE INVARIANTS
The following rules must be strictly adhered to:
- **Institutional Math is observational:** V3 cannot place, modify, or cancel orders.
- **No execution authority** may be granted to V3 without explicit architectural authorization.
- **Canonical OFI remains UNAVAILABLE:** BingX does not provide non-gapped incremental queue data.
- **No proxy renaming:** Do not alias queue imbalance, depth imbalance, or CVD as "OFI".
- **Liquidations remain UNAVAILABLE:** Cannot be fabricated reliably from standard data.
- **No look-ahead bias:** Features must only use data available *at or before* the decision timestamp.
- **Trailing normalization only:** Z-scores must use rolling trailing windows, never future data.
- **No arbitrary A+B+C confidence scoring:** Future confidence models must output statistically calibrated probabilities or expected returns, not additive point scores.
- **Shadow-first deployment:** New logic must run in shadow mode (like Phase 5F.1 passive collection) before controlling live money.
- **Audits are mandatory:** Perform audits at *batch boundaries*, not after every minor job.

## 4. PHASE HISTORY

- **Phase 5B.1–5B.3:** 
  - *Objective:* Stabilize the legacy pipeline and establish standard metrics.
  - *Implementation:* Built baseline features (VWAP, basic volatility).
  - *Audit:* Passed.
  - *Limitation:* Features lacked true institutional microstructure depth.
- **Phase 5B.3.1:** 
  - *Objective:* Create real-data bridge for V3 integration.
  - *Implementation:* Pushed data down from TradingEngine to DecisionEngine for shadow math.
  - *Audit:* Passed.
- **Phase 5C:** 
  - *Objective:* Mathematical specification and feature engineering.
  - *Implementation:* Coded equations for microprice, queue imbalance, kernels, regime detection.
  - *Audit:* Passed.
  - *Limitation:* Operated primarily on synthetic/static data.
- **Phase 5D & 5D.2:** 
  - *Objective:* BingX data acquisition audit & feature foundation.
  - *Implementation:* Initial WS ingestion and REST adapters.
  - *Audit:* Passed structurally.
  - *Limitation:* WS endpoint instability and missing event sequencing exposed gaps.
- **Phase 5D.3:** 
  - *Objective:* BingX WebSocket Capture Integrity Audit & Repair.
  - *Implementation:* Repaired WS to use Swap V2 API, added Ping/Pong, added backpressure queue, built robust reconnect/data-quality state machine.
  - *Audit:* 102/102 Structural/Local Tests Passed.
  - *Limitation:* **Blocked on live runtime verification due to BingX WAF rate-limit.**
- **Phase 5E:** 
  - *Objective:* Feature evidence and statistical validation foundation.
  - *Implementation:* Catalogued which mathematical features actually have predictive power (CVD, Microprice, KER). Prohibited arbitrary additive scoring.
  - *Audit:* Passed (Documentation/Research phase).
- **Phase 5F.0:** 
  - *Objective:* Probability calibration preflight.
  - *Implementation:* Designed canonical observation schema.
  - *Audit:* Concluded system was **NOT_READY** for ML calibration due to a lack of recorded historical data.
- **Phase 5F.1:** 
  - *Objective:* Passive historical evidence collection.
  - *Implementation:* Built SQLite X_t persistence and offline Y_t+k label builder.
  - *Audit:* Passed.
- **Phase 5F.2:** 
  - *Objective:* Live historical data accumulation audit.
  - *Implementation:* Audited the collection boundary.
  - *Audit:* Declared **NOT_READY** for calibration until the live WebSocket data actually runs and accumulates sufficient historical data.

## 5. FEATURE INVENTORY

**Volatility:**
- Log Returns: VALIDATED
- Realized Volatility: VALIDATED
- Parkinson: REDUNDANT
- Garman-Klass: REDUNDANT
- ATR: VALIDATED

**Trend/Regime:**
- KER: VALIDATED
- Directional Persistence: PROMISING
- ATR-scaled Trend: PROMISING
- EMA Structure: WEAK
- HMM status: RESEARCH_ONLY (Slow Path / Stubbed)
- PELT status: RESEARCH_ONLY (Slow Path / Stubbed)

**Momentum:**
- Momentum Z-score: VALIDATED
- Momentum acceleration: PROMISING
- Volume imbalance: VALIDATED

**Liquidity:**
- Mid Price: VALIDATED
- Spread: VALIDATED
- Queue Imbalance: VALIDATED
- Depth Imbalance: PROMISING
- Microprice: VALIDATED
- Book Concentration: WEAK
- Book Slope: PROMISING
- Visible Impact: PROMISING
- Amihud: WEAK
- Kyle Lambda: STUBBED

**Order Flow:**
- CVD: VALIDATED
- TVI: PROMISING
- OFI: **UNAVAILABLE**
- OI: INSUFFICIENT_DATA (Requires history)
- Funding: INSUFFICIENT_DATA (Requires history)
- Liquidations: **UNAVAILABLE**
- VWAP Deviation: PROMISING
- FGV / CISD: RESEARCH_ONLY

## 6. PHASE 5D.3 CURRENT STATE
- **Correct BingX Swap WebSocket endpoint:** `wss://open-api-swap.bingx.com/swap-market`
- **Current subscriptions:** `@trade`, `@depth20`, `@ticker`
- **Ping/Pong:** Handled pre-JSON-parse to ensure heartbeat survival.
- **Trade ingestion:** Dedicated deduplication by `trade_id` surviving reconnect replays.
- **Depth semantics:** `@depth20` is a snapshot stream. It is NOT incremental. 
- **Sequence limitations:** The Swap API provides NO sequence identifiers for local queue reconstruction.
- **OFI limitation:** Canonical OFI is mathematically impossible on this feed.
- **CVD/TVI:** Derived correctly using TradeEvent `is_buyer_maker` flag to determine the aggressor.
- **Microstructure:** BBO, Spread, Queue Imbalance, Microprice derived directly from snapshot.
- **Asynchronous persistence:** `queue.Queue` with a background `_writer_thread` decouples disk I/O from network ingestion.
- **Runtime observability:** Counters added for trade/depth/ticker events, reconnects, pongs, and parse errors.
- **Reconnect resilience & Data Quality:** State machine gracefully handles `VALID` → `DEGRADED` → `INSUFFICIENT_DATA` transitions based on missing data or stale books (>30s), falling back to REST if necessary.

## 7. CURRENT BLOCKER
**Job 18 — Controlled five-minute BingX live capture.**
The system encountered a `WinError 10060` (WAF rate limit / IP block) due to iterative API testing. 
**DO NOT repeatedly retry or hammer the API.** The codebase is structurally complete. We must wait for the throttle to clear.

## 8. HISTORICAL DATA / CALIBRATION STATE
Phase 5F.0 evaluated model readiness and concluded **NOT_READY**.
Phase 5F.1 built the passive SQLite collector.
Phase 5F.2 audited the collector and concluded **NOT_READY** for calibration, because the database is empty/synthetic.
**Do not begin model training.** A live, persistent, multi-day historical dataset must be collected via the WebSocket layer first.

## 9. IMPORTANT RAW-TRADE PERSISTENCE LIMITATION
- `TradeEvent` objects originate at `InstitutionalDataEngine._on_trade()`.
- `DecisionEngine` receives the aggregated `MarketDataSnapshot` containing CVD/TVI/Volume.
- The `PassiveDataCollector` currently records canonical `X_t` vectors (SQLite) and raw orderbooks (JSONL).
- **Raw `TradeEvent` persistence is NOT currently wired** because the snapshot does not carry the raw objects.
- Do NOT silently redesign this to pass raw trades. Note this as a future controlled orchestration enhancement if tick-level historical backtesting is required. The current SQLite `X_t` collection meets the Phase 5F probability calibration requirements.

## 10. CURRENT FILE MAP
- `institutional/data/websocket_manager.py`: Daemon WS connection, subscriptions, ping/pong, payload parsing, observability counters.
- `institutional/data/engine.py`: Central data bus, state deduplication, missing-data handling, time-window aggregation, snapshot generation.
- `institutional/data/rest_adapter.py`: Fallback REST mechanism for missing/stale WS data, funding/OI.
- `institutional/data/models.py`: Strongly typed data representations (`TradeEvent`, `OrderBookSnapshot`, `MarketDataSnapshot`).
- `institutional/institutional_math.py`: V3 Math Engine, consuming snapshots and producing statistical features.
- `institutional/types.py`: Enums (`DataQuality`, `FeatureStatus`) and core state models (`MarketState`, `MicrostructureState`).
- `institutional/historical/collector.py`: Async queue-based SQLite persistence for historical states and JSONL raw event logging.
- `institutional/historical/label_builder.py`: Offline script to construct $Y_{t+k}$ labels safely from collected historical data.
- `core/decision_engine.py`: Execution approval layer, handles V3 shadow evaluation and wires the collector.
- `core/trading_engine.py`: Orchestrator of strategy evaluation and order execution (V3 is strictly excluded from execution here).
- `scripts/phase5d3_live_capture.py`: Verification script to test live WS metrics without trading.
- `institutional/AUDIT_STATE.md`: Central record of phase progress, invariants, and audit status.
- `institutional/FEATURE_REGISTRY.md`: Map of implemented formulas and data sources.
- `institutional/FEATURE_EVIDENCE_REGISTRY.md`: Map of feature predictive validity (Validated vs Weak).

## 11. TEST STATUS
**102/102 PASSING.**
Run command: `PYTHONPATH="." pytest tests/ -v`

## 12. NEXT ACTION
1. Wait for BingX WAF/rate-limit recovery.
2. Run ONE controlled five-minute live capture: `PYTHONPATH="." python scripts/phase5d3_live_capture.py 300`
3. Analyze the result to ensure real trades, depth, and CVD populate correctly.
4. Perform the final Phase 5D.3 batch closeout audit based on that runtime verification.
5. Only after successful closeout, reassess whether Phase 5F dataset accumulation can begin.

## 13. RESUME RULES FOR CLINE
**READ THIS FILE EVERY TIME YOU START A SESSION.**
- Inspect only the files relevant to the exact current task.
- Do not redo completed phases.
- Do not repeatedly audit unchanged code.
- Do not hammer BingX.
- Do not fabricate unavailable data (e.g. Liquidations, OFI).
- Do not substitute Binance data and call it BingX data.
- Do not introduce canonical OFI proxies.
- Do not train a model on insufficient data.
- Do not grant V3 execution authority.
- Do not skip required batch audits.
- **Workflow:** State proposed change -> Identify impact -> Implement authorized batch -> Run tests -> Perform one batch audit -> Stop at the gate.
