# PHASE 6 FULL REGENERATION REPORT

## 1. Dataset Scope
- **Symbols**: BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, ADAUSDT, XRPUSDT
- **Timeframe**: 1m
- **Date Range**: 2022-01-01 through 2023-12-31

## 2. Input Sources
- **Raw directory**: `data/raw/`

## 3. Timestamp Contract
- **Timezone**: Strict UTC
- **Resolution**: Integer Unix milliseconds
- **Ordering**: Monotonically ordered within symbol
- **Causality**: `oi_timestamp <= candle_timestamp` (Backward `merge_asof`)

## 4. Code Correction Used
```python
dt = pd.to_datetime(df['create_time'], utc=True, format='mixed').dt.tz_convert(None)
df['timestamp'] = (dt - pd.Timestamp('1970-01-01')) // pd.Timedelta('1ms')
```

## 5. Symbols & Timeframes
- **Symbols**: BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, ADAUSDT, XRPUSDT
- **Timeframes**: 1m

## 6. Global Stats
- **Total Kline Rows**: 6,292,800
- **Total OI Rows**: 1,261,404
- **Total Merged Rows**: 6,292,800
- **Total Future Join Violations**: 0

## 7. Symbol Breakdown
### BTCUSDT
- **Match Rate**: 100.00%
- **Duplicate OI Removed**: 0
- **DeltaOI Statistics**:
  - Mean: -0.001
  - Std: 370.713
  - Min/Max: -124575.047 / 124739.933
  - Unique Values: 173796
  - Missing Pct: 0.00%
- **Causal Violations**: 0

### ETHUSDT
- **Match Rate**: 100.00%
- **Duplicate OI Removed**: 0
- **DeltaOI Statistics**:
  - Mean: 0.288
  - Std: 3162.998
  - Min/Max: -895509.619 / 895388.367
  - Unique Values: 206149
  - Missing Pct: 0.00%
- **Causal Violations**: 0

### SOLUSDT
- **Match Rate**: 100.00%
- **Duplicate OI Removed**: 0
- **DeltaOI Statistics**:
  - Mean: 3.898
  - Std: 20002.669
  - Min/Max: -5721476.000 / 5735386.000
  - Unique Values: 46220
  - Missing Pct: 0.00%
- **Causal Violations**: 0

### BNBUSDT
- **Match Rate**: 100.00%
- **Duplicate OI Removed**: 0
- **DeltaOI Statistics**:
  - Mean: 0.278
  - Std: 2478.405
  - Min/Max: -750904.410 / 750593.430
  - Unique Values: 155563
  - Missing Pct: 0.00%
- **Causal Violations**: 0

### ADAUSDT
- **Match Rate**: 100.00%
- **Duplicate OI Removed**: 0
- **DeltaOI Statistics**:
  - Mean: 40.677
  - Std: 664914.698
  - Min/Max: -221777356.000 / 220956819.000
  - Unique Values: 182967
  - Missing Pct: 0.00%
- **Causal Violations**: 0

### XRPUSDT
- **Match Rate**: 100.00%
- **Duplicate OI Removed**: 0
- **DeltaOI Statistics**:
  - Mean: 131.459
  - Std: 1273630.802
  - Min/Max: -414166130.900 / 414037241.300
  - Unique Values: 207567
  - Missing Pct: 0.00%
- **Causal Violations**: 0

## 8. Integrity Results
- **Timestamp Integrity**: Integer milliseconds, monotonically ordered, correct scaling.
- **OI Integrity**: Meaningful DeltaOI variability, no constant value collapse, overlaps candle range.
- **Causal Integrity**: 100% compliant (`oi_timestamp <= candle_timestamp`).
- **Symbol Isolation**: Checked structurally via individual generation.

## 9. Deliverables
- **Manifest**: `c:\Users\dopa.mine\Desktop\ophelia\data\processed\v2_fixed_timestamp/MANIFEST.json`
- **Files Created**: 6 Parquet datasets in `c:\Users\dopa.mine\Desktop\ophelia\data\processed\v2_fixed_timestamp`
- **Files Preserved**: `binance_um_btcusdt_1m_v1` untouched. `data/raw` untouched.

## 10. Final Gate
READY_FOR_EMPIRICAL_VALIDATION