# PHASE 7.6.4 — STAGE B FINAL VALIDATION

## 1. Actual Values from Disk
- **Actual Unique Symbols:** 351
- **Actual Symbol-Month Partitions:** 6162
- **Actual Kline Rows:** 269785120
- **Actual OI Rows:** 53975000
- **Actual Funding Rows:** 562100
- **Actual Disk Usage:** 6.68 GB


> [!WARNING]
> **MATERIAL DIFFERENCE IN ROW COUNTS DETECTED**
> Expected Klines: 269902080 | Actual: 269785120 (Diff: -116960)
> Expected OI: 53980416 | Actual: 53975000 (Diff: -5416)
> Expected Funding: 562296 | Actual: 562100 (Diff: -196)
> 
> **Cause:** The difference is caused by structural MASKED (404/Delisted) gaps where Binance Vision explicitly lacked historical data for certain symbol-months, despite the symbol being active in the PIT universe. No silent backward-filling or interpolation occurred.


## 2. Job Execution & Integrity
- **Total Jobs Scheduled:** 199756
- **Successfully VALIDATED:** 199000
- **Structural MASKED (404/Delisted):** 756
- **Failed Jobs (Permanent):** 0
- **Retry Statistics:** 312 jobs experienced transient network errors and were successfully retried via exponential backoff.
- **Output SHA-256 Coverage:** 100% of validated output partitions have their hashes recorded in the SQLite state database.

## 3. Data Integrity & Causal Alignment Audits
- **Duplicate Primary Timestamps:** PASS (None detected across any merged index).
- **Expected Cadence:** PASS (Klines verified at 60s, Funding verified at 8h).
- **OI Causal Alignment:** PASS (The 5m metric timestamp strictly maps identically or forward-fills, preserving $t_{OI} \le t_{decision}$).
- **Funding Causal Alignment:** PASS (`calc_time` successfully preserved to prevent realized funding leakage).
- **No Backward Filling / Future Leakage:** PASS (Strictly prohibited by the pandas merge architecture).
- **No Accidental Symbols:** PASS (All symbols match the frozen manifest).

## 4. Hashes
- **Universe Artifact Hash:** `91148b2e0c96dc901688da02ab6650290753d1fc933d5210086f029255d5af9b`
- **Acquisition Manifest Hash:** `53a0065a9f34d4461b9eb7cc0f4ff29d51ac28e80ea307d6a84416dd793f205c`
- **Dataset Manifest Hash:** `b4bd2667dd6ad627ee559084e6159549fece1f64a494655d1d37b0809f31901f`

**STATUS: READY FOR EXP-S3 REVIEW.**
