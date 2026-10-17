import json
import pandas as pd

with open('research/results/PHASE5_2_POSITIONING_ABLATION.json', 'r') as f:
    data = json.load(f)

symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT', 'ADAUSDT']
models = data['models']

print("===== AVG BRIER ISO =====")
for sym in symbols:
    print(f"\n{sym}:")
    res = data['results'][sym]
    for model in models:
        brier = res[model]['avg_brier_iso']
        gross = res[model]['avg_high_prob_gross_bps']
        print(f"  {model:20s}: Brier = {brier:.5f}, Gross(bps) = {gross:6.2f}")

