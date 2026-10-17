# PHASE 7 DATA SEMANTIC AUDIT

## 1. Dataset Identity
- **Dataset Version**: v2_fixed_timestamp
- **Generation Timestamp**: 2026-08-12T04:03:01.916156
- **Symbols**: BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, ADAUSDT, XRPUSDT
- **Row Count**: 6292800

## 2. Data Dictionary
| column | meaning | unit | source | timestamp | formula | point-in-time safe | status |
|---|---|---|---|---|---|---|---|
| `timestamp` | Start of candle | ms (Unix UTC) | Kline API | exact | - | YES | VALID |
| `close_time` | End of candle | ms (Unix UTC) | Kline API | exact | - | NO (use timestamp) | VALID |
| `symbol` | Trading pair | string | Kline API | - | - | YES | VALID |
| `open` | First price in interval | Quote (USDT) | Kline API | interval | - | YES | VALID |
| `high` | Max price in interval | Quote (USDT) | Kline API | interval | - | YES | VALID |
| `low` | Min price in interval | Quote (USDT) | Kline API | interval | - | YES | VALID |
| `close` | Last price in interval | Quote (USDT) | Kline API | interval | - | YES (after close) | VALID |
| `volume` | Total base asset traded | Base (BTC/ETH) | Kline API | interval | - | YES | VALID |
| `quote_volume` | Total quote asset traded | Quote (USDT) | Kline API | interval | - | YES | VALID |
| `trades` | Number of trades | count | Kline API | interval | - | YES | VALID |
| `taker_buy_volume` | Base asset bought by taker | Base | Kline API | interval | - | YES | VALID |
| `taker_buy_quote_volume`| Quote asset bought by taker | Quote | Kline API | interval | - | YES | VALID |
| `aggressive_buy_volume` | Taker buy base | Base | Derived | - | `taker_buy_volume` | YES | VALID |
| `aggressive_sell_volume`| Taker sell base | Base | Derived | - | `volume - taker_buy_volume` | YES | VALID |
| `delta_v` | Net order flow | Base | Derived | - | `buy_vol - sell_vol` | YES | VALID |
| `ofi` | Order flow imbalance | - | - | - | LIVE_ONLY | NO (Not historical) | HISTORICALLY_UNAVAILABLE |
| `microprice` | Microprice | - | - | - | LIVE_ONLY | NO (Not historical) | HISTORICALLY_UNAVAILABLE |
| `oi_timestamp` | Open Interest timestamp | ms (Unix UTC) | Metrics API | exact | - | YES | VALID |
| `sum_open_interest` | Total Open Interest | Base (BTC/ETH) | Metrics API | exact | - | YES | VALID |

## 3. Open Interest Semantics
Binance UM Open Interest (`sum_open_interest`) is denominated in the **BASE ASSET** (e.g. BTC, ETH).
Because it is denominated in Base Asset, the absolute value of `DeltaOI` is NOT comparable across symbols.
A change of 1.0 in BTC is ~$40k, while in ADA it is ~$0.50.
**Conclusion**: `DeltaOI` MUST be normalized (e.g., as a percentage return or Z-score) or multiplied by price to evaluate USD flow before cross-asset comparison is valid.

## 4. Raw Data Distribution Audit
### BTCUSDT Distribution
- **Rows**: 1051200
- **Negative Prices**: 0 (0 expected)
- **High < Low**: 0 (0 expected)
- **Negative Volume**: 0 (0 expected)
- **Missing OI %**: 0.00%
- **OI Min/Max**: 0.0 / 170585.887

### ETHUSDT Distribution
- **Rows**: 1051200
- **Negative Prices**: 0 (0 expected)
- **High < Low**: 0 (0 expected)
- **Negative Volume**: 0 (0 expected)
- **Missing OI %**: 0.00%
- **OI Min/Max**: 0.0 / 1603183.186

### SOLUSDT Distribution
- **Rows**: 1044000
- **Negative Prices**: 0 (0 expected)
- **High < Low**: 0 (0 expected)
- **Negative Volume**: 0 (0 expected)
- **Missing OI %**: 0.00%
- **OI Min/Max**: 0.0 / 15795774.0

### BNBUSDT Distribution
- **Rows**: 1051200
- **Negative Prices**: 0 (0 expected)
- **High < Low**: 0 (0 expected)
- **Negative Volume**: 0 (0 expected)
- **Missing OI %**: 0.00%
- **OI Min/Max**: 0.0 / 978293.45

### ADAUSDT Distribution
- **Rows**: 1051200
- **Negative Prices**: 0 (0 expected)
- **High < Low**: 0 (0 expected)
- **Negative Volume**: 0 (0 expected)
- **Missing OI %**: 0.00%
- **OI Min/Max**: 0.0 / 371175672.0

### XRPUSDT Distribution
- **Rows**: 1044000
- **Negative Prices**: 0 (0 expected)
- **High < Low**: 0 (0 expected)
- **Negative Volume**: 0 (0 expected)
- **Missing OI %**: 0.00%
- **OI Min/Max**: 0.0 / 625277973.4

## 5. Timestamp / Point-In-Time Forensics
- **UTC integer milliseconds**: Verified.
- **Monotonicity**: Verified within symbols.
- **Causal Join**: `oi_timestamp <= timestamp` verified. No future leakage.

## 6. Resampling Audit
Higher timeframes (e.g. 5m, 15m, 1h) must aggregate using standard OHLCV rules.
Higher timeframe values are ONLY available at the `close_time` of the aggregated bar.

## 7. Missing Data / Gap Policy
- **Missing Candles**: Leave as gaps in time, or forward-fill `close` but set `volume=0`. We choose: do NOT forward fill by default, handle gaps explicitly in features.
- **Missing OI**: Forward-fill ONLY up to 15 minutes, otherwise NaN.
- **Never backward-fill**.
