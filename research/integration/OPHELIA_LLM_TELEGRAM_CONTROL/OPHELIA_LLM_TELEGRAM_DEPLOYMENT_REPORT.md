# OPHELIA — LLM TELEGRAM DEPLOYMENT REPORT
Date: 2026-08-22 · Target: 15.235.193.47 (vps-e343ca06, SGP, 4 vCPU / 7.6GB / 72GB)

## Deployment timeline
1. Full VPS audit (services, env-keys, tree, logs, data, timers, pip).
2. Backup: `/opt/ophelia_backup_20260822_1029.tar.gz` (78MB,
   sha256 7ace259714ea05d42fde…). Excludes .venv/external/__pycache__.
3. Ollama installed (0.32.15, CPU-only), service active on 127.0.0.1:11434.
4. Models pulled: qwen3:4b (2.5GB) PRIMARY · qwen3:1.7b FALLBACK.
5. LLM verified: JSON-mode + think=false required (BOM-free payloads mandatory);
   ~8 tok/s CPU; intent latency ≈5–15s typical.
6. control_plane package deployed to /opt/ophelia/control_plane (root-owned files,
   ophelia-readable); data dir /opt/ophelia/control_data.
7. Secrets: `/opt/ophelia/control.env` created by copying keys from existing .env via
   sudo (values never printed/transported in logs): TELEGRAM_BOT_TOKEN,
   TELEGRAM_ALLOWED_USER_IDS, BINGX_API_KEY, BINGX_SECRET_KEY (chmod 600 root).
8. New systemd unit `ophelia-control.service` (hardened: NoNewPrivileges,
   ProtectSystem=full, PrivateTmp, Restart=on-failure).
9. Old `ophelia-telegram-monitor` STOPPED + DISABLED (getUpdates token conflict).
   `ophelia-shadow` LEFT RUNNING untouched (CVD durable state preserved).
10. 24h backfill seeded so indicators work immediately.

## Local vs VPS file comparison (production-relevant)

ADDED on VPS: control_plane/ (11 modules), control.env, ophelia-control.service,
control_data/{market_1m.db, news_context.json, test_report.json}.
MODIFIED: none of the existing VPS files were modified.
DELETED: none.
CONFLICTING/duplicate implementations resolved:
- Telegram: two bots existed conceptually — old shadow_monitor (read-only Phase-7)
  REPLACED by control-plane bot; old monitor disabled to avoid getUpdates conflict.
- EMA/VWAP/Supertrend duplicates across research/*: canonical production math lives in
  control_plane.indicators/analytics (documented formulas); research copies remain
  quarantined under research/ and are NOT importable from production path.
- Risk/sizing: authoritative implementation = core.validate_risk/build_proposal;
  legacy risk/risk_manager.py untouched but unused by the new plane.

## Resource verification (measured)
- RAM: 50% used with Ollama+model loaded alongside old shadow stack; 4.8GB was free
  pre-install; model RSS ≈2.6–3GB → acceptable headroom (~1.8GB free worst-case).
- CPU: idle ~6%; during generation single-digit cores saturation bounded by num_ctx=2048/
  num_predict≤400; no impact observed on ingest cadence (20s loop, journal clean).
- Latency: intent parse ≈5–15s (JSON mode, thinking disabled at ~8 tok/s).
- Disk: backup 78MB + models 3.7GB + code <1MB; 69GB→~65GB free post-install.

## Live execution status
SHADOW ONLY. The control plane has no order-execution capability whatsoever:
no exchange order functions exist in its tool registry, and the Core only records
proposals/fills inside SQLite (`shadow_trades`). LIVE_TRADING remains False in config.py;
BingX keys are present in env for FUTURE use but unused by this deployment.

## Credential hygiene
SSH password used exclusively via process env `OPH_SSH_PW` during this session;
never written to any file/log/report by the deployer. ACTION REQUIRED BY OWNER:
rotate the temporary SSH password now that deployment is complete.
