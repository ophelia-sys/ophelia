"""
Authoritative CVD (Cumulative Volume Delta) Research Engine for Ophelia.
Layer: institutional/cvd
Contract: Evaluates public order-flow trades without execution authority.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
import time
from institutional.types import DataQuality, Direction


@dataclass(frozen=True)
class CVDTrade:
    """Individual trade event conforming to BingX public trade payload."""
    trade_id: str
    timestamp: int  # UTC ms
    price: float
    quantity: float
    quote_quantity: float
    is_buyer_maker: bool
    source: str = "bingx_public_trades"

    @property
    def aggressor(self) -> str:
        """
        is_buyer_maker == True  -> Maker was buyer, Taker was seller -> Aggressive SELL
        is_buyer_maker == False -> Maker was seller, Taker was buyer -> Aggressive BUY
        """
        return "SELL" if self.is_buyer_maker else "BUY"

    @property
    def signed_delta(self) -> float:
        """Signed quote volume (positive for buy, negative for sell)."""
        vol = self.quote_quantity if self.quote_quantity > 0 else (self.price * self.quantity)
        return vol if self.aggressor == "BUY" else -vol


@dataclass
class CVDAggregation:
    """Aggregated CVD bar over a discrete timeframe interval."""
    interval_start_ms: int
    interval_end_ms: int
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    buy_volume: float
    sell_volume: float
    delta_volume: float
    cumulative_delta: float
    trade_count: int
    imbalance_ratio: float = 0.0  # (buy - sell) / (buy + sell)


class CVDEngine:
    """
    Deterministic Cumulative Volume Delta (CVD) Engine.
    Processes trade events, deduplicates, maintains continuous delta aggregation,
    and supports daily / session resets.
    """

    def __init__(
        self,
        symbol: str,
        interval_ms: int = 60_000,  # default 1m
        stale_threshold_ms: int = 120_000,
        max_seen_trades: int = 50_000,
        reset_interval_ms: Optional[int] = 86_400_000  # 24h reset
    ):
        self.symbol = symbol
        self.interval_ms = interval_ms
        self.stale_threshold_ms = stale_threshold_ms
        self.max_seen_trades = max_seen_trades
        self.reset_interval_ms = reset_interval_ms

        self.seen_trade_ids: Set[str] = set()
        self.seen_trades_fifo: List[str] = []
        
        self.cumulative_delta: float = 0.0
        self.last_reset_time_ms: int = 0
        self.last_trade_time_ms: int = 0
        
        # History of completed aggregations
        self.history: List[CVDAggregation] = []
        self.max_history_len: int = 1440  # 24h of 1m bars
        
        # In-flight bar
        self._current_bar: Optional[CVDAggregation] = None

    def add_trade(self, trade: CVDTrade) -> bool:
        """
        Ingest an individual trade event.
        Returns True if accepted, False if duplicate or rejected.
        """
        if trade.trade_id in self.seen_trade_ids:
            return False  # Deduplicate

        # Enforce FIFO bound on seen trade IDs
        self.seen_trade_ids.add(trade.trade_id)
        self.seen_trades_fifo.append(trade.trade_id)
        if len(self.seen_trades_fifo) > self.max_seen_trades:
            oldest = self.seen_trades_fifo.pop(0)
            self.seen_trade_ids.discard(oldest)

        # Check session / daily reset
        if self.reset_interval_ms and self.last_reset_time_ms > 0:
            if trade.timestamp - self.last_reset_time_ms >= self.reset_interval_ms:
                self.reset_cumulative(trade.timestamp)
        elif self.last_reset_time_ms == 0:
            self.last_reset_time_ms = trade.timestamp

        vol = trade.quote_quantity if trade.quote_quantity > 0 else (trade.price * trade.quantity)
        delta = trade.signed_delta
        self.cumulative_delta += delta
        self.last_trade_time_ms = max(self.last_trade_time_ms, trade.timestamp)

        bar_start = (trade.timestamp // self.interval_ms) * self.interval_ms
        bar_end = bar_start + self.interval_ms

        if self._current_bar is None or self._current_bar.interval_start_ms != bar_start:
            if self._current_bar is not None:
                # Finalize previous bar
                self._finalize_bar(self._current_bar)
            
            # Start new bar
            self._current_bar = CVDAggregation(
                interval_start_ms=bar_start,
                interval_end_ms=bar_end,
                open_price=trade.price,
                high_price=trade.price,
                low_price=trade.price,
                close_price=trade.price,
                buy_volume=vol if trade.aggressor == "BUY" else 0.0,
                sell_volume=vol if trade.aggressor == "SELL" else 0.0,
                delta_volume=delta,
                cumulative_delta=self.cumulative_delta,
                trade_count=1
            )
        else:
            # Update existing bar
            cb = self._current_bar
            cb.high_price = max(cb.high_price, trade.price)
            cb.low_price = min(cb.low_price, trade.price)
            cb.close_price = trade.price
            if trade.aggressor == "BUY":
                cb.buy_volume += vol
            else:
                cb.sell_volume += vol
            cb.delta_volume += delta
            cb.cumulative_delta = self.cumulative_delta
            cb.trade_count += 1

        # Update imbalance ratio
        tot_vol = self._current_bar.buy_volume + self._current_bar.sell_volume
        if tot_vol > 0:
            self._current_bar.imbalance_ratio = self._current_bar.delta_volume / tot_vol
        else:
            self._current_bar.imbalance_ratio = 0.0

        return True

    def _finalize_bar(self, bar: CVDAggregation):
        """Store completed bar into bounded history."""
        self.history.append(bar)
        if len(self.history) > self.max_history_len:
            self.history.pop(0)

    def reset_cumulative(self, current_time_ms: int):
        """Explicitly reset cumulative volume delta (e.g., at 00:00 UTC or session change)."""
        self.cumulative_delta = 0.0
        self.last_reset_time_ms = current_time_ms

    def get_data_quality(self, current_time_ms: Optional[int] = None) -> DataQuality:
        """Inspect data freshness and feed continuity."""
        if current_time_ms is None:
            current_time_ms = int(time.time() * 1000)

        if self.last_trade_time_ms == 0:
            return DataQuality.INSUFFICIENT_DATA

        age_ms = current_time_ms - self.last_trade_time_ms
        if age_ms > self.stale_threshold_ms:
            return DataQuality.STALE

        if len(self.history) < 2 and self._current_bar is None:
            return DataQuality.DEGRADED

        return DataQuality.VALID

    def get_taker_volume_imbalance(self, lookback_bars: int = 5) -> float:
        """Calculate taker volume imbalance over the recent N bars."""
        bars = self.get_recent_bars(lookback_bars)
        if not bars:
            return 0.0
        tot_buy = sum(b.buy_volume for b in bars)
        tot_sell = sum(b.sell_volume for b in bars)
        tot = tot_buy + tot_sell
        if tot == 0:
            return 0.0
        return (tot_buy - tot_sell) / tot

    def get_recent_bars(self, count: int) -> List[CVDAggregation]:
        """Return the most recent N aggregated bars including active in-flight bar."""
        res = list(self.history[-count:])
        if self._current_bar is not None and (not res or res[-1] != self._current_bar):
            res.append(self._current_bar)
        return res[-count:]

    def get_state(self, current_time_ms: Optional[int] = None) -> Dict:
        """Produce a complete telemetry state of the CVD engine."""
        dq = self.get_data_quality(current_time_ms)
        imbalance_5 = self.get_taker_volume_imbalance(5)
        
        direction = Direction.NEUTRAL
        if imbalance_5 > 0.15:
            direction = Direction.BULLISH
        elif imbalance_5 < -0.15:
            direction = Direction.BEARISH

        active_bar = self._current_bar
        return {
            "symbol": self.symbol,
            "cumulative_delta": round(self.cumulative_delta, 2),
            "current_bar_delta": round(active_bar.delta_volume if active_bar else 0.0, 2),
            "imbalance_ratio": round(active_bar.imbalance_ratio if active_bar else 0.0, 4),
            "taker_volume_imbalance_5m": round(imbalance_5, 4),
            "direction": direction.value,
            "data_quality": dq.value,
            "trade_count": active_bar.trade_count if active_bar else 0,
            "last_trade_time_ms": self.last_trade_time_ms,
            "bars_in_history": len(self.history)
        }
