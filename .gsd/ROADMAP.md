# ROADMAP: OPHELIA FULL RECOVERY & RELEASE

**Status:** ACTIVE  
**Spec Reference:** [.gsd/SPEC.md](file:///c:/Users/dopa.mine/Desktop/ophelia/.gsd/SPEC.md)  
**Current State Matrix:** [OPHELIA_CURRENT_STATE.md](file:///c:/Users/dopa.mine/Desktop/ophelia/OPHELIA_CURRENT_STATE.md)  
**Total Phases:** 9  

---

## Phases Overview

| Phase | Description | Status | Verification Criteria |
| :--- | :--- | :--- | :--- |
| **Phase 1** | **Multi-User Identity & Execution Safety Hardening** | PENDING | Zero `user_id=1` / global client fallbacks. Multi-user isolation test passing. |
| **Phase 2** | **Slot Allocation Service & Auto-Provisioning** | PENDING | `SlotAllocationService` running with atomic reservation and deterministic auto-provisioning. |
| **Phase 3** | **Automation Worker & Candidate-to-Slot Pipeline** | PENDING | Worker evaluates all active user automations, bridges `ENTRY_READY` candidates to slots. |
| **Phase 4** | **Position Manager Daemon Hardening** | PENDING | TP1 50% partial exit, exact net breakeven with fees/funding, monotonic trailing, restart recovery. |
| **Phase 5** | **TimesFM 3.0 Forecasting Subsystem Integration** | PENDING | PyTorch TimesFM 3.0 pinned, `ForecastService` running shadow forecasts with $q_{10}-q_{90}$ quantiles. |
| **Phase 6** | **Microstructure Research Engine** | PENDING | Modules A–E operational, calibrated metrics, normalized toxicity score, ADAOT research score. |
| **Phase 7** | **Multi-Market Parity (US Market & Gold)** | PENDING | Real data feeds, Top 100/Sectors/Movers, dynamic Gold resolution, honest freshness flags. |
| **Phase 8** | **Software Update, Android APKs & Telegram Distribution** | PENDING | Admin & User APKs compiled, SHA-256 verified, uploaded to VPS static and Telegram bot, tested on emulator. |
| **Phase 9** | **End-to-End Runtime Validation & Final Release** | PENDING | Complete runtime candidate-to-slot-to-exit trace with evidence logs and all 8 release reports. |

---

## Detailed Phase Breakdown

### Phase 1: Multi-User Identity & Execution Safety Hardening
- **Objective:** Eliminate all insecure fallbacks to User 1, default credentials, or environment clients. Enforce strict cryptographic identity and per-user state isolation across database and API.
- **Tasks:**
  1. Remove `user_id: int = 1` default arguments from `control_plane/db.py`, `core.py`, `notifications.py`, `opportunity_bus.py`, and `us_market.py`.
  2. Audit `credential_vault.py` and `_live_client()` to strictly require explicit authenticated `user_id` and owned credentials, rejecting fallback to `from_env()`.
  3. Purge synthetic/demo users from God Eye (`db.purge_synthetic_users()`), displaying honest connection states.
  4. Write and execute multi-user isolation unit tests (`tests/test_user_account_isolation.py`).
- **Done Criteria:** Automated test proves User A cannot read or manipulate User B's state, and unauthenticated execution attempts fail closed.

### Phase 2: Slot Allocation Service & Autonomous Provisioning
- **Objective:** Build dedicated `SlotAllocationService` to manage the complete slot lifecycle, prevent race conditions, and deterministically auto-provision capacity within authorized capital limits.
- **Tasks:**
  1. Create `control_plane/slot_engine.py` with `SlotAllocationService`:
     - `find_eligible_slot(candidate, user_id)`
     - `reserve_slot(slot_id, candidate_id, user_id)` (atomic with SQLite locking)
     - `auto_provision_slot(user_id, scope, template)` respecting max slot limits, margin ceiling, and max leverage
     - `occupy_slot(slot_id, position_id, user_id)`
     - `release_slot(slot_id, user_id)`
     - `reconcile_slots(user_id)`
  2. Implement SQLite migration for `autonomous_trade_slots` ensuring full column coverage (`max_loss_usdt`, `trailing_pct`, `tp1_pct`, `breakeven_mode`, `slot_mode`, `reserved_at`).
  3. Implement `ExecutionIntent` model and persistence table in SQLite (`execution_intents`).
  4. Write test suite verifying atomic double-reservation prevention and auto-provisioning limits.
- **Done Criteria:** Concurrent reservation test passes; auto-provisioning creates slot only within authorized template envelope.

### Phase 3: Automation Worker & Candidate-to-Slot Pipeline
- **Objective:** Fix the automation worker to continuously discover, evaluate, and advance all active user automations and connect qualifying candidates to slot reservation.
- **Tasks:**
  1. Refactor `db.list_automations(status=None, user_id=None)` so passing `user_id=None` fetches active automations across the entire fleet.
  2. Update `evaluate_active_automations()` in `control_plane/core.py` to evaluate each automation independently, recording live evaluation diagnostics (`last_evaluated_ms`, `last_eval_reason`).
  3. Bridge `retest_engine.py` and `intelligence.py` so that when a candidate reaches `ENTRY_READY`, it queries `SlotAllocationService`, creates an `ExecutionIntent`, and dispatches order placement.
  4. Add worker heartbeat and restart recovery mechanism in `control_plane/__main__.py`.
- **Done Criteria:** Newly created automation for any user is immediately evaluated within 5 seconds; qualifying setup atomically reserves a slot and creates execution intent.

### Phase 4: Position Manager Daemon Hardening
- **Objective:** Ensure VPS-authoritative position daemon executes precise 50% partial exit, mathematical net breakeven, monotonic dynamic trailing stops, and survives process restarts without orphaned positions.
- **Tasks:**
  1. Unify position evaluation in `control_plane/position_manager_daemon.py` to handle both SHADOW and LIVE modes.
  2. Implement TP1 execution taking exactly 50% off the table and recording realized P&L.
  3. Implement exact net breakeven calculation factoring in entry fees, exit fees, and funding rate adjustments.
  4. Enforce monotonic trailing stop invariant (new stop must never worsen previous stop).
  5. Add startup reconciliation check against BingX REST API to resume tracking existing open positions.
- **Done Criteria:** Simulated position lifecycle passes: Entry -> TP1 50% reduction -> Net breakeven stop set -> Trailing ratchet -> Exit -> Slot returned to `AVAILABLE`.

### Phase 5: TimesFM 3.0 Forecasting Subsystem Integration (COMPLETED — REAL_RUNTIME_VERIFIED)
- **Objective:** Integrate Google Research's TimesFM 3.0 as a pluggable, strictly causal forecasting engine operating in SHADOW mode.
- **Tasks:**
  1. Pin exact checkpoint and dependency: `google/timesfm-3.0-pytorch` (330M parameters), `timesfm-3.0.2`, `torch-2.14.1+cpu`.
  2. Implement `control_plane/forecast_service.py` with `TimesFMProvider` and `StatisticalBaselineProvider`.
  3. Implement timestamp-aware feature builder supporting past-only context and dynamic covariates without future data leakage.
  4. Generate measurable outputs: future price path, expected return, volatility, and quantiles ($q_{10}-q_{90}$).
  5. Store forecasts in SQLite `model_forecasts` table and benchmark out-of-sample performance (MAE, RMSE, directional accuracy) against naive persistence and VWAP baselines.
- **Done Criteria:** Benchmark script runs TimesFM 3.0 inference on real historical data, produces valid quantiles $q_{10} \le q_{50} \le q_{90}$, and confirms zero lookahead. (VERIFIED ON VPS: p50=1342ms, peak RAM=1530MB, all 16 test suites PASSED, Phase 1-4 tests PASSED).

### Phase 6: Microstructure Research Suite
- **Objective:** Implement the research paper modules as a structured market intelligence layer without turning unvalidated formulas into uncontrolled trading triggers.
- **Tasks:**
  1. Implement `control_plane/microstructure_engine.py` housing:
     - Module A: Trade flow innovation $I_t = V_t \cdot (Q_t - \rho Q_{t-1})$ with calibrated $\rho$.
     - Module B: Inter-trade duration, rolling median, duration percentile, and anomaly metrics.
     - Module C: Visible order book depth, spread percentile, OBI, depth depletion/replenishment.
     - Module D: Immediate, temporary, and persistent price impact estimation.
     - Module E: Composite Toxicity score and regime classification (`NORMAL`, `ELEVATED`, `TOXIC_BUY_FLOW`, `TOXIC_SELL_FLOW`, `LIQUIDITY_STRESS`).
  2. Implement experimental `ADAOT_RESEARCH_SCORE` labeled strictly as `RESEARCH / EXPERIMENTAL`.
  3. Implement ACD duration and disposition-effect research modules in `SHADOW_ONLY`.
  4. Verify all score outputs are normalized to $[0, 100]$.
- **Done Criteria:** Test suite validates all 5 microstructure modules on sample trade and order book feeds, verifying mathematical correctness and bounded outputs.

### Phase 7: Multi-Market Parity (US Market & Gold)
- **Objective:** Provide robust intelligence and trading parity across the 3 domains: Crypto, US Market, and Commodities / Gold.
- **Tasks:**
  1. Harden `control_plane/us_market.py` for Top 100 monitored equities, volume/impact-ranked Market Movers, collapsible Sectors, and Overnight engine.
  2. Implement dynamic BingX instrument resolution for Gold (`NCCOGOLD2USD-USDT`) with automatic fallback to verified TradFi contracts.
  3. Enforce honest data provenance: missing feeds display `NOT_AVAILABLE`; delayed feeds display `DELAYED`; no fabricated data.
- **Done Criteria:** US Market and Gold endpoints return valid real-time or explicitly flagged data; TradFi contract discovery succeeds dynamically.

### Phase 8: Software Update, Android APKs & Telegram Distribution
- **Objective:** Compile clean, synchronized Admin and User APKs, deploy them to VPS static downloads, update Telegram bot distribution, and verify on Android emulator.
- **Tasks:**
  1. Increment version numbers in `android-app/app/build.gradle.kts` (Admin v2.8.1 / code 29; User v1.2.1 / code 4).
  2. Compile `app-admin-debug.apk` and `app-user-debug.apk` using Java 17 and Gradle wrapper.
  3. Compute SHA-256 checksums and upload APKs to VPS `/opt/ophelia/static/` and `/opt/ophelia/control_data/apk/`.
  4. Update `control_plane/telegram_bot.py` `/admin_apk` and `/user_apk` commands with verified paths, checksums, and changelog.
  5. Deploy and verify APK launch on the existing Android emulator (`OpheliaPixel`).
- **Done Criteria:** Both APKs build cleanly, checksums match across Local, VPS, and Telegram, and emulator successfully launches the application.

### Phase 9: End-to-End Runtime Validation & Final Artifact Release
- **Objective:** Execute a complete, verified autonomous trading loop under controlled paper/shadow conditions, capture full empirical evidence, synchronize all environments, and publish final reports.
- **Tasks:**
  1. Synchronize all modified backend code and database migrations to VPS (`/opt/ophelia`).
  2. Restart and verify systemd services (`ophelia-api`, `ophelia-control`, `ollama`) with clean logs.
  3. Execute controlled end-to-end autonomous cycle:
     - Automation creation -> Candidate detection -> Retest confirmation -> `ENTRY_READY` -> Slot reservation -> Execution intent -> Order fill -> Position protection -> TP1 50% exit -> Net breakeven stop -> Trailing ratchet -> Position closure -> Slot release.
  4. Generate and save all 8 mandatory engineering artifacts:
     - `OPHELIA_CURRENT_STATE.md`
     - `OPHELIA_AUTONOMOUS_EXECUTION_AUDIT.md`
     - `OPHELIA_SLOT_ENGINE.md`
     - `OPHELIA_AUTOMATION_ENGINE.md`
     - `OPHELIA_TIMESFM.md`
     - `OPHELIA_MICROSTRUCTURE.md`
     - `OPHELIA_RELEASE.md`
     - `OPHELIA_RUNTIME_EVIDENCE.md`
- **Done Criteria:** All 8 engineering reports complete with verifiable timestamps, IDs, and empirical evidence logs; zero discrepancies across Local, VPS, Admin, and User.
