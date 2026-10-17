import os
import json
import pandas as pd
from datetime import datetime

RESULTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'results', 'VWAP_SUPERTREND_VOLUME_SOL_ETH_V1'))

def calculate_expectancy(win_rate, mean_return_pct):
    # gross expectancy in bps = mean_return_pct * 100
    return mean_return_pct * 100

def generate_report():
    with open(os.path.join(RESULTS_DIR, "sensitivity_results.json"), "r") as f:
        sensitivity = json.load(f)
        
    report = []
    
    report.append("# OPHELIA — VWAP + SUPERTREND + VOLUME STRATEGY V1 VALIDATION")
    report.append(f"Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
    
    report.append("## 1. Strategy Objective")
    report.append("Validate a deterministic V1 strategy for SOLUSDT and ETHUSDT using 5-minute candles, Session VWAP, Supertrend (10, 3.0), and Ophelia's volume aggregation logic. Live execution remains BLOCKED.\n")
    
    report.append("## 2. Pine Script Reference & 3. Exact V1 Interpretation")
    report.append("- **Pine Script Variant**: Triggered on `price crosses VWAP AND Supertrend is favorable`.")
    report.append("- **User V1 Interpretation**: Triggered on `Supertrend Direction Flips AND price is favorable relative to VWAP`.\n")
    
    report.append("## 4. Supertrend & 5. VWAP Validation")
    report.append("Supertrend uses `length=10, factor=3.0` calculated matching TradingView step logic. VWAP uses `(H+L+C)/3` typical price weighted by volume, resetting daily at 00:00 UTC.\n")
    
    report.append("## 6. Volume Data Validation & 7. Volume Rule Sensitivity")
    report.append("Volume features used standard Ophelia `volume` and `delta_v`. Multiplier sweeps were tested across 3, 5, 6 bar windows.\n")
    
    report.append("### Volume Sensitivity Results")
    report.append("| Symbol | Config | Trades | Win Rate | Mean Return (Gross) | Partial Rate |")
    report.append("|---|---|---|---|---|---|")
    
    for key, stats in sensitivity.items():
        sym = key.split('_')[0]
        config_name = key.replace(sym + '_', '')
        win_rate = stats.get('win_rate', 0) * 100
        mean_ret = stats.get('mean_return_pct', 0) * 100 # convert to bps
        partial = stats.get('partial_rate', 0) * 100
        report.append(f"| {sym} | {config_name} | {stats.get('total_trades', 0)} | {win_rate:.1f}% | {mean_ret:.1f} bps | {partial:.1f}% |")
    
    report.append("\n")
    
    # Analyze V1 Candidate Results explicitly
    v1_sol_stats = sensitivity.get("SOLUSDT_mult1.25_win5", {})
    v1_eth_stats = sensitivity.get("ETHUSDT_mult1.25_win5", {})
    
    report.append("## 17. SOL Results (V1: mult 1.25, win 5)")
    report.append(f"- **Trades**: {v1_sol_stats.get('total_trades', 0)}")
    report.append(f"- **Win Rate**: {v1_sol_stats.get('win_rate', 0)*100:.1f}%")
    report.append(f"- **Gross Expectancy**: {v1_sol_stats.get('mean_return_pct', 0)*100:.1f} bps")
    report.append(f"- **0.80% Partial Rate**: {v1_sol_stats.get('partial_rate', 0)*100:.1f}%\n")
    
    report.append("## 18. ETH Results (V1: mult 1.25, win 5)")
    report.append(f"- **Trades**: {v1_eth_stats.get('total_trades', 0)}")
    report.append(f"- **Win Rate**: {v1_eth_stats.get('win_rate', 0)*100:.1f}%")
    report.append(f"- **Gross Expectancy**: {v1_eth_stats.get('mean_return_pct', 0)*100:.1f} bps")
    report.append(f"- **0.80% Partial Rate**: {v1_eth_stats.get('partial_rate', 0)*100:.1f}%\n")
    
    # Calculate costs
    for sym, stats in [("SOL", v1_sol_stats), ("ETH", v1_eth_stats)]:
        gross = stats.get('mean_return_pct', 0) * 100
        report.append(f"### 21. Cost Sensitivity ({sym})")
        report.append(f"- Gross: {gross:.1f} bps")
        for cost in [8, 12, 16, 20]:
            net = gross - cost
            report.append(f"- Net at {cost} bps friction: {net:.1f} bps")
        report.append("")
        
    report.append("## 22. Pine Variant Comparison")
    # We load Pine variant events to see how many there are and what they returned
    # But wait, pine results are in jsonl, let's load them
    def compute_stats_from_events(path):
        if not os.path.exists(path): return {}
        events = [json.loads(line) for line in open(path)]
        if not events: return {"trades": 0}
        df = pd.DataFrame(events)
        realized = []
        for _, row in df.iterrows():
            if row['partial_achieved']:
                realized.append(0.5 * 0.80 + 0.5 * row['return_pct'])
            else:
                realized.append(row['return_pct'])
        df['realized_return_pct'] = realized
        return {
            "trades": len(df),
            "win_rate": float((df['realized_return_pct'] > 0).mean()) * 100,
            "mean_ret": float(df['realized_return_pct'].mean()) * 100
        }
    
    sol_pine = compute_stats_from_events(os.path.join(RESULTS_DIR, "SOLUSDT_pine_ref_events.jsonl"))
    eth_pine = compute_stats_from_events(os.path.join(RESULTS_DIR, "ETHUSDT_pine_ref_events.jsonl"))
    
    report.append(f"- **SOL Pine Variant**: {sol_pine.get('trades', 0)} trades, {sol_pine.get('win_rate', 0):.1f}% win rate, {sol_pine.get('mean_ret', 0):.1f} bps gross.")
    report.append(f"- **ETH Pine Variant**: {eth_pine.get('trades', 0)} trades, {eth_pine.get('win_rate', 0):.1f}% win rate, {eth_pine.get('mean_ret', 0):.1f} bps gross.\n")
    
    report.append("## 23. Edge Cases & Intrabar Assumptions")
    report.append("Intrabar assumption conservatively assumed that if a Stop and the 0.80% milestone were both breached in the same 5m candle, the **Stop was hit first**. This prevents manufacturing artificial performance.\n")
    
    report.append("## 26. LOCAL/VPS Status & 27. Shadow Readiness")
    report.append("Research completed locally. Not yet synchronized to VPS. Shadow mode disabled.\n")
    
    # Final recommendation logic
    sol_net = (v1_sol_stats.get('mean_return_pct', 0) * 100) - 12
    eth_net = (v1_eth_stats.get('mean_return_pct', 0) * 100) - 12
    
    report.append("## 29. Final Recommendation")
    if sol_net > 0 and eth_net > 0:
        report.append("### READY FOR SHADOW")
        report.append("The V1 strategy produces a positive net expectancy after 12 bps execution costs on both SOL and ETH, confirming the viability of the Supertrend flip + volume expansion hypothesis.")
    else:
        report.append("### NOT READY — FIX REQUIRED")
        report.append("The strategy fails to demonstrate a sufficient net expectancy after 12 bps execution friction.")
        if sol_net <= 0:
            report.append(f"- SOL Net Expectancy (12 bps): {sol_net:.1f} bps")
        if eth_net <= 0:
            report.append(f"- ETH Net Expectancy (12 bps): {eth_net:.1f} bps")
        report.append("The 1-bps buffer stop may be too tight, causing premature stop-outs before the 0.80% milestone is achieved. The volume multiplier rules showed mixed success.")
        
    out_path = os.path.join(RESULTS_DIR, f"OPHELIA_VWAP_SUPERTREND_VOLUME_STRATEGY_VALIDATION_{datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S')}.md")
    with open(out_path, "w") as f:
        f.write("\n".join(report))
        
    print(f"Report generated: {out_path}")

if __name__ == "__main__":
    generate_report()
