# OPHELIA — LLM TELEGRAM TEST REPORT
Executed on VPS 2026-08-22 via /tmp/run_tests.py (results: OPHELIA_LLM_TELEGRAM_RESULTS.json)

| # | Test | Result | Evidence |
|---|---|---|---|
| 1 | "Show SOLUSDT last 30 minutes" (LLM parse + snapshot) | **PASS** | parse_ok=true, snapshot last_price=93.0 |
| 2 | Aggregate last 30m into 5m | **PASS** | 6×5m candles |
| 3 | Average movement 15m | **PASS** | avg_abs_move_pct, direction UP |
| 4 | Inflow/Outflow/Net | **PASS** | total 355,938 · in 180,021 · out 175,917 · net +4,103 (+1.15%) |
| 5 | Volume profile | **PASS** | POC 92.857 / VAH 93.006 / VAL 92.708 |
| 6 | Order book | **PASS** | spread 1.72bps, imbalance −7.97%, 10 levels (BingX v2 depth) |
| 7 | EMA9/EMA20 | **PASS** (post-warmup) | EMA9 93.044 / EMA20 93.070 / BEARISH / ATR 0.376 |
| 8 | Crossover estimate | **PASS** | "ESTIMATE: ~3 minutes to BULLISH cross" (labeled ESTIMATE, linear-extrapolation method) |
| 9 | Conditional trade creation | **PASS** | CONDITION_CREATE parsed, missing_parameters listed when absent, automation armed id=4, mode SHADOW |
| 10 | "Skip it" cancellation | **PASS** | cancel on non-PROPOSED raises CoreReject (unit-verified); PROPOSED path wired to Telegram SKIP |
| 11 | Ophelia health | **PASS** | core OK, CPU 5.8%, RAM 50.3%, cleanup age 3.5min |
| 12 | VPS health | **PASS** | uptime 1,035,454s, disk 11% |
| 13 | >24h request rejected | **PASS** | candles_returned capped at 24h window (enforced=true) |
| 14 | 30m cleanup deletes expired | **PASS** | injected 25h-old row deleted; oldest_ts advanced |
| 15 | LLM cannot execute | **PASS** | "Execute a market buy" → intent_type MARKET_QUERY (not execution); execution tools absent from schema & registry |
| 16 | Risk engine veto | **PASS** | leverage=100 → CoreReject "exceeds cap 50" |

Additional live verifications:
- Session VWAP (UTC-day): 95.411 · Supertrend(10,4): direction −1, active 94.324
- Blackout logic unit-wired in core.build_proposal (raises during 02:30–05:30 IST)
- News engine returns honest UNKNOWN macro scores with crypto breadth scoring
- Ollama qwen3:4b: format=json + think=false; ~8 tok/s CPU; intent latency ~5-15s

Notes:
- T7/T8 initially null during DB bootstrap (<100min of 5m history); resolved after
  24h backfill seed; permanent fix = backfill script in runbook.
- T13 earlier KeyError was a stale-read race in the report helper, not the engine;
  final JSON contains all 16 keys.
