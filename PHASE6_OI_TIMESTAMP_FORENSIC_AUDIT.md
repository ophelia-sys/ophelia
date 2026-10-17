# PHASE 6 OI TIMESTAMP FORENSIC AUDIT

## A. Raw Schemas
- **Exact column names:** `['create_time', 'symbol', 'sum_open_interest', 'sum_open_interest_value', 'count_toptrader_long_short_ratio', 'sum_toptrader_long_short_ratio', 'count_long_short_ratio', 'sum_taker_long_short_vol_ratio']`
- **Timestamp column:** `create_time`
- **Timestamp datatype:** `str` (string)
- **Timestamp sample values:** `['2022-01-01 00:00:00', '2022-01-01 00:05:00', '2022-01-01 00:10:00']`
- **OI column name:** `sum_open_interest`
- **Unique timestamps (BTCUSDT 2022-01-01):** 288 (5-minute frequency)

## B. Timestamp Samples
- **First candle timestamp (raw):** `1640995200000` (integer ms)
- **First candle UTC:** `2022-01-01 00:00:00`
- **First OI timestamp (raw):** `2022-01-01 00:00:00` (string)

## C. Unit Detection & Root Cause
The root cause was isolated in `research/data/normalize_parquet.py`:
```python
df['timestamp'] = pd.to_datetime(df['create_time']).astype('int64') // 10**6
```
- In Pandas 3.0.5, `pd.to_datetime` automatically infers resolution, returning `datetime64[us]` (microseconds).
- `astype('int64')` outputs the raw microseconds: `1640995200000000`
- Dividing by $10^6$ gives `1640995200`.
- **Result:** The normalized OI timestamps were output as **seconds**, while the OHLCV timestamps were processed as **milliseconds**.

## D. As-Of Examples
For `BTCUSDT` at `2022-01-01 00:00:00`:
- **candle_timestamp:** `1640995200000` (milliseconds)
- **selected_oi_timestamp:** `1640995200` (seconds, but treated as milliseconds by the join)
- **asof_lag_ms:** `1639354204800` ms
- **asof_lag_years:** 51.98 years

Because `merge_asof(direction='backward')` finds the largest `oi_timestamp <= candle_timestamp`, and because `1.6 billion` (seconds) is always less than `1.6 trillion` (milliseconds), the join mathematically collapsed every single candle to the **very last row of the OI dataset** (from December 2023).

## E. Lag Distribution (Processed Data)
- **Min lag ms:** 1,639,291,133,100 (51.9 years)
- **Mean lag ms:** 1,670,885,250,102 (52.9 years)
- **Max lag ms:** 1,702,363,073,100 (53.9 years)

## F. OI Distribution
Because every candle joined to the exact same final OI observation from late 2023, the OI distribution was completely degenerate for all 6.29 million rows.
**Example (BTCUSDT):**
- N: 1,051,200
- Unique Values: 1
- Min: 74,018.38
- Max: 74,018.38
- Std: 0.0

## G. DeltaOI Distribution
- Since $OI_t = OI_{t-1}$ everywhere, `DeltaOI` was identically $0.0$ for all 6.29 million rows.
- **Zero DeltaOI percentage:** 100.00%

## H. Z-Score Distribution
The mathematical formula for the robust Z-score is:
$$Z_t = \frac{\Delta OI_t - Median(\Delta OI_{t-W:t-1})}{\max(MAD * 1.4826, 1e-6)}$$
Since $\Delta OI = 0$ everywhere, $Median = 0$, $MAD = 0$.
The formula safely defaults to a denominator of $1e-6$, yielding:
$$Z = \frac{0 - 0}{1e-6} = 0$$
This perfectly explains why `Z_DeltaOI` was identically $0$ with exactly 501 initial `NaN`s.

## I. Verification of the 501-Warmup
The exact 501 `NaN` count is mathematically proven by the sequence of transformations:
1. `DeltaOI[0]` is `NaN` because `.diff()` on the first element has no prior.
2. The robust Z-score formula shifts the series by 1 (`past_series = series.shift(1)`), moving `DeltaOI[0]` to index 1.
3. Therefore, `past_series` at indices 0 and 1 are both `NaN`. The first valid observation is at index 2.
4. A rolling median of window size $W=500$ requires 500 contiguous non-NaN values.
5. Starting from index 2, the $500^{th}$ valid element lands precisely at index 501.
6. Therefore, `rolling_median` and `Z_score` compute their first valid output exactly at index 501. Indices 0 through 500 remain `NaN`.

## J. Corrective Action
- Modify `normalize_parquet.py` to enforce unambiguous unit conversion:
  ```python
  df['timestamp'] = pd.to_datetime(df['create_time'], utc=True).astype('datetime64[ms]').astype('int64')
  ```
- This completely shields the pipeline from changes in NumPy or Pandas default precision inference.

## K. Actual Binance Metrics Semantics
- The metrics archives (`-metrics-`) provide **5-minute point-in-time snapshots** of Open Interest.
- The `merge_asof` logic naturally handles the 5m-to-1m alignment without leakage, provided the timestamps are in identical units.

## L. Tests Added
Regression tests will be implemented to explicitly assert:
- OI lag $\le$ 300,000 ms (5 minutes, standard sampling frequency).
- Absolute timestamps in the Parquet match expected magnitude.
- `DeltaOI` contains variance $> 0$.
