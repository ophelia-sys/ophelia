import pytest
import pandas as pd
import numpy as np
from research.phase6.labels import ForwardLabelsGenerator

def test_forward_labels():
    df = pd.DataFrame({
        'timestamp': [1, 2, 3, 4, 5],
        'close': [100, 101, 105, 102, 104],
        'high': [101, 103, 106, 103, 105],
        'low': [99, 100, 104, 100, 103]
    })
    
    gen = ForwardLabelsGenerator(horizons=[1, 2])
    result = gen.generate_labels(df)
    
    # R_1 at t=1 (idx 0, close=100) -> close at t=2 is 101
    assert np.isclose(result['R_1'].iloc[0], np.log(101/100))
    
    # MFE_2 at t=1 (idx 0, close=100) -> max high over t=2, t=3 is max(103, 106) = 106
    assert np.isclose(result['MFE_2'].iloc[0], (106 - 100) / 100)
    
    # MAE_2 at t=1 -> min low over t=2, t=3 is min(100, 104) = 100
    assert np.isclose(result['MAE_2'].iloc[0], (100 - 100) / 100)
    
def test_attach_labels():
    gen = ForwardLabelsGenerator(horizons=[1])
    events = [{"confirmation_timestamp": 2}]
    
    df_labels = pd.DataFrame({
        'timestamp': [1, 2, 3],
        'R_1': [0.1, 0.2, 0.3],
        'MFE_1': [0.15, 0.25, 0.35],
        'MAE_1': [-0.05, -0.1, -0.15]
    })
    
    enriched = gen.attach_labels_to_events(events, df_labels)
    assert enriched[0]["R_1"] == 0.2
    assert enriched[0]["MFE_1"] == 0.25
    assert enriched[0]["MAE_1"] == -0.1
