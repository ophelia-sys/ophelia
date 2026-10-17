"""Binance USD-M Primary Market Data Foundation & Causal Aggregation Subsystem.

Layer: control_plane/binance_data.py
Contract:
- Authoritative ingestion of Binance USD-M Perpetual 1m klines, trades, and order-book depth.
- Strict causal candle aggregation: 1m closed bars -> 5m, 15m, 30m, 1h derived candles.
- Zero lookahead: Only closed 1m bars enter finalized derived candles and TimesFM context.
- Forming candles explicitly marked PARTIAL / NOT_CLOSED.
- Quality states: VALID, PARTIAL, MISSING, STALE, DUPLICATE, OUT_OF_ORDER, DEGRADED, NOT_AVAILABLE.
- Historical backfill with pagination, rate-limit backoff, and continuity verification.
"""
from __future__ import annotations

import json
import logging
import math
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from . import config, db

logger = logging.getLogger("ophelia.binance_data")

BINANCE_FAPI_BASE_URL = "https://fapi.binance.com"
DEFAULT_USER_AGENT = "Ophelia-MultiVenue/1.0"
RESOLUTION_MINUTES = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
}


@dataclass(slots=True)
class BinanceCandle1m:
    symbol: str
    ts: int  # Open timestamp (epoch ms)
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_ts: int
    quote_volume: float
    trade_count: int
    taker_buy_volume: float
    taker_buy_quote_volume: float
    is_closed: bool = True
    data_quality: str = "VALID"
    freshness: str = "FRESH"
    venue: str = "BINANCE"
    venue_product: str = "USDM_PERPETUAL"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BinanceMarketDataProvider:
    """Authoritative client for Binance USD-M Perpetual Futures market data."""

    def __init__(self, base_url: str = BINANCE_FAPI_BASE_URL, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        query_str = f"?{urllib.parse.urlencode(params)}" if params else ""
        url = f"{self.base_url}{path}{query_str}"
        req = urllib.request.Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data
        except urllib.error.HTTPError as e:
            if e.code == 429:
                logger.warning("Binance rate limit 429 encountered on %s. Sleeping 2s.", path)
                time.sleep(2.0)
            logger.error("Binance HTTPError %d on %s: %s", e.code, path, e.reason)
            raise
        except Exception as e:
            logger.error("Binance request error on %s: %s", path, e)
            raise

    def fetch_server_time(self) -> int:
        data = self._get("/fapi/v1/time")
        return int(data.get("serverTime", int(time.time() * 1000)))

    def fetch_exchange_info(self) -> dict:
        return self._get("/fapi/v1/exchangeInfo")

    def fetch_klines(
        self,
        symbol: str,
        interval: str = "1m",
        limit: int = 1000,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[BinanceCandle1m]:
        """Fetch 1m klines from Binance USD-M Futures and normalize to typed models."""
        params: Dict[str, Any] = {"symbol": symbol.upper(), "interval": interval, "limit": min(limit, 1500)}
        if start_time is not None:
            params["startTime"] = int(start_time)
        if end_time is not None:
            params["endTime"] = int(end_time)

        raw_rows = self._get("/fapi/v1/klines", params)
        now_ms = int(time.time() * 1000)
        results: List[BinanceCandle1m] = []

        for r in raw_rows:
            if not isinstance(r, (list, tuple)) or len(r) < 11:
                continue
            open_ts = int(r[0])
            close_ts = int(r[6])
            is_closed = (now_ms >= close_ts)
            quality = "VALID" if is_closed else "PARTIAL"
            freshness = "FRESH" if (now_ms - open_ts < 300_000) else "HISTORICAL"

            results.append(BinanceCandle1m(
                symbol=symbol.upper(),
                ts=open_ts,
                open=float(r[1]),
                high=float(r[2]),
                low=float(r[3]),
                close=float(r[4]),
                volume=float(r[5]),
                close_ts=close_ts,
                quote_volume=float(r[7]),
                trade_count=int(r[8]),
                taker_buy_volume=float(r[9]),
                taker_buy_quote_volume=float(r[10]),
                is_closed=is_closed,
                data_quality=quality,
                freshness=freshness
            ))
        return results

    def fetch_agg_trades(self, symbol: str, limit: int = 500, start_time: Optional[int] = None) -> List[dict]:
        params: Dict[str, Any] = {"symbol": symbol.upper(), "limit": min(limit, 1000)}
        if start_time is not None:
            params["startTime"] = int(start_time)
        return self._get("/fapi/v1/aggTrades", params)

    def fetch_depth(self, symbol: str, limit: int = 20) -> dict:
        return self._get("/fapi/v1/depth", {"symbol": symbol.upper(), "limit": limit})

    def fetch_mark_price(self, symbol: str) -> dict:
        return self._get("/fapi/v1/premiumIndex", {"symbol": symbol.upper()})


class CausalCandleAggregator:
    """Strictly causal candle aggregation engine from closed 1m bars to higher resolutions."""

    @staticmethod
    def aggregate_window(raw_1m_bars: List[dict], target_resolution: str) -> Optional[dict]:
        """Aggregate a fixed chronological window of closed 1m bars into a derived candle.
        
        Invariants:
        - Exactly N consecutive closed 1m bars required (5 for 5m, 15 for 15m, 30 for 30m, 60 for 1h).
        - Every 1m bar must be closed (is_closed == True).
        - Consecutive timestamps must satisfy ts[i+1] == ts[i] + 60000.
        - Open is first bar open; Close is last bar close; High is max high; Low is min low.
        - Volumes and trade counts are summed.
        """
        required_bars = RESOLUTION_MINUTES.get(target_resolution)
        if not required_bars:
            raise ValueError(f"Unsupported target resolution: {target_resolution}")

        if len(raw_1m_bars) != required_bars:
            return None

        # Verify causality and closure
        for b in raw_1m_bars:
            if not b.get("is_closed", True):
                return None  # Partial candle cannot enter finalized derived history

        # Verify timestamp continuity
        sorted_bars = sorted(raw_1m_bars, key=lambda x: int(x["ts"]))
        expected_step = 60_000
        for i in range(len(sorted_bars) - 1):
            curr_ts = int(sorted_bars[i]["ts"])
            next_ts = int(sorted_bars[i + 1]["ts"])
            if next_ts - curr_ts != expected_step:
                # Sequence gap detected
                return None

        first_bar = sorted_bars[0]
        last_bar = sorted_bars[-1]
        symbol = first_bar.get("symbol", "")
        start_ts = int(first_bar["ts"])
        close_ts = int(last_bar.get("close_ts", last_bar["ts"] + 59_999))

        o = float(first_bar["open"])
        c = float(last_bar["close"])
        h = max(float(b["high"]) for b in sorted_bars)
        l = min(float(b["low"]) for b in sorted_bars)
        v = sum(float(b["volume"]) for b in sorted_bars)
        qv = sum(float(b.get("quote_volume", 0.0)) for b in sorted_bars)
        tc = sum(int(b.get("trade_count", 0)) for b in sorted_bars)
        tbv = sum(float(b.get("taker_buy_volume", 0.0)) for b in sorted_bars)

        now_ms = int(time.time() * 1000)
        return {
            "venue": "BINANCE",
            "symbol": symbol,
            "canonical_instrument_id": first_bar.get("canonical_instrument_id", f"CRYPTO:{symbol}"),
            "resolution": target_resolution,
            "ts": start_ts,
            "close_ts": close_ts,
            "open": round(o, 4),
            "high": round(h, 4),
            "low": round(l, 4),
            "close": round(c, 4),
            "volume": round(v, 4),
            "quote_volume": round(qv, 4),
            "trade_count": tc,
            "taker_buy_volume": round(tbv, 4),
            "source_bar_count": len(sorted_bars),
            "is_closed": True,
            "data_quality": "VALID",
            "freshness": "FRESH" if (now_ms - close_ts < 600_000) else "HISTORICAL"
        }

    @classmethod
    def aggregate_series(cls, raw_1m_bars: List[dict], target_resolution: str) -> List[dict]:
        """Aggregate a continuous series of closed 1m bars into aligned derived candles."""
        req_minutes = RESOLUTION_MINUTES.get(target_resolution, 5)
        interval_ms = req_minutes * 60_000
        if not raw_1m_bars:
            return []

        # Filter strictly closed bars and sort
        closed_bars = [b for b in raw_1m_bars if b.get("is_closed", True)]
        closed_bars.sort(key=lambda x: int(x["ts"]))

        # Group bars into aligned buckets
        buckets: Dict[int, List[dict]] = {}
        for b in closed_bars:
            ts = int(b["ts"])
            bucket_start = (ts // interval_ms) * interval_ms
            if bucket_start not in buckets:
                buckets[bucket_start] = []
            buckets[bucket_start].append(b)

        derived: List[dict] = []
        for bucket_start in sorted(buckets.keys()):
            bars = buckets[bucket_start]
            if len(bars) == req_minutes:
                candle = cls.aggregate_window(bars, target_resolution)
                if candle:
                    derived.append(candle)
        return derived


class BinanceHistoricalBackfill:
    """Historical backfill harness for populating high-quality research datasets."""

    def __init__(self, provider: Optional[BinanceMarketDataProvider] = None):
        self.provider = provider or BinanceMarketDataProvider()

    def backfill_symbol(
        self,
        symbol: str,
        target_days: int = 4,
        chunk_limit: int = 1000
    ) -> Dict[str, Any]:
        """Backfill 1m klines for up to target_days (max 4 days for initial research),
        validate continuity, persist raw 1m, and aggregate into 5m derived candles.
        """
        now_ms = int(time.time() * 1000)
        target_start_ts = now_ms - (target_days * 86_400 * 1000)
        # Align target start to nearest minute
        target_start_ts = (target_start_ts // 60_000) * 60_000

        all_1m_bars: List[dict] = []
        curr_start = target_start_ts

        logger.info("Starting Binance backfill for %s from %d to %d (%d days)", symbol, target_start_ts, now_ms, target_days)
        while curr_start < now_ms:
            try:
                bars = self.provider.fetch_klines(
                    symbol=symbol,
                    interval="1m",
                    limit=chunk_limit,
                    start_time=curr_start,
                    end_time=now_ms
                )
            except Exception as e:
                logger.error("Failed fetching kline batch at %d for %s: %s", curr_start, symbol, e)
                break

            if not bars:
                break

            for b in bars:
                if b.is_closed:
                    all_1m_bars.append(b.to_dict())

            last_ts = bars[-1].ts
            if last_ts <= curr_start:
                break
            curr_start = last_ts + 60_000
            time.sleep(0.05)  # Rate limit politeness

        # Deduplicate by timestamp
        dedup_map: Dict[int, dict] = {}
        for b in all_1m_bars:
            dedup_map[int(b["ts"])] = b
        sorted_bars = [dedup_map[ts] for ts in sorted(dedup_map.keys())]

        # Persist raw 1m
        raw_inserted = db.insert_binance_raw_1m(sorted_bars)

        # Causal aggregation to 5m
        derived_5m = CausalCandleAggregator.aggregate_series(sorted_bars, "5m")
        derived_5m_inserted = db.insert_binance_derived_candles(derived_5m)

        # Causal aggregation to 15m
        derived_15m = CausalCandleAggregator.aggregate_series(sorted_bars, "15m")
        derived_15m_inserted = db.insert_binance_derived_candles(derived_15m)

        return {
            "symbol": symbol.upper(),
            "target_days": target_days,
            "raw_1m_count": len(sorted_bars),
            "raw_1m_inserted": raw_inserted,
            "derived_5m_count": len(derived_5m),
            "derived_5m_inserted": derived_5m_inserted,
            "derived_15m_count": len(derived_15m),
            "derived_15m_inserted": derived_15m_inserted,
            "start_ts": sorted_bars[0]["ts"] if sorted_bars else None,
            "end_ts": sorted_bars[-1]["ts"] if sorted_bars else None,
            "status": "SUCCESS" if len(sorted_bars) > 0 else "EMPTY"
        }
