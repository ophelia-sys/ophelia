import pytest
import os
import numpy as np
import pandas as pd
from datetime import datetime
from institutional.data.models import TradeEvent
from institutional.cvd.live_engine import LiveCVDEngine
from research.experiments.exp_phase5_3_ml_ablation import engineer_cvd_features

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MODEL_PATH = os.path.join(BASE_DIR, "PHASE5_3_MODEL_G_FROZEN.pkl")

def get_test_trades(start_ms, count, buy_vol, sell_vol):
    trades = []
    # Make a uniform distribution of buys and sells within a 5m block
    # Actually just generate synthetic trades
    ts = start_ms
    for i in range(count):
        # alternate buy/sell
        if i % 2 == 0:
            trades.append(TradeEvent(
                symbol="BTCUSDT", trade_id=f"t_{ts}_{i}", timestamp=ts, 
                price=100.0, quantity=buy_vol/100.0, is_buyer_maker=False, source="bingx"
            ))
        else:
            trades.append(TradeEvent(
                symbol="BTCUSDT", trade_id=f"t_{ts}_{i}", timestamp=ts, 
                price=100.0, quantity=sell_vol/100.0, is_buyer_maker=True, source="bingx"
            ))
        ts += 1000 # 1 sec apart
    return trades

def generate_df_cvd(start_minute, periods):
    # Generates a synthetic df_cvd matching the test trades
    data = []
    ts = start_minute
    for p in range(periods):
        data.append({
            'minute': ts,
            'buy_volume': 100.0,
            'sell_volume': 50.0,
            'delta_volume': 50.0
        })
        ts += 300000
    return pd.DataFrame(data)

def test_live_aggregation_parity():
    engine = LiveCVDEngine("BTCUSDT", MODEL_PATH)
    
    start_time = 1640995200000 # 2022-01-01 00:00:00
    
    # We will generate 300 periods of 5m
    periods = 300
    
    for p in range(periods):
        block_start = start_time + p * 300000
        # 2 trades per block, add p to buy volume so variance is not 0
        trades = get_test_trades(block_start, 2, 100.0 + p, 50.0)
        for t in trades:
            engine.add_trade(t)
            
    T_decision = start_time + periods * 300000
    
    # Live features
    live_feats = engine.get_features(T_decision)
    assert live_feats is not None
    
    # Historical features
    df_cvd = generate_df_cvd(start_time, periods)
    
    # modify df_cvd to match the varying buy volume
    for p in range(periods):
        df_cvd.loc[p, 'buy_volume'] = 100.0 + p
        df_cvd.loc[p, 'delta_volume'] = (100.0 + p) - 50.0
        
    df_ohlcv = pd.DataFrame([{'timestamp': pd.to_datetime(start_time + p*300000, unit='ms')} for p in range(periods)])
    df_ohlcv['timestamp'] = pd.to_datetime(df_ohlcv['timestamp'])
    
    df_cvd['minute'] = pd.to_datetime(df_cvd['minute'], unit='ms')
    
    hist_df = engineer_cvd_features(df_ohlcv, df_cvd)
    
    hist_last = hist_df.iloc[-1]
    
    # Parity assertions
    assert np.isclose(live_feats.cvd_delta_5m, hist_last['cvd_delta_5m'])
    assert np.isclose(live_feats.cvd_delta_15m, hist_last['cvd_delta_15m'])
    assert np.isclose(live_feats.cvd_delta_1h, hist_last['cvd_delta_1h'])
    assert np.isclose(live_feats.cvd_imbalance_5m, hist_last['cvd_imbalance_5m'])
    assert np.isclose(live_feats.cvd_imbalance_15m, hist_last['cvd_imbalance_15m'])
    assert np.isclose(live_feats.cvd_imbalance_1h, hist_last['cvd_imbalance_1h'])
    assert np.isclose(live_feats.cvd_zscore_5m, hist_last['cvd_zscore_5m'])
    assert np.isclose(live_feats.cvd_zscore_15m, hist_last['cvd_zscore_15m'])
    assert np.isclose(live_feats.cvd_zscore_1h, hist_last['cvd_zscore_1h'])
    assert np.isclose(live_feats.cvd_acceleration_15m, hist_last['cvd_acceleration_15m'])
    assert np.isclose(live_feats.cvd_acceleration_1h, hist_last['cvd_acceleration_1h'])

def test_missing_data_state():
    engine = LiveCVDEngine("BTCUSDT", MODEL_PATH)
    start_time = 1640995200000
    periods = 100 # < 288 required for z-score
    for p in range(periods):
        block_start = start_time + p * 300000
        trades = get_test_trades(block_start, 2, 100.0, 50.0)
        for t in trades:
            engine.add_trade(t)
    T_decision = start_time + periods * 300000
    
    live_feats = engine.get_features(T_decision)
    # Expected to be None because not enough history for rolling 288
    assert live_feats is None

def test_zero_variance_zscore():
    engine = LiveCVDEngine("BTCUSDT", MODEL_PATH)
    start_time = 1640995200000
    periods = 300
    for p in range(periods):
        block_start = start_time + p * 300000
        # All blocks exactly identical delta volume = 0 -> Variance = 0
        trades = get_test_trades(block_start, 2, 100.0, 100.0)
        for t in trades:
            engine.add_trade(t)
    T_decision = start_time + periods * 300000
    live_feats = engine.get_features(T_decision)
    
    assert live_feats is not None
    # If variance is 0, zscore should be NaN according to the registry math
    assert np.isnan(live_feats.cvd_zscore_5m)
    assert np.isnan(live_feats.cvd_zscore_15m)
    assert np.isnan(live_feats.cvd_zscore_1h)
