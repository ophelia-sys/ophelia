# DATASET ARCHITECTURE

The quantitative research lab relies exclusively on historical dataset files verified and preserved from Phase 6.

## Structure

Data is stored as standardized Parquet files to enforce strict typing and fast sequential access.

- `data/processed/v2_fixed_timestamp/BTCUSDT.parquet`
- Schema includes OHLCV, Taker Buy/Sell Volumes, Aggressive Volumes, Microprice, and Open Interest.

## Loader Constraints

`ResearchDataLoader` is strictly isolated:
- Prevents external API access during research experiments.
- Verifies dataset integrity via hash assertions (`time_hash` = `29952ebb` for BTCUSDT).
- Operates on deep copies to prevent in-memory mutation leakage.

## Leakage Prevention

- Purged Walk-Forward Cross Validation ensures chronologically stable splits.
- An embargo period (default: 60 candles) explicitly distances train sets from test sets to prevent target leakage due to horizon overlaps.
