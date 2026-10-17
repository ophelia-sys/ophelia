import json

with open('research/results/PHASE5_2_1_LSR_VALIDATION_MANIFEST.json', 'r') as f:
    data = json.load(f)

symbols = data['symbols']

for sym in symbols:
    print(f"\n{'='*50}\n{sym}\n{'='*50}")
    sym_data = data['results'][sym]
    
    # 1. Feature Isolation (Config 1440)
    cfg = sym_data['configs']['1440']
    
    brier_base = sum([f['brier'] for f in cfg['BASE']['folds']]) / 3
    brier_lsr1 = sum([f['brier'] for f in cfg['LSR1']['folds']]) / 3
    brier_lsr2 = sum([f['brier'] for f in cfg['LSR2']['folds']]) / 3
    brier_lsr3 = sum([f['brier'] for f in cfg['LSR3']['folds']]) / 3
    
    print("1. FEATURE ISOLATION (Avg Brier)")
    print(f"   BASE: {brier_base:.6f}")
    print(f"   LSR1: {brier_lsr1:.6f} (diff: {brier_lsr1 - brier_base:.6f})")
    print(f"   LSR2: {brier_lsr2:.6f} (diff: {brier_lsr2 - brier_base:.6f})")
    print(f"   LSR3: {brier_lsr3:.6f} (diff: {brier_lsr3 - brier_base:.6f})")
    
    # 2. Statistical Tests (DM and Permutation)
    dm_stat = cfg['LSR3'].get('dm_stat', 0)
    dm_p = cfg['LSR3'].get('dm_p_value', 1.0)
    
    perm_p_values = [f.get('perm_p_value', 1.0) for f in cfg['LSR3']['folds']]
    
    print("\n2. STATISTICAL TESTS")
    print(f"   DM Stat: {dm_stat:.3f}, p-val: {dm_p:.4f}")
    print(f"   Permutation p-vals (Folds 1,2,3): {perm_p_values}")
    
    # 3. Bootstrap CIs
    ci_brier = cfg['LSR3'].get('ci_95_delta_brier', [0, 0])
    ci_gross = cfg['LSR3'].get('ci_95_delta_gross_bps', [0, 0])
    
    print("\n3. BLOCK BOOTSTRAP 95% CIs")
    print(f"   ΔBrier: [{ci_brier[0]:.6f}, {ci_brier[1]:.6f}]")
    print(f"   ΔGross: [{ci_gross[0]:.2f}, {ci_gross[1]:.2f}]")
    
    # 4. Fold Stability & Year Stability
    print("\n4. STABILITY")
    for i in range(3):
        base_f = cfg['BASE']['folds'][i]['brier']
        lsr3_f = cfg['LSR3']['folds'][i]['brier']
        print(f"   Fold {i+1}: BASE={base_f:.5f}, LSR3={lsr3_f:.5f} (Δ={lsr3_f - base_f:.5f})")
        
    for yr in ['2022', '2023']:
        b_yr = sum([f['years'].get(yr, {}).get('brier', 0) for f in cfg['BASE']['folds']])
        l_yr = sum([f['years'].get(yr, {}).get('brier', 0) for f in cfg['LSR3']['folds']])
        # Count folds where year is present
        b_cnt = sum([1 for f in cfg['BASE']['folds'] if yr in f['years']])
        if b_cnt > 0:
            b_yr /= b_cnt
            l_yr /= b_cnt
            print(f"   Year {yr}: BASE={b_yr:.5f}, LSR3={l_yr:.5f} (Δ={l_yr - b_yr:.5f})")
            
    # 5. Economic Ranking
    print("\n5. ECONOMIC RANKING (Top 20% Net Return at 12bps)")
    base_eco = [f['economics']['top20']['net_bps_cost_12'] for f in cfg['BASE']['folds']]
    lsr3_eco = [f['economics']['top20']['net_bps_cost_12'] for f in cfg['LSR3']['folds']]
    print(f"   BASE Avg Net: {sum(base_eco)/3:.2f} bps")
    print(f"   LSR3 Avg Net: {sum(lsr3_eco)/3:.2f} bps")
    
    # 6. Forward-Fill Sensitivity
    print("\n6. FORWARD-FILL SENSITIVITY (LSR3 Brier)")
    for stale in ['1440', '60', '0']:
        if stale in sym_data['configs']:
            b_s = sum([f['brier'] for f in sym_data['configs'][stale]['LSR3']['folds']]) / 3
            print(f"   {stale}m: {b_s:.6f}")
