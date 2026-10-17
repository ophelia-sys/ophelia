# OPHELIA — LOCAL + VPS AUDIT (Final Integration, 2026-08-22)

> **UPDATE 2026-08-25 (live-ready integration pass):** see the addendum at the
> bottom of this file and `OPHELIA_LOCAL_VPS_FILE_DIFF.md` for the second
> deployment performed on 2026-08-25.

## 1. VPS inventory (15.235.193.47 · vps-e343ca06 · Ubuntu 26.04 · 4vCPU/7.6GB/72GB)

| layer | found |
|---|---|
| services (pre-task) | ophelia-shadow.service (running, Phase-7 ML shadow via main.py), ophelia-telegram-monitor.service (running, read-only monitor) |
| python | /opt/ophelia/.venv Python 3.14.4; lightgbm/sklearn/pandas/numpy/psutil present |
| data | cvd_state_{BTC,ETH,SOL,XRP}-USDT.json (live-updating), shadow_state.json, trades.csv |
| logs | logs/ophelia.log 3.2MB (updating), ophelia_pre_change_shadow.log |
| env file | /opt/ophelia/.env (root-readable only) — keys: TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USER_IDS, BINGX_API_KEY, BINGX_SECRET_KEY |
| timers/cron | none ophelia-related (system defaults only) |
| models | PHASE7_MODEL_FROZEN_*.pkl (6 long + 5 short), PHASE7_DECISION_THRESHOLDS.json |

## 2. Local workspace inventory (production-relevant)

| layer | state |
|---|---|
| core/ exchange/ brokers/ risk/ portfolio/ strategies/ paper/ telegram/ | v1.0 architecture; EMA strategy QUARANTINED by design; LIVE_TRADING=False hardcoded |
| control_plane/ | NEW this task — production source of truth for the Telegram/LLM/data plane |
| research/ validation/ canonical measurement | strictly non-production; verified not imported by control_plane (only stdlib+numpy+pandas) |
| known local drift vs VPS | threshold key mismatch ("threshold" vs "long_threshold") in old Phase-7 path documented earlier; UNTOUCHED here (separate system, still in SHADOW) |

## 3. Duplicates / obsolete implementations identified

| concept | implementations found | resolution |
|---|---|---|
| Telegram bot | telegram/bot_adapter.py (in-process, privileged, unused on VPS), telegram/shadow_monitor.py (VPS, read-only), control_plane.bot (NEW) | NEW plane is authoritative for operator interface; legacy monitor disabled on VPS |
| EMA | indicators/ema.py, research copies, control_plane.indicators | production = control_plane (verified formulas); research quarantined |
| VWAP | institutional/vwap.py, research variants, control_plane.analytics | production = control_plane (session typical-price, UTC reset) |
| Supertrend | research/experiments/vwap_supertrend/indicators.py (validated), control_plane.analytics | identical math; production = control_plane |
| Data ingestion | institutional websocket stack (Phase-7), scripts/*, control_plane.ingest | separate concerns: old shadow keeps its own CVD pipeline; new rolling-1m DB is independent |
| Position sizing / risk | risk/risk_manager.py, brokers, control_plane.core.validate_risk | LLM-facing authority = control_plane.core; legacy untouched |

## 4. Conflicts between research and production code

- research/ packages are NOT importable from the deployed control_plane
  (verified: only stdlib/numpy/pandas imports).
- The stale Phase-7 shadow on the VPS still references thresholds/models that drifted
  locally; it remains isolated in SHADOW with broker isolation intact — flagged,
  deliberately not modified during integration.
- Old telegram-monitor vs new bot token conflict → resolved by disabling the former.

## 5. Backup

/opt/ophelia_backup_20260822_1029.tar.gz (78MB, sha256 7ace259714ea05d42fde…)
created BEFORE any modification. Rollback procedure in RUNBOOK.

---

## ADDENDUM — 2026-08-25 audit & live-ready pass

### Findings (this pass)
1. LLM "language service unavailable" root-caused: primary failure exception was
   swallowed without logging (llm.py), and the configured fallback model
   qwen3:1.7b was NEVER INSTALLED on the VPS -> every primary hiccup became a
   total failure. Fixed: real failure logging, fallback installed (1.4 GB),
   keep_alive=60m + periodic warmup (model now stays resident).
2. Latency root-caused: cold model loads (Ollama unloads after idle) + common
   queries routed through the LLM. Fixed: keep-alive warm model (simple LLM
   query 40.3s -> 4.3s) and deterministic fast-paths for the most common
   natural queries ("what's SOL doing?" 10-40s -> 0.01s, no LLM call).
3. Watchlist was SOL-USDT only; required default is BTC/ETH/XRP/SOL. Fixed:
   DB-backed watchlist (seeded from OPH_SYMBOLS), 24h backfill on add, data
   deletion on remove, exchange-instrument verification before add.
4. No slash commands existed. Implemented: /hi /status /health /progress
   /position /setup /watchlist /bingx /edit /closeall /help /live (+/start
   /stop aliases).
5. No live execution path existed. Implemented (mode-gated): SHADOW (default)
   vs LIVE double-confirmed via Telegram; signed BingX client (endpoints
   mirrored from core/endpoints.py, no invented fields); trade endpoints
   hard-disabled unless mode==LIVE; clientOrderId idempotency; audit log.
6. Position engine added: multi-stop (entry%/VWAP%/Supertrend%, first-hit
   exits, invalid-side stops rejected), partial targets (qty from entry fill),
   trailing (favorable-only ratchet), event idempotency (strategy|symbol|tf|
   candle_ts|direction), automation expiry.
7. VWAP_SUPERTREND strategy detection added (green ST x VWAP from below =
   LONG; red ST x VWAP from above = SHORT) with session-reset + >2%
   discontinuity guards (UTC-day VWAP re-anchor is never traded).
8. BingX account view (/bingx) verified live against the real account
   (read-only path).

### Verification (VPS, 2026-08-25)
- 20/20 engine tests + 16/16 conversation tests pass locally; ruff/mypy clean
  on all new code; remote py_compile OK on venv Python 3.14.4.
- Live harness: /bingx OK (balance 25.22 USDT, 1 position, uPnL +2.30),
  watchlist add/remove lifecycle OK (1440 rows -> 0), LIVE gate OK
  (SHADOW -> LIVE -> SHADOW, exact-phrase requirement enforced).
- Backup before changes: /opt/ophelia_backup_20260825_pre_live.tar.gz
  (sha256 11ddcbb608532a65...).
