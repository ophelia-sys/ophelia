---
phase: 5.6
plan: 3
wave: 3
depends_on:
  - "5.6.1"
  - "5.6.2"
files_modified:
  - android-app/app/src/main/java/com/ophelia/app/ui/screens/AutonomousTradingScreen.kt
  - android-app/app/src/main/java/com/ophelia/app/models/ApiModels.kt
  - docs/PHASE_5_6_MANUAL_TERMINAL_REPORT.md
autonomous: true
user_setup: []
must_haves:
  truths:
    - "Android Manual Order Terminal displays: Display Symbol, Asset Class, Venue Product, and Resolved Venue Symbol"
    - "Submit button is enabled ONLY when RESOLVED && TRADABLE && VALIDATED is true"
    - "Both Android APKs (Admin and User) build cleanly without errors"
    - "All changes deployed to VPS host (15.235.193.47) and services verified active"
    - "Full regression suite passes locally and on VPS"
  artifacts:
    - "android-app/app/build/outputs/apk/admin/debug/app-admin-debug.apk exists"
    - "android-app/app/build/outputs/apk/user/debug/app-user-debug.apk exists"
    - "docs/PHASE_5_6_MANUAL_TERMINAL_REPORT.md complete with all 18 required verdicts"
---

# Plan 5.6.3: Android Manual Order Terminal, Multi-Tier Parity & Gate Sign-Off

<objective>
Update the Android Manual Order Terminal UI, build APKs, deploy all changes across the 3 tiers (Local, VPS, App), verify real runtime endpoints, and generate the final Phase 5.6 gate report.
</objective>

<context>
- android-app/app/src/main/java/com/ophelia/app/ui/screens/AutonomousTradingScreen.kt
- android-app/app/src/main/java/com/ophelia/app/models/ApiModels.kt
- docs/PHASE_5_6_MANUAL_TERMINAL_REPORT.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Android Manual Order Terminal UI Enhancement</name>
  <files>
    android-app/app/src/main/java/com/ophelia/app/models/ApiModels.kt
    android-app/app/src/main/java/com/ophelia/app/ui/screens/AutonomousTradingScreen.kt
  </files>
  <action>
    1. In android-app/app/src/main/java/com/ophelia/app/models/ApiModels.kt:
       - Update MarketSearchItem to include venueProduct: String? = null, tradingStatus: String? = null, minQuantity: Double? = null, pricePrecision: Int? = null, quantityPrecision: Int? = null.
       - Update ManualOrderResponse to include venueProduct: String? = null, venueOrderId: String? = null, clientOrderId: String? = null, tradingStatus: String? = null.
    2. In android-app/app/src/main/java/com/ophelia/app/ui/screens/AutonomousTradingScreen.kt:
       - Update ManualOrderTerminalContent:
         - Display Display Symbol, Asset Class, Venue Product, and Resolved Venue Symbol in the asset card.
         - Maintain resolution state: isResolved, isTradable, isValidated.
         - Enable Submit button ONLY when isResolved && isTradable && isValidated (margin > 0, price > 0).
         - Display informative error messages on failure (e.g. VENUE_INSTRUMENT_UNAVAILABLE, TRADING_SUSPENDED).
    3. Build Android APKs using gradlew assembleAdminDebug assembleUserDebug.
  </action>
  <verify>
    cmd.exe /c "cd android-app && gradlew.bat assembleAdminDebug assembleUserDebug"
  </verify>
  <done>
    Android UI updated with canonical venue information and gating, and APKs build cleanly.
  </done>
</task>

<task type="auto">
  <name>Task 2: Multi-Tier VPS Deployment & Full Regression Suite</name>
  <files>
    docs/PHASE_5_6_MANUAL_TERMINAL_REPORT.md
  </files>
  <action>
    1. Deploy updated code to VPS (15.235.193.47):
       - Sync models/instrument.py, control_plane/instruments.py, control_plane/config.py, control_plane/db.py, control_plane/api.py, control_plane/core.py, control_plane/us_market.py, control_plane/symbols.py.
       - Restart systemd services ophelia-api and ophelia-control.
       - Test live endpoints using admin and user authentication.
    2. Run full regression suite:
       - tests/test_phase5_master_suite.py
       - tests/test_timesfm*
       - tests/test_instrument_resolution.py
       - tests/test_manual_order_terminal.py
    3. Produce comprehensive gate report docs/PHASE_5_6_MANUAL_TERMINAL_REPORT.md with all 18 required verdicts.
  </action>
  <verify>
    pytest tests/test_phase5_master_suite.py tests/test_instrument_resolution.py tests/test_manual_order_terminal.py -v
  </verify>
  <done>
    Full multi-tier deployment and regression suites verified on Local and VPS.
  </done>
</task>

</tasks>

<verification>
After tasks, verify:
- [ ] Both APKs built successfully
- [ ] VPS services active and healthy
- [ ] All 18 verdicts in PHASE_5_6_MANUAL_TERMINAL_REPORT.md pass
</verification>

<success_criteria>
- [ ] Phase 5.6 complete across Local, VPS, and App
- [ ] Real runtime verified on VPS
- [ ] Netflix bug permanently fixed through generic resolution architecture
</success_criteria>
