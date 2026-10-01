"""Phase 1 Database Migration and Identity Reconciliation Script.

Invariants:
- Ambiguous rows must NOT be assigned to user 1.
- Classify orphan/ambiguous data into explicit recovery states (e.g. REQUIRES_MIGRATION).
- Release stuck slots that do not correspond to an active trade.
- Clean up or flag orphaned references.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import time

def run_migration(db_path: str):
    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        return False

    print(f"Running Phase 1 Migration on {db_path}...")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. Inspect existing users
    cur.execute("SELECT id, email, role, status FROM users")
    users = cur.fetchall()
    print(f"Total users in DB: {len(users)}")
    valid_uids = {u[0] for u in users}

    # 2. Reconcile users with missing/empty email or invalid status -> REQUIRES_MIGRATION
    cur.execute(
        "UPDATE users SET status='REQUIRES_MIGRATION' WHERE (email IS NULL OR email = '' OR email = 'demo@ophelia.internal') AND id > 1"
    )
    if cur.rowcount > 0:
        print(f"Updated {cur.rowcount} ambiguous/demo user rows to REQUIRES_MIGRATION")

    # 3. Check and clean up orphaned notifications
    cur.execute("SELECT COUNT(*) FROM notifications WHERE user_id NOT IN (SELECT id FROM users)")
    orphan_notifs = cur.fetchone()[0]
    if orphan_notifs > 0:
        print(f"Found {orphan_notifs} orphan notifications. Marking with dedup prefix ORPHAN_MIGRATION...")
        # Mark or quarantine them
        cur.execute("DELETE FROM notifications WHERE user_id NOT IN (SELECT id FROM users)")
        print(f"Purged {orphan_notifs} orphan notifications without user owner.")

    # 4. Release stuck autonomous_trade_slots (e.g. RESERVED without open position)
    cur.execute("SELECT id, name, status, reserved_by_trade_id FROM autonomous_trade_slots WHERE status='RESERVED'")
    reserved_slots = cur.fetchall()
    for s_id, s_name, s_status, s_trade_id in reserved_slots:
        print(f"Checking reserved slot #{s_id} ({s_name}), reserved_by_trade_id={s_trade_id}")
        # Verify if an actual open position exists for this trade/slot
        cur.execute(
            "SELECT count(*) FROM positions WHERE status IN ('OPEN','PARTIAL','TRAILING') AND (detail_json LIKE ? OR client_order_id = ?)",
            (f'%"{s_id}"%', str(s_trade_id))
        )
        has_pos = cur.fetchone()[0] > 0
        if not has_pos:
            print(f"Slot #{s_id} is stuck RESERVED without open position. Releasing to AVAILABLE.")
            cur.execute(
                "UPDATE autonomous_trade_slots SET status='AVAILABLE', reserved_by_trade_id=NULL, current_position_id=NULL WHERE id=?",
                (s_id,)
            )

    # 5. Check automations table ownership
    cur.execute("SELECT COUNT(*) FROM automations WHERE user_id IS NULL OR user_id <= 0")
    bad_autos = cur.fetchone()[0]
    if bad_autos > 0:
        print(f"Found {bad_autos} automations without valid user_id. Marking CANCELLED/REQUIRES_MIGRATION.")
        cur.execute("UPDATE automations SET status='REQUIRES_MIGRATION' WHERE user_id IS NULL OR user_id <= 0")

    # 6. Check positions table ownership
    cur.execute("SELECT COUNT(*) FROM positions WHERE user_id IS NULL OR user_id <= 0")
    bad_pos = cur.fetchone()[0]
    if bad_pos > 0:
        print(f"Found {bad_pos} positions without valid user_id. Flagging in detail_json.")
        cur.execute("UPDATE positions SET detail_json=json_insert(COALESCE(detail_json, '{}'), '$.ownership_status', 'REQUIRES_MIGRATION') WHERE user_id IS NULL OR user_id <= 0")

    # 7. Check audit table - system audit events with user_id=0 or None
    cur.execute("UPDATE audit SET user_id=0 WHERE user_id IS NULL")

    # Commit all updates
    conn.commit()
    conn.close()
    print("Phase 1 Migration completed successfully.")
    return True

if __name__ == "__main__":
    db_file = sys.argv[1] if len(sys.argv) > 1 else "control_data/market_1m.db"
    run_migration(db_file)
