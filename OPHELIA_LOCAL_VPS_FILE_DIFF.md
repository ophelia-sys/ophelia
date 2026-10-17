# OPHELIA — LOCAL ↔ VPS FILE DIFF (post-deployment, 2026-08-22)

Comparison scope: production-relevant paths (/opt/ophelia vs repo). Research trees
excluded from parity by design (local-only).

## ADDED on VPS (by this deployment)

| path | purpose |
|---|---|
| /opt/ophelia/control_plane/ (11 .py) | NEW production control plane (config, db, ingest, indicators+analytics via analytics.py, news, sessions, llm, core, telegram_bot, __main__) |
| /opt/ophelia/control.env (600, root) | TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USER_IDS, BINGX keys copied from legacy .env (values never exposed) |
| /etc/systemd/system/ophelia-control.service | hardened unit; enabled |
| /opt/ophelia/control_data/ | market_1m.db (WAL), news_context.json, test_report.json |
| /opt/ophelia_backup_20260822_1029.tar.gz | pre-change backup (78MB, sha256 7ace259714ea…) |
| ollama binary + systemd service + qwen3:4b & qwen3:1.7b models | LLM runtime |

## MODIFIED

| path | change |
|---|---|
| systemd active units | ophelia-telegram-monitor: RUNNING → STOPPED/DISABLED (token conflict with new bot); ophelia-shadow: unchanged/running |

## DELETED

| path | reason |
|---|---|
| none | old files preserved; only in-memory process replaced |

## CONFLICTING (flagged, intentionally NOT resolved here)

| item | detail |
|---|---|
| local core/trading_engine threshold key bug | reads "threshold" while shipped JSON uses "long_threshold" (silent no-op of Phase-7 shadow decisions locally) — VPS runs older matching code; flagged for a future LOCAL+VPS synchronized fix per checkpoint rule |
| repo drift | massive uncommitted research/ work locally; VPS intentionally not synced with research trees (source-of-truth rule) |

## Hash spot-checks (deployment verification)

- control_plane/analytics.py: local 8404ED09171B… → after final patch redeploy verified
  via remote grep (import json + warmup_min present) and live behavior (EMA/VWAP/ST outputs).
- Backup integrity: tar listed + sha256 prefix recorded pre-changes.

---

## DIFF ADDENDUM — deployment 2026-08-25 (live-ready pass)

### MODIFIED on VPS (/opt/ophelia/control_plane/, local == VPS, md5-verified)
| file | change |
|---|---|
| config.py | 4-symbol default watchlist, LLM_KEEP_ALIVE, DEFAULT_TRADING_MODE |
| db.py | +watchlist/+positions/+events/+audit tables, mode get/set, position CRUD |
| llm.py | failure logging (root cause of "language service unavailable"), keep_alive, warmup, ping, last_error |
| ingest.py | watchlist-driven, 24h backfill on add |
| analytics.py | +supertrend_series, +session_vwap_series, +st_vwap_cross_event (reset/discontinuity guards), +get_vwap/get_supertrend/ema_series |
| core.py | strategy dispatch, dedup, expiry, position engine (multi-stop/partials/trailing), LIVE execution gate, account_summary, system_status |
| telegram_bot.py | slash-command layer, LIVE/CLOSEALL confirm flows, NL watchlist mgmt, deterministic fast-paths (latency), watcher upgrades |
| nlg.py | renderers: position/setup/watchlist/account/status/hi/live/closeall, supertrend/vwap summaries |
| __main__.py | LLM keepalive thread, watchlist seeding |

### ADDED on VPS
| path | purpose |
|---|---|
| control_plane/bingx_client.py | minimal stdlib signed BingX client; endpoints mirrored from core/endpoints.py; trade calls hard-disabled unless mode LIVE |
| qwen3:1.7b (ollama) | previously-missing fallback model |
| /opt/ophelia_backup_20260825_pre_live.tar.gz | pre-change backup, sha256 11ddcbb60853... |
| scripts/validate_screenshots.py (local + /tmp run copy, removed) | TradingView screenshot validation |

### ENV
| file | change |
|---|---|
| /opt/ophelia/control.env | OPH_SYMBOLS=SOL-USDT -> BTC-USDT,ETH-USDT,SOL-USDT,XRP-USDT (values never exposed) |

### DATA
- BTC/ETH/XRP backfilled to full 24h retention (1440 rows each).
- LINK-USDT lifecycle verified: add -> 1440 rows -> remove -> 0 rows.

### LOCAL-ONLY (not deployed, by design)
- tests/test_control_plane_engine.py (20 tests), scripts/validate_screenshots.py,
  research/ tree untouched.
