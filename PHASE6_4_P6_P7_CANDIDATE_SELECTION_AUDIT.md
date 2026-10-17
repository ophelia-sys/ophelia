# PHASE 6.4 - CANDIDATE SELECTION AUDIT (P6 & P7)

## Candidate Discovery
A repository and data inventory scan was conducted across `data/raw`, `data/normalized`, `data/processed`, and `research/` to identify potential fast-track orthogonal feature families that satisfy the strict data-cost requirements (no >10GB downloads, no >2 hours ingestion).

### P6: Funding / Perpetual Positioning Pressure
- **Local Data Available?** YES.
- **Exact Source:** `data/raw/positioning/funding/` containing Binance public data monthly zip archives (e.g., `ADAUSDT-fundingRate-2022-01.zip`).
- **Historical Coverage:** Complete 2022-2023 for all 6 primary symbols (BTCUSDT, ETHUSDT, BNBUSDT, ADAUSDT, SOLUSDT, XRPUSDT).
- **Estimated Download Size:** 0 bytes (Already exists locally).
- **Expected Processing Time:** < 5 seconds. Data is extremely small (<1KB per file).
- **Permanent Storage Size:** < 5 MB.
- **Selection Reason:** Satisfies the orthogonality requirement (structurally distinct from trade-flow CVD). Natively captures the market's bias/pressure. Zero cost data-engineering gate passed.

### P7: OHLCV-Derived Volume / Price Acceptance Proxies
- **Local Data Available?** YES.
- **Exact Source:** `data/normalized/v2_fixed_timestamp/` containing pre-processed `BASE` 5m OHLCV.
- **Historical Coverage:** Complete 2022-2023 for all 6 primary symbols.
- **Estimated Download Size:** 0 bytes (Already exists locally).
- **Expected Processing Time:** < 10 seconds. Calculated entirely in-memory using vectorized Pandas operations over the `BASE` DataFrame.
- **Permanent Storage Size:** 0 bytes (computed on-the-fly or stored ephemerally in standard experiment DataFrame).
- **Selection Reason:** Satisfies orthogonality against raw CVD by contextualizing volume with price levels (VWAP deviations, volume concentration). Data is already parsed and aligned, meaning zero ingestion cost. 

## Secondary Candidates Rejected
- **Order-Book Imbalance (OFI) / Microprice / Liquidity:** Rejected due to massive historical data requirements (Level-2 Orderbook data is multi-terabyte for 24 months and not currently available locally).

## Conclusion
The chosen families for fast-track Phase 6.4 are:
- **P6:** LAST-KNOWN-AVAILABLE FUNDING (Positioning Pressure)
- **P7:** OHLCV-DERIVED VOLUME / PRICE ACCEPTANCE PROXIES

Both families satisfy the Data-Cost Gate and Orthogonality constraints. Proceeding to exact mathematical feature definitions.
