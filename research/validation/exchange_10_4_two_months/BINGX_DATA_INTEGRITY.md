# BINGX DATA INTEGRITY

- candles: **6847**  (2026-07-08 05:25:00+00:00 -> 2026-07-31 23:55:00+00:00, UTC)
- duplicate timestamps: 0
- non-monotonic timestamps: 0
- missing 5m candles vs perfect grid: **0**
- invalid OHLC bars: 0
- non-positive prices: 0
- zero-volume bars: 0 | negative volume: 0

## Notes
- API horizon: BingX v3 klines serve only ~45 days; June unavailable (see BINGX_RAW_MANIFEST.json).
- Missing-candle count is measured from BingX's own first available bar, not from Jun 1.
- Partial-final-candle check: last bar 23:55 closes 00:00 -> complete (window ends at month boundary).
