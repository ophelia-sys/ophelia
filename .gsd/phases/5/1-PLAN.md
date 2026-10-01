---
phase: 5
plan: 1
wave: 1
---

# Plan 5.1: Clean up Phase-4 Presentation Issues & VPS System Hardening

## Objective
Fix the two Phase-4 presentation issues prior to new feature code:
1. Segregate P&L accounting into explicit namespaces (`LIVE`, `PAPER`, `SHADOW`, `AUDIT`, `RESEARCH`) so that controlled lifecycle/shadow gains (+157.42 USDT) do NOT contaminate live dashboard statistics.
2. Clarify slot capacity terminology across Admin & User UIs (`SYSTEM MAX SLOTS`, `USER CONFIGURED SLOTS`, `AVAILABLE SLOTS`, `OCCUPIED SLOTS`, `AUTHORIZED CAPITAL`, `ALLOCATED CAPITAL`).
3. Harden VPS system resources by adding a 4GB swapfile to prevent OOM, install CPU-only PyTorch and TimesFM 3.0 in the VPS virtual environment, and inspect the installed package/API signatures.

## Context
- `control_plane/db.py`
- `control_plane/account.py`
- `control_plane/api.py`
- `android-app/app/src/main/java/com/ophelia/app/ui/screens/HomeDashboardScreen.kt`
- `android-app/app/src/main/java/com/ophelia/app/ui/screens/AutonomousTradingScreen.kt`

## Tasks

<task type="auto">
  <name>Task 5.1.1: Segregate P&L accounting namespaces and filter dashboard statistics</name>
  <files>control_plane/db.py, control_plane/account.py, control_plane/api.py, android-app/app/src/main/java/com/ophelia/app/ui/screens/HomeDashboardScreen.kt</files>
  <action>
    - In `control_plane/db.py`:
      * Update `closed_positions_since(start_ms, user_id=None, mode=None)` to accept `mode` (e.g. `LIVE`, `PAPER`, `SHADOW`, `AUDIT`, `RESEARCH`). When mode is specified, filter `AND mode = ?`.
      * Update `get_recent_completed_trades(limit, user_id=None, mode=None)` to filter by `mode` when provided.
    - In `control_plane/account.py`:
      * Update `dashboard_view(user_id, force=False, is_admin_caller=False, mode="LIVE")` to query closed positions and recent trades filtered by the active mode. Default live accounts to `LIVE`.
      * Include `"mode": mode` and `"namespace": mode` inside `today_stats` and `dashboard_view` payload so the UI explicitly knows the accounting namespace.
    - In `control_plane/api.py`:
      * Update `@app.get("/api/dashboard")` to accept optional `mode: Optional[str] = "LIVE"`.
    - In `android-app/app/src/main/java/com/ophelia/app/ui/screens/HomeDashboardScreen.kt`:
      * In `TodayStatsCard`, display an explicit namespace badge (`LIVE`, `PAPER`, `SHADOW`, `AUDIT`) next to "TODAY STATS".
  </action>
  <verify>python -c "from control_plane import db, account; res = account.dashboard_view(user_id=1, mode='LIVE'); print(res['today_stats'])"</verify>
  <done>Shadow and audit closed trades (+157.42 USDT) do not appear in LIVE today stats; namespace is explicitly labeled.</done>
</task>

<task type="auto">
  <name>Task 5.1.2: Clarify slot capacity terminology in UI</name>
  <files>android-app/app/src/main/java/com/ophelia/app/ui/screens/HomeDashboardScreen.kt, android-app/app/src/main/java/com/ophelia/app/ui/screens/AutonomousTradingScreen.kt</files>
  <action>
    - In `HomeDashboardScreen.kt`:
      * Change label "Open Slots" to "OCCUPIED SLOTS" showing `${openPositions.size} / ${data.risk.positionsMax} MAX` with tooltip/context indicating `SYSTEM MAX SLOTS`.
    - In `AutonomousTradingScreen.kt`:
      * In the Metrics Grid, clarify column labels:
        - `USER CONFIGURED SLOTS`: `${data?.totalSlots ?: 0}`
        - `AVAILABLE SLOTS`: `${data?.availableSlots ?: 0}`
        - `OCCUPIED SLOTS`: `${data?.occupiedSlots ?: 0}`
        - `AUTHORIZED CAPITAL`: `${data?.totalAuthorizedMarginUsdt ?: 0.0} USDT`
        - `ALLOCATED CAPITAL`: `${data?.reservedMarginUsdt ?: 0.0} USDT`
      * Display `SYSTEM MAX SLOTS: ${data?.systemMaxConcurrentPositions ?: 4}` prominently in the card header.
  </action>
  <verify>python -c "print('Slot terminology updated to canonical terms')"</verify>
  <done>Zero contradictory slot terminology; clear distinction between system concurrency limit and user configured templates.</done>
</task>

<task type="auto">
  <name>Task 5.1.3: VPS system hardening and CPU PyTorch / TimesFM installation</name>
  <files>scratch/vps_helper.py</files>
  <action>
    - Allocate 4GB swap on VPS if not present:
      `sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile`
    - Install CPU-only PyTorch and TimesFM in VPS virtual environment:
      `/opt/ophelia/.venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu`
      `/opt/ophelia/.venv/bin/pip install timesfm`
    - Verify installed versions and inspect package module signatures.
  </action>
  <verify>python -c "from scratch.vps_helper import run_vps_command; out, err = run_vps_command('/opt/ophelia/.venv/bin/python3 -c \"import torch, timesfm; print(torch.__version__, timesfm.__version__)\"'); print(out); print(err)"</verify>
  <done>VPS has active 4GB swap; torch and timesfm are successfully installed in VPS .venv and imported without errors.</done>
</task>

## Success Criteria
- [ ] Accounting namespaces segregated: SHADOW/AUDIT gains do not bleed into LIVE stats.
- [ ] Slot capacity terminology unified and explicit in Admin and User UI screens.
- [ ] VPS has 4GB swap space activated to prevent OOM crashes.
- [ ] PyTorch CPU and TimesFM 3.0 successfully installed and verified in VPS environment.
