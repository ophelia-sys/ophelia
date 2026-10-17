# PHASE 6 OPEN INTEREST TIMESTAMP FORENSIC REPORT

## 1. Root Cause
The root cause of the historical data corruption was a datatype resolution mismatch in the pandas `to_datetime` parser. In Pandas 2.0+, parsing the `YYYY-MM-DD HH:MM:SS` string yielded a `datetime64[us]` (microseconds) array. Casting this to `int64` yielded integer microseconds since the epoch. The subsequent floor division by `1,000,000` (`// 10**6`) produced a timestamp in **seconds**, not milliseconds. 

## 2. Raw Timestamp Format
The Binance metrics CSV provides `create_time` as a string:
`2022-01-01 00:00:00` (Implicitly UTC).

## 3. Existing Conversion
```python
df['timestamp'] = pd.to_datetime(df['create_time']).astype('int64') // 10**6
```

## 4. Demonstrated Defect
- Raw value: `2022-01-01 00:00:00`
- Buggy output: `1640995200` (Seconds)
- Expected Kline output: `1640995200000` (Milliseconds)

When `merge_asof` (direction='backward') attempted to join Klines (e.g., `1640995200000`) against OI timestamps (`1640995200`), the OI timestamp was evaluated as essentially the year 1970. The join matched against random distant-future records or collapsed entirely, creating a multi-decade time displacement that broke the entire `DeltaOI` distribution.

## 5. Correct Timestamp Contract
The historical research layer formally enforces this explicit timestamp contract:
- **Timezone**: Strict UTC.
- **Datatype**: Integer Unix milliseconds since 1970-01-01 00:00:00.
- **Ordering**: Monotonically ordered within symbol.
- **Causality**: Free of impossible future values.

## 6. Corrected Implementation
In `research/data/normalize_parquet.py`, the conversion was rewritten to be robust against arbitrary Pandas backend resolutions:
```python
# Convert 'create_time' to explicit UTC and safely derive integer milliseconds
dt = pd.to_datetime(df['create_time'], utc=True, format='mixed').dt.tz_convert(None)
df['timestamp'] = (dt - pd.Timestamp("1970-01-01")) // pd.Timedelta('1ms')
```
*(Note: `format='mixed'` handling is enforced if applicable, though the raw data uses a standard string).*

## 7. Test Results
`tests/test_oi_timestamp_integrity.py` was created to evaluate the 10 forensic gates requested.
- **Passes**: 6/6 test functions (covering all 10 conditions).
- **Failures**: 0.

## 8. Small-Sample Results
A small-sample dataset was generated utilizing:
- **Symbol**: `BTCUSDT`
- **Period**: January 2022
- **Candle Rows**: 44,640
- **OI Metric Rows**: 8,928
- **Joined Rows**: 44,640
- **Match Rate**: 100.00%
- **Output File**: `data/processed/small_sample_btcusdt_2022_01.parquet`

## 9. Join Correctness
- **Min Candle TS**: `1640995200000` (2022-01-01 00:00:00)
- **Max Candle TS**: `1643673540000` (2022-01-31 23:59:00)
- **Min OI TS matched**: `1640995200000`
- **Max OI TS matched**: `1643673300000`
Timestamps align structurally at exactly the millisecond boundary.

## 10. DeltaOI Statistics
Delta OI no longer collapses to zero. The variance has returned to a mathematically healthy distribution:
- **Count**: 44,639 (first row NaN)
- **Mean**: 0.182
- **Std Dev**: 62.60
- **Min**: -2159.057
- **Max**: 921.624
- **Unique Values**: 8,824

## 11. Look-Ahead Audit
A strict check for future leakage (`oi_timestamp > timestamp`) inside the generated sample yielded:
- **Causal Leaks**: 0.

## 12. Files Changed
1. `research/data/normalize_parquet.py`
2. `tests/test_oi_timestamp_integrity.py` (New)

## 13. Files Intentionally Untouched
- `core/trading_engine.py`
- `core/decision_engine.py`
- `risk/risk_manager.py`
- `external/Kronos/provider.py`
- All live trading and execution logic.
- The original v1 benchmark datasets.

## 14. Final Gate
`READY_FOR_FULL_REGENERATION`
