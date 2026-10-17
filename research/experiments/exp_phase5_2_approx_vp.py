import os
import sys
import numpy as np
import pandas as pd
from numba import njit
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from research.experiments.exp_phase5_1_baseline_rerun import _compute_triple_barrier

@njit
def calc_approx_vp(m1_highs, m1_lows, m1_vols, m1_times, m5_times, window_size=1440, n_bins=100, va_pct=0.70):
    m5_len = len(m5_times)
    m1_len = len(m1_times)
    
    poc_arr = np.full(m5_len, np.nan)
    vah_arr = np.full(m5_len, np.nan)
    val_arr = np.full(m5_len, np.nan)
    
    m1_idx = 0
    
    for i in range(m5_len):
        t_5m = m5_times[i]
        
        # Advance m1_idx until it points to the first m1 candle strictly >= t_5m
        while m1_idx < m1_len and m1_times[m1_idx] < t_5m:
            m1_idx += 1
            
        start_idx = max(0, m1_idx - window_size)
        end_idx = m1_idx
        
        if end_idx - start_idx < window_size // 2:
            continue
            
        window_highs = m1_highs[start_idx:end_idx]
        window_lows = m1_lows[start_idx:end_idx]
        window_vols = m1_vols[start_idx:end_idx]
        
        mids = (window_highs + window_lows) / 2.0
        
        min_p = np.min(mids)
        max_p = np.max(mids)
        
        if max_p == min_p:
            poc_arr[i] = min_p
            vah_arr[i] = min_p
            val_arr[i] = min_p
            continue
            
        bin_width = (max_p - min_p) / n_bins
        hist = np.zeros(n_bins)
        
        for k in range(len(mids)):
            b = int((mids[k] - min_p) / bin_width)
            if b >= n_bins:
                b = n_bins - 1
            hist[b] += window_vols[k]
            
        poc_bin = np.argmax(hist)
        poc_arr[i] = min_p + (poc_bin + 0.5) * bin_width
        
        total_vol = np.sum(hist)
        target_vol = total_vol * va_pct
        accum_vol = hist[poc_bin]
        
        upper_bin = poc_bin
        lower_bin = poc_bin
        
        while accum_vol < target_vol and (upper_bin < n_bins - 1 or lower_bin > 0):
            vol_up = hist[upper_bin + 1] if upper_bin < n_bins - 1 else -1.0
            vol_dn = hist[lower_bin - 1] if lower_bin > 0 else -1.0
            
            if vol_up > vol_dn:
                upper_bin += 1
                accum_vol += vol_up
            else:
                lower_bin -= 1
                accum_vol += vol_dn
                
        vah_arr[i] = min_p + (upper_bin + 0.5) * bin_width
        val_arr[i] = min_p + (lower_bin + 0.5) * bin_width
        
    return poc_arr, vah_arr, val_arr

class Phase5ApproxVPExperiment:
    def __init__(self):
        self.data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/normalized'))
        
    def purged_walk_forward_splits(self, n_samples, n_folds=3, purge=12, embargo=12):
        fold_size = n_samples // (n_folds + 1)
        splits = []
        for i in range(n_folds):
            test_start = (i + 1) * fold_size
            test_end = (i + 2) * fold_size if i < n_folds - 1 else n_samples
            train_val_end = test_start - purge - embargo
            if train_val_end <= 0: continue
            
            val_size = max(int(fold_size * 0.2), 1)
            val_start = train_val_end - val_size
            train_end = val_start - purge - embargo
            if train_end <= 0: continue
            
            splits.append((np.arange(0, train_end), np.arange(val_start, train_val_end), np.arange(test_start, test_end)))
        return splits
        
    def load_and_prepare(self, symbol):
        df_1m = pd.read_parquet(os.path.join(self.data_dir, f'v1/binance_um_{symbol.lower()}_1m_v1.parquet'))
        df_5m = pd.read_parquet(os.path.join(self.data_dir, f'v2/binance_um_{symbol.lower()}_5m_v2.parquet'))
        
        df_1m.sort_values('timestamp', inplace=True)
        df_5m.sort_values('timestamp', inplace=True)
        
        poc, vah, val = calc_approx_vp(
            df_1m['high'].values, df_1m['low'].values, df_1m['volume'].values,
            df_1m['timestamp'].values, df_5m['timestamp'].values,
            window_size=1440, n_bins=100, va_pct=0.70
        )
        
        df_5m['vp_poc'] = poc
        df_5m['vp_vah'] = vah
        df_5m['vp_val'] = val
        
        c = df_5m['close']
        df_5m['dist_poc'] = (c - poc) / c
        df_5m['dist_vah'] = (c - vah) / c
        df_5m['dist_val'] = (c - val) / c
        df_5m['va_pos'] = (c - val) / (vah - val + 1e-8)
        
        # Base features (from Phase 5.1 BASE-5)
        df_5m['ret_1'] = c.pct_change(1)
        df_5m['ret_3'] = c.pct_change(3)
        df_5m['ret_5'] = c.pct_change(5)
        log_ret = np.log(c / c.shift(1))
        df_5m['realized_vol_20'] = log_ret.rolling(20).std() * np.sqrt(20)
        h_l = df_5m['high'] - df_5m['low']
        h_pc = (df_5m['high'] - c.shift(1)).abs()
        l_pc = (df_5m['low'] - c.shift(1)).abs()
        tr = pd.concat([h_l, h_pc, l_pc], axis=1).max(axis=1)
        df_5m['atr_14'] = tr.rolling(14).mean()
        df_5m['atr_pct_14'] = df_5m['atr_14'] / c
        df_5m['mom_10'] = log_ret.rolling(10).sum()
        v = df_5m['volume']
        df_5m['vol_ma_20'] = v.rolling(20).mean()
        df_5m['vol_ratio'] = v / (df_5m['vol_ma_20'] + 1e-8)
        
        df_5m.dropna(inplace=True)
        df_5m.reset_index(drop=True, inplace=True)
        return df_5m
        
    def evaluate(self, symbol):
        df = self.load_and_prepare(symbol)
        
        tp_arr = np.maximum(df['atr_pct_14'].values * 2.0, 0.0015)
        sl_arr = np.maximum(df['atr_pct_14'].values * 1.0, 0.0010)
        
        outcomes, exit_idxs, exit_prices = _compute_triple_barrier(
            df['high'].values, df['low'].values, df['close'].values, 
            tp_arr, sl_arr, 12, 0 # Exclude ambiguity
        )
        
        df['outcome'] = outcomes
        df['exit_price'] = exit_prices
        
        valid_mask = (df['outcome'] != 2)
        df = df[valid_mask].copy().reset_index(drop=True)
        
        df['target_long'] = (df['outcome'] == 1).astype(int)
        df['gross_ret'] = (df['exit_price'] / df['close']) - 1.0
        
        base_features = ['ret_1', 'ret_3', 'ret_5', 'realized_vol_20', 'atr_pct_14', 'mom_10', 'vol_ratio']
        vp_features = ['dist_poc', 'dist_vah', 'dist_val', 'va_pos']
        
        X_base = df[base_features].values
        X_vp = df[base_features + vp_features].values
        y = df['target_long'].values
        gross = df['gross_ret'].values
        
        splits = self.purged_walk_forward_splits(len(df), n_folds=3, purge=12, embargo=12)
        
        print(f"\\n{'='*40}\\nEvaluating {symbol}\\n{'='*40}")
        
        for model_name, X in [("MODEL A (BASE)", X_base), ("MODEL B (BASE+VP)", X_vp)]:
            brier_scores = []
            gross_returns_90 = []
            
            for train_idx, val_idx, test_idx in splits:
                scaler = StandardScaler()
                X_train = scaler.fit_transform(X[train_idx])
                X_test = scaler.transform(X[test_idx])
                
                lr = LogisticRegression(C=1.0, solver='lbfgs', max_iter=1000)
                cal = CalibratedClassifierCV(lr, method='isotonic', cv=3)
                cal.fit(X_train, y[train_idx])
                
                y_prob = cal.predict_proba(X_test)[:, 1]
                brier = brier_score_loss(y[test_idx], y_prob)
                brier_scores.append(brier)
                
                # Check top bucket (P90)
                p90 = np.percentile(y_prob, 90)
                top_mask = (y_prob >= p90)
                
                if np.sum(top_mask) > 10:
                    gross_returns_90.append(np.mean(gross[test_idx][top_mask]) * 10000)
                else:
                    gross_returns_90.append(0.0)
                    
            avg_brier = np.mean(brier_scores)
            avg_gross = np.mean(gross_returns_90)
            print(f"{model_name}: Brier={avg_brier:.5f} | Top Decile Gross={avg_gross:.2f} bps")

if __name__ == "__main__":
    exp = Phase5ApproxVPExperiment()
    for sym in ['BTCUSDT', 'ETHUSDT']:
        exp.evaluate(sym)
