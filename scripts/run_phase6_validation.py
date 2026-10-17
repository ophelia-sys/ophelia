from research.phase6.pipeline import ResearchPipeline
import pandas as pd
import numpy as np

def run_mock_validation():
    print("Initiating Phase 6 Historical Validation Pipeline...")
    
    # Simulating data limitation: we don't have historical OFI or Microprice
    df = pd.DataFrame({
        'timestamp': np.arange(0, 86400, 60), # 1 day of 1m candles
        'open': np.random.randn(1440).cumsum() + 100,
        'high': np.random.randn(1440).cumsum() + 101,
        'low': np.random.randn(1440).cumsum() + 99,
        'close': np.random.randn(1440).cumsum() + 100,
        'volume': np.random.randint(10, 1000, 1440)
    })
    
    # Ensure OHLC validity for the mock data
    df['high'] = df[['open', 'close', 'high']].max(axis=1)
    df['low'] = df[['open', 'close', 'low']].min(axis=1)
    
    atr = pd.Series(np.ones(1440))
    
    pipeline = ResearchPipeline()
    results = pipeline.run_pipeline(df, atr)
    
    print(f"Audit: {results['audit']['status']}")
    print(f"Events Generated: {results['events_count']}")
    print(f"Power: {results['power']['status']}")
    
if __name__ == "__main__":
    run_mock_validation()
