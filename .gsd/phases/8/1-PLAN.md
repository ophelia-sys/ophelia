---
phase: 8
plan: 1
wave: 1
---

# Plan 8.1: Software Update, Android APK Release & Telegram Distribution

## Objective
Synchronize the Android client applications across both product flavors (`admin` and `user`). Bump versions, compile clean debug APKs with Gradle 8+ and Java 17, compute SHA-256 hashes, deploy them to the VPS static and download paths, update the Telegram bot APK distribution commands, and verify installation on the existing emulator (`OpheliaPixel`).

## Context
- [.gsd/SPEC.md](file:///c:/Users/dopa.mine/Desktop/ophelia/.gsd/SPEC.md)
- [OPHELIA_CURRENT_STATE.md](file:///c:/Users/dopa.mine/Desktop/ophelia/OPHELIA_CURRENT_STATE.md)
- `android-app/app/build.gradle.kts`
- `control_plane/telegram_bot.py`
- `control_plane/api.py`

## Tasks

<task type="auto">
  <name>Task 8.1: Bump version numbers and compile Admin and User APKs</name>
  <files>android-app/app/build.gradle.kts, control_plane/api.py</files>
  <action>
    - In `android-app/app/build.gradle.kts`:
      * Admin flavor: `versionCode = 29`, `versionName = "2.8.1"`.
      * User flavor: `versionCode = 4`, `versionName = "1.2.1"`.
    - In `control_plane/api.py`:
      * Update `/api/system/version` endpoint to return Admin v2.8.1 (code 29) and User v1.2.1 (code 4) with release notes describing autonomous execution recovery, TimesFM 3.0, and microstructure research engine.
    - Compile APKs:
      * Run `gradlew.bat assembleAdminDebug --no-daemon` in `android-app/`.
      * Run `gradlew.bat assembleUserDebug --no-daemon` in `android-app/`.
      * Compute SHA-256 checksums of both output files.
  </action>
  <verify>Test-Path "android-app/app/build/outputs/apk/admin/debug/app-admin-debug.apk" -and Test-Path "android-app/app/build/outputs/apk/user/debug/app-user-debug.apk"</verify>
  <done>Both APKs compile with exit code 0; SHA-256 checksums computed and verified.</done>
</task>

<task type="auto">
  <name>Task 8.2: Deploy APKs to VPS, update Telegram Bot, and verify on emulator</name>
  <files>control_plane/telegram_bot.py</files>
  <action>
    - Upload APKs to VPS:
      * `app-admin-debug.apk` -> `/opt/ophelia/static/ophelia-admin-latest.apk` and `/opt/ophelia/control_data/apk/ophelia-admin.apk`
      * `app-user-debug.apk` -> `/opt/ophelia/static/ophelia-user-latest.apk` and `/opt/ophelia/control_data/apk/ophelia-user.apk`
    - In `control_plane/telegram_bot.py`:
      * Update `_send_admin_apk` and `_send_user_apk` with exact release notes, file paths, and SHA-256 hash checks.
      * Verify direct HTTPS download URLs (`https://15.235.193.47/static/ophelia-admin-latest.apk`, `https://15.235.193.47/static/ophelia-user-latest.apk`).
    - Verify on Android Emulator (`OpheliaPixel`):
      * Check emulator status via `adb.exe devices`.
      * Install both APKs: `adb install -r android-app/app/build/outputs/apk/admin/debug/app-admin-debug.apk` and `adb install -r android-app/app/build/outputs/apk/user/debug/app-user-debug.apk`.
      * Verify packages `com.ophelia.admin` and `com.ophelia.user` are registered on device.
  </action>
  <verify>& "C:\Users\dopa.mine\AppData\Local\Android\Sdk\platform-tools\adb.exe" shell pm list packages | Select-String "com.ophelia"</verify>
  <done>APKs deployed to VPS static downloads; Telegram bot distributes newest release; packages installed on emulator.</done>
</task>

## Success Criteria
- [ ] Admin APK (v2.8.1) and User APK (v1.2.1) compiled cleanly.
- [ ] No stale APKs remaining in VPS distribution paths.
- [ ] Telegram bot distributes updated APKs with matching SHA-256 checksums.
- [ ] Packages installed and launchable on `OpheliaPixel` emulator.
