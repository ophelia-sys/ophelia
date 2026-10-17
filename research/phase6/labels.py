import pandas as pd
import numpy as np
from typing import List, Dict

class ForwardLabelsGenerator:
    """
    Computes forward research labels for given horizons.
    Horizons are specified in number of periods (candles).
    """
    def __init__(self, horizons: List[int]):
        self.horizons = horizons

    def generate_labels(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generates continuous forward labels R, MFE, MAE for each horizon.
        df must contain 'close', 'high', 'low' columns.
        """
        result = df.copy()
        
        # Calculate forward labels for each horizon
        for h in self.horizons:
            # Forward returns
            # R_(t,h) = ln(C_(t+h) / C_t)
            # Use shift(-h) to bring future value back to t
            close_future = result['close'].shift(-h)
            result[f'R_{h}'] = np.log(close_future / result['close'])
            
            # MFE_(t,h) = (max H_(t+1 ... t+h) - C_t) / C_t
            # MAE_(t,h) = (min L_(t+1 ... t+h) - C_t) / C_t
            
            # Create rolling windows on the shifted (future) series.
            # rolling window looking backward from t+h to t+1
            # To do this natively in pandas without lookahead bugs during assignment:
            # We want rolling max of length h, shifted back by h.
            
            rolling_high_future = result['high'].rolling(window=h, min_periods=1).max().shift(-h)
            rolling_low_future = result['low'].rolling(window=h, min_periods=1).min().shift(-h)
            
            result[f'MFE_{h}'] = (rolling_high_future - result['close']) / result['close']
            result[f'MAE_{h}'] = (rolling_low_future - result['close']) / result['close']
            
        return result

    def attach_labels_to_events(self, events: List[Dict], labels_df: pd.DataFrame) -> List[Dict]:
        """
        Attaches calculated forward labels to discrete events based on timestamp.
        """
        if labels_df.empty:
            return events
            
        # Ensure timestamp is the index for fast lookup
        if 'timestamp' in labels_df.columns:
            labels_df = labels_df.set_index('timestamp')
            
        enriched_events = []
        for ev in events:
            t = ev["confirmation_timestamp"]
            if t in labels_df.index:
                row = labels_df.loc[t]
                
                # If there are duplicate timestamps, loc returns a dataframe. Take the last one.
                if isinstance(row, pd.DataFrame):
                    row = row.iloc[-1]
                    
                for h in self.horizons:
                    ev[f'R_{h}'] = row.get(f'R_{h}', np.nan)
                    ev[f'MFE_{h}'] = row.get(f'MFE_{h}', np.nan)
                    ev[f'MAE_{h}'] = row.get(f'MAE_{h}', np.nan)
            enriched_events.append(ev)
            
        return enriched_events
