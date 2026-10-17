import os
import sys
import json
import time
import numpy as np
import pandas as pd
from numba import njit
from sklearn.linear_model import LogisticRegression
from sklearn.dummy import DummyClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import log_loss, brier_score_loss, precision_score

# Ensure imports work without installing as package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

@njit
def _compute_triple_barrier(highs, lows, closes, target_pcts, stop_pcts, max_horizon):
    n = len(closes)
    outcomes = np.zeros(n, dtype=np.int8)  # 1=UP, -1=DOWN, 0=TIMEOUT/AMBIGUOUS
    exit_idx = np.zeros(n, dtype=np.int32)
    
    for i in range(n):
        entry_price = closes[i]
        tp = target_pcts[i]
        sl = stop_pcts[i]
        
        reached_outcome = 0
        reached_idx = min(i + max_horizon, n - 1)
        
        for j in range(1, max_horizon + 1):
            curr_idx = i + j
            if curr_idx >= n:
                reached_idx = n - 1
                break
                
            h = highs[curr_idx]
            l = lows[curr_idx]
            
            hit_up = (h / entry_price - 1.0) >= tp
            hit_dn = (l / entry_price - 1.0) <= -sl
            
            if hit_up and hit_dn:
                reached_outcome = 0 # Ambiguous
                reached_idx = curr_idx
                break
            elif hit_up:
                reached_outcome = 1
                reached_idx = curr_idx
                break
            elif hit_dn:
                reached_outcome = -1
                reached_idx = curr_idx
                break
                
        outcomes[i] = reached_outcome
        exit_idx[i] = reached_idx
        
    return outcomes, exit_idx


class Phase5BaselineExperiment:
    def __init__(self):
        self.data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/normalized/v2'))
        self.results_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../results'))
        os.makedirs(self.results_dir, exist_ok=True)
        
    def load_data(self, symbol, timeframe="5m"):
        path = os.path.join(self.data_dir, f"binance_um_{symbol.lower()}_{timeframe}_v2.parquet")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing {path}")
        df = pd.read_parquet(path)
        # Sort chronologically
        df.sort_values('timestamp', inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df
        
    def engineer_features(self, df):
        print("Engineering features...")
        df = df.copy()
        c = df['close']
        
        # BASE-1: Returns
        df['ret_1'] = c.pct_change(1)
        df['ret_3'] = c.pct_change(3)
        df['ret_5'] = c.pct_change(5)
        
        # BASE-2: Volatility
        df['log_ret'] = np.log(c / c.shift(1))
        df['realized_vol_20'] = df['log_ret'].rolling(20).std() * np.sqrt(20)
        
        # BASE-3: ATR
        h_l = df['high'] - df['low']
        h_pc = (df['high'] - c.shift(1)).abs()
        l_pc = (df['low'] - c.shift(1)).abs()
        tr = pd.concat([h_l, h_pc, l_pc], axis=1).max(axis=1)
        df['atr_14'] = tr.rolling(14).mean()
        # Normalized ATR (percentage)
        df['atr_pct_14'] = df['atr_14'] / c
        
        # BASE-4: Momentum
        df['mom_10'] = df['log_ret'].rolling(10).sum()
        
        # BASE-5: Volume
        v = df['volume']
        df['vol_ma_20'] = v.rolling(20).mean()
        df['vol_ratio'] = v / (df['vol_ma_20'] + 1e-8)
        
        # Drop NaNs from rolling windows
        df.dropna(subset=['ret_5', 'realized_vol_20', 'atr_pct_14', 'mom_10', 'vol_ratio'], inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df

    def apply_labels(self, df, tp_atr_mult=2.0, sl_atr_mult=1.0, horizon=12):
        print(f"Applying Triple-Barrier Labels (TP={tp_atr_mult}ATR, SL={sl_atr_mult}ATR, Horizon={horizon})...")
        
        # Cost is integrated in evaluation, but here we define the geometric bounds.
        # Ensure minimum bounds so we aren't targeting 1 pip in low vol.
        min_tp_pct = 0.0015 # 15 bps min
        min_sl_pct = 0.0010 # 10 bps min
        
        tp_arr = np.maximum(df['atr_pct_14'].values * tp_atr_mult, min_tp_pct)
        sl_arr = np.maximum(df['atr_pct_14'].values * sl_atr_mult, min_sl_pct)
        
        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values
        
        outcomes, exit_idxs = _compute_triple_barrier(highs, lows, closes, tp_arr, sl_arr, horizon)
        
        df['outcome'] = outcomes
        df['exit_idx'] = exit_idxs
        
        # Binary target for P(Long) baseline: 1 if outcome == +1, else 0
        df['target_long'] = (df['outcome'] == 1).astype(int)
        
        # Calculate continuous return to exit for economic evaluation
        # Realized gross return of a LONG position
        exit_prices = closes[exit_idxs]
        df['gross_ret'] = exit_prices / closes - 1.0
        
        return df

    def purged_walk_forward_splits(self, n_samples, n_folds=3, purge=12, embargo=12):
        """
        Creates strictly separated train, val, test splits.
        train -> val -> test (chronological within fold).
        """
        fold_size = n_samples // (n_folds + 1)
        splits = []
        
        for i in range(n_folds):
            test_start = (i + 1) * fold_size
            test_end = (i + 2) * fold_size if i < n_folds - 1 else n_samples
            
            # 80/20 train/val split inside the pre-test window
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
        
    def evaluate_model(self, y_true, y_prob, gross_ret, costs_bps):
        metrics = {}
        metrics['log_loss'] = float(log_loss(y_true, y_prob, labels=[0, 1]))
        metrics['brier'] = float(brier_score_loss(y_true, y_prob))
        
        # ECE calculation
        bins = np.linspace(0, 1, 11)
        bin_ids = np.digitize(y_prob, bins) - 1
        ece = 0.0
        for i in range(10):
            mask = (bin_ids == i)
            if mask.sum() > 0:
                prob_mean = y_prob[mask].mean()
                acc_mean = y_true[mask].mean()
                ece += (mask.sum() / len(y_prob)) * np.abs(prob_mean - acc_mean)
        metrics['ece'] = float(ece)
        
        # Economic metrics across thresholds (e.g., > 0.55 probability)
        # Using 90th percentile of probabilities as entry threshold for long
        thresh = np.percentile(y_prob, 90)
        taken_trades = (y_prob >= thresh)
        n_trades = taken_trades.sum()
        
        metrics['n_trades'] = int(n_trades)
        metrics['trade_freq'] = float(n_trades / len(y_prob))
        
        if n_trades > 0:
            trade_returns = gross_ret[taken_trades]
            metrics['hit_rate'] = float(np.mean(trade_returns > 0))
            metrics['gross_ret_mean_bps'] = float(np.mean(trade_returns) * 10000)
            
            for cost in costs_bps:
                net_returns = trade_returns - (cost / 10000.0)
                metrics[f'net_ret_mean_bps_cost_{cost}'] = float(np.mean(net_returns) * 10000)
                
                # Cumulative Net Return over the fold
                cum_net = np.prod(1.0 + net_returns) - 1.0
                metrics[f'cum_net_pct_cost_{cost}'] = float(cum_net * 100)
                
                # Sharpe (assuming 0 risk free, annualized assuming 1 trade per period, roughly)
                if np.std(net_returns) > 0:
                    sharpe = np.mean(net_returns) / np.std(net_returns)
                else:
                    sharpe = 0.0
                metrics[f'sharpe_cost_{cost}'] = float(sharpe)
        else:
            metrics['hit_rate'] = 0.0
            metrics['gross_ret_mean_bps'] = 0.0
            for cost in costs_bps:
                metrics[f'net_ret_mean_bps_cost_{cost}'] = 0.0
                metrics[f'cum_net_pct_cost_{cost}'] = 0.0
                metrics[f'sharpe_cost_{cost}'] = 0.0
                
        return metrics

    def run_experiment(self, symbol="BTCUSDT"):
        print(f"\\n{'='*50}\\nStarting Baseline for {symbol}\\n{'='*50}")
        df = self.load_data(symbol)
        df = self.engineer_features(df)
        
        feature_sets = {
            'BASE-0': [], # Intercept only
            'BASE-1': ['ret_1', 'ret_3', 'ret_5'],
            'BASE-2': ['ret_1', 'ret_3', 'ret_5', 'realized_vol_20'],
            'BASE-3': ['ret_1', 'ret_3', 'ret_5', 'realized_vol_20', 'atr_pct_14'],
            'BASE-4': ['ret_1', 'ret_3', 'ret_5', 'realized_vol_20', 'atr_pct_14', 'mom_10'],
            'BASE-5': ['ret_1', 'ret_3', 'ret_5', 'realized_vol_20', 'atr_pct_14', 'mom_10', 'vol_ratio']
        }
        
        # Settings
        tp_sl_configs = [(2.0, 1.0), (1.5, 1.0), (1.0, 1.0)]
        embargoes = [12, 24, 60]
        costs_bps = [0, 5, 8, 12, 15, 20, 25]
        horizon = 12
        purge = 12
        n_folds = 3
        
        manifest = {
            "symbol": symbol,
            "dataset": "5m_v2",
            "timeframe": "2022-2023",
            "feature_sets": list(feature_sets.keys()),
            "costs_bps": costs_bps,
            "results": []
        }
        
        # To limit combinatorics in output, we use default tp_sl=(2.0, 1.0) and embargo=12 for the full feature sweep.
        # We'll run sensitivities only on BASE-5.
        
        combinations = []
        for fset in feature_sets.keys():
            combinations.append((fset, 2.0, 1.0, 12))
        
        # Add sensitivities for BASE-5
        for tp, sl in tp_sl_configs:
            for emb in embargoes:
                if (tp, sl) != (2.0, 1.0) or emb != 12:
                    combinations.append(('BASE-5', tp, sl, emb))
                    
        for config in combinations:
            fset_name, tp, sl, emb = config
            print(f"\\nRunning {fset_name} | TP={tp} SL={sl} | Emb={emb}")
            
            df_lbl = self.apply_labels(df, tp_atr_mult=tp, sl_atr_mult=sl, horizon=horizon)
            
            features = feature_sets[fset_name]
            if len(features) > 0:
                X = df_lbl[features].values
            else:
                X = np.ones((len(df_lbl), 1))
                
            y = df_lbl['target_long'].values
            gross_ret = df_lbl['gross_ret'].values
            
            splits = self.purged_walk_forward_splits(len(df_lbl), n_folds=n_folds, purge=purge, embargo=emb)
            
            fold_results = []
            
            for i, (train_idx, val_idx, test_idx) in enumerate(splits):
                X_train, y_train = X[train_idx], y[train_idx]
                X_val, y_val = X[val_idx], y[val_idx]
                X_test, y_test = X[test_idx], y[test_idx]
                
                # Scaler strictly on train
                scaler = StandardScaler()
                X_train_scaled = scaler.fit_transform(X_train)
                X_val_scaled = scaler.transform(X_val)
                X_test_scaled = scaler.transform(X_test)
                
                # BASE RATE (Model 0)
                base_rate = y_train.mean()
                y_prob_naive = np.full(len(y_test), base_rate)
                
                # Logistic Regression (Model 1)
                lr = LogisticRegression(penalty='l2', C=1.0, solver='lbfgs', max_iter=1000)
                if len(features) > 0:
                    lr.fit(X_train_scaled, y_train)
                    # Uncalibrated prob
                    y_prob_uncal = lr.predict_proba(X_test_scaled)[:, 1]
                    
                    # Calibration (Isotonic fitted on CV folds of train set)
                    calibrator = CalibratedClassifierCV(lr, method='isotonic', cv=3)
                    calibrator.fit(X_train_scaled, y_train)
                    y_prob_cal = calibrator.predict_proba(X_test_scaled)[:, 1]
                else:
                    y_prob_uncal = y_prob_naive
                    y_prob_cal = y_prob_naive
                
                # Evaluate metrics
                metrics_naive = self.evaluate_model(y_test, y_prob_naive, gross_ret[test_idx], costs_bps)
                metrics_uncal = self.evaluate_model(y_test, y_prob_uncal, gross_ret[test_idx], costs_bps)
                metrics_cal = self.evaluate_model(y_test, y_prob_cal, gross_ret[test_idx], costs_bps)
                
                fold_results.append({
                    'fold': i,
                    'naive': metrics_naive,
                    'uncalibrated': metrics_uncal,
                    'calibrated': metrics_cal
                })
                
            # Aggregate across folds
            avg_cal_brier = np.mean([f['calibrated']['brier'] for f in fold_results])
            avg_naive_brier = np.mean([f['naive']['brier'] for f in fold_results])
            
            avg_cal_net_12bps = np.mean([f['calibrated']['net_ret_mean_bps_cost_12'] for f in fold_results])
            
            manifest["results"].append({
                "config": {"fset": fset_name, "tp": tp, "sl": sl, "embargo": emb},
                "avg_calibrated_brier": avg_cal_brier,
                "avg_naive_brier": avg_naive_brier,
                "avg_calibrated_net_ret_12bps": avg_cal_net_12bps,
                "folds": fold_results
            })
            
            print(f"  -> Calibrated Brier: {avg_cal_brier:.4f} (Naive: {avg_naive_brier:.4f}) | Expected Net (12bps): {avg_cal_net_12bps:.2f} bps")
            
        with open(os.path.join(self.results_dir, f"PHASE5_1_MANIFEST_{symbol}.json"), "w") as f:
            json.dump(manifest, f, indent=2)
            
        return manifest

if __name__ == "__main__":
    exp = Phase5BaselineExperiment()
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT', 'ADAUSDT']
    for sym in symbols:
        exp.run_experiment(sym)
