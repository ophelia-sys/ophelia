import numpy as np
import pandas as pd

class EconomicEngine:
    @staticmethod
    def calculate_mae_mfe(df: pd.DataFrame, entry_idx: int, exit_idx: int, is_long: bool):
        """
        Calculates Maximum Adverse Excursion (MAE) and Maximum Favorable Excursion (MFE)
        between entry_idx and exit_idx (inclusive).
        Assumes df has 'high', 'low', 'close'.
        """
        if entry_idx > exit_idx or exit_idx >= len(df):
            return 0.0, 0.0
            
        entry_price = df['close'].iloc[entry_idx]
        
        # Slicing the period
        period_high = df['high'].iloc[entry_idx:exit_idx+1].max()
        period_low = df['low'].iloc[entry_idx:exit_idx+1].min()
        
        if is_long:
            mfe = (period_high / entry_price) - 1.0
            mae = (period_low / entry_price) - 1.0
        else:
            mfe = 1.0 - (period_low / entry_price)
            mae = 1.0 - (period_high / entry_price)
            
        return mae, mfe

    @staticmethod
    def calculate_cost_curve(gross_returns: list, costs_bps: list):
        """
        Calculates net return and identifies break-even cost.
        """
        curve = {}
        for c in costs_bps:
            cost_frac = c / 10000.0
            curve[c] = [g - cost_frac for g in gross_returns]
            
        # Break-even is the mean gross return in bps
        break_even_bps = np.mean(gross_returns) * 10000.0
        return curve, break_even_bps

    @staticmethod
    def simulate_entry(df: pd.DataFrame, signal_idx: int, delay_candles: int = 0, is_long: bool = True):
        """
        Simulates entry execution.
        If delay_candles = 0, entry is on the close of the signal candle (immediate).
        If delay_candles > 0, entry is on the close of the delayed candle.
        Returns the entry index and entry price. Returns None if invalid.
        """
        entry_idx = signal_idx + delay_candles
        if entry_idx >= len(df):
            return None, None
            
        entry_price = df['close'].iloc[entry_idx]
        return entry_idx, entry_price

    @staticmethod
    def simulate_pullback_entry(df: pd.DataFrame, signal_idx: int, limit_price: float, max_wait: int, is_long: bool):
        """
        Simulates a limit order placed at limit_price for max_wait candles.
        If the candle low <= limit_price (for long) or high >= limit_price (for short), it fills.
        If the candle opens beyond the limit price, the fill is considered ambiguous or guaranteed at open.
        We take the conservative assumption: if it opens below limit (for long), filled at open.
        If high < limit (for long) and never touches, no fill.
        """
        for i in range(1, max_wait + 1):
            idx = signal_idx + i
            if idx >= len(df):
                break
                
            row = df.iloc[idx]
            
            if is_long:
                if row['low'] <= limit_price:
                    # Conservative fill: if it opened below limit, fill at open. Otherwise limit.
                    fill_price = row['open'] if row['open'] < limit_price else limit_price
                    return idx, fill_price, False
            else:
                if row['high'] >= limit_price:
                    fill_price = row['open'] if row['open'] > limit_price else limit_price
                    return idx, fill_price, False
                    
        return None, None, True # Missed opportunity

    @staticmethod
    def evaluate_barriers(df: pd.DataFrame, entry_idx: int, target_pct: float, stop_pct: float, is_long: bool, max_horizon: int):
        """
        Research-only barrier logic to predict P(T1 before SL).
        """
        entry_price = df['close'].iloc[entry_idx]
        
        for i in range(1, max_horizon + 1):
            idx = entry_idx + i
            if idx >= len(df):
                break
                
            row = df.iloc[idx]
            
            if is_long:
                high_ret = (row['high'] / entry_price) - 1.0
                low_ret = (row['low'] / entry_price) - 1.0
                
                if low_ret <= -stop_pct and high_ret >= target_pct:
                    # Ambiguous bar: touched both target and stop
                    return 'AMBIGUOUS', idx
                elif low_ret <= -stop_pct:
                    return 'STOP', idx
                elif high_ret >= target_pct:
                    return 'TARGET', idx
            else:
                high_ret = (row['high'] / entry_price) - 1.0
                low_ret = (row['low'] / entry_price) - 1.0
                
                if high_ret >= stop_pct and low_ret <= -target_pct:
                    return 'AMBIGUOUS', idx
                elif high_ret >= stop_pct:
                    return 'STOP', idx
                elif low_ret <= -target_pct:
                    return 'TARGET', idx
                    
        return 'EXPIRED', entry_idx + max_horizon
