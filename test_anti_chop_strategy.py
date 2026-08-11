import unittest
import pandas as pd
import numpy as np

from indicators.anti_chop import (
    calculate_atr, calculate_er, calculate_nes, calculate_nslope,
    calculate_bbs, calculate_rvol, calculate_natr, calculate_mrs
)
from external.Kronos.provider import KronosProvider
from strategies.anti_chop_ema_strategy import AntiChopEMAStrategy
from strategies.strategy import Strategy


class TestAntiChopIndicators(unittest.TestCase):
    
    def setUp(self):
        # Create a mock dataframe for indicator tests
        np.random.seed(42)
        dates = pd.date_range("2026-01-01", periods=300, freq="1min")
        
        # We need a clear upward trend for some tests
        closes = np.linspace(100, 200, 300) + np.random.normal(0, 1, 300)
        highs = closes + np.random.uniform(0.5, 2, 300)
        lows = closes - np.random.uniform(0.5, 2, 300)
        opens = closes - np.random.normal(0, 0.5, 300)
        
        self.df = pd.DataFrame({
            "timestamp": dates,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": np.random.uniform(10, 100, 300)
        })

    def test_er_calculation(self):
        er = calculate_er(self.df, period=10)
        self.assertEqual(len(er), 300)
        self.assertTrue((er.dropna() >= 0).all() and (er.dropna() <= 1.0001).all())

    def test_er_insufficient_data(self):
        short_df = self.df.iloc[:5]
        er = calculate_er(short_df, period=10)
        self.assertTrue((er == 0.0).all())
        
    def test_nes_calculation(self):
        nes = calculate_nes(self.df, 9, 21, 14)
        self.assertEqual(len(nes), 300)
        
    def test_nslope_calculation(self):
        nslope = calculate_nslope(self.df, 21, 3, 14)
        self.assertEqual(len(nslope), 300)

    def test_natr_calculation(self):
        natr = calculate_natr(self.df, 14)
        self.assertEqual(len(natr), 300)
        
    def test_rvol_calculation(self):
        rvol = calculate_rvol(self.df, 20)
        self.assertEqual(len(rvol), 300)

    def test_bbs_calculation(self):
        bbs = calculate_bbs(self.df, 20, 2.0, 50)
        self.assertEqual(len(bbs), 300)

    def test_mrs_calculation_bullish(self):
        # Create an artificial row mimicking strong bullish
        row = pd.Series({
            "close": 200, "ema9": 190, "ema21": 180, "ema200": 100,
            "er10": 0.65, "nes": 0.60, "nslope": 0.15, "rvol20": 1.5,
            "macd_hist": 0.5
        })
        prev_row = pd.Series({"macd_hist": 0.3})
        
        # Put them in a DataFrame
        df = pd.DataFrame([prev_row, row]).fillna(0) # previous won't have other columns but mrs logic handles it by getting row explicitly
        # Actually it's easier to give full columns
        df = pd.DataFrame([row, row])
        df.iloc[0, df.columns.get_loc("macd_hist")] = 0.3 # Previous macd
        
        mrs = calculate_mrs(df, 1)
        
        # Bullish Structure: ema9(190)>ema21(180) (+10), close(200)>ema200(100) (+10), ema21(180)>ema200(100) (+5) = 25
        # Efficiency: er(0.65) >= 0.60 (+20), abs(nes)(0.60) >= 0.50 (+10) = 30
        # Momentum: abs(nslope)(0.15) >= 0.12 (+15) = 15
        # MACD: 0.5 > 0.3 (+10) = 10
        # Volume: rvol(1.5) >= 1.30 (+20) = 20
        # Total bullish: 25+30+15+10+20 = 100
        
        self.assertEqual(mrs["bullish_score"], 100)
        self.assertTrue(mrs["bullish_score"] >= 65)

    def test_mrs_calculation_bearish(self):
        # Create an artificial row mimicking strong bearish
        row = pd.Series({
            "close": 50, "ema9": 90, "ema21": 100, "ema200": 200,
            "er10": 0.65, "nes": -0.60, "nslope": -0.15, "rvol20": 1.5,
            "macd_hist": -0.5
        })
        df = pd.DataFrame([row, row])
        df.iloc[0, df.columns.get_loc("macd_hist")] = -0.3 # Previous macd (less negative)
        
        mrs = calculate_mrs(df, 1)
        
        # Bearish Structure: ema9(90)<ema21(100) (+10), close(50)<ema200(200) (+10), ema21(100)<ema200(200) (+5) = 25
        # Efficiency: 30
        # Momentum: 15
        # MACD: -0.5 < -0.3 (+10 bearish)
        # Volume: 20
        # Total bearish: 100
        
        self.assertEqual(mrs["bearish_score"], 100)
        self.assertTrue(mrs["bearish_score"] >= 65)

    def test_mrs_blocks_entry(self):
        row = pd.Series({
            "close": 150, "ema9": 151, "ema21": 150, "ema200": 140, # Weak structure (10+10+5=25)
            "er10": 0.10, "nes": 0.10, "nslope": 0.01, "rvol20": 0.5, # 0 efficiency, 0 momentum, 0 vol
            "macd_hist": 0.1
        })
        df = pd.DataFrame([row, row])
        mrs = calculate_mrs(df, 1)
        self.assertEqual(mrs["bullish_score"], 25) # < 65


class MockKronosProvider:
    def __init__(self, direction="NEUTRAL", score=0.0):
        self._direction = direction
        self._score = score
        
    def analyze(self, symbol):
        return {"direction": self._direction, "score": self._score, "confidence": abs(self._score)}


class TestAntiChopStrategyLogic(unittest.TestCase):
    
    def setUp(self):
        self.strategy = AntiChopEMAStrategy()
        
        # Need at least 200 5m candles to not abort early.
        # So we need 200 * 5 = 1000 1m candles. Let's make it 1050 to be safe.
        dates = pd.date_range("2026-01-01 00:00:00", periods=1050, freq="1min")
        # Ensure latest 1m and 5m boundaries match correctly
        # The last index will be 1049 minutes after start
        
        self.df = pd.DataFrame({
            "timestamp": dates,
            "open": 100.0,
            "high": 100.0,
            "low": 100.0,
            "close": 100.0,
            "volume": 100.0
        })

    def _setup_perfect_bullish_crossover(self, candle_body_pct=0.10, candle_body_pct_5m=0.10):
        # Make the dataframe perfect for a bullish crossover on the last candle
        # EMA9 will cross EMA21.
        # We manipulate the internal _calculate_indicators function to just return what we want.
        
        # Override the indicator calculation for easy testing
        def mock_calc(df, fast, slow):
            df = df.copy()
            df["ema9"] = 100
            df["ema21"] = 90
            df["ema200"] = 80
            df["er10"] = 0.60
            df["nes"] = 0.50
            df["nslope"] = 0.10
            df["bbs"] = 0.80
            df["rvol20"] = 1.10
            df["natr14"] = 0.20
            df["macd_hist"] = 0.5
            
            # Setup a bullish cross at the end
            # Prev candle
            if len(df) > 1000: # It's 1m df
                df.at[df.index[-3], "ema9"] = 85
                df.at[df.index[-3], "ema21"] = 90
                df.at[df.index[-2], "ema9"] = 95
                df.at[df.index[-2], "ema21"] = 90
                
                # Make the candle body size as requested
                # candle_body_pct = abs(close - open) / open * 100
                # close = open * (1 + candle_body_pct / 100)
                open_price = 100.0
                close_price = open_price * (1 + candle_body_pct / 100.0)
                df.at[df.index[-2], "open"] = open_price
                df.at[df.index[-2], "close"] = close_price
            else: # It's 5m df
                open_price = 100.0
                close_price = open_price * (1 + candle_body_pct_5m / 100.0)
                df.at[df.index[-1], "open"] = open_price
                df.at[df.index[-1], "close"] = close_price
            
            return df

        self.strategy._calculate_indicators = mock_calc

    def _setup_perfect_bearish_crossover(self, candle_body_pct=0.10):
        # Override the indicator calculation for easy testing
        def mock_calc(df, fast, slow):
            df = df.copy()
            df["ema9"] = 80
            df["ema21"] = 90
            df["ema200"] = 100
            df["er10"] = 0.60
            df["nes"] = -0.50
            df["nslope"] = -0.10
            df["bbs"] = 0.80
            df["rvol20"] = 1.10
            df["natr14"] = 0.20
            df["macd_hist"] = -0.5
            
            # Setup a bearish cross at the end
            # Prev candle
            if len(df) > 1000: # It's 1m df
                df.at[df.index[-3], "ema9"] = 95
                df.at[df.index[-3], "ema21"] = 90
                df.at[df.index[-2], "ema9"] = 85
                df.at[df.index[-2], "ema21"] = 90
                
                open_price = 100.0
                close_price = open_price * (1 - candle_body_pct / 100.0)
                df.at[df.index[-2], "open"] = open_price
                df.at[df.index[-2], "close"] = close_price
            
            # Fix 5m structure logic for testing (needs close < ema21 for bearish)
            if len(df) < 1000: # It's 5m df
                df["close"] = 99.8
                df["ema21"] = 110.0
            
            return df

        self.strategy._calculate_indicators = mock_calc

    def test_normal_1m_candle_passes(self):
        self._setup_perfect_bullish_crossover(candle_body_pct=0.19)
        signal = self.strategy.get_signal(self.df)
        self.assertEqual(signal["signal"], Strategy.BUY)


    def test_er_below_threshold_blocks(self):
        self._setup_perfect_bullish_crossover(candle_body_pct=0.10)
        original_calc = self.strategy._calculate_indicators
        
        def mock_calc_er(df, fast, slow):
            df = original_calc(df, fast, slow)
            df["er10"] = 0.49 # Threshold is 0.50
            return df
            
        self.strategy._calculate_indicators = mock_calc_er
        signal = self.strategy.get_signal(self.df)
        self.assertEqual(signal["signal"], Strategy.HOLD)
        
    def test_5m_counter_trend_blocks(self):
        self._setup_perfect_bullish_crossover(candle_body_pct=0.10)
        original_calc = self.strategy._calculate_indicators
        
        def mock_calc_5m_bearish(df, fast, slow):
            df = original_calc(df, fast, slow)
            if len(df) < 1000: # This is the 5m df
                df.at[df.index[-1], "close"] = 80 # close < ema21(90)
                df.at[df.index[-1], "nslope"] = -0.1 # Slope is down
            return df
            
        self.strategy._calculate_indicators = mock_calc_5m_bearish
        signal = self.strategy.get_signal(self.df)
        self.assertEqual(signal["signal"], Strategy.HOLD)
        self.assertIn("5m structure failed", signal.get("reason", ""))




if __name__ == '__main__':
    unittest.main()
