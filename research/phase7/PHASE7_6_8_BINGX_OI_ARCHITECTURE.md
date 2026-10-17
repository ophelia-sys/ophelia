# PHASE 7.6.8 — INSTITUTIONAL BINGX OI ARCHIVAL ARCHITECTURE (HARDENED)

## 1. Problem Statement
BingX REST `/openApi/swap/v2/quote/openInterest` provides only current snapshots. To compute the trailing 14-day 90th percentile of 4h Delta OI, Ophelia requires an autonomous local archival engine that perfectly respects causal integrity.

## 2. Institutional Archival Architecture
Do not create a strategy-specific datastore. Design a generalized, append-only institutional data layer.

- **Persistence Layer:** `institutional/data/archive/bingx_oi.sqlite`
- **Table Schema:** 
  - `symbol` (TEXT)
  - `exchange_timestamp` (INTEGER) — Server time provided by the exchange.
  - `receive_timestamp` (INTEGER) — Local wall-clock time immediately upon network payload receipt.
  - `oi_value` (REAL)
  - `oi_notional` (REAL)
  - `data_quality` (TEXT) — E.g., `FRESH`, `DEGRADED`, `STALE`.
  - `source` (TEXT) — E.g., `REST_POLLER_V1`.
  - `schema_version` (INTEGER)
  - **PRIMARY KEY** (`symbol`, `receive_timestamp`)

## 3. Causal Timestamp Safety (CRITICAL)
- **Rule:** Never round or truncate a timestamp backward. 
- **Implementation:** If a payload arrives at 10:05:58, its `receive_timestamp` is strictly 10:05:58. 
- **Consumption Gating:** The S3 trading engine evaluates decision state at discrete intervals. An observation may only be consumed if `receive_timestamp <= decision_timestamp`.
- **Append-Only Immutable State:** The archive must never overwrite historical observations simply because a concurrent or delayed poll resolves differently. Missing gaps are permanently recorded as gaps.

## 4. Polling Cadence & Network Jitter
- **Target Interval:** 5 minutes.
- **Jitter Handling:** Network latency implies polls will execute at slightly offset times (e.g., 10:00:03, 10:05:07). The S3 mathematical engine utilizes `.merge_asof(direction='backward')` to align these exact timestamps causally to the 1m candle evaluation tick. Exact wall-clock alignment is not required; causal freshness is.

## 5. Explicit Staleness Policy (Data-Quality Constraints)
The 60-minute cutoff is an explicitly defined **DATA-QUALITY POLICY**. It is not claimed to be mathematically optimal.
- **FRESH:** OI observation age $\le 15 \text{ minutes}$.
- **DEGRADED:** $15 \text{ minutes} < \text{OI observation age} \le 60 \text{ minutes}$. (Forward-filled by the engine).
- **STALE:** $\text{OI observation age} > 60 \text{ minutes}$. (Yields explicit `NaN` to the S3 formulation).
- **UNAVAILABLE:** Missing entirely or persistently STALE.
- **Rule:** If the latest OI reading is `STALE` or `UNAVAILABLE`, the S3 final signal unconditionally evaluates to `UNAVAILABLE`.

## 6. Outage & Restart Behavior
- **On Restart:** The engine connects to `institutional/data/archive/`, preserves all historical observations, resumes polling, and visually detects network gaps.
- **Missing Intervals:** No artificial rows are manufactured. If 3 hours of polling failed, there is simply a 3-hour timestamp gap in the SQLite table, mathematically enforcing the `STALENESS` policy.
