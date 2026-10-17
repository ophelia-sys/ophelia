import json
import os
import numpy as np

with open('research/results/PHASE5_2_1_LSR_VALIDATION_MANIFEST.json', 'r') as f:
    data = json.load(f)

symbols = data['symbols']

output = ["# PHASE 5.2.1 LSR VALIDATION AUDIT\n"]

output.append("## 1. Executive Conclusion\n")

# Analyze results to build the conclusion dynamically
brier_diffs = []
dm_p_vals = []
net_returns_base = []
net_returns_lsr = []

for sym in symbols:
    cfg = data['results'][sym]['configs']['1440']
    b_base = sum(f['brier'] for f in cfg['BASE']['folds']) / 3
    b_lsr = sum(f['brier'] for f in cfg['LSR3']['folds']) / 3
    brier_diffs.append(b_lsr - b_base)
    
    dm_p_vals.append(cfg['LSR3'].get('dm_p_value', 1.0))
    
    nr_base = sum(f['economics']['top20'].get('net_bps_cost_12', 0) for f in cfg['BASE']['folds']) / 3
    nr_lsr = sum(f['economics']['top20'].get('net_bps_cost_12', 0) for f in cfg['LSR3']['folds']) / 3
    net_returns_base.append(nr_base)
    net_returns_lsr.append(nr_lsr)

mean_brier_diff = np.mean(brier_diffs)
median_brier_diff = np.median(brier_diffs)
symbols_improved = sum(1 for d in brier_diffs if d < 0)
mean_nr_base = np.mean(net_returns_base)
mean_nr_lsr = np.mean(net_returns_lsr)
mean_nr_diff = mean_nr_lsr - mean_nr_base

output.append(f"**Classification: RETAIN / INCONCLUSIVE / REMOVE**\n")
output.append(f"*(To be manually finalized based on criteria below)*\n\n")

output.append("### Summary of Evidence\n")
output.append(f"- **Predictive Improvement**: LSR improved the Brier score on {symbols_improved} out of {len(symbols)} symbols. Mean Brier Delta: {mean_brier_diff:.6f}.\n")
output.append(f"- **Economic Improvement**: Mean Top 20% Net Return (12 bps) changed from {mean_nr_base:.2f} to {mean_nr_lsr:.2f} bps (Delta: {mean_nr_diff:+.2f} bps).\n")
output.append(f"- **Statistical Significance**: Median DM p-value: {np.median(dm_p_vals):.4f}.\n")

output.append("\n## 2. Feature Isolation (Config 1440)\n")
output.append("| Symbol | BASE | LSR1 (Z-Score) | LSR2 (Change) | LSR3 (Combined) | Best |\n")
output.append("|---|---|---|---|---|---|\n")
for sym in symbols:
    cfg = data['results'][sym]['configs']['1440']
    b_b = sum(f['brier'] for f in cfg['BASE']['folds']) / 3
    b_1 = sum(f['brier'] for f in cfg['LSR1']['folds']) / 3
    b_2 = sum(f['brier'] for f in cfg['LSR2']['folds']) / 3
    b_3 = sum(f['brier'] for f in cfg['LSR3']['folds']) / 3
    
    vals = {'BASE': b_b, 'LSR1': b_1, 'LSR2': b_2, 'LSR3': b_3}
    best = min(vals, key=vals.get)
    
    output.append(f"| {sym} | {b_b:.6f} | {b_1:.6f} | {b_2:.6f} | {b_3:.6f} | {best} |\n")

output.append("\n## 3. Statistical Tests (LSR3 vs BASE)\n")
output.append("| Symbol | DM Stat | DM p-val | Permutation p-vals (Folds 1, 2, 3) |\n")
output.append("|---|---|---|---|\n")
for sym in symbols:
    cfg = data['results'][sym]['configs']['1440']
    dm_stat = cfg['LSR3'].get('dm_stat', 0)
    dm_p = cfg['LSR3'].get('dm_p_value', 1.0)
    perm_p = [f.get('perm_p_value', 1.0) for f in cfg['LSR3']['folds']]
    output.append(f"| {sym} | {dm_stat:.3f} | {dm_p:.4f} | {perm_p[0]:.4f}, {perm_p[1]:.4f}, {perm_p[2]:.4f} |\n")

output.append("\n## 4. Confidence Intervals (Block Bootstrap)\n")
output.append("| Symbol | 95% CI ΔBrier | 95% CI ΔGross (bps) |\n")
output.append("|---|---|---|\n")
for sym in symbols:
    cfg = data['results'][sym]['configs']['1440']
    ci_b = cfg['LSR3'].get('ci_95_delta_brier', [0, 0])
    ci_g = cfg['LSR3'].get('ci_95_delta_gross_bps', [0, 0])
    output.append(f"| {sym} | [{ci_b[0]:.6f}, {ci_b[1]:.6f}] | [{ci_g[0]:.2f}, {ci_g[1]:.2f}] |\n")

output.append("\n## 5. Economic Ranking (Top 20% Buckets)\n")
costs = [0, 5, 8, 12, 15, 20, 25]
output.append(f"| Symbol | BASE Net (12bps) | LSR3 Net (12bps) | Δ Net (bps) | Hit Rate BASE | Hit Rate LSR3 |\n")
output.append("|---|---|---|---|---|---|\n")
for sym in symbols:
    cfg = data['results'][sym]['configs']['1440']
    nr_b = sum(f['economics']['top20'].get('net_bps_cost_12', 0) for f in cfg['BASE']['folds']) / 3
    nr_l = sum(f['economics']['top20'].get('net_bps_cost_12', 0) for f in cfg['LSR3']['folds']) / 3
    hr_b = sum(f['economics']['top20'].get('hit_rate', 0) for f in cfg['BASE']['folds']) / 3
    hr_l = sum(f['economics']['top20'].get('hit_rate', 0) for f in cfg['LSR3']['folds']) / 3
    output.append(f"| {sym} | {nr_b:.2f} | {nr_l:.2f} | {nr_l - nr_b:+.2f} | {hr_b:.4f} | {hr_l:.4f} |\n")

output.append("\n## 6. Forward-Fill Sensitivity (LSR3 Brier)\n")
output.append("| Symbol | 1440m (24h) | 60m (1h) | 0m (Exact Match) |\n")
output.append("|---|---|---|---|\n")
for sym in symbols:
    c = data['results'][sym]['configs']
    b_1440 = sum(f['brier'] for f in c.get('1440', {}).get('LSR3', {'folds': [{'brier':0}]*3})['folds']) / 3
    b_60 = sum(f['brier'] for f in c.get('60', {}).get('LSR3', {'folds': [{'brier':0}]*3})['folds']) / 3
    b_0 = sum(f['brier'] for f in c.get('0', {}).get('LSR3', {'folds': [{'brier':0}]*3})['folds']) / 3
    output.append(f"| {sym} | {b_1440:.6f} | {b_60:.6f} | {b_0:.6f} |\n")

output.append("\n## 7. Temporal Stability (Yearly Brier)\n")
output.append("| Symbol | BASE 2022 | LSR3 2022 | BASE 2023 | LSR3 2023 |\n")
output.append("|---|---|---|---|---|\n")
for sym in symbols:
    cfg = data['results'][sym]['configs']['1440']
    
    def get_yr(model, yr):
        s = 0; n = 0
        for f in cfg[model]['folds']:
            if str(yr) in f['years']:
                s += f['years'][str(yr)]['brier']
                n += 1
        return s/n if n > 0 else 0
        
    b_b_22 = get_yr('BASE', 2022)
    b_l_22 = get_yr('LSR3', 2022)
    b_b_23 = get_yr('BASE', 2023)
    b_l_23 = get_yr('LSR3', 2023)
    
    output.append(f"| {sym} | {b_b_22:.6f} | {b_l_22:.6f} | {b_b_23:.6f} | {b_l_23:.6f} |\n")

output.append("\n## 8. Data Audit\n")
output.append("| Symbol | First Valid LSR | Total Missing LSR |\n")
output.append("|---|---|---|\n")
for sym in symbols:
    audit = data['results'][sym]['data_audit']
    output.append(f"| {sym} | {audit.get('first_valid_lsr', 'N/A')} | {audit.get('total_missing_lsr', 'N/A')} |\n")

with open(os.path.join(os.path.dirname(__file__), '../../PHASE5_2_1_LSR_VALIDATION_AUDIT.md'), 'w', encoding='utf-8') as f:
    f.writelines(output)

print("Report generated at PHASE5_2_1_LSR_VALIDATION_AUDIT.md")
