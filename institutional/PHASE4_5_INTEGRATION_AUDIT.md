# Phase 4.5: Institutional Math Integration Audit

## 1. Lineage Audit Matrix

The following matrix traces every execution-market microstructure feature from its raw BingX input to its terminal status within the Ophelia DecisionEngine architecture.

| Feature Name | Raw Input (BingX) | Data Models | Math Formula (liquidity.py) | Normalized / State | DecisionEngine Status | Production Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Mid Price** | `@depth20` (bids/asks) | `OrderBookSnapshot.mid_price` | `calculate_mid_price` | `MicrostructureState.mid_price` | UNAVAILABLE (Not consumed) | MEASURED |
| **Absolute Spread** | `@depth20` (bids/asks) | `OrderBookSnapshot.spread` | `calculate_spread` | `MicrostructureState.spread` | UNAVAILABLE (Not consumed) | MEASURED |
| **Relative Spread** | `@depth20` (bids/asks) | `OrderBookSnapshot.relative_spread` | `calculate_relative_spread` | `MarketState.liquidity_state` | UNAVAILABLE (Not consumed) | VALIDATED |
| **Queue Imbalance** | `@depth20` (best bid/ask qty) | `OrderBookSnapshot.queue_imbalance` | `calculate_queue_imbalance` | `MicrostructureState.queue_imbalance` | UNAVAILABLE (Not consumed) | MEASURED |
| **Depth Imbalance** | `@depth20` (bids/asks 20 levels)| `OrderBookSnapshot.depth_imbalance` | `calculate_depth_imbalance` | `MicrostructureState.depth_imbalance` | UNAVAILABLE (Not consumed) | MEASURED |
| **Canonical OFI** | N/A | N/A | N/A | `MarketState.order_flow_state` | UNAVAILABLE (Not consumed) | UNAVAILABLE |
| **Microprice** | `@depth20` (bids/asks) | `OrderBookSnapshot.microprice` | `calculate_microprice` | `MicrostructureState.microprice` | UNAVAILABLE (Not consumed) | MEASURED |
| **Book Slope (Bid)** | `@depth20` (bids) | `OrderBookSnapshot.book_slope_bid` | `calculate_order_book_slope` | `MicrostructureState.book_slope_bid` | UNAVAILABLE (Not consumed) | MEASURED |
| **Book Slope (Ask)** | `@depth20` (asks) | `OrderBookSnapshot.book_slope_ask` | `calculate_order_book_slope` | `MicrostructureState.book_slope_ask` | UNAVAILABLE (Not consumed) | MEASURED |
| **Book Concentration**| `@depth20` (bids/asks) | `OrderBookSnapshot.book_concentration`| `calculate_book_concentration` | `MicrostructureState.book_concentration`| UNAVAILABLE (Not consumed) | MEASURED |
| **Visible Impact** | `@depth20` (bids/asks) | N/A (Method) | `calculate_visible_impact_bps`| `MicrostructureState.visible_impact_*`| UNAVAILABLE (Not consumed) | MEASURED |
| **Delta CVD (1m/5m)** | `@trade` (qty, price, side) | `MarketDataSnapshot.cvd` | Engine Aggregation | `MarketState.order_flow_state` | UNAVAILABLE (Not consumed) | VALIDATED |
| **TVI (1m/5m)** | `@trade` (qty, price, side) | `MarketDataSnapshot.tvi` | Engine Aggregation | N/A | UNAVAILABLE (Not consumed) | MEASURED |

### Lineage Defect Corrections
1. **OFI Hallucination (P0):**
   - *Defect:* `MarketState.ofi` was silently substituted with `snapshot.depth_imbalance`.
   - *Correction:* `snapshot.depth_imbalance` has been placed strictly in its proper `MicrostructureState` field, and Canonical OFI has been explicitly marked `UNAVAILABLE`. `MarketState.order_flow_state` checks for valid CVD rather than relying on a fabricated OFI metric.

2. **Microstructure Integration Gap (P1):**
   - *Defect:* Several Phase 4.4 metrics existed on `MarketDataSnapshot` but were immediately discarded by `InstitutionalMathEngine` because they lacked explicit mapping into `MarketState`.
   - *Correction:* Created a strongly typed `MicrostructureState` class. All measured microstructure features are now mapped and preserved within `MarketState.microstructure`.

3. **Slope Dimensional Flaw (P1):**
   - *Defect:* `calculate_order_book_slope` relied on absolute price and raw contracts, making it lot-size and asset-price dependent. It also arbitrarily combined both sides of the book into a dict instead of explicit state fields.
   - *Correction:* Remapped dependent/independent variables to Quote Notional (Y) and Basis Points (X). Defined separately as `book_slope_bid` and `book_slope_ask` (USDT / BPS).

## 2. Status Definitions

*   **MEASURED**: The metric correctly parses raw BingX data and calculates a mathematically defensible value.
*   **AVAILABLE**: The data source is streaming correctly.
*   **VALIDATED**: The metric has undergone statistical evaluation for non-stationarity or is actively normalized to produce a reliable feature state.
*   **NORMALIZED**: The metric is mapped to a probability, Z-score, or percentile.
*   **RESEARCH_ONLY**: The metric is tracked in logs or states but is actively forbidden from triggering execution.
*   **UNAVAILABLE**: The necessary data is missing, or the metric is unsupported.

Currently, **NO MICROSTRUCTURE METRIC IS PRODUCTION_CONSUMED**. The math engine strictly serves as a statistical evidence and observation layer.

## 3. Look-Ahead Bias & Execution Safety Audit
*   The data layer guarantees isolation by parsing the REST/WebSocket layer and passing **only** `MarketDataSnapshot` to the Institutional Engine.
*   The Math engine runs entirely synchronously, evaluating `T-0` snapshots.
*   Empty books, missing trade aggressors, and cross-books immediately flag their respective feature qualities as `DEGRADED` or `INVALID` without zero-padding or fallback logic.
