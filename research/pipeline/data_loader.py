import os
import hashlib
import pandas as pd

class ResearchDataLoader:
    """
    Loads normalized historical data for the research pipeline.
    Maintains provenance and explicitly isolates execution from live models.
    """
    def __init__(self, data_dir: str = "data/processed/v2_fixed_timestamp"):
        self.data_dir = data_dir
        
    def load_symbol(self, symbol: str) -> pd.DataFrame:
        """
        Loads the Parquet file for a given symbol and computes basic provenance.
        """
        file_path = os.path.join(self.data_dir, f"{symbol}.parquet")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Missing historical data: {file_path}")
            
        df = pd.read_parquet(file_path)
        
        # Provenance checks
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        # Calculate naive hash of timestamps and shape to verify dataset version
        timestamp_hash = hashlib.sha256(df['timestamp'].values.tobytes()).hexdigest()[:8]
        
        print(f"[ResearchDataLoader] Loaded {symbol} | Shape: {df.shape} | Time Hash: {timestamp_hash}")
        
        # Return strict copy
        return df.copy()
