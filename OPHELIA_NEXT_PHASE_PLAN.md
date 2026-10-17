# OPHELIA NEXT PHASE PLAN

## Objective
The primary objective of the next phase is to resolve the timestamp anomaly discovered during Phase 6 data expansion and build a reliable, forensically sound foundation for Open Interest (OI) integration and subsequent ML empirical validation.

Based on the actual repository evidence, Phase 4 is genuinely complete and isolated, while Phase 6 is actively stalled by the `normalize_parquet.py` bug.

## 1. Immediate Corrective Actions
- **Target File**: `research/data/normalize_parquet.py`
- **Action**: Fix the `create_time` conversion bug. The current logic `df['timestamp'] = pd.to_datetime(df['create_time']).astype('int64') // 10**6` truncates the Unix timestamp to seconds. It must be corrected to produce milliseconds (e.g., `pd.to_datetime(df['create_time'], utc=True).astype('datetime64[ms]').astype('int64')`) so that it perfectly aligns with the OHLCV timestamps.

## 2. Implement Forensic Unit Tests
Before any data is rebuilt, a dedicated test suite (e.g., `tests/test_oi_timestamp_integrity.py` or similar in `research/phase6/`) must be written to explicitly guarantee:
1. **Resolution Matching**: `candle_timestamp` and `oi_timestamp` are strictly represented in milliseconds, preventing multi-decade offset errors.
2. **Causal Integrity**: `oi_timestamp <= candle_timestamp` (future data cannot be merged into current or past candles).
3. **Distribution Variability**: `DeltaOI` does not collapse to exactly zero because of a constant `asof` join target.
4. **Window Isolation**: `asof` merges do not bleed across different symbols.

## 3. Small-Scale Generation and Verification
- Regenerate a tiny slice of the dataset (e.g., one symbol, one month).
- Statistically analyze the resulting `DeltaOI` and `Z_DeltaOI` to ensure they have non-zero variance and represent genuine real-world observation streams.

## 4. Full Dataset Regeneration (Pending Approval)
- Once the localized tests pass and the small-scale generation proves the fix is mathematically sound, the full 6-symbol expanded dataset can be rebuilt.

## 5. Resumption of Phase 6 Validation (Pending Approval)
- Following dataset regeneration, the empirical validation of the historical dataset can resume. This includes power methodology verification, feature labeling, and statistical testing (FDR, Cohen's d).

## Explicit Restrictions for this Next Phase
- **DO NOT** execute the full historical data regeneration until the forensic tests pass.
- **DO NOT** alter the live `TradingEngine`, `DecisionEngine`, or any active `risk` component during this phase.
- **DO NOT** modify the Kronos integration logic until it can be empirically verified against the new, clean historical dataset.
- **DO NOT** rewrite the original v1 benchmark dataset.
