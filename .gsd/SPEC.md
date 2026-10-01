# SPECIFICATION: OPHELIA FULL RECOVERY, AUTONOMOUS EXECUTION REPAIR, TIMESFM + MICROSTRUCTURE INTEGRATION, FULL RELEASE

**Document Status:** FINALIZED  
**Planning Lock:** LOCKED  
**Date:** 2026-10-01  
**Target Environments:** Local Workstation ↔ VPS (`15.235.193.47`) ↔ Android Admin & User Applications  
**Operating Mode:** Default `SHADOW` (Live requires explicit user authorization and strict preflight verification)

---

## 1. MISSION & OBJECTIVES

Ophelia is a production-grade algorithmic cryptocurrency and multi-asset trading platform designed for BingX Perpetual Futures, US Equities intelligence, and Commodities (Gold).

The system has suffered operational and architectural degradation:
1. Automations created via API/UI fail to evaluate or execute because worker queries were constrained by legacy default parameters (`user_id=1`).
2. Autonomous trade slots were disconnected from the worker execution loop; `opportunity_bus.py` was orphaned with broken database references.
3. Auto-provisioning of trade slots within authorized capital envelopes was nonexistent.
4. Position management lacked mathematically exact net breakeven accounting for execution fees, funding, and realized partial exits.
5. TimesFM 3.0 was absent and must be integrated as a pluggable, strictly causal forecasting subsystem.
6. The microstructure research suite (trade flow innovation, duration, order book imbalance, price impact, composite toxicity) was unbuilt.
7. Local, VPS, Admin APK, User APK, and Telegram bot distribution channels have drifted and require full synchronization.

The objective of this specification is to govern the total recovery, repair, implementation, testing, synchronization, and empirical runtime verification of the complete Ophelia platform.

---

## 2. GOVERNING RULES & ARCHITECTURAL INVARIANTS

### 2.1 Deterministic Authority
- The Rust/Python deterministic core on the VPS is the **sole authoritative decision-maker** for market calculations, setup validation, state transitions, position sizing, SL/TP validation, execution gating, order execution, and reconciliation.
- ML and LLM models (TradingAgents, Qwen3 4B, TimesFM 3.0) are strictly **advisory**. They never place exchange orders or dictate capital/risk limits directly.

### 2.2 Server-Authoritative Architecture
- The VPS backend (`15.235.193.47`) is the 24/7 autonomous brain.
- The Android apps (Admin and User) are thin observation, configuration, and manual control interfaces.
- The system must continue monitoring, executing, protecting, trailing, and reconciling positions even when all Android clients are completely offline.

### 2.3 Strict Multi-User Isolation & Zero Fallbacks
- Every position, automation, trade slot, order, notification, credential, and balance is strictly scoped to the authenticated `user_id`.
- **Absolute Prohibition:** Never fall back to `user_id=1`, `user_id or 1`, `last_connected`, or global environment credentials.
- Google Authentication must verify the cryptographic Google JWT token and map to an immutable internal user ID.
- Admin role (`role == 'ADMIN'`) is strictly required for God Eye, system controls, and global limits.

### 2.4 Canonical Geometry & Target Logic
- LONG: $\text{SL} < \text{Entry} < \text{TP1} < \text{TP2} < \text{TP3}$
- SHORT: $\text{SL} > \text{Entry} > \text{TP1} > \text{TP2} > \text{TP3}$
- Risk = $|\text{Entry} - \text{SL}|$, Reward = $|\text{TP} - \text{Entry}|$, $R:R = \text{Reward} / \text{Risk}$.
- Never use artificial formulas like `max(1.0, rr)`. Never synthesize duplicate targets to fabricate TP3. Unavailable targets must be explicitly indicated as unavailable.

### 2.5 Trading Mode Safety
- Default execution mode is `SHADOW`.
- Live trading requires explicit double-confirmation, connected BingX API credentials with valid signature permissions, and passing all 19 deterministic safety gates.

---

## 3. REQUIREMENTS & SYSTEM MODULES

### Module 1: Multi-User Identity & API Hardening
1. Remove all instances of `user_id: int = 1` default arguments across the codebase.
2. Require verified JWT authentication on all user-facing endpoints.
3. Enforce strict isolation: User A cannot read, modify, or execute trades on User B's account.
4. Cleanse God Eye to display only genuine registered users with honest connection states (`CONNECTED`, `NOT_CONNECTED`, `REQUIRES_RECONNECT`).

### Module 2: Slot Allocation Service & Autonomous Provisioning
1. Implement canonical `SlotAllocationService` (`control_plane/slot_engine.py`):
   - `find_eligible_slot(candidate, user_id)`: Filters by enabled state, scope (ALL, CRYPTO, US_MARKET, COMMODITIES), strategy, and status (`AVAILABLE`).
   - `reserve_slot(slot_id, candidate_id, user_id)`: Atomic reservation preventing double-allocation race conditions.
   - `auto_provision_slot(user_id, scope, template)`: Deterministically creates a new slot if capacity permits within user/admin authorized limits (Max slots, margin cap, max leverage, max loss %).
   - `occupy_slot(slot_id, position_id, user_id)`: Transitions slot to `OCCUPIED`.
   - `release_slot(slot_id, user_id)`: Transitions slot back to `AVAILABLE` upon trade closure.
   - `reconcile_slots(user_id)`: Recovers orphaned reservations after server restart.
2. Slot State Machine: `AVAILABLE -> RESERVED -> OCCUPIED -> RECONCILING -> AVAILABLE`.
3. Immutable `ExecutionIntent` created and persisted before any exchange submission.

### Module 3: Automation Worker & Continuous Evaluation Engine
1. Fix `db.list_automations(status, user_id)` to allow querying active automations across all registered users when `user_id is None`.
2. Ensure `automation_worker_loop` continuously cycles through all active automations with exclusive lock lease, updating `last_evaluated_ms`, `last_eval_reason`, and worker heartbeats.
3. Support full lifecycle states: `CREATED`, `ACTIVE`, `PAUSED`, `WAITING_FOR_RETEST`, `WAITING_FOR_SLOT`, `READY_TO_EXECUTE`, `EXECUTING`, `COMPLETED`, `DISABLED`, `FAILED`.

### Module 4: Crypto 5/7 + Retest State Machine
1. Preserve causal sequence: `IDLE -> BREAKOUT_DETECTED -> WAITING_FOR_RETEST -> RETEST_ZONE_TOUCHED -> REJECTION_CONFIRMED -> ENTRY_CANDIDATE -> RISK_VALIDATED -> EXECUTED`.
2. Enforce real price interval for retests (`zone_low` to `zone_high`).
3. Retest confirmation is mandatory for 5/7, 6/7, and 7/7 setups to become `ENTRY_READY`.
4. Enforce HTF Directional Regime (Bullish structure -> LONG only; Bearish structure -> SHORT only).
5. Seamlessly dispatch `ENTRY_READY` candidates to `SlotAllocationService`.

### Module 5: Position Management Daemon
1. Server-side daemon running independently of clients.
2. TP1 Execution: Exactly 50% partial exit at TP1 price.
3. Mathematical Net Breakeven: Stop moved to true break-even taking into account actual entry fills, taker/maker fees, partial exit profit, and accumulated funding.
4. Monotonic Trailing: Trailing stop must never worsen previous stop price.
5. Process Restart Recovery: On daemon boot, query open positions from SQLite and BingX REST API to reconcile and resume trailing/protection without orphaned trades.

### Module 6: TimesFM 3.0 Forecasting Subsystem
1. Pin exact source and checkpoint: `google/timesfm-3.0-pytorch` (330M parameters from `google-research/timesfm`).
2. Architecture: `ForecastService` (`control_plane/forecast_service.py`) supporting `TimesFMProvider` and `StatisticalBaselineProvider`.
3. Forecast Measurable Targets: Future returns, price trajectory, volatility, and quantiles ($q_{10}$ to $q_{90}$).
4. Zero Future Leakage: Strict timestamp-indexed feature builder.
5. Shadow Mode First: Log all forecasts, measure out-of-sample MAE, RMSE, and directional accuracy against baselines before allowing strategy influence.
6. Model Governance: Store model name, commit hash, checkpoint, context length, horizon, latency, and runtime hardware.

### Module 7: Microstructure Research Engine
1. Implement `control_plane/microstructure_engine.py`:
   - Module A: Trade flow innovation $I_t = V_t \cdot (Q_t - \rho Q_{t-1})$ with calibrated $\rho$.
   - Module B: Inter-trade duration, rolling median, duration percentile, and anomaly detection.
   - Module C: Order book depth, spread percentile, OBI, depth depletion/replenishment.
   - Module D: Immediate, temporary, and persistent price impact estimation.
   - Module E: Composite Toxicity score and regime classification (`NORMAL`, `ELEVATED`, `TOXIC_BUY_FLOW`, `TOXIC_SELL_FLOW`, `LIQUIDITY_STRESS`).
   - Experimental ADAOT synthesis score (strictly labeled `RESEARCH / EXPERIMENTAL`).
   - Duration models (ACD-style) and Disposition-effect research modules in `SHADOW_ONLY`.

### Module 8: Multi-Market Parity (US Market & Gold)
1. First-class 3-domain structure: Crypto, US Market, Commodities / Gold.
2. US Market Overview: Top 100, Market Movers (ranked by volume/impact, not raw % change), Sectors (collapsible), Overnight engine.
3. Gold / Commodities: Dynamic BingX instrument resolution (`NCCOGOLD2USD-USDT`), full candidate and execution support.
4. Honest Data Provenance: Mark missing or delayed feeds as `NOT_AVAILABLE` or `DELAYED`. Never display fabricated data.

### Module 9: Admin vs User Scoping & Copy Trading
1. Admin App: God Eye fleet management, master trade broadcasting, global system controls, global risk limits.
2. User App: Scoped to user's own BingX account, own automations, own slots, own positions, and own notifications.
3. Master Copy Trading: Replicate master trades using follower's own slot, margin, and leverage envelope. Independent event idempotency.

### Module 10: Software Update & Telegram APK Distribution
1. Update `UpdateAppScreen.kt` and version endpoint with unified release changelog.
2. Rebuild both Admin APK (`com.ophelia.admin`) and User APK (`com.ophelia.user`).
3. Deploy APKs to VPS `/opt/ophelia/static/` and `/opt/ophelia/control_data/apk/`.
4. Update Telegram bot `/admin_apk` and `/user_apk` commands to distribute verified builds.
5. Validate installation and functionality on the existing Android emulator (`OpheliaPixel`).

### Module 11: Local/VPS Synchronization & Release Audit
1. Push all code updates from Local to VPS (`/opt/ophelia`).
2. Run database migrations on both Local and VPS.
3. Verify systemd services (`ophelia-api`, `ophelia-control`, `ollama`) are running error-free.
4. Generate final comprehensive audit reports and runtime evidence traces.

---

## 4. SUCCESS CRITERIA & EVIDENCE PROOFS

1. **Autonomous Loop Proven End-to-End:**
   - Automation created -> candidate detected -> 5/7 confirmed -> retest touched -> rejection confirmed -> `ENTRY_READY` -> slot reserved -> execution intent created -> order executed (SHADOW/PAPER) -> position protected -> TP1 50% hit -> Net breakeven set -> trailing stop ratcheted -> exit -> reconciliation -> slot released.
2. **Multi-User Proof:**
   - Automated tests proving User A cannot see or manipulate User B's state, and no order executes with fallback credentials.
3. **TimesFM 3.0 Proof:**
   - Runnable benchmark computing quantiles $q_{10}-q_{90}$ for BTC/ETH, proving no future data leakage and recording latency.
4. **Microstructure Proof:**
   - Research engine runs modules A-E with calibrated metrics and bounded toxicity score.
5. **Release Proof:**
   - Both APKs compiled, SHA-256 verified, pushed to VPS static downloads, and validated on emulator.

---

*Status: FINALIZED. Implementation will proceed according to this specification.*
