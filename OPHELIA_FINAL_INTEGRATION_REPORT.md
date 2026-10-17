# OPHELIA FINAL INTEGRATION REPORT

**Date:** 2026-08-25 · **Operator:** OX (ox-alpha) · **VPS:** 15.235.193.47 (`vps-e343ca06`, SGP, 4 vCPU / 7.6 GB / 72 GB)
**Final operating mode: SHADOW** (live trading is implemented but OFF; switch requires explicit Telegram double-confirmation by the user)

---

## 1. Existing system audit

Found and preserved (verified working before changes):
- Layered control plane: Binance 1m ingest → SQLite rolling store → analytics → deterministic core → LLM intent layer → NLG → Telegram.
- 24h retention + 30-min cleanup (live-verified in logs), EMA9/20, session VWAP (UTC reset), Supertrend(10,4), trade flow, volume profile, order book, IST blackout 02:30–05:30, sessions model, news bias engine, anti-fabrication parameter grounding.
- Legacy Phase-7 shadow service (separate system, untouched, still running isolated).

## 2. Local ↔ VPS comparison

- `control_plane/` was **hash-identical** (12/12 files, md5) before this pass — no drift in the production plane.
- Local repo has large uncommitted research/ trees; intentionally never deployed (source-of-truth rule).
- Legacy local `core/trading_engine.py` threshold-key mismatch remains flagged (pre-existing, out of scope, untouched).

## 3. Changes made (summary)

1. **LLM reliability** — root cause of “language service unavailable” fixed (see §4).
2. **Latency** — warm model + deterministic fast-paths (see §5).
3. **Watchlist** — DB-backed, 4-symbol default, add/remove with verification + data lifecycle.
4. **Slash commands** — full operator set (§17–§20 of master spec).
5. **VWAP_SUPERTREND strategy** — crossover detection with reset guards.
6. **Position engine** — multi-stop / partial targets / trailing / breakeven hook / expiry.
7. **Live execution path** — mode-gated, double-confirmed, idempotent, audited (OFF by default).
8. **/bingx account view** — live read-only account data.
9. **/closeall** — double-confirmed emergency close (live: exchange call; shadow: local close).

## 4. Qwen3 4B installation & the “language service unavailable” bug

Root cause (two stacked faults, both fixed):
1. `llm.py` swallowed the primary-model exception **without logging it**, then
2. fell back to `qwen3:1.7b`, which **was never installed** on the VPS → guaranteed total failure on any primary hiccup (timeout, Ollama cold load, memory pressure).

Fixes: real failure logging (`[llm] ERROR: primary … failed after Ns: reason`, retained in `last_error()` for /status), fallback model installed (1.4 GB), `keep_alive=60m` + warmup at startup and every 4 min (model stays resident). Fallback use is now logged, never silent.

## 5. LLM latency before/after

| path | before | after |
|---|---|---|
| “what's SOL doing?” (most common) | 40–60 s (LLM) | **0.01 s** (deterministic fast-path, no LLM) |
| LLM simple query (warm) | 40.3 s measured | **4.3 s** |
| LLM automation parse | ~12–13 s | ~12 s (acceptable; complex intent) |
| health / commands | 0.3 s | 0.3 s |

Cold-start eliminated by keep-alive (Ollama previously unloaded the model after idle; each first message paid a full CPU reload).

## 6. Files modified

Local (all deployed to VPS unless noted): `control_plane/{config,db,llm,ingest,analytics,core,telegram_bot,nlg,__main__}.py`; **added** `control_plane/bingx_client.py`; local-only: `tests/test_control_plane_engine.py`, `scripts/validate_screenshots.py`; docs updated.

## 7. Services

- `ophelia-control.service` — restarted twice (deploy + fix); active, restart-safe (systemd).
- `ollama.service` — active; models: `qwen3:4b` (2.5 GB), `qwen3:1.7b` (1.4 GB).
- `ophelia-shadow.service` — untouched, running (separate legacy system).

## 8. Qwen3 4B resource usage

VPS RAM after keep-alive: 3.9 GiB used / 7.6 GiB (model resident ~2.5 GB) — comfortable. CPU spikes only during generation. 4 vCPU sufficient; concurrency limited naturally (single bot loop).

## 9. Telegram natural-language tests

Verified via on-VPS harness (sends captured, nothing transmitted): “what's sol doing” (0.01 s, full briefing), “health”, “status”, “positions”, “news”, watchlist queries, automation parse (“supertrend vwap cross on sol 3m 50% 20x” → VWAP_SUPERTREND/3/50/20 ✓), follow-up context handling preserved from prior implementation.

## 10. Market-data tests

4 symbols ingesting every ~20 s (BTC/ETH/SOL/XRP), 5,764+ rows, newest candle ≤1 min old; dynamic aggregation 1m→3m/5m/15m verified through tools; 24h hard cap enforced in `query_candles`.

## 11. Watchlist tests

add LINK → verified on exchange → backfilled 1,440 rows → tracking live; remove LINK → rows 0, tracking stopped; bogus symbol → rejected with clear message; “gold” resolves to PAXGUSDT via verified alias (only added if the instrument exists).

## 12. News-engine tests

Daily bias BULLISH (crypto breadth methodology), honest UNKNOWN policy for unavailable macro inputs, preference-only policy preserved.

## 13. EMA verification

EMA (alpha=2/(N+1), SMA seed) unchanged and covered by tests; EMA9/20 reported at every crosshair in §16.

## 14. VWAP verification

Session VWAP (hlc3, volume-weighted, UTC-day reset) unchanged; series form added. At screenshot-3 crosshair the reset jump measured **95.5938 → 98.7833 (+3.36%)** — impossible for real VWAP, proving the reset artifact.

## 15. Supertrend verification

Canonical ST(10,4) recursion preserved; full-series form added and cross-verified against the original last-bar implementation. Flip mechanics audited bar-by-bar with band values (see §16).

## 16. TradingView screenshot validation

Fingerprint method: the readout OHLC is the **forming** candle at screenshot time → open matched tightly, high/low containment, chart tz resolved from data (**IST**, confirmed twice).

| | Screenshot 1 | Screenshot 2 | Screenshot 3 |
|---|---|---|---|
| Crosshair (chart=IST) | Sun 23 Aug 09:12 | Tue 25 Aug 01:27 | Tue 25 Aug 05:30 |
| Readout candle matched | **exact** 03:42 UTC Binance | **exact** 19:57 UTC Binance | **exact** 00:00 UTC Binance |
| Marked pattern | red ST × VWAP from above | green ST × VWAP from below | blue VWAP vertical jump |
| Ophelia detection | **BEARISH cross 09:03 IST** (ST 95.5369 < VWAP 95.703) | **BULLISH cross fired earlier: 20:09 IST Aug 24** (ST 94.9334 > VWAP 94.8206) | **suppressed — SESSION_RESET_GUARD at 00:00 UTC** |
| Values at crosshair (Ophelia) | ST RED 95.2335 / VWAP 95.6510 | **ST RED 96.5298** / VWAP 95.2666 | ST GREEN 97.3594 / VWAP 98.7833 (post-reset) |
| Would Ophelia take it? | **YES — SHORT** | **NOT at 01:27** (already long-then-flipped; canonical ST went RED at 17:00 UTC when price 95.36 touched band 95.7038) | **NO — reset artifact, correctly never traded** |

**Screenshot 2 discrepancy — precise reason (code NOT forced to match):** at the marked candle the TradingView indicator shows a GREEN Supertrend 95.472 *below* price while canonical ST(10,4) on the same Binance prices is RED at 96.5298 *above* price (band-touch flip at 17:00 UTC verified bar-by-bar: close 95.360 < lower band 95.7038, ATR 0.4214). A factor-4 Supertrend cannot sit ~1% below price immediately after a band-touch flip — the TV indicator's Supertrend parameters therefore differ from canonical 10/4 (its status line “5 9 20 200 2 10 4 2 hlc3 2” maps differently). The marked “cross at 01:27” does not exist under the canonical rule; the true canonical bullish cross that day fired at 20:09 IST.

**Entry timing (spec §21):** crossovers are evaluated on **closed** candles only — detection = candle close, execution = immediately after (market), i.e. at the open of the next candle. “Entry at the start of the crossover candle” would require knowing that candle's close in advance (lookahead) and is not implemented. For screenshot 1: crossover candle 09:03–09:06 IST → execution ~09:06 IST.

## 17. /setup test

Renders the armed/pending setup exactly as Core holds it: strategy, entry semantics, margin/leverage, stop rules, targets, trailing, mode, status, expiry. Verified in harness (no-setup and pending paths).

## 18. /position test

“No active position.” path verified; live-path rendering implemented (entry/current/stop/conditions/uPnL/PnL%); populates from real positions once one exists.

## 19. /edit test

Edit menu shows current pending setup or position with the six edit options; changes route through the same grounded-parameter flow (anti-fabrication preserved).

## 20. /closeall safety test

SHADOW path: “No open positions to close.” when empty; warning + /yes required; LIVE path sends `closeAllPositions` only after double confirmation and reports failure honestly (never assumes success).

## 21. /bingx test

**Live-verified against the real account:** balance 25.2203 USDT, equity 27.52, available 11.94, uPnL +2.30, 1 open exchange position with liquidation price; today's Ophelia-tracked realized PnL resets 00:00 UTC (05:30 IST) and is labeled as such.

## 22. 24h retention/cleanup test

Cleanup ran on schedule (deleting 17–120 rows/cycle as the window slides); analytical API hard-caps at 24h; watchlist removal deletes the symbol's rows immediately (verified: 1,440 → 0).

## 23. Risk validation test

Blackout (02:30–05:30 IST) enforced in proposal path; margin/leverage/notional caps enforced (`CoreReject` paths unit-tested); invalid stop sides rejected with explicit messages; equity now sourced from the live account when available.

## 24. Conditional automation test

Full flow verified: NL create → missing-parameter detection → proposal → YES arms → watcher detects confirmed crossover → PROPOSED → YES/NO confirm → shadow open/skip. Duplicate prevention: event id `strategy|symbol|tf|candle_ts|direction` (unit-tested); automation expiry supported (`expiry_hours` → EXPIRED notification).

## 25. Shadow test

Default mode SHADOW persisted in DB; in SHADOW the signed trade client is hard-refused (`TradeDisabledError`) and `_live_client()` raises — no code path can place a live order. Verified by unit test + live harness (mode SHADOW→LIVE→SHADOW round-trip).

## 26. Health/recovery tests

/health reports CPU/RAM/disk/uptime/data-age/cleanup/sessions; service restart-safe (state in SQLite; mode persisted); ingest self-heals after network errors (observed live); LLM failures logged and reported via /status.

## 27. Security review

- Secrets: never logged, never printed (env-only; control.env root-readable; outputs redacted in all harnesses).
- My temp scripts removed from VPS `/tmp`; **stale `/tmp/cp_tg_proof.py` from an earlier session (referenced the token env var) deleted**; other stale artifacts removed.
- LLM has no exchange access (denylist + architecture); trade endpoints disabled unless mode LIVE.
- Backup before changes: `/opt/ophelia_backup_20260825_pre_live.tar.gz` sha256 `11ddcbb6…`.
- **Action required by user:** the SSH password shared in chat was never used (key auth); rotate it anyway, and consider rotating the Telegram token since it once appeared in a chat transcript.

## 28. Remaining limitations

1. Live fills are taken from order response + mark price; exchange fill-stream reconciliation (partial fills) is not yet wired — acceptable for the intended order sizes, flagged for hardening.
2. Quantity precision uses 3-decimal rounding + min-notional check; per-contract stepSize from the contracts endpoint not yet applied.
3. News engine remains crypto-breadth only (macro/DXY/rates honestly UNKNOWN — free-source constraint unchanged).
4. Breakeven (“move stop to cost at +0.8%”) parses and stores but its auto-trigger is a TODO in the engine (trailing and multi-stop fully active).
5. The TradingView indicator's Supertrend parameters differ from canonical 10/4 (proven in §16); if you want the bot to mirror the TV chart exactly, the TV indicator's parameter mapping must be provided.
6. Legacy Phase-7 threshold-key mismatch (local) still open — separate system, untouched by design.

## 29. Exact steps to switch to LIVE

1. Open Telegram → send `/live` (shows current mode).
2. Send `/live on` (or `/start live`) → Ophelia asks for confirmation → send `YES`.
3. Ophelia demands the exact phrase → send `CONFIRM LIVE`.
4. Mode = LIVE (persisted; survives restarts). From then on, confirmed signals execute real BingX market orders with clientOrderId idempotency; /bingx shows your real balance; /closeall (double-confirmed) is the emergency stop.
5. To stop: `/live off` → `yes`. Open exchange positions are **not** auto-closed — use `/closeall` if desired.
6. Recommended first live test: small margin (e.g. “10% margin, 5x”), verify /bingx + /position after the first trigger.

---

**Verification snapshot at report time:** ophelia-control active · ollama active (4b resident, keep-alive 60m) · 4 symbols ingesting · cleanup healthy · mode SHADOW · 36/36 tests green · ruff/mypy clean on all new code.

---

# POST-INTEGRATION OPERATOR CORRECTIONS (2026-08-25, pass 2)

## Command architecture (old vs new)
| aspect | old | new |
|---|---|---|
| slash-command routing | deterministic router existed but thin | **mandatory rule enforced + verified**: every slash command resolves in the router before the LLM path; simulated LLM outage leaves ALL commands fully functional |
| /hi | one-line status string | **master operator menu** (mode/market/automations/positions/news/attention) with Telegram inline buttons; button presses route through the same deterministic router (callback_query support added) |
| /trade | did not exist | deterministic wizard: /trade -> [SUPERTREND+VWAP] / [EMA 9/20]; /st_vwap [3m|5m|15m] [long|short|any], /ema [3m|15m] [bullish|bearish|any]; defaults 3m |
| /sl | did not exist | manual % / VWAP / Supertrend / MULTI-STOP (first-trigger-exit) / breakeven / show; invalid stop sides rejected explicitly |
| /target | did not exist | R-multiple targets (1:2 etc.) stored as R, resolved to % at arm time from the LIVE stop distance (never fabricated) |
| /partial | did not exist | TP1/TP2/... with % @ %, trailing remainder, sum validation (must be 100 or trail remainder) |
| /margin | did not exist | percent-of-available or fixed USDT; live available margin shown |
| /leverage | did not exist | range-validated against Core caps |
| setup completeness | silent defaults | mandatory-field check: strategy/symbol/timeframe/direction/margin/leverage/stop/exit - missing shown as SETUP INCOMPLETE; /arm blocked until complete |
| /setup | short recap | full deterministic spec view (trigger semantics, stops, stop rule, targets, trailing, break-even, status, mode, expiry) |
| /edit | menu text | full editor: stop/trailing/breakeven/qty(+/-)/leverage on OPEN positions (old -> new -> YES/no confirmation; live qty/leverage edits go through the signed client), draft edits route to the wizards |

## Position accounting (root cause + fix)
- **Old behavior:** /position read only the local Ophelia DB -> the real XRPUSDT SHORT visible in /bingx was invisible ("No active position").
- **Root cause:** two different data sources for two commands.
- **Fix:** new `control_plane/account.py` - ONE normalized account-position service (short TTL cache) used by BOTH /position and /bingx.
- **Live acceptance:** `/position` = `XRP-USDT SHORT qty 151 entry $1.4953 liq $1.5798`; `/bingx` = same position, same numbers. CONSISTENT: True. Positions not created by Ophelia are labeled UNTRACKED and trigger RECONCILIATION_REQUIRED (surfaced in /position and /hi attention line).

## PnL accounting (old vs new)
- **Old:** /bingx showed "realized PnL (exchange, total)" - misleading (includes manual/external exchange activity).
- **New:** exchange-wide realized PnL REMOVED from /bingx. Ophelia-tracked PnL only: realized = Ophelia-created positions/shadow trades CLOSED in the current UTC accounting day (persists after close, survives restarts - derived from closed-trade timestamps, no in-memory reset state); unrealized = Ophelia open positions marked to last price; day boundary 00:00 UTC (05:30 IST) shown explicitly.
- Live state: Ophelia realized +0.00 (no Ophelia trades yet today) - correct even though the exchange has history.

## Break-even (TODO completed)
- Deterministic auto-trigger implemented in the position engine: trigger = +X% favorable move, new stop = entry (+ optional buffer), fires once (flag persisted), stop then behaves as a normal protective stop. Unit-tested incl. "drop back to entry exits".

## Partial-fill / state reconciliation
- `account.reconcile()` compares exchange positions vs Ophelia LIVE positions per symbol+side: MISSING_ON_EXCHANGE / QTY_MISMATCH / UNTRACKED_EXCHANGE_POSITION -> RECONCILIATION_REQUIRED flag; local state is never silently trusted. Wired into /position and the /hi attention line.

## Quantity precision (hard-coded rounding removed)
- Live contract specs fetched from `/openApi/swap/v2/quote/contracts` (pricePrecision/quantityPrecision/tradeMinQuantity/tradeMinUSDT): SOL step 0.01 min 0.03, XRP step 1 min 2, BTC step 0.0001, min notional 2 USDT each.
- `core.normalize_qty()` applies step/minQty/minNotional before every live order and logs QTY_NORMALIZED when it adjusts. The old 3-decimal rounding would have produced INVALID XRP orders (step is 1).

## Files changed (pass 2)
- NEW `control_plane/account.py`; `control_plane/{telegram_bot,core,db,nlg,bingx_client}.py` extended; `tests/test_control_plane_commands.py` NEW (34 tests).
- Deployed to VPS (control_plane md5-synced, service restarted, py_compile OK).

## Tests (pass 2)
- 72/72 green total: 34 command-layer + 20 engine + 18 conversation. Covers all mandatory operator tests: master menu, deterministic routing under simulated LLM outage, /position showing the real exchange position, /position<->/bingx consistency, no exchange-total realized PnL, Ophelia-tracked PnL persistence, reconciliation flags, wizards, R-target resolution, break-even auto-trigger, qty step normalization/rejection, /closeall double confirm, duplicate-signal prevention (engine suite).

## Measured command latency (VPS, live)
/hi 0.30-0.67s · /status 0.30s · /position 0.09-0.35s (live API, cached) · /bingx 0.2-3ms (cached) · /setup ~0ms · /watchlist 2-5ms · /health 0.30s. All < 2s target. LLM path remains ~4s warm for free-form queries.

## Remaining blockers (pass 2)
1. Live fill-stream reconciliation still event-driven-light: reconcile() is poll-based (positions endpoint); per-fill matching via allFillOrders is the next hardening step before high-size live trading.
2. Breakeven buffer uses entry price only (fees not auto-included unless buffer set explicitly).
3. News engine still crypto-breadth only (macro honestly UNKNOWN).
4. TradingView indicator param mismatch documented (screenshot 2); canonical 10/4 unchanged pending user decision.
- System remains in **SHADOW**; /live double-confirmation gate unchanged and re-verified.

## OPHELIA FINAL INTEGRATION ADDENDUM (LATEST)

All remaining tasks specified in the master handoff have been successfully completed:
- **Chunk E**: `/trade` flow setup wizard, `/margin`, `/leverage`, `/sl`, `/target`, `/partial` commands implemented and integrated. `/setup` explicitly shows MISSING fields.
- **Chunk F & G**: `CONTINUOUS` vs `ONE_SHOT` automation modes integrated with `/lifecycle`. Strict FIRST VALID SIGNAL logic confirmed via `core.py` (both VWAP_SUPERTREND and EMA_CROSSOVER). Qwen LLM prompt refined to prevent hallucinating missing default fields.
- **Chunk H**: `/position` vs `/bingx` unified service integration verified (exposing both `exchange_snapshot` and Ophelia-tracked state). Ophelia PnL persists strictly within UTC day boundaries. `/live` SHOW, START, STOP NEW ENTRIES with explicit double confirmation implemented (`/live on` -> `CONFIRM LIVE`).
- **Chunk I & J**: Local changes deployed to VPS (`/opt/ophelia`), verified, and live latency measured. VPS latency to BingX is highly optimized (~42ms vs ~524ms local). Tests verified, and the system is in a stable state.
