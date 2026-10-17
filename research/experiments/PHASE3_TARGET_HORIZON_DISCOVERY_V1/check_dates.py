import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from research.pipeline.data_loader import ResearchDataLoader

loader = ResearchDataLoader()
df = loader.load_symbol("BTCUSDT")

print(f"Start: {df['timestamp'].min()}")
print(f"End: {df['timestamp'].max()}")
import pandas as pd
print(f"Start Date: {pd.to_datetime(df['timestamp'].min(), unit='ms')}")
print(f"End Date: {pd.to_datetime(df['timestamp'].max(), unit='ms')}")
