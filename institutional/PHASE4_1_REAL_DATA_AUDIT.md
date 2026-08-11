# PHASE 4.1: INSTITUTIONAL REAL-DATA VERIFICATION AUDIT

This document reports the findings of the independent, read-only Real-Data Smoke Test and mathematical verification audit of the Phase 4 Institutional Data Acquisition Layer.

## 1. Actual Endpoints and Streams Verified

A live, read-only smoke test was performed against the BingX Perpetual Swap API for `BTC-USDT`. No execution API keys were loaded.

| Data Type | Actual Transport | Endpoint / Topic Used | Raw Payload Verified? |
| :--- | :--- | :--- | :--- |
| **OHLCV** | REST | `/openApi/swap/v2/quote/klines` | YES |
| **Order Book** | REST & WS | `/openApi/swap/v2/quote/depth` (REST)<br>`@depth20` (WS) | YES |
| **Trades** | REST & WS | `/openApi/swap/v2/quote/trades` (REST)<br>`@trade` (WS) | YES |
| **Open Interest** | REST | `/openApi/swap/v2/quote/openInterest` | YES |
| **Funding Rate** | REST | `/openApi/swap/v2/quote/fundingRate` | YES |
| **Liquidations** | REST | `/openApi/swap/v2/quote/forceOrders` | NO (Invalid Endpoint) |
| **Ticker** | REST & WS | `/openApi/swap/v2/quote/ticker` (REST)<br>`@ticker` (WS) | YES |

## 2. Actual Payload Fields & Aggressor Interpretation

### Aggressor Side: `AVAILABLE`
The WebSocket `@trade` topic and REST trades endpoint both return a payload containing `m` (or `isBuyerMaker` in REST), which acts as a boolean flag.
*   **Mathematical Semantics**: In matching engines, the "Maker" is the resting order. If `isBuyerMaker == true`, the Maker was the Buyer (resting Bid). Therefore, the aggressive Taker who crossed the spread to fill that order must have been the **Seller**.
*   **Implementation**: `TradeEvent.aggressor` correctly interprets `is_buyer_maker = True` as `SELL` and `is_buyer_maker = False` as `BUY`. This provides a true, mathematically verifiable aggressor side.

## 3. Which Formulas are Legitimately Calculable?

| Metric | Required Raw Data | Currently Available | Valid Calculation? |
| :--- | :--- | :--- | :--- |
| Spread | Best Bid/Ask | YES (REST + WS Depth) | YES |
| Relative Spread | Best Bid/Ask | YES | YES |
| Depth Imbalance | Full/Partial Book | YES (20 levels) | YES |
| TVI | Buy/Sell Volume | YES (Trades) | PARTIAL (Flawed aggregation) |
| CVD | Buy/Sell Volume | YES (Trades) | PARTIAL (Flawed aggregation) |
| OFI | Sequential Order Book Diffs | NO (Snapshots only) | UNAVAILABLE |
| Amihud | Returns, Dollar Volume | YES (Klines, Ticker) | YES |
| Kyle Lambda | Price delta, trade volume | NO (No seq aggregation) | UNAVAILABLE |
| OI State | Open Interest History | YES (REST) | YES |
| Funding Z-score | Funding History | YES (REST) | YES |
| Liquidation Imbalance| Liquidations (Force Orders) | NO | UNAVAILABLE |

## 4. Verification Details

### A. Order Flow Imbalance (OFI): `UNAVAILABLE`
OFI requires calculating the exact changes in queue depth across strictly sequential order book events (e.g., matching bid additions vs cancellations). The current `InstitutionalDataEngine` merely holds the *latest* `OrderBookSnapshot` and overwrites it. Sequential differences are lost. Therefore, canonical OFI cannot be calculated and remains `UNAVAILABLE`.

### B. Cumulative Volume Delta (CVD): `PARTIAL`
While the raw *Aggressor Volume* is perfectly available, the implementation inside `engine.get_snapshot()` iterates over `self._trades` (a `deque` of the last 1000 trades) and sums the volume. 
*   **Duplicate Prevention**: FAILED. The deque is never cleared. Successive calls to `get_snapshot` will double-count the same trades if they remain in the deque.
*   **Cumulative State**: FAILED. It calculates a rolling sum of up to 1000 trades, rather than a true cumulative delta over the timeframe.

### C. Trade Volume Imbalance (TVI): `PARTIAL`
TVI suffers from the same deque duplicate-counting bug as CVD. While the raw inputs (aggressive buy/sell volumes) are completely accurate, the aggregation boundary is flawed.

### D. Depth Imbalance & Spread: `AVAILABLE`
Both metrics require only a point-in-time snapshot of the order book. The current engine perfectly stores the latest `OrderBookSnapshot` (updated via WS `@depth20` or REST fallback). Zero-denominator crashes are handled. These are mathematically valid.

## 5. Network / Architectural Verification

*   **Freshness Behavior**: Verified. `MarketDataSnapshot` applies `FRESH` or `STALE` based on whether recent snapshots (age < 30s) are present.
*   **Reconnect Behavior**: Verified. `websocket-client` implements a `_run_forever` loop with a 5-second backoff reconnect mechanism. Because trades are appended to a limited deque and order books simply overwrite a dictionary key, a reconnect will seamlessly resume data feeding without crashing the core `TradingEngine`. 
*   **Execution-Safety Audit**: Verified. The entire `institutional/data/` layer is isolated. There are zero references or invocations to execution APIs (`place_order`, `broker`, `RiskManager`, etc.).

## 6. Audit Conclusion & Remaining Limitations

The data acquisition architecture successfully achieves strict isolation and accurate extraction of raw Institutional features (including true Aggressor Side). 
However, **CVD and TVI aggregation logic must be corrected** to clear the trade buffer upon each snapshot query (or maintain a persistent state) to avoid duplicate volume counting. 
Furthermore, **OFI and Liquidations remain UNAVAILABLE** due to exchange limitations and architectural choices regarding sequential depth handling. 

The accompanying `DATA_AVAILABILITY_MATRIX.md` and `INSTITUTIONAL_DATA_VALIDATION_REPORT.md` will be updated to reflect this audited reality.
