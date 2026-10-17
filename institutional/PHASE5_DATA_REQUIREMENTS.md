# PHASE 5: DATA REQUIREMENTS

To execute the Phase 5 Quantitative Research Specification without compromising the historical-vs-live boundary, we must identify the exact dataset requirements necessary to reconstruct the approved P0 and P1 research candidates.

## 1. Existing Data (Satisfied)
- **Canonical `1m` Binance UM Klines** (2022-01-01 to 2023-12-31) for 6 symbols.
- **Derived Timeframes** (`3m`, `5m`, `15m`, `1h`, `4h`) deterministically aggregated from the 1m canonical dataset.

## 2. Minimum Additional Historical Data Required

To research Derivatives metrics and robust Volume Profile, the following additional public datasets from Binance Vision are required. Do NOT download these yet.

### A. Open Interest (OI)
- **Source**: Binance Futures API (`/futures/data/openInterestHist`) or Vision Dumps.
- **Frequency**: 5-minute resolution is standard for historical dumps.
- **Symbols**: BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, ADAUSDT.
- **Timeframe**: 2022-01-01 to 2023-12-31.
- **Justification**: Essential for identifying leverage accumulation, crowding, and regime changes.

### B. Funding Rates
- **Source**: Binance Futures API (`/fapi/v1/fundingRate`) or Vision Dumps.
- **Frequency**: 8-hour boundaries.
- **Symbols**: BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, ADAUSDT.
- **Timeframe**: 2022-01-01 to 2023-12-31.
- **Justification**: Essential for identifying structural directional bias and market positioning.

### C. Trade-Level Data (Optional / Research Only)
- **Source**: Binance Vision Trades (`/data/futures/um/monthly/trades`).
- **Frequency**: Tick-by-tick.
- **Justification**: `1m` klines provide `taker_buy_volume`, allowing calculation of 1m net Cumulative Volume Delta (CVD). If 1m resolution CVD proves insufficiently predictive due to intra-candle cancellation, tick-level trade data will be required to calculate TVI (Tick Volume Indicator) and tick-level absorption.
- **Status**: Deferred. Evaluate 1m-CVD first before initiating massive tick-level downloads.

## 3. Data Strict Rejections

The following datasets are explicitly rejected for the intraday predictive research phase:
- **Orderbook (L2) Snapshots**: ~10TB+ historical requirement. Economically unviable to store/process. Live execution relies on real-time WS streaming, but we cannot reconstruct depth imbalance / OFI historically.
- **GEX / Gamma Walls**: Primarily SPX/equity structures. Crypto options data is fragmented (Deribit dominated) and irrelevant to the strict intraday horizons (1m - 4h) of perpetual futures trading.
- **CFTC COT Reports**: Weekly frequency. Meaningless for intraday (minutes to hours) statistical prediction.

## 4. Normalization and Alignment Strategy

When the required data (OI, Funding) is eventually downloaded:
1. It must be forward-filled (`ffill`) strictly to the canonical 1m timestamps.
2. It must be saved in Parquet format aligning with the dataset provenance rules established in the Historical Data phase.
3. No future-peeking during alignment. A funding rate published at 08:00:00 must only become available at the 08:00:00 index, maintaining causal integrity.
