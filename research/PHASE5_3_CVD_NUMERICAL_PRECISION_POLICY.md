# PHASE 5.3 CVD NUMERICAL PRECISION POLICY

## Rationale
During the processing of historical Binance `aggTrades` data, an issue was identified where certain altcoins (such as `XRPUSDT` and `ADAUSDT`) routinely failed the strict `1e-9` absolute error threshold for data conservation. 

This failure was not caused by missing rows, duplicate IDs, or structural data corruption. It was caused by standard IEEE 754 floating-point (`float64`) accumulation errors. Because these assets trade at fractions of a dollar, their nominal monthly token volumes are measured in the tens of billions. A `float64` sum of 14 billion tokens accumulates precision errors around `~2e-9`. Imposing a fixed absolute tolerance of `1e-9` across all assets—regardless of their nominal volume scales—will result in false-positive corruption flags for low-price, high-supply assets.

## The Scale-Aware Conservation Policy

To resolve this without weakening data integrity, the pipeline now implements a scale-aware floating-point conservation test. 

Conservation tolerance is a **numerical precision boundary, not a data quality waiver.**

### Rules

1. **Strict Float64 Usage**: All quantity, buy-volume, sell-volume, and signed-volume aggregations must be performed and maintained strictly in `float64`.
2. **Compensated Summation**: The final conservation sum is performed using `math.fsum()` to drastically reduce precision loss over the array iteration.
3. **Dynamic Tolerance**:
   ```python
   scale = max(abs(buy_volume), abs(sell_volume), abs(delta_volume), 1.0)
   tolerance = max(1e-10, scale * 1e-15)
   ```
   This ensures that the base strictness (`1e-10`) is applied for typical nominal volumes, but smoothly scales relative to massive absolute volumes with an extremely tight `1e-15` coefficient.
4. **Independent Temporal Checks**: The conservation invariant is asserted across multiple down-sampled aggregation paths (`1m`, `5m`, `15m`) against the raw total array sum.

## Hard Fail Conditions Remain Enforced

The floating-point tolerance applies *only* to volumetric summation precision. It **must not** mask genuine data anomalies. The following conditions remain strict, zero-tolerance **HARD FAILS** that will automatically quarantine the monthly dataset:

* Conflicting duplicate `agg_trade_id` fields
* Unexplained ID discontinuities or missing blocks
* Invalid, backward, or non-monotonic timestamps
* Invalid prices (≤0) or negative quantities
* Non-monotonic `agg_trade_id` sequences
* Volumetric discrepancy that exceeds the dynamic scale-aware tolerance

Any dataset quarantined by these failures must be subjected to a manual forensic audit and must not enter the production aggregation path until structurally repaired.
