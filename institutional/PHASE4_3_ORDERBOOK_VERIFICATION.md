# PHASE 4.3: ORDER-BOOK MICROSTRUCTURE VERIFICATION REPORT

## 1. Executive Summary
This phase conducted a real-data verification of the BingX public WebSocket depth streams (`@depth20` and `@depth`). The core objective was to determine if Ophelia can calculate mathematically defensible canonical Order Flow Imbalance (OFI) and other microstructure metrics without substituting data from other exchanges.

**Conclusion**: Canonical OFI is **UNAVAILABLE**. The BingX public WebSocket depth stream provides periodic full-book snapshots rather than an incremental event feed. Sequence IDs contain gaps, meaning intra-snapshot events are invisible. However, many other microstructure metrics (e.g., Microprice, Depth Imbalance) are **AVAILABLE**.

## 2. Actual BingX Endpoint / Stream
*   **WebSocket URL**: `wss://open-api-ws.bingx.com/market`
*   **Subscription Topics Tested**: `BTC-USDT@depth20`, `BTC-USDT@depth`
*   **Compression**: Payloads are gzipped (`gzip.decompress` required).

## 3. Raw Payload Schema
```json
{
  "code": 0,
  "data": {
    "asks": [ ["64740.24", "11.426913"], ... ],
    "bids": [ ["64727.92", "0.001839"], ... ],
    "lastUpdateId": 16226307465
  },
  "dataType": "BTC-USDT@depth20",
  "success": true,
  "timestamp": 1786371499993
}
```
*   `asks`: Always 20 levels. Ordered highest price to lowest price (descending).
*   `bids`: Always 20 levels. Ordered highest price to lowest price (descending).
*   `lastUpdateId`: An incrementing sequence number, but jumps/gaps exist between delivered messages (e.g., 16226307465 -> 16226307467).

## 4. Snapshot vs Delta Determination
The stream provides **Full Snapshots**.
*   **All levels present?** Yes, exactly 20 bids and 20 asks in every message.
*   **Zero quantities?** No. Zero quantities are never sent to indicate a deleted level. 
*   **Conclusion**: BingX does not broadcast incremental depth updates over these public channels.

## 5. Sequence Semantics
*   **Update IDs**: The `lastUpdateId` is monotonic but **not continuous**. 
*   **Gaps**: Sequences skip (e.g. `966` -> `972`). This proves that BingX processes internal order book events that are not broadcasted individually to the public WebSocket feed.
*   **Synchronization**: Because it's a stream of snapshots, no local book reconstruction or REST synchronization is required. Each message is a fully valid independent state.

## 6. Reconnect Semantics
*   If the WebSocket disconnects, no state reconstruction is required. The engine simply waits for the next snapshot message upon reconnection.
*   Staleness must be managed via a timestamp threshold (e.g., if `time.time() - timestamp > STALE_MS`, degrade to `STALE` or `UNAVAILABLE`).

## 7. Order Book Reconstruction Result
Local order book reconstruction is **not applicable/required** because the feed provides independent snapshots rather than deltas. The snapshot replaces the previous state entirely.

## 8. Microstructure Metric Availability Matrix

| Metric | Classification | Reason |
| :--- | :--- | :--- |
| **Best Bid / Best Ask** | AVAILABLE | Trivially derived from the snapshot boundaries. |
| **Mid Price** | AVAILABLE | Trivially derived from BBO. |
| **Absolute/Relative Spread**| AVAILABLE | Trivially derived from BBO. |
| **Multi-level Depth** | AVAILABLE | Up to 20 levels are consistently provided. |
| **Depth Imbalance** | AVAILABLE | Can be calculated instantly from any snapshot (`(BidDepth - AskDepth) / TotalDepth`). |
| **Queue Imbalance** | AVAILABLE | Same as above, applied to the top level. |
| **Order Book Slope** | AVAILABLE | Can be calculated across the 20 provided levels. |
| **Order Book Concentration**| AVAILABLE | Can be calculated across the 20 provided levels. |
| **Price Impact Approx.** | AVAILABLE | Can be estimated up to the depth of the 20 levels. |
| **Canonical OFI** | **UNAVAILABLE** | **Gaps in sequence IDs mean intermediate events are invisible. Cannot difference sequential states accurately.** |
| **Event-based OFI** | **UNAVAILABLE** | Same reason as above. |
| **Microprice** | AVAILABLE | Derived using top-of-book volume weighted prices. |
| **Book Pressure** | PARTIALLY_AVAILABLE | Static pressure is calculable; flow-based pressure is not. |
| **Liq. Withdrawal/Addition**| UNAVAILABLE | Cannot distinguish between natural trade consumption and explicit limit order cancellations between gaps. |
| **Kyle Lambda inputs** | PARTIALLY_AVAILABLE | Trades are available, but price snapshots are decoupled. Correlation is possible but requires approximation. |

## 9. Canonical OFI Determination
**NO — insufficient sequential information.**
Because the BingX depth stream broadcasts periodic snapshots with gaps in the update IDs, the events occurring between those snapshots (additions, cancellations, modifications) are lost. Canonical Cont-Kukanov-Stoikov OFI explicitly requires measuring the change across every single event. Differencing decoupled snapshots results in a statistically invalid OFI.

## 10. Microprice Determination
Calculable via: `(AskPrice * BidSize + BidPrice * AskSize) / (BidSize + AskSize)`.
*   **Freshness**: Bound to the snapshot rate (typically multiple times per second).
*   **Limitation**: It is a derived estimator from static snapshots, representing instantaneous liquidity imbalance at the BBO, not a directional predictor.

## 11. Depth Imbalance Determination
Calculable immediately via the static snapshot levels. It does not require historical state, making it perfectly suited for BingX's snapshot feed.

## 12. Price Impact Determination
Calculable by walking the 20 levels of the book. 
*   **Distinction**: This is a **visible-book impact estimate**, *not* true market impact (which includes hidden liquidity, iceberg orders, and latency arbitrage).

## 13. Kyle Lambda Data Sufficiency
The required inputs ($\Delta P_t$ and signed order flow $q_t$) exist on separate WebSocket channels (depth and trades). Because the feeds are asynchronous and the depth feed is a gapped snapshot, calibrating true tick-by-tick Kyle Lambda is impossible. It would require temporal binning and approximation, keeping it firmly in `RESEARCH_ONLY`.

## 14. Look-Ahead Audit
All verified microstructure calculations (Microprice, Depth Imbalance) rely exclusively on the single isolated snapshot payload timestamp. There is zero reliance on future timestamps or `shift(-1)` logic.

## 15. Execution-Safety Audit
No execution logic (`place_order`, `TradingEngine`, `RiskManager`) was modified. No new heavy dependencies were installed. No synthetic trades or simulated orders were triggered. The isolation of the Institutional Data Layer remains perfectly intact.

## 16. Recommended Next Phase
1.  **Phase 4.4**: Implement canonical parsing of the snapshots inside `websocket_manager.py` (specifically, handling BingX's descending sort order for asks).
2.  Implement the mathematically valid metrics (Microprice, Depth Imbalance, Queue Imbalance, Spread) as read-only properties of the `MarketDataSnapshot`.
3.  Formally reject OFI and Liquidity Addition/Withdrawal formulas in `institutional_math.py` to prevent hallucinated signals.

## 17. Exact Limitations
*   Ophelia cannot detect "spoofing" or rapid order-book cancellations that occur between the gapped BingX snapshots.
*   Only 20 levels of depth are available. Any price impact estimation beyond this depth is impossible.

## CRITICAL DECISION GATE
**QUESTION**: "Can Ophelia legitimately calculate canonical Cont-Kukanov-Stoikov Order Flow Imbalance from the currently verified BingX order-book stream?"

**ANSWER**: **NO** — insufficient sequential information.
