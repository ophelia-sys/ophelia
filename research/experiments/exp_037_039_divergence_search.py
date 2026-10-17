import os
import sys
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from research.phase6.pipeline import ResearchPipeline
from institutional.features import calculate_flow_price_divergence
from research.phase6.statistics import compute_excess_return, newey_west_se, fdr_bh, stationary_block_bootstrap
from scipy.stats import norm

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DATASET_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'binance_um_universe_1m_v2.parquet')
OUTPUT_PATH = os.path.join(BASE_DIR, 'research', 'PHASE6.1_GATE1_RESULTS.md')

def evaluate_fold_subset(events, folds, horizons, baseline_returns):
    """
    Evaluates events over a subset of folds and returns dict of results per horizon.
    """
    results = {}
    
    # Collect all events in the specified folds
    subset_events = []
    for f in folds:
        t_start, t_end = f["test_start"], f["test_end"]
        fold_evs = [e for e in events if t_start <= e["timestamp"] <= t_end]
        subset_events.extend(fold_evs)
        
    for h in horizons:
        b_arr = []
        for f in folds:
            # We don't have direct access to test_df here easily if we dropped it, 
            # so let's pass baseline_returns mapping from fold index
            b_arr.extend(baseline_returns[f['fold_idx']][h])
            
        b_arr = np.array(b_arr)
        f_returns = [e.get(f"R_{h}") for e in subset_events if e.get(f"R_{h}") is not None and not np.isnan(e.get(f"R_{h}"))]
        f_arr = np.array(f_returns)
        
        if len(f_arr) < 2 or len(b_arr) < 2:
            results[h] = {"N": len(f_arr), "excess_return": 0.0, "p_val": 1.0, "ci_lower": 0.0, "ci_upper": 0.0, "mean_return": 0.0, "effect_size": 0.0}
            continue
            
        excess, effect_size, _ = compute_excess_return(b_arr, f_arr)
        baseline_mean = np.mean(b_arr)
        y = f_arr - baseline_mean
        x = np.ones_like(y)
        hac_se = newey_west_se(x, y)
        
        if np.isnan(hac_se) or hac_se == 0:
            p_val = 1.0
        else:
            z_stat = excess / hac_se
            p_val = 2 * (1 - norm.cdf(abs(z_stat)))
            
        boot_samples = stationary_block_bootstrap(y, block_size=10, num_bootstraps=1000)
        boot_means = np.mean(boot_samples, axis=1)
        
        results[h] = {
            "N": len(f_arr),
            "mean_return": float(np.mean(f_arr)),
            "excess_return": float(excess),
            "effect_size": float(effect_size),
            "hac_se": float(hac_se),
            "p_val": float(p_val),
            "ci_lower": float(np.percentile(boot_means, 2.5)),
            "ci_upper": float(np.percentile(boot_means, 97.5))
        }
        
    return results

def run_experiment():
    print("Loading canonical dataset...")
    df = pd.read_parquet(DATASET_PATH)
    
    df['tr'] = np.maximum(df['high'] - df['low'], 
               np.maximum(abs(df['high'] - df['close'].shift()), 
                          abs(df['low'] - df['close'].shift())))
    atr_series = df.groupby('symbol')['tr'].transform(lambda x: x.rolling(14).mean())
    
    pipeline = ResearchPipeline(n_folds=5)
    
    # Override pipeline to return folds with test_df intact
    print("Running initial pipeline for event generation...")
    # 1. Audit
    pipeline.auditor.audit_dataset(df)
    
    df_regime_list = []
    df_labeled_list = []
    all_events = []
    
    for symbol, sym_df in df.groupby('symbol'):
        sym_df = sym_df.sort_values('timestamp').reset_index(drop=True)
        sym_atr = atr_series.loc[sym_df.index]
        sym_regime = pipeline.regimes.classify_regimes(sym_df)
        df_regime_list.append(sym_regime)
        sym_labeled = pipeline.label_gen.generate_labels(sym_regime)
        df_labeled_list.append(sym_labeled)
        sym_events = pipeline.event_gen.generate_events(sym_df, sym_atr)
        all_events.extend(sym_events)
        
    df_labeled = pd.concat(df_labeled_list, ignore_index=True)
    df_labeled = df_labeled.sort_values('timestamp').reset_index(drop=True)
    
    enriched_events = pipeline.label_gen.attach_labels_to_events(all_events, df_labeled)
    folds_meta = pipeline.validator.generate_folds(df_labeled, n_folds=5, max_horizon_seconds=3600)
    
    # Pre-extract baseline returns
    baseline_returns = {}
    for i, fold in enumerate(folds_meta):
        fold['fold_idx'] = i
        baseline_returns[i] = {h: [] for h in pipeline.horizons}
        test_df = fold["test_df"]
        for h in pipeline.horizons:
            col = f"R_{h}"
            if col in test_df.columns:
                baseline_returns[i][h].extend(test_df[col].dropna().tolist())
                
    dev_folds = folds_meta[:3]
    oos_folds = folds_meta[3:]
    
    grid = [1.0, 1.5, 2.0, 2.5, 3.0]
    features = ["FVG_CONFIRMATION", "POOL_CONFIRMATION", "LIQUIDITY_SWEEP"]
    
    print("\n--- HYPERPARAMETER SEARCH (DEV SET: FOLDS 1-3) ---")
    best_taus = {}
    
    for feat in features:
        print(f"\nSearching tau for {feat}...")
        feat_events = [e for e in enriched_events if e["event_type"] == feat and e.get("primary_event", False)]
        
        best_tau = None
        best_score = -float('inf')
        
        for tau in grid:
            # Filter events with divergence condition
            cond_events = []
            for e in feat_events:
                snap = e.get("feature_snapshot", {})
                z_r = snap.get("z_r", 0.0)
                z_oi = snap.get("z_delta_oi", 0.0)
                div = calculate_flow_price_divergence(z_r, z_oi, tau=tau)
                if div > 0:
                    cond_events.append(e)
                    
            res = evaluate_fold_subset(cond_events, dev_folds, pipeline.horizons, baseline_returns)
            
            # Use mean excess return at h=60 as the selection criteria
            score = res[60]["excess_return"]
            print(f"  tau={tau:.1f} -> N={res[60]['N']}, Excess(h=60)={score*10000:.2f} bps, p={res[60]['p_val']:.4f}")
            
            if score > best_score and res[60]['N'] > 10:
                best_score = score
                best_tau = tau
                
        best_taus[feat] = best_tau if best_tau is not None else 2.0
        print(f"Selected Best Tau for {feat}: {best_taus[feat]}")
        
    print("\n--- OUT-OF-SAMPLE EVALUATION (OOS SET: FOLDS 4-5) ---")
    
    final_report = []
    
    for feat in features:
        tau = best_taus[feat]
        print(f"\nEvaluating {feat} (tau={tau}) on OOS...")
        feat_events = [e for e in enriched_events if e["event_type"] == feat and e.get("primary_event", False)]
        
        cond_events = []
        for e in feat_events:
            snap = e.get("feature_snapshot", {})
            z_r = snap.get("z_r", 0.0)
            z_oi = snap.get("z_delta_oi", 0.0)
            div = calculate_flow_price_divergence(z_r, z_oi, tau=tau)
            if div > 0:
                cond_events.append(e)
                
        # 1. Unconditioned Baseline on OOS
        uncond_res = evaluate_fold_subset(feat_events, oos_folds, pipeline.horizons, baseline_returns)
        
        # 2. Conditioned on OOS
        cond_res = evaluate_fold_subset(cond_events, oos_folds, pipeline.horizons, baseline_returns)
        
        # Calculate multiple testing for this feature across horizons
        p_vals = [cond_res[h]["p_val"] for h in pipeline.horizons]
        fdr_ps = fdr_bh(np.array(p_vals))
        
        final_report.append(f"### Feature: {feat} (Selected Tau = {tau})")
        for i, h in enumerate(pipeline.horizons):
            c_r = cond_res[h]
            u_r = uncond_res[h]
            
            fdr = fdr_ps[i]
            
            # Verdict logic
            # Economically meaningful = > 3 bps at h=60, stats sig = FDR < 0.05
            verdict = "INCONCLUSIVE"
            if c_r["N"] < 10:
                verdict = "INCONCLUSIVE / INSUFFICIENT DATA"
            elif fdr < 0.05 and c_r["excess_return"] > 0.0003: # 3 bps
                verdict = "KEEP"
            elif fdr < 0.05 and c_r["excess_return"] > 0.0:
                verdict = "RESEARCH_ONLY"
            else:
                verdict = "REMOVE"
                
            report_line = (f"Horizon {h}m | N={c_r['N']} | "
                           f"Uncond Mean={u_r['mean_return']*10000:.2f} bps | "
                           f"Cond Mean={c_r['mean_return']*10000:.2f} bps | "
                           f"Excess={c_r['excess_return']*10000:.2f} bps | "
                           f"Raw-P={c_r['p_val']:.4f} | FDR-P={fdr:.4f} | "
                           f"CI=[{c_r['ci_lower']*10000:.2f}, {c_r['ci_upper']*10000:.2f}] bps | "
                           f"Verdict: {verdict}")
            print(report_line)
            final_report.append(report_line)
            
            if h == 60:
                # Compute economics
                # Cost is 12 bps 
                gross = c_r['mean_return'] * 10000
                net = gross - 12.0
                print(f"  Economics (h=60): Gross={gross:.2f} bps, Cost=12.00 bps, Net={net:.2f} bps")
                final_report.append(f"  Economics (h=60): Gross={gross:.2f} bps, Cost=12.00 bps, Net={net:.2f} bps")
                
    # Save report
    with open(OUTPUT_PATH, 'w') as f:
        f.write("# Phase 6.1 Gate 1 Results (EXP 037-039)\n\n")
        f.write("## Out-Of-Sample Validation (Folds 4-5)\n\n")
        f.write("\n".join(final_report))

if __name__ == "__main__":
    run_experiment()
