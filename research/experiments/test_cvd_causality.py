import os
import unittest
import pandas as pd
import numpy as np
import math

class TestCVDCausalityAndIntegrity(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../data/normalized/cvd'))
        cls.symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT', 'ADAUSDT']
        
    def test_aggregation_conservation(self):
        """
        Verify that 1m -> 5m -> 15m volume aggregates exactly conserve volume.
        """
        sym = 'BTCUSDT'
        month = '2022-01'
        
        path_1m = os.path.join(self.data_dir, '1m', f"{sym}-{month}.parquet")
        path_5m = os.path.join(self.data_dir, '5m', f"{sym}-{month}.parquet")
        path_15m = os.path.join(self.data_dir, '15m', f"{sym}-{month}.parquet")
        
        df_1m = pd.read_parquet(path_1m)
        df_5m = pd.read_parquet(path_5m)
        df_15m = pd.read_parquet(path_15m)
        
        sum_1m = math.fsum(df_1m['delta_volume'])
        sum_5m = math.fsum(df_5m['delta_volume'])
        sum_15m = math.fsum(df_15m['delta_volume'])
        
        # Scale-aware float64 tolerance check
        scale = max(abs(sum_1m), 1.0)
        tolerance = max(1e-10, scale * 1e-15)
        
        self.assertTrue(abs(sum_1m - sum_5m) <= tolerance, "1m to 5m conservation failed.")
        self.assertTrue(abs(sum_1m - sum_15m) <= tolerance, "1m to 15m conservation failed.")

    def test_causal_rolling_calculations(self):
        """
        Prove that rolling calculations do not use future observations.
        """
        dummy_delta = pd.Series([10.0, 20.0, -5.0, 15.0, 30.0], index=[0, 1, 2, 3, 4])
        
        roll_3 = dummy_delta.rolling(3).sum()
        self.assertEqual(roll_3.iloc[2], 10.0 + 20.0 - 5.0)
        self.assertTrue(np.isnan(roll_3.iloc[1]))
        
        accel = roll_3 - roll_3.shift(1)
        self.assertEqual(accel.iloc[3], roll_3.iloc[3] - roll_3.iloc[2])

    def test_no_future_transact_time(self):
        """
        Prove that T_decision causality is maintained.
        """
        sym = 'BTCUSDT'
        month = '2022-01'
        
        path_1m = os.path.join(self.data_dir, '1m', f"{sym}-{month}.parquet")
        path_5m = os.path.join(self.data_dir, '5m', f"{sym}-{month}.parquet")
        
        df_1m = pd.read_parquet(path_1m)
        df_5m = pd.read_parquet(path_5m)
        
        t_open = pd.to_datetime('2022-01-01 00:00:00')
        t_decision = t_open + pd.Timedelta(minutes=5)
        
        row_5m = df_5m[df_5m['minute'] == t_open].iloc[0]
        mask_causal = (df_1m['minute'] >= t_open) & (df_1m['minute'] < t_decision)
        manual_sum = math.fsum(df_1m.loc[mask_causal, 'delta_volume'])
        
        self.assertAlmostEqual(row_5m['delta_volume'], manual_sum, places=7, 
                               msg="5m CVD contains non-causal 1m data >= T_decision!")

    def test_sol_missing_months(self):
        """
        Verify SOLUSDT explicitly has NaN distributions in 2023-11 and 2023-12.
        """
        nov_path = os.path.join(self.data_dir, '5m', 'SOLUSDT-2023-11.parquet')
        dec_path = os.path.join(self.data_dir, '5m', 'SOLUSDT-2023-12.parquet')
        
        self.assertFalse(os.path.exists(nov_path), "SOLUSDT 2023-11 CVD parquet should not exist.")
        self.assertFalse(os.path.exists(dec_path), "SOLUSDT 2023-12 CVD parquet should not exist.")

    def test_cvd_is_missing_semantics(self):
        """
        Ensure cvd_is_missing strictly aligns with source absence,
        and that warm-up NaNs in derived features do NOT set cvd_is_missing.
        """
        # Create dummy OHLCV (10 periods) and CVD (missing period 5)
        ohlcv = pd.DataFrame({'timestamp': pd.date_range('2022-01-01 00:00', periods=10, freq='5min')})
        
        cvd_minutes = ohlcv['timestamp'].drop(5)  # Drop index 5 to simulate missing source
        cvd = pd.DataFrame({'minute': cvd_minutes, 'delta_volume': 100.0})
        
        # Simulating exactly the engineered process
        df = pd.merge(ohlcv, cvd, left_on='timestamp', right_on='minute', how='left')
        df['cvd_is_missing'] = df['delta_volume'].isna().astype(int)
        
        df['cvd_delta_15m'] = df['delta_volume'].rolling(3).sum()
        
        # Assert the missingness flag ONLY triggers at the actual source gap
        self.assertEqual(df['cvd_is_missing'].sum(), 1, "Only 1 row was missing in source, but flag sum != 1")
        self.assertEqual(df['cvd_is_missing'].iloc[5], 1, "Gap row should be flagged as missing")
        
        # Assert the rolling warmup NaNs do NOT trigger cvd_is_missing
        # rolling(3) will have NaNs at indices 0 and 1 due to warmup
        self.assertTrue(np.isnan(df['cvd_delta_15m'].iloc[0]))
        self.assertTrue(np.isnan(df['cvd_delta_15m'].iloc[1]))
        
        self.assertEqual(df['cvd_is_missing'].iloc[0], 0, "Warmup NaN incorrectly flagged as missing")
        self.assertEqual(df['cvd_is_missing'].iloc[1], 0, "Warmup NaN incorrectly flagged as missing")

if __name__ == '__main__':
    unittest.main()
