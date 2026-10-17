"""Unit tests for the Deterministic 48-Hour Historical Backtest Engine."""
import time
import pytest
from control_plane import backtest, db


def test_backtest_closed_candle_simulation():
    """Verify backtest executes causal simulation on synthetic deterministic candle data."""
    # Seed 100 synthetic 1m candles for BTC-USDT
    now_ms = int(time.time() * 1000)
    base_px = 65000.0
    candles = []
    
    # Create an upward impulse with breakout and retest
    for i in range(120):
        ts = now_ms - (120 - i) * 60_000
        if i < 40:
            px = base_px + (i * 5.0)
            candles.append({"ts": ts, "open": px, "high": px + 10, "low": px - 10, "close": px, "volume": 10.0, "taker_buy": 5.0, "trades": 50})
        elif i < 60: # Impulse breakout
            px = base_px + 200 + ((i - 40) * 30.0)
            candles.append({"ts": ts, "open": px - 15, "high": px + 30, "low": px - 20, "close": px, "volume": 50.0, "taker_buy": 40.0, "trades": 200})
        elif i < 80: # Retest pullback
            px = base_px + 700 - ((i - 60) * 15.0)
            candles.append({"ts": ts, "open": px + 10, "high": px + 15, "low": px - 15, "close": px, "volume": 15.0, "taker_buy": 7.0, "trades": 70})
        else: # Continuation toward targets
            px = base_px + 450 + ((i - 80) * 25.0)
            candles.append({"ts": ts, "open": px - 10, "high": px + 25, "low": px - 10, "close": px, "volume": 35.0, "taker_buy": 25.0, "trades": 150})

    db.upsert_candles("BINANCE", "BTC-USDT", candles)

    # Initial state check
    initial_open_pos = db.total_open_positions_count()

    # Run backtest
    res = backtest.run_48h_backtest(
        symbols=["BTC-USDT"],
        timeframes=[1, 3],
        hours=48,
        initial_capital_usdt=1000.0,
        margin_per_trade_usdt=100.0,
        leverage=10.0
    )

    assert res["status"] == "COMPLETED"
    assert "BACKTEST" in res["label"]
    assert "metrics" in res
    assert "win_rate_pct" in res["metrics"]
    assert "profit_factor" in res["metrics"]
    assert "total_fees_usdt" in res["metrics"]
    assert "net_return_usdt" in res["metrics"]
    assert "max_drawdown_pct" in res["metrics"]

    # Strict isolation verification: Zero mutation to live/shadow operational state
    assert db.total_open_positions_count() == initial_open_pos
