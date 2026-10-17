import pytest
import pandas as pd
import numpy as np

def generate_expanding_folds(events_df, n_folds=5, min_train=200, block_size=50):
    """
    Simulates the walk-forward logic.
    Each fold has:
    - Train (expanding)
    - Calibration (block_size)
    - Threshold (block_size)
    - Test (block_size)
    
    Purge logic: 
    - No observation in block A can have timestamp + 1h > block B's first timestamp
      if B immediately follows A.
    """
    folds = []
    
    if len(events_df) < min_train + (3 * block_size):
        return folds # INSUFFICIENT DATA
        
    for i in range(n_folds):
        train_end_idx = min_train + (i * block_size)
        calib_end_idx = train_end_idx + block_size
        thresh_end_idx = calib_end_idx + block_size
        test_end_idx = thresh_end_idx + block_size
        
        if test_end_idx > len(events_df):
            break
            
        train = events_df.iloc[:train_end_idx].copy()
        calib = events_df.iloc[train_end_idx:calib_end_idx].copy()
        thresh = events_df.iloc[calib_end_idx:thresh_end_idx].copy()
        test = events_df.iloc[thresh_end_idx:test_end_idx].copy()
        
        # Purge overlaps
        # 1h = 3600 seconds
        purge_gap = pd.Timedelta(hours=1)
        
        calib = calib[calib['timestamp'] >= train['timestamp'].iloc[-1] + purge_gap]
        thresh = thresh[thresh['timestamp'] >= calib['timestamp'].iloc[-1] + purge_gap]
        test = test[test['timestamp'] >= thresh['timestamp'].iloc[-1] + purge_gap]
        
        # Train also needs purge against calib's first timestamp (though our logic above filters calib instead)
        # Actually proper purge drops the end of train:
        train = train[train['timestamp'] + purge_gap <= calib['timestamp'].min()]
        
        folds.append((train, calib, thresh, test))
        
    return folds

def test_purge_logic():
    # Generate 400 events spaced exactly 30 minutes apart
    # This means the last event of block A and the first of block B are only 30m apart.
    # A 1h purge should drop the last 2 events of block A.
    dates = pd.date_range("2023-01-01", periods=400, freq="30min")
    df = pd.DataFrame({'timestamp': dates, 'val': np.arange(400)})
    
    folds = generate_expanding_folds(df, n_folds=1, min_train=200, block_size=50)
    assert len(folds) == 1
    
    train, calib, thresh, test = folds[0]
    
    # Train ends at index 199 in pure slicing (time: 2023-01-05 03:30)
    # Calib starts at index 200 (time: 2023-01-05 04:00)
    # train['timestamp'].max() + 1h = 2023-01-05 04:30
    # Wait, the purge logic above: train = train[train['timestamp'] + 1h <= calib['timestamp'].min()]
    # train's max should now be strictly <= calib.min() - 1h
    
    assert train['timestamp'].max() + pd.Timedelta(hours=1) <= calib['timestamp'].min()
    assert calib['timestamp'].max() + pd.Timedelta(hours=1) <= thresh['timestamp'].min()
    assert thresh['timestamp'].max() + pd.Timedelta(hours=1) <= test['timestamp'].min()

if __name__ == "__main__":
    pytest.main([__file__])
