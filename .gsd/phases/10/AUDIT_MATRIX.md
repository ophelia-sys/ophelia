# Phase 10: Multi-Venue System Audit Matrix & Architectural Assessment

**Phase:** Phase 10 (Multi-Venue Market Intelligence & TimesFM Trade Compatibility)  
**Date:** 2026-10-02  
**Operating Mode:** SHADOW ONLY (`TRADING_AUTHORITY = FALSE`)  
**Scope:** Complete repository audit across Local, VPS (`15.235.193.47`), and Android Application.

---

## 1. Comprehensive Component Audit Matrix

| Component | Current Implementation | Current Venue Assumption | Current Data Source | Current Timeframe | Current Dependencies | Required Change | Risk Level | Test Required | Production Impact |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CanonicalInstrument Model** | `models/instrument.py` | Single venue (`BINGX` default) | BingX Swap V2 contracts | N/A (Static metadata) | Python `dataclasses` | Extend to dual-venue schema: Binance USD-M & BingX Swap attributes, explicit mapping status enum (`UNRESOLVED`, `RESOLVED`, `TRADABLE_BOTH`, etc.) | LOW | Unit tests for cross-venue serialization, parsing, and equality | ZERO (additive fields preserve backward compatibility) |
| **InstrumentResolver** | `control_plane/instruments.py` | Single venue (`https://open-api.bingx.com/openApi/swap/v2/quote/contracts`) | BingX REST | N/A | `urllib`, `threading.Lock`, `config.py` | Add Binance USD-M exchangeInfo discovery (`https://fapi.binance.com/fapi/v1/exchangeInfo`), correlate by underlying asset (`BTC`, `ETH`, `SOL`, `XRP`, `GOLD`), cache with TTL | LOW | Dynamic discovery tests on Local & VPS for both venues | ZERO (read-only metadata caching) |
| **Market Data Persistence** | `control_plane/db.py` | Single venue (`candles` table with exchange='bingx') | BingX REST/WS | 1m | `sqlite3` WAL | Add dedicated `binance_raw_candles_1m` table and `binance_derived_candles` table with explicit lineage, sequence ID, quality states | LOW | Schema migration tests, index performance tests | ZERO (BingX `candles` table left untouched) |
| **Binance Data Ingestion & Stream** | Does NOT exist | Binance | Binance REST & WS | 1m raw | `urllib`, `websockets`, `json` | Implement `BinanceMarketDataProvider`, `BinanceHistoricalBackfill`, `BinanceRealtimeStream` with auto-reconnect and health states | MEDIUM | Backfill continuity tests, duplicate handling, reconnect tests | ZERO (runs in isolated worker thread/task) |
| **Causal Candle Aggregation** | Implicit in queries | Single venue | BingX raw | 1m -> 5m (ad-hoc) | SQL queries | Build deterministic causal 1m -> 5m/15m/30m/1h aggregator. Only closed 1m bars enter. Strict quality flags (`VALID`, `PARTIAL`, `STALE`) | MEDIUM | Exact OHLCV aggregation tests, missing candle rejection tests | ZERO (strictly additive) |
| **Microstructure Suite** | `control_plane/microstructure_engine.py` | Single venue (BingX spot & perp) | BingX trade & depth endpoints | Tick / event level | NumPy, SciPy, statsmodels | Build Binance trade flow (`aggTrades`) and order book depth (`depth20`) ingestion layer | LOW | Parity tests with existing 8 modules | ZERO (remains `RESEARCH_ONLY`) |
| **Retest & Setup State Machine** | `control_plane/retest_engine.py` | Single venue (reads BingX `candles`) | BingX DB | 3m / 5m | `fast_math` (Rust kernel), `structure_detectors` | Enable feeding Binance 5m causal closed candles as primary market intelligence while preserving BingX execution geometry | LOW | Retest state machine causality tests, target geometry tests | ZERO (improves setup accuracy without changing order path) |
| **Opportunity Bus / Candidates** | `control_plane/opportunity_bus.py` | Single venue with fallback ATR percentages and static `confidence=82.0` | BingX `candles` | Intraday | `db`, `symbols`, `daily_structural_bias` | Refactor candidate generation to consume primary Binance structure/retest, transition to `ENTRY_READY`, and freeze context | MEDIUM | Geometry invariant tests, freeze context tests | ZERO (retains `SHADOW` mode) |
| **TimesFM 3.0 Forecasting** | `control_plane/forecast_service.py` | Single venue, periodic schedule (5m), generic watchlist | BingX 5m candles | 5m (horizon=12) | PyTorch, `timesfm` 3.0.2 | Redesign from generic periodic forecast to candidate-specific binding (`CandidateForecastContext`) triggered at `ENTRY_READY` | MEDIUM | Zero-lookahead tests, quantile monotonicity ($q_{10} \le q_{50} \le q_{90}$) | ZERO (advisory only, no order placement) |
| **Forecast Trade Compatibility** | Does NOT exist | N/A | Candidate + TimesFM forecast | 15m, 30m, 45m, 60m | NumPy | Implement `ForecastTradeCompatibilityEngine` evaluating path, quantiles, dispersion against entry, SL, TP1, TP2, and holding horizon | LOW | Trade geometry vs distribution tests | ZERO (pure diagnostic and advisory evaluation) |
| **Cross-Venue Basis Engine** | Does NOT exist | Single venue implicit | Binance vs BingX tickers | Real-time / 1s | NumPy | Implement `control_plane/cross_venue_basis.py` calculating basis, basis %, basis z-score, quote freshness, and execution spread | LOW | Basis calculation tests, stale quote gate tests | ZERO (preflight validation only) |
| **Deterministic Risk & Preflight** | `control_plane/slot_allocation_service.py` | BingX execution only | BingX account balances & limits | Real-time | SQLite, `config.py` | Integrate cross-venue basis check and quote freshness into preflight before shadow reservation | LOW | 19-point preflight validation tests | ZERO (enforces existing safety barriers) |
| **Execution Venue Adapter** | `control_plane/bingx_client.py` | BingX Perpetual Futures | BingX REST API V2 | Real-time | HMAC SHA256, `requests`/`urllib` | Maintain strictly as the sole execution venue adapter. Binance market data NEVER touches BingX credentials | ZERO | Mock order execution tests | ZERO (`TRADING_AUTHORITY = FALSE`, live orders forbidden) |
| **FastAPI Observability** | `control_plane/api.py` | BingX & internal | SQLite tables | Real-time | FastAPI, JWT auth | Add endpoints: `/api/binance/*`, `/api/cross-venue/basis/*`, `/api/timesfm/candidate-forecast/*`, `/api/timesfm/compatibility/*` | LOW | Endpoint auth and schema tests | ZERO (read-only monitoring endpoints) |
| **Android Observability** | `android-app/` | Single venue display | FastAPI `/api/*` | Real-time | Jetpack Compose, Retrofit | Add Multi-Venue & TimesFM Compatibility cards in Admin/User UI with clear `RESEARCH / SHADOW` labels | LOW | Android compilation tests (`assembleAdminDebug`) | ZERO (observability only, no order buttons) |

---

## 2. Explicit Findings on 10 Architectural Tenets

### 1. What Already Exists and Can Be Reused
- `models/instrument.py`: Clean dataclass structure with price/quantity precision, min notional, and leverage rules. Can be cleanly extended to multi-venue representation without breaking downstream callers.
- `control_plane/retest_engine.py`: Sophisticated, causal retest state machine (`IDLE -> BREAKOUT_DETECTED -> WAITING_FOR_RETEST -> RETEST_ZONE_TOUCHED -> REJECTION_CONFIRMED -> ENTRY_CANDIDATE`). Computes valid structural targets ($SL < Entry < TP1 < TP2 < TP3$) with Rust acceleration. Fully reusable with Binance candle feeds.
- `control_plane/slot_allocation_service.py`: Battle-tested deterministic slot allocator with strict capital envelopes, user scoping, and concurrency safety.
- `control_plane/timesfm_adapter.py` & `control_plane/forecast_service.py`: Complete TimesFM 3.0 inference harness with PyTorch process isolation, quantile monotonicity enforcement, and resource headroom safeguards.
- `control_plane/microstructure_engine.py`: High-performance 8-module microstructure suite with circular buffers, L1/L5/L10 depth tracking, and econometric estimators.

### 2. What Is Incomplete
- Binance data layer: Zero ingestion code existed for Binance USD-M futures REST/WS.
- Candidate-specific TimesFM binding: TimesFM ran only on an arbitrary 5-minute timer across a hardcoded symbol list, rather than freezing context when a candidate reaches `ENTRY_READY`.
- Trade compatibility engine: No module existed to compare TimesFM distribution paths ($q_{10}, q_{50}, q_{90}$) against structural trade geometry ($Entry, SL, TP1, TP2$).
- Cross-venue basis tracking: No calculation of price divergence, basis velocity, or execution spread between Binance and BingX.

### 3. What Conflicts with Multi-Venue Architecture
- `control_plane/instruments.py`: Hardcoded to query only BingX REST endpoint `/openApi/swap/v2/quote/contracts`. Assumed single venue throughout the resolver cache.
- `control_plane/opportunity_bus.py`: Hardcoded fallback to `BTC-USDT` on BingX, queried directly from the BingX `candles` table.

### 4. What Is Hardcoded to BingX
- Table `candles` in `control_plane/db.py`: Primary key `(exchange, symbol, ts)` with `exchange` hardcoded to `'bingx'`.
- All price discovery in `control_plane/core.py` and `opportunity_bus.py` reads directly from BingX ticker or BingX klines.

### 5. What Is Hardcoded to Crypto Symbols
- Scanners in `opportunity_bus.py` contained hardcoded tuples `[("BTC-USDT", "BTC-USDT", 65000.0, ...)]`. Must be resolved dynamically from Canonical Instruments.

### 6. What Assumes One Venue
- The entire candidate generation pipeline assumed that the venue providing market data is the same venue where execution takes place.
- Signal prices were assumed to be the exact same as execution prices.

### 7. What Assumes One Price Source
- Structural level detection (swing highs/lows, VWAP, FVG) assumed single-source prices from BingX.
- Under high market volatility, BingX swap prices can deviate from Binance by 5–50 basis points. Using BingX prices for structure detection risks missing institutional breaks visible on Binance.

### 8. What Assumes One Timestamp Source
- Timestamp alignment across market events assumed BingX exchange server time.
- Binance and BingX server clocks may diverge by milliseconds to seconds. Cross-venue event correlation requires explicit timestamp delta tracking (`timestamp_delta_ms = abs(binance_ts - bingx_ts)`).

### 9. What Assumes TimesFM Is Generic Rather Than Candidate-Specific
- `ForecastService` ran periodic forecasts every 5 minutes regardless of whether a candidate was active.
- Candidates were scored with static artificial heuristic confidence scores (`confidence=82.0`), completely disconnected from TimesFM inference.

### 10. Where Historical and Live Research Share Unsafe State
- `market_1m.db` contained both live operational tables (`users`, `autonomous_trade_slots`) and ad-hoc research experiment logs.
- Dedicated raw Binance historical data must be stored with explicit venue identifiers and dataset lineage to prevent cross-contamination of operational state.

---

## 3. Implementation Plan & Review Gates

- **Phase 10A:** Canonical Multi-Venue Instrument Foundation (`models/instrument.py`, `control_plane/instruments.py`).
- **Phase 10B:** Binance Primary Market Data & Causal 1m -> 5m/15m/30m/1h Aggregation (`control_plane/binance_data.py`, `control_plane/db.py`).
- **Phase 10C:** Cross-Venue Basis Engine & Execution Translation (`control_plane/cross_venue_basis.py`).
- **Phase 10D:** Candidate-Specific TimesFM Redesign & Trade Compatibility Engine (`control_plane/timesfm_candidate.py`, `control_plane/trade_compatibility.py`).
- **Phase 10E:** Candidate-Level Empirical Utility Study & Binance vs BingX Comparative Research (Ablations A-F, MFE/MAE analysis).
- **Phase 10F:** Review Gates 1–5, Regression Suite, Sustained VPS Benchmark, Android Observability & Final Research Report.
