# Phase 7.6: Stage B Data Acquisition Specification (EXP-S3 Corrected)

## 1. Scope & Pre-Acquisition Audit
Before bulk acquisition of the 1m datasets, we must verify the actual historical availability and timestamp semantics of the authoritative Binance sources for a core sample (`BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `XRPUSDT`, `BNBUSDT`). 

**Pre-Acquisition Verification:**
- Verify exact source paths for `klines`, `fundingRate`, and `openInterestHist`.
- Validate that `openInterestHist` provides timestamps representing the *close* or *publication* time, ensuring no backward-filling.
- Validate that `fundingRate` timestamps cleanly distinguish the calculation/publication time from the settlement interval.

## 2. Mandatory Causal Alignment (Anti Look-Ahead)
- **OI Forward-Fill Rule:** A 5m Open Interest observation stamped at `08:05:00` becomes available for trading decisions exactly at `08:05:00`. It is merged to the `08:05` 1m kline and forward-filled to `08:06, 08:07...`. It must NEVER be mapped to `08:04` or earlier. An automated test will assert `t_OI <= t_kline` along with: future OI rejection, exact timestamp inclusion, large OI gaps, and missing OI handling.
- **Funding Look-Ahead Rule:** The `funding_rate` feature evaluated at `07:45:00` must strictly be the rate that was historically published *at or before* `07:45:00` (e.g., the 00:00:00 rate). If historical predictions are unavailable, only the last settled realized rate may be used as the feature. Future 8h settlement values cannot be leaked into predictive features.

## 3. Required Sources & Columns
| Dataset | Source (Binance Vision) | Granularity | Required Columns |
|---------|-------------------------|-------------|------------------|
| **Price/Volume** | `data/futures/um/monthly/klines/` | 1-minute | `open_time`, `open`, `high`, `low`, `close`, `volume`, `quote_volume`, `taker_buy_quote_volume` |
| **Funding** | `data/futures/um/monthly/fundingRate/` | 8-hour | `calc_time`, `funding_rate`, `symbol` |
| **Open Interest** | `data/futures/um/monthly/openInterestHist/` | 5-minute | `timestamp`, `sumOpenInterest`, `sumOpenInterestValue` |

## 4. Date Range & Missing Data
- **Start:** `2021-01-01`
- **End:** `2024-05-01`
- **Missing Data Policy:** If funding or OI is historically unavailable for a symbol-month on Binance Vision, the symbol is explicitly masked (`NaN`). We will NOT silently substitute zero or interpolate across vast structural gaps.

## 5. Efficient Acquisition & Partitioning
- The engine will evaluate `universe_artifact_v1.parquet`. Monthly ZIPs will be queued only for `(symbol, year_month)` pairs where `eligible = True`.
- A 14-day warmup buffer will be fetched prior to the first eligible month to seed the 7d funding Z-score and 14d OI percentile calculations.
- Parquet partitions will enforce the memory-safe disk layout: `data/raw/binance/futures/um/klines_1m/symbol=X/year=Y/`.

## 6. Expected Footprint
- **Symbols:** Dynamically scaled (Median 88, Max 216).
- **Row Count:** ~152 million rows (Klines), ~30 million rows (OI), ~1 million rows (Funding).
- **Storage Requirement:** ~3.0 GB of highly compressed partitioned Parquet files.

## 7. Data Integrity & Manifests
- Use Binance archive CHECKSUM files wherever available.
- Record: source URL, archive filename, checksum, download timestamp, parser version, dataset version.
- Generate a machine-readable acquisition manifest during Stage B download.
