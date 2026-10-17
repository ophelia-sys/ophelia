# OPHELIA — LLM TELEGRAM CONTROL PLANE — ARCHITECTURE
Phase: Final integration · Date: 2026-08-22 · Status: DEPLOYED (SHADOW)

## 1. Topology

```
TELEGRAM (user, allow-listed)
    ↓ getUpdates (long-poll)
control_plane.telegram_bot        [VPS systemd: ophelia-control]
    ↓ text
control_plane.llm  → Ollama qwen3:4b (fallback qwen3:1.7b) @127.0.0.1:11434
    ↓ strict JSON intent (validated; raw LLM text NEVER reaches Core)
INTENT ROUTER (telegram_bot.handle)
    ├── READ TOOLS  → control_plane.analytics / db / news   (read-only)
    ├── CONTROL     → db.automations (create/pause/resume/cancel/list)
    └── PROPOSAL    → control_plane.core.build_proposal()
                        ↓ deterministic risk + geometry
             TELEGRAM CONFIRMATION (YES/NO or SKIP it)
                        ↓ user confirms
             SHADOW execution recorded (db.shadow_trades) — NO live orders exist
OPHELIA CORE remains authoritative for strategy/risk/sizing/validation.
```

## 2. Components (source of truth: `/opt/ophelia/control_plane`, repo `control_plane/`)

| module | responsibility |
|---|---|
| config.py | env-driven settings; secrets only via env |
| db.py | SQLite rolling 1m candles (WAL), automations, shadow_trades; TTL cleanup; application-level 24h cap on every query |
| ingest.py | Binance fapi 1m poller (20s cadence) incl taker-buy volume; cleanup every 30 min |
| indicators/analytics | EMA9/20 (α=2/(N+1), SMA seed), Session VWAP (UTC), Supertrend(10,4.0) Pine-equivalent, arbitrary TF aggregation from 1m (2..60m), trade flow (inflow=taker_buy), volume profile (uniform-in-bar allocation, POC/VAH/VAL 70%), order book (BingX v2 depth, compact top-N), movement stats, EMA crossover ESTIMATE |
| news.py | daily context: crypto momentum/breadth scoring; macro/dollar/rates = UNKNOWN (no free authoritative source); bias is PREFERENCE only |
| sessions.py | sessions ASIA/LONDON/NY (UTC canonical); blackout 02:30–05:30 IST; daily reset 05:30 IST |
| llm.py | Ollama chat, format=json, think=false, few-shot prompt; schema validation; deny-list scan; param memory merge |
| core.py | risk validation (leverage cap, margin bounds, notional minimums), blackout veto, proposals, condition firing (confirmed-crossover watcher), shadow fills at next price sample, health aggregation |
| telegram_bot.py | polling bot; YES/NO + "Skip it" confirmation flows; fast-paths for health/automations/macro |

## 3. Security model

- Execution tools are NOT exposed to the LLM and do not exist in the control plane.
- LLM output is schema-validated; deny-list scan rejects execute-like intents.
- Secrets (Telegram token, BingX keys) live in `/opt/ophelia/control.env` (root, 600);
  never printed, never sent to the LLM, never logged.
- SSH password was session-only (env var) — must be rotated by owner.

## 4. Data retention contract

- Live DB holds ≤24h of 1m rows per symbol (cleanup sweep every 30 min).
- Every analytical query independently enforces ts ≥ now−24h.
- Requests older than 24h are rejected as unavailable.
- Research/backtest datasets are separate and untouched.

## 5. Failure behavior

LLM down → clarification fallback, no config changes. News down → UNKNOWN bias.
Data gap → queries return error, conditions cannot fire. Risk reject → proposal blocked.
Blackout → new entries refused (existing positions unaffected).
