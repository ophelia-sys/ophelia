# DATA AVAILABILITY MATRIX

This document outlines the current availability and status of institutional data sources from the BingX Perpetual Futures API as integrated into the Ophelia platform.

## Summary Matrix

| Data Type | Status | Transport | Endpoint / Topic | Quality Level | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **OHLCV** | AVAILABLE | REST | `/openApi/swap/v2/quote/klines` | VALID | Used for base mathematical calculations. Requires polling. |
| **Order Book** | AVAILABLE | REST & WS | `@depth20` | VALID | BBA (Best Bid/Ask) extracted from here. Feed provides gapped snapshots. Sequential diffs NOT supported. |
| **Trades** | AVAILABLE | WS | `@trade` | VALID | Aggressor side mathematically derived from `m` (isBuyerMaker). Fast stream. |
| **Open Interest** | AVAILABLE | REST | `/openApi/swap/v2/quote/openInterest` | VALID | Real payload verified. |
| **Funding Rate** | AVAILABLE | REST | `/openApi/swap/v2/quote/fundingRate` | VALID | Real payload verified. |
| **Liquidations** | UNAVAILABLE | - | `/openApi/swap/v2/quote/forceOrders` | UNAVAILABLE | Endpoint is invalid/returns error. Requires discovering a genuine liquidation stream. |

## Status Definitions

*   **AVAILABLE**: Endpoint verified, real payload received, schema validated, and currently integrated into the Institutional Data Engine.
*   **PARTIALLY_AVAILABLE**: Data exists but requires further transformation or is missing critical components (e.g., order book without high-frequency updates).
*   **UNAVAILABLE**: Endpoint invalid, undocumented, or fails verification. Ophelia assumes this data does not exist for the time being.

## Derived Metrics Availability

| Metric | Status | Reason |
| :--- | :--- | :--- |
| **Spread / Rel Spread** | AVAILABLE | Top-of-book correctly extracted from `OrderBookSnapshot` via `liquidity.py`. |
| **Queue Imbalance** | AVAILABLE | Top-of-book L1 bid/ask volume imbalance. |
| **Depth Imbalance** | AVAILABLE | Calculated reliably from 20 levels of `OrderBookSnapshot`. |
| **Microprice** | AVAILABLE | Instantaneous snapshot calculation derived from top-of-book volume weighted limits. |
| **Visible Impact (BPS)**| AVAILABLE | Walks the 20-level book to calculate VWAP against a requested notional size. |
| **Book Concentration**| AVAILABLE | Calculates HHI across the 20 visible levels of the snapshot. |
| **Book Slope** | AVAILABLE | Regression-based slope calculation (USDT/BPS) from the 20 visible levels. |
| **Amihud** | AVAILABLE | Properly sourced from OHLCV / Ticker. |
| **CVD / TVI** | AVAILABLE | Flawless windowed calculation verified in Phase 4.2. Deduplicated stream limits logic intact. |
| **OFI** | **UNAVAILABLE** | Requires strictly sequential order book events (diffs) with no gaps. BingX `@depth` streams send gapped snapshots only. Mathematically impossible to derive canonical OFI. |
| **Kyle Lambda** | RESEARCH_ONLY | Insufficient aligned sequential state storage for true event regression, but approximation possible via correlations. |
| **Liquidation Imbalance** | UNAVAILABLE | Raw liquidation data nonexistent via BingX API. |

## Mathematical Impact

Features that rely on `UNAVAILABLE` data (such as Liquidations and OFI) gracefully default their data quality to `INSUFFICIENT_DATA` or `UNAVAILABLE` as dictated by the Mathematical Engine's Corrective Phase contract. They do not crash the engine nor do they hallucinate inputs.
