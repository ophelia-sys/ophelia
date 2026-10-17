# PHASE 7.6.4 — FULL STAGE B ACQUISITION REQUIREMENT

## 1. Objective
To execute the frozen EXP-S3 Crowded Leverage Reversal protocol with valid statistical power, the complete 40-month, 216-symbol cross-sectional dataset defined by `universe_artifact_v1` must be acquired, parsed, strictly causally aligned, and saved to disk. 

## 2. Scope
- **Eligible Target:** 216 unique Binance Futures symbols defined by the frozen point-in-time universe artifact.
- **Time Range:** 2021-01-01 through 2024-05-01 (incorporating explicit 14-day trailing warmup windows).
- **Target Scale:**
  - `~152,000,000` rows of 1m Klines
  - `~30,000,000` rows of 5m Open Interest
  - `~1,000,000` rows of 8h Funding Rates
- **Estimated Footprint:** ~3.0 GB of highly partitioned Parquet files.

## 3. Mandatory Acquisition Architecture
Due to the sheer volume of network requests (over 10,000 monthly zip files for Klines/Funding and over 300,000 daily zip files for OI), the naive single-process Python acquirer is insufficient. The complete acquisition requires:

### A. Distributed/Chunked Job Queue
- The universe manifest must be segmented into chunks (e.g., 10 symbols per chunk).
- A stateful job tracker must record successful and failed monthly downloads, allowing resumable execution if the Binance API rate-limits the client or a transient network failure occurs.

### B. Memory-Safe Processing
- Zip files must be streamed, parsed into Pandas chunks, cast strictly into numerical types, and flushed to disk immediately. 
- In-memory concatenation of the entire 152M dataset is strictly prohibited.

### C. Validation Logging
- For every partition, a cryptographic SHA-256 hash of the resulting Parquet byte stream must be calculated and appended to the final manifest.
- Any structural 404s (e.g., Binance delisted a symbol's historical metrics) must explicitly write an empty mask marker to ensure no forward-filling logic accidentally bypasses missing data.

## 4. Next Steps
The Python script `stage_b_acquirer.py` must be upgraded to support stateful, resumable chunked execution. The user must manually run this script on a dedicated data node or authorize an unsupervised overnight run, as the total network I/O execution time will span several hours. 

Once the robust `dataset_manifest.json` with genuine SHA-256 checksums is generated, the S3 evaluation script can be safely re-run across the full cross-section.
