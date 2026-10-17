# OPHELIA EXCHANGE DATA PROVENANCE
Phase 2.9B - Independent exchange-data validation Â· Generated 2026-08-22

## Acquisition

| item | BINGX (primary) | BINANCE (secondary cross-check) |
|---|---|---|
| endpoint | `https://open-api.bingx.com/openApi/swap/v3/quote/klines` | `https://fapi.binance.com/fapi/v1/klines` |
| symbol | SOL-USDT | SOLUSDT |
| contract | USD-M perpetual swap | USD-M perpetual futures |
| interval | 5m | 5m |
| requested window | 2026-06-01 00:00 -> 2026-08-01 00:00 UTC | same |
| API history horizon | 2026-07-08T04:32:22.382000+00:00 | n/a (full depth available) |
| delivered window | 2026-07-08T05:25:00+00:00 -> (excl.) 2026-08-01T00:00:00+00:00 | 2026-06-01T00:00:00+00:00 -> (excl.) 2026-08-01T00:00:00+00:00 |
| candles retrieved | 6847 (raw 6847, dup removed 0) | 17568 (raw 17568, dup removed 0) |
| pages fetched | 7 | 12 |
| retrieval completed | 2026-08-22T05:21:23.484237+00:00 | 2026-08-22T04:25:58.052047+00:00 |
| CSV sha256 | `23935353c306874694a1b0ae67542839931123c0714693ff826a6d88cc1b4cef` | `9e46cccf8585cd2865542ef63001cc388c1ee690edf9aa4e56ccb3c5ed30f018` |
| raw pages | C:\Users\dopa.mine\Desktop\ophelia\research\validation\exchange_10_4_two_months\raw\bingx_raw_pages.json | C:\Users\dopa.mine\Desktop\ophelia\research\validation\exchange_10_4_two_months\raw\binance_raw_pages.json |

## Method notes
- Pagination semantics were established empirically before bulk fetch:
  BingX v3 returns DESCENDING candles anchored at endTime with a hard cap of 1000 rows;
  fetcher uses forward endTime-anchored windows. Binance returns ascending klines,
  limit 1500.
- BingX v3 serves only ~45 days of kline history: June 2026 is unavailable from the
  official endpoint (v2 returns empty as well). The BingX sample is therefore its
  maximal contiguous native window ending 2026-07-31 23:55 UTC.
- Raw responses are preserved verbatim under `raw/`. No third-party aggregates,
  no scraping, no synthetic data.
