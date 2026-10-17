import json
import os
import numpy as np

with open('research/results/PHASE5_2_1_LSR_VALIDATION_MANIFEST.json', 'r') as f:
    data = json.load(f)

symbols = data['symbols']

output = ["# PHASE 5.2.1 LSR VALIDATION AUDIT\n\n"]
output.append("> [!WARNING]\n")
output.append("> **Classification: INCONCLUSIVE**\n")
output.append("> LSR has sufficient evidence to justify further research, but not enough evidence for unconditional production retention. It is marked as **RESEARCH_CANDIDATE** (STATUS = INCONCLUSIVE) and will NOT be integrated into the production probability engine at this time.\n\n")

# --- Stats calculation for Section 6 ---
brier_diffs = []
brier_diffs_2022 = []
brier_diffs_2023 = []

for sym in symbols:
    cfg = data['results'][sym]['configs']['1440']
    b_b = sum(f['brier'] for f in cfg['BASE']['folds']) / 3
    b_l = sum(f['brier'] for f in cfg['LSR3']['folds']) / 3
    brier_diffs.append(b_l - b_b)
    
    def get_yr(model, yr):
        s, n = 0, 0
        for f in cfg[model]['folds']:
            if str(yr) in f['years']:
                s += f['years'][str(yr)]['brier']
                n += 1
        return s/n if n > 0 else 0

    diff_22 = get_yr('LSR3', 2022) - get_yr('BASE', 2022)
    diff_23 = get_yr('LSR3', 2023) - get_yr('BASE', 2023)
    brier_diffs_2022.append(diff_22)
    brier_diffs_2023.append(diff_23)

def get_stats(arr):
    return {
        'mean': np.mean(arr),
        'median': np.median(arr),
        'std': np.std(arr),
        'min': np.min(arr),
        'max': np.max(arr),
        'consistency': sum(1 for x in arr if x < 0)
    }

stats_all = get_stats(brier_diffs)
stats_2022 = get_stats(brier_diffs_2022)
stats_2023 = get_stats(brier_diffs_2023)

# --- Sections ---
output.append("## 1. Executive Summary & Multiple Testing\n")
output.append("The research has now tested 6 symbols, multiple LSR configurations, multiple folds, multiple years, and multiple economic thresholds. Research multiplicity must be explicitly acknowledged: evaluating multiple assets and regimes increases the likelihood of finding isolated significant results by chance.\n\n")
output.append("While LSR demonstrates average Brier improvement and robustness to missing-data treatment, its effect size is very small, block bootstrap CIs cross zero for 4/6 symbols, DM tests fail significance for SOL/XRP, permutation fails in multiple folds, and no symbol becomes profitable at 12bps. Therefore, the effect does not pass a strict threshold for unconditional production use.\n\n")

output.append("## 2. Statistical Tests (DM & Permutation Stability)\n")
output.append("The effect does NOT pass a strict \"significant in every fold\" criterion. Permutation failures occur in multiple independent walk-forward folds.\n\n")
output.append("| Symbol | DM Stat | DM p-val | Permutation p-vals (Folds 1, 2, 3) |\n")
output.append("|---|---|---|---|\n")
for sym in symbols:
    cfg = data['results'][sym]['configs']['1440']
    dm_s = cfg['LSR3'].get('dm_stat', 0)
    dm_p = cfg['LSR3'].get('dm_p_value', 1.0)
    perm_p = [f.get('perm_p_value', 1.0) for f in cfg['LSR3']['folds']]
    output.append(f"| {sym} | {dm_s:.3f} | {dm_p:.4f} | {perm_p[0]:.4f}, {perm_p[1]:.4f}, {perm_p[2]:.4f} |\n")
output.append("\n**DM Test Interpretation**: 4/6 symbols reject the equal-predictive-accuracy null at alpha=0.05. Given 6 tests, multiple testing correction tempers this significance.\n\n")

output.append("## 3. Confidence Intervals (Block Bootstrap)\n")
output.append("Only ETH and ADA have intervals that clearly exclude zero. BTC, SOL, XRP, and BNB have intervals containing zero.\n\n")
output.append("| Symbol | 95% CI ΔBrier | 95% CI ΔGross (bps) |\n")
output.append("|---|---|---|\n")
for sym in symbols:
    cfg = data['results'][sym]['configs']['1440']
    ci_b = cfg['LSR3'].get('ci_95_delta_brier', [0, 0])
    ci_g = cfg['LSR3'].get('ci_95_delta_gross_bps', [0, 0])
    output.append(f"| {sym} | [{ci_b[0]:.6f}, {ci_b[1]:.6f}] | [{ci_g[0]:.2f}, {ci_g[1]:.2f}] |\n")

output.append("\n## 4. Economic Result\n")
output.append("LSR currently demonstrates incremental predictive/ranking information, but NOT a standalone profitable trading edge. All six remain negative after 12bps transaction costs.\n\n")
output.append("| Symbol | BASE Net (12bps) | LSR3 Net (12bps) | Δ Net (bps) |\n")
output.append("|---|---|---|---|\n")
for sym in symbols:
    cfg = data['results'][sym]['configs']['1440']
    nr_b = sum(f['economics']['top20'].get('net_bps_cost_12', 0) for f in cfg['BASE']['folds']) / 3
    nr_l = sum(f['economics']['top20'].get('net_bps_cost_12', 0) for f in cfg['LSR3']['folds']) / 3
    output.append(f"| {sym} | {nr_b:.2f} | {nr_l:.2f} | {nr_l - nr_b:+.2f} |\n")

output.append("\n## 5. Temporal Stability\n")
output.append("The effect is not uniformly stable across regimes.\n")
output.append("- **BTC**: relatively stable\n")
output.append("- **ETH**: relatively stable\n")
output.append("- **SOL**: negative/inconsistent\n")
output.append("- **XRP**: relatively stable but statistically weak\n")
output.append("- **BNB**: regime-dependent\n")
output.append("- **ADA**: relatively stable\n\n")
output.append("| Symbol | BASE 2022 | LSR3 2022 | BASE 2023 | LSR3 2023 |\n")
output.append("|---|---|---|---|---|\n")
for sym in symbols:
    cfg = data['results'][sym]['configs']['1440']
    def get_yr(model, yr):
        s, n = 0, 0
        for f in cfg[model]['folds']:
            if str(yr) in f['years']:
                s += f['years'][str(yr)]['brier']
                n += 1
        return s/n if n > 0 else 0
    b_b_22 = get_yr('BASE', 2022); b_l_22 = get_yr('LSR3', 2022)
    b_b_23 = get_yr('BASE', 2023); b_l_23 = get_yr('LSR3', 2023)
    output.append(f"| {sym} | {b_b_22:.6f} | {b_l_22:.6f} | {b_b_23:.6f} | {b_l_23:.6f} |\n")

output.append("\n## 6. Cross-Asset Effect Size\n")
output.append("| Metric | All Years | 2022 | 2023 |\n")
output.append("|---|---|---|---|\n")
output.append(f"| Mean ΔBrier | {stats_all['mean']:.6f} | {stats_2022['mean']:.6f} | {stats_2023['mean']:.6f} |\n")
output.append(f"| Median ΔBrier | {stats_all['median']:.6f} | {stats_2022['median']:.6f} | {stats_2023['median']:.6f} |\n")
output.append(f"| Std Dev | {stats_all['std']:.6f} | {stats_2022['std']:.6f} | {stats_2023['std']:.6f} |\n")
output.append(f"| Min | {stats_all['min']:.6f} | {stats_2022['min']:.6f} | {stats_2023['min']:.6f} |\n")
output.append(f"| Max | {stats_all['max']:.6f} | {stats_2022['max']:.6f} | {stats_2023['max']:.6f} |\n")
output.append(f"| Negative Direction (Improvement) | {stats_all['consistency']}/6 | {stats_2022['consistency']}/6 | {stats_2023['consistency']}/6 |\n")

output.append("\n## 7. Next Research Question\n")
output.append("Before deciding whether LSR deserves production status, the next question is:\n")
output.append("> *Does LSR provide incremental economic value when combined with the next independent information source?*\n\n")
output.append("The next candidate is CVD / aggressor order flow. Current Phase 5.2.1 results and manifest are now **FROZEN** as a historical research record.\n")

with open(os.path.join(os.path.dirname(__file__), '../../PHASE5_2_1_LSR_VALIDATION_AUDIT.md'), 'w', encoding='utf-8') as f:
    f.writelines(output)
