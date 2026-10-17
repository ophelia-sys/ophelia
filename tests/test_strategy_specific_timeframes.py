import pytest
from unittest.mock import patch, MagicMock
from control_plane import core, analytics

def test_strategy_specific_timeframes():
    """
    Prove that BOTH strategy correctly delegates to 3m for VWAP_SUPERTREND
    and 1m for EMA_CROSSOVER.
    """
    automation = {
        "id": 1,
        "status": "ACTIVE",
        "strategy": "BOTH",
        "symbol": "BTC-USDT",
        "mode": "SHADOW",
        "margin_usdt": 100,
        "leverage": 10,
        "params": {
            "strategy_timeframes": {
                "VWAP_SUPERTREND": 3,
                "EMA_CROSSOVER": 1
            },
            "strategy_risk": {
                "VWAP_SUPERTREND": {"stops": [{"type": "entry_pct", "value": 1.0}]},
                "EMA_CROSSOVER": {"stops": [{"type": "entry_pct", "value": 0.5}]}
            }
        }
    }

    with patch('control_plane.analytics.get_candles') as mock_get_candles, \
         patch('control_plane.db.event_seen', return_value=False), \
         patch('control_plane.db.event_record'), \
         patch('control_plane.core.one_trade_block', return_value=False), \
         patch('control_plane.db.record_shadow_trade', return_value=999), \
         patch('control_plane.analytics.vwap_regime') as mock_regime, \
         patch('control_plane.analytics.st_vwap_cross_event') as mock_st, \
         patch('control_plane.core.check_crossover_event') as mock_ema:
         
        # Simulate VWAP_SUPERTREND generating a signal
        mock_regime.return_value = {"eligible": "LONG", "state": "CLEAR_ABOVE", "separation_pct": 1.5}
        mock_st.return_value = {"direction": "LONG", "candle_ts": 1000, "close": 50000.0, "st_line": 49000.0, "vwap": 49500.0}
        mock_ema.return_value = None
        
        res = core.fire_condition_if_triggered(automation)
        print("RES:", res)
        print("Mock calls:", mock_regime.call_args_list)
        
        # Verify VWAP_SUPERTREND was evaluated with tf=3
        mock_regime.assert_any_call("BTC-USDT", 3)
        mock_st.assert_called_once_with("BTC-USDT", 3)

        # Now simulate EMA_CROSSOVER generating a signal
        mock_regime.reset_mock()
        mock_st.reset_mock()
        mock_ema.reset_mock()
        
        mock_regime.return_value = {"eligible": "LONG", "state": "CLEAR_ABOVE", "separation_pct": 1.5}
        mock_st.return_value = None
        mock_ema.return_value = {"direction": "LONG", "candle_ts": 2000, "close": 50000.0, "ema9": 49000.0, "ema20": 48000.0}
        
        res = core.fire_condition_if_triggered(automation)
        
        # Verify EMA_CROSSOVER was evaluated with tf=1
        # VWAP_SUPERTREND is checked first, so mock_regime is called for tf=3, then mock_st for tf=3.
        # Then EMA_CROSSOVER is checked, so mock_regime is called for tf=1, then mock_ema for tf=1.
        mock_regime.assert_any_call("BTC-USDT", 1)
        mock_ema.assert_called_once_with("BTC-USDT", 1)

    print("Test passed! Timeframes are already independent during execution.")

if __name__ == "__main__":
    test_strategy_specific_timeframes()
