# OPHELIA — LLM TELEGRAM CONTROL PLANE — RUNBOOK
VPS: 15.235.193.47 (ubuntu) · Install: /opt/ophelia · Service: ophelia-control

## Daily operation

| action | command |
|---|---|
| status | `systemctl status ophelia-control` |
| logs | `sudo journalctl -u ophelia-control -n 50 --no-pager --output=cat` |
| restart | `sudo systemctl restart ophelia-control` |
| stop | `sudo systemctl stop ophelia-control` |
| LLM check | `curl -s http://127.0.0.1:11434/api/tags` |
| DB stats | `sudo sqlite3 /opt/ophelia/control_data/market_1m.db "select count(*),datetime(min(ts)/1000,'unixepoch'),datetime(max(ts)/1000,'unixepoch') from candles"` |
| backup | `sudo tar --exclude='ophelia/.venv' --exclude='ophelia/external' -czf /opt/ophelia_backup_$(date +%Y%m%d_%H%M).tar.gz -C /opt ophelia` |
| redeploy code | push control_plane.tgz → stop svc → rm -rf control_plane → extract → chown ophelia → start |

## Telegram usage (allow-listed users only)

- "Show SOLUSDT last 30 minutes" / "... using 5m candles" / "... in 3m candles"
- "Show average movement last 15 minutes"
- "Show inflow, outflow and net flow"
- "Show volume profile" · "Show current order book"
- "Show EMA9 and EMA20" · "How many 5m candles before a crossover?" (ESTIMATE)
- "If bullish EMA crossover occurs on SOLUSDT 5m, prepare a trade using 50% margin at 20x"
  → missing params asked → proposal → **YES / NO**
- On trigger: "Confirm execution? YES / NO (or 'Skip it')" — YES records OPEN_SHADOW;
  NO/Skip cancels; automation auto-pauses after firing (re-armable).
- "Pause/Resume/Cancel automation #id" · "Show my active automations"
- "Ophelia health" · "VPS health" · "Data health" · "What's today's macro bias?"

## Known bootstrap/limits

- Indicators need history: full EMA20/ATR/estimates require ~2h uptime after a cold DB
  (or use the backfill script pattern: fetch Binance last 24h 1m once).
- Order book uses BingX v2 depth (v3 returns empty arrays).
- Volume flow requires Binance-sourced candles (taker-buy field); documented approximation.
- Macro/dollar/rates/political scores are UNKNOWN (no free authoritative feed) —
  daily_bias derives from crypto breadth/momentum only, confidence capped.
- Blackout 02:30–05:30 IST blocks NEW entries; positions continue.

## Rollback

`sudo systemctl stop ophelia-control && sudo tar -xzf /opt/ophelia_backup_20260822_1029.tar.gz -C /opt && sudo systemctl daemon-reload && sudo systemctl enable --now ophelia-telegram-monitor && sudo systemctl disable --now ophelia-control`
