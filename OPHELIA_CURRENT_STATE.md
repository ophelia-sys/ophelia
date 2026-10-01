# OPHELIA CURRENT STATE MATRIX

**Audit Date:** 2026-10-01  
**Operating Environment:** Local (Windows 10/PowerShell) ↔ VPS (`15.235.193.47`, Ubuntu 26.04 LTS, x86_64, 4 vCPU, 7.6GB RAM)  
**Trading Mode Policy:** Default `SHADOW`  
**Authoritative Execution:** VPS is Authoritative; Android is Client/UI observation & control only.

---

## 1. System Matrix Overview

| Component | Local | VPS | Admin App | User App | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Backend API** | Python FastAPI (`control_plane/api.py`) | Running (`uvicorn` on 127.0.0.1:8000 + Nginx SSL) | `com.ophelia.admin` targets VPS:443 | `com.ophelia.user` targets VPS:443 | DEGRADED |
| **DB Schema** | `market_1m.db` schema present | `market_1m.db` (35 tables) | N/A (REST/WS API consumer) | N/A (REST/WS API consumer) | DRIFT / DEFECT |
| **Automation Engine** | `core.py` has `evaluate_active_automations` | Thread active (`ophelia-control.service`) | Create/Edit/List UI present | Create/Edit/List UI present | BROKEN (user_id=1 filter) |
| **Slot Engine** | DB tables exist, `opportunity_bus.py` orphaned | Table `autonomous_trade_slots` exists | Slot Configuration UI present | Slot Configuration UI present | DISCONNECTED FROM WORKER |
| **Execution Engine** | `core.py` executes directly without slots | Direct execution path in `core.py` | Receives execution events | Receives execution events | BYPASSES SLOTS / DEFECTIVE |
| **Position Manager** | `position_manager_daemon.py` | Thread active in `control_plane` | Active Positions UI | Active Positions UI | LACKS NET BREAKEVEN / RECON |
| **Crypto 5/7 + Retest** | `retest_engine.py` causal state machine | Generating candidates on 1m/3m/5m/15m/30m | ML Setup Review Screen | ML Setup Review Screen | ACTIVE (CANDIDATES NOT DISPATCHED) |
| **US Market** | `us_market.py` Top 100 & Sectors | Real-time scanner & TradFi registry | US Market Screen & Dossier | US Market Screen & Dossier | MISSING COUPLING TO SLOTS |
| **Gold / Commodities** | Dynamic BingX discovery in `config.py` | Ingesting GOLD (XAU) every 15s | Commodities Tab | Commodities Tab | FUNCTIONAL INGEST / UNWIRED SLOTS |
| **TimesFM** | Absent | Absent | Not integrated | Not integrated | MISSING (IMPLEMENTATION REQ) |
| **Microstructure** | Stub in `institutional/microstructure.py` | Basic metrics in `market_state.py` | Basic CVD/Depth in UI | Basic CVD/Depth in UI | MISSING EXPANDED RESEARCH SUITE |
| **Authentication** | Google Token verification present | Active in API middleware | Google Sign-In SDK | Google Sign-In SDK | FALLBACK DEFECTS (`user_id=1`) |
| **BingX Execution** | `bingx_client.py` + `credential_vault.py` | Active with encrypted credentials | Settings / API Key Setup | Settings / API Key Setup | FALLBACK TO GLOBAL CLIENT DEFECT |
| **Copy Trading** | `replication_orchestrator.py` | Bus logic present | Master Trade Broadcast UI | Copy Ophelia Switch | LACKS PER-SLOT ENVELOPE ISOLATION |
| **Software Update** | API endpoint `/api/system/version` | Active on VPS nginx | `UpdateAppScreen.kt` | `UpdateAppScreen.kt` | OUT OF SYNC VERSIONING |
| **Telegram APK Dist** | `telegram_bot.py` `/apk` commands | Bot running (`8368308798:AAE...`) | Distributes Admin APK | Distributes User APK | STALE APK REFS ON DISK |

---

## 2. Component Forensic Analysis

### 2.1 Backend API & Multi-User Authentication
* **EXPECTED:** All requests authenticated via verified Google token (`google_sub` -> `user_id`). Every operation scoped strictly to authenticated `user_id`. Admin operations require `role == 'ADMIN'`. Zero fallbacks to default user.
* **ACTUAL:** 
  - `control_plane/core.py` lines 728, 2143 fall back to `user_id=1` or `effective_uid = user_id if user_id is not None and user_id > 0 else 1`.
  - Over 20 functions in `control_plane/db.py` have signature `user_id: int = 1`.
  - Line 736 in `core.py`: `if is_admin_caller and effective_uid == 1: c = bingx_client.from_env()`.
* **DEFECT:** Silent fallback to User 1 / global server account. Multi-user isolation compromised under default parameter execution.
* **ROOT CAUSE:** Legacy test scaffolding hardcoded `user_id=1` as default parameter across database queries and execution helpers instead of requiring explicit authenticated context.
* **FIX REQUIRED:**
  1. Remove all `user_id: int = 1` default arguments across `control_plane/db.py`, `core.py`, and `notifications.py`.
  2. Require explicit `user_id: int` or `user_id: int | None = None` where `None` explicitly signals system-wide admin query.
  3. Reject any order, position, or slot manipulation lacking verified `user_id`.
  4. Enforce strict cryptographic credential lookup in `credential_vault.py` with zero fallback to `from_env()`.
* **VERIFICATION:** Automated test matrix asserting User A cannot query, reserve, or execute trades for User B; attempting execution with unauthenticated or zero `user_id` raises typed rejection.

---

### 2.2 Automation Engine & "Create Automation" Failure
* **EXPECTED:** When a user creates an automation (`POST /api/automations`), the background worker (`automation_worker_loop`) discovers it, continuously evaluates incoming candles against the strategy/retest state, detects `ENTRY_READY`, reserves an authorized slot, creates an execution intent, validates deterministic risk, submits the order, and monitors the position.
* **ACTUAL:** 
  - `db.list_automations(status="ACTIVE")` was defined as `def list_automations(status: str | None = None, user_id: int = 1) -> list[dict]`.
  - In `core.py:1761`, `evaluate_active_automations()` called `autos = db.list_automations(status="ACTIVE")` without `user_id`, which silently resolved to `user_id=1`.
  - User automations created by any authenticated user (e.g. User 5, User 9, etc.) were **never queried or evaluated** by the worker loop.
  - Active automations 45 and 46 sat on VPS with `last_evaluated_ms: None` indefinitely.
* **DEFECT:** Automations for all users other than User 1 are invisible to the evaluation loop. Furthermore, the automation evaluation loop does not interact with the slot allocation service.
* **ROOT CAUSE:** Default parameter `user_id=1` in `db.list_automations` coupled with the absence of a global fleet evaluation query in `core.py`.
* **FIX REQUIRED:**
  1. Refactor `db.list_automations(status=None, user_id=None)` to return all active automations across all users when `user_id is None`.
  2. Implement per-automation worker heartbeat and explicit state tracking (`last_evaluated_at`, `next_evaluation_at`, `last_decision`, `failure_reason`).
  3. Wire the qualified candidate evaluation to the dedicated `SlotAllocationService`.
* **VERIFICATION:** Create automation for User N; verify worker updates `last_evaluated_ms` within 5 seconds with live diagnostic reason.

---

### 2.3 Slot Allocation Service & Autonomous Provisioning
* **EXPECTED:** Dedicated `SlotAllocationService` that:
  - Discovers eligible available slots across asset classes (Crypto, US Market, Commodities).
  - Atomically reserves slots (`AVAILABLE -> RESERVED -> OCCUPIED -> RECONCILING -> AVAILABLE`).
  - Automatically provisions slots within server-authorized envelopes (Max slots, margin ceiling, max leverage, max loss %) when authorized by user/admin template.
  - Generates immutable `ExecutionIntent` before order submission.
* **ACTUAL:**
  - `opportunity_bus.py` attempted slot reservation but was completely orphaned, never called by any worker, and contained fatal runtime errors (`db.list_setup_candidates` and `db.find_eligible_available_slot` do not exist).
  - `core.py` completely bypassed the `autonomous_trade_slots` table, using only a flat `MAX_OPEN_TRADES` integer check.
  - No slot auto-provisioning existed; if a slot was not manually configured, the engine stalled.
* **DEFECT:** Autonomous trade slots are disconnected from the primary execution path. Auto-provisioning is missing.
* **ROOT CAUSE:** Incomplete refactoring during Phase 5/Phase 7 where slot models were added to SQLite and API endpoints, but never wired to `control_plane/core.py` and `control_plane/__main__.py`.
* **FIX REQUIRED:**
  1. Build canonical `SlotAllocationService` in `control_plane/slot_engine.py`:
     - `find_eligible_slot(candidate, user_id)`
     - `reserve_slot(slot_id, candidate_id, user_id)` (atomic with row locking/idempotency)
     - `auto_provision_slot(user_id, scope, template)` within strict capital bounds
     - `occupy_slot(slot_id, position_id, user_id)`
     - `release_slot(slot_id, user_id)`
     - `reconcile_slots(user_id)`
  2. Wire `SlotAllocationService` into `core.py` and `opportunity_bus.py`.
  3. Log all lifecycle transitions to SQLite `audit` table.
* **VERIFICATION:** Concurrent race test with two candidates attempting to reserve the same slot; exactly one succeeds. Verification of automatic slot creation within template limits.

---

### 2.4 Position Manager Daemon (TP1 50%, Net Breakeven, Monotonic Trailing)
* **EXPECTED:** VPS-authoritative position daemon continuously running independently of Android client:
  - Partial exit: exactly 50% closed at TP1.
  - Breakeven: strictly calculated net cost basis accounting for entry price, execution fees, funding, and realized partial profit.
  - Trailing stop: strictly monotonic (new stop never worsens prior stop), structure- and ATR-aware.
  - Restart recovery: reconstructs state on reboot without losing tracking or placing duplicate orders.
* **ACTUAL:**
  - `position_manager_daemon.py` exists but uses flat stop calculation.
  - `core.py` exit evaluation calls `_live_client()` without passing `user_id`.
  - Breakeven was simplified in some branches to `entry_price` without fee/slippage offset.
* **DEFECT:** Inaccurate breakeven calculation and risk of duplicate exits on process restart.
* **ROOT CAUSE:** Fragmented exit logic split between `core.py` and `position_manager_daemon.py`.
* **FIX REQUIRED:**
  1. Unify position lifecycle state machine: `SIGNAL -> RESERVED -> ORDER_SUBMITTED -> PARTIALLY_FILLED -> FILLED -> PROTECTED -> TP1 -> BREAKEVEN -> TRAILING -> EXITING -> CLOSED -> RECONCILED`.
  2. Implement rigorous net breakeven:
     $$\text{Stop}_{\text{BE}} = \text{Entry} \pm \frac{\text{Total Entry/Exit Fees} + \text{Funding}}{\text{Remaining Quantity}}$$
  3. Enforce monotonic invariant on trailing stops.
  4. Add reconciliation check on daemon startup to sync open positions with BingX REST API.
* **VERIFICATION:** Simulated and paper lifecycle: Entry -> TP1 (50% reduction) -> Breakeven moved with fee cushion -> Trailing stop ratchet -> Exit -> Slot released to `AVAILABLE`.

---

### 2.5 Crypto 5/7 + Retest Engine
* **EXPECTED:**
  - 5/7, 6/7, 7/7 setups require mandatory retest confirmation before `ENTRY_READY`.
  - Retest interval defined by real price range `[zone_low, zone_high]`.
  - HTF Directional Regime rules enforced: Bullish structure allows LONG only, Bearish allows SHORT only.
* **ACTUAL:**
  - `retest_engine.py` is operational and correctly detects states (`WAITING_FOR_RETEST`, `RETEST_ZONE_TOUCHED`, `ENTRY_READY`).
  - Active candidates in `setup_candidates` table reach `ENTRY_READY` but are not consumed by the execution loop because the queue between candidate engine and slot allocation was missing.
* **DEFECT:** Candidates qualify in intelligence layer but halt before slot reservation.
* **ROOT CAUSE:** Missing bridge between `intelligence.py` / `setup_candidates` and the execution dispatch worker.
* **FIX REQUIRED:**
  1. Connect `SetupCandidate` state change to `SlotAllocationService`.
  2. When candidate achieves `ENTRY_READY`, automatically trigger slot lookup and execution intent.
* **VERIFICATION:** Feed closed candle confirming retest touch and rejection; observe candidate transition to `ENTRY_READY` and immediate slot reservation.

---

### 2.6 TimesFM 3.0 Integration
* **EXPECTED:**
  - Pin exact version/checkpoint: `google/timesfm-3.0-pytorch` (330M parameter transformer from `google-research/timesfm`).
  - Architecture: `ForecastService` with `TimesFMProvider` and `StatisticalBaselineProvider`.
  - Forecasts: Future returns, price trajectory, volatility, and quantiles ($q_{10}$ to $q_{90}$).
  - Multivariate inputs and past/future covariates without future data leakage.
  - Initial state: Strictly `SHADOW` mode. Compare against naive persistence and VWAP baselines.
  - Model governance: log model name, commit hash, checkpoint, context length, horizon, latency, device (CPU).
* **ACTUAL:**
  - Zero TimesFM code currently exists in repository.
* **DEFECT:** Missing forecasting subsystem.
* **FIX REQUIRED:**
  1. Implement `control_plane/forecast_service.py` with pluggable providers.
  2. Integrate TimesFM 3.0 PyTorch runtime optimized for CPU inference on VPS (4 vCPUs, float32/bfloat16).
  3. Build feature builder providing causal historical series and covariates.
  4. Store predictions in SQLite table `model_forecasts` with out-of-sample error tracking (MAE, RMSE, directional accuracy).
* **VERIFICATION:** Run benchmark inference on BTC/ETH series; verify quantile outputs ($q_{10} \le q_{50} \le q_{90}$), check latency and verify no future data leakage.

---

### 2.7 Microstructure Research Engine
* **EXPECTED:**
  - Separate research/intelligence layer (not an uncontrolled trigger).
  - Module A: Trade flow innovation $I_t = V_t \cdot (Q_t - E[Q_t|\text{history}])$ with calibrated $\rho$.
  - Module B: Trade duration tracking, rolling median, duration anomaly.
  - Module C: Order book depth, spread percentile, OBI, depth depletion/replenishment.
  - Module D: Price impact estimation (immediate, temporary, persistent).
  - Module E: Composite Toxicity score and normalized regime (`NORMAL`, `ELEVATED`, `TOXIC_BUY_FLOW`, `TOXIC_SELL_FLOW`, `LIQUIDITY_STRESS`).
  - Experimental synthesis: `ADAOT_RESEARCH_SCORE` labeled strictly as `RESEARCH / EXPERIMENTAL`.
  - Disposition-effect and ACD duration models running in `SHADOW_ONLY`.
* **ACTUAL:**
  - Only basic CVD and simple spread proxy exist in `institutional/`.
* **DEFECT:** Missing the specified 5-module microstructure research architecture.
* **FIX REQUIRED:**
  1. Implement `control_plane/microstructure_engine.py` housing Modules A through E.
  2. Implement empirical calibration routines on real trade/depth data.
  3. Keep score outputs contextual/advisory for market regime classification; do not allow direct order triggers.
* **VERIFICATION:** Unit and empirical tests verifying mathematical correctness, bounded scores $[0, 100]$, and regime classification on historical feed.

---

### 2.8 Local ↔ VPS ↔ App Release Synchronization
* **EXPECTED:**
  - Local git repository, VPS backend, SQLite database migrations, Admin APK, User APK, and Telegram bot releases are 100% hash-consistent and version-stamped.
* **ACTUAL:**
  - VPS backend was deployed via manual tarballs; `/opt/ophelia` is not a git checkout.
  - Local repository has uncommitted files and git status untracked artifacts.
  - Admin APK is version `2.8.0` (code 28), User APK is `1.2.0` (code 3).
  - Telegram bot points to local/static paths that must be updated with the newly built synchronized APKs.
* **DEFECT:** Risk of environmental drift across Local, VPS, Admin, and User.
* **FIX REQUIRED:**
  1. Synchronize all modified backend code to VPS `/opt/ophelia`.
  2. Apply database migrations to both local `ophelia.db`/`market_1m.db` and VPS `/opt/ophelia/control_data/market_1m.db`.
  3. Rebuild Admin APK (`assembleAdminDebug`) and User APK (`assembleUserDebug`).
  4. Deploy APKs to VPS `/opt/ophelia/static/` and `/opt/ophelia/control_data/apk/`.
  5. Update Telegram bot distribution paths and version metadata.
  6. Document single unified release identifier across all artifacts.
* **VERIFICATION:** Cross-environment audit comparing git commit SHA, backend version string, DB migration version, APK package hashes, and Telegram download links.
