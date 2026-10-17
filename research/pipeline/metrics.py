import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, brier_score_loss, log_loss

class MetricsEvaluator:
    @staticmethod
    def block_bootstrap_ci(y_true, y_pred, block_size=60, n_bootstraps=500, fast=False):
        if fast:
            n_bootstraps = 10
        n = len(y_true)
        aucs = []
        np.random.seed(42)
        for _ in range(n_bootstraps):
            start_idx = np.random.randint(0, n - block_size + 1, size=n // block_size)
            idx = np.concatenate([np.arange(s, s + block_size) for s in start_idx])
            
            samp_true = y_true.iloc[idx] if hasattr(y_true, 'iloc') else y_true[idx]
            samp_pred = y_pred[idx]
            
            if len(np.unique(samp_true)) > 1:
                aucs.append(roc_auc_score(samp_true, samp_pred))
                
        aucs = np.array(aucs)
        se = np.std(aucs)
        return aucs, np.percentile(aucs, 2.5), np.percentile(aucs, 97.5), se

    @staticmethod
    def economic_deciles(y_true, y_pred, forward_returns, costs_bps=12):
        """
        costs_bps: Total round trip cost (e.g. 4 bps taker + 2 bps slippage per side = 12 bps)
        """
        df = pd.DataFrame({
            'y_true': y_true,
            'y_pred': y_pred,
            'R_fwd': forward_returns
        })
        
        df['decile'] = pd.qcut(df['y_pred'], 10, labels=False, duplicates='drop')
        
        results = []
        cost_frac = costs_bps / 10000.0
        
        for d in sorted(df['decile'].unique()):
            d_df = df[df['decile'] == d]
            realized_rate = d_df['y_true'].mean()
            mean_ret = d_df['R_fwd'].mean()
            
            # Simple assumption: Decile > 4 is long, <= 4 is short (if symmetrical)
            # We explicitly trade long if pred > 0.5, else short. 
            # Or just long the top decile, short the bottom.
            # Here we assume top deciles are longs, bottom are shorts.
            is_long = d >= 5
            gross_ret = mean_ret if is_long else -mean_ret
            net_ret = gross_ret - cost_frac
            
            results.append({
                'decile': d,
                'mean_prob': d_df['y_pred'].mean(),
                'realized_rate': realized_rate,
                'mean_ret_bps': mean_ret * 10000,
                'gross_ret_bps': gross_ret * 10000,
                'net_ret_bps': net_ret * 10000
            })
            
        return results

    @staticmethod
    def evaluate(y_true, y_pred, forward_returns=None, costs_bps=12, fast=False):
        obs_auc = roc_auc_score(y_true, y_pred)
        brier = brier_score_loss(y_true, y_pred)
        
        aucs, ci_lower, ci_upper, se = MetricsEvaluator.block_bootstrap_ci(y_true, y_pred, fast=fast)
        
        deciles = None
        if forward_returns is not None:
            deciles = MetricsEvaluator.economic_deciles(y_true, y_pred, forward_returns, costs_bps)
            
        return {
            'auc': obs_auc,
            'brier': brier,
            'ci': (ci_lower, ci_upper),
            'se': se,
            'deciles': deciles
        }
