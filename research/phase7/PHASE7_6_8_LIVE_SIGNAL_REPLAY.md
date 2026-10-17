# PHASE 7.6.8 — LIVE SIGNAL REPLAY & PARITY TEST (HARDENED)

## 1. Objective: Equivalence vs Parity
It is vital to draw a mathematical distinction between two concepts:
- **`FORMULA_REPLAY_EQUIVALENCE`**: Proves that given identical inputs, the live logic computes the exact same signal as the research logic.
- **`BINGX_DATA_SEMANTIC_PARITY`**: Proves that the actual bytes of data streaming from BingX represent the exact identical economic meaning as the data archived by Binance Vision.

This replay test suite targets `FORMULA_REPLAY_EQUIVALENCE`. The semantic parity was audited manually in `PHASE7_6_8_BINGX_FEATURE_PARITY.md`.

## 2. Test Suite Implementation
The deterministic replay suite is implemented in:
`tests/test_s3_live_parity.py`

## 3. Test Scenarios Validated

| Scenario | Condition Tested | Result |
|----------|------------------|--------|
| **Normal Conditions** | Clean, uninterrupted data streams. | **PASS** (100% equivalence) |
| **Causal Timestamps** | Evaluates whether future observations leak into current signals via faulty truncation. | **PASS** (Strict `.merge_asof(direction='backward')` prevents future leakage). |
| **Clock Mismatch / Jitter** | Network payloads arriving at off-interval seconds (e.g., 10:05:07). | **PASS** (Causally matched to the subsequent 1m candle tick). |
| **Future Observation Rejection** | Forcing an observation timestamp backward. | **PASS** (Engine rejects observations if `receive_time > decision_time`). |
| **Missing OI / Stale OI** | A simulated 2-hour network failure where OI drops. | **PASS** (60-minute forward fill limit correctly masks the signal as explicitly `UNAVAILABLE` after 60 mins). |
| **Missing Intervals (Gaps)** | Poller downtime recovery. | **PASS** (No synthetic rows generated; gap enforced mathematically). |
| **Restart Recovery** | Simulates loading historical SQLite payload into the memory engine. | **PASS** |
| **Warmup Constraints** | Starting computation before the exact 14d+4h threshold. | **PASS** (Signal is structurally `NaN` and `UNAVAILABLE` until exact warmup is mathematically satisfied). |

## 4. Final Status
- **`FORMULA_REPLAY_EQUIVALENCE` = PASS**
- **`BINGX_DATA_SEMANTIC_PARITY` = PASS** (Validated via manual API audit).
- **`LIVE_WARMUP_REQUIRED` = 14 Days + 4 Hours** (Active polling time).
- **`MAX_OI_STALENESS` = 60 Minutes**.
- **`S3_LIVE_DATA_READY` = YES** (But structurally barred from trading until the 14-day institutional archival buffer is physically accumulated).
