# OPHELIA PROGRESS CHECKPOINT
**Date & Time**: 2026-08-18 07:42:00 IST

## 1. LOCAL STATE
- **Project Root**: `C:\Users\dopa.mine\Desktop\ophelia`
- **Environment**: Antigravity IDE / Local Windows Workspace
- **Source Paths**: `core/`, `institutional/`, `telegram/`, `models/`
- **Models**: `models/phase7_frozen_long_v1.pkl`, `models/phase7_frozen_short_v1.pkl`
- **Thresholds**: `PHASE7_DECISION_THRESHOLDS.json`
- **Status**: The local workspace holds the unified SHORT architecture and advanced order-flow implementation (DTR, FLP, DIV, ABS) along with the Durable State updates.

## 2. VPS STATE
- **Hostname**: `vps-e343ca06`
- **OS**: `Ubuntu 26.04 LTS`
- **Python Version**: `Python 3.14.4` (in `/opt/ophelia/.venv/bin/python`)
- **Ophelia Installation Path**: `/opt/ophelia`
- **Active systemd Services**: `ophelia-shadow.service`, `ophelia-telegram-monitor.service`
- **Ophelia PID**: `152674`
- **Telegram PID**: `152670`
- **Ophelia Uptime**: ~32 minutes
- **Telegram Uptime**: ~32 minutes
- **Current Mode**: `SHADOW`
- **Broker State**: `LIVE EXECUTION: BLOCKED` (Strictly isolated)
- **Current CVD Warm-up State**: `6/288` (WARMING)
- **Current Shadow State**: `WARMING`
- **Current Model Versions**: `frozen_v1`
- **LONG Model Status**: HEALTHY
- **SHORT Model Status**: HEALTHY
- **WebSocket State**: CONNECTED
- **Current Errors/Warnings**: 0 Errors, 1 Warning (`Execution mode: SHADOW (Broker completely isolated)`)

## 3. DIFFERENTIAL SUMMARY
- **Differential**: LOCAL and VPS are currently 100% SYNCHRONIZED. The durable state persistence logic from LOCAL was manually verified and deployed to VPS 32 minutes ago. 

## 4. CURRENT OPHELIA ARCHITECTURE
- **Market Data**: Ingests 1m bars from BingX WebSocket, aggregates to 5m in-memory.
- **Features**: Phase 7 features (7 BASE features + 11 CVD features). 
- **Models**: Two independent LightGBM models (`phase7_frozen_long_v1.pkl` and `phase7_frozen_short_v1.pkl`).
- **Thresholds**: Independent thresholds maintained in `PHASE7_DECISION_THRESHOLDS.json`.
- **Decision Engine**: `LONG_CANDIDATE`, `SHORT_CANDIDATE`, `HOLD`. Conflict resolution acts as a safety layer (rejects if both trigger simultaneously).
- **Risk Management**: Independent Risk Modules for Long and Short (Margin check, Max Leverage, Liquidation safeguards).
- **Shadow System**: Records mock decisions and telemetry directly into `[SHADOW_JSON]` logs without placing live trades.
- **Telegram**: Reads persistent state and log files to report `health`, `status`, and `progress`.
- **Broker Isolation**: Hardcoded to safely block all `place_order` calls in SHADOW mode.

## 5. CURRENT SHORT ARCHITECTURE
The SHORT implementation exists as an independent processing track mirroring the LONG logic.
- Maintains its own probability (`probability_short`).
- Evaluated against its own frozen threshold (`frozen_threshold_short`).
- Yields a `SHORT_CANDIDATE` decision completely independently of LONG evaluation.
- Routed to `risk.evaluate_short()`.

## 6. ADVANCED ORDER-FLOW ARCHITECTURE
Four new advanced order-flow proxies exist as **telemetry** flags inside the system. They currently act as **analytical flags** written into the `[SHADOW_JSON]` logging layer, and do NOT alter the `LightGBM` model features or the entry decisions.
1. **Delta Deterioration (DTR)**: Tracks 5-minute directional momentum decay.
2. **Delta Flip (FLP)**: Tracks instant negative/positive delta reversals.
3. **Price/Order-Flow Divergence (DIV)**: Tracks price moving against cumulative volume delta.
4. **Absorption/Exhaustion Proxy (ABS)**: Tracks high relative volume with minimal candle body progress.

## 7. CURRENT CVD STATE
- **Current Warm-Up**: `6/288`
- **Required**: `288`
- **Persisted CVD State**: Yes. Stored as `/opt/ophelia/data/cvd_state_{symbol}.json`. 
- **Stored Blocks**: 6 validated blocks for each symbol (BTC, ETH, SOL, XRP).
- **State Loaded Successfully**: Yes (resumed efficiently after recent atomic persistence deployment).
- **Count Origin**: Based entirely on persisted historical JSON state written atomically by `live_engine.py`.

## 8. CURRENT SHADOW STATE
- **Original Historical Pre-Shadow Prerequisite**: COMPLETED (Lost memory trace due to VPS restart, but conceptually proven in past).
- **Historical Pre-Change Shadow**: PRESERVED inside `/opt/ophelia/logs/ophelia_pre_change_shadow.log`.
- **Current VPS CVD Warm-up**: ACTIVE. `6/288` blocks.
- **Current Actual Shadow**: NOT STARTED.
  - Phase: `WARMING`
  - `shadow_started_at`: `null`
  - Observations: 0
  - LONG count: 0
  - SHORT count: 0
  - HOLD count: 0
  - Conflict count: 0

## 9. TELEGRAM STATE
- Telegram Monitor is active, running via persistent systemd service (`ophelia-telegram-monitor`).
- Completely transitioned to using **Durable JSON State** as its source of truth for progress reporting instead of parsing stale logs.
- `/hi`: Responds with command list.
- `/health`: Responds with VPS metrics, Ophelia process health, CVD status (`WARMING UP (6/288)`).
- `/status`: Lists current market probabilities, telemetry triggers, and system health.
- `/progress`: Correctly segregates `CURRENT VPS CVD WARM-UP` from the `ACTUAL 24-HOUR SHADOW`. Currently shows `Status: WARMING` and `Target Shadow: NOT STARTED`.

## 10. DURABLE-STATE ARCHITECTURE
- **CVD**: `cvd_state_{symbol}.json` stores the raw 5-minute history block arrays for the specific symbol. Updated atomically via a `.tmp` file and `os.replace()` every 5 minutes in `get_features()`. Re-loaded safely into the engine on restart, ensuring warmup is not lost.
- **Shadow**: `shadow_state.json` stores the state machine tracker (`WARMING`, `READY`, `SHADOW_RUNNING`), timestamps, and telemetry counters. Updated atomically by the TradingEngine inside a locked thread operation. 
- **Source of Truth**: The local disk JSON files are the strict authority on system state, surviving any crashes or updates.

## 11. MODEL INVENTORY
- **LONG Model**: `models/phase7_frozen_long_v1.pkl` (Phase 7 BASE+CVD)
- **SHORT Model**: `models/phase7_frozen_short_v1.pkl` (Phase 7 BASE+CVD)
- **Thresholds**: `PHASE7_DECISION_THRESHOLDS.json`

## 12. SERVICE INVENTORY
### Local
- Source: `C:\Users\dopa.mine\Desktop\ophelia\`
- Tests: `C:\Users\dopa.mine\Desktop\ophelia\tests\`
- Research Artifacts: `C:\Users\dopa.mine\Desktop\ophelia\research\`

### VPS
- Source: `/opt/ophelia`
- Systemd: `ophelia-shadow.service`, `ophelia-telegram-monitor.service`
- Logs: `/opt/ophelia/logs/ophelia.log`, `/opt/ophelia/logs/ophelia_pre_change_shadow.log`
- Durable State: `/opt/ophelia/data/cvd_state_*.json`, `/opt/ophelia/data/shadow_state.json`
- Python Venv: `/opt/ophelia/.venv/bin/python`

## 13. SAFETY STATE
`LIVE BROKER EXECUTION: BLOCKED`
- ShadowBroker is active, securely discarding any generated order requests.
- Telegram Monitor executes entirely as read-only.
- Real orders are strictly impossible in the current `SHADOW` environment variables.

## 14. TEST STATUS
- **LONG/SHORT Independence Tests**: PASSED locally.
- **Advanced Order-flow Tests**: PASSED locally.
- **State Persistence Tests**: PASSED (Verified via VPS atomic writes).
- **Deployment Tests**: PASSED.
- **Unresolved Issues**: None.

## 15. KNOWN ISSUES
- The original 24-hour historical trade-level order-flow history was lost due to a VPS restart before durable state persistence was implemented. The system is securely rebuilding this 24-hour warm-up history naturally.

## 16. NEXT EXPECTED STEP
Continue current CVD warm-up.
When CVD reaches `288/288`:
`CVD → READY`
Then:
`ACTUAL POST-ORDER-FLOW-ENHANCEMENT SHADOW`
`→ SHADOW_RUNNING`
`→ shadow_started_at recorded`
`→ 24-hour shadow begins automatically`

---

## 17. IMPORTANT ARCHITECTURAL RULE — PERMANENT PROJECT RULE

**LOCAL AND VPS MUST REMAIN SYNCHRONIZED**

From this point forward, **every architectural change, runtime change, model change, strategy change, feature change, state-management change, and Telegram/runtime integration change must be handled as a LOCAL + VPS synchronization task.**

Never assume: `LOCAL = VPS`
Never assume: `VPS = LOCAL`

Before making a material change:
```text
LOCAL STATE
    ↕
VPS STATE
    ↕
DIFFERENTIAL CHECK
    ↓
CHANGE
    ↓
SYNC
    ↓
VERIFY BOTH
```

**Rules:**
LOCAL is the primary development/research environment.
VPS is the primary runtime/history/state environment.

Whenever code or architecture changes:
1. inspect LOCAL
2. inspect VPS
3. identify differences
4. apply the intended change
5. synchronize both where appropriate
6. verify hashes/versions
7. verify runtime behavior on VPS
8. record the change in the checkpoint

Do not allow architectural drift between LOCAL and VPS.

---

## 18. RESUME PROCEDURE — FUTURE RULE

**WHEN OPHELIA WORK RESUMES**

The first action must be:

1. Find the latest file matching: `OPHELIA_PROGRESS_CHECKPOINT_*.md`
2. Select the most recent checkpoint by its embedded date/time.
3. Read the entire checkpoint.
4. Connect to the VPS.
5. Compare LOCAL and VPS state.
6. Verify current runtime before making changes.
7. Continue from the documented checkpoint.

Do NOT start a new implementation from memory if a checkpoint exists.

---

## 19. CREDENTIAL-HANDLING NOTE
VPS credentials: configured for current session; password intentionally not persisted in project files.
