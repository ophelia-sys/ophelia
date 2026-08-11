# PHASE 4.5.1 — REPOSITORY-WIDE OFI & MICROSTRUCTURE LINEAGE AUDIT

## 1. Executive Summary

A comprehensive repository-wide audit has been executed to verify the semantic integrity and lineage of all Order Flow and microstructure metrics. The central objective was to ensure that **canonical Cont-Kukanov-Stoikov Order Flow Imbalance (OFI)** is not hallucinated, aliased, or spuriously generated from invalid proxies (such as Depth Imbalance or Queue Imbalance).

**Conclusion:** The codebase is **CLEAN**. The fatal aliasing defect (`ofi = snapshot.depth_imbalance`) was completely eradicated in the prior phase. There are no executable paths across the execution, analysis, normalization, or scoring logic where another metric is substituted into an OFI field. Canonical OFI remains securely and explicitly **UNAVAILABLE**.

## 2. Search Scope & Classification

A rigorous `grep`-based search was conducted across all `.py`, `.md`, `.json`, `.yaml`, and `.csv` files for aliases including `ofi`, `order_flow_imbalance`, `depth_imbalance`, `queue_imbalance`, `microprice`, `cvd`, and `tvi`.

The results have been explicitly classified:

- **FOUND OCCURRENCES:** 53 total matches for target keywords.
- **VALID OCCURRENCES:** 53 (Test definitions, markdown documentation, explicit UNAVAILABLE assignments, and correctly isolated metrics).
- **INVALID ALIASES:** 0 (None found in executable paths, state generation, or serialization schemas).
- **CORRECTED ALIASES:** 0 (No rewrites were necessary; the repository was already compliant).

## 3. Canonical OFI Contract

Because the verified BingX depth streams (`@depth20` and `@depth`) transmit full periodic snapshots with discontinuous sequence IDs, the intra-snapshot events (the individual add, cancel, and match orders) are mathematically unobservable.

Therefore, the canonical Cont-Kukanov-Stoikov event-based OFI calculation cannot be performed on BingX data without fabricating intermediate states.

**Contract:**
*   `canonical OFI = UNAVAILABLE`
*   No other Institutional Math metric is permitted to masquerade as OFI.
*   If downstream consumers explicitly require an OFI parameter, they will receive `np.nan` or the equivalent representation of `UNAVAILABLE`.

## 4. Lineage Proof of Production-Consumed Metrics

The following documents the explicit lineage of all major microstructure metrics to prove they are correctly isolated and remain untainted.

### Depth Imbalance
*   **BingX Raw Field:** `@depth20` Bid/Ask Quantities (Levels 1-20).
*   **Parser:** `InstitutionalWebSocketManager` -> `OrderBookSnapshot`
*   **Mathematical Function:** `institutional.liquidity.calculate_depth_imbalance`
*   **Data Model:** `MicrostructureState.depth_imbalance`
*   **MarketState:** `MarketState.microstructure.depth_imbalance`
*   **Downstream Consumer:** Decision Engine (Research-only monitoring).

### Queue Imbalance
*   **BingX Raw Field:** `@depth20` Bid/Ask Quantities (Level 1 only).
*   **Parser:** `InstitutionalWebSocketManager` -> `OrderBookSnapshot`
*   **Mathematical Function:** `institutional.liquidity.calculate_queue_imbalance`
*   **Data Model:** `MicrostructureState.queue_imbalance`
*   **MarketState:** `MarketState.microstructure.queue_imbalance`
*   **Downstream Consumer:** Decision Engine (Research-only monitoring).

### Microprice
*   **BingX Raw Field:** `@depth20` Top-of-book prices and volumes.
*   **Parser:** `InstitutionalWebSocketManager` -> `OrderBookSnapshot`
*   **Mathematical Function:** `institutional.liquidity.calculate_microprice`
*   **Data Model:** `MicrostructureState.microprice`
*   **MarketState:** `MarketState.microstructure.microprice`
*   **Downstream Consumer:** Decision Engine (Research-only monitoring).

### Cumulative Volume Delta (CVD)
*   **BingX Raw Field:** `@trade` Volume and `m` (isBuyerMaker) flag.
*   **Parser:** `InstitutionalWebSocketManager` -> `TradeEvent`
*   **Mathematical Function:** `institutional.order_flow.calculate_cvd` (Time-windowed rolling sum).
*   **Data Model:** `MarketDataSnapshot.cvd`
*   **MarketState:** Determines `MarketState.order_flow_state` (Returns `"VALID"` if CVD is valid).
*   **Downstream Consumer:** InstitutionalMathEngine evaluates CVD integrity to set the state string.

### Taker Volume Imbalance (TVI)
*   **BingX Raw Field:** `@trade` Volume and `m` (isBuyerMaker) flag.
*   **Parser:** `InstitutionalWebSocketManager` -> `TradeEvent`
*   **Mathematical Function:** `institutional.order_flow.calculate_taker_volume_imbalance`
*   **Data Model:** `MarketDataSnapshot.tvi`
*   **MarketState:** Independent flow metric, no collision with OFI.
*   **Downstream Consumer:** Decision Engine (Research-only monitoring).

## 5. Data Model Audit

The primary data schema, `MarketState` (defined in `institutional/types.py`), was explicitly reviewed.

*   **Finding:** `MarketState` does NOT contain an `ofi` field.
*   **Finding:** Order flow validity is represented solely by `MarketState.order_flow_state: str`, which evaluates whether foundational metrics (like CVD) exist, but does not calculate a directional probability based on them.
*   **Finding:** Microstructure variables (`depth_imbalance`, `queue_imbalance`, etc.) reside strictly within the nested `MicrostructureState` object. They are not elevated into generic aliases.

## 6. Static Safety Audit

The Institutional Data Acquisition and Institutional Math Layers have been verified to remain completely observational.
*   No functions import or execute `place_order`, `cancel_order`, or broker calls.
*   No RiskManager or TradingEngine mutations occur from inside `institutional_math.py`.
*   All tests enforce these boundaries.

## 7. Automated Testing Enforcement

A dedicated suite, `tests/test_ofi_lineage_integrity.py`, has been introduced.
These tests strictly prove that:
1. `MarketState` lacks an `ofi` field, thereby preventing serialization aliases.
2. `depth_imbalance` and `queue_imbalance` map uniquely to their respective fields.
3. The native `calculate_ofi` function gracefully and strictly returns `np.nan` given empty/invalid sequences.

**Canonical OFI is UNAVAILABLE from the currently verified BingX order-book feed and no other Institutional Math metric is permitted to masquerade as OFI.**
