# PHASE 7.6.4 — STAGE B EXECUTION PLAN (v2)

## 1. Exact Acquisition Scope (Frozen PIT Manifest)
The exact scope has been strictly generated from the frozen point-in-time `universe_artifact_v1` using `research/universe/generate_stage_b_manifest.py`. The resulting immutable contract is stored at `research/phase7/stage_b_acquisition_manifest.parquet`.
1. **Exact Job Count:** 199,756 HTTP zip requests
2. **Exact Symbol Count:** 351 unique historical symbols
3. **Exact Symbol-Month Count:** 6,162 contiguous blocks (including prepended 14-day warmup months where necessary)
4. **Expected Row Count:** 
   - Klines (1m): ~269,902,080 
   - Open Interest (5m): ~53,980,416 
   - Funding (8h): ~562,296 

## 2. Resource & Footprint Analysis (Research Workstation)
5. **Expected Storage / Final Partition Layout:** 
   - The final footprint will be strictly partitioned into Parquet by `symbol` and `year_month`.
   - **Total Parquet Size:** ~6.79 GB.
   - **Target Volumes:** `data/processed/research_universe_1m.parquet/`, `data/processed/research_oi_5m.parquet/`, `data/processed/research_funding.parquet/`.
6. **Expected Runtime:** ~1.5 to 2.5 hours (bottlenecked purely by Binance API latencies, averaging 30-50 requests per second at healthy adaptive limits).
7. **Expected Temporary Disk Peak:** 
   - **Memory/Disk Safety:** Archives are streamed, parsed chunk-by-chunk with strict dtype casting, written to Parquet, and then memory is immediately released. No full datasets are materialized in Pandas.
   - **Temporary Disk Peak:** < 250 MB at any given time.
   - *Conclusion:* The Research Workstation (current environment) has sufficient free disk and RAM to safely handle this footprint. 

## 3. Persistent State & Resumable Job Queue
The acquisition is orchestrated by a persistent SQLite database (`data/processed/stage_b_jobs.sqlite`). 
- **Tracking:** Every 199,756 job is tracked with fields: `job_id, symbol, dataset_type, period, url, status, attempt_count, last_error, http_status, bytes_downloaded, output_path, output_sha256, source_checksum_status, started_at, completed_at`.
- **States:** PENDING, DOWNLOADING, DOWNLOADED, PARSED, VALIDATED, COMPLETE, FAILED, MASKED.
- **Checkpointing:** State is updated atomically after every single job completes. A process crash allows instant, safe resumption without duplicating work.

## 4. Adaptive Concurrency & Telemetry
- **Dynamic Limits:** Concurrency starts at `DEFAULT_START = 20`. The engine evaluates successful request rates (200 OKs) and automatically ramps up to 40 → 60 → 80 → 120 → 160 → 200.
- **Rate-Limiting (429s):** If a `429 Too Many Requests` or sustained latency spike occurs, the engine exponentially backs off and automatically downgrades the concurrency limit.
- **Telemetry:** RPS, HTTP statuses, and total bandwidth are continuously monitored and logged.

## 5. Error Classification & Masking Strategy
All failures are rigorously classified to prevent silent errors:
- **404 Structural (Missing metrics from Binance):** Classified as `NOT_LISTED` or `DELISTED` / `SOURCE_GAP`. Marked as `MASKED`.
- **429 / 408 / 5xx / Connection Reset:** Trigger exponential backoff and job retry (up to max attempts).
- **Permanent Parse Failure (Corrupt Zip):** Marked as `FAILED`. Can be manually reviewed without deleting the entire dataset.

## 6. Checksum Integrity
8. **Source Checksum Availability:** 
   - `SOURCE_CHECKSUM = NOT_AVAILABLE` (To eliminate an additional 200k HTTP requests for `.CHECKSUM` files, Binance Vision hashes are bypassed).
   - **Data Quality:** The engine computes the SHA-256 hash of every generated Output Parquet partition. This ensures `OUTPUT_PARQUET_SHA256_VERIFIED` accurately records dataset immutability without falsely claiming source archival verification.

## 7. Next Steps
The robust acquisition architecture is fully built in `research/universe/stage_b_acquirer_v2.py`. 
Following the prompt constraints, the engine has **NOT** been started yet. After this plan is reviewed, the full dataset will be acquired, followed by execution of `research/universe/stage_b_validator.py` to produce `PHASE7_6_4_STAGE_B_FINAL_VALIDATION.md`. **EXP-S3 will not be executed.**
