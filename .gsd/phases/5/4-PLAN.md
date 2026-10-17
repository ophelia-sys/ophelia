---
phase: 5
plan: 4
wave: 4
---

# Plan 5.4: VPS Background Service, API Endpoints & Android UI Integration

## Objective
Integrate the `ForecastScheduler` into the VPS background control loop, expose secure REST endpoints (`/api/timesfm/diagnostics` and `/api/timesfm/forecasts`), and implement the diagnostic and forecast visualization cards across both Android applications (Admin and User). Compile and verify both APKs on the emulator.

## Context
- `control_plane/api.py`
- `control_plane/__main__.py`
- `control_plane/forecast_service.py`
- `android-app/app/src/main/java/com/ophelia/app/network/OpheliaApiService.kt`
- `android-app/app/src/main/java/com/ophelia/app/models/ApiModels.kt`
- `android-app/app/src/main/java/com/ophelia/app/ui/screens/AutonomousTradingScreen.kt`
- `android-app/app/src/main/java/com/ophelia/app/ui/screens/MlScreen.kt`

## Tasks

<task type="auto">
  <name>Task 5.4.1: Integrate ForecastScheduler into daemon and expose REST endpoints</name>
  <files>control_plane/__main__.py, control_plane/api.py, control_plane/forecast_service.py</files>
  <action>
    - In `control_plane/__main__.py`:
      * Initialize `ForecastScheduler` in the background worker loop.
      * Schedule periodic forecast generation for universal watchlist (BTC-USDT, ETH-USDT, SOL-USDT, XRP-USDT, GOLD).
      * Ensure worker catches all exceptions without stalling the main automation evaluation loop.
    - In `control_plane/api.py`:
      * Implement `@app.get("/api/timesfm/diagnostics")`:
        Returns model status, checkpoint, device, RAM/CPU metrics, last inference latency, queue depth, error count, and uptime. Requires authentication.
      * Implement `@app.get("/api/timesfm/forecasts")`:
        Returns latest cached forecast for symbol and timeframe. Explicitly includes `status="SHADOW"`.
  </action>
  <verify>python -c "from control_plane import api; print('TimesFM API endpoints registered')"</verify>
  <done>Daemon worker executes scheduler, and REST API returns cached forecasts and diagnostic telemetry.</done>
</task>

<task type="auto">
  <name>Task 5.4.2: Update Android API models and UI screens (Admin & User)</name>
  <files>android-app/app/src/main/java/com/ophelia/app/models/ApiModels.kt, android-app/app/src/main/java/com/ophelia/app/network/OpheliaApiService.kt, android-app/app/src/main/java/com/ophelia/app/ui/screens/AutonomousTradingScreen.kt, android-app/app/src/main/java/com/ophelia/app/ui/screens/MlScreen.kt</files>
  <action>
    - In `ApiModels.kt` and `OpheliaApiService.kt`:
      * Add `TimesFmDiagnosticsResponse` and `TimesFmForecastResponse` data classes.
      * Add `getTimesFmDiagnostics()` and `getTimesFmForecasts()` API calls.
    - In `AutonomousTradingScreen.kt` (Admin):
      * Add "TIMESFM 3.0 DIAGNOSTICS" collapsible card showing:
        Status (`READY`, `LOADING`, `SHADOW`), Checkpoint (`google/timesfm-3.0-pytorch`), Device, Latency, Queue Depth, Memory Usage.
    - In `MlScreen.kt` (User):
      * Add "TIMESFM FORECAST (SHADOW)" card showing:
        Forecast direction, expected return %, quantile bounds ($q_{10}-q_{90}$), horizon, generated age, and clear `SHADOW` badge.
  </action>
  <verify>python -c "print('Android models and screens updated for TimesFM')"</verify>
  <done>Admin and User UI displays TimesFM telemetry and scoped forecasts labeled SHADOW.</done>
</task>

<task type="auto">
  <name>Task 5.4.3: Compile Admin and User APKs and verify on Android emulator</name>
  <files>android-app/build_admin.bat, android-app/build_user.bat</files>
  <action>
    - Increment version codes in `android-app/app/build.gradle.kts`.
    - Run Gradle builds for `assembleAdminDebug` and `assembleUserDebug`.
    - Verify both APKs compile with 0 errors.
    - Install and launch both APKs on running emulator `OpheliaPixel` (`emulator-5554`).
  </action>
  <verify>powershell -Command "adb -s emulator-5554 shell pm list packages | Select-String ophelia"</verify>
  <done>Both APKs compiled and installed on OpheliaPixel emulator.</done>
</task>

## Success Criteria
- [ ] Daemon evaluates forecast scheduler without starving automation or position loops.
- [ ] `/api/timesfm/diagnostics` and `/api/timesfm/forecasts` operational.
- [ ] Admin app displays real-time model health and latency.
- [ ] User app displays scoped forecast card with SHADOW badge.
- [ ] Both APKs compile and install cleanly on emulator.
