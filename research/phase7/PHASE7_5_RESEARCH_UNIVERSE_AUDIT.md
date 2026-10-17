# Phase 7.5: Broad Binance Research Universe Audit

## 1. Data Availability & Breadth
An automated audit of the authoritative Binance Vision S3 repository reveals massive data availability for USD-M Perpetual futures.
- **Active USDT Perpetuals:** 654 symbols currently trading.
- **Total Historical Perpetuals (including delisted/expired):** 986 symbols.
- **Delisted/Dead Symbols:** 334 symbols (e.g., LUNAUSDT, SRMUSDT, GALBUSD, FTTUSDT).

**Conclusion on Breadth:** 
A research universe of 30+, 50+, or even 100+ liquid symbols is trivially achievable on Binance. The limitation is entirely computational rather than a lack of historical market availability.

## 2. Dataset Sizing & Compute Requirements
If we expand the canonical dataset to 1-minute `klines` (ignoring deep L2 data), the storage and memory requirements scale linearly.

**For a 100-Symbol Universe over 24 Months:**
- **Rows:** ~103,680,000
- **Raw CSV Size:** ~14.8 GB
- **Compressed Parquet Size:** ~3.0 GB
- **RAM Required for Pandas Processing:** ~30 GB

**For a 200-Symbol Universe over 24 Months:**
- **Rows:** ~207,360,000
- **Raw CSV Size:** ~29.6 GB
- **Compressed Parquet Size:** ~5.9 GB
- **RAM Required for Pandas Processing:** ~60 GB

### Infrastructure Recommendation
Given the ~30-60 GB RAM requirement for loading and transforming a 100-200 symbol universe, **historical research must remain on the Research Workstation**. A typical lightweight execution VPS (e.g., 4GB-8GB RAM) will immediately OOM (Out-of-Memory) if tasked with this level of cross-sectional backtesting.

## 3. Data Quality & Anomalies
When constructing a 100+ symbol universe, data quality degradation increases sharply outside the top 20 symbols. We must anticipate:
1. **Zero-Volume Periods:** Low-tier altcoins often exhibit consecutive 1-minute bars with zero trades.
2. **Missing Bars:** Binance API occasionally drops bars for illiquid pairs.
3. **Naming Changes & Contract Migrations:** e.g., LEND -> AAVE, or 1000SHIB formatting differences.

**Status:** `READY` for expansion, pending final specification approval.
