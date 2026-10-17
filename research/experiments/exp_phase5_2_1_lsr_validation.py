import os
import sys
import json
import numpy as np
import pandas as pd
import scipy.stats as stats
from numba import njit
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import log_loss, brier_score_loss

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

@njit
def _compute_triple_barrier(highs, lows, closes, target_pcts, stop_pcts, max_horizon, ambiguity_policy):
    n = len(closes)
    outcomes = np.zeros(n, dtype=np.int8)  
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


def diebold_mariano_test(loss1, loss2, h=12):
    """
    Diebold-Mariano test with Newey-West HAC variance.
    loss1 and loss2 are arrays of losses (e.g. Brier scores per observation).
    Returns DM stat and p-value.
    Null hypothesis: equal predictive accuracy.
    """
    d = loss1 - loss2
    mean_d = np.mean(d)
    T = len(d)
    if T == 0: return 0.0, 1.0
    
    gamma = np.zeros(h)
    for k in range(h):
        if T - k > 0:
            gamma[k] = np.sum((d[k:] - mean_d) * (d[:T-k] - mean_d)) / T
            
    # Newey-West HAC variance
    var_d = gamma[0] + 2 * sum((1 - k/h) * gamma[k] for k in range(1, h))
    
    if var_d <= 0:
        return 0.0, 1.0
        
    DM_stat = mean_d / np.sqrt(var_d / T)
    p_value = 2 * stats.norm.cdf(-abs(DM_stat))
    return float(DM_stat), float(p_value)

def block_permute(x, block_size=288):
    """
    Randomly permutes contiguous blocks of data to destroy target alignment
    while preserving auto-correlation.
    """
    n = len(x)
    n_blocks = int(np.ceil(n / block_size))
    block_indices = np.random.permutation(n_blocks)
    
    permuted_x = np.zeros_like(x)
    for i, b in enumerate(block_indices):
        start_src = b * block_size
        end_src = min((b + 1) * block_size, n)
        
        start_dst = i * block_size
        size = end_src - start_src
        end_dst = start_dst + size
        if end_dst > n:
            size = n - start_dst
            end_src = start_src + size
            end_dst = n
            
        permuted_x[start_dst:end_dst] = x[start_src:end_src]
    return permuted_x

def compute_ece(y_true, y_prob, n_bins=10):
    bins = np.linspace(0, 1, n_bins + 1)
    bin_ids = np.digitize(y_prob, bins) - 1
    ece = 0.0
    for i in range(n_bins):
        mask = (bin_ids == i)
        if mask.sum() > 0:
            acc = y_true[mask].mean()
            conf = y_prob[mask].mean()
            ece += (mask.sum() / len(y_true)) * np.abs(acc - conf)
    return float(ece)

def eval_economics(y_true, y_prob, gross_ret, costs_bps):
    res = {}
    
    # Calculate top probability buckets
    q80 = np.percentile(y_prob, 80)
    q90 = np.percentile(y_prob, 90)
    q95 = np.percentile(y_prob, 95)
    
    for q_name, q_val in [('top20', q80), ('top10', q90), ('top5', q95)]:
        mask = y_prob >= q_val
        n_trades = mask.sum()
        hr = float(y_true[mask].mean()) if n_trades > 0 else 0.0
        gr = float(np.mean(gross_ret[mask]) * 10000) if n_trades > 0 else 0.0
        
        bucket_res = {
            "n_trades": int(n_trades),
            "hit_rate": hr,
            "gross_bps": gr
        }
        for c in costs_bps:
            bucket_res[f"net_bps_cost_{c}"] = gr - c
        res[q_name] = bucket_res
        
    return res

class LSRValidationExperiment:
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
        
    def load_metrics(self, symbol):
        path = os.path.join(self.data_dir, 'normalized', 'positioning', f"{symbol}_metrics.parquet")
        df = pd.read_parquet(path)
        df['create_time'] = pd.to_datetime(df['create_time'])
        df.sort_values('create_time', inplace=True)
        return df
        
    def causal_join(self, df_ohlcv, df_m):
        df = df_ohlcv.copy()
        df_m_renamed = df_m[['create_time', 'count_long_short_ratio']].rename(
            columns={'create_time': 'timestamp', 'count_long_short_ratio': 'lsr'}
        )
        df = pd.merge(df, df_m_renamed, on='timestamp', how='left')
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

    def engineer_lsr_features(self, df, stale_mins=1440):
        # We need to test Config A (24h), Config B (0h), Config C (1h)
        # So we create a flexible prep function.
        ts = df['timestamp']
        
        # Forward fill tracks
        if stale_mins == 0:
            df['lsr_ff'] = df['lsr'] # no ffill
            df['lsr_age'] = 0.0
            df['lsr_is_missing'] = df['lsr'].isna().astype(int)
        else:
            df['lsr_ff'] = df['lsr'].ffill()
            df['lsr_last_ts'] = df['timestamp'].where(~df['lsr'].isna()).ffill()
            df['lsr_age'] = (ts - df['lsr_last_ts']).dt.total_seconds() / 60.0
            df['lsr_is_missing'] = (df['lsr_age'] > stale_mins).astype(int)
            df['lsr_is_missing'] = np.where(df['lsr_last_ts'].isna(), 1, df['lsr_is_missing'])
        
        df['lsr_zscore_1d'] = (df['lsr_ff'] - df['lsr_ff'].rolling(288).mean()) / (df['lsr_ff'].rolling(288).std() + 1e-8)
        df['lsr_change_1h'] = df['lsr_ff'].diff(12)
        
        # Impute early NaNs in forward-filled columns with 0.0 to allow regression
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        cols_to_zero = ['lsr_zscore_1d', 'lsr_change_1h']
        for c in cols_to_zero:
            df[c] = df[c].fillna(0.0)
            
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

    def run_experiment(self, symbols):
        costs_bps = [0, 5, 8, 12, 15, 20, 25]
        horizon = 12
        purge = 12
        emb = 12
        n_folds = 3
        tp = 2.0
        sl = 1.0
        ambig = 0
        n_perms = 100
        n_boot = 1000
        boot_block = 288
        
        base_features = ['ret_1', 'ret_3', 'ret_5', 'realized_vol_20', 'atr_pct_14', 'mom_10', 'vol_ratio']
        
        manifest = {
            "name": "Phase 5.2.1 LSR Validation Audit",
            "symbols": symbols,
            "stale_configs": [1440, 0, 60],
            "costs_bps": costs_bps,
            "permutations": n_perms,
            "bootstraps": n_boot,
            "results": {}
        }
        
        for sym in symbols:
            print(f"\\n{'='*50}\\nProcessing {sym}\\n{'='*50}")
            df_ohlcv = self.load_ohlcv(sym)
            df_m = self.load_metrics(sym)
            
            df_joined = self.causal_join(df_ohlcv, df_m)
            df_joined = self.engineer_base_features(df_joined)
            
            # Base valid universe
            df_joined.dropna(subset=base_features, inplace=True)
            df_joined.reset_index(drop=True, inplace=True)
            
            tp_arr = np.maximum(df_joined['atr_pct_14'].values * tp, 0.0015)
            sl_arr = np.maximum(df_joined['atr_pct_14'].values * sl, 0.0010)
            highs = df_joined['high'].values
            lows = df_joined['low'].values
            closes = df_joined['close'].values
            
            outcomes, exit_idxs, exit_prices = _compute_triple_barrier(highs, lows, closes, tp_arr, sl_arr, horizon, ambig)
            
            df_joined['outcome'] = outcomes
            df_joined['exit_price'] = exit_prices
            
            valid_mask = (outcomes != 2)
            df_valid = df_joined[valid_mask].copy().reset_index(drop=True)
            df_valid['target_long'] = (df_valid['outcome'] == 1).astype(int)
            df_valid['gross_ret'] = (df_valid['exit_price'] / df_valid['close']) - 1.0
            df_valid['year'] = df_valid['timestamp'].dt.year
            
            sym_results = {"configs": {}, "data_audit": {}}
            
            # Data Audit on df_joined (pre-filtering, to be exact)
            sym_results['data_audit']['first_valid_lsr'] = str(df_joined['timestamp'][~df_joined['lsr'].isna()].min())
            sym_results['data_audit']['total_missing_lsr'] = int(df_joined['lsr'].isna().sum())
            
            y = df_valid['target_long'].values
            gross_ret = df_valid['gross_ret'].values
            years = df_valid['year'].values
            
            splits = self.purged_walk_forward_splits(len(df_valid), n_folds=n_folds, purge=purge, embargo=emb)
            
            for stale_mins in [1440, 0, 60]:
                print(f"  Config: Stale Mins = {stale_mins}")
                df_cfg = self.engineer_lsr_features(df_valid.copy(), stale_mins=stale_mins)
                
                models = {
                    'BASE': base_features,
                    'LSR1': base_features + ['lsr_zscore_1d'],
                    'LSR2': base_features + ['lsr_change_1h'],
                    'LSR3': base_features + ['lsr_zscore_1d', 'lsr_change_1h']
                }
                
                config_results = {}
                
                for model_name, features in models.items():
                    print(f"    Training {model_name}...")
                    X = df_cfg[features].values
                    fold_results = []
                    
                    # Store out-of-sample predictions for boot/DM tests later
                    all_y_test = []
                    all_y_prob = []
                    all_gross = []
                    
                    for i, (train_idx, val_idx, test_idx) in enumerate(splits):
                        X_train, y_train = X[train_idx], y[train_idx]
                        X_test, y_test = X[test_idx], y[test_idx]
                        test_gross = gross_ret[test_idx]
                        test_years = years[test_idx]
                        
                        scaler = StandardScaler()
                        X_train_scaled = scaler.fit_transform(X_train)
                        X_test_scaled = scaler.transform(X_test)
                        
                        lr = LogisticRegression(C=1.0, solver='lbfgs', max_iter=1000)
                        lr.fit(X_train_scaled, y_train)
                        
                        cal_iso = CalibratedClassifierCV(lr, method='isotonic', cv=3)
                        cal_iso.fit(X_train_scaled, y_train)
                        y_prob_iso = cal_iso.predict_proba(X_test_scaled)[:, 1]
                        
                        brier = float(brier_score_loss(y_test, y_prob_iso))
                        ll = float(log_loss(y_test, y_prob_iso, labels=[0, 1]))
                        ece = compute_ece(y_test, y_prob_iso)
                        econ = eval_economics(y_test, y_prob_iso, test_gross, costs_bps)
                        
                        # Year splits
                        yr_stats = {}
                        for yr in [2022, 2023]:
                            yr_mask = (test_years == yr)
                            if yr_mask.sum() > 0:
                                yr_stats[str(yr)] = {
                                    "brier": float(brier_score_loss(y_test[yr_mask], y_prob_iso[yr_mask])),
                                    "logloss": float(log_loss(y_test[yr_mask], y_prob_iso[yr_mask], labels=[0, 1]))
                                }
                        
                        fold_results.append({
                            "fold": i+1,
                            "brier": brier,
                            "log_loss": ll,
                            "ece": ece,
                            "economics": econ,
                            "years": yr_stats
                        })
                        
                        all_y_test.extend(y_test)
                        all_y_prob.extend(y_prob_iso)
                        all_gross.extend(test_gross)
                        
                        # Only run permutation test for LSR3 and Stale=1440 config
                        if model_name == 'LSR3' and stale_mins == 1440:
                            n_beat = 0
                            for p in range(n_perms):
                                # Block permute the LSR columns specifically
                                # BASE features are columns 0..6
                                # LSR features are columns 7..8
                                X_train_permuted = X_train.copy()
                                for c_idx in [7, 8]:
                                    X_train_permuted[:, c_idx] = block_permute(X_train[:, c_idx], block_size=288)
                                    
                                scaler_p = StandardScaler()
                                X_train_p_scaled = scaler_p.fit_transform(X_train_permuted)
                                X_test_p_scaled = scaler_p.transform(X_test) # Note: we do NOT permute the test set LSR for evaluation! 
                                # Wait, to properly test the null hypothesis, if the test set is evaluated, its LSR doesn't matter because it's noise in the model, but actually standard permutation testing permutes train AND evaluates on test with normal test, OR permutes test.
                                # The most rigorous is: permute the target Y? No, permute the feature in train AND test so it has no relationship to Y in test either.
                                # We permute test set features so they're completely decoupled from the real Y.
                                X_test_permuted = X_test.copy()
                                for c_idx in [7, 8]:
                                    X_test_permuted[:, c_idx] = block_permute(X_test[:, c_idx], block_size=288)
                                X_test_p_scaled = scaler_p.transform(X_test_permuted)
                                
                                lr_p = LogisticRegression(C=1.0, solver='lbfgs', max_iter=1000)
                                lr_p.fit(X_train_p_scaled, y_train)
                                cal_p = CalibratedClassifierCV(lr_p, method='isotonic', cv=3)
                                cal_p.fit(X_train_p_scaled, y_train)
                                
                                y_prob_p = cal_p.predict_proba(X_test_p_scaled)[:, 1]
                                brier_p = brier_score_loss(y_test, y_prob_p)
                                
                                if brier_p <= brier: # less than or equal to true loss (at least as extreme)
                                    n_beat += 1
                                    
                            fold_results[-1]['perm_p_value'] = (1 + n_beat) / (n_perms + 1)
                        
                    config_results[model_name] = {
                        "folds": fold_results,
                        "agg_y_test": all_y_test,
                        "agg_y_prob": all_y_prob,
                        "agg_gross": all_gross
                    }
                    
                # Diebold-Mariano and Block Bootstrap between BASE and LSR3
                if 'BASE' in config_results and 'LSR3' in config_results:
                    y_true = np.array(config_results['BASE']['agg_y_test'])
                    y_prob_base = np.array(config_results['BASE']['agg_y_prob'])
                    y_prob_lsr3 = np.array(config_results['LSR3']['agg_y_prob'])
                    gross = np.array(config_results['BASE']['agg_gross'])
                    
                    # DM Test
                    loss_base = (y_true - y_prob_base)**2
                    loss_lsr = (y_true - y_prob_lsr3)**2
                    dm_stat, p_val = diebold_mariano_test(loss_base, loss_lsr, h=12)
                    
                    config_results['LSR3']['dm_stat'] = dm_stat
                    config_results['LSR3']['dm_p_value'] = p_val
                    
                    # Block Bootstrap CI
                    n = len(y_true)
                    n_blocks = int(np.ceil(n / boot_block))
                    delta_briers = []
                    delta_gross_bps = []
                    
                    for b in range(n_boot):
                        boot_indices = np.random.choice(n_blocks, n_blocks, replace=True)
                        idx = []
                        for block_idx in boot_indices:
                            start = block_idx * boot_block
                            end = min(start + boot_block, n)
                            idx.extend(range(start, end))
                        idx = np.array(idx)[:n] # truncate if exactly n needed
                        
                        brier_base = brier_score_loss(y_true[idx], y_prob_base[idx])
                        brier_lsr = brier_score_loss(y_true[idx], y_prob_lsr3[idx])
                        delta_briers.append(brier_lsr - brier_base) # Negative means LSR is better
                        
                        # Gross
                        mask_lsr = y_prob_lsr3[idx] >= np.percentile(y_prob_lsr3[idx], 80)
                        mask_base = y_prob_base[idx] >= np.percentile(y_prob_base[idx], 80)
                        
                        gr_lsr = np.mean(gross[idx][mask_lsr]) * 10000 if mask_lsr.sum()>0 else 0
                        gr_base = np.mean(gross[idx][mask_base]) * 10000 if mask_base.sum()>0 else 0
                        delta_gross_bps.append(gr_lsr - gr_base)
                        
                    config_results['LSR3']['ci_95_delta_brier'] = [
                        float(np.percentile(delta_briers, 2.5)), 
                        float(np.percentile(delta_briers, 97.5))
                    ]
                    config_results['LSR3']['ci_95_delta_gross_bps'] = [
                        float(np.percentile(delta_gross_bps, 2.5)), 
                        float(np.percentile(delta_gross_bps, 97.5))
                    ]
                
                # Clean up huge arrays before JSON dump
                for m in config_results:
                    del config_results[m]['agg_y_test']
                    del config_results[m]['agg_y_prob']
                    del config_results[m]['agg_gross']
                    
                sym_results['configs'][str(stale_mins)] = config_results
                
            manifest["results"][sym] = sym_results
            
        with open(os.path.join(self.results_dir, "PHASE5_2_1_LSR_VALIDATION_MANIFEST.json"), "w") as f:
            json.dump(manifest, f, indent=2)

if __name__ == "__main__":
    exp = LSRValidationExperiment()
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT', 'ADAUSDT']
    exp.run_experiment(symbols)
