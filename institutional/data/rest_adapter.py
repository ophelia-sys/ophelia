import time
import requests
from typing import Optional, List
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from institutional.types import DataQuality
from institutional.data.models import (
    TradeEvent, OrderBookSnapshot, FundingSnapshot,
    OpenInterestSnapshot, MarketTicker, OHLCVBar
)

class InstitutionalRESTAdapter:
    """
    Read-only adapter for acquiring public institutional metrics from BingX Swap API.
    
    This client is initialized with an injected BingXClient to strictly enforce
    the rule that BingXClient is the only component that communicates with BingX.
    """
    
    def __init__(self, client=None):
        if client is None:
            from exchange.bingx_client import BingXClient
            self.client = BingXClient()
        else:
            self.client = client

    def get_order_book(self, symbol: str, limit: int = 20) -> Optional[OrderBookSnapshot]:
        try:
            res = self.client.get_depth(symbol=symbol, limit=limit)
        except Exception as e:
            return OrderBookSnapshot(
                symbol=symbol, timestamp=int(time.time() * 1000),
                bids=[], asks=[], source="REST", data_quality=DataQuality.UNAVAILABLE
            )
        
        # res has: 'T': timestamp, 'bids': [[price, qty]], 'asks': [[price, qty]]
        timestamp = res.get("T", int(time.time() * 1000))
        bids = [[float(p), float(q)] for p, q in res.get("bids", [])]
        asks = [[float(p), float(q)] for p, q in res.get("asks", [])]
        
        return OrderBookSnapshot(
            symbol=symbol, timestamp=timestamp,
            bids=bids, asks=asks, source="REST"
        )

    def get_trades(self, symbol: str, limit: int = 100) -> List[TradeEvent]:
        try:
            res = self.client.get_trades(symbol=symbol, limit=limit)
            if not isinstance(res, list): return []
        except Exception as e:
            return []
            
        events = []
        for t in res:
            events.append(TradeEvent(
                symbol=symbol,
                trade_id=str(t.get("fillId", "")),
                timestamp=int(t.get("time", 0)),
                price=float(t.get("price", 0.0)),
                quantity=float(t.get("qty", 0.0)),
                is_buyer_maker=bool(t.get("isBuyerMaker", False)),
                source="REST"
            ))
        return events

    def get_funding_history(self, symbol: str) -> List[FundingSnapshot]:
        # The endpoint returns a list of historical funding rates.
        try:
            res = self.client.get_funding_rate(symbol=symbol)
            if not isinstance(res, list) or len(res) == 0:
                raise ValueError("Empty funding rate list")
        except Exception as e:
            return []
            
        snapshots = []
        for item in res:
            snapshots.append(FundingSnapshot(
                symbol=symbol,
                timestamp=int(item.get("fundingTime", 0)),
                funding_rate=float(item.get("fundingRate", 0.0)),
                mark_price=float(item.get("markPrice", 0.0)) if "markPrice" in item else None,
                source="REST"
            ))
        # Ensure chronological order (oldest first)
        snapshots.sort(key=lambda s: s.timestamp)
        return snapshots

    def get_open_interest(self, symbol: str) -> Optional[OpenInterestSnapshot]:
        try:
            res = self.client.get_open_interest(symbol=symbol)
            if not isinstance(res, dict): raise ValueError("Expected dict")
        except Exception as e:
            return OpenInterestSnapshot(
                symbol=symbol, timestamp=int(time.time() * 1000),
                open_interest=0.0, source="REST", data_quality=DataQuality.UNAVAILABLE
            )
            
        return OpenInterestSnapshot(
            symbol=res.get("symbol", symbol),
            timestamp=int(res.get("time", 0)),
            open_interest=float(res.get("openInterest", 0.0)),
            source="REST"
        )

    def get_ticker(self, symbol: str) -> Optional[MarketTicker]:
        try:
            # We can use the core.Serializer typed model, but we need raw for parsing
            ticker = self.client.get_ticker(symbol=symbol)
            return MarketTicker(
                symbol=ticker.symbol,
                timestamp=int(time.time() * 1000), # we can just use now
                last_price=float(ticker.last_price),
                volume_24h=float(ticker.volume),
                source="REST"
            )
        except Exception as e:
            return MarketTicker(
                symbol=symbol, timestamp=int(time.time() * 1000),
                last_price=0.0, volume_24h=0.0, source="REST", data_quality=DataQuality.UNAVAILABLE
            )

    def get_klines(self, symbol: str, interval: str, limit: int = 500) -> List[OHLCVBar]:
        try:
            res = self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
            if not isinstance(res, list): return []
        except Exception as e:
            return []
            
        bars = []
        for k in res:
            bars.append(OHLCVBar(
                symbol=symbol,
                timestamp=int(k.get("time", 0)),
                open=float(k.get("open", 0.0)),
                high=float(k.get("high", 0.0)),
                low=float(k.get("low", 0.0)),
                close=float(k.get("close", 0.0)),
                volume=float(k.get("volume", 0.0)),
                source="REST"
            ))
        # BingX returns the oldest first (typically), we can sort just in case
        bars.sort(key=lambda b: b.timestamp)
        return bars
