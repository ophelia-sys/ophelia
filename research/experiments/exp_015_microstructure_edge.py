import os
import sys
sys.path.insert(0, r'c:\Users\dopa.mine\Desktop\ophelia')

import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from research.pipeline.data_loader import ResearchDataLoader
from research.pipeline.features import FeatureGenerator
from research.pipeline.labels import LabelGenerator, OUTCOME_TARGET, OUTCOME_STOP, OUTCOME_TIMEOUT, OUTCOME_AMBIGUOUS
import os

# Create experiment report directory
os.makedirs(r'c:\Users\dopa.mine\Desktop\ophelia\research\experiments', exist_ok=True)

# 1. Load Data
loader = ResearchDataLoader()
df = loader.load_symbol('BTCUSDT')

# 2. Add Features
print("Generating features...")
base_families = ['baseline', 'volatility', 'trend', 'momentum', 'volume']
all_families = base_families + ['microstructure']

df = FeatureGenerator.generate_features(df, all_families)
base_cols = FeatureGenerator.get_feature_columns(base_families)
all_cols = FeatureGenerator.get_feature_columns(all_families)

df = df.dropna(subset=all_cols)
df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

# Pick best barrier from Exp 014 (placeholder: +20 / -15 with 60m timeout)
CHOSEN_TP = 20
CHOSEN_SL = 15
CHOSEN_TO = 60

print(f"\nGenerating labels for {CHOSEN_TP}/{CHOSEN_SL} at {CHOSEN_TO}m...")
df_model = LabelGenerator.generate_barrier_labels(df, target_bps=CHOSEN_TP, stop_bps=CHOSEN_SL, timeout_candles=CHOSEN_TO, is_long=True, prefix="b")

# y_target = 1 if TARGET_HIT, else 0
df_model['y_target'] = (df_model['b_outcome'] == OUTCOME_TARGET).astype(int)

# Split sets
dev_mask = df_model['datetime'] < '2023-04-01'
val_mask = (df_model['datetime'] >= '2023-04-01') & (df_model['datetime'] < '2023-07-01')

print(f"Dev rows: {dev_mask.sum()}, Val rows: {val_mask.sum()}")

def train_and_eval(features, name):
    X_train, y_train = df_model.loc[dev_mask, features], df_model.loc[dev_mask, 'y_target']
    X_val, y_val = df_model.loc[val_mask, features], df_model.loc[val_mask, 'y_target']
    
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
    
    val_df = df_model.loc[val_mask].copy()
    val_df['pred'] = model.predict(X_val)
    
    safe_name = name.replace(" ", "_").replace("+", "plus").lower()
    val_df.to_parquet(rf'c:\Users\dopa.mine\Desktop\ophelia\research\experiments\exp_015_predictions_{safe_name}.parquet')
    
    # Calculate economics for cost = 12 bps (default assumption)
    threshold = val_df['pred'].quantile(0.90)
    trades = val_df[val_df['pred'] >= threshold]
    
    cost_frac = 12.0 / 10000.0
    tp_frac = CHOSEN_TP / 10000.0
    sl_frac = CHOSEN_SL / 10000.0
    
    net_returns = []
    
    for _, row in trades.iterrows():
        outcome = row['b_outcome']
        
        # Policy: WORST_CASE
        if outcome == OUTCOME_AMBIGUOUS:
            outcome = OUTCOME_STOP
            
        if outcome == OUTCOME_TARGET:
            gross = tp_frac
        elif outcome == OUTCOME_STOP:
            gross = -sl_frac
        else: # TIMEOUT
            entry_idx = row.name
            exit_offset = int(row['b_exit_offset'])
            if entry_idx + exit_offset < len(df_model):
                gross = (df_model['close'].iloc[entry_idx + exit_offset] / row['close']) - 1.0
            else:
                gross = 0.0
                
        net = gross - cost_frac
        net_returns.append(net)
        
    net_returns = np.array(net_returns)
    ev_net = net_returns.mean() * 10000.0 if len(net_returns) > 0 else 0.0
    
    print(f"\n--- Model: {name} ---")
    print(f"Features: {features}")
    print(f"Validation AUC: {model.best_score['valid_1']['auc']:.4f}")
    print(f"Trades taken: {len(trades)}")
    print(f"Net Expected Value (12 bps cost): {ev_net:.2f} bps")
    
    return ev_net, model.best_score['valid_1']['auc']

print("\nRunning Ablation...")
train_and_eval(base_cols, "BASELINE EVENT MODEL")

for feat in ['taker_buy_ratio', 'ofi_proxy_z', 'delta_oi_z']:
    if feat in all_cols:
        train_and_eval(base_cols + [feat], f"BASELINE + {feat}")
        
train_and_eval(all_cols, "BASELINE + ALL MICROSTRUCTURE")
