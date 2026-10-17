import sqlite3
import json

conn = sqlite3.connect('/opt/ophelia/control_data/market_1m.db')
print("=== RECENT ML ANALYSES ===")
for r in conn.execute("SELECT analysis_id, symbol, model, confidence_pct, thesis, latency_ms, error_status FROM ml_analyses ORDER BY timestamp_ms DESC LIMIT 8").fetchall():
    print(f"[{r[1]}] Model: {r[2]} | Conf: {r[3]}% | Latency: {r[5]}ms | Error: {r[6]}\n  Thesis: {r[4]}")

print("\n=== RECENT SETUP CANDIDATES ===")
for r in conn.execute("SELECT setup_id, symbol, direction, timeframe, state, vwap, entry, stop_loss, target_1, target_2 FROM setup_candidates ORDER BY id DESC LIMIT 5").fetchall():
    print(f"[{r[1]}] {r[2]} {r[3]}m - State: {r[4]} | Entry: {r[6]} | SL: {r[7]} | TP1: {r[8]} | TP2: {r[9]}")

print("\n=== NEWS BY CATEGORY ===")
for cat, count in conn.execute("SELECT category, COUNT(*) FROM news_articles GROUP BY category").fetchall():
    print(f"  {cat}: {count}")

print("\n=== CAPACITY & TRADE CAP METRICS ===")
for k, v in conn.execute("SELECT key, value FROM meta WHERE key LIKE '%trade%' OR key LIKE '%cap%' OR key='mode'").fetchall():
    print(f"  {k}: {v}")
