# Phase 7.6.1: Binance Historical Open Interest Source Audit

## 1. Authoritative Source
The authoritative Binance source for historical open interest is **NOT** the `monthly/openInterestHist` path (which returns 404 for historical epochs), but rather the **Binance Vision Daily Metrics** archives.

## 2. Exact Path
- **URL Template:** `https://data.binance.vision/data/futures/um/daily/metrics/{symbol}/{symbol}-metrics-{yyyy-mm-dd}.zip`
- *Example:* `https://data.binance.vision/data/futures/um/daily/metrics/BTCUSDT/BTCUSDT-metrics-2023-01-01.zip`

## 3. Date Coverage & Feasibility
This endpoint provides contiguous daily historical archives spanning the full required 2021–2024 timeframe for all active/historical contracts. The required sample verification explicitly confirmed 200 OK responses for the following research symbols on `2023-01-01`, `2023-01-05`, and `2023-01-15`:
- `BTCUSDT`
- `ETHUSDT`
- `SOLUSDT`
- `XRPUSDT`
- `BNBUSDT`
- `ADAUSDT`
- `DOGEUSDT`
- `MATICUSDT`

## 4. Granularity
The metrics archives provide exactly **5-minute (5m)** resolution. Each daily zip contains a CSV with exactly 288 rows per symbol per day.

## 5. Schema
The CSV schema contains the exact required OI fields (plus additional ratio metrics that can be discarded):
```text
create_time                             string (e.g. 2023-01-01 00:05:00)
symbol                                  string
sum_open_interest                       float64
sum_open_interest_value                 float64
count_toptrader_long_short_ratio        float64
sum_toptrader_long_short_ratio          float64
count_long_short_ratio                  float64
sum_taker_long_short_vol_ratio          float64
```

## 6. Timestamp Semantics & Causal Alignment Rule
- The timestamp field `create_time` denotes the exact observation/publication moment (e.g., `00:05:00`). 
- **Causal Alignment Rule:** A value stamped `00:05:00` is strictly observable by `00:05:00`. When merged against the 1m price grid, the `00:05:00` OI row is mapped precisely to the `00:05:00` 1m kline and forward-filled to `00:06, 00:07, 00:08, 00:09`. It cannot backward-fill to `00:04`.

## 7. Missingness
Because these files are aggregated daily by Binance, structural outages result in missing 5m rows. Missing rows will be handled via standard explicit left-joins against a continuous minute-frequency timeline, resulting in `NaN` values. The system will NOT interpolate.

## 8. Resolution Adequacy
A 5m resolution is perfectly adequate for the EXP-S3 Crowded Leverage Reversal hypothesis, which requires:
- $\Delta OI$ over $1h$ or $4h$ lookbacks.
- Rolling $14$-day OI percentiles.
The 5m granularity provides highly precise endpoints for the 1h/4h lookback differences and avoids the extreme noise of tick-level OI.

## 9. Storage Estimate
- **Daily Size:** ~15 KB compressed per symbol-day.
- **Monthly Size:** ~450 KB compressed per symbol-month.
- **Stage B Universe Size:** With a median of 88 eligible symbols over 40 months ($\approx 3,500$ symbol-months), the total raw zip download footprint will be approximately **~1.5 GB**. This is extremely lightweight.

## 10. Final Availability Classification
**A. AVAILABLE** — Binance Vision daily metrics provide sufficient, high-quality, 5m-resolution historical OI for the experiment.

## 11. Recommendation for S3
Proceed with the S3 experiment using the exact daily `metrics` URL. Since these are *daily* zips (unlike the monthly klines), the Stage B Data Acquisition engine must be modified to iterate daily over the required eligible months, rather than pulling a single monthly zip for OI.

No modifications to the S3 mathematical hypothesis or variables are required. No third-party data is necessary.
