# PHASE 7 VPS SHADOW DEPLOYMENT

## 1. Overview
This document records the official Shadow deployment on the VPS. 

- **Target Path:** `/opt/ophelia`
- **User:** `ophelia`
- **Daemon:** `ophelia-shadow.service`
- **Monitor Daemon:** `ophelia-telegram-monitor.service`

## 2. Environment Restrictions
The service enforces strict broker isolation via:
1. `Environment="OPHELIA_MODE=SHADOW"` inside the `systemd` service.
2. `ShadowBroker` injected in `core/trading_engine.py` (Raises `ShadowModeIsolationError` on order methods).
3. HTTP-layer POST interception in `exchange/bingx_client.py` (Raises error on trade/order endpoints).

## 3. Artifact Validation
Hashes of deployed models and threshold configurations must be confirmed on the VPS before starting the official window:
- [ ] Model hashes verify
- [ ] Threshold hashes verify

## 4. Operational Configuration
- **Restart Policy:** `Restart=on-failure` (10 second delay)
- **Log Rotation:** Systemd journal handles `stdout` / `stderr` rotation.
- **Health Check:** `scripts/vps_health_monitor.py` verifies the JSONL shadow logs to measure memory/disk footprint and ensure decisions are generated every 5m without inference errors.
- **Telegram Monitoring:** Standalone `ophelia-telegram-monitor.service` running read-only alert loop.

## 5. Official Shadow Observation Schedule
- **Deployment Validated At (UTC):** NOT YET EXECUTED
- **Shadow Window Start (UTC):** NOT OFFICIAL / NOT STARTED
- **Expected Completion (UTC):** Pending (+24 hours)
