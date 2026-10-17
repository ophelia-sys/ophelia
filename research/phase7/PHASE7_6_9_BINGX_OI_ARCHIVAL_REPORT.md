# PHASE 7.6.9 — BINGX OI ARCHIVAL REPORT

**Status:** PASS / RUNNING
**Date:** 2026-08-14

## 1. Objective
Establish an institutional-grade, read-only open interest (OI) archival mechanism for BingX live market data, enforcing strict causal constraints. This serves as the foundation for live evaluation of the S3_CONDITIONAL_VOL_V1 alpha candidate.

## 2. Completed Architecture
The architecture comprises a robust SQLite-backed archival system and a dedicated polling daemon (`institutional/data/archive/oi_poller.py`).

### 2.1 Persistence Layer
- **Storage:** `bingx_oi.sqlite` (Append-only SQLite database)
- **Causality Enforcement:** The system inherently uses the local `receive_timestamp` as the primary time key. A decision made at time $t$ may only consume an observation if $receive\_timestamp \le decision\_timestamp$. The `UNIQUE(symbol, receive_timestamp)` constraint prevents exact-time duplication while allowing multiple observations per second if necessary, though polling is locked to 5 minutes.
- **Fields Logged:** `observation_id`, `symbol`, `exchange_timestamp`, `receive_timestamp`, `oi_value`, `oi_notional`, `data_quality`, `source`, `schema_version`.

### 2.2 Polling Daemon
- **Target Symbols:** BTC-USDT, ETH-USDT, SOL-USDT, XRP-USDT, BNB-USDT
- **Cadence:** 5 minutes
- **Safety:** Implemented as a read-only daemon. It handles `SIGINT`/`SIGTERM` for graceful shutdown and implements bounded exception handling to survive transient network failures without creating orphaned processes.
- **Staleness Tracking:** Observations are tagged dynamically on read. Missing observations are NOT backward-filled.

## 3. Data Quality & Warmup Rules
The standard for S3 OI evaluation requires a rigorous historical baseline.

### 3.1 Quality States
Data is evaluated dynamically at query-time:
- **FRESH:** $\le$ 15m age
- **DEGRADED:** > 15m and $\le$ 60m age
- **STALE:** > 60m age
- **UNAVAILABLE:** persistently missing / no data

### 3.2 Warmup Progress
S3 requires a 14-day rolling baseline for percentile evaluation, plus a 4-hour forward delta requirement. 
**Required:** 14 days + 4 hours ($\approx$ 4,080 polling points per symbol).
The system evaluates this independently per symbol.

## 4. Operational Status
The daemon has been started successfully as a background task.

**Current Live Status (as of reporting):**
- Polling is active.
- Database writes are successfully persisting.
- `receive_timestamp` vs `exchange_timestamp` causality tests passed.
- No execution logic exists in the poller.

```text
BTC-USDT   | OI Age:     90.8s | Polled: 8     | Warmup:   0.2%
ETH-USDT   | OI Age:     90.8s | Polled: 8     | Warmup:   0.2%
SOL-USDT   | OI Age:     90.8s | Polled: 8     | Warmup:   0.2%
XRP-USDT   | OI Age:     90.8s | Polled: 8     | Warmup:   0.2%
BNB-USDT   | OI Age:     90.8s | Polled: 8     | Warmup:   0.2%
```

## 5. Conclusion
The OI Archival layer is functionally complete, causally sound, and actively accumulating the required baseline for S3 evaluation.
