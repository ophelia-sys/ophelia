# BINANCE DATA INTEGRITY

- candles: **17568**  (2026-06-01 00:00:00+00:00 -> 2026-07-31 23:55:00+00:00, UTC)
- duplicate timestamps: 0
- non-monotonic timestamps: 0
- missing 5m candles vs perfect grid: **0**
- invalid OHLC bars: 0
- non-positive prices: 0
- zero-volume bars: 0 | negative volume: 0

## Notes
- Full two-complete-month window retrieved from fapi/v1/klines.
- Partial-final-candle check: last bar 23:55 closes 00:00 -> complete.
