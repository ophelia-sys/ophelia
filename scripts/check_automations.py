import sqlite3
import time

conn = sqlite3.connect('/opt/ophelia/control_data/market_1m.db')
rows = conn.execute(
    'SELECT id, user_id, status, last_evaluated_ms, last_eval_reason, last_execution_status FROM automations WHERE id IN (45, 46)'
).fetchall()
print("AUTOMATIONS 45, 46:")
now_ms = int(time.time() * 1000)
for r in rows:
    last_eval = r[3]
    age_s = (now_ms - last_eval) / 1000.0 if last_eval else None
    print(f"ID={r[0]}, user_id={r[1]}, status={r[2]}, last_evaluated_ms={r[3]} (age: {age_s:.1f}s ago if evaluated), reason={r[4]}, exec_status={r[5]}")

print("\nSLOT 128 STATUS:")
slot = conn.execute("SELECT id, name, status, user_id, current_trade_id FROM autonomous_trade_slots WHERE id=128").fetchone()
print(f"Slot 128: {slot}")

print("\nUSER 205 STATUS:")
u = conn.execute("SELECT id, email, role, status FROM users WHERE id=205").fetchone()
print(f"User 205: {u}")
