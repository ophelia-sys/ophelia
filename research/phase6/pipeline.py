import numpy as np
import pandas as pd
from typing import Dict, Any, List
from .events import EventGenerator
from .labels import ForwardLabelsGenerator
from .data_quality import DataQualityAuditor
from .costs import CostModel
from .power import PowerAnalysis
from .regimes import RegimeAnalyzer
from .validation import WalkForwardValidator
from .statistics import compute_excess_return, newey_west_se, fdr_bh, stationary_block_bootstrap
from scipy.stats import norm

class ResearchPipeline:
    """
    Orchestrates the Phase 6 Historical Empirical Validation Pipeline.
    Executes true Walk-Forward Evaluation and statistical inference.
    """
    def __init__(self, n_folds: int = 5):
        self.auditor = DataQualityAuditor()
        self.event_gen = EventGenerator()
        self.horizons = [1, 3, 5, 15, 30, 60]
        self.label_gen = ForwardLabelsGenerator(horizons=self.horizons)
        self.cost_model = CostModel()
        self.power = PowerAnalysis()
        self.regimes = RegimeAnalyzer()
        self.validator = WalkForwardValidator(embargo_seconds=86400)
        self.n_folds = n_folds
        
    def run_pipeline(self, df: pd.DataFrame, atr_series: pd.Series) -> Dict[str, Any]:
        """
        Executes the statistical validation pipeline.
        """
        # 1. Audit
        audit = self.auditor.audit_dataset(df)
        
        # 2 & 3. Process Regimes, Labels, and Events strictly per symbol
        df_regime_list = []
        df_labeled_list = []
        all_events = []
        
        for symbol, sym_df in df.groupby('symbol'):
            print(f"Processing symbol: {symbol} - Regimes...")
            sym_df = sym_df.sort_values('timestamp').reset_index(drop=True)
            sym_atr = atr_series.loc[sym_df.index] if atr_series is not None else None
            
            sym_regime = self.regimes.classify_regimes(sym_df)
            df_regime_list.append(sym_regime)
            
            print(f"Processing symbol: {symbol} - Labels...")
            sym_labeled = self.label_gen.generate_labels(sym_regime)
            df_labeled_list.append(sym_labeled)
            
            print(f"Processing symbol: {symbol} - Events...")
            sym_events = self.event_gen.generate_events(sym_df, sym_atr)
            all_events.extend(sym_events)
            
        print("Concatenating dataframes...")
        df_regime = pd.concat(df_regime_list, ignore_index=True)
        df_labeled = pd.concat(df_labeled_list, ignore_index=True)
        
        # Sort back to chronological across all symbols for cross-sectional walk-forward
        df_labeled = df_labeled.sort_values('timestamp').reset_index(drop=True)
        
        self.event_gen.events = all_events
        enriched_events = self.label_gen.attach_labels_to_events(all_events, df_labeled)
        event_stats = self.event_gen.get_event_statistics()
        
        # 4. Walk-Forward Folds
        folds_meta = self.validator.generate_folds(df_labeled, n_folds=self.n_folds, max_horizon_seconds=3600)
        
        # Gather out-of-sample data
        test_events = []
        test_baseline_returns = {h: [] for h in self.horizons}
        fold_reports = []
        
        print(f"Processing {len(folds_meta)} walk-forward folds...")
        for i, fold in enumerate(folds_meta):
            print(f"Processing fold {i+1}/{len(folds_meta)}...")
            t_start, t_end = fold["test_start"], fold["test_end"]
            tr_start, tr_end = fold["train_start"], fold["train_end"]
            
            # Events in Train
            tr_events = [e for e in enriched_events if tr_start <= e["timestamp"] <= tr_end and e.get("primary_event", False)]
            fold["train_event_count"] = len(tr_events)
            
            # Events in Test
            te_events = [e for e in enriched_events if t_start <= e["timestamp"] <= t_end and e.get("primary_event", False)]
            fold["test_event_count"] = len(te_events)
            test_events.extend(te_events)
            
            # Baseline returns in Test
            test_df = fold["test_df"]
            for h in self.horizons:
                col = f"R_{h}"
                if col in test_df.columns:
                    test_baseline_returns[h].extend(test_df[col].dropna().tolist())
                    
            # Keep reporting-safe copy (without full DataFrames)
            safe_meta = {k: v for k, v in fold.items() if not isinstance(v, pd.DataFrame)}
            fold_reports.append(safe_meta)

        # 5. Statistical Evaluation (per Feature x Horizon)
        features = ["FVG_CONFIRMATION", "POOL_CONFIRMATION", "LIQUIDITY_SWEEP"]
        results = []
        p_values = []
        
        print("Starting Statistical Evaluation (Newey-West & Bootstrap)...")
        for feature in features:
            print(f"Evaluating feature: {feature}")
            f_events = [e for e in test_events if e["event_type"] == feature]
            
            for h in self.horizons:
                print(f"  Horizon {h}m...")
                # Baseline array
                b_arr = np.array(test_baseline_returns[h])
                
                # Feature array
                f_returns = [e.get(f"R_{h}") for e in f_events if e.get(f"R_{h}") is not None and not np.isnan(e.get(f"R_{h}"))]
                f_arr = np.array(f_returns)
                
                if len(f_arr) < 2 or len(b_arr) < 2:
                    results.append({
                        "feature": feature, "horizon": h, "N": len(f_arr), 
                        "classification": "INCONCLUSIVE / INSUFFICIENT DATA",
                        "raw_p": np.nan
                    })
                    p_values.append(np.nan)
                    continue
                    
                excess, effect_size, _ = compute_excess_return(b_arr, f_arr)
                
                # Newey-West HAC inference on excess return
                baseline_mean = np.mean(b_arr)
                y = f_arr - baseline_mean
                x = np.ones_like(y)
                
                hac_se = newey_west_se(x, y)
                if np.isnan(hac_se) or hac_se == 0:
                    z_stat = 0
                    p_val = 1.0
                else:
                    z_stat = excess / hac_se
                    p_val = 2 * (1 - norm.cdf(abs(z_stat)))
                    
                # Block bootstrap CI for excess return
                boot_samples = stationary_block_bootstrap(y, block_size=10, num_bootstraps=1000)
                boot_means = np.mean(boot_samples, axis=1)
                ci_lower = float(np.percentile(boot_means, 2.5))
                ci_upper = float(np.percentile(boot_means, 97.5))
                
                res = {
                    "feature": feature,
                    "horizon": h,
                    "N": len(f_arr),
                    "mean_return": float(np.mean(f_arr)),
                    "median_return": float(np.median(f_arr)),
                    "baseline_mean": float(baseline_mean),
                    "excess_return": float(excess),
                    "effect_size": float(effect_size),
                    "hac_se": float(hac_se),
                    "raw_p": float(p_val),
                    "ci_lower": ci_lower,
                    "ci_upper": ci_upper
                }
                
                results.append(res)
                p_values.append(p_val)
                
        # 6. Multiple Testing Correction (FDR)
        fdr_p = fdr_bh(np.array(p_values))
        for i, res in enumerate(results):
            res["fdr_p"] = float(fdr_p[i]) if not np.isnan(fdr_p[i]) else np.nan
            if res.get("classification") != "INCONCLUSIVE / INSUFFICIENT DATA":
                if res["fdr_p"] < 0.05 and res["excess_return"] > 0:
                    res["classification"] = "EMPIRICAL EVIDENCE SUPPORTS FEATURE"
                else:
                    res["classification"] = "EMPIRICAL EVIDENCE FAILS TO SUPPORT FEATURE"
                    
        # 7. Costs
        cost_results = {}
        for scenario in ["OPTIMISTIC", "REALISTIC", "PESSIMISTIC", "BINGX_SIMULATION"]:
            # Evaluate cost on all primary events at horizon 60
            cost_results[scenario] = self.cost_model.evaluate_trades(test_events, horizon=60, scenario=scenario)
            
        # 8. Power
        # We compute the overall baseline volatility at h=60 for the simulation
        b_arr_60 = np.array(test_baseline_returns[60])
        baseline_std_60 = np.std(b_arr_60) if len(b_arr_60) > 0 else 0
        n_eff = len(test_events) # Approximation of effective test sample
        power_report = self.power.analyze_power(baseline_std=baseline_std_60, n_eff=n_eff)
        
        return {
            "audit": audit,
            "event_stats": event_stats,
            "folds": fold_reports,
            "statistical_results": results,
            "cost_results": cost_results,
            "power": power_report,
            "baselines": {h: {"N": len(test_baseline_returns[h]), "mean": np.mean(test_baseline_returns[h]), "std": np.std(test_baseline_returns[h])} for h in self.horizons}
        }
