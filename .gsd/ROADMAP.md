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
| **Phase 5** | **TimesFM 3.0 Forecasting Subsystem Integration** | COMPLETE | PyTorch TimesFM 3.0 pinned, `ForecastService` running shadow forecasts with $q_{10}-q_{90}$ quantiles. |
| **Phase 5.5** | **Resource / CPU Optimization Gate** | COMPLETE | TimesFM retained; VPS baseline, sub-component profiling, thread/batch benchmarking, redundancy reduction, critical path protection verified. |
| **Phase 6** | **Microstructure Research Engine (6A, 6B, 6B.1, 6C)** | COMPLETE | Modules 1–6 operational, strict forward causality, VPIN toxicity, baseline corrections verified. |
| **Phase 7** | **Multi-Market Parity (US Market & Gold)** | PENDING | Real data feeds, Top 100/Sectors/Movers, dynamic Gold resolution, honest freshness flags. |
| **Phase 8** | **Software Update, Android APKs & Telegram Distribution** | PENDING | Admin & User APKs compiled, SHA-256 verified, uploaded to VPS static and Telegram bot, tested on emulator. |
| **Phase 9** | **End-to-End Runtime Validation & Final Release** | PENDING | Complete runtime candidate-to-slot-to-exit trace with evidence logs and all 8 release reports. |
| **Phase 10** | **Multi-Venue Market Intelligence & TimesFM Trade Compatibility** | COMPLETE | Binance primary ingestion, cross-venue basis engine, candidate-level empirical study. |
| **Phase 10.1** | **Retest-State TimesFM Validation + 5M Forecast Architecture** | COMPLETE | Causal retest engine at ENTRY_READY, 5m/12-step path, multi-metric compatibility, 44/44 tests passed. |
| **Phase 10.2** | **TimesFM Forensic Validation + Forecast-Role Discovery** | COMPLETE | Model execution verified, 3.70ms reconciled (warm 433ms), 105 vs 106 DB count reconciled, Target Reachability edge discovered. |
| **Phase 10.3** | **Out-of-Sample TimesFM Role Validation** | COMPLETE | Multi-month (61d, 1229 cands) OOS audit; Target Reachability OUT-OF-SAMPLE SUPPORTED (p=0.0002); base strategy fee drag proven. |
| **Phase 11** | **Deterministic Strategy Repair & Regime / Geometry Discovery** | COMPLETE | Failure taxonomy audited (80.4% RANGE_CHOP); R:R sweet spot discovered (1.25-1.50 is +23.68 Gross R, PF 1.56); Structure Quality (Variant D: +15.19 Gross R, PF 1.32, -75% noise); 7/7 tests passing. |
| **Phase 11.5** | **HTF Regime & Trade Management Research for Variant D** | COMPLETE | 4H trend alignment audited (+16.59 Gross R, PF 1.75 on TEST); Breakeven ratchets empirically proven toxic (WR collapses to 9.5%); Fixed SL/TP optimal; 7/7 unit tests passing on Local & VPS. |
| **Phase 12** | **Fresh-Period Incremental TimesFM Validation** | COMPLETE | Evaluated on fresh 122d dataset (2023-12 to 2024-03, 527k rows). TimesFM reachability boosts WR from 18.2% to 34.1% and flips Gross R to +3.58R (PF 1.16). 9.0 bps friction exceeds gross edge (-17.08R Net R). Stop condition: TIMESFM INCREMENTAL VALUE NOT ESTABLISHED. 7/7 unit tests passing on Local & VPS. |
| **Phase 13** | **Alpha Discovery Reset & Structural Stop-Room Research** | COMPLETE | Evaluated on 12-month 2023 dataset (1.58M 1m rows, 423k events, 3.38M outcomes, 1.69M stop evaluations). NO ROBUST ALPHA FOUND. Entry != Stop timeframe proven: 1H swing stops cut premature stop-outs by 68% (down to 4.5%). Minimum viable breathing room discovered: >= 0.50%-0.75%. 6/6 tests passing on Local & VPS. |

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

### Phase 5: TimesFM 3.0 Forecasting Subsystem Integration & Hardening Gate (COMPLETED — REAL_RUNTIME_VERIFIED)
- **Objective:** Integrate Google Research's TimesFM 3.0 as a pluggable, strictly causal forecasting engine operating in SHADOW mode, and harden operational state, resource isolation, zero-lookahead, and API/UI parity.
- **Tasks:**
  1. Pin exact checkpoint and dependency: `google/timesfm-3.0-pytorch` (330M parameters), `timesfm-3.0.2`, `torch-2.14.1+cpu`.
  2. Implement `control_plane/forecast_service.py` with `TimesFMProvider` and `StatisticalBaselineProvider`.
  3. Implement timestamp-aware feature builder supporting past-only context and dynamic covariates without future data leakage (`test_timesfm_no_lookahead_integration.py`).
  4. Generate measurable outputs: future price path, expected return, volatility, and quantiles ($q_{10}-q_{90}$).
  5. Store forecasts in SQLite `model_forecasts` table and benchmark out-of-sample performance (MAE, RMSE, directional accuracy) against naive persistence, EMA, and VWAP baselines.
  6. **Hardening Gate (22 Verification Criteria):**
     - Authoritative diagnostics state cross-process sync (`model_subsystem_state`).
     - Real health check on 64-step sequence verifying shape and quantile monotonicity ($q_{10} \le q_{50} \le q_{90}$).
     - 5-stage resource isolation stress benchmark on real VPS (`timesfm_stress_benchmark.json`).
     - Memory-headroom check and "SWAP ENABLED FOR MEMORY-PRESSURE MITIGATION" policy.
     - Scope pinned to `PHASE_5_INITIAL_SCHEDULER = "5m"`.
     - Evaluation sample tiers (`INSUFFICIENT_SAMPLE` for $N=2$).
     - Non-destructive migration discipline (zero `DROP TABLE`).
     - 5-part cache key & User-scoped vs public forecast isolation.
     - Admin diagnostics role auth (`ADMIN` only) and User forecast/eval auth.
     - Admin UI (System Health vs Forecast Quality bifurcation) & User UI (`CALIBRATING` status badge, uncalibrated confidence disabled).
- **Done Criteria:** Benchmark script runs TimesFM 3.0 inference on real historical data, produces valid quantiles $q_{10} \le q_{50} \le q_{90}$, confirms zero lookahead, and passes all 22 hardening gate criteria. (VERIFIED ON VPS: p50=1342ms, peak RAM=1530MB, all 23 Phase 5 tests PASSED, 29 Phase 1-4 tests PASSED, total 52 PASSED in 24.90s). Status: `PHASE_5 = REAL_RUNTIME_VERIFIED`, `PREDICTIVE_QUALITY = NOT_YET_VALIDATED`.

### Phase 5.6: Unified Manual Order Terminal + Venue Instrument Resolution
- **Objective:** Fix the manual order execution defect and implement a canonical multi-asset instrument resolution architecture across Crypto, US Equities, and Commodities without hardcoded symbol hacks.
- **Tasks:**
  1. Perform Phase 5.5 corrections: rename numerical tolerance (`0.0039`), update contention claim to `MATERIALLY_REDUCED`, restore `DEFAULT_MAX_OPEN_TRADES = 4`, and audit Ollama (`RETAINED_AND_ISOLATED`).
  2. Implement `CanonicalInstrument` model with 17 authoritative fields in `models/instrument.py` and `control_plane/instruments.py`.
  3. Implement `InstrumentResolver` querying live BingX quote contracts dynamically, caching with 10-minute TTL, invalidating safely, and resolving user symbols across asset classes without mixing paths.
  4. Fix Netflix resolution defect (`NFLX` -> `NCSKNETFLIX2USD-USDT`) via generic alias and contract metadata discovery.
  5. Refactor `/api/orders/manual` with strict pre-submit validation pipeline, full order lifecycle states (`ACKNOWLEDGED`, `FILLED`, etc.), and persistence in `manual_orders`.
  6. Update Android `ManualOrderTerminalContent` to display resolved venue attributes and require `RESOLVED && TRADABLE && VALIDATED` before enabling submission.
  7. Deploy and verify across Local, VPS, and App with multi-user isolation and regression testing.
- **Done Criteria:** Dynamic discovery correctly resolves Netflix, Apple, Nvidia, Bitcoin, Gold, and Silver to authoritative BingX venue symbols; manual order pipeline persists full lifecycle states with user-scoped credentials; all regressions pass. (VERIFIED ON VPS & LOCAL: Real runtime probe confirmed live search and order submission for NFLX -> NCSKNETFLIX2USD-USDT, all 19 Phase 5.6 and master tests PASSED, Android APKs compiled cleanly. Status: `PHASE_5_6 = REAL_RUNTIME_VERIFIED`).

### Phase 6: Microstructure Research Suite
- **Objective:** Implement empirical microstructure research modules as a structured market intelligence layer without turning unvalidated formulas into uncontrolled trading triggers.
- **Phase 6A: Module 1 (Trade-Flow Innovation) + Module 2 (Trade Duration / Arrival Pressure)** — **COMPLETE (`REAL_RUNTIME_VERIFIED`)**
  - Signed trade flow, direct vs inferred aggressor, rolling expected flow, flow innovation, winsorized z-score, flow persistence.
  - Dufour-Engle style trade duration $\Delta t_i$, median rolling baseline, arrival intensity $1/\max(\text{med}, 1)$, duration pressure, duration z-score, persistence. Non-directional.
  - Full local and VPS test suite (21 tests) passing. 100% TimesFM regression (26 tests) passing.
  - Live VPS runtime BingX trade ingestion probe verified. Real SQLite persistence under `microstructure_*` tables.
  - Authenticated FastAPI endpoints operational. Android Admin & User APKs updated with research observation UI.
- **Phase 6B: Module 3 (Order-Book Imbalance) + Module 4 (Spread / Liquidity Stress)** — **COMPLETE (`REAL_RUNTIME_VERIFIED`)**
  - Visible order-book imbalance at multiple depth horizons (Top/L1, L5, L10, Depth N) with zero-denominator safety (`NOT_AVAILABLE`).
  - Spread & Liquidity stress: absolute & relative spread, mid-price, rolling expected spread, winsorized z-score, percentile, spread stress, depth stress, book thinning, and recovery state machine (`NORMAL`, `THINNING`, `STRESSED`, `RECOVERING`).
  - Crossed books ($P_b \ge P_a$) flagged `DEGRADED`. Hidden liquidity and cancellation flow hardcoded `NOT_AVAILABLE`.
  - Full local and VPS test suite (25 tests) passing. 100% Phase 6A (21 tests) and TimesFM (26 tests) regression passing.
  - Live VPS runtime BingX depth ingestion probe verified for `BTC-USDT` (41.11 ms latency). SQLite persistence in `microstructure_order_book` and `microstructure_liquidity_stress`.
  - Authenticated FastAPI endpoints operational (`/api/microstructure/order-book`, `/api/microstructure/liquidity-stress`, `/api/microstructure/summary`). Android Admin & User APKs updated with research observation UI.
- **Phase 6B.1: Statistical Baseline Correction** — **COMPLETE (`REAL_RUNTIME_VERIFIED`)**
  - OBI persistence strictly returns `None` (not 0.0) when $N < 5$.
  - Spread & Liquidity Stress raw observables (`spread`, `mid_price`, `relative_spread`) calculate immediately on $N=1$. Baseline metrics (`expected_spread`, `spread_zscore`, `spread_percentile`, `spread_stress`, `depth_stress`, `book_thinning`, `liquidity_stress`, `liquidity_recovery_state`) return `None` and `"NOT_AVAILABLE"` with `quality_state = INSUFFICIENT_SAMPLE` until $N \ge 5$.
- **Phase 6C: Module 5 (Empirical Price Impact) + Module 6 (Toxicity & Adverse Flow)** — **COMPLETE (`REAL_RUNTIME_VERIFIED`)**
  - Module 5 (Empirical Price Impact): `KYLE_INSPIRED_EMPIRICAL_IMPACT`. Strict forward causality pairing flow at $t$ with forward return over $(t, t+h]$. Zero contemporaneous or future leakage. Kyle slope $\lambda$, $R^2$ stability, buy impact, sell impact, and asymmetry ($\lambda_{\text{buy}} - \lambda_{\text{sell}}$). Min sample threshold (20 pairs total, 5 per side for asymmetry).
  - Module 6 (Toxicity & Adverse Flow): `VPIN_INSPIRED_RESEARCH`. Interpretable submetrics exposed first (`flow_intensity`, `adverse_price_response`, `spread_stress_context`, `depth_stress_context`, `trade_arrival_stress`). VPIN volume imbalance fraction bounded $[0, 1]$. Zero trader psychology/intent speculation.
  - Full local and VPS test suite (25 tests) passing. Total 70 microstructure tests passing on VPS.
  - Live VPS runtime BingX trade ingestion probe verified for `BTC-USDT` (370.84 ms latency). SQLite persistence in `microstructure_price_impact` and `microstructure_toxicity`.
  - Authenticated FastAPI endpoints operational (`/api/microstructure/price-impact`, `/api/microstructure/toxicity`, `/api/microstructure/summary`). Android Admin & User APKs compiled, hosted on VPS (`https://15.235.193.47/static/ophelia-admin-latest.apk`, `https://15.235.193.47/static/ophelia-user-latest.apk`), and verified with updated telemetry cards.
- **Phase 6D: Module 7 (Hasbrouck Bivariate VAR) + Module 8 (Bivariate VECM)** — **COMPLETE (`REAL_RUNTIME_VERIFIED`)**
  - Module 7: Bivariate VAR on $[r_t, x_t]'$ with deterministic BIC lag selection ($p \in [1, 5]$), companion matrix stability check ($|\lambda| < 1.0$), Ljung-Box autocorrelation diagnostic, Cholesky orthogonalization ordering $[x_t, r_t]'$, permanent price impact $q_\infty$, and trade flow variance share $V_x / V$.
  - Module 8: Cointegrating equilibrium between BingX Spot (`BTC-USDT-SPOT`) and BingX Perpetual (`BTC-USDT-PERP`). Deterministic timestamp alignment via `NEAREST_PRIOR` ($\Delta t \le 5000\text{ms}$), ADF integration order tests ($I(1)$ levels, $I(0)$ differences), Johansen Case 3 cointegration trace test (critical value 15.49 for $r=0$), normalized cointegrating vector $\beta = [1, -\beta_2]'$, error correction speeds $\alpha = [\alpha_1, \alpha_2]'$, and Gonzalo-Granger price discovery shares $(\text{GG}_{\text{spot}}, \text{GG}_{\text{perp}})$.
  - Full local and VPS test suite (25 tests) passing. Total 95 microstructure tests passing on VPS in 1.61s.
  - Live VPS runtime BingX trade ingestion probe verified for `BTC-USDT` Spot and Perp. Status: `VALID`, cointegration rank 1.
  - Authenticated FastAPI endpoints operational (`/api/microstructure/hasbrouck`, `/api/microstructure/vecm`, `/api/microstructure/summary` returning all 8 modules). Android Admin & User APKs updated.
- **Phase 6D.1: Econometric Hardening & Governance Correction** — **COMPLETE (`REAL_RUNTIME_VERIFIED`)**
  - VECM sample size threshold mathematically governed ($N \ge 300$, fails closed with `INSUFFICIENT_SAMPLE`).
  - Gonzalo-Granger component shares raw preservation (`gg_share_1_raw`, `gg_share_2_raw`) and out-of-range flag (`gg_share_in_range`) without clipping; separate bounded speed shares ($[0, 1]$).
  - 20-step cumulative IRF accurately labeled `cumulative_impact_H20`; permanent impact populated only upon asymptotic convergence ($H \le 50$, tolerance $10^{-6}$).
  - Size-aware signed-sqrt volume robustness specification for Hasbrouck VAR.
  - Methodology versioning incremented to `HASBROUCK_STYLE_V1.1` and `VECM_STYLE_V1.1`. Verified 30/30 tests passing on Local and VPS.
- **Phase 6E: Integrated Microstructure Empirical Evaluation Framework** — **COMPLETE (`REAL_RUNTIME_VERIFIED`)**
  - Research experiment registry with immutable metadata tracking in SQLite (`microstructure_experiments`, `microstructure_experiment_metrics`, `microstructure_ablation_results`, `microstructure_regime_results`, `microstructure_cross_asset_results`).
  - Chronological TRAIN/VAL/TEST splits with purge + embargo windows to prevent label overlap leakage.
  - Multi-group feature ablations across all 8 modules + coherent super groups against Naive Persistence, EMA, and Momentum baselines.
  - Diebold-Mariano tests with Newey-West/HAC Bartlett kernel standard errors out to lag $h-1$ and Benjamini-Hochberg FDR control ($\alpha=0.05$).
  - Market regime segmentation (volatility terciles) and cross-asset robustness (BTC, ETH, SOL).
  - Empirical study executed on real BingX market data (17 experiments, 404 metrics, 67 ablations, 32 regimes, 67 cross-asset records). Verified 25/25 tests passing on Local and VPS.
- **Phase 6F: TimesFM Feature-Consumption Experiments** — **COMPLETE (`REAL_RUNTIME_VERIFIED`)**
  - Production causal adapter leveraging native `past_only_covariates` interface on `timesfm.TimesFM3Forecaster` with train-only standard scaling.
  - Walk-forward controlled experiments comparing Condition A (Close-only) vs B (+Flow/Duration) vs C (+OBI/Liquidity) vs D (+Impact/Toxicity) vs E (+Hasbrouck/VECM) vs F (+All Microstructure).
  - Incremental predictive value measured with Diebold-Mariano tests and FDR-adjusted q-values across quantiles.
  - Empirical verdict: Microstructure covariates do NOT provide statistically significant forecast improvement after Benjamini-Hochberg FDR control ($q > 0.05$); covariate conditioning adds 30-210ms latency overhead.
  - Mutual failure isolation verified; quantile monotonicity ($q_{10} \le q_{50} \le q_{90}$) strictly enforced. Verified 12/12 tests passing on Local and VPS.
- **Phase 6G-6J: Research Review Matrix, Full Safety Regression & Stability Gate** — **COMPLETE (`REAL_RUNTIME_VERIFIED`)**
  - Comprehensive 8-module & TimesFM research matrix documented in `docs/PHASE_6D1_6E_6F_RESEARCH_REPORT.md` (synced to Local and VPS).
  - Full system regression verified: Total 137/137 microstructure and TimesFM tests passing on VPS in 198.85s; zero failures.
  - Sustained VPS stability benchmarked: API healthy (`ONLINE`, `SHADOW`), memory 73.6% utilized (2.04GB available), load 5.25-5.37, zero swap thrashing, SQLite WAL operating cleanly.
  - Invariant strictly maintained: Zero live trading authority (`TRADING_AUTHORITY = FALSE`), zero orders placed, zero slot mutations, TimesFM retained in `SHADOW_ONLY`, microstructure in `RESEARCH_ONLY`.
- **Done Criteria:** All microstructure modules evaluated in empirical harness; TimesFM covariate experiments completed and compared against close-only baseline; full regression and VPS stability verified. (Current Status: `PHASE_6D = REAL_RUNTIME_VERIFIED`, `PHASES_6D1_6E_6F_6G_6J = REAL_RUNTIME_VERIFIED`).

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

### Phase 10: Multi-Venue Market Intelligence & TimesFM Trade Compatibility (Binance Primary + BingX Execution) [COMPLETED]
- **Status:** COMPLETED (All sub-phases 10A-10F verified on Local and VPS)
- **Objective:** Build and rigorously validate multi-venue architecture separating Primary Market Intelligence (Binance USD-M Futures) from Execution/Account Authority (BingX Perpetual Swap), redesign TimesFM 3.0 to provide candidate-specific distribution and path forecasts at `ENTRY_READY`, implement cross-venue basis translation, and execute empirical candidate-level utility validation.
- **Invariants:** `TRADING_AUTHORITY = FALSE`, `EXECUTION_MODE = SHADOW`, `LIVE_ORDER_PLACEMENT = FORBIDDEN`, `AUTONOMOUS_SLOT_RESERVATION = FORBIDDEN`.
- **Sub-Phases:**
  - **Phase 10A [COMPLETE]:** System Audit & Canonical Multi-Venue Instrument Foundation (`models/instrument.py`, `control_plane/instruments.py`).
  - **Phase 10B [COMPLETE]:** Binance Primary Market-Data Foundation & Causal 1m Aggregator (`control_plane/binance_data.py`, `control_plane/db.py`).
  - **Phase 10C [COMPLETE]:** Binance/BingX Cross-Venue Basis Engine & Translation Subsystem (`control_plane/cross_venue_basis.py`).
  - **Phase 10D [COMPLETE]:** TimesFM Candidate-Specific Forecast Redesign & Forecast Trade Compatibility Engine (`control_plane/timesfm_candidate.py`, `control_plane/trade_compatibility.py`).
  - **Phase 10E [COMPLETE]:** Candidate-Level Empirical Utility Study & Binance vs BingX Comparative Research (Ablation A-F, candidate outcome study, walk-forward, statistical FDR review).
  - **Phase 10F [COMPLETE]:** Review Gates (1–5), Full Safety Regression, Sustained Stability & Comprehensive Final Report (`docs/PHASE_BINANCE_TIMESFM_COMPATIBILITY_REPORT.md`).
- **Done Criteria:** All components implemented and passing unit/integration tests on Local and VPS; zero lookahead mathematically proven; candidate-level empirical study completed and documented; full 115+ test regression verified; sustained VPS stability benchmarked; complete report delivered.

### Phase 10.1: Retest-State TimesFM Validation + 5M Forecast Architecture (Correction of Phase 10 Empirical Methodology) [COMPLETE]
- **Status:** COMPLETED (All 16/16 Phase 10.1 tests + 28/28 regression tests passing on Local and VPS)
- **Objective:** Correct Phase 10 empirical methodology flaws: replace breakout expansion candidates with genuine retest confirmation candidates (`ENTRY_READY`), replace crude binary threshold with multi-metric compatibility engine, deploy primary 5m / 12-step path forecast architecture (`TIMESFM_PRIMARY_TIMEFRAME = "5m"`), enforce closed-bar causality, persist raw and postprocessed quantiles with crossing detection, calculate direction-neutral normalized R, and conduct rigorous candidate outcome research.
- **Invariants:** `TRADING_AUTHORITY = FALSE`, `EXECUTION_MODE = SHADOW`, `LIVE_ORDER_PLACEMENT = FORBIDDEN`, `AUTONOMOUS_SLOT_RESERVATION = FORBIDDEN`.
- **Key Findings:**
  - Base Strategy Alone: 105 trades, 17.14% WR, **+11.25 Net R**, PF 1.27.
  - TimesFM Compatible Cohort: 13 trades, 7.69% WR, **-3.18 Net R**, PF 0.65.
  - TimesFM Incompatible Cohort: 13 trades, 7.69% WR, **+3.41 Net R**, PF 3.16.
  - TimesFM Neutral Cohort: 79 trades, 20.25% WR, **+11.02 Net R**, PF 1.35.
  - Conclusion: TimesFM predictive utility is **NOT ESTABLISHED / INCONCLUSIVE**. TimesFM cannot be used as an execution filter. Remains strictly advisory in SHADOW mode.
- **Done Criteria:** Causal retest generator operational; primary 5m architecture and 12-step paths saved to DB; multi-metric trade compatibility active; 16/16 Phase 10.1 tests and 28 regression tests passing; live VPS running synchronized services; report authored at `docs/PHASE_10_1_RETEST_TIMESFM_VALIDATION_REPORT.md`.

### Phase 10.2: TimesFM Forensic Validation + Forecast-Role Discovery [COMPLETE]
- **Status:** COMPLETED (All 16/16 Phase 10.2 tests passed on Local and VPS)
- **Objective:** Forensically verify TimesFM 3.0 implementation, reconcile Phase 10.1 latency (3.70ms vs ~1.3s benchmark), prove whether forecasts arise from neural model vs baseline, reconcile SQLite database counts (105 vs 106 records), and discover non-binary forecast roles (pullback depth, target reachability, holding horizon, post-entry reforecasting).
- **Invariants:** `TRADING_AUTHORITY = FALSE`, `EXECUTION_MODE = SHADOW`, `LIVE_ORDER_PLACEMENT = FORBIDDEN`, `AUTONOMOUS_SLOT_RESERVATION = FORBIDDEN`.
- **Key Findings:**
  - Implementation Verified: `TimesFM3Forecaster` (`google/timesfm-3.0-pytorch`) audited on CPU. Context=128x5m, Horizon=12x5m, Output=(1,12,3).
  - Latency Reconciled: Real warm CPU inference is **median 433.23 ms** (P95: 528.21 ms); cold load is 20.75 s; cache retrieval is 0.016 ms; compatibility math is 0.148 ms. The Phase 10.1 "3.70 ms" was pure-NumPy AR fallback loop + SQLite insert.
  - Model vs Baseline Attribution: Fallback drifts downward (-0.0349%) during retest pullbacks, while Google TimesFM 3.0 correctly projects continuation (+0.1333%). The Phase 10.1 "linear extrapolation penalizing retests" was an artifact of the fallback.
  - Database Counts Reconciled: Exactly 105 genuine historical candidates + 1 unit test artifact (`TEST-CAND-DB-001`, `TEST-BTCUSDT`) = 106 rows.
  - Non-Binary Role Discovery (Target Reachability Edge): Upper quantile reachability ($q_{90} \ge \text{TP1}$) provides strong asymmetric risk filtering:
    - Reachable ($q_{90} \ge \text{TP1}$): **25.00% Win Rate** (17/68 wins, +16.82 Net R).
    - Unreachable ($q_{90} < \text{TP1}$): **2.70% Win Rate** (1/37 wins, -5.57 Net R).
    - Rejecting unreachable trades discards candidates that fail **97.30% of the time**.
  - Pullback Depth: $q_{10}$ captures maximum adverse excursion in 83.3% of winning trades.
  - Post-Entry Reforecasting: Forecast delta at $T+15\text{m}$ correlates with trade outcome ($r = 0.44$).
- **Done Criteria:** 16/16 Phase 10.2 forensic tests passing; SQLite schema migrations and timings deployed; all 5 review gates passed; comprehensive report delivered at `docs/PHASE_10_2_TIMESFM_FORECAST_ROLE_DISCOVERY_REPORT.md`.

### Phase 10.3: Out-of-Sample TimesFM Role Validation [COMPLETE]
- **Status:** COMPLETED (All 10/10 Phase 10.3 tests passed on Local and VPS)
- **Objective:** Rigorously validate exploratory TimesFM forecasting roles (Target Reachability, Post-Entry Management, Pullback Depth, Holding Horizon, Time-to-Move, Entry Direction) across continuous multi-month historical data (61 days, 1,229 candidates) under strict chronological partitions and realistic 0.09% execution friction.
- **Invariants:** `TRADING_AUTHORITY = FALSE`, `EXECUTION_MODE = SHADOW`, `LIVE_ORDER_PLACEMENT = FORBIDDEN`, `AUTONOMOUS_SLOT_RESERVATION = FORBIDDEN`.
- **Key Findings:**
  - Multi-Month Expansion: 61 days (2023-10-01 to 2023-11-30) across BTCUSDT, ETHUSDT, SOLUSDT; 1,229 candidates; 61 day clusters; $N_{\text{eff}} = 751$ (Test $N_{\text{eff}} = 324$).
  - Base Strategy Reality: Under 0.05% fee + 0.04% slippage, raw unhedged base strategy suffers continuous negative drift (-180.42R on TEST). The Phase 10.1 +11.25R was sample-specific to 4 days.
  - Hypothesis A (Target Reachability $q_{90} \ge \text{TP1}$): **OUT-OF-SAMPLE SUPPORTED**. Doubles win rate (30.88% vs 13.37%, $p=0.0002$); survives Benjamini-Hochberg FDR ($\alpha=0.05$). Functions as an effective target feasibility filter.
  - Hypothesis B (Post-Entry Management at $T+15\text{m}$): **PROMISING (RESEARCH HYPOTHESIS)**. Preserves +8.50R by early exit / breakeven tightening ahead of full stop-outs ($p=0.0420$).
  - Hypothesis C (Pullback Depth $q_{10}$): **PROMISING (RESEARCH HYPOTHESIS)**. Lower quantile $q_{10}$ covers actual MAE in 88.17% of all candidates on TEST set.
  - Hypothesis D (Holding Horizon) & E (Time-to-Move): **INCONCLUSIVE / OUT-OF-SAMPLE NOT SUPPORTED** ($p=0.3120, p=0.4850$).
  - Hypothesis F (Entry Direction Gating $q_{50} \ge Entry$): **REJECTED (INVERTS ALPHA)** ($p=0.7200$; rejects 82.8% of valid retests).
  - Baselines Comparison: 60m point forecast RMSE (Persistence 95.37, Session VWAP 97.65, TimesFM 102.07, EMA 110.84). TimesFM value lies in asymmetric quantiles, not point estimates.
- **Done Criteria:** 10/10 Phase 10.3 tests passing on Local and VPS; all 6 pre-registered hypotheses audited under Benjamini-Hochberg FDR; full report delivered at `docs/PHASE_10_3_TIMESFM_OUT_OF_SAMPLE_VALIDATION_REPORT.md`.

### Phase 11: Deterministic Strategy Repair & Regime / Geometry Discovery [COMPLETE]
- **Status:** COMPLETED (All 7/7 Phase 11 unit tests passed; full 18-section report delivered)
- **Objective:** Causally diagnose and repair the deterministic ENTRY_READY retest strategy before TimesFM integration. Isolate TimesFM from trade selection to identify failure taxonomy, evaluate canonical R:R geometry, quantify structure quality, audit candidate clustering, and benchmark controlled variants (A–F) with Benjamini-Hochberg FDR correction.
- **Invariants:** `TRADING_AUTHORITY = FALSE`, `EXECUTION_MODE = SHADOW`, `LIVE_ORDERS = FORBIDDEN`, `AUTONOMOUS_SLOT_RESERVATION = FORBIDDEN`.
- **Key Findings:**
  - Failure Taxonomy: 80.43% of trade losses on TEST split stem from `RANGE_CHOP` (low-volatility oscillation without momentum follow-through).
  - Geometry Analysis: Evaluated canonical R:R buckets (<1.25, 1.25-1.5, 1.5-2.0, 2.0-2.5, 2.5-3.0, >3.0). Setups with $R:R \in [1.25, 1.50]$ are **strongly gross profitable (+23.68 Gross R, Profit Factor 1.56, Win Rate 22.45%)**. High R:R setups ($>2.0$) are empirically toxic (Mean R -1.22R, Win Rate 11.8%).
  - Structure Quality (Variant D): Filtering for Displacement $\ge 1.2$ ATR, Rejection Body Ratio $\ge 0.45$, and RVOL $\ge 1.0$ removes 75.1% of noise candidates (from 465 down to 116), flips Gross PnL from $-0.55R$ to $+15.19R$, lifts Profit Factor from 1.00 to 1.32, and improves Win Rate from 18.49% to 22.41%.
  - Local Regime Gating Paradox: 5m moving-average and ADX indicators misclassify 99% of valid retests as `RANGE_CHOP` due to the mechanical pullback of the retest bar. Local regime gating (Variant B) is EXPLICITLY REJECTED; regime context must reside on HTF (1h/4h).
  - Candidate Clustering: Multi-signal candidate bursts within 60 minutes suffer a 52% drop in win rate (18.96% down to 9.09%). A strict single-signal per impulse rule is required.
  - Friction Sensitivity: Strategy is virtually breakeven at zero friction (-0.55R, Mean R -0.001R). The entire -180.42R loss under base friction (9 bps) is execution friction from high trade frequency.
  - Phase 12 Strategy Spec: Selected Variant D (Structure Quality) as the foundational deterministic research candidate to receive TimesFM distributional target reachability gating.
- **Done Criteria:** 7/7 Phase 11 unit tests passing; all 44 Phase 10 regression tests passing; full 18-section report delivered at `docs/PHASE_11_DETERMINISTIC_STRATEGY_REPAIR_REPORT.md`.

### Phase 11.5: HTF Regime & Trade Management Research for Variant D [COMPLETE]
- **Status:** COMPLETED (All 7/7 Phase 11.5 unit tests passed on Local & VPS; full report delivered)
- **Objective:** Evaluate Higher-Timeframe (1H & 4H) regime alignment and 9 discrete trade management policies strictly on Variant D (Displacement $\ge 1.2$ ATR, Rejection body $\ge 0.45$, RVOL $\ge 1.0$) across continuous 61-day Binance data.
- **Invariants:** `TRADING_AUTHORITY = FALSE`, `EXECUTION_MODE = SHADOW`, `LIVE_ORDERS = FORBIDDEN`, `AUTONOMOUS_SLOT_RESERVATION = FORBIDDEN`.
- **Key Findings:**
  - 4H Trend Alignment: Highly informative. Aligning with 4H trend doubles win rate ($29.03\%$ vs $14.81\%$), producing $+16.59$ Gross R with a 1.75 Profit Factor (vs $-1.40$ Gross R opposing).
  - Breakeven Stop Trap: Early breakeven ratchets (BE at +0.5R, +0.8R, +1.0R) empirically proven toxic, suffocating normal 5m oscillation and collapsing win rates from $43.1\%$ to $9.5\%-17.2\%$ and Gross PnL from $+16.25R$ to $-18.82R$.
  - Top Trade Management Policy: `FIXED_SL_TP` remains the optimal policy (+16.25 Gross R, PF 1.32).
  - Net Expectancy Truth: Gross edge is confirmed (+15.19R Test, PF 1.32, and +16.59R 4H aligned, PF 1.75), but Net PnL remains negative ($-42.34R$ base, $-14.86R$ 4H aligned) under 9.0 bps friction. Deterministic rules alone do not achieve positive net expectancy without secondary predictive probability gating (TimesFM).
  - Parity: 100% tests passing on Local and VPS (`15.235.193.47`). Zero test failures.
### Phase 13: Alpha Discovery Reset & Structural Stop-Room Research [COMPLETE]
- **Status:** COMPLETED (All 6/6 Phase 13 unit tests passed on Local & VPS; 5 authoritative reports delivered; all machine-readable artifacts generated)
- **Objective:** Reset research program from micro-tuning 5m retest filters to broad, unbiased market microstructure discovery and empirical structural stop-room research. Determine if Binance microstructure contains repeatable forward relationships across multiple horizons (1m to 120m), establish empirical MAE/MFE distribution of genuine opportunities, conduct the "Stop Hit -> Thesis Resumption" study, evaluate multi-timeframe structural invalidation (5m vs 15m vs 1H), and audit economic survivability under verified BingX notional execution costs.
- **Invariants:** `TRADING_AUTHORITY = FALSE`, `EXECUTION_MODE = SHADOW`, `LIVE_ORDERS = FORBIDDEN`, `AUTONOMOUS_SLOT_RESERVATION = FORBIDDEN`.
- **Key Findings:**
  - Evaluated Window: 12 continuous months of 2023 across BTCUSDT, ETHUSDT, SOLUSDT (1,576,800 1m bars, 423,130 events, 3,385,040 forward outcomes, 1,692,520 stop evaluations).
  - Alpha Status: `NO ROBUST ALPHA FOUND`. None of the 10 broad microstructure event classes demonstrated positive directional edge surviving chronological OOS and Benjamini-Hochberg FDR ($\alpha = 0.05$). Directional returns across 60m horizons ranged from $-0.022\%$ to $+0.012\%$.
  - Entry Timeframe != Stop Timeframe: 5m swing stops (median 0.305%) suffer 14.20% premature stop-outs (Class B: stopped out by noise before price resumes to target). 1H swing stops (median 0.671%) slash premature stop-outs by 68% (down to 4.50%) and improve net expectancy by +0.553 R.
  - Winner MAE Distribution: 75% of eventual winners experience $\le 0.367\%$ MAE, and 90% experience $\le 0.745\%$ MAE. Eventual losers experience median MAE of 0.810% and mean MAE of 1.204%.
  - Friction Scaling Law in Practice: Friction consumes 0.662 R on 5m swing stops vs 0.241 R on 1H swing stops. Stops $<0.30\%$ impose an insurmountable mathematical tax of 0.37R to 0.50R per trade.
  - Minimum Viable Breathing Room: Empirically established as $\ge 0.50\% - 0.75\%$ (or $\ge 1.5 \times \text{ATR}_{15m}$). Stops tighter than 0.35% are mathematically unviable.
  - Reports Delivered:
    - `docs/PHASE_13_ALPHA_DISCOVERY_REPORT.md` (Answers all 19 mandated questions in Section 30)
    - `docs/PHASE_13_STOP_ROOM_RESEARCH.md` (MAE of winners vs losers, thesis resumption, breathing room)
    - `docs/PHASE_13_EVENT_UNIVERSE_REPORT.md` (Event catalog, base rates, baseline comparisons)
    - `docs/PHASE_13_STATISTICAL_VALIDATION.md` (FDR control, chronological OOS, bootstrap CIs)
    - `docs/PHASE_13_ECONOMIC_VALIDATION.md` (4 friction scenarios, notional fee vs stop-distance economics)
- **Done Criteria:** 6/6 Phase 13 unit tests passing on Local and VPS; full discovery run complete; all 5 comprehensive reports delivered.






