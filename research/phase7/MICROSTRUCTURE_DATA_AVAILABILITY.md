# Microstructure Data Availability
**Scope:** High-Frequency Order-Book Data for Binance USD-M Futures (BTC, ETH, SOL, XRP, BNB)

## 1. Tick-Level Depth (Order Book Incremental Updates)
**Status:** **PARTIALLY_AVAILABLE / RESEARCH_ONLY**
Binance provides real-time tick-level depth via WebSocket (`<symbol>@depth`), but **does not natively host complete historical tick-by-tick L2 update logs** for public download via Binance Vision.
Historical tick-level reconstruction requires either:
1. Live capture and local storage of the WS stream + REST snapshots.
2. Sourcing from paid third-party historical tick data vendors (e.g., Tardis.dev, Databento).

## 2. Depth Snapshots
**Status:** **PARTIALLY_AVAILABLE**
Binance Vision (`data.binance.vision`) hosts daily zip files containing periodic `bookDepth` snapshots. These are useful for static modeling but do not perfectly replicate continuous tick-level event flow.

## 3. Best Bid / Ask (bookTicker)
**Status:** **AVAILABLE**
Historical BBA updates (`bookTicker`) are available on Binance Vision. This allows calculation of True Queue Imbalance (at L1) and Microprice, though it lacks deep book (L2+) visibility.

## 4. Trades / AggTrades
**Status:** **AVAILABLE**
Complete tick-level aggregated trades (`aggTrades`) are fully available historically. This permits calculation of trade flow, aggressive volume, tick-level CVD, and TVI.

### Verdict
For genuine historical deep-book (L2) research (like Book Slope and Depth Imbalance), data is currently **UNAVAILABLE** in the repository and requires establishing a dedicated live-capture data pipeline or a third-party data purchase. L1 features (Microprice, L1 Queue Imbalance) can be researched using historical `bookTicker` data.
