import json

with open('depth_samples.json', 'r') as f:
    msgs = json.load(f)

depth_msgs = [m for m in msgs if m.get('dataType') == 'BTC-USDT@depth20']
print('Total depth messages:', len(depth_msgs))

for i, m in enumerate(depth_msgs):
    data = m['data']
    asks = data.get('asks', [])
    bids = data.get('bids', [])
    zero_qty_asks = [a for a in asks if float(a[1]) == 0]
    zero_qty_bids = [b for b in bids if float(b[1]) == 0]
    last_update_id = data.get("lastUpdateId")
    
    print(f"Msg {i}: asks={len(asks)}, bids={len(bids)}, zero_asks={len(zero_qty_asks)}, zero_bids={len(zero_qty_bids)}, lastUpdateId={last_update_id}")
