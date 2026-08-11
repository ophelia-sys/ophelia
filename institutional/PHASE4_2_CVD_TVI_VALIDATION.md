# PHASE 4.2: CVD & TVI AGGREGATION VALIDATION REPORT

This document validates the architectural corrections made to the `InstitutionalDataEngine` to achieve mathematically rigorous, deduplicated, window-based aggregation of Cumulative Volume Delta (CVD) and Trade Volume Imbalance (TVI).

## 1. Original Defect & Root Cause
In Phase 4.1, it was discovered that `engine.py` appended trades to an unbounded (or 1000-max) deque, and `get_snapshot()` iterated over this deque without clearing it or windowing the sum. This caused overlapping periods to double-count trades if `get_snapshot()` was called sequentially, rendering CVD and TVI statistically invalid.

## 2. New Aggregation Architecture
The architecture has been redesigned to decouple **Raw Trade Retention** from **Analytical State Calculation**:
*   **Raw Trade Retention**: The engine retains a maximum of 10,000 recent trades (covering approximately 10-15 minutes on highly liquid pairs) within `_trades` to allow multiple window queries.
*   **Analytical State Calculation**: `get_snapshot(timeframe)` acts as a pure read-only filter. It iterates over the bounded buffer and calculates the sum *strictly* for trades whose exchange timestamp falls within the explicit window `[now - timeframe_ms, now]`.
*   **Snapshot Purity**: Repeatedly calling `get_snapshot()` without new exchange trades arriving guarantees mathematically identical outputs, as it doesn't consume or flush state.

## 3. Duplicate Handling
To protect the aggregation against WebSocket reconnects, replays, or duplicated event delivery:
*   A `trade_id` field has been added to `TradeEvent`.
*   `rest_adapter.py` extracts this from `fillId`.
*   `websocket_manager.py` extracts this from the `t` field.
*   `engine.py` maintains an O(1) look-up `set()` of the last 10,000 processed `trade_id`s. Any incoming event whose `trade_id` exists in the set is instantly dropped.

## 4. Exact Mathematical Definitions
Window $W = [t_{now} - timeframe, t_{now}]$

*   **BUY_VOLUME** = $\sum Q_i$ for all trades $i \in W$ where `isBuyerMaker == False` (Aggressor is Buyer).
*   **SELL_VOLUME** = $\sum Q_i$ for all trades $i \in W$ where `isBuyerMaker == True` (Aggressor is Seller).
*   **Delta CVD** = $BUY\_VOLUME_W - SELL\_VOLUME_W$
*   **TVI** = $(BUY\_VOLUME_W - SELL\_VOLUME_W) / (BUY\_VOLUME_W + SELL\_VOLUME_W)$

## 5. Timestamp & Look-ahead Behavior
*   The engine evaluates inclusion using the strictly historical condition: `window_start <= trade.timestamp <= now`.
*   Future-dated trades (if delivered by exchange desync) are excluded because `trade.timestamp > now`.
*   Local machine time is only used to anchor the `now` bound; trade inclusion strictly uses the exchange-provided `T` (trade time).

## 6. Thread-Safety & Execution Isolation
*   **Thread Safety**: Trades are written into the buffer inside a `threading.RLock()` via the background WebSocket thread. `get_snapshot()` acquires the exact same lock to read the buffer. Iteration uses a copied `list()` of the deque to avoid iteration size changes during processing.
*   **Execution Isolation**: The changes are strictly isolated to `institutional/data/`. `TradingEngine`, `DecisionEngine`, and the EMA strategy logic remain completely untouched.

## 7. Data Quality Semantics
*   If `trades_in_window == 0`: Quality degrades to `INSUFFICIENT_DATA`, and `cvd` / `tvi` are returned as `None` (UNAVAILABLE). They are **never** fabricated as `0.0`.
*   If a trade is missing the `isBuyerMaker` flag: It does not contribute to CVD/TVI, and quality degrades to `DEGRADED`.

## 8. Test Results
The comprehensive `test_institutional_trade_aggregation.py` suite passed with 100% success (14 tests covering all edge cases):
1.  **Single Buy / Sell**: Correct volume and TVI direction.
2.  **Equal Buy/Sell**: CVD exactly 0.
3.  **Duplicate Rejection**: Verified `trade_id` uniqueness prevents double counting.
4.  **Repeated Snapshots**: Proven identical outputs without state consumption.
5.  **Timeframe Windows**: Proven that old trades (e.g. 61s old in a 1m window) are ignored.
6.  **Zero-denominator**: Handled gracefully (`None`, not crash/fake zero).
7.  **Future-dated Exclusion**: Ignored future trades.
8.  **Missing Aggressor**: Safely ignored and flagged `DEGRADED`.
9.  **No Trades**: Flagged `INSUFFICIENT_DATA` and returned `None`.
