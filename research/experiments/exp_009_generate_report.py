import os
import json
from datetime import datetime

def load_json(filename):
    path = os.path.join(os.path.dirname(__file__), filename)
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}

def format_bps(val):
    if val is None: return "N/A"
    return f"{val:+.2f} bps"

def format_pct(val):
    if val is None: return "N/A"
    return f"{val * 100:.2f}%"

def main():
    entry_res = load_json("component_forensics_entry.json")
    exit_res = load_json("component_forensics_exit.json")
    deep_res = load_json("component_forensics_deep.json")
    
    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    report_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), 
        f"../../../../.gemini/antigravity-ide/brain/20c1895a-9ffa-4c76-b74e-b5e10027aae2/OPHELIA_VWAP_SUPERTREND_COMPONENT_FORENSICS_{timestamp}.md"
    ))
    
    lines = [
        f"# OPHELIA — V1.2 COMPONENT FORENSICS REPORT",
        f"Generated: {timestamp} UTC\n",
        "## 1. Executive Summary",
        "This report isolates the Entry vs Exit quality of the deterministic VWAP + Supertrend + Volume + Anti-Chop strategy. "
        "The objective is to determine whether the strategy's current lack of robust performance is due to a weak core entry signal or a risk-management (exit) framework that is destroying edge.\n",
        "## 2. Data and Validation Periods",
        "- **Symbols:** SOLUSDT, ETHUSDT",
        "- **Timeframe:** 5-minute",
        "- **Period:** Inception to 2023-10-31 (Blind Holdout strictly excluded)",
        "- **Entry Timing:** OPEN of candle $t+1$ (strictly causal after signal at CLOSE of candle $t$).\n",
        "## 3. Entry Ablation Matrix (Entry Quality Before Any Exit)\n"
    ]
    
    configs = {
        "A": "Raw Supertrend",
        "B": "Supertrend + VWAP",
        "C": "Supertrend + Volume",
        "D": "Supertrend + Anti-Chop",
        "E": "Supertrend + VWAP + Volume",
        "F": "Supertrend + VWAP + Anti-Chop",
        "G": "Supertrend + Volume + Anti-Chop",
        "H": "Full V1.1 (ST + VWAP + Vol + Chop)"
    }
    
    for c_id, c_name in configs.items():
        lines.append(f"### Configuration {c_id}: {c_name}")
        lines.append("| Symbol | Side | Trades | 5m Fwd | 15m Fwd | 30m Fwd | 60m Fwd | 60m MFE | 60m MAE | % > 0 | % > 20bps | % > 80bps |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for sym in ["SOLUSDT", "ETHUSDT"]:
            for side in ["L", "S"]:
                k = f"{sym}_{c_id}_{side}"
                if k in entry_res:
                    s = entry_res[k]
                    if s.get('trades', 0) > 0:
                        lines.append(
                            f"| {sym} | {side} | {s['trades']} | {format_bps(s.get('mean_5m_bps'))} | {format_bps(s.get('mean_15m_bps'))} | "
                            f"{format_bps(s.get('mean_30m_bps'))} | {format_bps(s.get('mean_60m_bps'))} | "
                            f"{format_bps(s.get('mean_mfe_bps'))} | {format_bps(s.get('mean_mae_bps'))} | "
                            f"{format_pct(s.get('pct_gt_0'))} | {format_pct(s.get('pct_gt_20bps'))} | {format_pct(s.get('pct_gt_80bps'))} |"
                        )
        lines.append("")
        
    lines.append("## 4. VWAP Filter Study")
    lines.append("| Symbol | Side | Filter | Trades | Mean 60m Fwd |")
    lines.append("|---|---|---|---|---|")
    if 'vwap' in deep_res:
        for k, v in deep_res['vwap'].items():
            sym, side, dist = k.split('_')
            lines.append(f"| {sym} | {side} | {dist} | {v['trades']} | {format_bps(v['mean_60m_bps'])} |")
    lines.append("\n## 5. Volume Study")
    lines.append("| Symbol | Side | Volume Filter | Trades | Mean 60m Fwd |")
    lines.append("|---|---|---|---|---|")
    if 'volume' in deep_res:
        for k, v in deep_res['volume'].items():
            parts = k.split('_')
            sym, side, vol_type = parts[0], parts[1], parts[2]
            lines.append(f"| {sym} | {side} | {vol_type} | {v['trades']} | {format_bps(v['mean_60m_bps'])} |")
            
    lines.append("\n## 6. Anti-Chop Study")
    lines.append("| Symbol | Side | Raw Signals | Removed | Fav. Removed | Unfav. Removed | Pre-Filter 60m | Post-Filter 60m |")
    lines.append("|---|---|---|---|---|---|---|---|")
    if 'chop' in deep_res:
        for k, v in deep_res['chop'].items():
            sym, side = k.split('_')
            lines.append(
                f"| {sym} | {side} | {v['raw_signals']} | {v['removed_signals']} | "
                f"{v['favorable_removed']} | {v['unfavorable_removed']} | "
                f"{format_bps(v['pre_filter_mean_bps'])} | {format_bps(v['post_filter_mean_bps'])} |"
            )
            
    lines.append("\n## 7. Exit-Only Comparison (Config H Entries)")
    lines.append("Comparing exits for the exact same entry timestamps (V1.1 Full entries).")
    
    exit_names = {
        "A": "V1.1 Current Risk (VWAP stop + milestone + trailing)",
        "B": "Fixed 15m (3 bars)",
        "C": "Fixed 30m (6 bars)",
        "D": "Fixed 60m (12 bars)",
        "E": "Opposite Supertrend",
        "F": "VWAP Loss"
    }
    
    for cost in [8, 12, 16, 20]:
        lines.append(f"\n### Cost Sensitivity: {cost} bps round-trip")
        lines.append("| Symbol | Exit Type | Trades | Win Rate | Mean Gross | Mean Net | Median Net | Avg Hold Bars | Profit Factor |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for sym in ["SOLUSDT", "ETHUSDT"]:
            for ex in ["A", "B", "C", "D", "E", "F"]:
                k = f"{sym}_Exit_{ex}_Cost_{cost}"
                if k in exit_res:
                    s = exit_res[k]
                    if s.get('trades', 0) > 0:
                        pf = f"{s['profit_factor']:.2f}" if s['profit_factor'] != float('inf') else "INF"
                        lines.append(
                            f"| {sym} | {exit_names[ex]} | {s['trades']} | {format_pct(s['win_rate'])} | "
                            f"{format_bps(s['mean_gross_bps'])} | {format_bps(s['mean_net_bps'])} | "
                            f"{format_bps(s['median_net_bps'])} | {s['avg_holding_bars']:.1f} | {pf} |"
                        )
                        
    lines.append("\n## 8. Entry vs Exit Diagnosis")
    lines.append("### Entry Assessment")
    lines.append("- Reviewing the 60m forward expectancy (Entry Ablation Matrix).")
    lines.append("- Identifying if the core edge exists before any exits.")
    lines.append("\n### Exit Assessment")
    lines.append("- Reviewing if simple fixed-time or structural exits outperform the complex V1.1 Exit (A).")
    lines.append("\n## 9. Final Decision")
    lines.append("To be concluded after manual review of the metrics above.")
    
    with open(report_path, "w") as f:
        f.write("\n".join(lines))
    print(f"Generated report at {report_path}")

if __name__ == "__main__":
    main()
