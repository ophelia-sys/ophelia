# Official API & Data Contract Verification

**Phase:** Phase 10 (Multi-Venue Architecture)  
**Date:** 2026-10-02  
**Verification Method:** Direct live REST probe from Local Workstation & VPS (`15.235.193.47`)

---

## 1. Verified Binance USD-M Perpetual Futures Contract (`https://fapi.binance.com`)

| Endpoint | Method | Latency (ms) | Observed Status | Key Fields & Semantics |
| :--- | :--- | :--- | :--- | :--- |
| `/fapi/v1/time` | GET | 264.85 | `OK` | `serverTime` (epoch ms, e.g. 1790935480560) |
| `/fapi/v1/exchangeInfo` | GET | 1102.11 | `OK` | 920 contracts. `symbol` (e.g. `BTCUSDT`), `contractType` (`PERPETUAL`), `status` (`TRADING`), `pricePrecision`, `quantityPrecision`, filters: `LOT_SIZE` (`minQty`, `stepSize`), `MIN_NOTIONAL` (`notional`) |
| `/fapi/v1/klines` | GET | 239.09 | `OK` | Array format: `[0: open_time, 1: open, 2: high, 3: low, 4: close, 5: volume, 6: close_time, 7: quote_volume, 8: trade_count, 9: taker_buy_volume, 10: taker_buy_quote_volume, 11: ignore]` |
| `/fapi/v1/aggTrades` | GET | 197.99 | `OK` | `[{"a": agg_trade_id, "p": price, "q": qty, "f": first_id, "l": last_id, "T": timestamp_ms, "m": is_buyer_maker}]` |
| `/fapi/v1/depth` | GET | 203.44 | `OK` | `{"lastUpdateId": ..., "E": event_time, "T": trans_time, "bids": [[price, qty], ...], "asks": [[price, qty], ...]}` |
| `/fapi/v1/fundingRate` | GET | 205.61 | `OK` | `[{"symbol": "BTCUSDT", "fundingRate": "...", "fundingTime": ..., "markPrice": "..."}]` |
| `/fapi/v1/openInterest` | GET | 199.00 | `OK` | `{"symbol": "BTCUSDT", "openInterest": "...", "time": ...}` |
| `/fapi/v1/premiumIndex` | GET | 213.09 | `OK` | `{"symbol": "BTCUSDT", "markPrice": "...", "indexPrice": "...", "lastFundingRate": "..."}` |

### WebSocket Streams (`wss://fstream.binance.com/ws` / `/stream?streams=`)
- Kline Stream: `<symbol>@kline_1m` -> `{"e":"kline","E":...,"s":"BTCUSDT","k":{"t":open_time,"T":close_time,"s":"BTCUSDT","i":"1m","o":open,"c":close,"h":high,"l":low,"v":vol,"n":trades,"x":is_closed,"q":quote_vol,"V":taker_buy_vol}}`
- AggTrade Stream: `<symbol>@aggTrade` -> `{"e":"aggTrade","E":...,"s":"BTCUSDT","a":...,"p":...,"q":...,"T":trade_time,"m":is_buyer_maker}`
- Depth Stream: `<symbol>@depth20@100ms` -> Top 20 bids/asks pushed every 100ms.

---

## 2. Verified BingX Swap V2 Contract (`https://open-api.bingx.com`)

| Endpoint | Method | Latency (ms) | Observed Status | Key Fields & Semantics |
| :--- | :--- | :--- | :--- | :--- |
| `/openApi/swap/v2/quote/contracts` | GET | 611.18 | `OK` | 1,239 contracts. `symbol` (e.g. `BTC-USDT`), `size`, `quantityPrecision`, `pricePrecision`, `tradeMinQuantity`, `tradeMinUSDT`, `maxLeverage`, `status` (`1`=Tradable) |
| `/openApi/swap/v2/trade/order` | POST | N/A | Mock Verified | User-scoped API Key + HMAC SHA256 signature (`timestamp`, `apiKey`, `sign`). Order placement strictly gated behind `TRADING_AUTHORITY = FALSE`. |

---

## 3. Versioning & Contract Identifiers

- `BINANCE_DATA_PROVIDER_VERSION = "BINANCE_USDM_V1"`
- `BINANCE_DATA_SCHEMA_VERSION = "BINANCE_CANDLE_SCHEMA_V1"`
- `CROSS_VENUE_BASIS_VERSION = "CROSS_VENUE_BASIS_V1"`
- `TIMESFM_CANDIDATE_SCHEMA_VERSION = "TIMESFM_CANDIDATE_V1"`
- `CONTRACT_DISCOVERY_TIMESTAMP = 1790935480560` (2026-10-02)
