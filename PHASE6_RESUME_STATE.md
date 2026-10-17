# PHASE 6 RESUME STATE

This file is specifically for the NEXT Antigravity session. It contains precise technical context that a new session can use to continue the work without relying on conversation memory.

**IMPORTANT:** The next session must treat this file as the authoritative continuation state, but it must still inspect the actual repository before making changes.

============================================================
## 1. PROJECT
============================================================

- **Repository:** `C:\Users\dopa.mine\Desktop\ophelia`
- **Project:** Ophelia trading/research system.
- **Current phase:** Phase 6 — Historical Empirical Validation / Data Expansion / OI Integration.
- **Live execution must remain isolated from all Phase 6 research work.**

============================================================
## 2. PREVIOUS VERIFIED BASELINE
============================================================

Record the last known test baseline and important commits/state that were actually verified.

Current known test progression:
- Phase 5D.3 baseline: 99 tests
- Phase 6 feature generation: 114 tests
- Phase 6 empirical validation foundation: 123 tests
- Backtest foundation: 130 tests
- Later statistical corrections: 132 tests

*Do NOT claim a number is currently passing unless the next session verifies it.*

The previous Phase 5D.3 commit was:
`ecfcff0412f6fafb9faa9ef174293026cda62069`
Commit message:
`Phase 5D.3: finalize institutional data and websocket baseline`

*Nothing from the current expansion should be assumed committed.*

============================================================
## 3. FROZEN PHASE 6 MATHEMATICAL SPECIFICATION
============================================================

Record the currently frozen formulas.

**Robust Z-score:**
```text
Z_t = (X_t - Median(X_{t-W:t-1})) / max(MAD(X_{t-W:t-1}) * 1.4826, 1e-6)
```
*Current observation MUST NOT enter its normalization window.*

**Modified Amihud:**
```text
Illiq_t = abs(log(C_t / C_{t-1})) / (DollarVolume_t + 1e-6)
```

**Trade Delta:**
```text
DeltaV = BuyVolume - SellVolume
```

**Standardized Flow-Price Divergence:**
```text
Divergence_bull = Z_R - Z_DeltaV
```
*only evaluated when:* `Z_DeltaV < -tau`
*This feature is called:* Standardized Flow-Price Divergence (Do NOT call it proven absorption.)

**Scaled Microprice:**
```text
MI = 2 * (P_micro - P_mid) / (P_ask - P_bid)
```
*Microprice remains LIVE_ONLY unless genuine historical L1 data exists.*

**OI State Vector:**
```text
OI_State = [Z_DeltaOI, Z_R]
```
*Do NOT collapse it into a scalar.*

*FVG and Liquidity Pool state machines remain deterministic state trackers, not trading signals.*

============================================================
## 4. EXECUTION ISOLATION
============================================================

Phase 6 research must NOT modify or integrate into live execution.

Do NOT modify:
- `core/`
- `strategies/`
- `exchange/`

Specifically preserve isolation from:
- `core/decision_engine.py`
- `core/trading_engine.py`
- `core/scanner.py`
- `strategies/`
- adaptive_headroom
- EMA execution logic
- risk management
- order placement

*Research modules must never acquire execution authority.*

============================================================
## 5. HISTORICAL DATA FOUNDATION
============================================================

Permanent historical infrastructure created:
- `data/raw/`
- `data/normalized/`
- `data/manifests/`
- `research/data/`
- `research/backtest/`
- `research/phase6/`

Important modules include:
- `research/data/download_vision.py`
- `research/data/normalize_parquet.py`
- `research/data/validate_gaps.py`
- `research/backtest/engine.py`
- `research/backtest/data_loader.py`
- `research/backtest/cost_models.py`
- `research/backtest/portfolio.py`
- `research/phase6/events.py`
- `research/phase6/labels.py`
- `research/phase6/statistics.py`
- `research/phase6/power.py`
- `research/phase6/costs.py`
- `research/phase6/data_quality.py`
- `research/phase6/validation.py`
- `research/phase6/redundancy.py`
- `research/phase6/regimes.py`
- `research/phase6/pipeline.py`
- `research/phase6/reporting.py`

============================================================
## 6. ORIGINAL HISTORICAL DATASET
============================================================

Existing immutable dataset:
`binance_um_btcusdt_1m_v1`

Original scope:
- BTCUSDT
- 1-minute
- 2023-01-01 through 2023-03-31
- 129,600 rows

*This dataset must NOT be overwritten.*

============================================================
## 7. EXPANDED DATASET
============================================================

Target expanded dataset:
`binance_um_universe_1m_v2`

Universe:
BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, ADAUSDT, XRPUSDT

Date range:
2022-01-01 through 2023-12-31

Granularity:
1-minute

Expected/processed rows:
6,292,800

All six symbols had:
- 24/24 monthly kline archives
- 730/730 metrics daily archives

The dry-run reported:
~6.31 million expected rows
~0.27 GB raw ZIP
~0.22 GB normalized Parquet
~0.49 GB estimated storage

============================================================
## 8. HISTORICAL OI SOURCE
============================================================

The Binance metrics archive was inspected.

Actual schema:
`['create_time', 'symbol', 'sum_open_interest', 'sum_open_interest_value', 'count_toptrader_long_short_ratio', 'sum_toptrader_long_short_ratio', 'count_long_short_ratio', 'sum_taker_long_short_vol_ratio']`

OI timestamp:
`create_time`

Raw datatype:
`string`

Example:
```text
2022-01-01 00:00:00
2022-01-01 00:05:00
2022-01-01 00:10:00
```

Historical OI sampling frequency:
5 minutes

OI field:
`sum_open_interest`

The intended causal join is:
For candle timestamp $t$, select latest OI observation satisfying:
`OI_timestamp <= t`
using backward/as-of semantics.
*Never select future OI.*

============================================================
## 9. CRITICAL BUG DISCOVERED
============================================================

A serious timestamp-unit bug was discovered in:
`research/data/normalize_parquet.py`

Problematic implementation:
```python
df['timestamp'] = pd.to_datetime(df['create_time']).astype('int64') // 10**6
```

Under the current Pandas behavior, string timestamps were inferred at microsecond resolution.
Therefore:
`astype('int64')` returned microseconds.
Dividing by $10^6$ produced SECONDS.
OHLCV timestamps were milliseconds.

Result:
OHLCV: ~1.64e12
OI: ~1.64e9

The as-of join therefore technically satisfied `oi_timestamp <= candle_timestamp` but was catastrophically wrong.
Every OHLCV candle effectively matched the final OI observation from late 2023.

This produced approximately ~52–54 year apparent OI lag.
Observed:
- Min lag: 1,639,291,133,100 ms
- Mean lag: 1,670,885,250,102 ms
- Max lag: 1,702,363,073,100 ms

*This is INVALID.*

============================================================
## 10. CONSEQUENCE OF OI BUG
============================================================

Because all candles were assigned the same final OI value:
OI was constant.

Therefore:
`DeltaOI = 0` for essentially every row.

This produced:
`Z_DeltaOI = 0` for all valid observations.

All six symbols showed:
- Mean Z_DeltaOI = 0
- Std Z_DeltaOI = 0
- Min = 0
- Max = 0
with 501 initial NaNs.

*This is NOT a valid empirical OI result.*
All empirical results depending on this OI integration must be considered INVALID until the dataset is rebuilt.

============================================================
## 11. 501 WARMUP FINDING
============================================================

The 501 NaN warmup was traced as:
`DeltaOI[0] = NaN` because `diff()` has no predecessor.
Robust Z-score shifts the series by one.
With W=500, the first valid rolling window begins after the required 500 prior valid observations.
The existing audit calculated the first valid result at index 501.

*The next session must verify this against the actual implementation and tests rather than blindly trusting the report.*

============================================================
## 12. CORRECTIVE ACTION PROPOSED
============================================================

The proposed correction in `research/data/normalize_parquet.py` is:
```python
df['timestamp'] = pd.to_datetime(df['create_time'], utc=True).astype('datetime64[ms]').astype('int64')
```

This is intended to force the OI timestamp into Unix milliseconds explicitly.
*The next session MUST inspect the actual code and verify compatibility with the installed Pandas version before applying it. Do not blindly copy the correction.*

============================================================
## 13. REQUIRED FORENSIC TESTS
============================================================

Before rebuilding the complete 6-symbol dataset, add/verify tests for:
1. Seconds-vs-milliseconds detection.
2. Milliseconds-vs-seconds detection.
3. OI timestamp magnitude.
4. OI timestamp UTC conversion.
5. `OI <= candle timestamp`.
6. OI lag <= expected 5-minute sampling interval, subject to clearly documented boundary behavior.
7. Future OI cannot be selected.
8. OI values are not accidentally constant.
9. DeltaOI has non-zero variation where source data varies.
10. Symbol isolation.
11. OI observations do not bleed across symbols.
12. Data-gap handling.
13. Correct Robust Z-score warmup.
14. No modification to live execution.

*The next session should first test a small sample before rebuilding all 6.29 million rows.*

============================================================
## 14. CURRENT FORENSIC REPORT
============================================================

Permanent report created:
`PHASE6_OI_TIMESTAMP_FORENSIC_AUDIT.md`

It documents:
- raw schema
- timestamp bug
- 53-year lag
- constant OI
- zero DeltaOI
- zero Z_DeltaOI
- root cause
- proposed correction
- OI sampling frequency
- regression-test requirements

*Read this file before continuing.*

============================================================
## 15. CURRENT DATA STATUS
============================================================

The current expanded OI-normalized dataset is NOT TRUSTED.

Do NOT use it for:
- empirical validation
- statistical inference
- OI feature testing
- model training
- backtesting
- conclusions about alpha

The multi-asset validation run was TERMINATED after the OI anomaly was identified.

============================================================
## 16. PREVIOUS PHASE 6 EMPIRICAL RESULT
============================================================

The earlier 2022–2023 validation before the OI bug was discovered showed:
`POOL_CONFIRMATION` did NOT demonstrate statistically significant predictive power.

The observed 60-minute excess return was approximately: +2.06 bps
MDE approximately: 3.99 bps
Cohen's d approximately: 0.032
FDR-adjusted p-value was not significant.

The earlier conclusion was:
`POOL_CONFIRMATION` fails to demonstrate statistical significance.

*However, those results should be distinguished from the OI-integrated dataset. The OI bug does not automatically invalidate calculations that did not use OI, but the next session must verify exactly which pipeline version produced each result before relying on it. Do not silently mix datasets/results.*

============================================================
## 17. V2 POWER METHODOLOGY
============================================================

The corrected power methodology uses Cohen's d.
For a two-sided alpha=0.05 and target power=0.80:
```text
MDE = (Z_(1-alpha/2) + Z_beta) * SE
SE = baseline_std / sqrt(N_eff)
```
Previous 60m example:
- baseline std = 0.006282
- N_eff = 1946
- SE ≈ 0.0001424
- MDE ≈ 0.000399 ≈ 3.99 bps

The previous error where assumed effects were interpreted as raw decimal returns was corrected.
*Do not reintroduce that bug.*

============================================================
## 18. EVENT CLUSTERING / PURGE / EMBARGO
============================================================

Previous forensic audit found timestamp-unit bugs in these areas.
These have subsequently been corrected and verified in the V2 validation.

Required units:
- 5-minute clustering: 300,000 ms
- 60-minute purge: 3,600,000 ms
- 24-hour embargo: 86,400,000 ms

*The next session must still inspect the current implementation before relying on these claims. Never assume seconds and milliseconds are interchangeable.*

============================================================
## 19. HISTORICAL VALIDATION METHODOLOGY
============================================================

The intended frozen methodology is:
Data ingestion → feature generation → event generation → forward labels → primary event filtering → Train → Purge → Embargo → Test → baseline comparison → feature comparison → HAC/Newey-West → block bootstrap → FDR correction → power analysis → transaction costs → per-symbol analysis → cross-universe analysis → final classification.

Features must be classified separately as:
1. MATHEMATICALLY VALID
2. EMPIRICALLY SUPPORTED
3. ECONOMICALLY VIABLE

*Mathematical correctness does not imply alpha.*

============================================================
## 20. COST MODEL
============================================================

Current scenarios include:
OPTIMISTIC, REALISTIC, PESSIMISTIC, BINGX_SIMULATION

Always report:
- mean gross return/trade
- mean fees/trade
- mean slippage/trade
- mean funding/trade
- mean net return/trade
- cumulative net return

*Never call cumulative return "expectancy".*

============================================================
## 21. OI/L2 LIMITATIONS
============================================================

- Historical OI: AVAILABLE once timestamp integration is corrected.
- Historical OFI: LIVE_ONLY unless genuine sequential L1 order-book history exists.
- Historical Microprice: LIVE_ONLY unless genuine sequential L1 order-book history exists.

*Do not fabricate L1 data from OHLCV.*

============================================================
## 22. CURRENT EXACT STOPPING POINT
============================================================

The current work stopped AFTER:
- dry-run universe audit
- full historical download
- initial normalization
- OI anomaly discovery
- forensic investigation
- **IMPLEMENTATION OF OI TIMESTAMP FIX** (via `format='mixed'`)
- **OI MATHEMATICAL REFINEMENT (Definition A natively on 5m grid with strict zero-dispersion policy)**
- **REGRESSION TESTING** (`test_phase6_oi_definition_a.py`)
- **SMALL SAMPLE REBUILD** (BTCUSDT-1m-2022-01)
- **FULL 6-SYMBOL CANONICAL DATASET RECONSTRUCTION** (`binance_um_universe_1m_v2.parquet`, ~6.29 million rows)
- **INDEPENDENT RAW CROSS-CHECK VERIFICATION** (causal correctness proven, exact timestamp missingness measured)
- **ARCHIVING CORRUPTED DATASET** (v2 artifact moved to `research/data/forensic_corrupt/`)

The current next task is empirical validation.
The dataset has been explicitly tagged as:
CANONICAL_DATASET_VALIDATED

The Phase 6 Data Foundation is ~43% COMPLETE.

============================================================
## 23. DO NOT DO THESE THINGS
============================================================

Do NOT:
- use the corrupted OI dataset (archived in `research/data/forensic_corrupt/`)
- overwrite the original v1 dataset
- optimize Phase 6 thresholds blindly
- modify live trading logic
- fabricate OFI
- fabricate Microprice
- declare alpha
- trust a report merely because tests pass
- trust a causal inequality without checking timestamp units
- trust formatted 0.0000 values without inspecting raw distributions

============================================================
## 24. FIRST ACTION FOR NEXT SESSION
============================================================

The next Antigravity session MUST begin by reading:
- `PHASE6_RESUME_STATE.md`
- `PHASE6_CANONICAL_DATASET_REBUILD_REPORT.md`

Then inspect:
- `binance_um_universe_1m_v2.parquet` dimensions
- `institutional/normalization.py` parameters

Then report:
- CURRENT REPOSITORY STATE
- CURRENT STATUS (PHASE6_CANONICAL_DATASET_REBUILT_AND_VALIDATED)
- NEXT SAFE ACTION (Empirical Validation)

*Do NOT implement empirical models until that inspection is complete.*

============================================================
END OF RESUME STATE
============================================================
