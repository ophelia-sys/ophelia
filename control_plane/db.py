"""Rolling 1-minute market database (SQLite) with strict 24h application-level TTL."""
from __future__ import annotations

import json
_j = json
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone

from . import config

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None


def _connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        os.makedirs(config.DATA_DIR, exist_ok=True)
        _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        _conn.execute("PRAGMA journal_mode=WAL")
        
        # Core tables
        _conn.execute("""CREATE TABLE IF NOT EXISTS candles(
            exchange TEXT NOT NULL, symbol TEXT NOT NULL, ts INTEGER NOT NULL,
            open REAL, high REAL, low REAL, close REAL, volume REAL,
            taker_buy REAL, trades INTEGER, PRIMARY KEY(exchange, symbol, ts))""")
        _conn.execute("CREATE INDEX IF NOT EXISTS ix_candles_ts ON candles(ts)")
        _conn.execute("""CREATE TABLE IF NOT EXISTS meta(
            key TEXT PRIMARY KEY, value TEXT)""")
        
        # User management
        _conn.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE,
            password_hash TEXT, created_ms INTEGER, bingx_api_key_enc TEXT,
            bingx_secret_enc TEXT)""")
            
        _conn.execute("""CREATE TABLE IF NOT EXISTS exchange_accounts(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            exchange TEXT, name TEXT, api_key TEXT, api_secret_enc TEXT,
            created_ms INTEGER)""")
        
        _init_user_and_copy_tables(_conn)
        _init_us_market_and_slot_tables(_conn)
        _conn.commit()
    return _conn


def _init_user_and_copy_tables(conn: sqlite3.Connection) -> None:
    # 1. users table migrations
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    cols_to_add = [
        ("user_uid", "TEXT"),
        ("role", "TEXT DEFAULT 'USER'"),
        ("google_subject", "TEXT"),
        ("display_name", "TEXT"),
        ("status", "TEXT DEFAULT 'PENDING'"),
        ("copy_enabled", "INTEGER DEFAULT 1"),
        ("admin_copy_allowed", "INTEGER DEFAULT 1"),
        ("suspended", "INTEGER DEFAULT 0"),
        ("bingx_connection_status", "TEXT DEFAULT 'DISCONNECTED'"),
        ("bingx_account_identifier", "TEXT"),
        ("created_at", "INTEGER"),
        ("last_login", "INTEGER"),
        ("last_heartbeat", "INTEGER"),
        ("last_bingx_sync", "INTEGER"),
        ("app_version", "TEXT"),
        ("last_execution_status", "TEXT"),
        ("last_error", "TEXT"),
    ]
    for col_name, col_type in cols_to_add:
        if col_name not in existing_cols:
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError:
                pass

    # Ensure admin user (id=1, ophelia-sys) exists securely
    try:
        import bcrypt
        env_admin_pwd = os.getenv("OPHELIA_ADMIN_PASSWORD")
        if env_admin_pwd:
            admin_pwd_hash = bcrypt.hashpw(env_admin_pwd.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        else:
            admin_pwd_hash = "$2b$12$e0c0P9eZ1mO/Esm6N4uP4O47lJ0ZgG1NnIeNZZH0B6hI.W6wI2u5m"
    except Exception:
        admin_pwd_hash = "$2b$12$e0c0P9eZ1mO/Esm6N4uP4O47lJ0ZgG1NnIeNZZH0B6hI.W6wI2u5m"

    admin_row = conn.execute("SELECT id FROM users WHERE id=1").fetchone()
    now_ms = int(time.time() * 1000)
    if not admin_row:
        conn.execute(
            "INSERT OR REPLACE INTO users(id, user_uid, role, email, display_name, password_hash, status, copy_enabled, admin_copy_allowed, created_at) "
            "VALUES(1, 'ophelia-sys', 'ADMIN', 'ophelia-sys', 'Ophelia Admin', ?, 'ACTIVE', 1, 1, ?)",
            (admin_pwd_hash, now_ms)
        )
    else:
        conn.execute(
            "UPDATE users SET role='ADMIN', status='ACTIVE', display_name='Ophelia Admin', "
            "user_uid='ophelia-sys', email='ophelia-sys' WHERE id=1"
        )

    # 2. user_devices
    conn.execute("""CREATE TABLE IF NOT EXISTS user_devices(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        device_id TEXT,
        device_model TEXT,
        fcm_token TEXT,
        app_version TEXT,
        created_ms INTEGER,
        last_seen_ms INTEGER
    )""")

    # 3. user_bingx_credentials
    conn.execute("""CREATE TABLE IF NOT EXISTS user_bingx_credentials(
        user_id INTEGER PRIMARY KEY,
        api_key_enc TEXT NOT NULL,
        api_secret_enc TEXT NOT NULL,
        key_identifier TEXT NOT NULL,
        permissions_json TEXT,
        has_withdrawal INTEGER DEFAULT 0,
        is_valid INTEGER DEFAULT 0,
        last_verified_ms INTEGER,
        last_error TEXT,
        updated_ms INTEGER
    )""")

    # 4. master_trades
    conn.execute("""CREATE TABLE IF NOT EXISTS master_trades(
        master_trade_id TEXT PRIMARY KEY,
        admin_user_id INTEGER NOT NULL DEFAULT 1,
        automation_id INTEGER,
        strategy TEXT NOT NULL,
        symbol TEXT NOT NULL,
        direction TEXT NOT NULL,
        entry_reference_price REAL NOT NULL,
        leverage REAL NOT NULL,
        sl_price REAL NOT NULL,
        tp1_price REAL,
        tp2_price REAL,
        tp3_price REAL,
        tp1_qty_pct REAL DEFAULT 50.0,
        tp2_qty_pct REAL DEFAULT 30.0,
        tp3_qty_pct REAL DEFAULT 20.0,
        trailing INTEGER DEFAULT 0,
        breakeven INTEGER DEFAULT 0,
        allocation_mode TEXT DEFAULT 'PROPORTIONAL_RATIO',
        allocation_value REAL DEFAULT 100.0,
        admin_balance_snapshot REAL NOT NULL,
        admin_equity_snapshot REAL NOT NULL,
        admin_margin_selected REAL NOT NULL,
        ml_snapshot_hash TEXT,
        trigger_ts INTEGER NOT NULL,
        expiration INTEGER,
        status TEXT DEFAULT 'ACTIVE'
    )""")

    # 5. master_trade_events
    conn.execute("""CREATE TABLE IF NOT EXISTS master_trade_events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        master_trade_id TEXT NOT NULL,
        master_event_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        sequence_number INTEGER NOT NULL,
        correlation_id TEXT NOT NULL,
        payload_json TEXT,
        timestamp_ms INTEGER NOT NULL
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_mte_trade ON master_trade_events(master_trade_id, sequence_number)")

    # 6. copy_executions
    conn.execute("""CREATE TABLE IF NOT EXISTS copy_executions(
        copy_execution_id TEXT PRIMARY KEY,
        master_trade_id TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        correlation_id TEXT NOT NULL,
        idempotency_key TEXT UNIQUE NOT NULL,
        status TEXT NOT NULL,
        blocked_reason TEXT,
        allocated_margin REAL,
        calculated_quantity REAL,
        executed_quantity REAL,
        executed_price REAL,
        client_order_id TEXT,
        exchange_order_id TEXT,
        execution_latency_ms INTEGER,
        created_ms INTEGER NOT NULL,
        updated_ms INTEGER NOT NULL
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_ce_master ON copy_executions(master_trade_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_ce_user ON copy_executions(user_id)")

    # 7. execution_events
    conn.execute("""CREATE TABLE IF NOT EXISTS execution_events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        copy_execution_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        latency_ms INTEGER,
        detail_json TEXT,
        timestamp_ms INTEGER NOT NULL
    )""")

    # 8. user_positions
    conn.execute("""CREATE TABLE IF NOT EXISTS user_positions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        symbol TEXT NOT NULL,
        direction TEXT NOT NULL,
        quantity REAL NOT NULL,
        entry_price REAL NOT NULL,
        leverage REAL NOT NULL,
        margin REAL NOT NULL,
        sl_price REAL,
        tp1_price REAL,
        tp2_price REAL,
        tp3_price REAL,
        trailing INTEGER DEFAULT 0,
        breakeven INTEGER DEFAULT 0,
        master_trade_id TEXT,
        copy_execution_id TEXT,
        status TEXT DEFAULT 'OPEN',
        unrealized_pnl REAL DEFAULT 0.0,
        realized_pnl REAL DEFAULT 0.0,
        created_ms INTEGER NOT NULL,
        updated_ms INTEGER NOT NULL
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_up_user ON user_positions(user_id, status)")

    # 9. reconciliation_events
    conn.execute("""CREATE TABLE IF NOT EXISTS reconciliation_events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        symbol TEXT NOT NULL,
        status TEXT NOT NULL,
        exchange_state_json TEXT,
        local_state_json TEXT,
        discrepancy_reason TEXT,
        timestamp_ms INTEGER NOT NULL
    )""")

    # 10. user_automation_allocations
    conn.execute("""CREATE TABLE IF NOT EXISTS user_automation_allocations(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        automation_id INTEGER NOT NULL,
        allocated_amount REAL NOT NULL DEFAULT 0.0,
        enabled INTEGER NOT NULL DEFAULT 1,
        updated_ms INTEGER NOT NULL,
        UNIQUE(user_id, automation_id)
    )""")



def upsert_candles(exchange: str, symbol: str, rows: list[dict]) -> int:
    if not rows:
        return 0
    conn = _connect()
    with _lock:
        conn.executemany(
            "INSERT OR REPLACE INTO candles(exchange,symbol,ts,open,high,low,close,"
            "volume,taker_buy,trades) VALUES(?,?,?,?,?,?,?,?,?,?)",
            [(exchange, symbol, r["ts"], r["open"], r["high"], r["low"],
              r["close"], r.get("volume"), r.get("taker_buy"), r.get("trades"))
             for r in rows])
        conn.commit()
    return len(rows)


def cleanup_expired() -> dict:
    """Delete rows older than retention; returns stats (never raises)."""
    conn = _connect()
    cutoff = int((time.time() * 1000) - config.RETENTION_HOURS * 3600_000)
    try:
        with _lock:
            cur = conn.execute("DELETE FROM candles WHERE ts < ?", (cutoff,))
            conn.execute(
                "INSERT INTO meta(key,value) VALUES('last_cleanup_ms',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(int(time.time() * 1000)),))
            conn.commit()
            deleted = cur.rowcount
        ok = True
        err = None
    except Exception as e:                                        # noqa: BLE001
        deleted, ok, err = 0, False, str(e)[:200]
    return {"deleted": deleted, "ok": ok, "error": err,
            "cutoff_utc": datetime.fromtimestamp(cutoff / 1000, timezone.utc).isoformat()}


def query_candles(symbol: str, start_ms: int, end_ms: int,
                  exchange: str | None = None,
                  enforce_ttl: bool = True) -> list[dict]:
    """Analytical read - optionally enforces application TTL limit."""
    if enforce_ttl:
        now = time.time() * 1000
        floor = now - config.MAX_LOOKBACK_HOURS * 3600_000
        start_ms = max(start_ms, int(floor))
    if start_ms >= end_ms:
        return []
    conn = _connect()
    symbols_to_check = [symbol]
    venue = config.to_venue_symbol(symbol)
    if venue not in symbols_to_check:
        symbols_to_check.append(venue)
    disp = config.to_display_symbol(symbol)
    if disp not in symbols_to_check:
        symbols_to_check.append(disp)

    placeholders = ",".join("?" for _ in symbols_to_check)
    q = (f"SELECT exchange,symbol,ts,open,high,low,close,volume,taker_buy,trades "
         f"FROM candles WHERE symbol IN ({placeholders}) AND ts>=? AND ts<?")
    args = list(symbols_to_check) + [start_ms, end_ms]
    if exchange:
        q += " AND exchange=?"
        args.append(exchange)
    q += " ORDER BY ts"
    with _lock:
        rows = conn.execute(q, args).fetchall()
    keys = ("exchange", "symbol", "ts", "open", "high", "low", "close",
            "volume", "taker_buy", "trades")
    return [dict(zip(keys, r)) for r in rows]


def oldest_newest(symbol: str | None = None) -> dict:
    conn = _connect()
    q = "SELECT MIN(ts),MAX(ts),COUNT(*) FROM candles"
    args: list = []
    if symbol:
        q += " WHERE symbol=?"
        args.append(symbol)
    with _lock:
        lo, hi, n = conn.execute(q, args).fetchone()
    last_clean = conn.execute(
        "SELECT value FROM meta WHERE key='last_cleanup_ms'").fetchone()
    return {"oldest_ts": lo, "newest_ts": hi, "rows": n,
            "last_cleanup_ms": int(last_clean[0]) if last_clean else None}


# ---------------------------------------------------------------- automations

def _auto_conn() -> sqlite3.Connection:
    c = _connect()
    with _lock:
        c.execute("""CREATE TABLE IF NOT EXISTS automations(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER DEFAULT 1,
            account_id INTEGER DEFAULT 1,
            created_ms INTEGER, status TEXT, strategy TEXT, symbol TEXT, timeframe TEXT,
            direction_pref TEXT, margin_usage_pct REAL, leverage REAL,
            margin_usdt REAL, mode TEXT, params_json TEXT, note TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS shadow_trades(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER DEFAULT 1,
            account_id INTEGER DEFAULT 1,
            automation_id INTEGER, ts_open_ms INTEGER, direction TEXT, entry REAL,
            stop REAL, target REAL, qty REAL, status TEXT, ts_close_ms INTEGER,
            exit_price REAL, pnl_usdt REAL, detail_json TEXT)""")
        
        c.execute("""CREATE TABLE IF NOT EXISTS retest_states(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframe INTEGER NOT NULL,
            direction TEXT NOT NULL,
            state TEXT NOT NULL,
            breakout_ts INTEGER,
            breakout_price REAL,
            vwap_at_breakout REAL,
            zone_low REAL,
            zone_high REAL,
            fvg_id TEXT,
            elapsed_candles INTEGER DEFAULT 0,
            touch_ts INTEGER,
            rejection_ts INTEGER,
            confirmation_ts INTEGER,
            invalidation_ts INTEGER,
            updated_ms INTEGER)""")

        c.execute("""CREATE TABLE IF NOT EXISTS setup_candidates(
            setup_id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            timeframe INTEGER NOT NULL,
            strategy TEXT NOT NULL,
            current_state TEXT NOT NULL,
            reason TEXT,
            vwap REAL,
            breakout_price REAL,
            retest_state TEXT,
            cvd_confirmed INTEGER DEFAULT 0,
            rvol_confirmed INTEGER DEFAULT 0,
            fvg_confirmed INTEGER DEFAULT 0,
            entry_conditions_json TEXT,
            confirmation_conditions_json TEXT,
            invalidation_json TEXT,
            suggested_sl REAL,
            suggested_tp1 REAL,
            suggested_tp2 REAL,
            risk_reward REAL,
            confidence_pct REAL,
            thesis TEXT,
            generated_ms INTEGER,
            expires_ms INTEGER,
            status TEXT DEFAULT 'ACTIVE')""")

        c.execute("""CREATE TABLE IF NOT EXISTS ml_analyses(
            analysis_id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            analysis_type TEXT NOT NULL,
            model TEXT NOT NULL,
            model_version TEXT,
            timestamp_ms INTEGER NOT NULL,
            data_cutoff_ms INTEGER,
            thesis TEXT,
            opportunities_json TEXT,
            risks_json TEXT,
            confidence_pct REAL,
            latency_ms INTEGER,
            error_status TEXT)""")

        c.execute("""CREATE TABLE IF NOT EXISTS news_articles(
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            timestamp_ms INTEGER NOT NULL,
            title TEXT NOT NULL,
            url TEXT,
            category TEXT,
            relevance REAL,
            sentiment TEXT,
            importance TEXT,
            dedupe_key TEXT UNIQUE,
            market_reaction_json TEXT,
            model TEXT,
            analysis_ts_ms INTEGER)""")

        # Migrations for existing tables
        try:
            c.execute("ALTER TABLE automations ADD COLUMN user_id INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE automations ADD COLUMN account_id INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE automations ADD COLUMN last_evaluated_ms INTEGER")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE automations ADD COLUMN last_eval_reason TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE automations ADD COLUMN last_signal_ms INTEGER")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE automations ADD COLUMN last_signal_direction TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE automations ADD COLUMN last_execution_status TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE automations ADD COLUMN direction TEXT")
        except sqlite3.OperationalError:
            pass
        # Auto-migrate NULL direction_pref from params_json (preserves existing setups)
        try:
            c.execute("""UPDATE automations 
                         SET direction_pref = COALESCE(
                             json_extract(params_json, '$.direction_pref'),
                             json_extract(params_json, '$.direction'),
                             json_extract(params_json, '$.direction_preference'),
                             'LONG'
                         )
                         WHERE direction_pref IS NULL""")
            c.execute("""UPDATE automations 
                         SET direction = direction_pref 
                         WHERE direction IS NULL""")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE shadow_trades ADD COLUMN user_id INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE shadow_trades ADD COLUMN account_id INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass
        # Migrations for setup_candidates (Phase 4 Lifecycle & Retest Intelligence)
        for col_name, col_type in [
            ("waiting_for", "TEXT"),
            ("next_required_event", "TEXT"),
            ("distance_pct", "REAL"),
            ("distance_atr", "REAL"),
            ("priority", "TEXT"),
            ("priority_reasons_json", "TEXT"),
            ("conditions_json", "TEXT"),
            ("data_freshness_json", "TEXT"),
            ("actionability_score", "REAL DEFAULT 0.0"),
            ("zone_json", "TEXT"),
            ("structural_invalidation", "TEXT"),
            ("user_id", "INTEGER DEFAULT 1"),
            ("account_id", "INTEGER DEFAULT 1"),
            ("automation_id", "INTEGER DEFAULT NULL"),
        ]:
            try:
                c.execute(f"ALTER TABLE setup_candidates ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError:
                pass
        c.commit()
    return c


def create_automation(spec: dict, user_id: int, account_id: int = 1) -> int:
    c = _auto_conn()
    canonical_dir = (
        spec.get("direction")
        or spec.get("direction_pref")
        or spec.get("direction_preference")
        or "LONG"
    ).upper()
    effective_uid = spec.get("user_id") or user_id
    if not effective_uid or effective_uid <= 0:
        raise ValueError("Valid user_id required to create automation")
    with _lock:
        cur = c.execute(
            "INSERT INTO automations(user_id,account_id,created_ms,status,strategy,symbol,timeframe,"
            "direction_pref,direction,margin_usage_pct,leverage,margin_usdt,mode,params_json,note)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (effective_uid, account_id, int(time.time() * 1000), spec.get("status", "ACTIVE"),
             spec["strategy"], spec["symbol"], spec.get("timeframe") or spec.get("timeframe_min"),
             canonical_dir, canonical_dir, spec.get("margin_usage_pct"),
             spec.get("leverage"), spec.get("margin_usdt"), spec.get("mode", "SHADOW"),
             json_dumps(spec), spec.get("note")))
        c.commit()
        return int(cur.lastrowid or 0)


def json_dumps(o):
    import json as _j
    return _j.dumps(o)


def update_automation_diagnostics(
    aid: int,
    last_eval_ms: int,
    reason: str,
    signal_ms: int | None = None,
    signal_dir: str | None = None,
    exec_status: str | None = None
) -> None:
    c = _auto_conn()
    with _lock:
        if signal_ms is not None and signal_dir is not None:
            c.execute(
                "UPDATE automations SET last_evaluated_ms=?, last_eval_reason=?, "
                "last_signal_ms=?, last_signal_direction=?, last_execution_status=? "
                "WHERE id=?",
                (last_eval_ms, reason, signal_ms, signal_dir, exec_status, aid)
            )
        else:
            c.execute(
                "UPDATE automations SET last_evaluated_ms=?, last_eval_reason=?, "
                "last_execution_status=COALESCE(?, last_execution_status) "
                "WHERE id=?",
                (last_eval_ms, reason, exec_status, aid)
            )
        c.commit()


def list_automations(status: str | None = None, user_id: int | None = None) -> list[dict]:
    c = _auto_conn()
    q = ("SELECT id,user_id,account_id,created_ms,status,strategy,symbol,timeframe,direction_pref,"
         "margin_usage_pct,leverage,margin_usdt,mode,params_json,"
         "last_evaluated_ms,last_eval_reason,last_signal_ms,last_signal_direction,last_execution_status "
         "FROM automations")
    clauses: list = []
    args: list = []
    if user_id is not None:
        clauses.append("user_id=?")
        args.append(user_id)
    if status:
        clauses.append("status=?")
        args.append(status)
    else:
        clauses.append("status NOT IN ('CANCELLED', 'DELETED', 'ARCHIVED')")
    if clauses:
        q += " WHERE " + " AND ".join(clauses)
    q += " ORDER BY id DESC LIMIT 50"
    with _lock:
        rows = c.execute(q, args).fetchall()
    keys = ("id", "user_id", "account_id", "created_ms", "status", "strategy", "symbol", "timeframe",
            "direction_pref", "margin_usage_pct", "leverage", "margin_usdt",
            "mode", "params_json",
            "last_evaluated_ms", "last_eval_reason", "last_signal_ms", "last_signal_direction", "last_execution_status")
    out = []
    for r in rows:
        d = dict(zip(keys, r))
        try:
            d["params"] = json.loads(d.get("params_json") or "{}")
        except Exception:
            d["params"] = {}

            
        p = d["params"]
        raw_sym = d.get("symbol")
        syms = p.get("symbols")
        if not syms and raw_sym and raw_sym not in ("ALL_WATCHLIST", "MULTIPLE"):
            syms = [raw_sym]
        d["symbols"] = syms
        
        scope = "ALL_WATCHLIST" if raw_sym == "ALL_WATCHLIST" else ("MULTIPLE" if syms and len(syms) > 1 else "SINGLE")
        d["symbol_scope"] = scope
        d["direction"] = d.get("direction_pref") or p.get("direction_preference") or p.get("direction") or "ANY"
        d["vwap_gate_enabled"] = bool(p.get("vwap_gate_enabled", True))
        d["lifecycle"] = p.get("lifecycle") or "CONTINUOUS"
        d["margin_pct"] = d.get("margin_usage_pct") or p.get("margin_usage_pct") or p.get("margin_pct")
        d["fixed_margin"] = d.get("margin_usdt") or p.get("margin_usdt") or p.get("fixed_margin")
        d["strategy_risk"] = p.get("strategy_risk") or p
        d["name"] = p.get("name") or f"{d['strategy']} ({d.get('timeframe', '5m')})"
        out.append(d)
    return out


def get_automation(aid: int, user_id: int | None = None) -> dict | None:
    c = _auto_conn()
    q = ("SELECT id,user_id,account_id,created_ms,status,strategy,symbol,timeframe,direction_pref,"
         "margin_usage_pct,leverage,margin_usdt,mode,params_json,"
         "last_evaluated_ms,last_eval_reason,last_signal_ms,last_signal_direction,last_execution_status "
         "FROM automations WHERE id=?")
    args = [aid]
    if user_id is not None:
        q += " AND user_id=?"
        args.append(user_id)
    with _lock:
        row = c.execute(q, args).fetchone()
    if not row:
        return None
    keys = ("id", "user_id", "account_id", "created_ms", "status", "strategy", "symbol", "timeframe",
            "direction_pref", "margin_usage_pct", "leverage", "margin_usdt",
            "mode", "params_json",
            "last_evaluated_ms", "last_eval_reason", "last_signal_ms", "last_signal_direction", "last_execution_status")
    d = dict(zip(keys, row))
    try:
        d["params"] = json.loads(d.get("params_json") or "{}")
    except Exception:
        d["params"] = {}
    return d


def set_automation_status(aid: int, status: str, user_id: int | None = None) -> bool:
    c = _auto_conn()
    with _lock:
        if user_id is not None:
            cur = c.execute("UPDATE automations SET status=? WHERE id=? AND user_id=?", (status, aid, user_id))
        else:
            cur = c.execute("UPDATE automations SET status=? WHERE id=?", (status, aid))
        c.commit()
    return cur.rowcount > 0


def delete_automation(aid: int, user_id: int | None = None) -> bool:
    c = _auto_conn()
    with _lock:
        if user_id is not None:
            cur = c.execute("DELETE FROM automations WHERE id=? AND user_id=?", (aid, user_id))
        else:
            cur = c.execute("DELETE FROM automations WHERE id=?", (aid,))
        c.commit()
    return cur.rowcount > 0


def update_automation(aid: int, spec: dict, user_id: int | None = None) -> bool:
    c = _auto_conn()
    with _lock:
        updates = []
        params = []
        if "status" in spec:
            updates.append("status=?")
            params.append(spec["status"])
        if "strategy" in spec:
            updates.append("strategy=?")
            params.append(spec["strategy"])
        if "symbol" in spec:
            updates.append("symbol=?")
            params.append(spec["symbol"])
        if "timeframe" in spec:
            updates.append("timeframe=?")
            params.append(str(spec["timeframe"]))
        if "margin_usage_pct" in spec:
            updates.append("margin_usage_pct=?")
            params.append(float(spec["margin_usage_pct"]))
        if "leverage" in spec:
            updates.append("leverage=?")
            params.append(float(spec["leverage"]))
        if "direction_pref" in spec or "direction" in spec:
            updates.append("direction_pref=?")
            params.append(spec.get("direction_pref") or spec.get("direction"))
        if "params" in spec or "strategy_risk" in spec:
            updates.append("params_json=?")
            params.append(json_dumps(spec.get("params") or spec.get("strategy_risk")))
        if not updates:
            return False
        params.append(aid)
        sql = f"UPDATE automations SET {', '.join(updates)} WHERE id=?"
        if user_id is not None:
            sql += " AND user_id=?"
            params.append(user_id)
        cur = c.execute(sql, params)
        c.commit()
    return cur.rowcount > 0


def get_user_automation_allocations(user_id: int) -> list[dict]:
    c = _auto_conn()
    with _lock:
        rows = c.execute(
            "SELECT automation_id, allocated_amount, enabled, updated_ms "
            "FROM user_automation_allocations WHERE user_id=?", (user_id,)
        ).fetchall()
    return [{"automation_id": r[0], "allocated_amount": float(r[1]), "enabled": bool(r[2]), "updated_ms": r[3]} for r in rows]


def set_user_automation_allocation(user_id: int, automation_id: int, allocated_amount: float, enabled: bool = True) -> bool:
    if allocated_amount < 0:
        raise ValueError("Allocated amount cannot be negative")
    c = _auto_conn()
    now_ms = int(time.time() * 1000)
    with _lock:
        c.execute(
            "INSERT INTO user_automation_allocations(user_id, automation_id, allocated_amount, enabled, updated_ms) "
            "VALUES(?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id, automation_id) DO UPDATE SET allocated_amount=excluded.allocated_amount, "
            "enabled=excluded.enabled, updated_ms=excluded.updated_ms",
            (user_id, automation_id, float(allocated_amount), 1 if enabled else 0, now_ms)
        )
        c.commit()
    return True



def record_shadow_trade(row: dict, user_id: int | None = None, account_id: int = 1) -> int:
    effective_uid = row.get("user_id") or user_id
    if not effective_uid or effective_uid <= 0:
        raise ValueError("Valid user_id required to record shadow trade")
    c = _auto_conn()
    with _lock:
        cur = c.execute(
            "INSERT INTO shadow_trades(user_id,account_id,automation_id,ts_open_ms,direction,entry,stop,"
            "target,qty,status,ts_close_ms,exit_price,pnl_usdt,detail_json)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (effective_uid, account_id, row.get("automation_id"), row["ts_open_ms"], row["direction"],
             row["entry"], row["stop"], row["target"], row.get("qty"),
             row["status"], row.get("ts_close_ms"), row.get("exit_price"),
             row.get("pnl_usdt"), json_dumps(row.get("detail", {}))))
        c.commit()
        return int(cur.lastrowid or 0)


def open_shadow_trades(user_id: int | None = None) -> list[dict]:
    c = _auto_conn()
    q = ("SELECT id,user_id,account_id,automation_id,ts_open_ms,direction,entry,stop,target,qty "
         "FROM shadow_trades WHERE status='OPEN_SHADOW'")
    args: list = []
    if user_id is not None:
        q += " AND user_id=?"
        args.append(user_id)
    with _lock:
        rows = c.execute(q, args).fetchall()
    keys = ("id", "user_id", "account_id", "automation_id", "ts_open_ms", "direction", "entry", "stop",
            "target", "qty")
    return [dict(zip(keys, r)) for r in rows]


# ---------------------------------------------------------------- watchlist

def _wl_conn() -> sqlite3.Connection:
    c = _connect()
    with _lock:
        c.execute("""CREATE TABLE IF NOT EXISTS watchlist(
            user_id INTEGER DEFAULT 1, symbol TEXT, added_ms INTEGER, active INTEGER DEFAULT 1,
            PRIMARY KEY(user_id, symbol))""")
            
        c.execute("DROP TABLE IF EXISTS user_watchlist")

        c.execute("CREATE TABLE IF NOT EXISTS events("
                  "event_id TEXT PRIMARY KEY, kind TEXT, trade_id INTEGER,"
                  "created_ms INTEGER)")
        
        c.execute("""CREATE TABLE IF NOT EXISTS positions(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER DEFAULT 1,
            account_id INTEGER DEFAULT 1,
            opened_ms INTEGER, symbol TEXT, direction TEXT, entry REAL, qty REAL,
            leverage REAL, margin_usdt REAL, stops_json TEXT, targets_json TEXT,
            trailing_pct REAL, trailing_ref REAL, stop_current REAL, status TEXT,
            mode TEXT, client_order_id TEXT, closed_ms INTEGER, exit_price REAL,
            realized_pnl REAL, detail_json TEXT)""")
            
        try:
            c.execute("ALTER TABLE positions ADD COLUMN user_id INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE positions ADD COLUMN account_id INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass

        c.execute("""CREATE TABLE IF NOT EXISTS audit(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER DEFAULT 1,
            ts_ms INTEGER, actor TEXT, action TEXT, detail_json TEXT)""")
            
        try:
            c.execute("ALTER TABLE audit ADD COLUMN user_id INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass

        c.execute("""CREATE TABLE IF NOT EXISTS account_snapshots(
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            ts_ms INTEGER, 
            user_id INTEGER, 
            equity REAL, 
            wallet_balance REAL, 
            margin_used REAL, 
            unrealized_pnl REAL)""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_account_snapshots_ts ON account_snapshots(ts_ms)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_account_snapshots_user ON account_snapshots(user_id)")

        c.execute("""CREATE TABLE IF NOT EXISTS ws_outbox(
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            ts_ms INTEGER, 
            user_id INTEGER, 
            event_type TEXT, 
            payload_json TEXT)""")
            
        c.execute("""CREATE TABLE IF NOT EXISTS notifications(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            dedup_key TEXT UNIQUE NOT NULL,
            severity TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            mode TEXT NOT NULL,
            category TEXT NOT NULL,
            payload_json TEXT DEFAULT '{}',
            read INTEGER DEFAULT 0,
            created_ms INTEGER NOT NULL)""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_notifications_user_ts ON notifications(user_id, created_ms DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_notifications_category ON notifications(user_id, category, created_ms DESC)")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_notifications_dedup ON notifications(dedup_key)")

        c.execute("""CREATE TABLE IF NOT EXISTS notification_settings(
            user_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 1,
            trades_enabled INTEGER DEFAULT 1,
            tp_sl_enabled INTEGER DEFAULT 1,
            risk_enabled INTEGER DEFAULT 1,
            automations_enabled INTEGER DEFAULT 1,
            system_enabled INTEGER DEFAULT 1,
            equity_4h_enabled INTEGER DEFAULT 1)""")

        c.execute("""CREATE TABLE IF NOT EXISTS equity_checkpoints(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ts_ms INTEGER NOT NULL,
            total_equity REAL NOT NULL,
            wallet_balance REAL NOT NULL,
            available_margin REAL NOT NULL,
            realized_pnl REAL DEFAULT 0.0,
            unrealized_pnl REAL DEFAULT 0.0,
            open_positions INTEGER DEFAULT 0,
            mode TEXT NOT NULL)""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_equity_checkpoints_user_ts ON equity_checkpoints(user_id, ts_ms DESC)")
            
        c.commit()
    return c


def ensure_seed_watchlist(user_id: int | None = None) -> list[str]:
    """Seed or reconcile watchlist table from config, ensuring all configured symbols
    (including GOLD (XAU)) are active, and deactivate obsolete test symbols."""
    c = _wl_conn()
    now_ms = int(time.time() * 1000)
    target_uids = [user_id] if user_id is not None else [1]
    with _lock:
        for uid in target_uids:
            for s in config.SYMBOLS:
                c.execute(
                    "INSERT INTO watchlist(user_id,symbol,added_ms,active) VALUES(?,?,?,1) "
                    "ON CONFLICT(user_id,symbol) DO UPDATE SET active=1",
                    (uid, s, now_ms)
                )
            placeholders = ",".join("?" for _ in config.SYMBOLS)
            c.execute(
                f"UPDATE watchlist SET active=0 WHERE user_id=? AND symbol NOT IN ({placeholders})",
                [uid] + list(config.SYMBOLS)
            )
        c.commit()
        effective_uid = user_id if user_id is not None else 1
        rows = c.execute("SELECT symbol FROM watchlist WHERE user_id=? AND active=1 "
                         "ORDER BY added_ms", (effective_uid,)).fetchall()
    return [r[0] for r in rows]


def get_user_watchlist(user_id: int) -> list[str]:
    c = _wl_conn()
    with _lock:
        rows = c.execute("SELECT symbol FROM watchlist WHERE user_id=? AND active=1 "
                         "ORDER BY added_ms", (user_id,)).fetchall()
        if not rows:
            return ensure_seed_watchlist(user_id)
    return [r[0] for r in rows]


def watchlist_add(symbol: str, user_id: int) -> bool:
    if not user_id or user_id <= 0:
        raise ValueError("Valid user_id required for watchlist_add")
    c = _wl_conn()
    with _lock:
        cur = c.execute("INSERT INTO watchlist(user_id,symbol,added_ms,active) VALUES(?,?,?,1) "
                        "ON CONFLICT(user_id,symbol) DO UPDATE SET active=1",
                        (user_id, symbol, int(time.time() * 1000)))
        c.commit()
    return cur.rowcount > 0


def watchlist_remove(symbol: str, user_id: int) -> bool:
    if not user_id or user_id <= 0:
        raise ValueError("Valid user_id required for watchlist_remove")
    c = _wl_conn()
    with _lock:
        cur = c.execute("UPDATE watchlist SET active=0 WHERE user_id=? AND symbol=?",
                        (user_id, symbol))
        
        # Check if anyone else is watching this symbol globally
        still_watched = c.execute("SELECT 1 FROM watchlist WHERE symbol=? AND active=1 LIMIT 1", (symbol,)).fetchone()
        if not still_watched:
            c.execute("DELETE FROM candles WHERE symbol=?", (symbol,))
            
        c.commit()
    return cur.rowcount > 0


def watchlist_symbols(user_id: int | None = None) -> list[str]:
    """Return active symbols for a user, or globally if user_id is None."""
    c = _wl_conn()
    with _lock:
        if user_id is not None:
            rows = c.execute("SELECT symbol FROM watchlist WHERE user_id=? AND active=1 "
                             "ORDER BY added_ms", (user_id,)).fetchall()
        else:
            rows = c.execute("SELECT DISTINCT symbol FROM watchlist WHERE active=1").fetchall()
    return [r[0] for r in rows]


# ---------------------------------------------------------------- mode

def get_mode() -> str:
    c = _wl_conn()
    with _lock:
        row = c.execute("SELECT value FROM meta WHERE key='trading_mode'").fetchone()
    mode = row[0] if row else None
    if mode not in ("SHADOW", "LIVE"):
        return config.DEFAULT_TRADING_MODE
    return mode


def get_exchange_account(account_id: int = 1) -> dict | None:
    c = _auto_conn()
    with _lock:
        try:
            row = c.execute(
                "SELECT id, user_id, exchange, name, api_key, api_secret_enc "
                "FROM exchange_accounts WHERE id=?", (account_id,)
            ).fetchone()
        except sqlite3.OperationalError:
            return None
    if not row:
        return None
    keys = ("id", "user_id", "exchange", "name", "api_key", "api_secret_enc")
    return dict(zip(keys, row))


def set_mode(mode: str) -> None:
    if mode not in ("SHADOW", "LIVE"):
        raise ValueError(f"invalid trading mode: {mode}")
    c = _wl_conn()
    with _lock:
        c.execute("INSERT INTO meta(key,value) VALUES('trading_mode',?) "
                  "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (mode,))
        c.commit()


def get_meta(key: str) -> str | None:
    """Read an arbitrary key from the meta table. Returns None if missing."""
    c = _wl_conn()
    with _lock:
        row = c.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def set_meta(key: str, value: str) -> None:
    """Write an arbitrary key-value pair into the meta table (upsert)."""
    c = _wl_conn()
    with _lock:
        c.execute("INSERT INTO meta(key,value) VALUES(?,?) "
                  "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
        c.commit()


# ---------------------------------------------------------------- events (idempotency)

def event_seen(event_id: str) -> bool:
    c = _wl_conn()
    with _lock:
        row = c.execute("SELECT 1 FROM events WHERE event_id=?", (event_id,)).fetchone()
    return row is not None

event_exists = event_seen


def event_record(event_id: str, kind: str, trade_id: int | None) -> None:
    c = _wl_conn()
    with _lock:
        c.execute("INSERT OR IGNORE INTO events(event_id,kind,trade_id,created_ms) "
                  "VALUES(?,?,?,?)",
                  (event_id, kind, trade_id, int(time.time() * 1000)))
        c.commit()


def event_delete(event_id: str) -> None:
    c = _wl_conn()
    with _lock:
        c.execute("DELETE FROM events WHERE event_id=?", (event_id,))
        c.commit()


# ---------------------------------------------------------------- positions

def create_position(row: dict, user_id: int | None = None, account_id: int = 1) -> int:
    effective_uid = row.get("user_id") or user_id
    if not effective_uid or effective_uid <= 0:
        raise ValueError("Valid user_id required to create position")
    c = _wl_conn()
    with _lock:
        stops_val = row["stops_json"] if isinstance(row.get("stops_json"), str) else json_dumps(row.get("stops", []))
        targets_val = row["targets_json"] if isinstance(row.get("targets_json"), str) else json_dumps(row.get("targets", []))
        cur = c.execute(
            "INSERT INTO positions(user_id,account_id,opened_ms,symbol,direction,entry,qty,leverage,"
            "margin_usdt,stops_json,targets_json,trailing_pct,trailing_ref,"
            "stop_current,status,mode,client_order_id,detail_json) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (effective_uid, account_id, int(time.time() * 1000), row["symbol"], row["direction"],
             row["entry"], row["qty"], row.get("leverage"), row.get("margin_usdt"),
             stops_val, targets_val,
             row.get("trailing_pct"), row.get("trailing_ref"), row.get("stop_current"),
             row.get("status", "OPEN"), row.get("mode", "SHADOW"),
             row.get("client_order_id"), json_dumps(row.get("detail", {}))))
        c.commit()

        pid = int(cur.lastrowid or 0)
    try:
        from . import notifications
        row_copy = dict(row)
        row_copy["id"] = pid
        row_copy["position_id"] = pid
        notifications.notify_trade_opened(row_copy, user_id=effective_uid)
    except Exception:
        pass
    return pid


def total_open_positions_count(user_id: int | None = None) -> int:
    """Return total open trades for a user (or across all users if user_id is None)."""
    c = _wl_conn()
    with _lock:
        if user_id is not None:
            pos_cnt = c.execute(
                "SELECT count(*) FROM positions WHERE status IN ('OPEN','PARTIAL','TRAILING') AND user_id=?",
                (user_id,)
            ).fetchone()[0]
            shadow_cnt = c.execute(
                "SELECT count(*) FROM shadow_trades WHERE status IN ('OPEN_SHADOW','OPEN_LIVE') AND user_id=?",
                (user_id,)
            ).fetchone()[0]
        else:
            pos_cnt = c.execute(
                "SELECT count(*) FROM positions WHERE status IN ('OPEN','PARTIAL','TRAILING')"
            ).fetchone()[0]
            shadow_cnt = c.execute(
                "SELECT count(*) FROM shadow_trades WHERE status IN ('OPEN_SHADOW','OPEN_LIVE')"
            ).fetchone()[0]
    return pos_cnt + shadow_cnt


def get_max_open_trades(user_id: int | None = None) -> int:
    """Retrieve user-configured persistent max open trades from meta table.
    Defaults to config.DEFAULT_MAX_OPEN_TRADES (4), bounded by config.SYSTEM_SAFETY_MAX_OPEN_TRADES (50).
    """
    c = _connect()
    with _lock:
        if user_id is not None and user_id >= 1:
            try:
                row = c.execute("SELECT value FROM meta WHERE key=?", (f"max_open_trades_{user_id}",)).fetchone()
                if row and row[0]:
                    val = int(row[0])
                    return max(1, min(config.SYSTEM_SAFETY_MAX_OPEN_TRADES, val))
            except Exception:
                pass
        row = c.execute("SELECT value FROM meta WHERE key='configured_max_open_trades'").fetchone()
    if row and row[0]:
        try:
            val = int(row[0])
            return max(1, min(config.SYSTEM_SAFETY_MAX_OPEN_TRADES, val))
        except (ValueError, TypeError):
            pass
    return config.DEFAULT_MAX_OPEN_TRADES


def set_max_open_trades(val: int) -> int:
    """Update user-configured persistent max open trades in meta table.
    Must be between 1 and config.SYSTEM_SAFETY_MAX_OPEN_TRADES.
    """
    val = int(val)
    if val < 1:
        raise ValueError("max_open_trades must be at least 1")
    if val > config.SYSTEM_SAFETY_MAX_OPEN_TRADES:
        raise ValueError(f"max_open_trades cannot exceed system safety ceiling ({config.SYSTEM_SAFETY_MAX_OPEN_TRADES})")
    c = _connect()
    with _lock:
        c.execute(
            "INSERT INTO meta(key,value) VALUES('configured_max_open_trades',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(val),)
        )
        c.commit()
    return val


def count_active_automations(user_id: int) -> int:
    """Return count of active automations for user (decoupled from open trade cap)."""
    if not user_id or user_id <= 0:
        raise ValueError("Valid user_id required for count_active_automations")
    c = _auto_conn()
    with _lock:
        row = c.execute(
            "SELECT count(*) FROM automations WHERE user_id=? AND status IN ('ACTIVE', 'RUNNING')",
            (user_id,)
        ).fetchone()
    return int(row[0] if row else 0)


def get_capacity_metrics(user_id: int) -> dict:
    """Authoritative capacity and exposure metrics enforcing configurable trade cap.
    Separates configured_max_open_trades from system_safety_max_open_trades.
    If cap is lowered below current exposure:
      - never force-close existing positions
      - block new entries
      - available slots = 0
      - cap_state = 'CAP_BELOW_EXPOSURE', cap_message = 'CAP BELOW CURRENT EXPOSURE'
    """
    if not user_id or user_id <= 0:
        raise ValueError("Valid user_id required for get_capacity_metrics")
    configured_max = get_max_open_trades()
    safety_max = config.SYSTEM_SAFETY_MAX_OPEN_TRADES
    open_count = total_open_positions_count(user_id=user_id)
    active_autos = count_active_automations(user_id)

    if configured_max < open_count:
        avail_slots = 0
        cap_state = "CAP_BELOW_EXPOSURE"
        cap_msg = "CAP BELOW CURRENT EXPOSURE"
    elif configured_max == open_count:
        avail_slots = 0
        cap_state = "CAP_REACHED"
        cap_msg = "CAP REACHED"
    else:
        avail_slots = configured_max - open_count
        cap_state = "SLOTS_AVAILABLE"
        cap_msg = f"{avail_slots} SLOTS AVAILABLE"

    return {
        "configured_max_open_trades": configured_max,
        "system_safety_max_open_trades": safety_max,
        "max_open_trades": configured_max,
        "open_positions_count": open_count,
        "available_execution_slots": avail_slots,
        "active_automations_count": active_autos,
        "cap_state": cap_state,
        "cap_message": cap_msg,
    }


def update_position(pid: int, **fields) -> None:
    if not fields:
        return
    if "detail" in fields:
        d = fields.pop("detail")
        fields["detail_json"] = json.dumps(d) if isinstance(d, (dict, list)) else str(d)
    if "stops" in fields:
        s = fields.pop("stops")
        fields["stops_json"] = json.dumps(s) if isinstance(s, (dict, list)) else str(s)
    if "targets" in fields:
        t = fields.pop("targets")
        fields["targets_json"] = json.dumps(t) if isinstance(t, (dict, list)) else str(t)
    allowed = {"qty", "stop_current", "trailing_ref", "trailing_pct",
               "status", "closed_ms", "exit_price", "realized_pnl",
               "stops_json", "targets_json", "detail_json", "client_order_id",
               "entry", "leverage", "margin_usdt"}
    sets = []
    args: list = []
    for k, v in fields.items():
        if k not in allowed:
            raise ValueError(f"field not allowed: {k}")
        sets.append(f"{k}=?")
        args.append(v)
    args.append(pid)
    c = _wl_conn()
    with _lock:
        c.execute(f"UPDATE positions SET {', '.join(sets)} WHERE id=?", args)
        c.commit()

    if fields.get("status") in ("CLOSED", "STOPPED", "TRAILING_STOPPED", "DESYNC_CLOSED"):
        try:
            release_slot_by_position(pid)
            release_slot_by_position(str(pid))
            row = c.execute("SELECT detail_json FROM positions WHERE id=?", (pid,)).fetchone()
            if row and row[0]:
                d = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                if isinstance(d, dict) and d.get("slot_id"):
                    release_autonomous_trade_slot(int(d["slot_id"]))
        except Exception:
            pass



def open_positions(mode: str | None = None, user_id: int | None = None) -> list[dict]:
    c = _wl_conn()
    q = ("SELECT id,user_id,account_id,opened_ms,symbol,direction,entry,qty,leverage,margin_usdt,"
         "stops_json,targets_json,trailing_pct,trailing_ref,stop_current,status,"
         "mode,client_order_id,detail_json FROM positions WHERE status IN "
         "('OPEN','PARTIAL','TRAILING')")
    args: list = []
    if user_id is not None:
        q += " AND user_id=?"
        args.append(user_id)
    if mode:
        q += " AND mode=?"
        args.append(mode)
    q += " ORDER BY id"
    with _lock:
        rows = c.execute(q, args).fetchall()
    keys = ("id", "user_id", "account_id", "opened_ms", "symbol", "direction", "entry", "qty", "leverage",
            "margin_usdt", "stops_json", "targets_json", "trailing_pct",
            "trailing_ref", "stop_current", "status", "mode", "client_order_id",
            "detail_json")
    out = []
    for r in rows:
        d = dict(zip(keys, r))
        d["stops"] = json.loads(d.pop("stops_json") or "[]")
        d["targets"] = json.loads(d.pop("targets_json") or "[]")
        try:
            d["detail"] = json.loads(d.pop("detail_json") or "{}")
        except json.JSONDecodeError:
            d["detail"] = {}
        out.append(d)
    return out


def get_position(pid: int, user_id: int | None = None) -> dict | None:
    c = _wl_conn()
    q = ("SELECT id,user_id,account_id,opened_ms,symbol,direction,entry,qty,leverage,margin_usdt,"
         "stops_json,targets_json,trailing_pct,trailing_ref,stop_current,status,"
         "mode,client_order_id,detail_json FROM positions WHERE id=?")
    args: list = [pid]
    if user_id is not None:
        q += " AND user_id=?"
        args.append(user_id)
    with _lock:
        row = c.execute(q, args).fetchone()
    if not row:
        return None
    keys = ("id", "user_id", "account_id", "opened_ms", "symbol", "direction", "entry", "qty", "leverage",
            "margin_usdt", "stops_json", "targets_json", "trailing_pct",
            "trailing_ref", "stop_current", "status", "mode", "client_order_id",
            "detail_json")
    d = dict(zip(keys, row))
    try:
        d["stops"] = json.loads(d.pop("stops_json") or "[]")
    except Exception:
        d["stops"] = []
    try:
        d["targets"] = json.loads(d.pop("targets_json") or "[]")
    except Exception:
        d["targets"] = []
    try:
        d["detail"] = json.loads(d.pop("detail_json") or "{}")
    except Exception:
        d["detail"] = {}
    return d


def has_open_position_for_automation(automation_id: int, user_id: int, mode: str | None = None) -> bool:
    """Return True if an active open position already exists for this automation and user."""
    if not user_id or user_id < 1:
        raise ValueError("Explicit positive user_id is required to check automation positions")
    c = _wl_conn()
    q = ("SELECT detail_json FROM positions WHERE status IN ('OPEN','PARTIAL','TRAILING') AND user_id=?")
    args: list = [user_id]
    if mode:
        q += " AND mode=?"
        args.append(mode)
    with _lock:
        rows = c.execute(q, args).fetchall()
    for r in rows:
        try:
            det = json.loads(r[0] or "{}")
            if det.get("automation_id") == automation_id:
                return True
        except Exception:
            pass
    return False


def has_open_position_for_symbol(symbol: str, user_id: int, mode: str | None = None) -> bool:
    """Return True if an active open position already exists for this symbol and user."""
    if not user_id or user_id < 1:
        raise ValueError("Explicit positive user_id is required to check symbol positions")
    c = _wl_conn()
    q = ("SELECT count(*) FROM positions WHERE status IN ('OPEN','PARTIAL','TRAILING') AND user_id=? AND symbol=?")
    args: list = [user_id, symbol]
    if mode:
        q += " AND mode=?"
        args.append(mode)
    with _lock:
        cnt = c.execute(q, args).fetchone()[0]
    return cnt > 0


def closed_positions_since(start_ms: int, user_id: int | None = None) -> list[dict]:
    c = _wl_conn()
    q = ("SELECT id,user_id,account_id,symbol,direction,entry,exit_price,qty,realized_pnl,mode "
         "FROM positions WHERE status IN ('CLOSED','STOPPED','TARGET') AND closed_ms>=?")
    args = [start_ms]
    if user_id is not None:
        q += " AND user_id=?"
        args.append(user_id)
    with _lock:
        rows = c.execute(q, args).fetchall()
    keys = ("id", "user_id", "account_id", "symbol", "direction", "entry", "exit_price", "qty",
            "realized_pnl", "mode")
    return [dict(zip(keys, r)) for r in rows]


def get_recent_completed_trades(limit: int = 3, user_id: int | None = None) -> list[dict]:
    c = _wl_conn()
    q = ("SELECT id, symbol, direction, entry, exit_price, qty, realized_pnl, "
         "leverage, margin_usdt, closed_ms FROM positions "
         "WHERE status IN ('CLOSED','STOPPED','TARGET') "
         "AND exit_price IS NOT NULL AND closed_ms > 1000000 ")
    args: list = []
    if user_id is not None:
        q += "AND user_id=? "
        args.append(user_id)
    q += "ORDER BY closed_ms DESC LIMIT ?"
    args.append(limit)
    with _lock:
        rows = c.execute(q, args).fetchall()
    keys = ("id", "symbol", "direction", "entry", "exit_price", "qty", "realized_pnl", 
            "leverage", "margin", "closed_ms")
    out = []
    for r in rows:
        d = dict(zip(keys, r))
        # Compute PnL % based on entry and exit if possible, otherwise rough estimate
        if d["entry"] and d["exit_price"] and d["leverage"]:
            sign = 1 if d["direction"] == "LONG" else -1
            move_pct = (d["exit_price"] / d["entry"] - 1) * sign
            d["pnl_pct"] = round(move_pct * d["leverage"] * 100, 2)
        else:
            d["pnl_pct"] = 0.0
        # If margin is None (e.g. older trades), approximate it
        if not d["margin"] and d["entry"] and d["qty"] and d["leverage"]:
            d["margin"] = round((d["entry"] * d["qty"]) / d["leverage"], 2)
        out.append(d)
    return out


def insert_account_snapshot(user_id: int, equity: float, wallet_balance: float, 
                            margin_used: float, unrealized_pnl: float) -> None:
    c = _wl_conn()
    with _lock:
        c.execute(
            "INSERT INTO account_snapshots(ts_ms, user_id, equity, wallet_balance, margin_used, unrealized_pnl) "
            "VALUES(?,?,?,?,?,?)",
            (int(time.time() * 1000), user_id, equity, wallet_balance, margin_used, unrealized_pnl)
        )
        c.commit()


def get_equity_at_or_before(ts_ms: int, user_id: int) -> float | None:
    if not user_id or user_id < 1:
        raise ValueError("Valid user_id required to get equity snapshot")
    c = _wl_conn()
    with _lock:
        # Get the snapshot closest to but not after ts_ms
        row = c.execute(
            "SELECT equity FROM account_snapshots WHERE user_id=? AND ts_ms<=? ORDER BY ts_ms DESC LIMIT 1",
            (user_id, ts_ms)
        ).fetchone()
    return row[0] if row else None


def get_paginated_trade_history(user_id: int, page: int = 1, limit: int = 50,
                                symbol: str | None = None, status: str | None = None,
                                mode: str | None = None) -> dict:
    if not user_id or user_id < 1:
        raise ValueError("Valid user_id required for trade history")
    c = _wl_conn()
    offset = max(0, (page - 1) * limit)
    query = ("SELECT id, user_id, symbol, direction, entry, exit_price, qty, realized_pnl, "
             "leverage, margin_usdt, status, mode, opened_ms, closed_ms, detail_json, "
             "stops_json, targets_json, trailing_pct, stop_current "
             "FROM positions WHERE user_id=? ")
    count_query = "SELECT COUNT(*) FROM positions WHERE user_id=? "
    params: list = [user_id]
    
    if symbol:
        query += " AND symbol=? "
        count_query += " AND symbol=? "
        params.append(symbol)
    if status:
        query += " AND status=? "
        count_query += " AND status=? "
        params.append(status)
    if mode:
        query += " AND mode=? "
        count_query += " AND mode=? "
        params.append(mode)
        
    with _lock:
        total = c.execute(count_query, params).fetchone()[0]
        query += " ORDER BY closed_ms DESC, opened_ms DESC LIMIT ? OFFSET ?"
        exec_params = list(params)
        exec_params.extend([limit, offset])
        rows = c.execute(query, exec_params).fetchall()
        
    keys = ("id", "user_id", "symbol", "direction", "entry", "exit_price", "qty", "realized_pnl",
            "leverage", "margin", "status", "mode", "opened_ms", "closed_ms", "detail_json",
            "stops_json", "targets_json", "trailing_pct", "stop_current")
    trades = []
    for r in rows:
        d = dict(zip(keys, r))
        try:
            detail = json.loads(d.pop("detail_json") or "{}")
        except Exception:
            detail = {}
        d["reason_close"] = detail.get("reason_close", detail.get("exit_reason", ""))
        d["fees"] = float(detail.get("fees", 0.0) or 0.0)
        d["funding"] = float(detail.get("funding", 0.0) or 0.0)
        if d.get("opened_ms") and d.get("closed_ms"):
            d["duration_sec"] = max(0, int((d["closed_ms"] - d["opened_ms"]) / 1000))
        else:
            d["duration_sec"] = 0
            
        # Parse SL / TP / Trailing
        try:
            stops = json.loads(d.pop("stops_json") or "[]")
            d["sl"] = float(stops[0]["value"] if stops and isinstance(stops[0], dict) else (stops[0] if stops else d.get("stop_current") or 0.0))
        except Exception:
            d["sl"] = float(d.get("stop_current") or 0.0)
        try:
            targets = json.loads(d.pop("targets_json") or "[]")
            d["tp"] = float(targets[0]["value"] if targets and isinstance(targets[0], dict) else (targets[0] if targets else 0.0))
        except Exception:
            d["tp"] = 0.0
            
        d["trailing"] = float(d.get("trailing_pct") or detail.get("trailing_pct") or 0.0)
        
        if d["entry"] and d["exit_price"] and d["leverage"]:
            sign = 1 if d["direction"] == "LONG" else -1
            move_pct = (d["exit_price"] / d["entry"] - 1) * sign
            d["pnl_pct"] = round(move_pct * d["leverage"] * 100, 2)
        else:
            d["pnl_pct"] = 0.0
        trades.append(d)
        
    return {
        "page": page,
        "limit": limit,
        "total": total,
        "pages": (total + limit - 1) // limit if limit > 0 else 1,
        "trades": trades
    }


def get_performance_analytics(user_id: int, range_days: int = 30) -> dict:
    if not user_id or user_id < 1:
        raise ValueError("Valid user_id required for performance analytics")
    c = _wl_conn()
    now = int(time.time() * 1000)
    cutoff = now - (range_days * 86400 * 1000)
    
    with _lock:
        # Snapshots for equity curve
        snap_rows = c.execute(
            "SELECT ts_ms, equity, wallet_balance, unrealized_pnl FROM account_snapshots "
            "WHERE user_id=? AND ts_ms>=? ORDER BY ts_ms ASC", (user_id, cutoff)
        ).fetchall()
        
        # Closed positions for trade performance
        pos_rows = c.execute(
            "SELECT realized_pnl, status, closed_ms, symbol FROM positions "
            "WHERE user_id=? AND closed_ms>=? AND status IN ('CLOSED','STOPPED','TARGET')",
            (user_id, cutoff)
        ).fetchall()
        
    equity_curve = [{"ts": r[0], "equity": float(r[1]), "balance": float(r[2]), "upnl": float(r[3])} for r in snap_rows]
    
    total_trades = len(pos_rows)
    wins = [r[0] for r in pos_rows if (r[0] or 0.0) > 0]
    losses = [r[0] for r in pos_rows if (r[0] or 0.0) < 0]
    
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = round((win_count / total_trades) * 100, 2) if total_trades > 0 else 0.0
    
    total_win_pnl = sum(wins)
    total_loss_pnl = abs(sum(losses))
    profit_factor = round(total_win_pnl / total_loss_pnl, 2) if total_loss_pnl > 0 else (round(total_win_pnl, 2) if total_win_pnl > 0 else 1.0)
    
    net_pnl = round(sum([r[0] or 0.0 for r in pos_rows]), 2)
    avg_win = round(total_win_pnl / win_count, 2) if win_count > 0 else 0.0
    avg_loss = round(sum(losses) / loss_count, 2) if loss_count > 0 else 0.0
    
    return {
        "range_days": range_days,
        "total_trades": total_trades,
        "wins": win_count,
        "losses": loss_count,
        "win_rate": win_rate,
        "net_pnl": net_pnl,
        "profit_factor": profit_factor,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "equity_curve": equity_curve
    }


def get_audit_events(user_id: int | None = None, limit: int = 50, offset: int = 0, component: str | None = None) -> list[dict]:
    c = _wl_conn()
    clauses = []
    params = []
    if user_id is not None:
        clauses.append("user_id=?")
        params.append(user_id)
    if component:
        clauses.append("actor=?")
        params.append(component)
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    query = f"SELECT id, user_id, ts_ms, actor, action, detail_json FROM audit {where_sql} ORDER BY ts_ms DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with _lock:
        rows = c.execute(query, params).fetchall()
    keys = ("id", "user_id", "ts_ms", "actor", "action", "detail")
    out = []
    for r in rows:
        d = dict(zip(keys, r))
        try:
            d["detail"] = json.loads(d["detail"] or "{}")
        except Exception:
            d["detail"] = {}
        ts = d.get("ts_ms") or int(time.time() * 1000)
        d["timestamp_iso"] = datetime.fromtimestamp(ts / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        d["component"] = d.get("actor") or "SYSTEM"
        d["symbol"] = d["detail"].get("symbol") if isinstance(d.get("detail"), dict) else None
        d["result"] = d["detail"].get("result") or d["detail"].get("status") if isinstance(d.get("detail"), dict) else "OK"
        out.append(d)
    return out


# ---------------------------------------------------------------- audit

def audit(actor: str, action: str, detail: dict, user_id: int | None = None, symbol: str | None = None, mode: str | None = None, result: str | None = None) -> None:
    c = _wl_conn()
    sanitized_detail = dict(detail) if isinstance(detail, dict) else {"info": str(detail)}
    if symbol:
        sanitized_detail["symbol"] = symbol
    if mode:
        sanitized_detail["mode"] = mode
    if result:
        sanitized_detail["result"] = result

    # Sanitize any accidental sensitive fields
    for k in list(sanitized_detail.keys()):
        if any(sens in k.lower() for sens in ["key", "secret", "password", "token", "auth"]):
            sanitized_detail[k] = "***REDACTED***"

    now_ms = int(time.time() * 1000)
    effective_uid = user_id if (user_id is not None and user_id > 0) else 0
    with _lock:
        c.execute("INSERT INTO audit(user_id,ts_ms,actor,action,detail_json) VALUES(?,?,?,?,?)",
                  (effective_uid, now_ms, actor.upper(), action.upper(), json_dumps(sanitized_detail)))
        c.commit()

    # Also log to in-memory terminal buffer if available
    try:
        from . import core
        if hasattr(core, "log_terminal_line"):
            core.log_terminal_line(actor, f"{action} | {json_dumps(sanitized_detail)}")
    except Exception:
        pass


# ---------------------------------------------------------------- accounts & connection control

def get_api_credential_source() -> str:
    c = _wl_conn()
    with _lock:
        row = c.execute("SELECT value FROM meta WHERE key='api_credential_source'").fetchone()
    return row[0] if row and row[0] in ("VPS", "APP") else "VPS"

def set_api_credential_source(source: str, user_id: int | None = None) -> str:
    src = source.upper()
    if src not in ("VPS", "APP"):
        raise ValueError("Invalid credential source; must be VPS or APP")
    c = _wl_conn()
    with _lock:
        c.execute("INSERT INTO meta(key, value) VALUES('api_credential_source', ?) "
                  "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (src,))
        c.commit()
    audit("SYSTEM", "CREDENTIAL_SOURCE_CHANGE", {"new_source": src}, user_id=user_id)
    return src

def get_bingx_connection_enabled() -> bool:
    c = _wl_conn()
    with _lock:
        row = c.execute("SELECT value FROM meta WHERE key='bingx_connection_enabled'").fetchone()
    return (row[0].lower() == "true") if row else True

def set_bingx_connection_enabled(enabled: bool, user_id: int | None = None) -> bool:
    val = "true" if enabled else "false"
    c = _wl_conn()
    with _lock:
        c.execute("INSERT INTO meta(key, value) VALUES('bingx_connection_enabled', ?) "
                  "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (val,))
        c.commit()
    action = "BINGX_CONNECT" if enabled else "BINGX_DISCONNECT"
    audit("SYSTEM", action, {"enabled": enabled}, user_id=user_id)
    return enabled

def purge_fake_test_records() -> dict:
    c = _auto_conn()
    with _lock:
        del_pos = c.execute("DELETE FROM positions WHERE user_id = 99 OR (symbol='SOL-USDT' AND entry >= 60000)").rowcount
        del_notif = c.execute("DELETE FROM notifications WHERE user_id = 99 OR id IN (11, 18, 23) OR message LIKE '%SOL-USDT%65,000%' OR message LIKE '%SOL-USDT%65,100%'").rowcount
        c.commit()
    return {"purged_positions": del_pos, "purged_notifications": del_notif}

def add_exchange_account(user_id: int, exchange: str, name: str, api_key: str, api_secret_enc: str) -> int:
    c = _wl_conn()
    with _lock:
        cur = c.execute(
            "INSERT INTO exchange_accounts(user_id, exchange, name, api_key, api_secret_enc) "
            "VALUES(?,?,?,?,?)", (user_id, exchange, name, api_key, api_secret_enc)
        )
        c.commit()
        return cur.lastrowid

def get_user_exchange_accounts(user_id: int) -> list[dict]:
    c = _auto_conn()
    with _lock:
        rows = c.execute(
            "SELECT id, exchange, name, api_key FROM exchange_accounts WHERE user_id=?", 
            (user_id,)
        ).fetchall()
    keys = ("id", "exchange", "name", "api_key")
    return [dict(zip(keys, r)) for r in rows]

def delete_exchange_account(account_id: int, user_id: int) -> bool:
    c = _wl_conn()
    with _lock:
        cur = c.execute("DELETE FROM exchange_accounts WHERE id=? AND user_id=?", (account_id, user_id))
        c.commit()
        return cur.rowcount > 0

# ---------------------------------------------------------------- ws outbox

def emit_ws_event(event_type: str, payload: dict, user_id: int) -> None:
    c = _wl_conn()
    import json, time
    with _lock:
        c.execute(
            'INSERT INTO ws_outbox(ts_ms, user_id, event_type, payload_json) VALUES(?,?,?,?)',
            (int(time.time() * 1000), user_id, event_type, json.dumps(payload))
        )
        c.commit()

def poll_ws_outbox(last_id: int) -> list[tuple[int, int, str, dict]]:
    c = _wl_conn()
    import json
    with _lock:
        rows = c.execute(
            'SELECT id, user_id, event_type, payload_json FROM ws_outbox WHERE id > ? ORDER BY id ASC LIMIT 100', 
            (last_id,)
        ).fetchall()
    
    events = []
    for r in rows:


        try:
            payload = json.loads(r[3])
            events.append((r[0], r[1], r[2], payload))
        except Exception:
            pass
    return events

def cleanup_ws_outbox(max_age_ms: int = 3600000) -> None:
    import time
    cutoff = int(time.time() * 1000) - max_age_ms
    c = _wl_conn()
    with _lock:
        c.execute('DELETE FROM ws_outbox WHERE ts_ms < ?', (cutoff,))
        c.commit()


# ---------------------------------------------------------------- notifications

def create_notification(user_id: int, event_type: str, dedup_key: str, severity: str,
                        title: str, message: str, mode: str, category: str,
                        payload: dict | None = None) -> tuple[dict | None, bool]:
    """Idempotently insert a notification. Returns (notification_dict, True) if newly created,
    or (None, False) if dedup_key already exists."""
    import json, time
    now_ms = int(time.time() * 1000)
    payload_str = json.dumps(payload or {})
    c = _wl_conn()
    with _lock:
        try:
            cur = c.execute(
                "INSERT INTO notifications(user_id, event_type, dedup_key, severity, "
                "title, message, mode, category, payload_json, read, created_ms) "
                "VALUES(?,?,?,?,?,?,?,?,?,0,?)",
                (user_id, event_type, dedup_key, severity, title, message, mode, category, payload_str, now_ms)
            )
            c.commit()
            if cur.rowcount > 0:
                notif_id = cur.lastrowid
                row = {
                    "id": notif_id,
                    "user_id": user_id,
                    "event_type": event_type,
                    "dedup_key": dedup_key,
                    "severity": severity,
                    "title": title,
                    "message": message,
                    "mode": mode,
                    "category": category,
                    "payload": payload or {},
                    "read": False,
                    "created_ms": now_ms
                }
                return row, True
        except sqlite3.IntegrityError:
            # Duplicate dedup_key
            pass
    return None, False


def get_notifications(user_id: int, category: str = "ALL", limit: int = 50, offset: int = 0) -> list[dict]:
    if not user_id or user_id < 1:
        raise ValueError("Valid user_id required to get notifications")
    import json
    c = _wl_conn()
    with _lock:
        if category and category != "ALL":
            rows = c.execute(
                "SELECT id, user_id, event_type, dedup_key, severity, title, message, mode, category, payload_json, read, created_ms "
                "FROM notifications WHERE user_id=? AND category=? ORDER BY created_ms DESC LIMIT ? OFFSET ?",
                (user_id, category, limit, offset)
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT id, user_id, event_type, dedup_key, severity, title, message, mode, category, payload_json, read, created_ms "
                "FROM notifications WHERE user_id=? ORDER BY created_ms DESC LIMIT ? OFFSET ?",
                (user_id, limit, offset)
            ).fetchall()
    
    out = []
    for r in rows:
        try:
            p = json.loads(r[9]) if r[9] else {}
        except Exception:
            p = {}
        out.append({
            "id": r[0],
            "user_id": r[1],
            "event_type": r[2],
            "dedup_key": r[3],
            "severity": r[4],
            "title": r[5],
            "message": r[6],
            "mode": r[7],
            "category": r[8],
            "payload": p,
            "read": bool(r[10]),
            "created_ms": r[11]
        })
    return out


def mark_notification_read(notif_id: int, user_id: int) -> bool:
    if not user_id or user_id < 1:
        raise ValueError("Valid user_id required to mark notification read")
    c = _wl_conn()
    with _lock:
        cur = c.execute("UPDATE notifications SET read=1 WHERE id=? AND user_id=?", (notif_id, user_id))
        c.commit()
        return cur.rowcount > 0


def mark_all_notifications_read(user_id: int) -> int:
    if not user_id or user_id < 1:
        raise ValueError("Valid user_id required to mark all notifications read")
    c = _wl_conn()
    with _lock:
        cur = c.execute("UPDATE notifications SET read=1 WHERE user_id=? AND read=0", (user_id,))
        c.commit()
        return cur.rowcount


def get_unread_notification_count(user_id: int) -> int:
    if not user_id or user_id < 1:
        raise ValueError("Valid user_id required to get unread notification count")
    c = _wl_conn()
    with _lock:
        row = c.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND read=0", (user_id,)).fetchone()
    return row[0] if row else 0


def clear_all_notifications(user_id: int) -> int:
    """Clear user notifications only. Persistent audit logs remain 100% untouched."""
    if not user_id or user_id < 1:
        raise ValueError("Valid user_id required to clear notifications")
    c = _wl_conn()
    with _lock:
        cur = c.execute("DELETE FROM notifications WHERE user_id=?", (user_id,))
        c.commit()
        return cur.rowcount


def get_notification_settings(user_id: int) -> dict:
    if not user_id or user_id < 1:
        raise ValueError("Valid user_id required to get notification settings")
    c = _wl_conn()
    with _lock:
        row = c.execute(
            "SELECT enabled, trades_enabled, tp_sl_enabled, risk_enabled, "
            "automations_enabled, system_enabled, equity_4h_enabled "
            "FROM notification_settings WHERE user_id=?", (user_id,)
        ).fetchone()
    if not row:
        # Default settings
        return {
            "enabled": True,
            "trades_enabled": True,
            "tp_sl_enabled": True,
            "risk_enabled": True,
            "automations_enabled": True,
            "system_enabled": True,
            "equity_4h_enabled": True
        }
    return {
        "enabled": bool(row[0]),
        "trades_enabled": bool(row[1]),
        "tp_sl_enabled": bool(row[2]),
        "risk_enabled": bool(row[3]),
        "automations_enabled": bool(row[4]),
        "system_enabled": bool(row[5]),
        "equity_4h_enabled": bool(row[6])
    }


def save_notification_settings(user_id: int, settings: dict) -> dict:
    c = _wl_conn()
    with _lock:
        c.execute(
            "INSERT INTO notification_settings(user_id, enabled, trades_enabled, tp_sl_enabled, "
            "risk_enabled, automations_enabled, system_enabled, equity_4h_enabled) "
            "VALUES(?,?,?,?,?,?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "enabled=excluded.enabled, "
            "trades_enabled=excluded.trades_enabled, "
            "tp_sl_enabled=excluded.tp_sl_enabled, "
            "risk_enabled=excluded.risk_enabled, "
            "automations_enabled=excluded.automations_enabled, "
            "system_enabled=excluded.system_enabled, "
            "equity_4h_enabled=excluded.equity_4h_enabled",
            (
                user_id,
                int(settings.get("enabled", True)),
                int(settings.get("trades_enabled", True)),
                int(settings.get("tp_sl_enabled", True)),
                int(settings.get("risk_enabled", True)),
                int(settings.get("automations_enabled", True)),
                int(settings.get("system_enabled", True)),
                int(settings.get("equity_4h_enabled", True))
            )
        )
        c.commit()
    return get_notification_settings(user_id)


# ---------------------------------------------------------------- equity checkpoints

def record_equity_checkpoint(user_id: int, equity: float, balance: float,
                            avail_margin: float, realized_pnl: float = 0.0,
                            unrealized_pnl: float = 0.0, open_positions: int = 0,
                            mode: str = "SHADOW", ts_ms: int | None = None) -> int:
    import time
    if ts_ms is None:
        ts_ms = int(time.time() * 1000)
    c = _wl_conn()
    with _lock:
        cur = c.execute(
            "INSERT INTO equity_checkpoints(user_id, ts_ms, total_equity, wallet_balance, "
            "available_margin, realized_pnl, unrealized_pnl, open_positions, mode) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (user_id, ts_ms, equity, balance, avail_margin, realized_pnl, unrealized_pnl, open_positions, mode)
        )
        c.commit()
        return cur.lastrowid


def get_latest_equity_checkpoint(user_id: int) -> dict | None:
    if not user_id or user_id < 1:
        return None
    c = _wl_conn()
    with _lock:
        row = c.execute(
            "SELECT id, user_id, ts_ms, total_equity, wallet_balance, available_margin, "
            "realized_pnl, unrealized_pnl, open_positions, mode "
            "FROM equity_checkpoints WHERE user_id=? ORDER BY ts_ms DESC LIMIT 1",
            (user_id,)
        ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "user_id": row[1],
        "ts_ms": row[2],
        "total_equity": row[3],
        "wallet_balance": row[4],
        "available_margin": row[5],
        "realized_pnl": row[6],
        "unrealized_pnl": row[7],
        "open_positions": row[8],
        "mode": row[9]
    }


def get_equity_checkpoint_before(user_id: int, ts_ms: int) -> dict | None:
    c = _wl_conn()
    with _lock:
        row = c.execute(
            "SELECT id, user_id, ts_ms, total_equity, wallet_balance, available_margin, "
            "realized_pnl, unrealized_pnl, open_positions, mode "
            "FROM equity_checkpoints WHERE user_id=? AND ts_ms<=? ORDER BY ts_ms DESC LIMIT 1",
            (user_id, ts_ms)
        ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "user_id": row[1],
        "ts_ms": row[2],
        "total_equity": row[3],
        "wallet_balance": row[4],
        "available_margin": row[5],
        "realized_pnl": row[6],
        "unrealized_pnl": row[7],
        "open_positions": row[8],
        "mode": row[9]
    }


# ============================================================
# RETEST STATE PERSISTENCE (CAUSAL DETERMINISTIC STATE MACHINE)
# ============================================================

def save_retest_state(record: dict) -> None:
    c = _auto_conn()
    now_ms = int(time.time() * 1000)
    with _lock:
        existing = c.execute(
            "SELECT id FROM retest_states WHERE symbol=? AND timeframe=? AND direction=?",
            (record["symbol"], record["timeframe"], record["direction"])
        ).fetchone()
        if existing:
            c.execute(
                "UPDATE retest_states SET state=?, breakout_ts=?, breakout_price=?, "
                "vwap_at_breakout=?, zone_low=?, zone_high=?, fvg_id=?, elapsed_candles=?, "
                "touch_ts=?, rejection_ts=?, confirmation_ts=?, invalidation_ts=?, updated_ms=? "
                "WHERE id=?",
                (record.get("state", "IDLE"), record.get("breakout_ts"), record.get("breakout_price"),
                 record.get("vwap_at_breakout"), record.get("zone_low"), record.get("zone_high"),
                 record.get("fvg_id"), record.get("elapsed_candles", 0), record.get("touch_ts"),
                 record.get("rejection_ts"), record.get("confirmation_ts"), record.get("invalidation_ts"),
                 now_ms, existing[0])
            )
        else:
            c.execute(
                "INSERT INTO retest_states(symbol, timeframe, direction, state, breakout_ts, "
                "breakout_price, vwap_at_breakout, zone_low, zone_high, fvg_id, elapsed_candles, "
                "touch_ts, rejection_ts, confirmation_ts, invalidation_ts, updated_ms) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (record["symbol"], record["timeframe"], record["direction"], record.get("state", "IDLE"),
                 record.get("breakout_ts"), record.get("breakout_price"), record.get("vwap_at_breakout"),
                 record.get("zone_low"), record.get("zone_high"), record.get("fvg_id"),
                 record.get("elapsed_candles", 0), record.get("touch_ts"), record.get("rejection_ts"),
                 record.get("confirmation_ts"), record.get("invalidation_ts"), now_ms)
            )
        c.commit()


def get_retest_state(symbol: str, timeframe: int, direction: str) -> dict | None:
    c = _auto_conn()
    with _lock:
        row = c.execute(
            "SELECT id, symbol, timeframe, direction, state, breakout_ts, breakout_price, "
            "vwap_at_breakout, zone_low, zone_high, fvg_id, elapsed_candles, touch_ts, "
            "rejection_ts, confirmation_ts, invalidation_ts, updated_ms "
            "FROM retest_states WHERE symbol=? AND timeframe=? AND direction=?",
            (symbol, timeframe, direction)
        ).fetchone()
    if not row:
        return None
    keys = ["id", "symbol", "timeframe", "direction", "state", "breakout_ts", "breakout_price",
            "vwap_at_breakout", "zone_low", "zone_high", "fvg_id", "elapsed_candles", "touch_ts",
            "rejection_ts", "confirmation_ts", "invalidation_ts", "updated_ms"]
    return dict(zip(keys, row))


def list_retest_states(symbol: str | None = None) -> list[dict]:
    c = _auto_conn()
    q = ("SELECT id, symbol, timeframe, direction, state, breakout_ts, breakout_price, "
         "vwap_at_breakout, zone_low, zone_high, fvg_id, elapsed_candles, touch_ts, "
         "rejection_ts, confirmation_ts, invalidation_ts, updated_ms FROM retest_states")
    args = []
    if symbol:
        q += " WHERE symbol=?"
        args.append(symbol)
    q += " ORDER BY updated_ms DESC"
    with _lock:
        rows = c.execute(q, args).fetchall()
    keys = ["id", "symbol", "timeframe", "direction", "state", "breakout_ts", "breakout_price",
            "vwap_at_breakout", "zone_low", "zone_high", "fvg_id", "elapsed_candles", "touch_ts",
            "rejection_ts", "confirmation_ts", "invalidation_ts", "updated_ms"]
    return [dict(zip(keys, r)) for r in rows]


# ============================================================
# SETUP CANDIDATES (STRUCTURED TRADE IDEAS)
# ============================================================

def save_setup_candidate(cand: dict) -> None:
    c = _auto_conn()
    import json as _j
    # Pack rich fields into entry_conditions
    entry_conds = dict(cand.get("entry_conditions") or {})
    for k in ["entry_price", "suggested_tp3", "sl_distance_pct", "tp1_distance_pct", "tp2_distance_pct", "tp3_distance_pct",
              "recommended_tp1_pct", "recommended_tp2_pct", "recommended_tp3_pct", "recommended_margin",
              "recommended_leverage", "recommended_quantity", "ai_confidence", "calibration_status",
              "empirical_success_probability", "risk_distance", "reward_distance_tp1", "reward_distance_tp2",
              "reward_distance_tp3", "reward_risk_ratio", "reward_risk_tp1", "reward_risk_tp2", "reward_risk_tp3",
              "reasons", "display_symbol", "venue_symbol", "setup_status",
              "waiting_for", "next_required_event", "distance_pct", "distance_atr", "priority",
              "priority_reasons", "conditions", "data_freshness", "actionability_score", "zone"]:
        if k in cand:
            entry_conds[k] = cand[k]

    # Phase 4 field extraction & calculation
    waiting_for = cand.get("waiting_for") or cand.get("reasons", {}).get("waiting_for", "")
    next_required_event = cand.get("next_required_event") or cand.get("reasons", {}).get("next_required_event", "")
    distance_pct = cand.get("distance_pct")
    distance_atr = cand.get("distance_atr")
    zone_dict = cand.get("zone") or {}
    zone_json = _j.dumps(zone_dict) if zone_dict else None
    structural_invalidation = cand.get("invalidation", {}).get("reason") or cand.get("structural_invalidation", "")
    conditions_list = cand.get("conditions") or []
    conditions_json = _j.dumps(conditions_list) if conditions_list else None
    data_freshness = cand.get("data_freshness") or {}
    data_freshness_json = _j.dumps(data_freshness) if data_freshness else None

    # Priority & Actionability score
    prio = cand.get("priority")
    prio_reasons = cand.get("priority_reasons") or []
    act_score = cand.get("actionability_score")
    if prio is None or act_score is None:
        try:
            from . import priority_classifier
            classified = priority_classifier.classify_trade_priority(cand, {})
            prio = classified.get("priority", "MEDIUM")
            prio_reasons = classified.get("priority_reasons", [])
            act_score = classified.get("actionability_score", 400.0)
        except Exception:
            prio = "MEDIUM"
            prio_reasons = []
            act_score = 400.0
    prio_reasons_json = _j.dumps(prio_reasons) if prio_reasons else None

    with _lock:
        c.execute(
            "INSERT OR REPLACE INTO setup_candidates(setup_id, symbol, direction, timeframe, "
            "strategy, current_state, reason, vwap, breakout_price, retest_state, cvd_confirmed, "
            "rvol_confirmed, fvg_confirmed, entry_conditions_json, confirmation_conditions_json, "
            "invalidation_json, suggested_sl, suggested_tp1, suggested_tp2, risk_reward, "
            "confidence_pct, thesis, generated_ms, expires_ms, status, "
            "waiting_for, next_required_event, distance_pct, distance_atr, priority, "
            "priority_reasons_json, conditions_json, data_freshness_json, actionability_score, "
            "zone_json, structural_invalidation) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (cand["setup_id"], cand["symbol"], cand["direction"], cand.get("timeframe", 3),
             cand.get("strategy", "VWAP_STRUCTURE_RETEST"), cand.get("current_state", "WAITING_FOR_RETEST"),
             cand.get("reason", ""), cand.get("vwap"), cand.get("breakout_price"),
             cand.get("retest_state", "WAITING"), int(bool(cand.get("cvd_confirmed"))),
             int(bool(cand.get("rvol_confirmed"))), int(bool(cand.get("fvg_confirmed"))),
             _j.dumps(entry_conds),
             _j.dumps(cand.get("confirmation_conditions") or {}),
             _j.dumps(cand.get("invalidation") or {}),
             cand.get("suggested_sl"), cand.get("suggested_tp1"), cand.get("suggested_tp2"),
             cand.get("risk_reward"), cand.get("confidence_pct", 70.0), cand.get("thesis", ""),
             cand.get("generated_ms", int(time.time() * 1000)), cand.get("expires_ms"),
             cand.get("status", "ACTIVE"),
             waiting_for, next_required_event, distance_pct, distance_atr, prio,
             prio_reasons_json, conditions_json, data_freshness_json, act_score,
             zone_json, structural_invalidation)
        )
        c.commit()



def validate_setup_geometry(setup: dict) -> tuple[bool, str]:
    """Strictly validates directional geometry invariants:
      - LONG:  SL < Entry < TP1 < TP2 < TP3 (for non-null targets)
      - SHORT: SL > Entry > TP1 > TP2 > TP3 (for non-null targets)
      - Strictly distinct levels (no duplicate TPs)
      - Minimum risk distance > 0
      - Minimum reward distance > 0
      - No forced TP3: setups with only TP1 or TP1+TP2 are valid
    """
    try:
        entry = float(setup.get("entry_price") or setup.get("breakout_price") or setup.get("entry") or 0.0)
        sl = float(setup.get("suggested_sl") or setup.get("sl") or 0.0)
        tp1 = float(setup.get("suggested_tp1") or setup.get("tp1") or 0.0)
        tp2_raw = setup.get("suggested_tp2") if setup.get("suggested_tp2") is not None else setup.get("tp2")
        tp3_raw = setup.get("suggested_tp3") if setup.get("suggested_tp3") is not None else setup.get("tp3")
        tp2 = float(tp2_raw) if tp2_raw not in (None, "", "UNAVAILABLE", 0, 0.0) else 0.0
        tp3 = float(tp3_raw) if tp3_raw not in (None, "", "UNAVAILABLE", 0, 0.0) else 0.0
    except (ValueError, TypeError):
        return False, "Invalid numeric values in setup geometry"

    direction = str(setup.get("direction", "LONG")).upper()

    if entry <= 0 or sl <= 0 or tp1 <= 0:
        return False, "Non-positive price detected"

    if direction == "LONG":
        if not (sl < entry):
            return False, f"LONG SL ({sl}) must be strictly below Entry ({entry})"
        if not (entry < tp1):
            return False, f"LONG TP1 ({tp1}) must be strictly above Entry ({entry})"
        if tp2 > 0 and not (tp1 < tp2):
            return False, f"LONG TP2 ({tp2}) must be strictly above TP1 ({tp1})"
        if tp3 > 0 and not (tp2 > 0 and tp2 < tp3):
            return False, f"LONG TP3 ({tp3}) requires valid TP2 and must be strictly above TP2"
    elif direction == "SHORT":
        if not (sl > entry):
            return False, f"SHORT SL ({sl}) must be strictly above Entry ({entry})"
        if not (entry > tp1):
            return False, f"SHORT TP1 ({tp1}) must be strictly below Entry ({entry})"
        if tp2 > 0 and not (tp1 > tp2):
            return False, f"SHORT TP2 ({tp2}) must be strictly below TP1 ({tp1})"
        if tp3 > 0 and not (tp2 > 0 and tp2 > tp3):
            return False, f"SHORT TP3 ({tp3}) requires valid TP2 and must be strictly below TP2"
    else:
        return False, f"Unknown direction {direction}"

    # Check for duplicate target prices
    tps = [p for p in [tp1, tp2, tp3] if p > 0]
    if len(tps) != len(set(tps)):
        return False, f"Duplicate TP targets detected: {tps}"

    return True, "VALID"


def compute_setup_snapshot_hash(setup: dict) -> str:
    import hashlib
    tp2_val = setup.get("suggested_tp2") if setup.get("suggested_tp2") is not None else setup.get("tp2")
    tp3_val = setup.get("suggested_tp3") if setup.get("suggested_tp3") is not None else setup.get("tp3")
    tp2_str = f"{float(tp2_val):.4f}" if tp2_val not in (None, "", "UNAVAILABLE", 0, 0.0) else "NONE"
    tp3_str = f"{float(tp3_val):.4f}" if tp3_val not in (None, "", "UNAVAILABLE", 0, 0.0) else "NONE"
    components = [
        str(setup.get("symbol")),
        str(setup.get("direction")),
        str(setup.get("timeframe") or setup.get("timeframe_label")),
        f"{float(setup.get('entry_price') or setup.get('breakout_price') or setup.get('entry') or 0.0):.4f}",
        f"{float(setup.get('suggested_sl') or setup.get('sl') or 0.0):.4f}",
        f"{float(setup.get('suggested_tp1') or setup.get('tp1') or 0.0):.4f}",
        tp2_str,
        tp3_str,
    ]
    return hashlib.sha256(":".join(components).encode("utf-8")).hexdigest()[:16]



def normalize_setup_fields(d: dict) -> dict:
    is_long = str(d.get("direction", "LONG")).upper() == "LONG"
    entry_px = float(d.get("entry_price") or d.get("breakout_price") or d.get("entry") or 0.0)
    sl = float(d.get("suggested_sl") or d.get("sl") or 0.0)
    tp1 = float(d.get("suggested_tp1") or d.get("tp1") or 0.0)

    tp2_raw = d.get("suggested_tp2") if d.get("suggested_tp2") is not None else d.get("tp2")
    tp3_raw = d.get("suggested_tp3") if d.get("suggested_tp3") is not None else d.get("tp3")

    tp2 = float(tp2_raw) if tp2_raw not in (None, "", "UNAVAILABLE", 0, 0.0) else None
    tp3 = float(tp3_raw) if tp3_raw not in (None, "", "UNAVAILABLE", 0, 0.0) else None

    if entry_px > 0 and sl > 0 and tp1 > 0:
        if is_long:
            risk_dist = max(entry_px - sl, entry_px * 0.001)
            rew1 = max(tp1 - entry_px, 0.0)
            sl_pct = -round((risk_dist / entry_px) * 100.0, 2)
            tp1_pct = round((rew1 / entry_px) * 100.0, 2)

            rew2 = max(tp2 - entry_px, 0.0) if tp2 is not None else None
            tp2_pct = round((rew2 / entry_px) * 100.0, 2) if rew2 is not None else None

            rew3 = max(tp3 - entry_px, 0.0) if tp3 is not None else None
            tp3_pct = round((rew3 / entry_px) * 100.0, 2) if rew3 is not None else None
        else:
            risk_dist = max(sl - entry_px, entry_px * 0.001)
            rew1 = max(entry_px - tp1, 0.0)
            sl_pct = round((risk_dist / entry_px) * 100.0, 2)
            tp1_pct = -round((rew1 / entry_px) * 100.0, 2)

            rew2 = max(entry_px - tp2, 0.0) if tp2 is not None else None
            tp2_pct = -round((rew2 / entry_px) * 100.0, 2) if rew2 is not None else None

            rew3 = max(entry_px - tp3, 0.0) if tp3 is not None else None
            tp3_pct = -round((rew3 / entry_px) * 100.0, 2) if rew3 is not None else None

        rr1 = round(rew1 / max(risk_dist, 1e-6), 2)
        rr2 = round(rew2 / max(risk_dist, 1e-6), 2) if rew2 is not None else None
        rr3 = round(rew3 / max(risk_dist, 1e-6), 2) if rew3 is not None else None

        d["suggested_tp1"] = round(tp1, 4)
        d["suggested_tp2"] = round(tp2, 4) if tp2 is not None else None
        d["suggested_tp3"] = round(tp3, 4) if tp3 is not None else None
        d["tp2_status"] = "AVAILABLE" if tp2 is not None else "UNAVAILABLE"
        d["tp3_status"] = "AVAILABLE" if tp3 is not None else "UNAVAILABLE"

        d["risk_distance"] = round(risk_dist, 4)
        d["reward_distance_tp1"] = round(rew1, 4)
        d["reward_distance_tp2"] = round(rew2, 4) if rew2 is not None else None
        d["reward_distance_tp3"] = round(rew3, 4) if rew3 is not None else None

        d["reward_risk_ratio"] = rr1
        d["reward_risk_tp1"] = rr1
        d["reward_risk_tp2"] = rr2
        d["reward_risk_tp3"] = rr3
        d["risk_reward"] = rr1

        d["sl_distance_pct"] = sl_pct
        d["tp1_distance_pct"] = tp1_pct
        d["tp2_distance_pct"] = tp2_pct
        d["tp3_distance_pct"] = tp3_pct

        d["risk_pct"] = round((risk_dist / entry_px) * 100.0, 2)
        d["reward_pct_tp1"] = round((rew1 / entry_px) * 100.0, 2)
        d["reward_pct_tp2"] = round((rew2 / entry_px) * 100.0, 2) if rew2 is not None else None
        d["reward_pct_tp3"] = round((rew3 / entry_px) * 100.0, 2) if rew3 is not None else None

    is_valid, val_reason = validate_setup_geometry(d)
    d["is_geometry_valid"] = is_valid
    d["geometry_validation_error"] = val_reason if not is_valid else None
    d["snapshot_hash"] = compute_setup_snapshot_hash(d)
    d["calibration_status"] = "NOT CALIBRATED"
    d["empirical_success_probability"] = None
    d.setdefault("ai_confidence", d.get("confidence_pct", 65.0))
    sym = d.get("symbol") or "BTC-USDT"
    d.setdefault("symbol", sym)
    d.setdefault("display_symbol", config.to_display_symbol(sym))
    d.setdefault("venue_symbol", config.to_venue_symbol(sym))
    return d


def list_setup_candidates(status: str = "ACTIVE", symbol: str | None = None, timeframe: int | None = None, limit: int = 50) -> list[dict]:
    c = _auto_conn()
    import json as _j
    q = ("SELECT setup_id, symbol, direction, timeframe, strategy, current_state, reason, "
         "vwap, breakout_price, retest_state, cvd_confirmed, rvol_confirmed, fvg_confirmed, "
         "entry_conditions_json, confirmation_conditions_json, invalidation_json, suggested_sl, "
         "suggested_tp1, suggested_tp2, risk_reward, confidence_pct, thesis, generated_ms, "
         "expires_ms, status, waiting_for, next_required_event, distance_pct, distance_atr, "
         "priority, priority_reasons_json, conditions_json, data_freshness_json, actionability_score, "
         "zone_json, structural_invalidation FROM setup_candidates WHERE status=?")
    args: list = [status]
    if symbol and symbol.strip().upper() != "ALL":
        s_clean = symbol.strip()
        if "GOLD" in s_clean.upper() or s_clean == "NCCOGOLD2USD-USDT":
            q += " AND (symbol LIKE '%GOLD%' OR symbol = 'NCCOGOLD2USD-USDT')"
        else:
            disp = config.to_display_symbol(s_clean)
            venue = config.to_venue_symbol(s_clean)
            q += " AND (symbol = ? OR symbol = ?)"
            args.extend([disp, venue])
    if timeframe and int(timeframe) > 0:
        q += " AND timeframe = ?"
        args.append(int(timeframe))
    q += f" ORDER BY actionability_score DESC, generated_ms DESC LIMIT {max(1, int(limit))}"
    with _lock:
        rows = c.execute(q, args).fetchall()
    keys = ["setup_id", "symbol", "direction", "timeframe", "strategy", "current_state", "reason",
            "vwap", "breakout_price", "retest_state", "cvd_confirmed", "rvol_confirmed", "fvg_confirmed",
            "entry_conditions_json", "confirmation_conditions_json", "invalidation_json", "suggested_sl",
            "suggested_tp1", "suggested_tp2", "risk_reward", "confidence_pct", "thesis", "generated_ms",
            "expires_ms", "status", "waiting_for", "next_required_event", "distance_pct", "distance_atr",
            "priority", "priority_reasons_json", "conditions_json", "data_freshness_json", "actionability_score",
            "zone_json", "structural_invalidation"]
    res = []
    seen_keys = set()
    for r in rows:
        d = dict(zip(keys, r))
        d["candidate_id"] = d["setup_id"]
        d["cvd_confirmed"] = bool(d["cvd_confirmed"])
        d["rvol_confirmed"] = bool(d["rvol_confirmed"])
        d["fvg_confirmed"] = bool(d["fvg_confirmed"])
        entry_conds = _j.loads(d.pop("entry_conditions_json") or "{}")
        d["entry_conditions"] = entry_conds
        d["confirmation_conditions"] = _j.loads(d.pop("confirmation_conditions_json") or "{}")
        d["invalidation"] = _j.loads(d.pop("invalidation_json") or "{}")
        d["priority_reasons"] = _j.loads(d.pop("priority_reasons_json") or "[]")
        d["conditions"] = _j.loads(d.pop("conditions_json") or "[]")
        d["data_freshness"] = _j.loads(d.pop("data_freshness_json") or "{}")
        d["zone"] = _j.loads(d.pop("zone_json") or "{}")
        
        # Unpack rich fields
        for k in ["suggested_tp3", "sl_distance_pct", "tp1_distance_pct", "tp2_distance_pct", "tp3_distance_pct",
                  "recommended_tp1_pct", "recommended_tp2_pct", "recommended_tp3_pct", "recommended_margin",
                  "recommended_leverage", "recommended_quantity", "ai_confidence", "calibration_status",
                  "empirical_success_probability", "risk_distance", "reward_distance_tp1", "reward_distance_tp2",
                  "reward_distance_tp3", "reward_risk_ratio", "reward_risk_tp1", "reward_risk_tp2", "reward_risk_tp3",
                  "reasons", "display_symbol", "venue_symbol", "setup_status", "entry_price",
                  "risk_pct", "reward_pct_tp1", "reward_pct_tp2", "reward_pct_tp3", "target_provenance"]:
            if k in entry_conds and k not in d:
                d[k] = entry_conds[k]

        # Fill defaults if new columns were null for legacy rows
        if not d.get("waiting_for"):
            d["waiting_for"] = d.get("reasons", {}).get("waiting_for", "Scanning for retest touch")
        if not d.get("next_required_event"):
            d["next_required_event"] = d.get("reasons", {}).get("next_required_event", "RETEST_ZONE_TOUCH")
        if not d.get("priority"):
            d["priority"] = "MEDIUM"

        d = normalize_setup_fields(d)
        
        # Deduplicate active candidates: strictly 1 per symbol/direction/timeframe
        dedup_key = (d["symbol"], d["direction"], d.get("timeframe", 3))
        if dedup_key not in seen_keys:
            seen_keys.add(dedup_key)
            res.append(d)
            
    return res


def get_setup_candidate(setup_id: str) -> dict | None:
    c = _auto_conn()
    import json as _j
    with _lock:
        row = c.execute(
            "SELECT setup_id, symbol, direction, timeframe, strategy, current_state, reason, "
            "vwap, breakout_price, retest_state, cvd_confirmed, rvol_confirmed, fvg_confirmed, "
            "entry_conditions_json, confirmation_conditions_json, invalidation_json, suggested_sl, "
            "suggested_tp1, suggested_tp2, risk_reward, confidence_pct, thesis, generated_ms, "
            "expires_ms, status, waiting_for, next_required_event, distance_pct, distance_atr, "
            "priority, priority_reasons_json, conditions_json, data_freshness_json, actionability_score, "
            "zone_json, structural_invalidation FROM setup_candidates WHERE setup_id=?",
            (setup_id,)
        ).fetchone()
    if not row:
        return None
    keys = ["setup_id", "symbol", "direction", "timeframe", "strategy", "current_state", "reason",
            "vwap", "breakout_price", "retest_state", "cvd_confirmed", "rvol_confirmed", "fvg_confirmed",
            "entry_conditions_json", "confirmation_conditions_json", "invalidation_json", "suggested_sl",
            "suggested_tp1", "suggested_tp2", "risk_reward", "confidence_pct", "thesis", "generated_ms",
            "expires_ms", "status", "waiting_for", "next_required_event", "distance_pct", "distance_atr",
            "priority", "priority_reasons_json", "conditions_json", "data_freshness_json", "actionability_score",
            "zone_json", "structural_invalidation"]
    d = dict(zip(keys, row))
    d["candidate_id"] = d["setup_id"]
    d["cvd_confirmed"] = bool(d["cvd_confirmed"])
    d["rvol_confirmed"] = bool(d["rvol_confirmed"])
    d["fvg_confirmed"] = bool(d["fvg_confirmed"])
    entry_conds = _j.loads(d.pop("entry_conditions_json") or "{}")
    d["entry_conditions"] = entry_conds
    d["confirmation_conditions"] = _j.loads(d.pop("confirmation_conditions_json") or "{}")
    d["invalidation"] = _j.loads(d.pop("invalidation_json") or "{}")
    d["priority_reasons"] = _j.loads(d.pop("priority_reasons_json") or "[]")
    d["conditions"] = _j.loads(d.pop("conditions_json") or "[]")
    d["data_freshness"] = _j.loads(d.pop("data_freshness_json") or "{}")
    d["zone"] = _j.loads(d.pop("zone_json") or "{}")
    for k in ["suggested_tp3", "sl_distance_pct", "tp1_distance_pct", "tp2_distance_pct", "tp3_distance_pct",
              "recommended_tp1_pct", "recommended_tp2_pct", "recommended_tp3_pct", "recommended_margin",
              "recommended_leverage", "recommended_quantity", "ai_confidence", "calibration_status",
              "empirical_success_probability", "risk_distance", "reward_distance_tp1", "reward_distance_tp2",
              "reward_distance_tp3", "reward_risk_ratio", "reward_risk_tp1", "reward_risk_tp2", "reward_risk_tp3",
              "reasons", "display_symbol", "venue_symbol", "setup_status", "entry_price",
              "risk_pct", "reward_pct_tp1", "reward_pct_tp2", "reward_pct_tp3", "target_provenance"]:
        if k in entry_conds and k not in d:
            d[k] = entry_conds[k]

    if not d.get("waiting_for"):
        d["waiting_for"] = d.get("reasons", {}).get("waiting_for", "Scanning for retest touch")
    if not d.get("next_required_event"):
        d["next_required_event"] = d.get("reasons", {}).get("next_required_event", "RETEST_ZONE_TOUCH")
    if not d.get("priority"):
        d["priority"] = "MEDIUM"

    return normalize_setup_fields(d)



# ============================================================
# ML ANALYSES AUDIT & TIMELINE
# ============================================================

def save_ml_analysis(item: dict) -> None:
    c = _auto_conn()
    import json as _j
    with _lock:
        c.execute(
            "INSERT OR REPLACE INTO ml_analyses(analysis_id, symbol, analysis_type, model, "
            "model_version, timestamp_ms, data_cutoff_ms, thesis, opportunities_json, "
            "risks_json, confidence_pct, latency_ms, error_status) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (item["analysis_id"], item["symbol"], item.get("analysis_type", "SETUP_SCAN"),
             item.get("model", "qwen3:4b"), item.get("model_version", "1.0"),
             item.get("timestamp_ms", int(time.time() * 1000)), item.get("data_cutoff_ms"),
             item.get("thesis", ""), _j.dumps(item.get("opportunities") or []),
             _j.dumps(item.get("risks") or []), item.get("confidence_pct", 70.0),
             item.get("latency_ms", 0), item.get("error_status"))
        )
        c.commit()


def list_ml_analyses(symbol: str | None = None, limit: int = 20) -> list[dict]:
    c = _auto_conn()
    import json as _j
    q = ("SELECT analysis_id, symbol, analysis_type, model, model_version, timestamp_ms, "
         "data_cutoff_ms, thesis, opportunities_json, risks_json, confidence_pct, latency_ms, "
         "error_status FROM ml_analyses")
    args = []
    if symbol:
        q += " WHERE symbol=?"
        args.append(symbol)
    q += " ORDER BY timestamp_ms DESC LIMIT ?"
    args.append(limit)
    with _lock:
        rows = c.execute(q, args).fetchall()
    keys = ["analysis_id", "symbol", "analysis_type", "model", "model_version", "timestamp_ms",
            "data_cutoff_ms", "thesis", "opportunities_json", "risks_json", "confidence_pct",
            "latency_ms", "error_status"]
    res = []
    for r in rows:
        d = dict(zip(keys, r))
        d["opportunities"] = _j.loads(d.pop("opportunities_json") or "[]")
        d["risks"] = _j.loads(d.pop("risks_json") or "[]")
        res.append(d)
    return res


# ============================================================
# NEWS & MACRO EVENTS PERSISTENCE
# ============================================================

def save_news_article(item: dict) -> None:
    c = _auto_conn()
    import json as _j
    with _lock:
        c.execute(
            "INSERT OR IGNORE INTO news_articles(id, source, timestamp_ms, title, url, "
            "category, relevance, sentiment, importance, dedupe_key, market_reaction_json, "
            "model, analysis_ts_ms) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (item["id"], item["source"], item["timestamp_ms"], item["title"],
             item.get("url", ""), item.get("category", "MARKETS"), item.get("relevance", 1.0),
             item.get("sentiment", "NEUTRAL"), item.get("importance", "NORMAL"),
             item["dedupe_key"], _j.dumps(item.get("market_reaction") or {}),
             item.get("model", "qwen3:4b"), item.get("analysis_ts_ms", int(time.time() * 1000)))
        )
        c.commit()


def list_news_articles(limit: int = 50, category: str | None = None) -> list[dict]:
    c = _auto_conn()
    import json as _j
    q = ("SELECT id, source, timestamp_ms, title, url, category, relevance, sentiment, "
         "importance, dedupe_key, market_reaction_json, model, analysis_ts_ms "
         "FROM news_articles")
    args = []
    if category and category != "ALL":
        q += " WHERE category=?"
        args.append(category)
    q += " ORDER BY timestamp_ms DESC LIMIT ?"
    args.append(limit)
    with _lock:
        rows = c.execute(q, args).fetchall()
    keys = ["id", "source", "timestamp_ms", "title", "url", "category", "relevance", "sentiment",
            "importance", "dedupe_key", "market_reaction_json", "model", "analysis_ts_ms"]
    res = []
    for r in rows:
        d = dict(zip(keys, r))
        d["market_reaction"] = _j.loads(d.pop("market_reaction_json") or "{}")
        res.append(d)
    return res


# ============================================================
# TWO-APP USER & COPY TRADING PERSISTENCE
# ============================================================

_USER_KEYS = [
    "id", "user_uid", "role", "google_subject", "email", "display_name", "status",
    "copy_enabled", "admin_copy_allowed", "suspended", "bingx_connection_status",
    "bingx_account_identifier", "created_at", "last_login", "last_heartbeat",
    "last_bingx_sync", "app_version", "last_execution_status", "last_error"
]


def _row_to_user(r: tuple) -> dict:
    d = dict(zip(_USER_KEYS, r))
    d["copy_enabled"] = bool(d.get("copy_enabled"))
    d["admin_copy_allowed"] = bool(d.get("admin_copy_allowed"))
    d["suspended"] = bool(d.get("suspended"))
    uid_int = d.get("id") or 0
    d["ophelia_user_id"] = f"USR-{uid_int:04d}"
    if not d.get("user_uid"):
        d["user_uid"] = d["ophelia_user_id"]
    return d


def get_user_by_id(user_id: int) -> dict | None:
    c = _connect()
    cols = ", ".join(_USER_KEYS)
    with _lock:
        r = c.execute(f"SELECT {cols} FROM users WHERE id=?", (user_id,)).fetchone()
    return _row_to_user(r) if r else None


def get_user_by_google_sub(google_sub: str) -> dict | None:
    c = _connect()
    cols = ", ".join(_USER_KEYS)
    with _lock:
        r = c.execute(f"SELECT {cols} FROM users WHERE google_subject=?", (google_sub,)).fetchone()
    return _row_to_user(r) if r else None


def get_user_by_uid(uid: str) -> dict | None:
    c = _connect()
    cols = ", ".join(_USER_KEYS)
    with _lock:
        r = c.execute(f"SELECT {cols} FROM users WHERE user_uid=?", (uid,)).fetchone()
    return _row_to_user(r) if r else None


def create_google_user(google_sub: str, email: str, display_name: str, app_version: str = "") -> dict:
    c = _connect()
    import uuid as _uuid
    now_ms = int(time.time() * 1000)
    user_uid = f"u_{now_ms}_{_uuid.uuid4().hex[:6]}"
    with _lock:
        existing = c.execute("SELECT id FROM users WHERE google_subject=?", (google_sub,)).fetchone()
        if existing:
            c.execute("UPDATE users SET email=?, display_name=?, app_version=?, last_login=? WHERE id=?",
                      (email, display_name, app_version, now_ms, existing[0]))
            c.commit()
            return get_user_by_id(existing[0])
        existing_email = c.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if existing_email:
            c.execute("UPDATE users SET google_subject=?, display_name=?, app_version=?, last_login=? WHERE id=?",
                      (google_sub, display_name, app_version, now_ms, existing_email[0]))
            c.commit()
            return get_user_by_id(existing_email[0])

        cur = c.execute(
            "INSERT INTO users(user_uid, role, google_subject, email, display_name, status, "
            "copy_enabled, admin_copy_allowed, suspended, bingx_connection_status, created_at, "
            "last_login, last_heartbeat, app_version) "
            "VALUES(?, 'USER', ?, ?, ?, 'ACTIVE', 1, 1, 0, 'DISCONNECTED', ?, ?, ?, ?)",
            (user_uid, google_sub, email, display_name, now_ms, now_ms, now_ms, app_version)
        )
        c.commit()
        user_id = int(cur.lastrowid or 0)
    return get_user_by_id(user_id) or {"id": user_id, "user_uid": user_uid, "role": "USER", "email": email}


def list_all_users(role: str | None = None) -> list[dict]:
    c = _connect()
    cols = ", ".join(_USER_KEYS)
    q = f"SELECT {cols} FROM users"
    args = []
    if role:
        q += " WHERE role=?"
        args.append(role)
    q += " ORDER BY id ASC"
    with _lock:
        rows = c.execute(q, args).fetchall()
    return [_row_to_user(r) for r in rows]


def update_user_copy_enabled(user_id: int, enabled: bool) -> bool:
    c = _connect()
    with _lock:
        cur = c.execute("UPDATE users SET copy_enabled=? WHERE id=?", (1 if enabled else 0, user_id))
        c.commit()
    return cur.rowcount > 0


def update_admin_copy_allowed(user_id: int, allowed: bool) -> bool:
    c = _connect()
    with _lock:
        cur = c.execute("UPDATE users SET admin_copy_allowed=? WHERE id=?", (1 if allowed else 0, user_id))
        c.commit()
    return cur.rowcount > 0


def update_user_suspended(user_id: int, suspended: bool) -> bool:
    c = _connect()
    status_val = "SUSPENDED" if suspended else "ACTIVE"
    with _lock:
        cur = c.execute("UPDATE users SET suspended=?, status=? WHERE id=?", (1 if suspended else 0, status_val, user_id))
        c.commit()
    return cur.rowcount > 0


def update_user_bingx_status(user_id: int, status: str, account_id: str | None = None, err: str | None = None) -> bool:
    c = _connect()
    now_ms = int(time.time() * 1000)
    with _lock:
        cur = c.execute(
            "UPDATE users SET bingx_connection_status=?, "
            "bingx_account_identifier=COALESCE(?, bingx_account_identifier), "
            "last_error=?, last_bingx_sync=? WHERE id=?",
            (status, account_id, err, now_ms, user_id)
        )
        c.commit()
    return cur.rowcount > 0


def update_user_heartbeat(user_id: int, app_version: str = "") -> None:
    c = _connect()
    now_ms = int(time.time() * 1000)
    with _lock:
        if app_version:
            c.execute("UPDATE users SET last_heartbeat=?, app_version=? WHERE id=?", (now_ms, app_version, user_id))
        else:
            c.execute("UPDATE users SET last_heartbeat=? WHERE id=?", (now_ms, user_id))
        c.commit()


# ------------------------------------------------------------ Credentials
def store_user_bingx_credentials(user_id: int, api_key_enc: str, api_secret_enc: str,
                                 key_identifier: str, permissions: list[str],
                                 has_withdrawal: bool = False, is_valid: bool = True) -> None:
    c = _connect()
    import json as _j
    now_ms = int(time.time() * 1000)
    with _lock:
        c.execute(
            "INSERT OR REPLACE INTO user_bingx_credentials(user_id, api_key_enc, api_secret_enc, "
            "key_identifier, permissions_json, has_withdrawal, is_valid, last_verified_ms, updated_ms) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (user_id, api_key_enc, api_secret_enc, key_identifier, _j.dumps(permissions),
             1 if has_withdrawal else 0, 1 if is_valid else 0, now_ms, now_ms)
        )
        c.commit()


def get_user_bingx_credentials(user_id: int) -> dict | None:
    c = _connect()
    import json as _j
    with _lock:
        r = c.execute(
            "SELECT user_id, api_key_enc, api_secret_enc, key_identifier, permissions_json, "
            "has_withdrawal, is_valid, last_verified_ms, last_error, updated_ms "
            "FROM user_bingx_credentials WHERE user_id=?",
            (user_id,)
        ).fetchone()
    if not r:
        return None
    keys = ["user_id", "api_key_enc", "api_secret_enc", "key_identifier", "permissions_json",
            "has_withdrawal", "is_valid", "last_verified_ms", "last_error", "updated_ms"]
    d = dict(zip(keys, r))
    d["permissions"] = _j.loads(d.pop("permissions_json") or "[]")
    d["has_withdrawal"] = bool(d["has_withdrawal"])
    d["is_valid"] = bool(d["is_valid"])
    return d


def delete_user_bingx_credentials(user_id: int) -> bool:
    c = _connect()
    with _lock:
        cur = c.execute("DELETE FROM user_bingx_credentials WHERE user_id=?", (user_id,))
        c.execute("UPDATE users SET bingx_connection_status='DISCONNECTED', bingx_account_identifier=NULL WHERE id=?", (user_id,))
        c.commit()
    return cur.rowcount > 0


# ------------------------------------------------------------ Master Trades
_MASTER_TRADE_KEYS = [
    "master_trade_id", "admin_user_id", "automation_id", "strategy", "symbol",
    "direction", "entry_reference_price", "leverage", "sl_price", "tp1_price",
    "tp2_price", "tp3_price", "tp1_qty_pct", "tp2_qty_pct", "tp3_qty_pct",
    "trailing", "breakeven", "allocation_mode", "allocation_value",
    "admin_balance_snapshot", "admin_equity_snapshot", "admin_margin_selected",
    "ml_snapshot_hash", "trigger_ts", "expiration", "status"
]


def save_master_trade(mt: dict) -> None:
    c = _connect()
    cols = ", ".join(_MASTER_TRADE_KEYS)
    placeholders = ", ".join(["?"] * len(_MASTER_TRADE_KEYS))
    vals = [
        mt["master_trade_id"],
        mt.get("admin_user_id", 1),
        mt.get("automation_id"),
        mt.get("strategy", "OPHELIA_MASTER"),
        mt["symbol"],
        mt["direction"],
        float(mt.get("entry_reference_price") or mt.get("entry_price") or 0.0),
        float(mt.get("leverage", 10.0)),
        float(mt.get("sl_price") or 0.0),
        float(mt["tp1_price"]) if mt.get("tp1_price") is not None else None,
        float(mt["tp2_price"]) if mt.get("tp2_price") is not None else None,
        float(mt["tp3_price"]) if mt.get("tp3_price") is not None else None,
        float(mt.get("tp1_qty_pct", 50.0)),
        float(mt.get("tp2_qty_pct", 30.0)),
        float(mt.get("tp3_qty_pct", 20.0)),
        1 if mt.get("trailing") else 0,
        1 if mt.get("breakeven") else 0,
        mt.get("allocation_mode", "PROPORTIONAL_RATIO"),
        float(mt.get("allocation_value", 100.0)),
        float(mt.get("admin_balance_snapshot", 0.0)),
        float(mt.get("admin_equity_snapshot", 0.0)),
        float(mt.get("admin_margin_selected", 0.0)),
        mt.get("ml_snapshot_hash"),
        int(mt.get("trigger_ts", int(time.time() * 1000))),
        int(mt["expiration"]) if mt.get("expiration") else None,
        mt.get("status", "ACTIVE")
    ]
    with _lock:
        c.execute(f"INSERT OR REPLACE INTO master_trades({cols}) VALUES({placeholders})", vals)
        c.commit()


def get_master_trade(master_trade_id: str) -> dict | None:
    c = _connect()
    cols = ", ".join(_MASTER_TRADE_KEYS)
    with _lock:
        r = c.execute(f"SELECT {cols} FROM master_trades WHERE master_trade_id=?", (master_trade_id,)).fetchone()
    if not r:
        return None
    d = dict(zip(_MASTER_TRADE_KEYS, r))
    d["trailing"] = bool(d["trailing"])
    d["breakeven"] = bool(d["breakeven"])
    return d


def list_master_trades(limit: int = 50) -> list[dict]:
    c = _connect()
    cols = ", ".join(_MASTER_TRADE_KEYS)
    with _lock:
        rows = c.execute(f"SELECT {cols} FROM master_trades ORDER BY trigger_ts DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(zip(_MASTER_TRADE_KEYS, r))
        d["trailing"] = bool(d["trailing"])
        d["breakeven"] = bool(d["breakeven"])
        out.append(d)
    return out


# ------------------------------------------------------------ Master Trade Events
def save_master_trade_event(event: dict) -> None:
    c = _connect()
    import json as _j
    with _lock:
        c.execute(
            "INSERT INTO master_trade_events(master_trade_id, master_event_id, event_type, "
            "sequence_number, correlation_id, payload_json, timestamp_ms) "
            "VALUES(?,?,?,?,?,?,?)",
            (event["master_trade_id"], event["master_event_id"], event["event_type"],
             event["sequence_number"], event["correlation_id"],
             _j.dumps(event.get("payload") or {}),
             event.get("timestamp_ms", int(time.time() * 1000)))
        )
        c.commit()


def get_master_trade_events(master_trade_id: str) -> list[dict]:
    c = _connect()
    import json as _j
    with _lock:
        rows = c.execute(
            "SELECT id, master_trade_id, master_event_id, event_type, sequence_number, "
            "correlation_id, payload_json, timestamp_ms "
            "FROM master_trade_events WHERE master_trade_id=? ORDER BY sequence_number ASC",
            (master_trade_id,)
        ).fetchall()
    keys = ["id", "master_trade_id", "master_event_id", "event_type", "sequence_number",
            "correlation_id", "payload_json", "timestamp_ms"]
    res = []
    for r in rows:
        d = dict(zip(keys, r))
        d["payload"] = _j.loads(d.pop("payload_json") or "{}")
        res.append(d)
    return res


# ------------------------------------------------------------ Copy Executions
_COPY_EXEC_KEYS = [
    "copy_execution_id", "master_trade_id", "user_id", "correlation_id",
    "idempotency_key", "status", "blocked_reason", "allocated_margin",
    "calculated_quantity", "executed_quantity", "executed_price",
    "client_order_id", "exchange_order_id", "execution_latency_ms",
    "created_ms", "updated_ms"
]


def save_copy_execution(item: dict) -> None:
    c = _connect()
    cols = ", ".join(_COPY_EXEC_KEYS)
    placeholders = ", ".join(["?"] * len(_COPY_EXEC_KEYS))
    now_ms = int(time.time() * 1000)
    vals = [
        item["copy_execution_id"],
        item["master_trade_id"],
        item["user_id"],
        item["correlation_id"],
        item["idempotency_key"],
        item["status"],
        item.get("blocked_reason"),
        item.get("allocated_margin"),
        item.get("calculated_quantity"),
        item.get("executed_quantity"),
        item.get("executed_price"),
        item.get("client_order_id"),
        item.get("exchange_order_id"),
        item.get("execution_latency_ms"),
        item.get("created_ms", now_ms),
        item.get("updated_ms", now_ms),
    ]
    with _lock:
        c.execute(f"INSERT OR REPLACE INTO copy_executions({cols}) VALUES({placeholders})", vals)
        c.commit()


def update_copy_execution(copy_execution_id: str, updates: dict) -> None:
    c = _connect()
    updates["updated_ms"] = int(time.time() * 1000)
    set_clauses = [f"{k}=?" for k in updates.keys()]
    vals = list(updates.values()) + [copy_execution_id]
    with _lock:
        c.execute(f"UPDATE copy_executions SET {', '.join(set_clauses)} WHERE copy_execution_id=?", vals)
        c.commit()


def get_copy_execution(copy_execution_id: str) -> dict | None:
    c = _connect()
    cols = ", ".join(_COPY_EXEC_KEYS)
    with _lock:
        r = c.execute(f"SELECT {cols} FROM copy_executions WHERE copy_execution_id=?", (copy_execution_id,)).fetchone()
    return dict(zip(_COPY_EXEC_KEYS, r)) if r else None


def list_copy_executions(master_trade_id: str | None = None, user_id: int | None = None) -> list[dict]:
    c = _connect()
    cols = ", ".join(_COPY_EXEC_KEYS)
    q = f"SELECT {cols} FROM copy_executions"
    conds = []
    args = []
    if master_trade_id:
        conds.append("master_trade_id=?")
        args.append(master_trade_id)
    if user_id:
        conds.append("user_id=?")
        args.append(user_id)
    if conds:
        q += " WHERE " + " AND ".join(conds)
    q += " ORDER BY created_ms DESC"
    with _lock:
        rows = c.execute(q, args).fetchall()
    return [dict(zip(_COPY_EXEC_KEYS, r)) for r in rows]


# ------------------------------------------------------------ User Positions
_USER_POS_KEYS = [
    "id", "user_id", "symbol", "direction", "quantity", "entry_price",
    "leverage", "margin", "sl_price", "tp1_price", "tp2_price", "tp3_price",
    "trailing", "breakeven", "master_trade_id", "copy_execution_id",
    "status", "unrealized_pnl", "realized_pnl", "created_ms", "updated_ms"
]


def save_user_position(pos: dict) -> int:
    c = _connect()
    now_ms = int(time.time() * 1000)
    with _lock:
        cur = c.execute(
            "INSERT INTO user_positions(user_id, symbol, direction, quantity, entry_price, "
            "leverage, margin, sl_price, tp1_price, tp2_price, tp3_price, trailing, breakeven, "
            "master_trade_id, copy_execution_id, status, unrealized_pnl, realized_pnl, created_ms, updated_ms) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (pos["user_id"], pos["symbol"], pos["direction"], float(pos["quantity"]),
             float(pos["entry_price"]), float(pos.get("leverage", 10.0)), float(pos.get("margin", 0.0)),
             float(pos["sl_price"]) if pos.get("sl_price") is not None else None,
             float(pos["tp1_price"]) if pos.get("tp1_price") is not None else None,
             float(pos["tp2_price"]) if pos.get("tp2_price") is not None else None,
             float(pos["tp3_price"]) if pos.get("tp3_price") is not None else None,
             1 if pos.get("trailing") else 0, 1 if pos.get("breakeven") else 0,
             pos.get("master_trade_id"), pos.get("copy_execution_id"),
             pos.get("status", "OPEN"), float(pos.get("unrealized_pnl", 0.0)),
             float(pos.get("realized_pnl", 0.0)), pos.get("created_ms", now_ms), now_ms)
        )
        c.commit()
        return int(cur.lastrowid or 0)


def get_open_user_positions(user_id: int | None = None) -> list[dict]:
    c = _connect()
    cols = ", ".join(_USER_POS_KEYS)
    q = f"SELECT {cols} FROM user_positions WHERE status='OPEN'"
    args = []
    if user_id is not None:
        q += " AND user_id=?"
        args.append(user_id)
    with _lock:
        rows = c.execute(q, args).fetchall()
    out = []
    for r in rows:
        d = dict(zip(_USER_POS_KEYS, r))
        d["trailing"] = bool(d["trailing"])
        d["breakeven"] = bool(d["breakeven"])
        out.append(d)
    return out


def update_user_position(pos_id: int, updates: dict) -> bool:
    c = _connect()
    updates["updated_ms"] = int(time.time() * 1000)
    set_clauses = [f"{k}=?" for k in updates.keys()]
    vals = list(updates.values()) + [pos_id]
    with _lock:
        cur = c.execute(f"UPDATE user_positions SET {', '.join(set_clauses)} WHERE id=?", vals)
        c.commit()
    return cur.rowcount > 0


def close_user_position_db(user_id: int, symbol: str, exit_price: float, pnl: float) -> bool:
    c = _connect()
    now_ms = int(time.time() * 1000)
    with _lock:
        row = c.execute("SELECT copy_execution_id FROM user_positions WHERE user_id=? AND symbol=? AND status='OPEN'", (user_id, symbol)).fetchone()
        cur = c.execute(
            "UPDATE user_positions SET status='CLOSED', realized_pnl=?, updated_ms=? "
            "WHERE user_id=? AND symbol=? AND status='OPEN'",
            (pnl, now_ms, user_id, symbol)
        )
        c.commit()
    if row and row[0]:
        release_slot_by_position(str(row[0]))
    return cur.rowcount > 0


# ------------------------------------------------------------ Reconciliation Events
def record_reconciliation_event(event: dict) -> None:
    c = _connect()
    import json as _j
    now_ms = int(time.time() * 1000)
    with _lock:
        c.execute(
            "INSERT INTO reconciliation_events(user_id, symbol, status, exchange_state_json, "
            "local_state_json, discrepancy_reason, timestamp_ms) "
            "VALUES(?,?,?,?,?,?,?)",
            (event["user_id"], event["symbol"], event["status"],
             _j.dumps(event.get("exchange_state") or {}),
             _j.dumps(event.get("local_state") or {}),
             event.get("discrepancy_reason"),
             event.get("timestamp_ms", now_ms))
        )
        c.commit()


def list_reconciliation_events(user_id: int | None = None, limit: int = 50) -> list[dict]:
    c = _connect()
    import json as _j
    q = "SELECT id, user_id, symbol, status, exchange_state_json, local_state_json, discrepancy_reason, timestamp_ms FROM reconciliation_events"
    args = []
    if user_id is not None:
        q += " WHERE user_id=?"
        args.append(user_id)
    q += " ORDER BY timestamp_ms DESC LIMIT ?"
    args.append(limit)
    with _lock:
        rows = c.execute(q, args).fetchall()
    keys = ["id", "user_id", "symbol", "status", "exchange_state_json", "local_state_json", "discrepancy_reason", "timestamp_ms"]
    res = []
    for r in rows:
        d = dict(zip(keys, r))
        d["exchange_state"] = _j.loads(d.pop("exchange_state_json") or "{}")
        d["local_state"] = _j.loads(d.pop("local_state_json") or "{}")
        res.append(d)
    return res


# ============================================================
# GLOBAL AUTONOMOUS TRADE SLOTS & US MARKET INITIALIZATION
# ============================================================
def _init_us_market_and_slot_tables(conn: sqlite3.Connection) -> None:
    """Initialize global autonomous trade slots, US Top 100 universe, stock intelligence, sectors, news, and TradFi registry."""
    conn.execute("""CREATE TABLE IF NOT EXISTS autonomous_trade_slots(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        enabled INTEGER DEFAULT 1,
        allocated_margin_usdt REAL NOT NULL,
        max_leverage REAL NOT NULL DEFAULT 5.0,
        status TEXT NOT NULL DEFAULT 'AVAILABLE',
        asset_scope TEXT NOT NULL DEFAULT 'ALL',
        allowed_asset_classes TEXT DEFAULT 'CRYPTO,COMMODITIES,US_MARKET',
        allowed_symbols TEXT DEFAULT '',
        strategy_scope TEXT DEFAULT 'ALL_STRATEGIES',
        current_trade_id TEXT,
        current_position_id TEXT,
        created_at INTEGER,
        updated_at INTEGER,
        last_used_at INTEGER,
        user_id INTEGER DEFAULT 1,
        max_loss_usdt REAL DEFAULT 0.0,
        max_loss_pct REAL DEFAULT 10.0,
        trailing_enabled INTEGER DEFAULT 1,
        trailing_pct REAL DEFAULT 1.5,
        tp1_enabled INTEGER DEFAULT 1,
        tp1_pct REAL DEFAULT 50.0,
        breakeven_enabled INTEGER DEFAULT 1,
        breakeven_mode TEXT DEFAULT 'AFTER_TP1',
        slot_mode TEXT DEFAULT 'BOTH'
    )""")

    # Seamless migration: verify and add any missing columns in existing DB
    try:
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(autonomous_trade_slots)").fetchall()}
        new_cols = [
            ("user_id", "INTEGER DEFAULT 1"),
            ("max_loss_usdt", "REAL DEFAULT 0.0"),
            ("max_loss_pct", "REAL DEFAULT 10.0"),
            ("trailing_enabled", "INTEGER DEFAULT 1"),
            ("trailing_pct", "REAL DEFAULT 1.5"),
            ("tp1_enabled", "INTEGER DEFAULT 1"),
            ("tp1_pct", "REAL DEFAULT 50.0"),
            ("breakeven_enabled", "INTEGER DEFAULT 1"),
            ("breakeven_mode", "TEXT DEFAULT 'AFTER_TP1'"),
            ("slot_mode", "TEXT DEFAULT 'BOTH'"),
            ("account_id", "INTEGER DEFAULT 1"),
            ("scope", "TEXT DEFAULT 'ALL'"),
            ("strategy_scope", "TEXT DEFAULT 'ALL_STRATEGIES'"),
            ("mode", "TEXT DEFAULT 'BOTH'"),
            ("maximum_loss_percent", "REAL DEFAULT 10.0"),
            ("trailing_configuration", "TEXT DEFAULT ''"),
            ("tp1_percent", "REAL DEFAULT 50.0"),
            ("move_sl_to_cost", "INTEGER DEFAULT 1"),
            ("reserved_at", "INTEGER DEFAULT NULL"),
            ("released_at", "INTEGER DEFAULT NULL"),
            ("reservation_id", "TEXT DEFAULT NULL"),
            ("last_error", "TEXT DEFAULT NULL"),
            ("last_error_reason", "TEXT DEFAULT NULL"),
        ]
        for col_name, col_type in new_cols:
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE autonomous_trade_slots ADD COLUMN {col_name} {col_type}")
    except Exception:
        pass

    # Table for authorized user slot templates (Autonomous Slot Provisioning)
    conn.execute("""CREATE TABLE IF NOT EXISTS user_slot_templates(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        account_id INTEGER DEFAULT 1,
        scope TEXT NOT NULL DEFAULT 'CRYPTO',
        strategy_scope TEXT NOT NULL DEFAULT 'ALL',
        margin REAL NOT NULL DEFAULT 50.0,
        leverage REAL NOT NULL DEFAULT 5.0,
        max_loss_pct REAL NOT NULL DEFAULT 2.0,
        tp1_pct REAL NOT NULL DEFAULT 50.0,
        breakeven INTEGER NOT NULL DEFAULT 1,
        trailing INTEGER NOT NULL DEFAULT 1,
        trailing_pct REAL NOT NULL DEFAULT 1.5,
        max_slots INTEGER NOT NULL DEFAULT 5,
        max_autonomous_capital REAL NOT NULL DEFAULT 500.0,
        created_at INTEGER,
        updated_at INTEGER,
        UNIQUE(user_id, scope)
    )""")

    # Table for immutable execution intents
    conn.execute("""CREATE TABLE IF NOT EXISTS execution_intents(
        execution_intent_id TEXT PRIMARY KEY,
        candidate_id TEXT,
        automation_id INTEGER,
        slot_id INTEGER,
        user_id INTEGER NOT NULL,
        account_id INTEGER DEFAULT 1,
        instrument TEXT NOT NULL,
        direction TEXT NOT NULL,
        requested_margin REAL NOT NULL,
        leverage REAL NOT NULL,
        entry_policy TEXT,
        stop_policy TEXT,
        tp_policy TEXT,
        trailing_policy TEXT,
        created_at INTEGER NOT NULL,
        updated_at INTEGER,
        status TEXT NOT NULL DEFAULT 'CREATED',
        idempotency_key TEXT UNIQUE,
        error_reason TEXT,
        position_id TEXT
    )""")

    conn.execute("""CREATE TABLE IF NOT EXISTS setup_candidates(
        setup_id TEXT PRIMARY KEY,
        symbol TEXT NOT NULL,
        direction TEXT NOT NULL,
        timeframe INTEGER NOT NULL DEFAULT 5,
        strategy TEXT NOT NULL DEFAULT 'ALL',
        current_state TEXT NOT NULL DEFAULT 'IDLE',
        reason TEXT,
        vwap REAL,
        breakout_price REAL,
        retest_state TEXT,
        cvd_confirmed INTEGER DEFAULT 0,
        rvol_confirmed INTEGER DEFAULT 0,
        fvg_confirmed INTEGER DEFAULT 0,
        entry_conditions_json TEXT,
        confirmation_conditions_json TEXT,
        invalidation_json TEXT,
        suggested_sl REAL,
        tp1 REAL,
        tp2 REAL,
        tp3 REAL,
        rr_ratio REAL,
        created_at INTEGER,
        updated_at INTEGER,
        user_id INTEGER DEFAULT 1,
        account_id INTEGER DEFAULT 1,
        automation_id INTEGER DEFAULT NULL,
        waiting_for TEXT,
        next_required_event TEXT,
        distance_pct REAL,
        distance_atr REAL,
        priority TEXT,
        priority_reasons_json TEXT,
        conditions_json TEXT,
        data_freshness_json TEXT,
        actionability_score REAL DEFAULT 0.0,
        zone_json TEXT,
        structural_invalidation TEXT,
        suggested_tp1 REAL,
        suggested_tp2 REAL,
        risk_reward REAL,
        confidence_pct REAL,
        thesis TEXT,
        generated_ms INTEGER,
        expires_ms INTEGER,
        status TEXT DEFAULT 'ACTIVE'
    )""")
    try:
        cand_cols = {row[1] for row in conn.execute("PRAGMA table_info(setup_candidates)").fetchall()}
        cand_add_cols = [
            ("user_id", "INTEGER DEFAULT 1"),
            ("account_id", "INTEGER DEFAULT 1"),
            ("automation_id", "INTEGER DEFAULT NULL"),
            ("waiting_for", "TEXT"),
            ("next_required_event", "TEXT"),
            ("distance_pct", "REAL"),
            ("distance_atr", "REAL"),
            ("priority", "TEXT"),
            ("priority_reasons_json", "TEXT"),
            ("conditions_json", "TEXT"),
            ("data_freshness_json", "TEXT"),
            ("actionability_score", "REAL DEFAULT 0.0"),
            ("zone_json", "TEXT"),
            ("structural_invalidation", "TEXT"),
            ("suggested_tp1", "REAL"),
            ("suggested_tp2", "REAL"),
            ("risk_reward", "REAL"),
            ("confidence_pct", "REAL"),
            ("thesis", "TEXT"),
            ("generated_ms", "INTEGER"),
            ("expires_ms", "INTEGER"),
            ("status", "TEXT DEFAULT 'ACTIVE'"),
        ]
        for col_name, col_type in cand_add_cols:
            if col_name not in cand_cols:
                conn.execute(f"ALTER TABLE setup_candidates ADD COLUMN {col_name} {col_type}")
    except Exception:
        pass

    now_ms = int(time.time() * 1000)
    slot_count = conn.execute("SELECT COUNT(*) FROM autonomous_trade_slots").fetchone()[0]
    if slot_count == 0:
        conn.execute("""INSERT INTO autonomous_trade_slots(
            id, name, enabled, allocated_margin_usdt, max_leverage, status, asset_scope,
            allowed_asset_classes, strategy_scope, created_at, updated_at,
            user_id, max_loss_usdt, max_loss_pct, trailing_enabled, trailing_pct,
            tp1_enabled, tp1_pct, breakeven_enabled, breakeven_mode, slot_mode
        ) VALUES (1, 'SLOT 1', 1, 50.0, 5.0, 'AVAILABLE', 'ALL', 'CRYPTO,COMMODITIES,US_MARKET', 'ALL_STRATEGIES', ?, ?, 1, 5.0, 10.0, 1, 1.5, 1, 50.0, 1, 'AFTER_TP1', 'BOTH')""",
        (now_ms, now_ms))
        conn.execute("""INSERT INTO autonomous_trade_slots(
            id, name, enabled, allocated_margin_usdt, max_leverage, status, asset_scope,
            allowed_asset_classes, strategy_scope, created_at, updated_at,
            user_id, max_loss_usdt, max_loss_pct, trailing_enabled, trailing_pct,
            tp1_enabled, tp1_pct, breakeven_enabled, breakeven_mode, slot_mode
        ) VALUES (2, 'SLOT 2', 1, 75.0, 5.0, 'AVAILABLE', 'ALL', 'CRYPTO,COMMODITIES,US_MARKET', 'ALL_STRATEGIES', ?, ?, 1, 7.5, 10.0, 1, 1.5, 1, 50.0, 1, 'AFTER_TP1', 'BOTH')""",
        (now_ms, now_ms))

    conn.execute("""CREATE TABLE IF NOT EXISTS us_top_100_universe(
        symbol TEXT PRIMARY KEY,
        rank INTEGER,
        company_name TEXT,
        exchange TEXT,
        sector TEXT,
        industry TEXT,
        market_cap REAL,
        average_volume REAL,
        volatility REAL,
        liquidity_score REAL,
        bingx_available INTEGER DEFAULT 0,
        bingx_symbol TEXT,
        data_provider TEXT,
        data_freshness TEXT,
        last_updated INTEGER
    )""")

    conn.execute("""CREATE TABLE IF NOT EXISTS us_stock_intelligence_state(
        symbol TEXT PRIMARY KEY,
        price REAL,
        change_pct REAL,
        direction TEXT,
        bias TEXT,
        confidence REAL,
        sector TEXT,
        industry TEXT,
        market_regime TEXT,
        volume_state TEXT,
        rvol REAL,
        order_flow TEXT,
        vwap REAL,
        vwap_state TEXT,
        volatility REAL,
        liquidity TEXT,
        news_state TEXT,
        news_direction TEXT,
        news_impact TEXT,
        options_state TEXT,
        gex_state TEXT,
        bingx_state TEXT,
        bingx_symbol TEXT,
        overnight_bias TEXT,
        candidate_state TEXT,
        waiting_for TEXT,
        trade_direction TEXT,
        targets_json TEXT,
        rr_ratio REAL,
        data_freshness TEXT,
        updated_at INTEGER
    )""")

    conn.execute("""CREATE TABLE IF NOT EXISTS us_sector_state(
        sector TEXT PRIMARY KEY,
        return_pct REAL,
        relative_strength_spy REAL,
        volume REAL,
        breadth_pct REAL,
        momentum REAL,
        regime TEXT,
        news_intensity TEXT,
        news_sentiment TEXT,
        top_movers_json TEXT,
        updated_at INTEGER
    )""")

    conn.execute("""CREATE TABLE IF NOT EXISTS us_news_events(
        event_id TEXT PRIMARY KEY,
        headline TEXT,
        timestamp INTEGER,
        source TEXT,
        event_type TEXT,
        entities_json TEXT,
        companies_json TEXT,
        sector TEXT,
        sentiment TEXT,
        direction TEXT,
        impact TEXT,
        confidence REAL,
        market_reaction TEXT,
        created_at INTEGER
    )""")

    conn.execute("""CREATE TABLE IF NOT EXISTS bingx_tradfi_registry(
        underlying_symbol TEXT PRIMARY KEY,
        bingx_symbol TEXT NOT NULL,
        status TEXT,
        tick_size REAL,
        quantity_step REAL,
        minimum_quantity REAL,
        minimum_notional REAL,
        contract_size REAL,
        max_leverage REAL,
        funding_rate REAL,
        price_precision INTEGER,
        quantity_precision INTEGER,
        last_verified INTEGER
    )""")


# ============================================================
# GLOBAL AUTONOMOUS TRADE SLOTS CRUD & STATE MACHINE
# ============================================================
_SLOT_COLUMNS = [
    "id", "name", "enabled", "allocated_margin_usdt", "max_leverage", "status",
    "asset_scope", "allowed_asset_classes", "allowed_symbols", "strategy_scope",
    "current_trade_id", "current_position_id", "created_at", "updated_at", "last_used_at",
    "user_id", "max_loss_usdt", "max_loss_pct", "trailing_enabled", "trailing_pct",
    "tp1_enabled", "tp1_pct", "breakeven_enabled", "breakeven_mode", "slot_mode",
    "account_id", "scope", "mode", "maximum_loss_percent", "trailing_configuration",
    "tp1_percent", "move_sl_to_cost", "reserved_at", "released_at", "reservation_id",
    "last_error", "last_error_reason"
]

def _row_to_slot(r: tuple) -> dict:
    d = dict(zip(_SLOT_COLUMNS, r))
    d["enabled"] = bool(d.get("enabled", 1))
    d["trailing_enabled"] = bool(d.get("trailing_enabled", 1))
    d["tp1_enabled"] = bool(d.get("tp1_enabled", 1))
    d["breakeven_enabled"] = bool(d.get("breakeven_enabled", 1))
    d["user_id"] = int(d.get("user_id") or 1)
    d["account_id"] = int(d.get("account_id") or 1)
    d["max_loss_usdt"] = float(d.get("max_loss_usdt") or 0.0)
    d["max_loss_pct"] = float(d.get("max_loss_pct") or 10.0)
    d["maximum_loss_percent"] = float(d.get("maximum_loss_percent") or d.get("max_loss_pct") or 10.0)
    d["trailing_pct"] = float(d.get("trailing_pct") or 1.5)
    d["tp1_pct"] = float(d.get("tp1_pct") or 50.0)
    d["tp1_percent"] = float(d.get("tp1_percent") or d.get("tp1_pct") or 50.0)
    d["breakeven_mode"] = str(d.get("breakeven_mode") or "AFTER_TP1")
    d["slot_mode"] = str(d.get("slot_mode") or "BOTH")
    d["mode"] = str(d.get("mode") or d.get("slot_mode") or "BOTH")
    d["scope"] = str(d.get("scope") or d.get("asset_scope") or "ALL")
    d["strategy_scope"] = str(d.get("strategy_scope") or "ALL_STRATEGIES")
    d["move_sl_to_cost"] = bool(d.get("move_sl_to_cost") if d.get("move_sl_to_cost") is not None else d.get("breakeven_enabled", 1))
    d["trailing_configuration"] = str(d.get("trailing_configuration") or f"trail={d.get('trailing_pct', 1.5)}%")
    return d

def ensure_root_admin() -> None:
    """Ensure root admin user (id=1, ophelia-sys) exists with valid password hash."""
    admin_pass = os.environ.get("OPHELIA_ADMIN_PASSWORD", "Vishalnaik@1994")
    try:
        import bcrypt
        admin_pwd_hash = bcrypt.hashpw(admin_pass.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    except Exception:
        admin_pwd_hash = "$2b$12$e0c0P9eZ1mO/Esm6N4uP4O47lJ0ZgG1NnIeNZZH0B6hI.W6wI2u5m"
    now_ms = int(time.time() * 1000)
    c = _connect()
    with _lock:
        c.execute("""
            INSERT INTO users(id, user_uid, role, email, display_name, password_hash, status, copy_enabled, admin_copy_allowed, created_at)
            VALUES(1, 'ophelia-sys', 'ADMIN', 'ophelia-sys', 'Ophelia Admin', ?, 'ACTIVE', 1, 1, ?)
            ON CONFLICT(id) DO UPDATE SET
                role='ADMIN',
                status='ACTIVE',
                display_name='Ophelia Admin',
                user_uid='ophelia-sys',
                email='ophelia-sys',
                password_hash=excluded.password_hash
        """, (admin_pwd_hash, now_ms))
        c.execute("UPDATE users SET password_hash=?, role='ADMIN', status='ACTIVE' WHERE email='admin@ophelia.internal' OR user_uid='ophelia-sys'", (admin_pwd_hash,))
        c.commit()

def ensure_default_user_slots(user_id: int) -> None:
    """Ensure a new or existing user has at least one default autonomous trade slot."""
    if not user_id or user_id < 1:
        return
    c = _connect()
    with _lock:
        cnt = c.execute("SELECT COUNT(*) FROM autonomous_trade_slots WHERE user_id=?", (user_id,)).fetchone()[0]
        if cnt == 0:
            now_ms = int(time.time() * 1000)
            c.execute("""INSERT INTO autonomous_trade_slots(
                name, enabled, allocated_margin_usdt, max_leverage, status, asset_scope,
                allowed_asset_classes, strategy_scope, created_at, updated_at,
                user_id, max_loss_usdt, max_loss_pct, trailing_enabled, trailing_pct,
                tp1_enabled, tp1_pct, breakeven_enabled, breakeven_mode, slot_mode
            ) VALUES ('SLOT 1', 1, 50.0, 5.0, 'AVAILABLE', 'ALL', 'CRYPTO,COMMODITIES,US_MARKET',
                      'ALL_STRATEGIES', ?, ?, ?, 5.0, 10.0, 1, 1.5, 1, 50.0, 1, 'AFTER_TP1', 'BOTH')""",
            (now_ms, now_ms, user_id))
            c.commit()

def get_autonomous_trade_slots(enabled_only: bool = False, user_id: int | None = None) -> list[dict]:
    """Retrieve dynamic autonomous trade slots, optionally filtered by enabled and user_id."""
    c = _connect()
    q = f"SELECT {', '.join(_SLOT_COLUMNS)} FROM autonomous_trade_slots"
    clauses = []
    args = []
    if enabled_only:
        clauses.append("enabled=1")
    if user_id is not None:
        clauses.append("user_id=?")
        args.append(user_id)
    if clauses:
        q += " WHERE " + " AND ".join(clauses)
    q += " ORDER BY id ASC"
    with _lock:
        rows = c.execute(q, args).fetchall()
    return [_row_to_slot(r) for r in rows]

def get_autonomous_trade_slot(slot_id: int, user_id: int | None = None) -> dict | None:
    c = _connect()
    q = f"SELECT {', '.join(_SLOT_COLUMNS)} FROM autonomous_trade_slots WHERE id=?"
    args = [slot_id]
    if user_id is not None:
        q += " AND user_id=?"
        args.append(user_id)
    with _lock:
        row = c.execute(q, args).fetchone()
    return _row_to_slot(row) if row else None

def add_autonomous_trade_slot(
    name: str,
    allocated_margin_usdt: float,
    max_leverage: float = 5.0,
    asset_scope: str = "ALL",
    allowed_asset_classes: str | list | None = "CRYPTO,COMMODITIES,US_MARKET",
    allowed_symbols: str | list | None = "",
    strategy_scope: str | None = "ALL_STRATEGIES",
    enabled: bool = True,
    user_id: int = 0,
    max_loss_usdt: float = 0.0,
    max_loss_pct: float = 10.0,
    trailing_enabled: bool = True,
    trailing_pct: float = 1.5,
    tp1_enabled: bool = True,
    tp1_pct: float = 50.0,
    breakeven_enabled: bool = True,
    breakeven_mode: str = "AFTER_TP1",
    slot_mode: str = "BOTH"
) -> int:
    """Add a new dynamic autonomous trade slot with server-enforced safety ceilings."""
    if not user_id or user_id < 1:
        raise ValueError("Valid user_id required to add autonomous trade slot")
    margin = float(allocated_margin_usdt)
    lev = float(max_leverage)
    if margin <= 0.0 or margin > 1000.0:
        raise ValueError("Allocated margin must be between 1.0 and 1000.0 USDT per slot")
    if lev <= 0.0 or lev > 10.0:
        raise ValueError("Max leverage must be between 1.0x and 10.0x")

    c = _connect()
    with _lock:
        existing_slots = c.execute("SELECT allocated_margin_usdt FROM autonomous_trade_slots WHERE user_id=?", (user_id,)).fetchall()
        if len(existing_slots) >= 10:
            raise ValueError("Maximum 10 autonomous trade slots permitted per user")
        total_margin = sum(r[0] for r in existing_slots) + margin
        if total_margin > 5000.0:
            raise ValueError("Total authorized margin across slots cannot exceed 5000.0 USDT")

    now_ms = int(time.time() * 1000)

    asset_scope_str = (asset_scope or "ALL").strip().upper() if isinstance(asset_scope, str) else "ALL"
    if isinstance(allowed_asset_classes, list):
        allowed_asset_classes_str = ",".join(str(x).strip().upper() for x in allowed_asset_classes)
    else:
        allowed_asset_classes_str = (allowed_asset_classes or "CRYPTO,COMMODITIES,US_MARKET").strip().upper()

    if isinstance(allowed_symbols, list):
        allowed_symbols_str = ",".join(str(x).strip().upper() for x in allowed_symbols)
    else:
        allowed_symbols_str = (allowed_symbols or "").strip().upper()

    strategy_scope_str = (strategy_scope or "ALL_STRATEGIES").strip().upper() if isinstance(strategy_scope, str) else "ALL_STRATEGIES"

    loss_pct = max(1.0, min(100.0, float(max_loss_pct)))
    loss_usdt = float(max_loss_usdt)
    if loss_usdt <= 0.0:
        loss_usdt = round(margin * (loss_pct / 100.0), 2)

    mode_str = (slot_mode or "BOTH").strip().upper()
    if mode_str not in ("AUTONOMOUS", "COPY_OPHELIA", "BOTH"):
        mode_str = "BOTH"

    with _lock:
        cur = c.execute("""INSERT INTO autonomous_trade_slots(
            name, enabled, allocated_margin_usdt, max_leverage, status, asset_scope,
            allowed_asset_classes, allowed_symbols, strategy_scope, created_at, updated_at,
            user_id, max_loss_usdt, max_loss_pct, trailing_enabled, trailing_pct,
            tp1_enabled, tp1_pct, breakeven_enabled, breakeven_mode, slot_mode
        ) VALUES (?, ?, ?, ?, 'AVAILABLE', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (name.strip().upper(), 1 if enabled else 0, margin, lev,
         asset_scope_str, allowed_asset_classes_str, allowed_symbols_str,
         strategy_scope_str, now_ms, now_ms,
         user_id, loss_usdt, loss_pct, 1 if trailing_enabled else 0, float(trailing_pct),
         1 if tp1_enabled else 0, float(tp1_pct), 1 if breakeven_enabled else 0,
         breakeven_mode.strip().upper(), mode_str))
        c.commit()
        return cur.lastrowid

def update_autonomous_trade_slot(
    slot_id: int,
    name: str | None = None,
    allocated_margin_usdt: float | None = None,
    max_leverage: float | None = None,
    asset_scope: str | None = None,
    allowed_asset_classes: str | list | None = None,
    allowed_symbols: str | list | None = None,
    strategy_scope: str | None = None,
    enabled: bool | None = None,
    user_id: int | None = None,
    max_loss_usdt: float | None = None,
    max_loss_pct: float | None = None,
    trailing_enabled: bool | None = None,
    trailing_pct: float | None = None,
    tp1_enabled: bool | None = None,
    tp1_pct: float | None = None,
    breakeven_enabled: bool | None = None,
    breakeven_mode: str | None = None,
    slot_mode: str | None = None
) -> tuple[bool, str | None]:
    """Update slot parameters. Blocked if slot is OCCUPIED/RESERVED unless updating enabled flag."""
    slot = get_autonomous_trade_slot(slot_id, user_id=user_id)
    if not slot:
        return False, "Slot not found or unauthorized"
    if slot["status"] in ("OCCUPIED", "RESERVED"):
        if any(x is not None for x in (allocated_margin_usdt, max_leverage, asset_scope, allowed_symbols, max_loss_usdt, slot_mode)):
            return False, f"Slot {slot_id} is currently {slot['status']} - parameters cannot be altered while active"

    c = _connect()
    updates = []
    args = []
    if name is not None:
        updates.append("name=?")
        args.append(name.strip().upper())
    if allocated_margin_usdt is not None:
        margin = float(allocated_margin_usdt)
        if margin <= 0.0 or margin > 1000.0:
            return False, "Allocated margin must be between 1.0 and 1000.0 USDT"
        updates.append("allocated_margin_usdt=?")
        args.append(margin)
    if max_leverage is not None:
        lev = float(max_leverage)
        if lev <= 0.0 or lev > 10.0:
            return False, "Max leverage must be between 1.0x and 10.0x"
        updates.append("max_leverage=?")
        args.append(lev)
    if asset_scope is not None:
        updates.append("asset_scope=?")
        updates_val = asset_scope.strip().upper() if isinstance(asset_scope, str) else "ALL"
        args.append(updates_val)
    if allowed_asset_classes is not None:
        updates.append("allowed_asset_classes=?")
        if isinstance(allowed_asset_classes, list):
            args.append(",".join(str(x).strip().upper() for x in allowed_asset_classes))
        else:
            args.append(str(allowed_asset_classes).strip().upper())
    if allowed_symbols is not None:
        updates.append("allowed_symbols=?")
        if isinstance(allowed_symbols, list):
            args.append(",".join(str(x).strip().upper() for x in allowed_symbols))
        else:
            args.append(str(allowed_symbols).strip().upper())
    if strategy_scope is not None:
        updates.append("strategy_scope=?")
        args.append(strategy_scope.strip().upper() if isinstance(strategy_scope, str) else "ALL_STRATEGIES")
    if enabled is not None:
        updates.append("enabled=?")
        args.append(1 if enabled else 0)
    if max_loss_usdt is not None:
        updates.append("max_loss_usdt=?")
        args.append(float(max_loss_usdt))
    if max_loss_pct is not None:
        updates.append("max_loss_pct=?")
        args.append(float(max_loss_pct))
    if trailing_enabled is not None:
        updates.append("trailing_enabled=?")
        args.append(1 if trailing_enabled else 0)
    if trailing_pct is not None:
        updates.append("trailing_pct=?")
        args.append(float(trailing_pct))
    if tp1_enabled is not None:
        updates.append("tp1_enabled=?")
        args.append(1 if tp1_enabled else 0)
    if tp1_pct is not None:
        updates.append("tp1_pct=?")
        args.append(float(tp1_pct))
    if breakeven_enabled is not None:
        updates.append("breakeven_enabled=?")
        args.append(1 if breakeven_enabled else 0)
    if breakeven_mode is not None:
        updates.append("breakeven_mode=?")
        args.append(breakeven_mode.strip().upper())
    if slot_mode is not None:
        mode_str = slot_mode.strip().upper()
        if mode_str in ("AUTONOMOUS", "COPY_OPHELIA", "BOTH"):
            updates.append("slot_mode=?")
            args.append(mode_str)

    if not updates:
        return True, None
    now_ms = int(time.time() * 1000)
    updates.append("updated_at=?")
    args.append(now_ms)
    args.append(slot_id)

    q = f"UPDATE autonomous_trade_slots SET {', '.join(updates)} WHERE id=?"
    if user_id is not None:
        q += " AND user_id=?"
        args.append(user_id)

    with _lock:
        cur = c.execute(q, args)
        c.commit()
    return (cur.rowcount > 0), None

def delete_autonomous_trade_slot(slot_id: int, user_id: int | None = None) -> tuple[bool, str | None]:
    """Delete a dynamic slot. Strictly prohibited if slot is OCCUPIED or RESERVED."""
    slot = get_autonomous_trade_slot(slot_id, user_id=user_id)
    if not slot:
        return False, "Slot not found or unauthorized"
    if slot["status"] in ("OCCUPIED", "RESERVED"):
        return False, f"Cannot delete slot {slot_id} while it is {slot['status']}. Close position first."
    c = _connect()
    q = "DELETE FROM autonomous_trade_slots WHERE id=?"
    args = [slot_id]
    if user_id is not None:
        q += " AND user_id=?"
        args.append(user_id)
    with _lock:
        cur = c.execute(q, args)
        c.commit()
    return (cur.rowcount > 0), None

def reserve_autonomous_trade_slot(slot_id: int, trade_id: str, user_id: int | None = None) -> bool:
    """Atomic conditional reservation of an available slot. Zero race condition / double allocation."""
    try:
        from .slot_allocation_service import SlotAllocationService
        if user_id is not None and user_id > 0:
            ok, _, _ = SlotAllocationService.reserve_slot(slot_id, str(trade_id), user_id=user_id)
            return ok
    except Exception:
        pass
    c = _connect()
    now_ms = int(time.time() * 1000)
    q = """UPDATE autonomous_trade_slots
        SET status='RESERVED', current_trade_id=?, reserved_at=?, updated_at=?
        WHERE id=? AND status='AVAILABLE' AND enabled=1"""
    args = [str(trade_id), now_ms, now_ms, slot_id]
    if user_id is not None:
        q += " AND user_id=?"
        args.append(user_id)
    with _lock:
        cur = c.execute(q, args)
        c.commit()
        return cur.rowcount > 0

def occupy_autonomous_trade_slot(slot_id: int, position_id: str, user_id: int | None = None) -> bool:
    """Mark slot as OCCUPIED once trade/position is successfully confirmed."""
    try:
        from .slot_allocation_service import SlotAllocationService
        if user_id is not None and user_id > 0:
            ok, _ = SlotAllocationService.occupy_slot(slot_id, str(position_id), user_id=user_id)
            return ok
    except Exception:
        pass
    c = _connect()
    now_ms = int(time.time() * 1000)
    q = """UPDATE autonomous_trade_slots
        SET status='OCCUPIED', current_position_id=?, last_used_at=?, updated_at=?
        WHERE id=? AND status IN ('RESERVED', 'AVAILABLE')"""
    args = [str(position_id), now_ms, now_ms, slot_id]
    if user_id is not None:
        q += " AND user_id=?"
        args.append(user_id)
    with _lock:
        cur = c.execute(q, args)
        c.commit()
        return cur.rowcount > 0

def release_autonomous_trade_slot(slot_id: int, user_id: int | None = None) -> bool:
    """Release occupied/reserved slot back to AVAILABLE state after position close or failure."""
    try:
        from .slot_allocation_service import SlotAllocationService
        ok, _ = SlotAllocationService.release_slot(slot_id, user_id=user_id, reason="DIRECT_RELEASE")
        return ok
    except Exception:
        pass
    c = _connect()
    now_ms = int(time.time() * 1000)
    q = """UPDATE autonomous_trade_slots
        SET status='AVAILABLE', current_trade_id=NULL, current_position_id=NULL,
            reservation_id=NULL, released_at=?, updated_at=?
        WHERE id=?"""
    args = [now_ms, now_ms, slot_id]
    if user_id is not None:
        q += " AND user_id=?"
        args.append(user_id)
    with _lock:
        cur = c.execute(q, args)
        c.commit()
        return cur.rowcount > 0

def release_slot_by_position(position_id: str | int) -> bool:
    """Release any autonomous trade slot held by this position ID back to AVAILABLE."""
    c = _connect()
    now_ms = int(time.time() * 1000)
    pos_str = str(position_id)
    with _lock:
        cur = c.execute("""UPDATE autonomous_trade_slots
            SET status='AVAILABLE', current_trade_id=NULL, current_position_id=NULL,
                last_used_at=?, updated_at=?
            WHERE current_position_id=?""",
            (now_ms, now_ms, pos_str))
        c.commit()
        return cur.rowcount > 0

def find_eligible_available_slot(
    asset_class: str,
    strategy: str = "ALL",
    symbol: str = "",
    user_id: int = 0,
    slot_mode: str = "AUTONOMOUS"
) -> dict | None:
    """Find matching AVAILABLE and ENABLED autonomous trade slot via SlotAllocationService."""
    try:
        from .slot_allocation_service import SlotAllocationService
        slot, _ = SlotAllocationService.find_eligible_slot(
            candidate={"asset_class": asset_class, "strategy": strategy, "symbol": symbol},
            user_id=user_id
        )
        if slot:
            return slot
    except Exception:
        pass

    if not is_global_autonomous_enabled():
        return None
    if not user_id or user_id < 1:
        return None
    slots = get_autonomous_trade_slots(enabled_only=True, user_id=user_id)
    asset_upper = asset_class.strip().upper()
    sym_upper = symbol.strip().upper()
    strat_upper = strategy.strip().upper()
    mode_upper = slot_mode.strip().upper()

    for s in slots:
        if s["status"] != "AVAILABLE":
            continue
        s_mode = (s.get("slot_mode") or "BOTH").strip().upper()
        if mode_upper != "ANY" and s_mode != "BOTH" and s_mode != mode_upper:
            continue
        scope = s.get("scope") or s["asset_scope"]
        allowed_classes = [x.strip() for x in (s.get("allowed_asset_classes") or "ALL").split(",") if x.strip()]
        if scope != "ALL" and asset_upper not in scope and asset_upper not in allowed_classes and "ALL" not in allowed_classes:
            continue
        allowed_syms = [x.strip() for x in (s.get("allowed_symbols") or "").split(",") if x.strip()]
        if allowed_syms and sym_upper not in allowed_syms:
            continue
        strat_scope = (s.get("strategy_scope") or "ALL").strip().upper()
        if strat_scope not in ("ALL", "ALL_STRATEGIES") and strat_upper not in ("ALL", "ALL_STRATEGIES") and strat_upper not in strat_scope:
            continue
        return s
    return None

def get_autonomous_trading_summary(user_id: int | None = None) -> dict:
    """Return high-level summary of autonomous trade slots and capital status for user."""
    if user_id is not None and user_id > 0:
        ensure_default_user_slots(user_id)
    slots = get_autonomous_trade_slots(user_id=user_id)
    total_slots = len(slots)
    enabled_slots = sum(1 for s in slots if s["enabled"])
    available_slots = sum(1 for s in slots if s["enabled"] and s["status"] == "AVAILABLE")
    occupied_slots = sum(1 for s in slots if s["status"] == "OCCUPIED")
    reserved_slots = sum(1 for s in slots if s["status"] == "RESERVED")

    total_authorized_margin = sum(s["allocated_margin_usdt"] for s in slots if s["enabled"])
    reserved_margin = sum(s["allocated_margin_usdt"] for s in slots if s["status"] in ("OCCUPIED", "RESERVED"))
    available_margin = max(0.0, total_authorized_margin - reserved_margin)

    return {
        "global_enabled": is_global_autonomous_enabled(),
        "user_id": user_id,
        "total_slots": total_slots,
        "enabled_slots": enabled_slots,
        "available_slots": available_slots,
        "occupied_slots": occupied_slots,
        "reserved_slots": reserved_slots,
        "total_authorized_margin_usdt": round(total_authorized_margin, 2),
        "reserved_margin_usdt": round(reserved_margin, 2),
        "available_authorized_margin_usdt": round(available_margin, 2),
        "slots": slots
    }

def is_global_autonomous_enabled() -> bool:
    v = get_meta("global_autonomous_trading_enabled")
    return (v == "1" or v is None)

def set_global_autonomous_enabled(enabled: bool) -> None:
    set_meta("global_autonomous_trading_enabled", "1" if enabled else "0")


# ============================================================
# USER SLOT TEMPLATES & EXECUTION INTENTS HELPERS
# ============================================================
def get_user_slot_template(user_id: int, scope: str = "ALL") -> dict | None:
    """Retrieve authorized user slot template for a given asset scope or ALL."""
    if not user_id or user_id < 1:
        return None
    c = _connect()
    scope_upper = (scope or "ALL").strip().upper()
    with _lock:
        row = c.execute("""
            SELECT id, user_id, account_id, scope, strategy_scope, margin, leverage,
                   max_loss_pct, tp1_pct, breakeven, trailing, trailing_pct, max_slots,
                   max_autonomous_capital, created_at, updated_at
            FROM user_slot_templates
            WHERE user_id=? AND (scope=? OR scope='ALL')
            ORDER BY CASE WHEN scope=? THEN 1 ELSE 2 END ASC
            LIMIT 1
        """, (user_id, scope_upper, scope_upper)).fetchone()
    if not row:
        return None
    cols = [
        "id", "user_id", "account_id", "scope", "strategy_scope", "margin", "leverage",
        "max_loss_pct", "tp1_pct", "breakeven", "trailing", "trailing_pct", "max_slots",
        "max_autonomous_capital", "created_at", "updated_at"
    ]
    d = dict(zip(cols, row))
    d["breakeven"] = bool(d["breakeven"])
    d["trailing"] = bool(d["trailing"])
    return d


def get_user_slot_templates(user_id: int) -> list[dict]:
    """Retrieve all authorized user slot templates for a user."""
    if not user_id or user_id < 1:
        return []
    c = _connect()
    with _lock:
        rows = c.execute("""
            SELECT id, user_id, account_id, scope, strategy_scope, margin, leverage,
                   max_loss_pct, tp1_pct, breakeven, trailing, trailing_pct, max_slots,
                   max_autonomous_capital, created_at, updated_at
            FROM user_slot_templates
            WHERE user_id=?
            ORDER BY id ASC
        """, (user_id,)).fetchall()
    cols = [
        "id", "user_id", "account_id", "scope", "strategy_scope", "margin", "leverage",
        "max_loss_pct", "tp1_pct", "breakeven", "trailing", "trailing_pct", "max_slots",
        "max_autonomous_capital", "created_at", "updated_at"
    ]
    res = []
    for r in rows:
        d = dict(zip(cols, r))
        d["breakeven"] = bool(d["breakeven"])
        d["trailing"] = bool(d["trailing"])
        res.append(d)
    return res


def set_user_slot_template(template_data: dict | None = None, user_id: int | None = None, **kwargs) -> int:
    """Set or update an authorized user slot template within server safety envelope."""
    if template_data is None:
        template_data = kwargs
    elif kwargs:
        template_data = dict(template_data, **kwargs)
    effective_uid = user_id or template_data.get("user_id")
    if not effective_uid or effective_uid < 1:
        raise ValueError("Valid user_id required")
    user_id = int(effective_uid)
    now_ms = int(time.time() * 1000)
    c = _connect()
    scope = (template_data.get("scope") or "CRYPTO").strip().upper()
    strat_scope = (template_data.get("strategy_scope") or "ALL").strip().upper()
    margin = float(template_data.get("margin", 50.0))
    leverage = min(float(template_data.get("leverage", 5.0)), 10.0)
    max_loss_pct = min(float(template_data.get("max_loss_pct", 2.0)), 10.0)
    tp1_pct = float(template_data.get("tp1_pct", 50.0))
    breakeven = 1 if template_data.get("breakeven", True) else 0
    trailing = 1 if template_data.get("trailing", True) else 0
    trailing_pct = float(template_data.get("trailing_pct", 1.5))
    max_slots = min(int(template_data.get("max_slots", 5)), 10)
    max_capital = min(float(template_data.get("max_autonomous_capital", 500.0)), 2500.0)
    account_id = int(template_data.get("account_id") or 1)

    with _lock:
        cur = c.execute("""
            INSERT INTO user_slot_templates(
                user_id, account_id, scope, strategy_scope, margin, leverage, max_loss_pct,
                tp1_pct, breakeven, trailing, trailing_pct, max_slots, max_autonomous_capital,
                created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, scope) DO UPDATE SET
                account_id=excluded.account_id,
                strategy_scope=excluded.strategy_scope,
                margin=excluded.margin,
                leverage=excluded.leverage,
                max_loss_pct=excluded.max_loss_pct,
                tp1_pct=excluded.tp1_pct,
                breakeven=excluded.breakeven,
                trailing=excluded.trailing,
                trailing_pct=excluded.trailing_pct,
                max_slots=excluded.max_slots,
                max_autonomous_capital=excluded.max_autonomous_capital,
                updated_at=excluded.updated_at
        """, (user_id, account_id, scope, strat_scope, margin, leverage, max_loss_pct,
              tp1_pct, breakeven, trailing, trailing_pct, max_slots, max_capital, now_ms, now_ms))
        c.commit()
        return cur.lastrowid


def create_execution_intent(intent: dict) -> str:
    """Create a persisted immutable execution intent record."""
    c = _connect()
    now_ms = int(time.time() * 1000)
    intent_id = intent.get("execution_intent_id") or f"intent-{uuid.uuid4().hex[:12]}"
    idempotency_key = intent.get("idempotency_key") or intent_id
    with _lock:
        c.execute("""
            INSERT INTO execution_intents(
                execution_intent_id, candidate_id, automation_id, slot_id, user_id,
                account_id, instrument, direction, requested_margin, leverage,
                entry_policy, stop_policy, tp_policy, trailing_policy, created_at,
                updated_at, status, idempotency_key, error_reason, position_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            intent_id,
            intent.get("candidate_id"),
            intent.get("automation_id"),
            intent.get("slot_id"),
            intent["user_id"],
            intent.get("account_id", 1),
            intent["instrument"],
            intent["direction"],
            float(intent["requested_margin"]),
            float(intent["leverage"]),
            _j.dumps(intent.get("entry_policy") or {}),
            _j.dumps(intent.get("stop_policy") or {}),
            _j.dumps(intent.get("tp_policy") or {}),
            _j.dumps(intent.get("trailing_policy") or {}),
            now_ms,
            now_ms,
            intent.get("status", "CREATED"),
            idempotency_key,
            intent.get("error_reason"),
            intent.get("position_id")
        ))
        c.commit()
    return intent_id


def update_execution_intent_status(
    intent_id: str,
    status: str,
    error_reason: str | None = None,
    position_id: str | None = None
) -> bool:
    """Update execution intent state machine status atomically."""
    c = _connect()
    now_ms = int(time.time() * 1000)
    with _lock:
        cur = c.execute("""
            UPDATE execution_intents
            SET status=?,
                error_reason=COALESCE(?, error_reason),
                position_id=COALESCE(?, position_id),
                updated_at=?
            WHERE execution_intent_id=?
        """, (status, error_reason, position_id, now_ms, intent_id))
        c.commit()
        return cur.rowcount > 0


def get_execution_intent(intent_id: str) -> dict | None:
    """Retrieve execution intent by ID."""
    c = _connect()
    with _lock:
        row = c.execute("""
            SELECT execution_intent_id, candidate_id, automation_id, slot_id, user_id,
                   account_id, instrument, direction, requested_margin, leverage,
                   entry_policy, stop_policy, tp_policy, trailing_policy, created_at,
                   updated_at, status, idempotency_key, error_reason, position_id
            FROM execution_intents WHERE execution_intent_id=?
        """, (intent_id,)).fetchone()
    if not row:
        return None
    cols = [
        "execution_intent_id", "candidate_id", "automation_id", "slot_id", "user_id",
        "account_id", "instrument", "direction", "requested_margin", "leverage",
        "entry_policy", "stop_policy", "tp_policy", "trailing_policy", "created_at",
        "updated_at", "status", "idempotency_key", "error_reason", "position_id"
    ]
    d = dict(zip(cols, row))
    for k in ("entry_policy", "stop_policy", "tp_policy", "trailing_policy"):
        if d.get(k):
            try:
                d[k] = _j.loads(d[k])
            except Exception:
                pass
    return d


def get_execution_intent_by_automation(automation_id: int) -> dict | None:
    """Retrieve most recent execution intent for an automation ID."""
    c = _connect()
    with _lock:
        row = c.execute("""
            SELECT execution_intent_id, candidate_id, automation_id, slot_id, user_id,
                   account_id, instrument, direction, requested_margin, leverage,
                   entry_policy, stop_policy, tp_policy, trailing_policy, created_at,
                   updated_at, status, idempotency_key, error_reason, position_id
            FROM execution_intents WHERE automation_id=?
            ORDER BY created_at DESC LIMIT 1
        """, (automation_id,)).fetchone()
    if not row:
        return None
    cols = [
        "execution_intent_id", "candidate_id", "automation_id", "slot_id", "user_id",
        "account_id", "instrument", "direction", "requested_margin", "leverage",
        "entry_policy", "stop_policy", "tp_policy", "trailing_policy", "created_at",
        "updated_at", "status", "idempotency_key", "error_reason", "position_id"
    ]
    d = dict(zip(cols, row))
    for k in ("entry_policy", "stop_policy", "tp_policy", "trailing_policy"):
        if d.get(k):
            try:
                d[k] = _j.loads(d[k])
            except Exception:
                pass
    return d


def list_execution_intents(user_id: int | None = None, limit: int = 50) -> list[dict]:
    """List execution intents optionally filtered by user_id."""
    c = _connect()
    q = """
        SELECT execution_intent_id, candidate_id, automation_id, slot_id, user_id,
               account_id, instrument, direction, requested_margin, leverage,
               entry_policy, stop_policy, tp_policy, trailing_policy, created_at,
               updated_at, status, idempotency_key, error_reason, position_id
        FROM execution_intents
    """
    args = []
    if user_id is not None:
        q += " WHERE user_id=?"
        args.append(user_id)
    q += " ORDER BY created_at DESC LIMIT ?"
    args.append(limit)
    with _lock:
        rows = c.execute(q, args).fetchall()
    cols = [
        "execution_intent_id", "candidate_id", "automation_id", "slot_id", "user_id",
        "account_id", "instrument", "direction", "requested_margin", "leverage",
        "entry_policy", "stop_policy", "tp_policy", "trailing_policy", "created_at",
        "updated_at", "status", "idempotency_key", "error_reason", "position_id"
    ]
    res = []
    for r in rows:
        d = dict(zip(cols, r))
        for k in ("entry_policy", "stop_policy", "tp_policy", "trailing_policy"):
            if d.get(k):
                try:
                    d[k] = _j.loads(d[k])
                except Exception:
                    pass
        res.append(d)
    return res


def get_setup_candidate_by_automation(automation_id: int) -> dict | None:
    """Retrieve setup candidate linked to an automation."""
    c = _connect()
    with _lock:
        row = c.execute("""
            SELECT setup_id, symbol, direction, timeframe, strategy, current_state,
                   reason, vwap, breakout_price, retest_state, suggested_sl,
                   suggested_tp1, suggested_tp2, risk_reward, confidence_pct,
                   thesis, generated_ms, expires_ms, status, waiting_for,
                   next_required_event, priority, user_id, account_id, automation_id
            FROM setup_candidates
            WHERE automation_id=?
            ORDER BY generated_ms DESC LIMIT 1
        """, (automation_id,)).fetchone()
    if not row:
        return None
    cols = [
        "setup_id", "symbol", "direction", "timeframe", "strategy", "current_state",
        "reason", "vwap", "breakout_price", "retest_state", "suggested_sl",
        "suggested_tp1", "suggested_tp2", "risk_reward", "confidence_pct",
        "thesis", "generated_ms", "expires_ms", "status", "waiting_for",
        "next_required_event", "priority", "user_id", "account_id", "automation_id"
    ]
    return dict(zip(cols, row))



# ============================================================
# US MARKET INTELLIGENCE PERSISTENCE & HELPERS
# ============================================================
def upsert_us_stock_intelligence(st: dict) -> None:
    c = _connect()
    now_ms = int(time.time() * 1000)
    cols = [
        "symbol", "price", "change_pct", "direction", "bias", "confidence",
        "sector", "industry", "market_regime", "volume_state", "rvol", "order_flow",
        "vwap", "vwap_state", "volatility", "liquidity", "news_state", "news_direction",
        "news_impact", "options_state", "gex_state", "bingx_state", "bingx_symbol",
        "overnight_bias", "candidate_state", "waiting_for", "trade_direction",
        "targets_json", "rr_ratio", "data_freshness", "updated_at"
    ]
    placeholders = ", ".join(["?"] * len(cols))
    import json as _j
    vals = (
        st["symbol"].strip().upper(),
        float(st.get("price") or 0.0),
        float(st.get("change_pct") or 0.0),
        st.get("direction") or "UNDEFINED",
        st.get("bias") or "NEUTRAL",
        float(st.get("confidence") or 0.0),
        st.get("sector") or "UNKNOWN",
        st.get("industry") or "UNKNOWN",
        st.get("market_regime") or "UNDEFINED",
        st.get("volume_state") or "NORMAL",
        float(st.get("rvol") or 1.0),
        st.get("order_flow") or "NOT_AVAILABLE",
        float(st.get("vwap") or 0.0),
        st.get("vwap_state") or "NEAR",
        float(st.get("volatility") or 0.0),
        st.get("liquidity") or "NORMAL",
        st.get("news_state") or "NEUTRAL",
        st.get("news_direction") or "NEUTRAL",
        st.get("news_impact") or "LOW",
        st.get("options_state") or "NOT_AVAILABLE",
        st.get("gex_state") or "NOT_AVAILABLE",
        st.get("bingx_state") or "NOT_AVAILABLE",
        st.get("bingx_symbol") or "",
        st.get("overnight_bias") or "NEUTRAL",
        st.get("candidate_state") or "IDLE",
        st.get("waiting_for") or "SETUP_MATURATION",
        st.get("trade_direction") or "NO_TRADE",
        _j.dumps(st.get("targets") or []),
        float(st.get("rr_ratio") or 0.0),
        st.get("data_freshness") or "LIVE",
        int(st.get("updated_at") or now_ms)
    )
    with _lock:
        c.execute(f"INSERT OR REPLACE INTO us_stock_intelligence_state({', '.join(cols)}) VALUES({placeholders})", vals)
        c.commit()

def get_us_stock_intelligence(symbol: str) -> dict | None:
    c = _connect()
    sym = symbol.strip().upper()
    cols = [
        "symbol", "price", "change_pct", "direction", "bias", "confidence",
        "sector", "industry", "market_regime", "volume_state", "rvol", "order_flow",
        "vwap", "vwap_state", "volatility", "liquidity", "news_state", "news_direction",
        "news_impact", "options_state", "gex_state", "bingx_state", "bingx_symbol",
        "overnight_bias", "candidate_state", "waiting_for", "trade_direction",
        "targets_json", "rr_ratio", "data_freshness", "updated_at"
    ]
    with _lock:
        row = c.execute("SELECT * FROM us_stock_intelligence_state WHERE symbol=?", (sym,)).fetchone()
    if not row:
        return None
    d = dict(zip(cols, row))
    import json as _j
    d["targets"] = _j.loads(d.pop("targets_json") or "[]")
    return d

def list_us_stock_intelligence(filter_bias: str | None = None, min_rvol: float | None = None, bingx_only: bool = False) -> list[dict]:
    c = _connect()
    q = "SELECT * FROM us_stock_intelligence_state WHERE 1=1"
    args = []
    if filter_bias:
        q += " AND bias=?"
        args.append(filter_bias.strip().upper())
    if min_rvol:
        q += " AND rvol>=?"
        args.append(float(min_rvol))
    if bingx_only:
        q += " AND bingx_state='VERIFIED'"
    q += " ORDER BY rvol DESC"
    cols = [
        "symbol", "price", "change_pct", "direction", "bias", "confidence",
        "sector", "industry", "market_regime", "volume_state", "rvol", "order_flow",
        "vwap", "vwap_state", "volatility", "liquidity", "news_state", "news_direction",
        "news_impact", "options_state", "gex_state", "bingx_state", "bingx_symbol",
        "overnight_bias", "candidate_state", "waiting_for", "trade_direction",
        "targets_json", "rr_ratio", "data_freshness", "updated_at"
    ]
    with _lock:
        rows = c.execute(q, args).fetchall()
    import json as _j
    res = []
    for r in rows:
        d = dict(zip(cols, r))
        d["targets"] = _j.loads(d.pop("targets_json") or "[]")
        res.append(d)
    return res

def upsert_us_top_100_universe(stocks: list[dict]) -> None:
    c = _connect()
    now_ms = int(time.time() * 1000)
    cols = [
        "symbol", "rank", "company_name", "exchange", "sector", "industry",
        "market_cap", "average_volume", "volatility", "liquidity_score",
        "bingx_available", "bingx_symbol", "data_provider", "data_freshness", "last_updated"
    ]
    placeholders = ", ".join(["?"] * len(cols))
    with _lock:
        for s in stocks:
            vals = (
                s["symbol"].strip().upper(),
                int(s.get("rank") or 999),
                s.get("company_name") or s["symbol"],
                s.get("exchange") or "NASDAQ",
                s.get("sector") or "TECHNOLOGY",
                s.get("industry") or "",
                float(s.get("market_cap") or 0.0),
                float(s.get("average_volume") or 0.0),
                float(s.get("volatility") or 0.0),
                float(s.get("liquidity_score") or 0.0),
                1 if s.get("bingx_available") else 0,
                s.get("bingx_symbol") or "",
                s.get("data_provider") or "YAHOO_REALTIME",
                s.get("data_freshness") or "LIVE",
                int(s.get("last_updated") or now_ms)
            )
            c.execute(f"INSERT OR REPLACE INTO us_top_100_universe({', '.join(cols)}) VALUES({placeholders})", vals)
        c.commit()

def get_us_top_100_universe() -> list[dict]:
    c = _connect()
    cols = [
        "symbol", "rank", "company_name", "exchange", "sector", "industry",
        "market_cap", "average_volume", "volatility", "liquidity_score",
        "bingx_available", "bingx_symbol", "data_provider", "data_freshness", "last_updated"
    ]
    with _lock:
        rows = c.execute(f"SELECT {', '.join(cols)} FROM us_top_100_universe ORDER BY rank ASC").fetchall()
    res = []
    for r in rows:
        d = dict(zip(cols, r))
        d["bingx_available"] = bool(d["bingx_available"])
        res.append(d)
    return res

def upsert_us_sector_state(sectors: list[dict]) -> None:
    c = _connect()
    now_ms = int(time.time() * 1000)
    cols = [
        "sector", "return_pct", "relative_strength_spy", "volume", "breadth_pct",
        "momentum", "regime", "news_intensity", "news_sentiment", "top_movers_json", "updated_at"
    ]
    placeholders = ", ".join(["?"] * len(cols))
    import json as _j
    with _lock:
        for s in sectors:
            vals = (
                s["sector"].strip().upper(),
                float(s.get("return_pct") or 0.0),
                float(s.get("relative_strength_spy") or 0.0),
                float(s.get("volume") or 0.0),
                float(s.get("breadth_pct") or 50.0),
                float(s.get("momentum") or 0.0),
                s.get("regime") or "ROTATING",
                s.get("news_intensity") or "NORMAL",
                s.get("news_sentiment") or "NEUTRAL",
                _j.dumps(s.get("top_movers") or []),
                int(s.get("updated_at") or now_ms)
            )
            c.execute(f"INSERT OR REPLACE INTO us_sector_state({', '.join(cols)}) VALUES({placeholders})", vals)
        c.commit()

def list_us_sectors() -> list[dict]:
    c = _connect()
    cols = [
        "sector", "return_pct", "relative_strength_spy", "volume", "breadth_pct",
        "momentum", "regime", "news_intensity", "news_sentiment", "top_movers_json", "updated_at"
    ]
    with _lock:
        rows = c.execute(f"SELECT {', '.join(cols)} FROM us_sector_state ORDER BY return_pct DESC").fetchall()
    import json as _j
    res = []
    for r in rows:
        d = dict(zip(cols, r))
        d["top_movers"] = _j.loads(d.pop("top_movers_json") or "[]")
        res.append(d)
    return res

def insert_us_news_event(event: dict) -> None:
    c = _connect()
    now_ms = int(time.time() * 1000)
    cols = [
        "event_id", "headline", "timestamp", "source", "event_type",
        "entities_json", "companies_json", "sector", "sentiment", "direction",
        "impact", "confidence", "market_reaction", "created_at"
    ]
    placeholders = ", ".join(["?"] * len(cols))
    import json as _j
    vals = (
        event["event_id"],
        event.get("headline") or "",
        int(event.get("timestamp") or now_ms),
        event.get("source") or "FINANCIAL_FEED",
        event.get("event_type") or "NEWS",
        _j.dumps(event.get("entities") or []),
        _j.dumps(event.get("companies") or []),
        event.get("sector") or "MARKET_WIDE",
        event.get("sentiment") or "NEUTRAL",
        event.get("direction") or "NEUTRAL",
        event.get("impact") or "MEDIUM",
        float(event.get("confidence") or 0.8),
        event.get("market_reaction") or "CONFIRMED",
        int(event.get("created_at") or now_ms)
    )
    with _lock:
        c.execute(f"INSERT OR REPLACE INTO us_news_events({', '.join(cols)}) VALUES({placeholders})", vals)
        c.commit()

def list_us_news_events(limit: int = 50, sector: str | None = None, symbol: str | None = None) -> list[dict]:
    c = _connect()
    q = "SELECT * FROM us_news_events WHERE 1=1"
    args = []
    if sector:
        q += " AND sector=?"
        args.append(sector.strip().upper())
    if symbol:
        q += " AND (companies_json LIKE ? OR entities_json LIKE ?)"
        pattern = f"%{symbol.strip().upper()}%"
        args.extend([pattern, pattern])
    q += " ORDER BY timestamp DESC LIMIT ?"
    args.append(limit)
    cols = [
        "event_id", "headline", "timestamp", "source", "event_type",
        "entities_json", "companies_json", "sector", "sentiment", "direction",
        "impact", "confidence", "market_reaction", "created_at"
    ]
    with _lock:
        rows = c.execute(q, args).fetchall()
    import json as _j
    res = []
    for r in rows:
        d = dict(zip(cols, r))
        d["entities"] = _j.loads(d.pop("entities_json") or "[]")
        d["companies"] = _j.loads(d.pop("companies_json") or "[]")
        res.append(d)
    return res

def upsert_bingx_tradfi_contracts(contracts: list[dict]) -> None:
    c = _connect()
    now_ms = int(time.time() * 1000)
    cols = [
        "underlying_symbol", "bingx_symbol", "status", "tick_size", "quantity_step",
        "minimum_quantity", "minimum_notional", "contract_size", "max_leverage",
        "funding_rate", "price_precision", "quantity_precision", "last_verified"
    ]
    placeholders = ", ".join(["?"] * len(cols))
    with _lock:
        for ct in contracts:
            vals = (
                ct["underlying_symbol"].strip().upper(),
                ct["bingx_symbol"].strip().upper(),
                ct.get("status") or "VERIFIED",
                float(ct.get("tick_size") or 0.01),
                float(ct.get("quantity_step") or 0.01),
                float(ct.get("minimum_quantity") or 0.01),
                float(ct.get("minimum_notional") or 5.0),
                float(ct.get("contract_size") or 1.0),
                float(ct.get("max_leverage") or 20.0),
                float(ct.get("funding_rate") or 0.0),
                int(ct.get("price_precision") or 2),
                int(ct.get("quantity_precision") or 2),
                int(ct.get("last_verified") or now_ms)
            )
            c.execute(f"INSERT OR REPLACE INTO bingx_tradfi_registry({', '.join(cols)}) VALUES({placeholders})", vals)
        c.commit()

def get_bingx_tradfi_registry() -> dict[str, dict]:
    c = _connect()
    cols = [
        "underlying_symbol", "bingx_symbol", "status", "tick_size", "quantity_step",
        "minimum_quantity", "minimum_notional", "contract_size", "max_leverage",
        "funding_rate", "price_precision", "quantity_precision", "last_verified"
    ]
    with _lock:
        rows = c.execute(f"SELECT {', '.join(cols)} FROM bingx_tradfi_registry").fetchall()
    return {r[0]: dict(zip(cols, r)) for r in rows}

def get_bingx_tradfi_contract(underlying_symbol: str) -> dict | None:
    c = _connect()
    sym = underlying_symbol.strip().upper()
    cols = [
        "underlying_symbol", "bingx_symbol", "status", "tick_size", "quantity_step",
        "minimum_quantity", "minimum_notional", "contract_size", "max_leverage",
        "funding_rate", "price_precision", "quantity_precision", "last_verified"
    ]
    with _lock:
        row = c.execute(f"SELECT {', '.join(cols)} FROM bingx_tradfi_registry WHERE underlying_symbol=?", (sym,)).fetchone()
    return dict(zip(cols, row)) if row else None


# ============================================================
# GOD EYE SYNTHETIC DATA PURGE (CRITICAL HARDENING)
# ============================================================
def purge_synthetic_users() -> dict:
    """Purge all fake, mock, and demo user records from SQLite database."""
    c = _connect()
    with _lock:
        synthetic_users = c.execute("""
            SELECT id, email, display_name FROM users
            WHERE id != 1 AND (
                LOWER(COALESCE(display_name, '')) LIKE '%offline%' OR
                LOWER(COALESCE(display_name, '')) LIKE '%brother%' OR
                LOWER(COALESCE(display_name, '')) LIKE '%test%' OR
                LOWER(COALESCE(display_name, '')) LIKE '%demo%' OR
                LOWER(COALESCE(display_name, '')) LIKE '%godeye%' OR
                LOWER(COALESCE(email, '')) LIKE '%offline%' OR
                LOWER(COALESCE(email, '')) LIKE '%test%' OR
                LOWER(COALESCE(email, '')) LIKE '%demo%' OR
                LOWER(COALESCE(email, '')) LIKE '%godeye%'
            )
        """).fetchall()

        syn_ids = [r[0] for r in synthetic_users]
        if syn_ids:
            id_placeholders = ",".join(["?"] * len(syn_ids))
            c.execute(f"DELETE FROM users WHERE id IN ({id_placeholders})", syn_ids)
            for tbl in ["exchange_accounts", "user_bingx_credentials", "user_positions", "positions", "automations", "notifications", "user_devices"]:
                try:
                    c.execute(f"DELETE FROM {tbl} WHERE user_id IN ({id_placeholders})", syn_ids)
                except sqlite3.OperationalError:
                    pass
            c.commit()

        remaining = c.execute("SELECT id, user_uid, role, display_name, email FROM users").fetchall()

    return {
        "purged_count": len(syn_ids),
        "purged_user_ids": syn_ids,
        "remaining_users_count": len(remaining),
        "remaining_users": [{"id": r[0], "user_uid": r[1], "role": r[2], "name": r[3], "email": r[4]} for r in remaining]
    }



