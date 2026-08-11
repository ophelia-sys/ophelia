import unittest
import pandas as pd
from unittest.mock import patch

from core.decision_engine import DecisionEngine
from core.institutional_math import InstitutionalMathEngine, MathAnalysis
from strategies.strategy import Strategy

def create_mock_df(candle_body_pct: float, timestamp: str = "2026-08-10 10:00:00") -> pd.DataFrame:
    open_price = 1000.0
    close_price = open_price * (1 + (candle_body_pct / 100.0))
    
    df = pd.DataFrame({
        "timestamp": [pd.Timestamp(timestamp)],
        "open": [open_price],
        "high": [open_price * 1.05],
        "low": [open_price * 0.95],
        "close": [close_price],
        "volume": [100.0]
    })
    return df

def generate_test_df(pct_1m: float, pct_5m: float) -> pd.DataFrame:
    # 5m pct logic is derived from open of the first minute and close of the last minute.
    # To satisfy 5m pct, the first candle opens at 1000.0
    # The last candle closes at 1000.0 * (1 + pct_5m / 100.0)
    # 1m pct logic is derived from the last candle's open and close.
    
    open_5m = 1000.0
    close_5m = open_5m * (1 + (pct_5m / 100.0))
    
    open_1m = close_5m / (1 + (pct_1m / 100.0))
    
    dfs = []
    # Create earlier candles to make a complete 5m candle
    for i in range(4): # 10:00 to 10:03
        df = pd.DataFrame({
            "timestamp": [pd.Timestamp(f"2026-08-10 10:0{i}:00")],
            "open": [open_5m],
            "high": [open_5m],
            "low": [open_5m],
            "close": [open_5m],
            "volume": [10.0]
        })
        dfs.append(df)
        
    # The final 1m candle at 10:04 finishes the 5m candle
    df_last = pd.DataFrame({
        "timestamp": [pd.Timestamp(f"2026-08-10 10:04:00")],
        "open": [open_1m],
        "high": [max(open_1m, close_5m)],
        "low": [min(open_1m, close_5m)],
        "close": [close_5m],
        "volume": [10.0]
    })
    dfs.append(df_last)
    
    return pd.concat(dfs).reset_index(drop=True)


class TestDecisionEngineBoundaries(unittest.TestCase):

    def _eval(self, pct_1m, pct_5m, kronos_dir="NEUTRAL", kronos_score=0.0):
        with patch('core.decision_engine.InstitutionalMathEngine.evaluate') as mock_math, \
             patch('external.Kronos.provider.KronosProvider.analyze') as mock_kronos:
            
            mock_math.return_value = InstitutionalMathEngine._empty_analysis()
            mock_kronos.return_value = {"direction": kronos_dir, "score": kronos_score}
            
            engine = DecisionEngine()
            df_1m_full = generate_test_df(pct_1m, pct_5m)
            signal = {"signal": Strategy.BUY, "cross": "BULLISH"}
            
            return engine.evaluate("BTC-USDT", df_1m_full, signal)

    # 1-MINUTE BOUNDARIES (0.20%, 0.40%)
    
    def test_exact_boundary_1m_0_20(self):
        result = self._eval(pct_1m=0.20, pct_5m=0.10)
        self.assertTrue(result.approved)

    def test_boundary_1m_0_200001_no_kronos(self):
        result = self._eval(pct_1m=0.200001, pct_5m=0.10)
        self.assertFalse(result.approved)
        self.assertIn("requires Kronos override", result.reason)

    def test_boundary_1m_exact_0_40_no_kronos(self):
        result = self._eval(pct_1m=0.40, pct_5m=0.10)
        self.assertFalse(result.approved)
        self.assertIn("requires Kronos override", result.reason)
        
    def test_boundary_1m_exact_0_40_with_kronos(self):
        result = self._eval(pct_1m=0.40, pct_5m=0.10, kronos_dir="BULLISH", kronos_score=0.90)
        self.assertTrue(result.approved)

    def test_boundary_1m_0_400001_always_blocks(self):
        result = self._eval(pct_1m=0.400001, pct_5m=0.10, kronos_dir="BULLISH", kronos_score=0.90)
        self.assertFalse(result.approved)
        self.assertIn("hard reject", result.reason)

    # 5-MINUTE BOUNDARIES (0.35%, 0.60%)
    
    def test_exact_boundary_5m_0_35(self):
        result = self._eval(pct_1m=0.10, pct_5m=0.35)
        self.assertTrue(result.approved)

    def test_boundary_5m_0_350001_no_kronos(self):
        result = self._eval(pct_1m=0.10, pct_5m=0.350001)
        self.assertFalse(result.approved)
        self.assertIn("5m oversized candle requires Kronos override", result.reason)

    def test_boundary_5m_exact_0_60_no_kronos(self):
        result = self._eval(pct_1m=0.10, pct_5m=0.60)
        self.assertFalse(result.approved)
        self.assertIn("requires Kronos override", result.reason)
        
    def test_boundary_5m_exact_0_60_with_kronos(self):
        result = self._eval(pct_1m=0.10, pct_5m=0.60, kronos_dir="BULLISH", kronos_score=0.90)
        self.assertTrue(result.approved)

    def test_boundary_5m_0_600001_always_blocks(self):
        result = self._eval(pct_1m=0.10, pct_5m=0.600001, kronos_dir="BULLISH", kronos_score=0.90)
        self.assertFalse(result.approved)
        self.assertIn("hard reject", result.reason)

    # KRONOS BOUNDARIES (0.77)
    
    def test_kronos_exactly_0_77(self):
        result = self._eval(pct_1m=0.30, pct_5m=0.10, kronos_dir="BULLISH", kronos_score=0.77)
        self.assertFalse(result.approved)

    def test_kronos_0_770001_passes(self):
        result = self._eval(pct_1m=0.30, pct_5m=0.10, kronos_dir="BULLISH", kronos_score=0.770001)
        self.assertTrue(result.approved)

    def test_kronos_exactly_minus_0_77(self):
        with patch('core.decision_engine.InstitutionalMathEngine.evaluate') as mock_math, \
             patch('external.Kronos.provider.KronosProvider.analyze') as mock_kronos:
            
            mock_math.return_value = InstitutionalMathEngine._empty_analysis()
            mock_kronos.return_value = {"direction": "BEARISH", "score": -0.77}
            
            engine = DecisionEngine()
            df_1m_full = generate_test_df(pct_1m=0.30, pct_5m=0.10)
            signal = {"signal": Strategy.SELL, "cross": "BEARISH"}
            
            result = engine.evaluate("BTC-USDT", df_1m_full, signal)
            self.assertFalse(result.approved)
            
    def test_kronos_minus_0_770001_passes(self):
        with patch('core.decision_engine.InstitutionalMathEngine.evaluate') as mock_math, \
             patch('external.Kronos.provider.KronosProvider.analyze') as mock_kronos:
            
            mock_math.return_value = InstitutionalMathEngine._empty_analysis()
            mock_kronos.return_value = {"direction": "BEARISH", "score": -0.770001}
            
            engine = DecisionEngine()
            df_1m_full = generate_test_df(pct_1m=0.30, pct_5m=0.10)
            signal = {"signal": Strategy.SELL, "cross": "BEARISH"}
            
            result = engine.evaluate("BTC-USDT", df_1m_full, signal)
            self.assertTrue(result.approved)

    def test_kronos_opposite_direction_blocks(self):
        result = self._eval(pct_1m=0.30, pct_5m=0.10, kronos_dir="BEARISH", kronos_score=-0.90)
        self.assertFalse(result.approved)

if __name__ == '__main__':
    unittest.main()
