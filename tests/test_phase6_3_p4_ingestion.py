import pytest
import pandas as pd
import numpy as np
import sys
import os
import collections

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from research.data.ingest_aggtrades_p4 import P4IngestionPipeline

def test_p4_causal_threshold():
    pipeline = P4IngestionPipeline("TEST")
    
    # Fill rolling history with 288 bars of simulated trades
    # Let's say all past trades were exactly size 100
    for _ in range(288):
        pipeline.rolling_history.append(np.array([100.0, 100.0]))
        
    # The 99th percentile of [100.0, ...] should be 100.0
    threshold = pipeline._compute_threshold()
    assert threshold == 100.0
    
    # Now process a new bar t where trades are size 500
    df = pd.DataFrame({
        'quote_qty': [500.0, 500.0],
        'is_buyer_maker': [True, False]
    })
    
    ts = pd.Timestamp('2022-01-01 00:00:00')
    feat = pipeline._process_bar(ts, df)
    
    # The threshold used to compute features for bar t MUST be 100.0, NOT 500.0
    assert feat['threshold'] == 100.0
    
    # Since trades are 500 (>= 100), they should count as large
    assert feat['large_buy_volume_5m'] == 500.0
    assert feat['large_sell_volume_5m'] == 500.0
    
    # After bar t is processed, the new history should include the 500s
    assert 500.0 in pipeline.rolling_history[-1]

def test_p4_chunk_boundary():
    # Simulate pending trades that span chunks
    pipeline = P4IngestionPipeline("TEST")
    
    # Create chunk 1 with first half of bar
    df1 = pd.DataFrame({
        'bar_ts': [pd.Timestamp('2022-01-01 00:00:00')] * 3,
        'quote_qty': [10.0, 20.0, 30.0],
        'is_buyer_maker': [True, False, True]
    })
    
    # Create chunk 2 with second half of bar
    df2 = pd.DataFrame({
        'bar_ts': [pd.Timestamp('2022-01-01 00:00:00')] * 2,
        'quote_qty': [40.0, 50.0],
        'is_buyer_maker': [False, True]
    })
    
    # Normally the pipeline accumulates these in pending_trades
    pending = [df1, df2]
    merged = pd.concat(pending)
    
    feat = pipeline._process_bar(merged['bar_ts'].iloc[0], merged)
    
    # It should have processed all 5 trades
    assert feat['trade_count'] == 5
