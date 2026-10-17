import pandas as pd
import numpy as np
import os
import json

def calculate_conditional_maker_economics(df, maker_fee_bps=0.0):
    """
    Calculate theoretical maker economics conditionally on getting filled.
    A bid placed at the end of minute T at `best_bid` is only filled 
    if the `low` of minute T+1 is <= `best_bid`.
    """
    results = {}
    
    # Best Bid at end of minute = Close - (End Spread / 2)
    df['mid_p'] = df['close']
    df['best_bid'] = df['mid_p'] - (df['end_spread'] / 2)
    df['best_ask'] = df['mid_p'] + (df['end_spread'] / 2)
    
    # Next minute low and high
    df['next_low'] = df['low'].shift(-1)
    df['next_high'] = df['high'].shift(-1)
    
    # Future mid prices
    df['mid_p_plus_1'] = df['mid_p'].shift(-1)
    df['mid_p_plus_5'] = df['mid_p'].shift(-5)
    
    # Did the bid get filled?
    df['bid_filled'] = df['next_low'] <= df['best_bid']
    # Did the ask get filled?
    df['ask_filled'] = df['next_high'] >= df['best_ask']
    
    # Conditional MTM for Bid
    # If filled, MTM is (Future Mid) - Fill Price (best_bid)
    # We will measure MTM 5 minutes later
    df.loc[df['bid_filled'], 'bid_mtm_5m'] = df['mid_p_plus_5'] - df['best_bid']
    df.loc[df['ask_filled'], 'ask_mtm_5m'] = df['best_ask'] - df['mid_p_plus_5']  # Short MTM
    
    # Convert to bps
    df['bid_mtm_5m_bps'] = (df['bid_mtm_5m'] / df['best_bid']) * 10000
    df['ask_mtm_5m_bps'] = (df['ask_mtm_5m'] / df['best_ask']) * 10000
    
    # Total Gross EV is the MTM of filled bids + filled asks
    df['gross_maker_pnl_bps'] = 0.0
    df.loc[df['bid_filled'], 'gross_maker_pnl_bps'] += df['bid_mtm_5m_bps']
    df.loc[df['ask_filled'], 'gross_maker_pnl_bps'] += df['ask_mtm_5m_bps']
    
    # Number of fills
    df['num_fills'] = df['bid_filled'].astype(int) + df['ask_filled'].astype(int)
    
    # Net EV subtracts the maker fee per fill
    df['net_maker_pnl_bps'] = df['gross_maker_pnl_bps'] - (df['num_fills'] * maker_fee_bps)
    
    # Overall statistics
    total_minutes = len(df.dropna(subset=['mid_p_plus_5']))
    bid_fills = df['bid_filled'].sum()
    ask_fills = df['ask_filled'].sum()
    total_fills = bid_fills + ask_fills
    
    fill_prob_bid = bid_fills / total_minutes
    fill_prob_ask = ask_fills / total_minutes
    
    avg_gross_ev_per_fill = df['gross_maker_pnl_bps'].sum() / total_fills if total_fills > 0 else 0
    avg_net_ev_per_fill = df['net_maker_pnl_bps'].sum() / total_fills if total_fills > 0 else 0
    
    results['fill_prob_bid'] = fill_prob_bid
    results['fill_prob_ask'] = fill_prob_ask
    results['avg_gross_ev_per_fill_bps'] = avg_gross_ev_per_fill
    results['avg_net_ev_per_fill_bps'] = avg_net_ev_per_fill
    results['total_net_pnl_bps'] = df['net_maker_pnl_bps'].sum()
    results['avg_half_spread_bps'] = ((df['end_spread'] / 2) / df['mid_p'] * 10000).mean()
    
    return results

def run_branch_a():
    print("========================================")
    print("EXP 031: BRANCH A - CONDITIONAL MAKER ECONOMICS")
    print("========================================")
    
    dev = pd.read_parquet("data/processed/phase5_5/BTCUSDT_context_dev.parquet")
    val = pd.read_parquet("data/processed/phase5_5/BTCUSDT_context_val.parquet")
    oos = pd.read_parquet("data/processed/phase5_5/BTCUSDT_context_oos.parquet")
    
    df = pd.concat([dev, val, oos], ignore_index=True)
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    print(f"Loaded {len(df)} 1-minute rows (Nov 1 - Nov 15).")
    
    maker_fees = [2.0, 0.0, -1.2]
    results_list = []
    
    for fee in maker_fees:
        res = calculate_conditional_maker_economics(df.copy(), maker_fee_bps=fee)
        res['maker_fee_bps'] = fee
        results_list.append(res)
            
    res_df = pd.DataFrame(results_list)
    
    out_dir = "research/results/phase5_6"
    os.makedirs(out_dir, exist_ok=True)
    res_df.to_csv(os.path.join(out_dir, "branch_a_maker_economics.csv"), index=False)
    
    print(res_df.to_string(index=False))

if __name__ == "__main__":
    run_branch_a()
