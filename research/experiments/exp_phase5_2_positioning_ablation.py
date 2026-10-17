import os
import sys
import json
import numpy as np
import pandas as pd
from numba import njit
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import log_loss, brier_score_loss

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

@njit
def _compute_triple_barrier(highs, lows, closes, target_pcts, stop_pcts, max_horizon, ambiguity_policy):
    # ambiguity_policy: 0 = EXCLUDE, 1 = STOP_FIRST
    n = len(closes)
    outcomes = np.zeros(n, dtype=np.int8)  # 1=UP, -1=DOWN, 0=TIMEOUT, 2=AMBIGUOUS_EXCLUDE
    exit_idx = np.zeros(n, dtype=np.int32)
    exit_prices = np.zeros(n, dtype=np.float64)
    
    for i in range(n):
        entry_price = closes[i]
        tp = target_pcts[i]
        sl = stop_pcts[i]
        
        reached_outcome = 0
        reached_idx = min(i + max_horizon, n - 1)
        reached_price = closes[reached_idx] 
        
        for j in range(1, max_horizon + 1):
            curr_idx = i + j
            if curr_idx >= n:
                reached_idx = n - 1
                reached_price = closes[reached_idx]
                break
                
            h = highs[curr_idx]
            l = lows[curr_idx]
            
            hit_up = (h / entry_price - 1.0) >= tp
            hit_dn = (l / entry_price - 1.0) <= -sl
            
            if hit_up and hit_dn:
                reached_idx = curr_idx
                if ambiguity_policy == 0:
                    reached_outcome = 2
                    reached_price = np.nan
                elif ambiguity_policy == 1:
                    reached_outcome = -1
                    reached_price = entry_price * (1.0 - sl)
                break
            elif hit_up:
                reached_outcome = 1
                reached_idx = curr_idx
                reached_price = entry_price * (1.0 + tp)
                break
            elif hit_dn:
                reached_outcome = -1
                reached_idx = curr_idx
                reached_price = entry_price * (1.0 - sl)
                break
                
        outcomes[i] = reached_outcome
        exit_idx[i] = reached_idx
        exit_prices[i] = reached_price
        
    return outcomes, exit_idx, exit_prices


class Phase5PositioningAblation:
    def __init__(self):
        self.data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data'))
        self.results_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../results'))
        os.makedirs(self.results_dir, exist_ok=True)
        
    def load_ohlcv(self, symbol):
        path = os.path.join(self.data_dir, 'normalized', 'v2', f"binance_um_{symbol.lower()}_5m_v2.parquet")
        df = pd.read_parquet(path)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.sort_values('timestamp', inplace=True)
        return df
        
    def load_positioning(self, symbol):
        norm_dir = os.path.join(self.data_dir, 'normalized', 'positioning')
        
        # Metrics
        df_m = pd.read_parquet(os.path.join(norm_dir, f"{symbol}_metrics.parquet"))
        df_m['create_time'] = pd.to_datetime(df_m['create_time'])
        df_m.sort_values('create_time', inplace=True)
        
        # Premium Index
        df_p = pd.read_parquet(os.path.join(norm_dir, f"{symbol}_premiumIndex.parquet"))
        df_p['datetime'] = pd.to_datetime(df_p['datetime'])
        df_p.sort_values('datetime', inplace=True)
        
        # Funding
        df_f = pd.read_parquet(os.path.join(norm_dir, f"{symbol}_fundingRate.parquet"))
        df_f['datetime'] = pd.to_datetime(df_f['datetime'])
        df_f.sort_values('datetime', inplace=True)
        
        return df_m, df_p, df_f
        
    def causal_join(self, df_ohlcv, df_m, df_p, df_f):
        df = df_ohlcv.copy()
        
        # Metrics: Join on create_time == timestamp
        df_m_renamed = df_m[['create_time', 'sum_open_interest', 'count_long_short_ratio']].rename(
            columns={'create_time': 'timestamp', 'sum_open_interest': 'oi', 'count_long_short_ratio': 'lsr'}
        )
        df = pd.merge(df, df_m_renamed, on='timestamp', how='left')
        
        # Premium: Join on open_time == timestamp
        df_p_renamed = df_p[['datetime', 'close']].rename(
            columns={'datetime': 'timestamp', 'close': 'premium'}
        )
        df = pd.merge(df, df_p_renamed, on='timestamp', how='left')
        
        # Funding: As-of join calc_time <= timestamp
        df_f_renamed = df_f[['datetime', 'last_funding_rate']].rename(
            columns={'datetime': 'funding_timestamp', 'last_funding_rate': 'funding_rate'}
        )
        df = pd.merge_asof(df, df_f_renamed, left_on='timestamp', right_on='funding_timestamp', direction='backward')
        
        return df
        
    def engineer_base_features(self, df):
        c = df['close']
        df['ret_1'] = c.pct_change(1)
        df['ret_3'] = c.pct_change(3)
        df['ret_5'] = c.pct_change(5)
        df['log_ret'] = np.log(c / c.shift(1))
        df['realized_vol_20'] = df['log_ret'].rolling(20).std() * np.sqrt(20)
        
        h_l = df['high'] - df['low']
        h_pc = (df['high'] - c.shift(1)).abs()
        l_pc = (df['low'] - c.shift(1)).abs()
        tr = pd.concat([h_l, h_pc, l_pc], axis=1).max(axis=1)
        df['atr_14'] = tr.rolling(14).mean()
        df['atr_pct_14'] = df['atr_14'] / c
        df['mom_10'] = df['log_ret'].rolling(10).sum()
        
        v = df['volume']
        df['vol_ma_20'] = v.rolling(20).mean()
        df['vol_ratio'] = v / (df['vol_ma_20'] + 1e-8)
        
        return df

    def engineer_positioning_features(self, df, oi_stale_mins=1440, prem_stale_mins=60):
        # Time helpers
        ts = df['timestamp']
        
        # Forward fill tracks
        # For OI
        df['oi_ff'] = df['oi'].ffill()
        df['oi_last_ts'] = df['timestamp'].where(~df['oi'].isna()).ffill()
        df['oi_age'] = (ts - df['oi_last_ts']).dt.total_seconds() / 60.0
        df['oi_is_missing'] = (df['oi_age'] > oi_stale_mins).astype(int)
        df['oi_is_missing'] = np.where(df['oi_last_ts'].isna(), 1, df['oi_is_missing'])
        
        df['oi_zscore_1d'] = (df['oi_ff'] - df['oi_ff'].rolling(288).mean()) / (df['oi_ff'].rolling(288).std() + 1e-8)
        df['oi_pct_change_1h'] = df['oi_ff'].pct_change(12)
        
        # For LSR
        df['lsr_ff'] = df['lsr'].ffill()
        df['lsr_last_ts'] = df['timestamp'].where(~df['lsr'].isna()).ffill()
        df['lsr_age'] = (ts - df['lsr_last_ts']).dt.total_seconds() / 60.0
        df['lsr_is_missing'] = (df['lsr_age'] > oi_stale_mins).astype(int)
        df['lsr_is_missing'] = np.where(df['lsr_last_ts'].isna(), 1, df['lsr_is_missing'])
        
        df['lsr_zscore_1d'] = (df['lsr_ff'] - df['lsr_ff'].rolling(288).mean()) / (df['lsr_ff'].rolling(288).std() + 1e-8)
        df['lsr_change_1h'] = df['lsr_ff'].diff(12)
        
        # For Premium Index
        df['premium_ff'] = df['premium'].ffill()
        df['premium_last_ts'] = df['timestamp'].where(~df['premium'].isna()).ffill()
        df['premium_age'] = (ts - df['premium_last_ts']).dt.total_seconds() / 60.0
        df['premium_is_missing'] = (df['premium_age'] > prem_stale_mins).astype(int)
        df['premium_is_missing'] = np.where(df['premium_last_ts'].isna(), 1, df['premium_is_missing'])
        
        df['premium_level'] = df['premium_ff']
        df['premium_zscore_1d'] = (df['premium_ff'] - df['premium_ff'].rolling(288).mean()) / (df['premium_ff'].rolling(288).std() + 1e-8)
        df['premium_change_1h'] = df['premium_ff'].diff(12)
        
        # For Funding
        df['funding_rate_last'] = df['funding_rate']
        df['funding_age'] = (ts - df['funding_timestamp']).dt.total_seconds() / 60.0
        
        # Impute early NaNs in forward-filled columns with 0.0 just to make LogisticRegression run. 
        # The is_missing flag will be 1, so the model learns it's uninformative.
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        cols_to_zero = ['oi_zscore_1d', 'oi_pct_change_1h', 'lsr_zscore_1d', 'lsr_change_1h', 
                        'premium_level', 'premium_zscore_1d', 'premium_change_1h', 'funding_rate_last']
        for c in cols_to_zero:
            df[c] = df[c].fillna(0.0)
            
        # Also fill ages for the very first few rows where it's NaN
        df['oi_age'] = df['oi_age'].fillna(oi_stale_mins + 1)
        df['lsr_age'] = df['lsr_age'].fillna(oi_stale_mins + 1)
        df['premium_age'] = df['premium_age'].fillna(prem_stale_mins + 1)
        df['funding_age'] = df['funding_age'].fillna(480.0)
        
        return df

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
            
            train_idx = np.arange(0, train_end)
            val_idx = np.arange(val_start, train_val_end)
            test_idx = np.arange(test_start, test_end)
            splits.append((train_idx, val_idx, test_idx))
        return splits
        
    def evaluate_buckets(self, y_true, y_prob, gross_ret, costs_bps):
        bins = np.linspace(0, 1, 11)
        bin_ids = np.digitize(y_prob, bins) - 1
        buckets = []
        for i in range(10):
            mask = (bin_ids == i)
            n_obs = int(mask.sum())
            if n_obs > 0:
                mean_p = float(y_prob[mask].mean())
                emp_freq = float(y_true[mask].mean())
                tr = gross_ret[mask]
                mean_gross = float(np.mean(tr) * 10000) if len(tr) > 0 else 0.0
                
                bucket_info = {
                    "bucket": f"0.{i}-0.{i+1}",
                    "n_obs": n_obs,
                    "mean_prob": mean_p,
                    "emp_freq": emp_freq,
                    "mean_gross_bps": mean_gross,
                }
                for c in costs_bps:
                    bucket_info[f"mean_net_bps_cost_{c}"] = mean_gross - c
                buckets.append(bucket_info)
        return buckets

    def run_experiment(self, symbols):
        costs_bps = [0, 5, 8, 12, 15, 20, 25]
        horizon = 12
        purge = 12
        emb = 12
        n_folds = 3
        tp = 2.0
        sl = 1.0
        ambig = 0
        
        base_features = ['ret_1', 'ret_3', 'ret_5', 'realized_vol_20', 'atr_pct_14', 'mom_10', 'vol_ratio']
        oi_features = ['oi_zscore_1d', 'oi_pct_change_1h', 'oi_age', 'oi_is_missing']
        lsr_features = ['lsr_zscore_1d', 'lsr_change_1h', 'lsr_age', 'lsr_is_missing']
        premium_features = ['premium_level', 'premium_zscore_1d', 'premium_change_1h', 'premium_age', 'premium_is_missing']
        funding_features = ['funding_rate_last', 'funding_age']
        missingness_only = ['oi_is_missing', 'premium_is_missing', 'lsr_is_missing']
        
        models = {
            'MODEL_A_BASE': base_features,
            'MODEL_B_OI': base_features + oi_features,
            'MODEL_C_FUNDING': base_features + funding_features,
            'MODEL_D_PREMIUM': base_features + premium_features,
            'MODEL_E_LSR': base_features + lsr_features,
            'MODEL_F_OI_FUNDING': base_features + oi_features + funding_features,
            'MODEL_G_FULL': base_features + oi_features + funding_features + premium_features + lsr_features,
            'MODEL_MISSINGNESS': base_features + missingness_only
        }
        
        manifest = {
            "name": "Phase 5.2 Positioning Ablation",
            "dataset": "5m_v2",
            "timeframe": "2022-2023",
            "costs_bps": costs_bps,
            "horizon": horizon,
            "purge": purge,
            "embargo": emb,
            "tp_atr": tp,
            "sl_atr": sl,
            "stale_thresholds": {"oi_mins": 1440, "lsr_mins": 1440, "premium_mins": 60},
            "rolling_windows": {"oi_zscore": 288, "lsr_zscore": 288, "premium_zscore": 288},
            "models": list(models.keys()),
            "results": {}
        }

        for sym in symbols:
            print(f"\\n{'='*50}\\nProcessing {sym}\\n{'='*50}")
            df_ohlcv = self.load_ohlcv(sym)
            df_m, df_p, df_f = self.load_positioning(sym)
            
            df = self.causal_join(df_ohlcv, df_m, df_p, df_f)
            df = self.engineer_base_features(df)
            df = self.engineer_positioning_features(df)
            
            # Base valid universe (require base features)
            df.dropna(subset=base_features, inplace=True)
            df.reset_index(drop=True, inplace=True)
            
            tp_arr = np.maximum(df['atr_pct_14'].values * tp, 0.0015)
            sl_arr = np.maximum(df['atr_pct_14'].values * sl, 0.0010)
            highs = df['high'].values
            lows = df['low'].values
            closes = df['close'].values
            
            outcomes, exit_idxs, exit_prices = _compute_triple_barrier(highs, lows, closes, tp_arr, sl_arr, horizon, ambig)
            
            df['outcome'] = outcomes
            df['exit_price'] = exit_prices
            
            valid_mask = (outcomes != 2)
            df_valid = df[valid_mask].copy().reset_index(drop=True)
            
            df_valid['target_long'] = (df_valid['outcome'] == 1).astype(int)
            df_valid['gross_ret'] = (df_valid['exit_price'] / df_valid['close']) - 1.0
            
            manifest["results"][sym] = {}
            y = df_valid['target_long'].values
            gross_ret = df_valid['gross_ret'].values
            splits = self.purged_walk_forward_splits(len(df_valid), n_folds=n_folds, purge=purge, embargo=emb)
            
            for model_name, features in models.items():
                print(f"  Training {model_name}...")
                X = df_valid[features].values
                fold_results = []
                
                for i, (train_idx, val_idx, test_idx) in enumerate(splits):
                    X_train, y_train = X[train_idx], y[train_idx]
                    X_test, y_test = X[test_idx], y[test_idx]
                    
                    scaler = StandardScaler()
                    X_train_scaled = scaler.fit_transform(X_train)
                    X_test_scaled = scaler.transform(X_test)
                    
                    base_rate = y_train.mean()
                    y_prob_naive = np.full(len(y_test), base_rate)
                    
                    lr = LogisticRegression(C=1.0, solver='lbfgs', max_iter=1000)
                    lr.fit(X_train_scaled, y_train)
                    
                    cal_iso = CalibratedClassifierCV(lr, method='isotonic', cv=3)
                    cal_iso.fit(X_train_scaled, y_train)
                    y_prob_iso = cal_iso.predict_proba(X_test_scaled)[:, 1]
                    
                    test_gross = gross_ret[test_idx]
                    brier = float(brier_score_loss(y_test, y_prob_iso))
                    ll = float(log_loss(y_test, y_prob_iso))
                    
                    # Top quintile stats
                    q80 = np.percentile(y_prob_iso, 80)
                    high_prob_mask = (y_prob_iso >= q80)
                    if high_prob_mask.sum() > 0:
                        high_prob_gross = float(np.mean(test_gross[high_prob_mask]) * 10000)
                    else:
                        high_prob_gross = 0.0
                        
                    fold_results.append({
                        "brier_iso": brier,
                        "log_loss_iso": ll,
                        "high_prob_gross_bps": high_prob_gross,
                        "buckets": self.evaluate_buckets(y_test, y_prob_iso, test_gross, costs_bps)
                    })
                
                avg_brier = np.mean([f['brier_iso'] for f in fold_results])
                avg_gross = np.mean([f['high_prob_gross_bps'] for f in fold_results])
                
                manifest["results"][sym][model_name] = {
                    "avg_brier_iso": avg_brier,
                    "avg_high_prob_gross_bps": avg_gross,
                    "folds": fold_results
                }
                
        with open(os.path.join(self.results_dir, "PHASE5_2_POSITIONING_ABLATION.json"), "w") as f:
            json.dump(manifest, f, indent=2)

if __name__ == "__main__":
    exp = Phase5PositioningAblation()
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT', 'ADAUSDT']
    exp.run_experiment(symbols)
