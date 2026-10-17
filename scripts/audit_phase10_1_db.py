import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from control_plane import db

con = db._connect()
cur = con.cursor()

print("============================================================")
print("PHASE 10.1 SQLITE DATABASE AUDIT")
print("============================================================")
fc_count = cur.execute("SELECT COUNT(*) FROM candidate_forecasts").fetchone()[0]
out_count = cur.execute("SELECT COUNT(*) FROM candidate_research_outcomes").fetchone()[0]
print(f"Total Candidate Forecasts: {fc_count}")
print(f"Total Candidate Outcomes: {out_count}")

print("\n--- Outcome Counts by Lifecycle State ---")
for r in cur.execute("SELECT retest_state_at_entry, COUNT(*) FROM candidate_research_outcomes GROUP BY retest_state_at_entry").fetchall():
    print(f"  State {r[0]}: {r[1]} candidates")

print("\n--- ENTRY_READY Candidates by Compatibility Cohort ---")
for r in cur.execute("""
    SELECT trade_compatibility, COUNT(*), SUM(tp1_hit), SUM(sl_hit), ROUND(SUM(normalized_realized_r), 2), ROUND(AVG(normalized_realized_r), 2)
    FROM candidate_research_outcomes
    WHERE retest_state_at_entry='ENTRY_READY'
    GROUP BY trade_compatibility
""").fetchall():
    print(f"  Cohort {r[0]}: Count={r[1]}, Wins={r[2]}, Losses={r[3]}, Net R={r[4]}, Expectancy R={r[5]}")

print("\n--- BREAKOUT_SCREENING Legacy Candidates ---")
for r in cur.execute("""
    SELECT trade_compatibility, COUNT(*), SUM(tp1_hit), SUM(sl_hit), ROUND(SUM(normalized_realized_r), 2)
    FROM candidate_research_outcomes
    WHERE retest_state_at_entry='BREAKOUT_SCREENING'
    GROUP BY trade_compatibility
""").fetchall():
    print(f"  Legacy Cohort {r[0]}: Count={r[1]}, Wins={r[2]}, Losses={r[3]}, Net R={r[4]}")

print("============================================================")
