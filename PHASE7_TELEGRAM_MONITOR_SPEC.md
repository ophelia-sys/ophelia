# PHASE 7 TELEGRAM MONITOR SPECIFICATION

## 1. Architecture
The Telegram Monitor is a standalone service (`ophelia-telegram-monitor.service`) running independently from the main trading engine (`ophelia-shadow.service`).
It strictly operates in read-only mode, with no direct access to `TradingEngine`, `Broker`, or any mutable state. It tails the `logs/ophelia.log` file to compute metrics and fire alerts.

## 2. Configuration & Secrets
- **TELEGRAM_BOT_TOKEN:** Injected via environment variables (`/opt/ophelia/.env`).
- **TELEGRAM_ALLOWED_USER_IDS:** Comma-separated list of Telegram user IDs injected via environment.
- The bot explicitly rejects any updates from unauthorized `user_id`s, responding with a generic rejection. No sensitive information is leaked.

## 3. Command Interface
- `/stats`: Computes full shadow status and live statistics from the shadow logs.
- `/status`: Compact health summary containing uptime, total bars, and system component status.
- `/health`: Detailed VPS metric health (CPU, RAM, Disk) and inference status.
- `/logs`: Returns the last 10 valid shadow decisions.
- `/symbol <SYMBOL>`: Returns the targeted probability, threshold, and feature validity for the selected symbol. Rejects invalid symbols.
- `/progress`: Calculates the time elapsed, remaining time, and checks the 24-hour operation acceptance criteria.

## 4. Alerting
The bot uses a background thread (`alert_loop`) that tails the logs to emit real-time push alerts for:
- Service restarts (systemd interventions).
- Market data errors, missing features, and LightGBM exceptions.
- It suppresses normal HOLD / LONG_CANDIDATE spam.
- An optional hourly digest provides a summary of the past hour's operation.

## 5. Failure Isolation
- If `ophelia-telegram-monitor.service` crashes, the trading engine is completely unaffected.
- If the Telegram API goes offline, the monitor silently retries, but no blocking occurs in the trading pipeline.
- If the logs rotate, the monitor attempts to recover gracefully by seeking to the end of the new file.
