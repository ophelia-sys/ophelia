import os
import sys
import json

# Ensure imports work without installing as package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from research.pipeline.data_loader import ResearchDataLoader
from research.pipeline.ablation import AblationFramework

def run_experiment():
    print("--- Running Experiment 001: BTCUSDT 5m Baseline Ablation ---")
    
    loader = ResearchDataLoader()
    df = loader.load_symbol("BTCUSDT")
    
    # Restrict to 2022+ for the experiment size bounds based on previous phases
    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[df['dt'].dt.year >= 2022].copy()
    
    ablation = AblationFramework(target_col='target_60', fwd_return_col='R_60', embargo=60)
    
    # Feature families
    sequence = [
        ['baseline'],
        ['baseline', 'volatility'],
        ['baseline', 'volatility', 'trend'],
        ['baseline', 'volatility', 'trend', 'momentum'],
        ['baseline', 'volatility', 'trend', 'momentum', 'volume']
    ]
    
    print("\nRunning Ablation Sequence with LogisticRegression...")
    results = ablation.run_ablation(df, sequence, model_name='logistic', costs_bps=12)
    
    # Output markdown report
    output_path = os.path.join("research", "EXPERIMENT_001_REPORT.md")
    with open(output_path, "w") as f:
        f.write("# EXPERIMENT 001: Baseline BTCUSDT (5m) Ablation\n\n")
        f.write("## Hypothesis\n")
        f.write("Does the incremental addition of Volatility, Trend, Momentum, and Volume features improve OOS predictive and economic metrics beyond simple returns?\n\n")
        f.write("## Validation\n")
        f.write("- **Method**: Purged Walk-Forward (3 folds)\n")
        f.write("- **Embargo**: 60 periods\n")
        f.write("- **Target**: target_60 (Directional return over next 60 periods, i.e., 5 hours)\n")
        f.write("- **Cost Assumption**: 12 bps round-trip\n\n")
        
        f.write("## Results (Logistic Regression)\n\n")
        
        for res in results:
            f.write(f"### Features: {res['families']}\n")
            f.write(f"- **AUC**: {res['metrics']['auc']:.4f}\n")
            f.write(f"- **Brier Score**: {res['metrics']['brier']:.4f}\n")
            f.write(f"- **95% CI**: [{res['metrics']['ci'][0]:.4f}, {res['metrics']['ci'][1]:.4f}]\n")
            f.write(f"- **Top Decile (9) Gross Ret (bps)**: {res['metrics']['deciles'][-1]['gross_ret_bps']:.2f}\n")
            f.write(f"- **Top Decile (9) Net Ret (bps)**: {res['metrics']['deciles'][-1]['net_ret_bps']:.2f}\n\n")
            
        f.write("## Conclusion\n")
        f.write("We observe the incremental changes in AUC and net economic returns. If the net economic return does not rise above 0, the model remains statistically significant but economically useless (STATISTICALLY_SIGNIFICANT_NOT_ECONOMIC).\n")
        
    print(f"Experiment completed. Report saved to {output_path}")

if __name__ == "__main__":
    import pandas as pd
    run_experiment()
