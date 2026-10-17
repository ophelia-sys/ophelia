import os
import sys
sys.path.insert(0, r'c:\Users\dopa.mine\Desktop\ophelia')

import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from research.pipeline.data_loader import ResearchDataLoader
from research.pipeline.features import FeatureGenerator
from research.pipeline.labels import LabelGenerator, OUTCOME_TIMEOUT, OUTCOME_TARGET, OUTCOME_STOP, OUTCOME_AMBIGUOUS
import os

# Create experiment report directory
os.makedirs(r'c:\Users\dopa.mine\Desktop\ophelia\research\experiments', exist_ok=True)

# 1. Load Data
loader = ResearchDataLoader()
df = loader.load_symbol('BTCUSDT')

# 2. Add Baseline Features
print("Generating features...")
families = ['baseline', 'volatility', 'trend', 'momentum', 'volume']
df = FeatureGenerator.generate_features(df, families)
feature_cols = FeatureGenerator.get_feature_columns(families)

# Drop NaNs
df = df.dropna(subset=feature_cols)

# We use the previous development set (e.g. up to 2023-06-30 for dev, holding out final period)
# The old locked OOS is closed, but the user said:
# "Create a new Phase 5.3 candidate-selection workflow:
# DEVELOPMENT -> VALIDATION -> CANDIDATE LOCK -> NEW UNTOUCHED OOS"
# Let's define:
# Dev: 2022-01-01 to 2023-03-31
# Val: 2023-04-01 to 2023-06-30
# New OOS: 2023-07-01 to 2023-12-31

# Assuming 'timestamp' is unix millis
df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

# 3. Grid Search settings
barrier_grid = [
    (10, 10), (15, 10), (20, 10), 
    (20, 15), (30, 15), (30, 20)
]
timeouts = [15, 30, 60]

print("Evaluating Barrier/Timeout grid unconditionally for baselines...")
results = []
for tp, sl in barrier_grid:
    for t_out in timeouts:
        # Generate labels
        df_labeled = LabelGenerator.generate_barrier_labels(df, target_bps=tp, stop_bps=sl, timeout_candles=t_out, is_long=True, prefix="tmp")
        
        # Unconditional stats on the whole dataset for this grid config (just as a baseline)
        c_tot = len(df_labeled)
        c_target = (df_labeled['tmp_outcome'] == OUTCOME_TARGET).sum()
        c_stop = (df_labeled['tmp_outcome'] == OUTCOME_STOP).sum()
        c_time = (df_labeled['tmp_outcome'] == OUTCOME_TIMEOUT).sum()
        c_ambig = (df_labeled['tmp_outcome'] == OUTCOME_AMBIGUOUS).sum()
        
        results.append({
            'target_bps': tp,
            'stop_bps': sl,
            'timeout_m': t_out,
            'prob_target': c_target / c_tot,
            'prob_stop': c_stop / c_tot,
            'prob_timeout': c_time / c_tot,
            'prob_ambiguous': c_ambig / c_tot
        })

res_df = pd.DataFrame(results)
print(res_df)

# Now, we train a LightGBM model for a specific target barrier just to evaluate Cost Sensitivity
# Let's pick a balanced one, e.g. +20 / -15 with 60m timeout
CHOSEN_TP = 20
CHOSEN_SL = 15
CHOSEN_TO = 60
print(f"\nTraining model for {CHOSEN_TP}/{CHOSEN_SL} at {CHOSEN_TO}m...")

df_model = LabelGenerator.generate_barrier_labels(df, target_bps=CHOSEN_TP, stop_bps=CHOSEN_SL, timeout_candles=CHOSEN_TO, is_long=True, prefix="b")

# The model predicts the probability of TARGET_HIT
# Wait, for a conservative approach we exclude AMBIGUOUS from training or treat as 0
# Let's treat TARGET as 1, all others as 0.
df_model['y_target'] = (df_model['b_outcome'] == OUTCOME_TARGET).astype(int)

# Split sets
dev_mask = df_model['datetime'] < '2023-04-01'
val_mask = (df_model['datetime'] >= '2023-04-01') & (df_model['datetime'] < '2023-07-01')
oos_mask = df_model['datetime'] >= '2023-07-01'

X_train, y_train = df_model.loc[dev_mask, feature_cols], df_model.loc[dev_mask, 'y_target']
X_val, y_val = df_model.loc[val_mask, feature_cols], df_model.loc[val_mask, 'y_target']
X_test = df_model.loc[val_mask, feature_cols] # We predict on validation set to avoid locking OOS

lgb_train = lgb.Dataset(X_train, y_train)
lgb_val = lgb.Dataset(X_val, y_val, reference=lgb_train)

params = {
    'objective': 'binary',
    'metric': 'auc',
    'learning_rate': 0.05,
    'num_leaves': 15,
    'max_depth': 4,
    'seed': 42,
    'verbose': -1
}

model = lgb.train(
    params,
    lgb_train,
    num_boost_round=200,
    valid_sets=[lgb_train, lgb_val],
    callbacks=[lgb.early_stopping(stopping_rounds=20, verbose=False)]
)

print("\nModel trained. Evaluating cost sensitivity on Validation Set...")

# Predict on val
val_df = df_model.loc[val_mask].copy()
val_df['pred'] = model.predict(X_val)

# Take top decile for trading
threshold = val_df['pred'].quantile(0.90)
trades = val_df[val_df['pred'] >= threshold].copy()

# Save predictions for audit
val_df.to_parquet(r'c:\Users\dopa.mine\Desktop\ophelia\research\experiments\exp_014_predictions.parquet')

# Calculate EV and Net return
def calc_economic_value(trade_df, cost_bps, policy='CONSERVATIVE_EXCLUSION'):
    # Iterate trades and apply policy
    cost_frac = cost_bps / 10000.0
    
    tp_frac = CHOSEN_TP / 10000.0
    sl_frac = CHOSEN_SL / 10000.0
    
    net_returns = []
    holding_times = []
    
    for _, row in trade_df.iterrows():
        outcome = row['b_outcome']
        
        # Handling Ambiguous
        if outcome == OUTCOME_AMBIGUOUS:
            if policy == 'CONSERVATIVE_EXCLUSION':
                continue
            elif policy == 'WORST_CASE':
                outcome = OUTCOME_STOP
                
        # Gross Return
        if outcome == OUTCOME_TARGET:
            gross = tp_frac
        elif outcome == OUTCOME_STOP:
            gross = -sl_frac
        else: # TIMEOUT
            # Approximate by taking actual forward return at timeout
            entry_idx = row.name
            exit_offset = int(row['b_exit_offset'])
            if entry_idx + exit_offset < len(df_model):
                gross = (df_model['close'].iloc[entry_idx + exit_offset] / row['close']) - 1.0
            else:
                gross = 0.0
                
        net = gross - cost_frac
        net_returns.append(net)
        holding_times.append(row['b_exit_offset'])
        
    net_returns = np.array(net_returns)
    holding_times = np.array(holding_times)
    
    if len(net_returns) == 0:
        return 0, 0, 0, 0
        
    prob_win = (net_returns > 0).mean()
    expected_net = net_returns.mean()
    gross_net = net_returns.mean() + cost_frac
    
    return expected_net, gross_net, prob_win, holding_times.mean()

print("\nCost Sensitivity (Policy: WORST_CASE):")
costs = [6, 8, 10, 12, 15, 20]
for c in costs:
    ev_net, ev_gross, p_win, h_time = calc_economic_value(trades, c, policy='WORST_CASE')
    print(f"Cost: {c} bps | Net EV: {ev_net*10000:.2f} bps | Gross EV: {ev_gross*10000:.2f} bps | P(Net>0): {p_win:.4f} | Avg Hold: {h_time:.1f}m")

print("\nCost Sensitivity (Policy: CONSERVATIVE_EXCLUSION):")
for c in costs:
    ev_net, ev_gross, p_win, h_time = calc_economic_value(trades, c, policy='CONSERVATIVE_EXCLUSION')
    print(f"Cost: {c} bps | Net EV: {ev_net*10000:.2f} bps | Gross EV: {ev_gross*10000:.2f} bps | P(Net>0): {p_win:.4f} | Avg Hold: {h_time:.1f}m")

print("\nExperiment 014 Complete.")
