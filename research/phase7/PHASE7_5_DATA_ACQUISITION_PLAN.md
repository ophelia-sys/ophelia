# Phase 7.5: Data Acquisition Plan (Stage B)

## 1. Acquisition Scope
The goal of Stage B is to download granular 1-minute `klines` ONLY for the symbol-months where a coin was definitively part of the `RESEARCH_UNIVERSE`.

- **Universe Definition:** We will rely on `data/processed/universe_artifact_v1.parquet`.
- **Date Range:** 2021-01-01 through 2024-05-01 (or as defined by research requirements).
- **Required Columns:** `open_time`, `open`, `high`, `low`, `close`, `volume`, `quote_volume`, `count`, `taker_buy_volume`, `taker_buy_quote_volume`.

## 2. Storage & Compute Estimates
Assuming a research universe whose median breadth is $N=50$ symbols (based on the Stage A output):
- **Rows per day per symbol:** 1,440
- **Total rows (50 symbols * 3.3 years):** ~86.7 million rows.
- **Estimated Raw CSV Size:** ~12 GB
- **Estimated Parquet Size:** ~2.5 GB

## 3. Partition Scheme (Memory-Safe Design)
Loading 86.7 million rows of highly granular market data into a single Pandas DataFrame risks OOM crashes during feature engineering. The Stage B dataset will be organized into a **Partitioned Parquet structure**.

**Directory Structure:**
```text
data/processed/research_universe_1m.parquet/
    symbol=BTCUSDT/
        year=2021/
            part-0000.parquet
        year=2022/
    symbol=ETHUSDT/
```
*Rationale:* This partition scheme natively supports Polars/Dask lazy-evaluation and DuckDB streaming reads. The workstation can execute cross-sectional joins chunk-by-chunk without loading the entire matrix into RAM.

## 4. Execution Workflow
1. **Identify Needed ZIPs:** The Stage B acquirer will group the `universe_artifact_v1.parquet` by `(symbol, year_month)`. If a symbol was `eligible=True` for *any* day in that month, the script queues the corresponding monthly 1m zip for download.
2. **Download & Checksum:** Files will be fetched from `data.binance.vision/data/futures/um/monthly/klines/{symbol}/1m/`. The script will extract the CSV, apply schema casting, and convert immediately to Parquet.
3. **Resume / Retry:** The script will check if a target partition file already exists and possesses a valid size. Failed network requests will retry 3 times with exponential backoff.
4. **Processing Time:** Estimated at 15-30 minutes on a standard broadband connection.

## 5. Storage / Backup
- **Primary Disk Requirement:** ~3 GB (after Parquet compression). The raw ZIPs and CSVs will be streamed into memory and discarded immediately, preventing temporary disk bloat.
- **Backup Strategy:** The processed dataset will remain strictly on the Research Workstation's primary NVMe drive. Since it is entirely deterministic and derived from public data, no cloud backup is required.

## 6. Next Steps
Do not commence this download until explicit authorization for Phase 7.4 EXP-S3 or similar cross-sectional experiment is granted.
