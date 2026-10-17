import os
import sys
import json
import numpy as np
import pandas as pd
from numba import njit
from sklearn.linear_model import LogisticRegression
from sklearn.dummy import DummyClassifier
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
        reached_price = closes[reached_idx] # Default timeout price
        
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


class Phase5BaselineRerun:
    def __init__(self):
        self.data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/normalized/v2'))
        self.results_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../results'))
        os.makedirs(self.results_dir, exist_ok=True)
        
    def load_data(self, symbol, timeframe="5m"):
        path = os.path.join(self.data_dir, f"binance_um_{symbol.lower()}_{timeframe}_v2.parquet")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing {path}")
        df = pd.read_parquet(path)
        df.sort_values('timestamp', inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df
        
    def engineer_features(self, df):
        df = df.copy()
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
        
        df.dropna(subset=['ret_5', 'realized_vol_20', 'atr_pct_14', 'mom_10', 'vol_ratio'], inplace=True)
        df.reset_index(drop=True, inplace=True)
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
        
    def get_prob_distribution(self, y_prob):
        if len(y_prob) == 0:
            return {}
        return {
            "min": float(np.min(y_prob)),
            "max": float(np.max(y_prob)),
            "mean": float(np.mean(y_prob)),
            "std": float(np.std(y_prob)),
            "median": float(np.median(y_prob)),
            "P10": float(np.percentile(y_prob, 10)),
            "P25": float(np.percentile(y_prob, 25)),
            "P50": float(np.percentile(y_prob, 50)),
            "P75": float(np.percentile(y_prob, 75)),
            "P90": float(np.percentile(y_prob, 90)),
            "P95": float(np.percentile(y_prob, 95)),
            "P99": float(np.percentile(y_prob, 99)),
        }
        
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

    def run_experiment(self, symbol="BTCUSDT"):
        print(f"\\n{'='*50}\\nStarting Rerun Baseline for {symbol}\\n{'='*50}")
        df = self.load_data(symbol)
        df = self.engineer_features(df)
        
        feature_sets = {
            'BASE-0': [],
            'BASE-1': ['ret_1', 'ret_3', 'ret_5'],
            'BASE-2': ['ret_1', 'ret_3', 'ret_5', 'realized_vol_20'],
            'BASE-3': ['ret_1', 'ret_3', 'ret_5', 'realized_vol_20', 'atr_pct_14'],
            'BASE-4': ['ret_1', 'ret_3', 'ret_5', 'realized_vol_20', 'atr_pct_14', 'mom_10'],
            'BASE-5': ['ret_1', 'ret_3', 'ret_5', 'realized_vol_20', 'atr_pct_14', 'mom_10', 'vol_ratio']
        }
        
        costs_bps = [0, 5, 8, 12, 15, 20, 25]
        horizon = 12
        purge = 12
        n_folds = 3
        
        manifest = {
            "symbol": symbol,
            "dataset": "5m_v2",
            "timeframe": "2022-2023",
            "costs_bps": costs_bps,
            "results": []
        }
        
        # Primary combinations (BASE-0 to BASE-5) on default params (TP=2.0, SL=1.0, Emb=12, Pol=EXCLUDE)
        combinations = []
        for fset in feature_sets.keys():
            combinations.append((fset, 2.0, 1.0, 12, 0))
            
        # Sensitivities for BASE-5
        combinations.extend([
            ('BASE-5', 2.0, 1.0, 24, 0),
            ('BASE-5', 2.0, 1.0, 60, 0),
            ('BASE-5', 1.5, 1.0, 12, 0),
            ('BASE-5', 1.0, 1.0, 12, 0),
            ('BASE-5', 2.0, 1.0, 12, 1) # STOP_FIRST policy
        ])
        
        manual_trace = []
        
        for config in combinations:
            fset_name, tp, sl, emb, ambig = config
            print(f"\\nRunning {fset_name} | TP={tp} SL={sl} | Emb={emb} | Ambig={'EXCLUDE' if ambig==0 else 'STOP_FIRST'}")
            
            tp_arr = np.maximum(df['atr_pct_14'].values * tp, 0.0015)
            sl_arr = np.maximum(df['atr_pct_14'].values * sl, 0.0010)
            highs = df['high'].values
            lows = df['low'].values
            closes = df['close'].values
            
            outcomes, exit_idxs, exit_prices = _compute_triple_barrier(highs, lows, closes, tp_arr, sl_arr, horizon, ambig)
            
            df_lbl = df.copy()
            df_lbl['outcome'] = outcomes
            df_lbl['exit_idx'] = exit_idxs
            df_lbl['exit_price'] = exit_prices
            
            # Label distribution stats
            n_tot = len(outcomes)
            n_ambig = np.sum(outcomes == 2)
            lbl_dist = {
                "P(+1)": float(np.sum(outcomes == 1) / n_tot),
                "P(-1)": float(np.sum(outcomes == -1) / n_tot),
                "P(0)": float(np.sum(outcomes == 0) / n_tot),
                "P(AMBIG)": float(n_ambig / n_tot)
            }
            
            # Exclude ambiguous
            valid_mask = (outcomes != 2)
            df_valid = df_lbl[valid_mask].copy().reset_index(drop=True)
            
            df_valid['target_long'] = (df_valid['outcome'] == 1).astype(int)
            df_valid['gross_ret'] = (df_valid['exit_price'] / df_valid['close']) - 1.0
            
            features = feature_sets[fset_name]
            X = df_valid[features].values if len(features) > 0 else np.ones((len(df_valid), 1))
            y = df_valid['target_long'].values
            gross_ret = df_valid['gross_ret'].values
            
            splits = self.purged_walk_forward_splits(len(df_valid), n_folds=n_folds, purge=purge, embargo=emb)
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
                
                if len(features) > 0:
                    lr.fit(X_train_scaled, y_train)
                    y_prob_uncal = lr.predict_proba(X_test_scaled)[:, 1]
                    
                    cal_iso = CalibratedClassifierCV(lr, method='isotonic', cv=3)
                    cal_iso.fit(X_train_scaled, y_train)
                    y_prob_iso = cal_iso.predict_proba(X_test_scaled)[:, 1]
                    
                    cal_sig = CalibratedClassifierCV(lr, method='sigmoid', cv=3)
                    cal_sig.fit(X_train_scaled, y_train)
                    y_prob_sig = cal_sig.predict_proba(X_test_scaled)[:, 1]
                else:
                    y_prob_uncal = y_prob_naive
                    y_prob_iso = y_prob_naive
                    y_prob_sig = y_prob_naive
                
                # Metrics (Using Isotonic as Primary)
                test_gross = gross_ret[test_idx]
                
                metrics = {
                    "brier_naive": float(brier_score_loss(y_test, y_prob_naive)),
                    "brier_iso": float(brier_score_loss(y_test, y_prob_iso)),
                    "dist_iso": self.get_prob_distribution(y_prob_iso),
                    "dist_sig": self.get_prob_distribution(y_prob_sig),
                    "dist_uncal": self.get_prob_distribution(y_prob_uncal),
                    "buckets_iso": self.evaluate_buckets(y_test, y_prob_iso, test_gross, costs_bps)
                }
                
                # Manual Trace capture
                if len(manual_trace) < 20 and fset_name == 'BASE-5' and tp == 2.0 and ambig == 0:
                    # Select positive predictions above base rate
                    strong_idx = np.where(y_prob_iso > base_rate)[0]
                    for s_idx in strong_idx[:5]:
                        row = df_valid.iloc[test_idx[s_idx]]
                        manual_trace.append({
                            "timestamp": str(pd.to_datetime(row['timestamp'], unit='ms')),
                            "symbol": symbol,
                            "prob": float(y_prob_iso[s_idx]),
                            "entry": float(row['close']),
                            "tp": float(row['close'] * (1 + max(row['atr_pct_14'] * tp, 0.0015))),
                            "sl": float(row['close'] * (1 - max(row['atr_pct_14'] * sl, 0.0010))),
                            "exit_reason": int(row['outcome']),
                            "exit_price": float(row['exit_price']),
                            "gross_ret_bps": float(test_gross[s_idx] * 10000)
                        })
                        if len(manual_trace) >= 20:
                            break
                            
                fold_results.append(metrics)
                
            avg_brier = np.mean([f['brier_iso'] for f in fold_results])
            
            # Calculate aggregate expected return for high prob buckets
            # Weighted average of gross return in bucket > 0.5 or highest populated bucket
            
            manifest["results"].append({
                "config": {"fset": fset_name, "tp": tp, "sl": sl, "embargo": emb, "ambig": ambig},
                "label_dist": lbl_dist,
                "avg_brier_iso": avg_brier,
                "folds": fold_results
            })
            
            print(f"  -> Avg Brier Iso: {avg_brier:.4f} | P(+1): {lbl_dist['P(+1)']:.2%}")

        with open(os.path.join(self.results_dir, f"PHASE5_1_RERUN_{symbol}.json"), "w") as f:
            json.dump({"manifest": manifest, "manual_trace": manual_trace}, f, indent=2)
            
if __name__ == "__main__":
    exp = Phase5BaselineRerun()
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT', 'ADAUSDT']
    for sym in symbols:
        exp.run_experiment(sym)
