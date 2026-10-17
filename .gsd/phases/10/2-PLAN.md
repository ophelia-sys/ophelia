---
phase: 10
plan: 2
wave: 2
---

# Plan 10.2: Binance Primary Market-Data Foundation & Causal Candle Aggregation

## Objective
Build a clean, high-performance Binance market data ingestion and causal normalization layer:
- Ingestion of Binance USD-M Perpetual 1m klines, aggregate trades, and order book depth.
- Separate storage in `binance_raw_candles_1m` and `binance_derived_candles` in `control_plane/db.py` (zero mixing into BingX `candles`).
- Deterministic causal aggregation from closed 1m bars to 5m, 15m, 30m, 1h candles.
- Quality states: `VALID`, `PARTIAL`, `MISSING`, `STALE`, `DUPLICATE`, `OUT_OF_ORDER`, `DEGRADED`, `NOT_AVAILABLE`.
- Historical backfill engine covering research instruments (`BTCUSDT`, `ETHUSDT`, `SOLUSDT`).

## Context
- `control_plane/binance_data.py`
- `control_plane/db.py`
- `models/instrument.py`
- `.gsd/phases/10/CONTRACT_VERIFICATION.md`

## Tasks

<task type="auto">
  <name>Create Dedicated Binance Database Tables and Indices</name>
  <files>control_plane/db.py</files>
  <action>
    - Add `_init_binance_tables(conn)` in `control_plane/db.py`:
      - `binance_raw_candles_1m`: `(venue, venue_product, symbol, canonical_instrument_id, ts, open, high, low, close, volume, quote_volume, trade_count, taker_buy_volume, taker_buy_quote_volume, is_closed, data_quality, freshness, ingestion_ts)`
      - Primary key: `(venue, symbol, ts)`. Index on `(symbol, ts)`.
      - `binance_derived_candles`: `(symbol, canonical_instrument_id, resolution, ts, open, high, low, close, volume, quote_volume, trade_count, taker_buy_volume, source_count, data_quality, is_closed, ingestion_ts)`
      - Primary key: `(symbol, resolution, ts)`. Index on `(symbol, resolution, ts)`.
    - Provide query and persistence methods: `insert_binance_raw_1m()`, `get_binance_raw_1m()`, `insert_binance_derived_candles()`, `get_binance_derived_candles()`.
  </action>
  <verify>python -c "from control_plane import db; conn = db._connect(); cols = [r[1] for r in conn.execute('PRAGMA table_info(binance_raw_candles_1m)').fetchall()]; assert 'quote_volume' in cols; assert 'data_quality' in cols"</verify>
  <done>Dedicated Binance tables initialized with strict lineage and quality fields.</done>
</task>

<task type="auto">
  <name>Implement BinanceMarketDataProvider & Causal Aggregator</name>
  <files>control_plane/binance_data.py</files>
  <action>
    - Create `control_plane/binance_data.py` with:
      - `BinanceMarketDataProvider`: REST client for historical klines, aggTrades, depth, funding, and mark price.
      - `BinanceHistoricalBackfill`: Backfills 1m klines with pagination (limit=1000), rate limit handling, and continuity verification.
      - `CausalCandleAggregator`: Deterministically aggregates closed 1m bars into 5m, 15m, 30m, and 1h bars.
        - Rules: Requires exact count of closed 1m bars (5 bars for 5m, 15 for 15m, etc.).
        - Open is first bar open, High is max high, Low is min low, Close is last bar close, Volume is sum of volumes.
        - Forming bar marked `PARTIAL / NOT_CLOSED` and excluded from finalized derived history.
        - Flags missing bars with `MISSING` or `DEGRADED`, never fills with zero-price values.
  </action>
  <verify>python -c "from control_plane.binance_data import CausalCandleAggregator; agg = CausalCandleAggregator(); bars = [{'ts': i*60000, 'open': 100+i, 'high': 105+i, 'low': 95+i, 'close': 102+i, 'volume': 10.0, 'quote_volume': 1000.0, 'trade_count': 5, 'taker_buy_volume': 4.0, 'is_closed': True} for i in range(5)]; d = agg.aggregate_window(bars, '5m'); assert d['is_closed'] is True; assert d['volume'] == 50.0; assert d['open'] == 100.0; assert d['close'] == 106.0"</verify>
  <done>Causal aggregator produces exact OHLCV derived candles from closed 1m bars.</done>
</task>

<task type="auto">
  <name>Author Unit and Integration Tests for Binance Data Engine</name>
  <files>tests/test_binance_data_engine.py</files>
  <action>
    - Test 1m kline ingestion and schema validation.
    - Test causal aggregation across 5m, 15m, 30m, 1h windows.
    - Test out-of-order rejection, duplicate handling, and partial candle exclusion.
    - Test historical backfill pagination and continuity checks.
  </action>
  <verify>pytest tests/test_binance_data_engine.py -v</verify>
  <done>All Binance data tests pass with zero lookahead and strict quality validation.</done>
</task>

## Success Criteria
- [ ] Binance raw 1m data stored in dedicated table without venue confusion.
- [ ] Causal aggregation mathematically validated for 5m/15m/30m/1h.
- [ ] Backfill harness ready for historical data ingestion on BTC, ETH, SOL.
