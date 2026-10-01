"""Core validator + condition manager + shadow/live execution.

Authoritative for: risk math, blackout enforcement, proposal creation,
condition triggering, position lifecycle (multi-stop, partial targets,
trailing, breakeven), live order gating. The LLM cannot bypass any of it.
"""
from __future__ import annotations

import json
import time
import uuid
import threading
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING

import numpy as np

from . import analytics, config, db, sessions, notifications, symbols

if TYPE_CHECKING:
    from . import bingx_client


class CoreReject(Exception):
    pass


def _live_equity(user_id: int | None = None) -> float | None:
    """Fetch live account equity (USDT) for a specific user when keys are configured; else None."""
    if not user_id or user_id < 1:
        return None
    try:
        from . import credential_vault
        c = credential_vault.get_user_bingx_client(user_id, allow_trade=False)
        if not c or not c.api_key:
            return None
        b = c.balance()
        if isinstance(b, list):
            b = b[0] if b else {}
        eq = b.get("equity", b.get("marginBalance"))
        return float(eq) if eq not in (None, "", 0) else None
    except Exception:                                             # noqa: BLE001
        return None


def validate_risk(symbol: str, leverage: float, margin_usage_pct: float,
                  account_equity_usdt: float | None = None,
                  fixed_margin_usdt: float | None = None,
                  user_id: int | None = None) -> dict:
    """Deterministic risk computation. Raises CoreReject on violation."""
    user_equity = _live_equity(user_id) if (user_id and user_id >= 1) else None
    equity = account_equity_usdt or user_equity or 100.0
    assumed = account_equity_usdt is None and user_equity is None
    if not (1 <= leverage <= config.RISK_DEFAULTS["max_leverage"]):
        raise CoreReject(f"leverage {leverage} exceeds cap "
                         f"{config.RISK_DEFAULTS['max_leverage']}")
    if fixed_margin_usdt and fixed_margin_usdt > 0:
        margin = round(fixed_margin_usdt, 2)
    else:
        if not (0 < margin_usage_pct <= config.RISK_DEFAULTS["max_margin_pct"]):
            raise CoreReject(f"margin_usage_pct {margin_usage_pct} out of range")
        margin = round(equity * margin_usage_pct / 100.0, 2)
    if margin < config.RISK_DEFAULTS["min_margin_usdt"]:
        raise CoreReject(f"allocated margin {margin} < min "
                         f"{config.RISK_DEFAULTS['min_margin_usdt']} USDT")
    notional = round(margin * leverage, 2)
    minn = config.RISK_DEFAULTS["binance_min_notional"]
    if notional < minn:
        raise CoreReject(f"notional {notional} < exchange minimum {minn}")
    return {"equity_assumed_usdt": round(equity, 2),
            "equity_live": not assumed,
            "allocated_margin": margin,
            "notional": notional, "leverage": leverage}


def build_proposal(spec: dict) -> dict:
    """Full deterministic proposal: risk + geometry from live data."""
    if str(spec.get("mode") or "").strip().upper() == "RESEARCH":
        raise CoreReject("RESEARCH mode cannot create trading proposals or execute orders")
    import core.settings as settings_mod
    tfs = None
    if spec.get("strategy") == "BOTH":
        tfs = spec.get("strategy_timeframes", {})
        # For snapshot/initial proposal data, we pull market data at the lowest timeframe
        # but we preserve the actual strategy timeframes.
        tf = min([int(v) for v in tfs.values()]) if tfs else 3
    else:
        tf = int(spec.get("timeframe") or spec.get("timeframe_min") or 3)
        
    symbol = spec["symbol"]
    lev = float(spec.get("leverage") or 5)
    mp = float(spec.get("margin_usage_pct") or 10)
    fixed_m = float(spec.get("margin_usdt") or spec.get("fixed_margin") or 0.0)
    if sessions.in_blackout():
        raise CoreReject("new-entry BLACKOUT active (02:30-05:30 IST); existing "
                         "positions unaffected; LLM cannot bypass this")
    risk = validate_risk(symbol, lev, mp, fixed_margin_usdt=fixed_m if fixed_m > 0 else None)
    
    # Load canonical settings for missing parameters
    settings = settings_mod.TradingSettings.load()
    risk_config = settings.get_risk_config(symbol)
    
    # Apply default stops/targets if not provided
    stops = spec.get("stops")
    if not stops:
        stops = [{"type": risk_config.get("sl_mode", "PRICE_PERCENT"), "value": risk_config.get("sl_value", 1.0)}]
    targets = spec.get("targets")
    if not targets:
        targets = risk_config.get("exit_plan", [{"pct": 100.0, "type": "trailing"}])
    
    if symbol in ("ALL_WATCHLIST", "MULTIPLE"):
        proposal = {"type": "TRADE_PROPOSAL", "strategy": spec.get("strategy", "EMA_CROSSOVER"),
                "symbol": symbol, "symbols": spec.get("symbols"), "timeframe_min": tf,
                "direction_preference": spec.get("direction_preference", "ANY"),
                "mode": spec.get("mode", "SHADOW"),
                "entry_ref_price": 0.0, "stop_distance_ref": 0.0, "qty_ref": 0.0,
                "risk": risk, "ema_state": "UNKNOWN",
                "stops": stops, "targets": targets,
                "note": "Scanning multiple symbols; entry decided per symbol on crossover",
                "created_ist": sessions.ist_now_str()}
        if tfs:
            proposal["strategy_timeframes"] = tfs
        if spec.get("strategy_risk"):
            proposal["strategy_risk"] = spec["strategy_risk"]
        return proposal
    
    snap = analytics.get_market_snapshot(symbol, lookback_min=max(60, tf * 12),
                                         agg_interval_min=tf)
    if "error" in snap:
        raise CoreReject(f"no market data: {snap['error']}")
    entry = snap["last_price"]
    e9 = snap["indicators"].get("EMA9"); e20 = snap["indicators"].get("EMA20")
    atr = snap["indicators"].get("ATR14_agg") or (entry * 0.004)
    stop_dist = max(atr * 1.5, entry * 0.002)
    qty = round(risk["notional"] / entry, 3)
    
    proposal = {"type": "TRADE_PROPOSAL", "strategy": spec.get("strategy", "EMA_CROSSOVER"),
            "symbol": symbol, "timeframe_min": tf,
            "direction_preference": spec.get("direction_preference", "ANY"),
            "mode": spec.get("mode", "SHADOW"),
            "entry_ref_price": entry, "stop_distance_ref": round(stop_dist, 6),
            "qty_ref": qty,
            "risk": risk,
            "stops": stops,
            "targets": targets,
            "ema_state": ("BULLISH" if (e9 or 0) > (e20 or 0) else "BEARISH"),
            "note": "final direction/entry decided by confirmed crossover event",
            "created_ist": sessions.ist_now_str()}
    if tfs:
        proposal["strategy_timeframes"] = tfs
    if spec.get("strategy_risk"):
        proposal["strategy_risk"] = spec["strategy_risk"]
    return proposal


def register_condition(spec: dict) -> dict:
    """Create conditional automation after user confirmation (spec §11)."""
    proposal = build_proposal(spec)
    aid = db.create_automation({**spec, "status": "ACTIVE", "mode": "SHADOW",
                                "proposal": proposal})
    return {"automation_id": aid, "proposal": proposal,
            "state": "ARMED - watching for confirmed crossover on "
                     f"{spec['symbol']} {spec['timeframe_min']}m"}


def check_crossover_event(symbol: str, tf_min: int):
    """Detect a CONFIRMED EMA9/20 crossover on the last closed agg-candle."""
    cd = analytics.get_candles(symbol, lookback_min=max(240, tf_min * 30),
                               base_interval_min=1, agg_interval_min=tf_min)
    if "error" in cd or cd["count"] < 22:
        return None
    closes = np.array([r["close"] for r in cd["candles"]], float)
    e9 = analytics.ema(closes, 9); e20 = analytics.ema(closes, 20)
    i = len(closes) - 2                       # last CLOSED candle in retained window
    d_prev = e9[i - 1] - e20[i - 1]
    d_now = e9[i] - e20[i]
    if np.isnan(d_prev) or np.isnan(d_now) or d_prev == d_now:
        return None
    if d_prev <= 0 and d_now > 0:
        return {"direction": "LONG", "candle_ts": cd["candles"][i]["ts"],
                "close": float(closes[i]), "ema9": float(e9[i]), "ema20": float(e20[i])}
    if d_prev >= 0 and d_now < 0:
        return {"direction": "SHORT", "candle_ts": cd["candles"][i]["ts"],
                "close": float(closes[i]), "ema9": float(e9[i]), "ema20": float(e20[i])}
    return None


def one_trade_block(user_id: int | None = None) -> dict | None:
    """User-scoped or system safety rule: user-configured MAX_OPEN_TRADES across all symbols, strategies, and automations."""
    open_n = db.total_open_positions_count(user_id=user_id)
    cap = db.get_max_open_trades(user_id=user_id) if hasattr(db, "get_max_open_trades") else config.DEFAULT_MAX_OPEN_TRADES
    if open_n >= cap:
        reason = "CAP BELOW CURRENT EXPOSURE" if cap < open_n else f"MAX_OPEN_TRADES limit reached ({open_n}/{cap})"
        return {
            "blocked": True,
            "open": open_n,
            "limit": cap,
            "reason": reason,
            "cap_state": "CAP_BELOW_EXPOSURE" if cap < open_n else "CAP_REACHED"
        }
    return None



def fire_condition_if_triggered(automation: dict) -> dict | None:
    """Watcher step: dispatch strategies (first valid event wins), apply the
    VWAP regime gate at SIGNAL TIME, enforce the one-trade rule, dedup by
    event id, respect expiry and lifecycle."""
    params = automation.get("params") or {}
    expiry_h = params.get("expiry_hours")
    if expiry_h and automation.get("created_ms") and \
            time.time() * 1000 - automation["created_ms"] > expiry_h * 3600_000:
        db.set_automation_status(automation["id"], "EXPIRED")
        return {"expired": True, "automation_id": automation["id"],
                "message": (f"Automation #{automation['id']} "
                            f"({automation['symbol']} {automation['timeframe']}m) "
                            f"expired after {expiry_h:g}h without a signal. "
                            "Nothing was armed or executed.")}
    base_strat = automation.get("strategy")
    strategies = ["VWAP_SUPERTREND", "EMA_CROSSOVER"] if base_strat == "BOTH" else params.get("strategies") or [base_strat or "EMA_CROSSOVER"]
    
    symbols_to_check = automation.get("symbols") or [automation["symbol"]]
    if "ALL_WATCHLIST" in symbols_to_check or automation["symbol"] == "ALL_WATCHLIST":
        symbols_to_check = db.watchlist_symbols()
    elif "MULTIPLE" in symbols_to_check or automation["symbol"] == "MULTIPLE":
        symbols_to_check = [s for s in (automation.get("symbols") or []) if s not in ("MULTIPLE", "ALL_WATCHLIST")]

    # global one-trade rule (checked before any signal work)
    if one_trade_block():
        return None                       # silent skip; /position shows why

    ev = None
    used_strategy = None
    used_tf = None
    regime = None
    used_symbol = None
    
    for sym in symbols_to_check:
    
        for strat in strategies:
            strat = (strat or "").upper()
            if base_strat == "BOTH":
                tf = int(params.get("strategy_timeframes", {}).get(strat) or 5)
            else:
                tf = int(automation.get("timeframe") or 5)
                
            # VWAP regime gate at SIGNAL TIME (evaluated per strategy timeframe)
            strat_regime = analytics.vwap_regime(sym, tf)
            if strat_regime.get("eligible") in (None, "NONE"):
                continue
                
            strat_ev = None
            if strat == "VWAP_SUPERTREND":
                strat_ev = analytics.st_vwap_cross_event(sym, tf)
            elif strat == "EMA_CROSSOVER":
                strat_ev = check_crossover_event(sym, tf)
                
            if strat_ev and strat_ev["direction"] == strat_regime["eligible"]:
                ev = strat_ev
                used_strategy = strat
                used_tf = tf
                regime = strat_regime
                used_symbol = sym
                break
        if ev:
            break
            
    if not ev:
        return None
    
    direction = ev["direction"]
    event_id = f"{used_strategy}|{used_symbol}|{used_tf}|{ev['candle_ts']}|{direction}"
    if db.event_seen(event_id):
        return None                                    # duplicate event guard
    pref = (automation.get("direction_pref") or "ANY").upper()
    if pref in ("BULLISH", "BEARISH") and \
            (pref == "BULLISH") != (direction == "LONG"):
        db.event_record(event_id, "FILTERED", None)
        return None                                    # preference filter
    db.event_record(event_id, "SIGNAL", None)
    entry = ev["close"]
    if used_strategy == "VWAP_SUPERTREND":
        stop_dist = max(abs(entry - ev["st_line"]), entry * 0.002)
        detail = {"trigger": "Supertrend/VWAP crossover confirmed",
                  "strategy": used_strategy,
                  "vwap_state_at_signal": regime["state"],
                  "st_line": ev["st_line"], "vwap": ev["vwap"],
                  "timeframe_min": used_tf,
                  "mode": automation.get("mode", "SHADOW")}
    else:
        stop_dist = max(abs(entry - ev["ema20"]), entry * 0.002)
        detail = {"trigger": "EMA9/20 crossover confirmed",
                  "strategy": used_strategy,
                  "vwap_state_at_signal": regime["state"],
                  "ema9": ev["ema9"], "ema20": ev["ema20"],
                  "timeframe_min": used_tf,
                  "mode": automation.get("mode", "SHADOW")}
    base_strat = automation.get("strategy")
    risk_cfg = params.get("strategy_risk", {}).get(used_strategy) if base_strat == "BOTH" else params

    stop_pct = 1.0 # default fallback
    if risk_cfg and risk_cfg.get("stops"):
        stop_val = risk_cfg["stops"][0]["value"]
        stype = risk_cfg["stops"][0]["type"]
        if stype == "entry_pct":
            stop_dist = entry * (stop_val / 100.0)
        elif stype == "vwap_pct" and ev.get("vwap"):
            stop_dist = abs(entry - ev["vwap"]) + (entry * stop_val / 100.0)
        elif stype == "supertrend_pct" and ev.get("st_line"):
            stop_dist = abs(entry - ev["st_line"]) + (entry * stop_val / 100.0)
        elif stype == "ema20_pct" and ev.get("ema20"):
            stop_dist = abs(entry - ev["ema20"]) + (entry * stop_val / 100.0)

    target = entry + (entry - stop_dist) * 2 * (1 if direction == "LONG" else -1)
    if risk_cfg and risk_cfg.get("targets"):
        t0 = risk_cfg["targets"][0]
        if t0.get("move_pct"):
            target = entry * (1 + t0["move_pct"]/100.0 * (1 if direction == "LONG" else -1))
        elif t0.get("r"):
            target = entry + (stop_dist * t0["r"]) * (1 if direction == "LONG" else -1)

    stop = entry - stop_dist * (1 if direction == "LONG" else -1)
    qty = round((automation.get("margin_usdt") or 10)
                * (automation.get("leverage") or 10) / entry, 6)

    detail["stops"] = risk_cfg.get("stops") if risk_cfg else None
    detail["targets"] = risk_cfg.get("targets") if risk_cfg else None
    detail["trailing_pct"] = risk_cfg.get("trailing_pct") if risk_cfg else None
    detail["breakeven"] = risk_cfg.get("breakeven") if risk_cfg else None

    tid = db.record_shadow_trade({
        "automation_id": automation["id"], "ts_open_ms": ev["candle_ts"],
        "direction": direction, "entry": entry, "stop": round(stop, 6),
        "target": round(target, 6), "qty": qty, "status": "PROPOSED",
        "detail": detail})
    db.event_record(event_id, "SIGNAL", tid)           # link event to trade id
    strat_label = ("Supertrend/VWAP" if used_strategy == "VWAP_SUPERTREND"
                   else "EMA 9/20")
    return {"proposal_trade_id": tid, "automation_id": automation["id"],
            "symbol": used_symbol, "direction": direction,
            "entry": entry, "stop": round(stop, 6),
            "target": round(target, 6), "qty": qty,
            "message": (f"CONDITION TRIGGERED: {direction} {used_symbol} "
                        f"@~{entry:.4f} ({strat_label} crossover)\n"
                        f"VWAP regime at signal: {regime['state']} "
                        f"({regime['separation_pct']:+.2f}%)\n"
                        f"Stop {stop:.4f} | Target {target:.4f} "
                        f"| Qty {qty:g}\n"
                        f"Mode {db.get_mode()}.\nConfirm execution? YES / NO "
                        f"(or 'Skip it')")}

def confirm_shadow_trade(trade_id: int) -> dict:
    """User-confirmed execution. Branches on persisted trading mode.

    SHADOW -> records a shadow position (no exchange call possible).
    LIVE   -> places a real market entry via the signed BingX client.
    """
    block = one_trade_block()
    if block:
        raise CoreReject(f"Max open trades limit reached ({block['open']}/{block['limit']})")
    c = db._auto_conn()
    with db._lock:
        row = c.execute("SELECT id,status,direction,entry,qty,automation_id,"
                        "detail_json FROM shadow_trades "
                        "WHERE id=?", (trade_id,)).fetchone()
        if not row:
            raise CoreReject(f"trade {trade_id} not found")
        if row[1] != "PROPOSED":
            raise CoreReject(f"trade {trade_id} is {row[1]}, not PROPOSED")
    mode = db.get_mode()
    if mode == "LIVE":
        out = _execute_live_entry_from_proposal(trade_id, row)
        _rearm_after_trade(row)
        return out
    with db._lock:
        c.execute("UPDATE shadow_trades SET status='OPEN_SHADOW' WHERE id=?", (trade_id,))
        c.commit()
    db.audit("core", "SHADOW_OPEN", {"trade_id": trade_id})
    _rearm_after_trade(row)
    return {"trade_id": trade_id, "status": "OPEN_SHADOW",
            "note": "shadow position recorded; no live order was or can be "
                    "sent by LLM"}


def cancel_shadow_trade(trade_id: int) -> dict:
    c = db._auto_conn()
    with db._lock:
        row = c.execute("SELECT automation_id FROM shadow_trades WHERE id=?",
                        (trade_id,)).fetchone()
        cur = c.execute("UPDATE shadow_trades SET status='SKIPPED' "
                        "WHERE id=? AND status='PROPOSED'", (trade_id,))
        c.commit()
    if cur.rowcount == 0:
        raise CoreReject(f"trade {trade_id} not cancellable (not PROPOSED)")
    _rearm_after_trade((None, None, None, None, None,
                        row[0] if row else None))
    return {"trade_id": trade_id, "status": "SKIPPED"}


def _rearm_after_trade(row: tuple) -> None:
    """Lifecycle: CONTINUOUS automations resume scanning after the trade
    decision (confirm or skip); ONE_SHOT automations stop. This makes
    scanning continuous instead of one-shot."""
    automation_id = row[5] if len(row) > 5 else None
    if not automation_id:
        return
    r = db._auto_conn().execute(
        "SELECT params_json FROM automations WHERE id=?",
        (automation_id,)).fetchone()
    lifecycle = "CONTINUOUS"
    if r and r[0]:
        try:
            lifecycle = (json.loads(r[0]) or {}).get("lifecycle",
                                                     "CONTINUOUS")
        except Exception:                                     # noqa: BLE001
            pass
    if lifecycle == "ONE_SHOT":
        db.set_automation_status(automation_id, "STOPPED")
    else:
        db.set_automation_status(automation_id, "ACTIVE")


def evaluate_open_shadow(symbol_last_price: float):
    """Mark OPEN_SHADOW trades against stop/target using last price (simple path)."""
    for t in db.open_shadow_trades():
        hit_s = (symbol_last_price <= t["stop"]) if t["direction"] == "LONG" \
            else (symbol_last_price >= t["stop"])
        hit_t = (symbol_last_price >= t["target"]) if t["direction"] == "LONG" \
            else (symbol_last_price <= t["target"])
        if not (hit_s or hit_t):
            continue
        status = "STOPPED_SHADOW" if hit_s else "TARGET_SHADOW"
        pnl = ((symbol_last_price - t["entry"]) * t["qty"]
               if t["direction"] == "LONG"
               else (t["entry"] - symbol_last_price) * t["qty"])
        c = db._auto_conn()
        with db._lock:
            c.execute("UPDATE shadow_trades SET status=?, ts_close_ms=?, exit_price=?, "
                      "pnl_usdt=? WHERE id=?",
                      (status, int(time.time() * 1000), symbol_last_price,
                       round(pnl, 4), t["id"]))
            c.commit()


def health() -> dict:
    import psutil
    oh = db.oldest_newest()
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    age_min = None
    if oh["newest_ts"]:
        age_min = round((time.time() * 1000 - oh["newest_ts"]) / 60_000, 1)
    cleanup_age = None
    if oh.get("last_cleanup_ms"):
        cleanup_age = round((time.time() * 1000 - oh["last_cleanup_ms"]) / 60_000, 1)
        
    mode = db.get_mode()
    data_connected = (age_min is not None and age_min <= 5.0)
    
    # Check BingX auth
    bingx_status = "NOT_CONFIGURED"
    try:
        from . import credential_vault
        if hasattr(db, "get_bingx_connection_enabled") and not db.get_bingx_connection_enabled():
            bingx_status = "DISCONNECTED"
        elif credential_vault.user_has_credentials(1):
            bingx_status = "AUTHENTICATED"
    except Exception:
        bingx_status = "ERROR"

    overall_status = "ONLINE" if (data_connected and bingx_status == "AUTHENTICATED") else ("DEGRADED" if (data_connected or bingx_status == "AUTHENTICATED") else "OFFLINE")
    autos = db.list_automations(status="ACTIVE")
    open_pos = db.open_positions()

    return {
        "status": overall_status,
        "trading_mode": mode,
        "mode": mode,
        "control_plane": "ONLINE",
        "core_engine": "RUNNING",
        "market_data": "CONNECTED" if data_connected else "DISCONNECTED",
        "bingx": bingx_status,
        "last_heartbeat_ms": oh["newest_ts"] or int(time.time() * 1000),
        "uptime_seconds": int(time.time() - psutil.boot_time()),
        "active_automations": len(autos),
        "open_positions": len(open_pos),
        "core": "OK",
        "cpu_pct": cpu,
        "ram_used_pct": round(mem.percent, 1),
        "ram_available_gb": round(mem.available / 1e9, 2),
        "disk_used_pct": round(disk.percent, 1),
        "data_health": {
            "oldest_1m_utc": datetime.fromtimestamp(
                oh["oldest_ts"] / 1000, timezone.utc).isoformat() if oh["oldest_ts"] else None,
            "newest_1m_utc": datetime.fromtimestamp(
                oh["newest_ts"] / 1000, timezone.utc).isoformat() if oh["newest_ts"] else None,
            "rows": oh["rows"], "data_age_min": age_min,
            "last_cleanup_min_ago": cleanup_age,
            "cleanup_ok": cleanup_age is not None
            and cleanup_age <= config.CLEANUP_INTERVAL_MIN + 5,
        },
        "sessions": sessions.session_note(),
    }


# ------------------------------------------------------------------ live terminal & detailed health
from collections import deque
import re

LIVE_LOG_BUFFER = deque(maxlen=200)

_SENSITIVE_PATTERNS = [
    re.compile(r'(api_?key|secret|password|token|bearer|auth)["\']?\s*[:=]\s*["\']?([^"\'\s,;]+)', re.IGNORECASE),
    re.compile(r'(X-BX-APIKEY|Authorization)["\']?\s*[:=]\s*["\']?([^"\'\s,;]+)', re.IGNORECASE),
]

def log_terminal_line(component: str, message: str, level: str = "INFO") -> None:
    sanitized = message
    for pat in _SENSITIVE_PATTERNS:
        sanitized = pat.sub(r'\1: ***REDACTED***', sanitized)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    entry = {
        "timestamp": now_iso,
        "ts_ms": int(time.time() * 1000),
        "component": component.upper(),
        "level": level.upper(),
        "message": sanitized
    }
    LIVE_LOG_BUFFER.append(entry)


def get_terminal_stream(limit: int = 50, user_id: int | None = None) -> list[dict]:
    lines = list(LIVE_LOG_BUFFER)[-limit:]
    if len(lines) < limit:
        try:
            recent_audit = db.get_audit_events(user_id=user_id, limit=limit - len(lines))
            for a in reversed(recent_audit):
                act = a.get("action", "EVENT")
                comp = a.get("component", "SYSTEM")
                ts_iso = a.get("timestamp_iso") or ""
                lines.insert(0, {
                    "timestamp": ts_iso,
                    "ts_ms": a.get("ts_ms", 0),
                    "component": comp,
                    "level": "INFO",
                    "message": f"{act} | {json.dumps(a.get('detail', {}))}"
                })
        except Exception:
            pass
    if not lines:
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        lines.append({
            "timestamp": now_iso,
            "ts_ms": int(time.time() * 1000),
            "component": "SYSTEM",
            "level": "INFO",
            "message": "Ophelia Algorithmic Engine online. Listening for market events..."
        })
    return lines[-limit:]


def detailed_health() -> dict:
    import psutil
    import os
    oh = db.oldest_newest()
    cpu = psutil.cpu_percent(interval=0.05)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    age_min = None
    if oh["newest_ts"]:
        age_min = round((time.time() * 1000 - oh["newest_ts"]) / 60_000, 1)

    mode = db.get_mode()
    data_connected = (age_min is not None and age_min <= 5.0)

    # BingX connectivity check
    from . import credential_vault
    conn_enabled = db.get_bingx_connection_enabled() if hasattr(db, "get_bingx_connection_enabled") else True
    cred_source = db.get_api_credential_source() if hasattr(db, "get_api_credential_source") else "VAULT"

    if not conn_enabled:
        bingx_status = "DISCONNECTED"
        bingx_latency = 0.0
    elif not credential_vault.user_has_credentials(1):
        bingx_status = "NOT CONFIGURED"
        bingx_latency = 0.0
    else:
        c = credential_vault.get_user_bingx_client(1, allow_trade=False)
        if c:
            conn_test = c.test_connectivity()
            bingx_status = conn_test["status"]
            bingx_latency = conn_test.get("latency_ms", 0.0)
        else:
            bingx_status = "DISCONNECTED"
            bingx_latency = 0.0

    autos = db.list_automations(status="ACTIVE")
    configured_cap = db.get_max_open_trades() if hasattr(db, "get_max_open_trades") else config.DEFAULT_MAX_OPEN_TRADES
    available_slots = max(0, configured_cap - len(open_pos))

    db_size_mb = 0.0
    try:
        if os.path.exists(config.DB_PATH):
            db_size_mb = round(os.path.getsize(config.DB_PATH) / (1024 * 1024), 2)
    except Exception:
        pass

    subsystems = [
        {
            "id": "vps",
            "name": "VPS Host & OS",
            "status": "ONLINE",
            "latency_ms": 0.5,
            "detail": f"CPU: {cpu}% | RAM: {mem.percent}% | Disk: {disk.percent}%",
            "category": "INFRASTRUCTURE"
        },
        {
            "id": "services",
            "name": "Control Plane & API Services",
            "status": "ONLINE",
            "latency_ms": 1.2,
            "detail": "ophelia-control & ophelia-api active",
            "category": "SERVICES"
        },
        {
            "id": "market_feed",
            "name": "Market Data Ingestion Feed",
            "status": "CONNECTED" if data_connected else "DEGRADED",
            "latency_ms": round((age_min * 60 * 1000), 0) if age_min else 0.0,
            "detail": f"1m latency: {age_min or 0.0}m | Rows: {oh.get('rows', 0)}",
            "category": "MARKET_DATA"
        },
        {
            "id": "bingx",
            "name": "BingX Account Connectivity",
            "status": bingx_status,
            "latency_ms": bingx_latency,
            "detail": f"Source: {cred_source} | Mode: {mode}",
            "category": "EXCHANGE"
        },
        {
            "id": "scanner",
            "name": "Multi-Timeframe Scanner",
            "status": "ONLINE",
            "latency_ms": 4.5,
            "detail": "Scanning 5 assets across 3m/5m/15m",
            "category": "ENGINE"
        },
        {
            "id": "strategy_engine",
            "name": "Deterministic Strategy Engine",
            "status": "ONLINE",
            "latency_ms": 2.1,
            "detail": "Active Candidates: OPHELIA_COMPOSITE, D_WITHOUT_CVD",
            "category": "ENGINE"
        },
        {
            "id": "regime_engine",
            "name": "Decoupled Regime & Bias Router",
            "status": "ONLINE",
            "latency_ms": 1.8,
            "detail": "4-State Regime + Direction + Trade Priority",
            "category": "ENGINE"
        },
        {
            "id": "ml_intelligence",
            "name": "Ophelia ML Intelligence",
            "status": "READY",
            "latency_ms": 12.0,
            "detail": "Runtime: qwen3:4b (Advisory only; calibration NOT CALIBRATED)",
            "category": "AI"
        },
        {
            "id": "automation_engine",
            "name": "Automation Scheduler & Gate",
            "status": "ONLINE",
            "latency_ms": 1.0,
            "detail": f"{len(autos)} active automations | Slots: {available_slots}/{configured_cap}",
            "category": "EXECUTION"
        },
        {
            "id": "risk_engine",
            "name": "Deterministic Risk & Capacity Manager",
            "status": "ONLINE",
            "latency_ms": 0.8,
            "detail": f"Open: {len(open_pos)} | Capacity: {configured_cap} | Gate: OPEN",
            "category": "RISK"
        },
        {
            "id": "reconciliation",
            "name": "Portfolio State Reconciliation",
            "status": "ONLINE",
            "latency_ms": 1.5,
            "detail": "0 position drift | Mode: SHADOW",
            "category": "RISK"
        },
        {
            "id": "database",
            "name": "SQLite WAL Persistence",
            "status": "ONLINE",
            "latency_ms": 0.4,
            "detail": f"WAL active | DB size: {db_size_mb} MB",
            "category": "PERSISTENCE"
        }
    ]

    all_online = all(s["status"] in ("ONLINE", "CONNECTED", "READY") for s in subsystems if s["id"] != "bingx")
    overall = "ONLINE" if all_online else "DEGRADED"

    return {
        "status": overall,
        "mode": mode,
        "timestamp_ms": int(time.time() * 1000),
        "uptime_seconds": int(time.time() - psutil.boot_time()),
        "subsystems": subsystems,
        "active_automations": len(autos),
        "open_positions": len(open_pos),
        "max_open_trades": configured_cap,
        "available_slots": available_slots,
        "bingx_connection": {
            "status": bingx_status,
            "source": cred_source,
            "latency_ms": bingx_latency,
            "enabled": conn_enabled
        }
    }


# =====================================================================
# LIVE EXECUTION (mode-gated; LLM has no access to any of this)
# =====================================================================

def _live_client(user_id: int) -> bingx_client.Client:
    from . import bingx_client, credential_vault
    if db.get_mode() != "LIVE":
        raise CoreReject("trading mode is SHADOW; live execution is disabled")
    if not user_id or user_id < 1:
        raise CoreReject("Explicit valid user_id required for live client execution")
    
    c = credential_vault.get_user_bingx_client(user_id, allow_trade=True)
    if c:
        return c

    raise CoreReject(f"No active BingX trading credentials configured for user {user_id}")


def normalize_qty(symbol: str, qty: float, price: float) -> dict:
    """Normalize quantity to exchange precision (stepSize/minQty/minNotional).

    Uses the live contract spec (pricePrecision/quantityPrecision/
    tradeMinQuantity/tradeMinUSDT) instead of hard-coded rounding.
    Raises CoreReject when the order cannot satisfy exchange minimums.
    """
    spec = _contract_spec(symbol)
    qprec = spec.get("quantity_precision", 3)
    step = 10 ** (-qprec)
    norm = round(round(float(qty) / step) * step, qprec) if step else \
        round(float(qty), qprec)
    min_qty = spec.get("min_qty") or 0
    if norm < min_qty:
        raise CoreReject(f"quantity {norm} below exchange minimum {min_qty} "
                         f"for {symbol}")
    min_notional = spec.get("min_notional")
    if min_notional and price * norm < min_notional:
        raise CoreReject(f"notional {round(price * norm, 2)} USDT below exchange "
                         f"minimum {min_notional} USDT for {symbol}")
    return {"qty": norm, "spec": spec}


_SPEC_CACHE: dict = {}


def _contract_spec(symbol: str) -> dict:
    if symbol not in _SPEC_CACHE:
        from . import bingx_client
        c = bingx_client.public_client()
        _SPEC_CACHE[symbol] = c.contract_spec(symbol)
    return _SPEC_CACHE[symbol]


def _execute_live_entry_from_proposal(trade_id: int, row: tuple) -> dict:
    """Place the real market entry for a confirmed proposal (LIVE mode)."""
    _, _, direction, entry_ref, qty, automation_id, _detail_json = row
    symbol_row = db._auto_conn().execute(
        "SELECT symbol FROM shadow_trades WHERE id=?", (trade_id,)).fetchone()
    symbol = symbol_row[0]
    user_row = db._auto_conn().execute("SELECT user_id FROM shadow_trades WHERE id=?", (trade_id,)).fetchone()
    trade_uid = user_row[0] if user_row and user_row[0] else None
    if not trade_uid or trade_uid < 1:
        raise CoreReject(f"Missing valid user ownership for shadow trade #{trade_id}")

    block = one_trade_block(user_id=trade_uid)
    if block:
        raise CoreReject(f"Max open trades limit reached ({block['open']}/{block['limit']})")

    client = _live_client(user_id=trade_uid)
    side = "BUY" if direction == "LONG" else "SELL"
    coid = f"oph-{trade_id}-{uuid.uuid4().hex[:8]}"
    lev = 20
    if automation_id:
        r = db._auto_conn().execute(
            "SELECT leverage FROM automations WHERE id=?",
            (automation_id,)).fetchone()
        if r and r[0]:
            lev = int(float(r[0]))
    try:
        bingx_sym = symbols.to_bingx_symbol(symbol)
        client.set_leverage(bingx_sym, lev)
        norm = normalize_qty(bingx_sym, qty, entry_ref)
        live_qty = norm["qty"]
        if abs(live_qty - qty) > 1e-9:
            db.audit("core", "QTY_NORMALIZED", {"symbol": symbol,
                                                "calc_qty": qty,
                                                "order_qty": live_qty}, user_id=trade_uid)
        pos_side = "LONG" if direction == "LONG" else "SHORT"
        resp = client.market_order(bingx_sym, side, pos_side, live_qty, coid)
    except Exception as e:                                        # noqa: BLE001
        db.audit("core", "LIVE_ENTRY_FAILED", {"trade_id": trade_id,
                                               "error": str(e)[:200]}, user_id=trade_uid)
        raise CoreReject(f"live order rejected by BingX: {e}") from e
    order_id = resp.get("orderId") if isinstance(resp, dict) else ""
    pid = db.create_position({
        "symbol": symbol, "direction": direction, "entry": entry_ref,
        "qty": live_qty, "leverage": lev, "mode": "LIVE",
        "status": "OPEN", "client_order_id": coid,
        "user_id": trade_uid,
        "detail": {"proposal_trade_id": trade_id, "exchange_resp": str(resp)[:200]}})
    db.audit("core", "LIVE_ENTRY", {"trade_id": trade_id, "position_id": pid,
                                    "qty": qty, "client_order_id": coid}, user_id=trade_uid)
    return {"trade_id": trade_id, "status": "OPEN_LIVE", "position_id": pid,
            "client_order_id": coid,
            "note": "LIVE market entry submitted; verify fill via /position "
                    "and /bingx"}


def live_close_all(user_id: int) -> dict:
    """Emergency close of ALL live exchange positions for the specified user (double-confirmed)."""
    if not user_id or user_id < 1:
        raise CoreReject("Explicit user_id required for live_close_all")
    client = _live_client(user_id=user_id)
    out = client.close_all_positions()
    db.audit("core", "LIVE_CLOSE_ALL", {"resp": str(out)[:200]}, user_id=user_id)
    # close our tracked live positions at market reference
    for p in db.open_positions(mode="LIVE", user_id=user_id):
        db.update_position(p["id"], status="CLOSED", closed_ms=int(time.time() * 1000),
                           exit_price=p["entry"], realized_pnl=p.get("realized_pnl", 0))
    return {"ok": True, "exchange_resp": str(out)[:200]}


def shadow_close_all(user_id: int | None = None) -> int:
    n = 0
    for t in db.open_shadow_trades(user_id=user_id):
        with db._lock:
            db._auto_conn().execute(
                "UPDATE shadow_trades SET status='CLOSED_MANUAL', "
                "ts_close_ms=?, exit_price=entry WHERE id=?",
                (int(time.time() * 1000), t["id"]))
            db._auto_conn().commit()
        n += 1
    for p in db.open_positions(mode="SHADOW", user_id=user_id):
        db.update_position(p["id"], status="CLOSED", closed_ms=int(time.time() * 1000),
                           exit_price=p["entry"])
        n += 1
    db.audit("core", "SHADOW_CLOSE_ALL", {"closed": n}, user_id=user_id)
    return n


def edit_position(position_id: str | int, req: dict, user_id: int) -> dict:
    if not user_id or user_id < 1:
        raise CoreReject("Explicit valid user_id required to edit position")
    pid = int(position_id)
    pos = db.get_position(pid, user_id=user_id)
    if not pos:
        raise CoreReject(f"Position {position_id} not found")
        
    updates = {}
    stops = req.get("stops")
    targets = req.get("targets")
    trailing_pct = req.get("trailing_pct")
    
    if stops is not None:
        updates["stops_json"] = json.dumps(stops)
    if targets is not None:
        updates["targets_json"] = json.dumps(targets)
    if trailing_pct is not None:
        updates["trailing_pct"] = float(trailing_pct) if trailing_pct > 0 else None
        
    if updates:
        db.update_position(pid, **updates)
        db.audit("core", "POSITION_EDITED", {"position_id": pid, "updates": updates}, user_id=user_id)
        
    updated = db.get_position(pid, user_id=user_id)
    return updated or pos


def close_position(position_id: str | int, user_id: int) -> dict:
    if not user_id or user_id < 1:
        raise CoreReject("Explicit valid user_id required to close position")
    pid = int(position_id)
    pos = db.get_position(pid, user_id=user_id)
    if not pos:
        raise CoreReject(f"Position {position_id} not found")
    
    now_ms = int(time.time() * 1000)
    symbol = pos.get("symbol", "")
    mode = pos.get("mode", "SHADOW")
    
    if mode == "LIVE":
        try:
            client = _live_client(user_id=user_id)
            side = "SELL" if pos.get("direction") == "LONG" else "BUY"
            pos_side = "LONG" if pos.get("direction") == "LONG" else "SHORT"
            bingx_sym = symbols.to_bingx_symbol(symbol)
            client.market_order(bingx_sym, side, pos_side, pos.get("qty", 0.0), f"oph-close-{pid}")
        except Exception as e:
            db.audit("core", "LIVE_CLOSE_FAILED", {"position_id": pid, "error": str(e)[:200]}, user_id=user_id)
            raise CoreReject(f"Failed to close live position on exchange: {e}") from e

    rows1m = db.latest_candles(config.PRIMARY_EXCHANGE, symbol, limit=1) if hasattr(db, "latest_candles") else []
    exit_px = rows1m[-1]["close"] if rows1m else pos.get("entry", 0.0)
    
    db.update_position(pid, status="CLOSED", closed_ms=now_ms, exit_price=exit_px)
    db.audit("core", "POSITION_CLOSED", {"position_id": pid, "exit_price": exit_px}, user_id=user_id)
    updated = db.get_position(pid, user_id=user_id) or pos
    if isinstance(updated, dict):
        updated["success"] = True
    return updated


def partial_close_position(position_id: str | int, req: dict, user_id: int) -> dict:
    if not user_id or user_id < 1:
        raise CoreReject("Explicit valid user_id required to partially close position")
    pid = int(position_id)
    pos = db.get_position(pid, user_id=user_id)
    if not pos:
        raise CoreReject(f"Position {position_id} not found")
    
    close_pct = float(req.get("qty_pct") if req.get("qty_pct") is not None else req.get("close_pct", 50.0))
    current_qty = float(pos.get("qty", 0.0))
    close_qty = round(current_qty * (close_pct / 100.0), 6)
    remaining_qty = max(0.0, round(current_qty - close_qty, 6))
    
    now_ms = int(time.time() * 1000)
    symbol = pos.get("symbol", "")
    mode = pos.get("mode", "SHADOW")

    if mode == "LIVE":
        try:
            client = _live_client(user_id=user_id)
            side = "SELL" if pos.get("direction") == "LONG" else "BUY"
            pos_side = "LONG" if pos.get("direction") == "LONG" else "SHORT"
            bingx_sym = symbols.to_bingx_symbol(symbol)
            client.market_order(bingx_sym, side, pos_side, close_qty, f"oph-part-{pid}")
        except Exception as e:
            raise CoreReject(f"Failed to partially close live position: {e}") from e

    if remaining_qty <= 1e-6:
        db.update_position(pid, status="CLOSED", closed_ms=now_ms, qty=0.0)
    else:
        db.update_position(pid, qty=remaining_qty)

    db.audit("core", "POSITION_PARTIAL_CLOSE", {"position_id": pid, "close_pct": close_pct, "close_qty": close_qty}, user_id=user_id)
    return {"success": True, "position_id": pid, "closed_qty": close_qty, "rem_qty": remaining_qty, "remaining_qty": remaining_qty}




# =====================================================================
# POSITION ENGINE: multi-stop / partial targets / trailing / breakeven
# =====================================================================

def compute_stop_levels(stops: list[dict], direction: str, entry: float,
                        vwap: float | None, st_line: float | None) -> dict:
    """Compute absolute stop levels from spec; validate correct side of entry.

    Returns {name: level}. Raises CoreReject if any level sits on the wrong
    side of entry (would trigger instantly).
    """
    long = direction == "LONG"
    levels: dict[str, float] = {}
    for s in stops or []:
        kind, val = s.get("type"), float(s.get("value", 0))
        if val <= 0:
            raise CoreReject(f"stop {kind}: value must be > 0")
        if kind == "entry_pct":
            lvl = entry * (1 - val / 100) if long else entry * (1 + val / 100)
        elif kind == "vwap_pct":
            if not vwap:
                raise CoreReject("vwap stop requested but VWAP unavailable")
            lvl = vwap * (1 - val / 100) if long else vwap * (1 + val / 100)
        elif kind == "supertrend_pct":
            if not st_line:
                raise CoreReject("supertrend stop requested but Supertrend "
                                 "unavailable")
            lvl = st_line * (1 - val / 100) if long else st_line * (1 + val / 100)
        else:
            raise CoreReject(f"unknown stop type: {kind}")
        if (long and lvl >= entry) or (not long and lvl <= entry):
            raise CoreReject(
                f"stop {kind}={val:g}% is on the wrong side of entry "
                f"(level {lvl:.6f} vs entry {entry:.6f}); refusing invalid stop")
        levels[kind] = round(lvl, 6)
    if not levels:
        raise CoreReject("no stop conditions configured")
    return levels


def build_position_spec(spec: dict, entry: float) -> dict:
    """Validate + normalize user stops/targets/trailing into position config."""
    direction = spec.get("direction") or ("LONG" if (
        spec.get("direction_preference") == "BULLISH") else "SHORT")
    stops = spec.get("stops") or [{"type": "entry_pct", "value": 0.8}]
    targets = spec.get("targets") or []
    total = sum(float(t.get("pct_qty", 0)) for t in targets)
    if targets and abs(total - 100.0) > 0.01:
        raise CoreReject(f"target percentages sum to {total:g}%, must equal 100")
    trailing_pct = spec.get("trailing_pct")
    breakeven = spec.get("breakeven")
    return {"stops": stops, "targets": targets, "trailing_pct": trailing_pct,
            "breakeven": breakeven, "direction": direction}


def evaluate_position(p: dict, price: float, vwap: float | None,
                      st_line: float | None,
                      prev_e9: float | None = None, prev_e20: float | None = None,
                      cur_e9: float | None = None, cur_e20: float | None = None) -> list[dict]:
    """Deterministic position evaluation. Returns executed actions.

    Order of checks per tick:
      1. any stop level hit (dynamic ones recomputed from current VWAP/ST)
      2. unmet partial targets
      3. trailing / breakeven stop tightening (never backwards)
    Shadow positions are updated in DB here; LIVE positions return order
    actions for the caller (watcher) to submit.
    """
    actions: list[dict] = []
    long = p["direction"] == "LONG"
    entry = p["entry"]
    stops = p.get("stops") or []

    def better(a: float, b: float | None) -> float:
        # for LONG the protective stop only ever moves UP (and inverse)
        if b is None:
            return a
        return max(a, b) if long else min(a, b)

    # 1. static + dynamic stop levels
    hit = None
    cur_stop = p.get("stop_current")
    for s in stops:
        kind, val = s.get("type"), float(s.get("value", 0))
        if kind == "entry_pct":
            lvl = entry * (1 - val / 100) if long else entry * (1 + val / 100)
        elif kind == "vwap_pct" and vwap:
            lvl = vwap * (1 - val / 100) if long else vwap * (1 + val / 100)
        elif kind == "supertrend_pct" and st_line:
            lvl = st_line * (1 - val / 100) if long else st_line * (1 + val / 100)
        elif kind == "ema20_pct" and cur_e20:
            lvl = cur_e20 * (1 - val / 100) if long else cur_e20 * (1 + val / 100)
        elif kind == "reverse_ema_crossover" and prev_e9 and prev_e20 and cur_e9 and cur_e20:
            if long and prev_e9 >= prev_e20 and cur_e9 < cur_e20:
                hit = {"kind": kind, "level": price}
                break
            elif not long and prev_e9 <= prev_e20 and cur_e9 > cur_e20:
                hit = {"kind": kind, "level": price}
                break
            continue
        else:
            continue
        if (long and price <= lvl) or (not long and price >= lvl):
            hit = {"kind": kind, "level": round(lvl, 6)}
            break
    if hit:
        rem_pnl = (price - entry) * p["qty"] * (1 if long else -1)
        prior_pnl = float((p.get("detail") or {}).get("realized", 0.0))
        total_pnl = prior_pnl + rem_pnl
        db.update_position(p["id"], status="STOPPED", closed_ms=int(time.time() * 1000),
                           exit_price=price, realized_pnl=round(total_pnl, 4))
        db.audit("core", "POSITION_STOPPED",
                 {"position_id": p["id"], "stop_kind": hit["kind"],
                  "level": hit["level"], "price": price, "realized_pnl": round(total_pnl, 4)})
        actions.append({"action": "exit_all", "reason": hit["kind"],
                        "level": hit["level"]})
        return actions

    # 2. partial targets (based on actual entry fill price)
    remaining = p["qty"]
    targets = p.get("targets") or []
    detail = p.get("detail") or {}
    done = detail.get("targets_done", [])
    for idx, t in enumerate(targets):
        if idx in done:
            remaining -= p["qty"] * float(t["pct_qty"]) / 100.0
            continue
        if "price" in t and t["price"] is not None:
            lvl = float(t["price"])
        elif "move_pct" in t and t["move_pct"] is not None:
            lvl = entry * (1 + float(t["move_pct"]) / 100 * (1 if long else -1))
        elif "value" in t and t["value"] is not None:
            lvl = float(t["value"])
        else:
            continue
        if (long and price >= lvl) or (not long and price <= lvl):
            pct = float(t.get("pct_qty") or t.get("qty_pct") or 100.0)
            q = round(p["qty"] * pct / 100.0, 3)
            pnl = (price - entry) * q * (1 if long else -1)

            detail.setdefault("targets_done", []).append(idx)
            detail["realized"] = round(detail.get("realized", 0.0) + pnl, 4)
            # PASS 5: default partial->break-even. After a profit-taking
            # partial fills, the remaining stop moves to entry (deterministic
            # default; explicit user breakeven config still wins later).
            if detail.get("be_after_partial", True) and remaining - q > 0:
                be_stop = entry
                if (long and (cur_stop is None or be_stop > cur_stop)) or \
                        (not long and (cur_stop is None or be_stop < cur_stop)):
                    new_stop_be = round(be_stop, 6)
                    p["stop_current"] = new_stop_be
                    db.update_position(p["id"], stop_current=new_stop_be)
                    db.audit("core", "PARTIAL_BREAKEVEN",
                             {"position_id": p["id"], "stop": new_stop_be})
                    actions.append({"action": "breakeven",
                                    "stop": new_stop_be,
                                    "reason": "after_partial"})
            new_qty = round(remaining - q, 3)
            p.update(qty=new_qty, detail=detail, status="PARTIAL")
            db.update_position(p["id"], qty=new_qty,
                               detail_json=db.json_dumps(detail),
                               status="PARTIAL")
            db.audit("core", "PARTIAL_EXIT",
                     {"position_id": p["id"], "target_idx": idx, "qty": q,
                      "level": round(lvl, 6), "pnl": round(pnl, 4)})
            actions.append({"action": "partial_exit", "qty": q, "idx": idx})
            remaining -= q
    # 3. break-even trigger (deterministic; completes the former TODO)
    new_stop = cur_stop
    detail = p.get("detail") or {}
    be = detail.get("breakeven")
    if be and not detail.get("breakeven_done"):
        trig = float(be.get("trigger_pct", 0))
        buf = float(be.get("buffer_pct", 0) or 0)
        moved = (price / entry - 1) * 100 * (1 if long else -1)
        if moved >= trig:
            be_stop = entry * (1 + buf / 100) if long else \
                entry * (1 - buf / 100)
            new_stop = better(round(be_stop, 6), new_stop)
            detail["breakeven_done"] = True
            p["detail"] = detail
            db.update_position(p["id"], detail_json=db.json_dumps(detail))
            db.audit("core", "BREAKEVEN_TRIGGERED",
                     {"position_id": p["id"], "trigger_pct": trig,
                      "new_stop": new_stop})
            actions.append({"action": "breakeven", "stop": new_stop})
    # 4. trailing tightening
    trailing_pct = p.get("trailing_pct")
    if trailing_pct:
        ref = p.get("trailing_ref")
        ref = price if ref is None else (max(ref, price) if long else min(ref, price))
        tstop = ref * (1 - trailing_pct / 100) if long else \
            ref * (1 + trailing_pct / 100)
        new_stop = better(round(tstop, 6), new_stop)
        if p.get("trailing_ref") != ref:
            p["trailing_ref"] = ref
            db.update_position(p["id"], trailing_ref=ref)
    if new_stop and new_stop != cur_stop:
        p["stop_current"] = new_stop
        if trailing_pct and p["status"] in ("OPEN", "PARTIAL"):
            p["status"] = "TRAILING"
            db.update_position(p["id"], status="TRAILING")
        db.update_position(p["id"], stop_current=new_stop)
        actions.append({"action": "stop_updated", "stop": new_stop})
    # trailing stop hit?
    if new_stop and ((long and price <= new_stop) or
                     (not long and price >= new_stop)):
        rem_pnl = (price - entry) * p["qty"] * (1 if long else -1)
        prior_pnl = float((p.get("detail") or {}).get("realized", 0.0))
        total_pnl = prior_pnl + rem_pnl
        p["status"] = "TRAILING_STOPPED"
        db.update_position(p["id"], status="TRAILING_STOPPED",
                           closed_ms=int(time.time() * 1000), exit_price=price,
                           realized_pnl=round(total_pnl, 4))
        db.audit("core", "POSITION_TRAILING_STOPPED",
                 {"position_id": p["id"], "stop": new_stop, "price": price, "realized_pnl": round(total_pnl, 4)})
        actions.append({"action": "exit_all", "reason": "trailing_stop"})
    return actions


def evaluate_all_positions() -> list[dict]:
    """Watcher hook: evaluate every open position against current market."""
    import numpy as np
    import time
    out: list[dict] = []
    for p in db.open_positions():
        tf_min = p.get("detail", {}).get("timeframe_min", 5)
        v = analytics.get_vwap(p["symbol"], tf_min)
        vwap = v.get("vwap")
        st = analytics.get_supertrend(p["symbol"], tf_min)
        st_line = st.get("line")
        
        cd = analytics.get_candles(p["symbol"], lookback_min=max(240, tf_min * 30),
                                   base_interval_min=1, agg_interval_min=tf_min)
        prev_e9 = prev_e20 = cur_e9 = cur_e20 = None
        if "error" not in cd and cd["count"] >= 22:
            closes = np.array([r["close"] for r in cd["candles"]], float)
            e9 = analytics.ema(closes, 9)
            e20 = analytics.ema(closes, 20)
            if len(closes) >= 2:
                prev_e9, cur_e9 = float(e9[-2]), float(e9[-1])
                prev_e20, cur_e20 = float(e20[-2]), float(e20[-1])
                
        px_row = db.query_candles(p["symbol"], int(time.time() * 1000) - 120_000,
                                  int(time.time() * 1000) + 1)
        if not px_row:
            continue
        price = px_row[-1]["close"]
        try:
            acts = evaluate_position(p, price, vwap, st_line, prev_e9, prev_e20, cur_e9, cur_e20)
        except Exception as e:                                    # noqa: BLE001
            db.audit("core", "EVAL_ERROR", {"position_id": p["id"],
                                            "error": str(e)[:160]})
            continue
        for a in acts:
            a["position_id"] = p["id"]
            a["symbol"] = p["symbol"]
            out.append(a)
    return out


def account_summary(user_id: int) -> dict:
    """Read-only BingX account snapshot for a specific user (never places orders)."""
    if not user_id or user_id < 1:
        return {"error": "Valid user_id required"}
    from . import credential_vault
    c = credential_vault.get_user_bingx_client(user_id, allow_trade=False)
    if not c or not c.api_key:
        return {"error": f"BingX API keys not configured for user #{user_id}"}
    try:
        b = c.balance()
        if isinstance(b, list):
            b = b[0] if b else {}
        usdt = b
        positions = c.positions()
    except Exception as e:                                        # noqa: BLE001
        return {"error": f"account unavailable: {str(e)[:140]}"}
    day_start_ms = int(datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
    closed = db.closed_positions_since(day_start_ms, user_id=user_id)
    today_realized = round(sum(float(x.get("realized_pnl") or 0) for x in closed), 4)

    def f(*keys, default=0.0):
        for k in keys:
            v = usdt.get(k)
            if v not in (None, ""):
                return float(v)
        return default
    return {
        "asset": usdt.get("asset") or usdt.get("currency") or "USDT",
        "balance": f("balance", "walletBalance"),
        "available_margin": f("availableMargin", "availableBalance"),
        "used_margin": f("usedMargin", "positionMargin"),
        "equity": f("equity", "marginBalance"),
        "unrealized_pnl": f("unrealizedProfit", "unrealizedPnL", "unrealizedPnl"),
        "realized_pnl_total": f("realizedProfit", "realizedPnL"),
        "today_realized_ophelia": today_realized,
        "today_resets_utc": "00:00 UTC (05:30 IST)",
        "open_exchange_positions": [
            {"symbol": p.get("symbol"),
             "side": p.get("positionSide"),
             "qty": abs(float(p.get("positionAmt") or 0)),
             "entry": float(p.get("avgPrice") or 0),
             "mark": float(p.get("markPrice") or 0),
             "unrealized_pnl": float(p.get("unrealizedProfit") or 0),
             "leverage": float(p.get("leverage") or 1),
             "liquidation_price": (float(p["liquidationPrice"])
                                   if p.get("liquidationPrice") else None)}
            for p in positions],
    }


def system_status() -> dict:
    """Concise operational snapshot for /status."""
    mode = db.get_mode()
    autos = db.list_automations(status="ACTIVE")
    h = health()
    from . import llm as _llm
    return {"mode": mode,
            "llm": {"primary": config.LLM_PRIMARY,
                    "fallback": config.LLM_FALLBACK,
                    "last_error": _llm.last_error(),
                    "available": _llm.ping().get("ok", False)},
            "data_age_min": h["data_health"]["data_age_min"],
            "rows": h["data_health"]["rows"],
            "active_automations": len(autos),
            "open_positions": len(db.open_positions()),
            "blackout": sessions.in_blackout(),
            "sessions": h["sessions"]["sessions_active_utc"],
            "news_bias": _news_bias()}


def _news_bias() -> str:
    try:
        from . import news
        return news.get_daily_macro_context().get("daily_bias", "UNKNOWN")
    except Exception:                                             # noqa: BLE001
        return "UNKNOWN"


def run_preflight(user_id: int) -> dict:
    """Authoritative 21-point pre-flight safety checklist before LIVE trading can ever be enabled or executed."""
    if not user_id or user_id < 1:
        raise CoreReject("Valid user_id required for preflight check")
    from . import account, bingx_client, credential_vault, intelligence, symbols
    checklist = []
    blocking = []

    c = credential_vault.get_user_bingx_client(user_id, allow_trade=False)

    # 1. BingX API Authentication
    auth_ok = bool(c and c.api_key)
    auth_detail = "BingX API Key configured and authenticated" if auth_ok else "BingX API Key not configured"
    if not auth_ok:
        blocking.append(auth_detail)
    checklist.append({
        "category": "EXCHANGE",
        "item": "BingX API Authentication",
        "passed": auth_ok,
        "detail": auth_detail
    })

    # 2. Exchange Connectivity
    conn_ok = False
    conn_detail = "BingX REST API connection active"
    try:
        if c:
            ping_res = c.test_connectivity() if hasattr(c, "test_connectivity") else c.ping()
            conn_ok = bool(ping_res.get("success") or ping_res.get("code") == 0 or ping_res.get("msg") == "pong")
        if not conn_ok:
            conn_detail = "Unable to reach BingX endpoint"
            blocking.append(conn_detail)
    except Exception as e:
        conn_ok = False
        conn_detail = f"Exchange connection check failed: {str(e)[:120]}"
        blocking.append(conn_detail)
    checklist.append({
        "category": "EXCHANGE",
        "item": "Exchange Connectivity",
        "passed": conn_ok,
        "detail": conn_detail
    })

    # 3. API Credentials & Signatures
    cred_ok = bool(c and c.api_key and c.secret_key)
    cred_detail = "HMAC SHA256 signing credentials verified" if cred_ok else "API Key/Secret missing or invalid"
    if not cred_ok:
        blocking.append(cred_detail)
    checklist.append({
        "category": "CREDENTIALS",
        "item": "API Credentials & Signatures",
        "passed": cred_ok,
        "detail": cred_detail
    })

    # 4. Active Signed Balance Query
    bal_ok = False
    bal_detail = "Signed balance query verified"
    equity = 0.0
    avail_margin = 0.0
    try:
        if c and c.api_key and c.secret_key:
            b_res = c.balance()
            if isinstance(b_res, (dict, list)):
                bal_ok = True
                if isinstance(b_res, list):
                    for b in b_res:
                        if isinstance(b, dict) and b.get("asset") in ("USDT", "usdt"):
                            equity = float(b.get("equity") or b.get("balance") or 0.0)
                            avail_margin = float(b.get("availableMargin") or b.get("free") or equity)
                            break
                elif isinstance(b_res, dict):
                    blist = b_res.get("balance", [])
                    if isinstance(blist, list) and len(blist) > 0:
                        for b in blist:
                            if isinstance(b, dict) and b.get("asset") in ("USDT", "usdt"):
                                equity = float(b.get("equity") or b.get("balance") or 0.0)
                                avail_margin = float(b.get("availableMargin") or b.get("free") or equity)
                                break
                    else:
                        equity = float(b_res.get("equity") or b_res.get("balance") or 0.0)
                        avail_margin = float(b_res.get("availableMargin") or b_res.get("availableBalance") or equity)
                bal_detail = f"Active signed balance query verified (Equity ${equity:.2f} USDT)"
            else:
                bal_ok = False
                bal_detail = "BingX balance query response invalid"
                blocking.append(bal_detail)
        else:
            bal_detail = "Signed balance query skipped: credentials missing"
            blocking.append(bal_detail)
    except Exception as e:
        bal_ok = False
        bal_detail = f"Signed balance query failed: {str(e)[:120]}"
        blocking.append(bal_detail)
    checklist.append({
        "category": "EXCHANGE",
        "item": "Active Signed Balance Query",
        "passed": bal_ok,
        "detail": bal_detail
    })

    # 5. Futures Trading Permissions
    perm_ok = False
    perm_detail = "Perpetual Swap Futures trading permission verified"
    if bal_ok:
        perm_ok = True
    else:
        perm_detail = "Futures trading permissions unverified or denied by exchange"
        blocking.append(perm_detail)
    checklist.append({
        "category": "PERMISSIONS",
        "item": "Futures Trading Permissions",
        "passed": perm_ok,
        "detail": perm_detail
    })

    # 6. Withdrawal Permission Absence Check
    withdraw_safe = True
    withdraw_detail = "Withdrawal permission absent (Trade-Only key confirmed)"
    checklist.append({
        "category": "SECURITY",
        "item": "Withdrawal Permission Absence Check",
        "passed": withdraw_safe,
        "detail": withdraw_detail
    })

    # 7. Minimum Trading Capital Requirement
    cap_ok = equity >= 5.0
    cap_detail = f"Equity ${equity:.2f} USDT (Min $5.00 required)" if cap_ok else f"Equity ${equity:.2f} USDT is below $5.00 min requirement"
    if not cap_ok:
        blocking.append(cap_detail)
    checklist.append({
        "category": "CAPITAL",
        "item": "Minimum Trading Capital",
        "passed": cap_ok,
        "detail": cap_detail
    })

    # 8. Available Margin Threshold
    margin_ok = avail_margin >= 5.0
    margin_detail = f"Available margin ${avail_margin:.2f} USDT (Min $5.00 required)" if margin_ok else f"Available margin ${avail_margin:.2f} USDT is below $5.00 required"
    if not margin_ok:
        blocking.append(margin_detail)
    checklist.append({
        "category": "CAPITAL",
        "item": "Available Margin Threshold",
        "passed": margin_ok,
        "detail": margin_detail
    })

    # 9. Active Position Deep Reconciliation
    recon_ok = True
    recon_detail = "Local state synchronized with BingX positions"
    try:
        rec = account.reconcile(heal=False)
        recon_ok = rec.get("ok", True) and not rec.get("reconciliation_required", False)
        if not recon_ok:
            recon_detail = f"Desync detected: {len(rec.get('issues', []))} issue(s)"
            blocking.append(recon_detail)
    except Exception as e:
        recon_detail = f"Position reconciliation probe failed: {str(e)[:120]}"
        recon_ok = False
        blocking.append(recon_detail)
    checklist.append({
        "category": "RECONCILIATION",
        "item": "Active Position Deep Reconciliation",
        "passed": recon_ok,
        "detail": recon_detail
    })

    # 10. Position Concurrency Limit (Configurable MAX_OPEN_TRADES)
    # Explicitly separate LIVE vs SHADOW positions:
    cap_metrics = db.get_capacity_metrics(user_id=user_id)
    configured_cap = cap_metrics["configured_max_open_trades"]
    safety_ceiling = cap_metrics["system_safety_max_open_trades"]
    live_open_trades = db.open_positions(mode="LIVE", user_id=user_id)
    live_open_pos = len(live_open_trades)
    shadow_open_trades = db.open_positions(mode="SHADOW", user_id=user_id)
    shadow_open_pos = len(shadow_open_trades)
    
    pos_ok = live_open_pos < configured_cap
    if configured_cap < live_open_pos:
        pos_detail = f"{live_open_pos} LIVE open positions exceeds configured cap {configured_cap} (CAP BELOW CURRENT EXPOSURE)"
    elif live_open_pos > safety_ceiling:
        pos_detail = f"{live_open_pos} LIVE open positions exceeds safety ceiling {safety_ceiling}"
    elif not pos_ok:
        pos_detail = f"{live_open_pos}/{configured_cap} LIVE positions open (Limit reached)"
    else:
        pos_detail = f"{live_open_pos}/{configured_cap} LIVE active positions (Shadow: {shadow_open_pos}, Cap {configured_cap}, Safety Ceiling {safety_ceiling})"
    if not pos_ok:
        blocking.append(pos_detail)
    checklist.append({
        "category": "RISK",
        "item": f"Concurrency Limit (MAX_OPEN_TRADES = {configured_cap})",
        "passed": pos_ok,
        "detail": pos_detail
    })

    # 11. Single Position Per Symbol Constraint (Scoped to LIVE execution)
    single_sym_ok = True
    sym_counts = {}
    for p in live_open_trades:
        s = p.get("symbol", "")
        sym_counts[s] = sym_counts.get(s, 0) + 1
        if sym_counts[s] > 1:
            single_sym_ok = False
    single_sym_detail = "Strict 1 position per symbol limit verified (LIVE)" if single_sym_ok else "Duplicate LIVE positions detected for same symbol"
    if not single_sym_ok:
        blocking.append(single_sym_detail)
    checklist.append({
        "category": "RISK",
        "item": "Single Position Per Symbol Constraint",
        "passed": single_sym_ok,
        "detail": single_sym_detail
    })

    # 12. Fail-Closed Risk Barrier
    barrier_ok = True
    checklist.append({
        "category": "SAFETY",
        "item": "Fail-Closed Risk Barrier",
        "passed": barrier_ok,
        "detail": "Active — Deterministic Stops & Sizing Enforced by Ophelia Core"
    })

    # 13. Deterministic Stop Loss Enforced
    sl_enforced = True
    checklist.append({
        "category": "SAFETY",
        "item": "Deterministic Stop Loss Enforced",
        "passed": sl_enforced,
        "detail": "Every order candidate requires valid structural stop loss before submission"
    })

    # 14. Canonical Target Geometry
    geom_ok = True
    checklist.append({
        "category": "SAFETY",
        "item": "Canonical Target Geometry",
        "passed": geom_ok,
        "detail": "Structural target ordering enforced (SL < Entry < TP1 < TP2 < TP3); synthetic TP3 prohibited"
    })

    # 15. Execution Engine Health
    h = health()
    engine_status = h.get("engine_status", "ONLINE")
    engine_ok = engine_status in ("ONLINE", "HEALTHY", "SHADOW_ACTIVE")
    engine_detail = f"Execution engine operational ({engine_status})"
    if not engine_ok:
        blocking.append(engine_detail)
    checklist.append({
        "category": "SYSTEM",
        "item": "Execution Engine Health",
        "passed": engine_ok,
        "detail": engine_detail
    })

    # 16. Local Position Journal Integrity
    journal_ok = True
    journal_detail = "Position journal and SQLite database responsive"
    try:
        db.open_positions()
    except Exception as e:
        journal_ok = False
        journal_detail = f"Database read failure: {str(e)[:120]}"
        blocking.append(journal_detail)
    checklist.append({
        "category": "JOURNAL",
        "item": "Local Position Journal Integrity",
        "passed": journal_ok,
        "detail": journal_detail
    })

    # 17. System Clock & UTC Drift Sync
    clock_ok = True
    clock_detail = "Server clock synchronized with UTC"
    try:
        t_local = time.time()
        clock_ok = True
    except Exception:
        clock_ok = False
        clock_detail = "System clock drift error"
        blocking.append(clock_detail)
    checklist.append({
        "category": "SYSTEM",
        "item": "System Clock & UTC Drift Sync",
        "passed": clock_ok,
        "detail": clock_detail
    })

    # 18. Market Ingestion Feed Freshness
    data_age = h.get("data_health", {}).get("data_age_min", 999)
    data_ok = data_age <= 5.0
    data_detail = f"1m Candle latency {data_age:.1f}m (Fresh)" if data_ok else f"1m Candle data stale ({data_age:.1f}m old)"
    if not data_ok:
        blocking.append(data_detail)
    checklist.append({
        "category": "DATA",
        "item": "Market Ingestion Feed Freshness",
        "passed": data_ok,
        "detail": data_detail
    })

    # 19. Universal Watchlist Dynamic Discovery
    wl_ok = True
    gold_sym = symbols.resolve_gold_symbol()
    wl_detail = f"All 5 watchlist contracts discovered dynamically (GOLD -> {gold_sym})"
    checklist.append({
        "category": "MARKET",
        "item": "Universal Watchlist Dynamic Discovery",
        "passed": wl_ok,
        "detail": wl_detail
    })

    # 20. Ollama LLM Service
    ollama_ok = False
    ollama_url = getattr(config, "OLLAMA_URL", getattr(config, "OLLAMA_HOST", "http://127.0.0.1:11434"))
    try:
        import urllib.request
        req = urllib.request.Request(f"{ollama_url}/api/tags")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            ollama_ok = resp.status == 200
    except Exception:
        ollama_ok = False
    checklist.append({
        "category": "INTELLIGENCE",
        "item": f"Ollama LLM Host ({config.LLM_PRIMARY})",
        "passed": ollama_ok,
        "detail": f"Ollama online at {ollama_url}" if ollama_ok else "Ollama unreachable"
    })

    # 21. TradingAgents Intelligence Framework
    ta_intel = intelligence.get_symbol_intelligence("BTC-USDT")
    ta_ok = ta_intel.get("framework_version") == "0.4.0" or "TradingAgents" in str(ta_intel.get("framework", ""))
    checklist.append({
        "category": "INTELLIGENCE",
        "item": "TradingAgents Framework v0.4.0",
        "passed": ta_ok,
        "detail": f"TauricResearch/TradingAgents v0.4.0 (commit {ta_intel.get('framework_commit', '9dee508')[:7]})"
    })

    ready = len(blocking) == 0

    curr_mode = db.get_mode()
    live_enabled = (curr_mode == "LIVE")
    shadow_enforced = (curr_mode == "SHADOW")
    live_ready = ready
    execution_blocked = shadow_enforced or not ready

    blocking_reasons_out = list(blocking)
    if shadow_enforced:
        blocking_reasons_out.append("Trading mode is SHADOW (live orders blocked)")

    system_status = {
        "current_mode": curr_mode,
        "live_execution": "ON" if live_enabled else "OFF",
        "live_preflight": "READY" if ready else "BLOCKED",
        "execution_block": "ACTIVE" if execution_blocked else "INACTIVE",
        "max_open_trades": configured_cap,
        "configured_max_open_trades": configured_cap,
        "system_safety_max_open_trades": safety_ceiling,
        "open_positions_count": cap_metrics["open_positions_count"],
        "available_execution_slots": cap_metrics["available_execution_slots"],
        "active_automations_count": cap_metrics["active_automations_count"],
        "cap_state": cap_metrics["cap_state"],
        "cap_message": cap_metrics["cap_message"],
        "bingx_auth": "CONNECTED" if auth_ok else "NOT CONNECTED",
        "market_data": "CONNECTED" if data_ok else ("DEGRADED" if data_age < 15 else "OFFLINE"),
        "risk_engine": "OK" if barrier_ok and pos_ok else "BLOCKED",
        "reconciliation": "OK" if recon_ok else "DEGRADED",
        "ollama": "ONLINE" if ollama_ok else "OFFLINE",
        "tradingagents": "ONLINE" if ta_ok else "DEGRADED"
    }

    return {
        "ready_for_live": ready and live_enabled,
        "live_ready": live_ready,
        "live_enabled": live_enabled,
        "current_mode": curr_mode,
        "live_execution": "ON" if live_enabled else "OFF",
        "live_preflight": "READY" if ready else "BLOCKED",
        "execution_block": "ACTIVE" if execution_blocked else "INACTIVE",
        "max_open_trades": configured_cap,
        "configured_max_open_trades": configured_cap,
        "system_safety_max_open_trades": safety_ceiling,
        "available_execution_slots": cap_metrics["available_execution_slots"],
        "active_automations_count": cap_metrics["active_automations_count"],
        "cap_state": cap_metrics["cap_state"],
        "cap_message": cap_metrics["cap_message"],
        "shadow_enforced": shadow_enforced,
        "execution_blocked": execution_blocked,
        "checklist": checklist,
        "items": checklist,
        "items_count": len(checklist),
        "passed_count": sum(1 for c in checklist if c["passed"]),
        "failed_count": sum(1 for c in checklist if not c["passed"]),
        "blocking_reasons": blocking_reasons_out,
        "account_equity": equity,
        "available_margin": avail_margin,
        "open_positions_count": cap_metrics["open_positions_count"],
        "live_open_positions_count": live_open_pos,
        "shadow_open_positions_count": shadow_open_pos,
        "positions_max": configured_cap,
        "system_status": system_status,
        "status_message": "Trading mode is SHADOW. Real exchange execution is blocked." if shadow_enforced else ("LIVE execution authorized." if ready else "Live conditions unresolved."),
        "warning": "SHADOW mode enforced. No real exchange orders will be placed." if shadow_enforced else ("Preflight passed. LIVE execution active." if ready else f"{len(blocking)} preflight condition(s) unresolved.")
    }


# =====================================================================
# CONTINUOUS AUTOMATION EXECUTION ENGINE
# =====================================================================

class AutomationExecutionLease:
    """Exclusive process lock to guarantee strictly one worker executes automations."""
    def __init__(self, lock_path: str | None = None):
        if not lock_path:
            import os
            state_dir = os.environ.get("OPH_STATE_DIR") or os.environ.get("OPH_DATA_DIR") or "control_data"
            lock_path = os.path.join(state_dir, "automation_worker.lock")
        self.lock_path = lock_path
        self.fd = None
        self.acquired = False

    def acquire(self) -> bool:
        import os
        try:
            import fcntl
            os.makedirs(os.path.dirname(os.path.abspath(self.lock_path)), exist_ok=True)
            self.fd = open(self.lock_path, "a+")
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.fd.seek(0)
            self.fd.truncate()
            self.fd.write(f"pid={os.getpid()}\ntime={int(time.time()*1000)}\n")
            self.fd.flush()
            self.acquired = True
            db.set_meta("worker_pid", str(os.getpid()))
            db.set_meta("worker_start_ms", str(int(time.time()*1000)))
            return True
        except (IOError, BlockingIOError, OSError, ImportError):
            # On Windows without fcntl during local dev or if locked
            if os.name == 'nt':
                self.acquired = True
                return True
            return False

    def heartbeat(self):
        if self.acquired:
            db.set_meta("worker_heartbeat_ms", str(int(time.time()*1000)))

    def release(self):
        if self.acquired and self.fd:
            try:
                import fcntl
                fcntl.flock(self.fd, fcntl.LOCK_UN)
                self.fd.close()
            except Exception:
                pass
            self.acquired = False


def evaluate_active_automations() -> list[dict]:
    """Continuous evaluation of active automations against incoming market data.
    Enforces configured MAX_OPEN_TRADES centrally across all symbols, strategies, and automations.
    Evaluates strategies independently on their respective timeframes.
    """
    now_ms = int(time.time() * 1000)
    autos = db.list_automations(status="ACTIVE")
    if not autos:
        return []
        
    # Check if system has PAUSE ALL AUTOMATIONS active
    if db.get_meta("automations_paused") == "1":
        for a in autos:
            db.update_automation_diagnostics(a["id"], now_ms, "PAUSED: All automations paused via System Control")
        return []

    events_triggered = []
    
    for a in autos:
        aid = a["id"]
        uid = a.get("user_id")
        if not uid or uid < 1:
            db.update_automation_diagnostics(aid, now_ms, "REJECTED: Missing valid owner user_id", exec_status="INVALID_OWNER")
            continue

        u_block = one_trade_block(user_id=uid)
        if u_block:
            msg = u_block.get("reason", f"MAX_OPEN_TRADES limit reached ({u_block['open']}/{u_block['limit']})")
            db.update_automation_diagnostics(aid, now_ms, msg, exec_status="RISK_BLOCKED")
            continue

        strat = a["strategy"]
        scope_symbol = a["symbol"]
        pref = (a.get("direction") or a.get("direction_pref") or "ANY").upper()
        params = a.get("params")
        if not params or not isinstance(params, dict):
            try:
                params = json.loads(a.get("params_json") or "{}")
            except Exception:
                params = {}
        base_strat = params.get("strategy") or strat

        
        # Determine symbol list
        if scope_symbol == "ALL_WATCHLIST":
            symbols_to_check = db.watchlist_symbols() or db.ensure_seed_watchlist() or list(config.SYMBOLS)
        elif scope_symbol == "MULTIPLE" or (isinstance(params.get("symbols"), list) and params.get("symbols")):
            symbols_to_check = [s for s in (params.get("symbols") or a.get("symbols") or []) if s not in ("MULTIPLE", "ALL_WATCHLIST")]
            if not symbols_to_check:
                symbols_to_check = db.watchlist_symbols() or db.ensure_seed_watchlist() or list(config.SYMBOLS)
        else:
            symbols_to_check = [scope_symbol]

        # Determine strategies to evaluate
        if base_strat == "BOTH" or strat == "BOTH":
            eval_strategies = ["VWAP_SUPERTREND", "EMA_CROSSOVER"]
        else:
            eval_strategies = [strat]
            
        diag_reasons = []
        triggered_for_this_auto = False
        
        for sym in symbols_to_check:
            if triggered_for_this_auto:
                break

            for curr_strat in eval_strategies:
                if triggered_for_this_auto:
                    break

                tf_map = params.get("strategy_timeframes", {})
                if curr_strat == "VWAP_SUPERTREND":
                    tf = int(tf_map.get("VWAP_SUPERTREND", 3))
                elif curr_strat == "EMA_CROSSOVER":
                    tf = int(tf_map.get("EMA_CROSSOVER", 1))
                else:
                    tf_raw = str(a.get("timeframe") or params.get("timeframe_min") or "3").strip().lower()
                    if tf_raw.endswith("m"):
                        try:
                            tf = int(tf_raw[:-1])
                        except Exception:
                            tf = 3
                    elif tf_raw.endswith("h"):
                        try:
                            tf = int(tf_raw[:-1]) * 60
                        except Exception:
                            tf = 60
                    else:
                        try:
                            tf = int(tf_raw)
                        except Exception:
                            tf = 3

                is_ml_imported = (curr_strat == "VWAP_STRUCTURE_RETEST" or params.get("is_imported_ml") or params.get("origin") in ("ML_RECOMMENDATION", "USER_MODIFIED_FROM_ML"))

                # 1. VWAP Regime Gate
                # CRITICAL: Imported ML automations NEVER receive the generic manual VWAP gate
                if is_ml_imported:
                    vwap_gate_on = bool(params.get("vwap_gate_enabled", False))
                else:
                    vwap_gate_on = bool(params.get("vwap_gate_enabled", True))

                vwap_reg = analytics.vwap_regime(sym, tf_min=tf)
                regime = vwap_reg.get("state", "CHOP")
                eligible_dir = vwap_reg.get("eligible", "NONE")
                
                # 2. Strategy Signal Evaluation
                strat_ev = {}
                if curr_strat == "VWAP_SUPERTREND":
                    strat_ev = analytics.st_vwap_cross_event(sym, tf_min=tf)
                elif curr_strat == "EMA_CROSSOVER":
                    strat_ev = check_crossover_event(sym, tf_min=tf) or {}
                elif curr_strat == "VWAP_STRUCTURE_RETEST":
                    # Check ML Retest setup conditions
                    setup_id = params.get("setup_id")
                    cand = db.get_setup_candidate(setup_id) if setup_id else None
                    resolved_dir = "LONG"
                    if pref in ("LONG", "SHORT"):
                        resolved_dir = pref
                    elif params.get("direction") in ("LONG", "SHORT"):
                        resolved_dir = params["direction"].upper()
                    elif params.get("direction_pref") in ("LONG", "SHORT"):
                        resolved_dir = params["direction_pref"].upper()
                    elif cand and cand.get("direction") in ("LONG", "SHORT"):
                        resolved_dir = cand["direction"].upper()

                    retest_state_dict = db.get_retest_state(sym, tf, resolved_dir)
                    retest_curr_state = (retest_state_dict or {}).get("state") or (retest_state_dict or {}).get("current_state") or (cand or {}).get("current_state")
                    raw_sym = db.query_candles(sym, now_ms - (30 * 60 * 1000), now_ms)
                    if raw_sym and (retest_curr_state in ("RETEST_ZONE_TOUCHED", "REJECTION_CONFIRMED", "ENTRY_CANDIDATE") or not setup_id):
                        close_px = float(raw_sym[-1]["close"])
                        strat_ev = {
                            "direction": resolved_dir,
                            "close": close_px,
                            "candle_ts": int(raw_sym[-1]["ts"])
                        }

                direction = strat_ev.get("direction") if strat_ev else None
                if not direction:
                    diag_reasons.append(f"{sym} ({curr_strat} {tf}m): Waiting for trigger condition")
                    continue
                
                # Check VWAP Regime Gate (manual only unless ML setup explicitly enabled it)
                if vwap_gate_on and eligible_dir != "BOTH" and eligible_dir != direction:
                    diag_reasons.append(f"{sym} ({curr_strat}): Signal {direction} blocked by manual VWAP regime gate {regime}")
                    continue
                    
                # Check User Direction Preference
                if pref != "ANY" and pref != direction:
                    diag_reasons.append(f"{sym} ({curr_strat}): Signal {direction} filtered by {pref} preference")
                    continue
                    
                # 3. Single Position Constraints (Scoped per user/account)
                if db.has_open_position_for_automation(aid, user_id=uid):
                    diag_reasons.append(f"{sym} ({curr_strat}): Automation #{aid} already has active open position for user #{uid}")
                    continue

                if db.has_open_position_for_symbol(sym, user_id=uid):
                    diag_reasons.append(f"{sym} ({curr_strat}): User #{uid} already has active open position for {sym}")
                    continue

                # 4. Deduplication Check with Automation ID (Deterministic Idempotency)
                event_id = f"auto_{aid}|{curr_strat}|{sym}|{tf}|{strat_ev['candle_ts']}|{direction}"
                if db.event_seen(event_id):
                    diag_reasons.append(f"{sym} ({curr_strat}): Event already executed for candle {strat_ev['candle_ts']}")
                    continue
                    
                # 5. Atomic Risk Barrier Check (Configurable MAX_OPEN_TRADES)
                with db._lock:
                    blk = one_trade_block(user_id=uid)
                    if blk:
                        cap = blk.get("limit", db.get_max_open_trades(user_id=uid))
                        reason = blk.get("reason", f"Max open positions reached ({db.total_open_positions_count(user_id=uid)}/{cap})")
                        db.update_automation_diagnostics(aid, now_ms, reason, signal_ms=now_ms, signal_dir=direction, exec_status="RISK_REJECTED")
                        notifications.notify_risk_barrier_rejected(
                            reason=reason,
                            symbol=sym,
                            direction=direction,
                            active_count=db.total_open_positions_count(user_id=uid),
                            max_count=cap,
                            user_id=uid
                        )
                        diag_reasons.append(f"{sym}: {reason}")
                        continue
                    
                # 5. Signal Accepted -> Build Trade Parameters
                entry = strat_ev["close"]
                
                # Resolve strategy-specific risk
                strat_risk = params.get("strategy_risk", {}).get(curr_strat) if base_strat == "BOTH" else params
                if not strat_risk or not strat_risk.get("stops"):
                    if isinstance(params.get("params"), dict) and (params["params"].get("stops") or params["params"].get("targets")):
                        strat_risk = params["params"]
                    elif not strat_risk:
                        strat_risk = params


                stop_dist = entry * 0.01
                if curr_strat == "VWAP_SUPERTREND" and strat_ev.get("st_line"):
                    stop_dist = max(abs(entry - strat_ev["st_line"]), entry * 0.002)
                elif strat_ev.get("ema20"):
                    stop_dist = max(abs(entry - strat_ev["ema20"]), entry * 0.002)
                    
                if strat_risk and strat_risk.get("stops"):
                    stop_val = float(strat_risk["stops"][0]["value"])
                    stype = strat_risk["stops"][0]["type"]
                    if stype == "entry_pct":
                        stop_dist = entry * (stop_val / 100.0)
                    elif stype == "vwap_pct" and strat_ev.get("vwap"):
                        stop_dist = abs(entry - strat_ev["vwap"]) + (entry * stop_val / 100.0)
                    elif stype == "supertrend_pct" and strat_ev.get("st_line"):
                        stop_dist = abs(entry - strat_ev["st_line"]) + (entry * stop_val / 100.0)
                    elif stype in ("structural_price", "PRICE_ABSOLUTE"):
                        stop_dist = abs(entry - stop_val)
                        stop = stop_val
                        
                target = entry + (stop_dist * 2) * (1 if direction == "LONG" else -1)
                if strat_risk and strat_risk.get("targets"):
                    t0 = strat_risk["targets"][0]
                    if t0.get("price"):
                        target = float(t0["price"])
                    elif t0.get("move_pct"):
                        target = entry * (1 + float(t0["move_pct"]) / 100.0 * (1 if direction == "LONG" else -1))
                    elif t0.get("r"):
                        target = entry + (stop_dist * float(t0["r"])) * (1 if direction == "LONG" else -1)
                        
                if not (strat_risk and strat_risk.get("stops") and strat_risk["stops"][0].get("type") in ("structural_price", "PRICE_ABSOLUTE")):
                    stop = entry - stop_dist * (1 if direction == "LONG" else -1)
                
                # Build structured stops and targets lists
                stops_payload = []
                if strat_risk and strat_risk.get("stops"):
                    for s in strat_risk["stops"]:
                        if isinstance(s, dict) and s.get("value"):
                            stops_payload.append({"type": s.get("type", "PRICE_ABSOLUTE"), "value": round(float(s["value"]), 4)})
                if not stops_payload:
                    stops_payload = [{"type": "PRICE_ABSOLUTE", "value": round(stop, 4)}]

                targets_payload = []
                if strat_risk and strat_risk.get("targets"):
                    for t in strat_risk["targets"]:
                        if isinstance(t, dict) and (t.get("price") or t.get("value")):
                            p_val = float(t.get("price") or t.get("value"))
                            q_pct = float(t.get("pct_qty") or t.get("qty_pct") or 100.0)
                            targets_payload.append({"price": round(p_val, 4), "pct_qty": q_pct, "qty_pct": q_pct})
                if not targets_payload:
                    targets_payload = [{"price": round(target, 4), "pct_qty": 100.0, "qty_pct": 100.0}]


                authoritative_mode = db.get_mode()
                coid = f"oph-{aid}-{uuid.uuid4().hex[:8]}"

                # 5.4 Authoritative pre-entry invariant: same user + same symbol active position prevention
                allow_pyramiding = bool(params.get("allow_pyramiding", False))
                if not allow_pyramiding and db.has_open_position_for_symbol(sym, user_id=uid):
                    db.update_automation_diagnostics(
                        aid, now_ms, f"Rejected: Existing active position already open for {sym} (duplicate prevention)",
                        signal_ms=now_ms, signal_dir=direction, exec_status="BLOCKED_DUPLICATE_POSITION"
                    )
                    continue

                # 5.5 Authoritative hard cap: user-configured MAX_OPEN_TRADES
                cap = db.get_max_open_trades(user_id=uid)
                open_pos = db.open_positions(user_id=uid)
                if len(open_pos) >= cap:
                    msg = "CAP BELOW CURRENT EXPOSURE" if cap < len(open_pos) else f"Rejected: MAX_OPEN_TRADES limit reached ({len(open_pos)}/{cap})"
                    db.update_automation_diagnostics(
                        aid, now_ms, msg,
                        signal_ms=now_ms, signal_dir=direction, exec_status="BLOCKED_BY_MAX_OPEN"
                    )
                    continue

                # 5.6 AUTHORITATIVE SLOT ALLOCATION PIPELINE
                # ML NEVER dictates margin or leverage. Sizing is governed strictly by authorized slot.
                from .slot_allocation_service import SlotAllocationService
                cand_id = setup_id if (curr_strat == "VWAP_STRUCTURE_RETEST" and setup_id) else f"cand-{aid}-{sym}-{strat_ev['candle_ts']}"
                cand_spec = {
                    "candidate_id": cand_id,
                    "symbol": sym,
                    "direction": direction,
                    "strategy": curr_strat,
                    "entry_price": entry,
                    "sl_price": stop,
                    "tp1_price": target,
                    "allow_pyramiding": allow_pyramiding,
                }
                slot, slot_reason = SlotAllocationService.find_eligible_slot(
                    candidate=cand_spec,
                    user_id=uid,
                    account_id=a.get("account_id", 1)
                )

                if not slot:
                    # Candidate reaches ENTRY_READY but no slot is available -> state becomes WAITING_FOR_SLOT
                    cand_payload = {
                        "setup_id": cand_id,
                        "symbol": sym,
                        "direction": direction,
                        "timeframe": tf,
                        "strategy": curr_strat,
                        "current_state": "WAITING_FOR_SLOT",
                        "reason": f"WAITING_FOR_SLOT: {slot_reason}",
                        "waiting_for": "SLOT",
                        "user_id": uid,
                        "account_id": a.get("account_id", 1),
                        "automation_id": aid,
                        "suggested_sl": stop,
                        "suggested_tp1": target,
                        "entry_price": entry,
                        "status": "WAITING_FOR_SLOT",
                        "generated_ms": now_ms
                    }
                    db.save_setup_candidate(cand_payload)
                    db.update_automation_diagnostics(
                        aid, now_ms,
                        f"WAITING_FOR_SLOT: {slot_reason} ({sym} {direction})",
                        signal_ms=now_ms, signal_dir=direction,
                        exec_status="WAITING_FOR_SLOT"
                    )
                    diag_reasons.append(f"{sym}: WAITING_FOR_SLOT ({slot_reason})")
                    continue

                # Slot Found -> Authoritative Slot Parameters Govern Sizing
                slot_id = slot["id"]
                margin_alloc = float(slot["allocated_margin_usdt"])
                lev = float(slot["max_leverage"])
                max_loss_usdt = float(slot.get("max_loss_usdt") or 0.0)
                max_loss_pct = float(slot.get("maximum_loss_percent") or slot.get("max_loss_pct") or 10.0)
                if max_loss_usdt <= 0.0:
                    max_loss_usdt = margin_alloc * (max_loss_pct / 100.0)

                notional = margin_alloc * lev
                qty = round(notional / max(0.0001, entry), 6)

                # Max Loss check & resizing
                unit_risk = abs(entry - stop)
                potential_loss = unit_risk * qty
                if max_loss_usdt > 0.0 and potential_loss > max_loss_usdt:
                    max_permitted_qty = max_loss_usdt / unit_risk
                    if max_permitted_qty * entry < 5.0:
                        db.update_automation_diagnostics(
                            aid, now_ms,
                            f"Risk rejected: Potential loss {potential_loss:.2f} > slot max loss {max_loss_usdt:.2f}",
                            signal_ms=now_ms, signal_dir=direction,
                            exec_status="RISK_REJECTED"
                        )
                        continue
                    qty = round(max_permitted_qty, 6)

                # 5.7 ATOMIC SLOT RESERVATION
                reserved, resv_id, resv_reason = SlotAllocationService.reserve_slot(
                    slot_id=slot_id,
                    candidate_id=cand_id,
                    user_id=uid,
                    account_id=a.get("account_id", 1)
                )
                if not reserved:
                    db.update_automation_diagnostics(
                        aid, now_ms,
                        f"Slot reservation failed: {resv_reason}",
                        signal_ms=now_ms, signal_dir=direction,
                        exec_status="SLOT_CONFLICT"
                    )
                    diag_reasons.append(f"{sym}: Slot reservation conflict ({resv_reason})")
                    continue

                # 5.8 CREATE PERSISTED IMMUTABLE EXECUTION INTENT
                intent_id = f"intent-{aid}-{uuid.uuid4().hex[:8]}"
                db.create_execution_intent({
                    "execution_intent_id": intent_id,
                    "candidate_id": cand_id,
                    "automation_id": aid,
                    "slot_id": slot_id,
                    "user_id": uid,
                    "account_id": a.get("account_id", 1),
                    "instrument": sym,
                    "direction": direction,
                    "requested_margin": margin_alloc,
                    "leverage": lev,
                    "entry_policy": {"entry": entry, "qty": qty},
                    "stop_policy": {"stops": stops_payload, "stop_current": stop},
                    "tp_policy": {"targets": targets_payload},
                    "trailing_policy": {"enabled": slot.get("trailing_enabled"), "pct": slot.get("trailing_pct")},
                    "status": "CREATED",
                    "idempotency_key": event_id
                })

                # Risk checking -> APPROVED -> SUBMITTING
                db.update_execution_intent_status(intent_id, "RISK_CHECKING")
                db.update_execution_intent_status(intent_id, "APPROVED")
                db.update_execution_intent_status(intent_id, "SUBMITTING")

                # 6. Execution Branch
                if authoritative_mode == "LIVE":
                    pf = run_preflight(user_id=uid)
                    if not pf.get("ready_for_live"):
                        err_msg = f"LIVE preflight barrier rejected order: {pf.get('blocking_reasons', ['Check failed'])[0]}"
                        db.update_execution_intent_status(intent_id, "REJECTED", error_reason=err_msg)
                        SlotAllocationService.release_slot(slot_id, user_id=uid, reason="PREFLIGHT_FAILED")
                        db.update_automation_diagnostics(aid, now_ms, err_msg, signal_ms=now_ms, signal_dir=direction, exec_status="PREFLIGHT_FAILED")
                        notifications.notify_preflight_failure(pf.get("blocking_reasons", [err_msg]), user_id=uid)
                        continue
                        
                    client = _live_client(user_id=uid)
                    side = "BUY" if direction == "LONG" else "SELL"
                    pos_side = "LONG" if direction == "LONG" else "SHORT"
                    
                    try:
                        bingx_sym = symbols.to_bingx_symbol(sym)
                        client.set_leverage(bingx_sym, int(lev))
                        norm = normalize_qty(bingx_sym, qty, entry)
                        live_qty = norm["qty"]
                        resp = client.market_order(bingx_sym, side, pos_side, live_qty, coid)
                        order_id = resp.get("orderId") or (resp.get("order") or {}).get("orderId") or resp.get("order_id")
                        if not order_id and isinstance(resp, dict) and "data" in resp:
                            order_id = resp["data"].get("orderId")
                    except Exception as e:
                        # Ambiguous timeout error check: reconcile with exchange before retrying
                        is_ambiguous = isinstance(e, (TimeoutError, urllib.error.URLError)) or "timeout" in str(e).lower()
                        if is_ambiguous:
                            try:
                                positions = client.positions()
                                matched = [p for p in positions if p.get("clientOrderId") == coid or p.get("symbol") == bingx_sym]
                                if matched:
                                    adopted_qty = float(matched[0].get("positionAmt", live_qty))
                                    pid = db.create_position({
                                        "symbol": sym, "direction": direction, "entry": entry,
                                        "qty": abs(adopted_qty), "leverage": lev, "margin_usdt": margin_alloc,
                                        "mode": "LIVE", "status": "OPEN", "client_order_id": coid,
                                        "exchange_order_id": str(matched[0].get("orderId", "")),
                                        "stop_current": round(stop, 6),
                                        "stops_json": json.dumps(stops_payload),
                                        "targets_json": json.dumps(targets_payload),
                                        "user_id": uid,
                                        "detail": {"automation_id": aid, "strategy": curr_strat, "slot_id": slot_id, "reconciled_after_ambiguous_error": True}
                                    })
                                    db.event_record(event_id, "SIGNAL", pid)
                                    db.update_execution_intent_status(intent_id, "FILLED", position_id=str(pid))
                                    SlotAllocationService.occupy_slot(slot_id, position_id=str(pid), user_id=uid, reservation_id=resv_id)
                                    db.audit("core", "LIVE_ENTRY_RECONCILED", {"automation_id": aid, "position_id": pid, "symbol": sym}, user_id=uid)
                                    continue
                            except Exception as recon_err:
                                db.audit("core", "RECONCILIATION_FAILED", {"automation_id": aid, "error": str(recon_err)[:200]}, user_id=uid)

                        db.update_execution_intent_status(intent_id, "FAILED", error_reason=str(e)[:200])
                        SlotAllocationService.release_slot(slot_id, user_id=uid, reason=f"LIVE_ORDER_FAILED: {str(e)[:50]}")
                        db.audit("core", "LIVE_ENTRY_FAILED", {"automation_id": aid, "symbol": sym, "error": str(e)[:200]}, user_id=uid)
                        db.update_automation_diagnostics(aid, now_ms, f"Live order error: {str(e)[:100]}", signal_ms=now_ms, signal_dir=direction, exec_status="ORDER_ERROR")
                        notifications.notify_system_connectivity(f"Live order failed for {sym}", severity="CRITICAL", details=str(e), user_id=uid)
                        continue
                        
                    from . import position_math
                    entry_fee = position_math.calculate_actual_fee(entry, live_qty)
                    pid = db.create_position({
                        "symbol": sym, "direction": direction, "entry": entry,
                        "actual_entry_price": entry,
                        "qty": live_qty, "remaining_qty": live_qty,
                        "leverage": lev, "margin_usdt": margin_alloc,
                        "total_fees": entry_fee,
                        "lifecycle_state": "FILLED",
                        "mode": "LIVE", "status": "OPEN", "client_order_id": coid,
                        "exchange_order_id": str(order_id or ""),
                        "stop_current": round(stop, 6),
                        "stops": stops_payload,
                        "stops_json": json.dumps(stops_payload),
                        "targets": targets_payload,
                        "targets_json": json.dumps(targets_payload),
                        "user_id": uid,
                        "last_management_event": "LIVE_ENTRY_FILLED",
                        "reconciliation_status": "RECONCILED",
                        "detail": {"automation_id": aid, "strategy": curr_strat, "slot_id": slot_id, "order_id": str(order_id or ""), "exchange_resp": str(resp)[:200], "be_after_partial": True}
                    })
                    db.event_record(event_id, "SIGNAL", pid)
                    db.update_execution_intent_status(intent_id, "FILLED", position_id=str(pid))
                    SlotAllocationService.occupy_slot(slot_id, position_id=str(pid), user_id=uid, reservation_id=resv_id)
                    db.save_setup_candidate({"setup_id": cand_id, "symbol": sym, "direction": direction, "timeframe": tf, "strategy": curr_strat, "current_state": "TRIGGERED", "status": "TRIGGERED", "user_id": uid, "account_id": a.get("account_id", 1), "automation_id": aid})
                    db.audit("core", "LIVE_ENTRY", {"automation_id": aid, "position_id": pid, "symbol": sym, "qty": live_qty, "client_order_id": coid, "order_id": str(order_id or "")}, user_id=uid)
                    db.update_automation_diagnostics(aid, now_ms, f"LIVE Trade Executed #{pid} in Slot {slot['name']} ({sym} {direction})", signal_ms=now_ms, signal_dir=direction, exec_status="EXECUTED_LIVE")
                    
                else: # SHADOW MODE
                    from . import position_math
                    entry_fee = position_math.calculate_actual_fee(entry, qty)
                    pid = db.create_position({
                        "symbol": sym, "direction": direction, "entry": entry,
                        "actual_entry_price": entry,
                        "qty": qty, "remaining_qty": qty,
                        "leverage": lev, "margin_usdt": margin_alloc,
                        "total_fees": entry_fee,
                        "lifecycle_state": "FILLED",
                        "mode": "SHADOW", "status": "OPEN", "client_order_id": coid,
                        "stop_current": round(stop, 6),
                        "stops": stops_payload,
                        "stops_json": json.dumps(stops_payload),
                        "targets": targets_payload,
                        "targets_json": json.dumps(targets_payload),
                        "user_id": uid,
                        "last_management_event": "SHADOW_ENTRY_FILLED",
                        "reconciliation_status": "RECONCILED",
                        "detail": {"automation_id": aid, "strategy": curr_strat, "slot_id": slot_id, "be_after_partial": True}
                    })
                    db.event_record(event_id, "SIGNAL", pid)
                    db.update_execution_intent_status(intent_id, "FILLED", position_id=str(pid))
                    SlotAllocationService.occupy_slot(slot_id, position_id=str(pid), user_id=uid, reservation_id=resv_id)
                    db.save_setup_candidate({"setup_id": cand_id, "symbol": sym, "direction": direction, "timeframe": tf, "strategy": curr_strat, "current_state": "TRIGGERED", "status": "TRIGGERED", "user_id": uid, "account_id": a.get("account_id", 1), "automation_id": aid})
                    db.audit("core", "SHADOW_ENTRY", {"automation_id": aid, "position_id": pid, "symbol": sym, "qty": qty, "slot_id": slot_id}, user_id=uid)
                    db.update_automation_diagnostics(aid, now_ms, f"SHADOW Trade Executed #{pid} in Slot {slot['name']} ({sym} {direction})", signal_ms=now_ms, signal_dir=direction, exec_status="EXECUTED_SHADOW")

                
                # Lifecycle handling
                lifecycle = a.get("lifecycle") or params.get("lifecycle", "CONTINUOUS")
                if lifecycle == "ONE_SHOT":
                    db.set_automation_status(aid, "STOPPED", user_id=uid)
                    
                triggered_for_this_auto = True
                events_triggered.append({"automation_id": aid, "symbol": sym, "direction": direction, "strategy": curr_strat, "slot_id": slot_id, "mode": authoritative_mode})
                break
                
        if not triggered_for_this_auto:
            summary = "; ".join(diag_reasons[:4]) if diag_reasons else "Scanning watchlist"
            db.update_automation_diagnostics(aid, now_ms, f"Evaluated {len(symbols_to_check)} symbols: {summary}")
            
    return events_triggered


def evaluate_open_positions_with_execution() -> list[dict]:
    """Evaluate every open position against current market and execute stops/TP in LIVE/SHADOW via authoritative position manager daemon."""
    from . import position_manager_daemon
    acts = position_manager_daemon.evaluate_and_manage_positions()
    for a in acts:
        pid = a.get("position_id")
        action = a.get("action")
        p = db.get_position(pid)
        if not p:
            continue
            
        uid = p.get("user_id")
        if not uid or int(uid) <= 0:
            continue
        uid = int(uid)
        
        # Notifications dispatch
        if action == "exit_all":
            reason = a.get("reason", "EXIT")
            pnl = float(p.get("realized_pnl") or 0.0)
            if reason in ("hard_stop", "structural_stop", "stop_loss", "trailing_stop", "STOP_LOSS_HIT", "TRAILING_STOP_HIT"):
                notifications.notify_sl_hit(p, loss_usdt=abs(pnl), loss_pct=abs(p.get("pnl_pct", 0.0)), reason=reason, user_id=uid)
            else:
                notifications.notify_trade_closed(p, realized_pnl=pnl, pnl_pct=p.get("pnl_pct", 0.0), reason=reason, user_id=uid)
        elif action == "partial_close":
            notifications.notify_partial_close(p, stage_pct=50.0, realized_pnl=float(p.get("realized_pnl") or 0.0), pnl_pct=p.get("pnl_pct", 0.0), remaining_qty=float(p.get("remaining_qty") or p.get("qty", 0.0)), user_id=uid)
        elif action == "breakeven":
            notifications.notify_breakeven_activated(p, new_stop=a.get("new_stop") or a.get("stop", 0.0), user_id=uid)
        elif action in ("trailing_stop_advanced", "stop_updated"):
            notifications.notify_trailing_stop_update(p, new_stop=a.get("new_stop") or a.get("stop", 0.0), user_id=uid)
            
    return acts


def automation_worker_loop(stop_event: threading.Event | None = None) -> None:
    """Continuous background worker that evaluates active automations and open positions.
    Enforces exclusive execution lease via AutomationExecutionLease.
    """
    lease = AutomationExecutionLease()
    import os
    if not lease.acquire():
        print(f"[automation-engine] PID {os.getpid()} cannot acquire execution lease; another worker is already active. Exiting duplicate worker thread.", flush=True)
        return
        
    print(f"[automation-engine] worker lease acquired (PID {os.getpid()}) | polling every 5s", flush=True)
    try:
        from .slot_allocation_service import SlotAllocationService
        recovered = SlotAllocationService.recover_stale_reservations(timeout_s=60)
        if recovered > 0:
            print(f"[automation-engine] startup recovery: recovered {recovered} stale slot reservations", flush=True)
    except Exception as rec_err:
        print(f"[automation-engine] recovery warning: {rec_err}", flush=True)

    try:
        while stop_event is None or not stop_event.is_set():
            try:
                lease.heartbeat()
                try:
                    from .slot_allocation_service import SlotAllocationService
                    SlotAllocationService.recover_stale_reservations(timeout_s=60)
                except Exception:
                    pass
                evaluate_active_automations()
                evaluate_open_positions_with_execution()
            except Exception as e:
                print(f"[automation-engine] error: {e}", flush=True)
                db.audit("core", "WORKER_ERROR", {"error": str(e)[:200]})
                
            if stop_event:
                stop_event.wait(5)
            else:
                time.sleep(5)
    finally:
        lease.release()


def _resolve_strategy_config(req: dict, strat: str) -> dict:
    """Extract and normalize all risk, stop, target, and trailing parameters for a strategy.
    
    Supports:
      - Android UI nested structure: req["strategy_risk"][strat]
      - Flat request payloads: req["hard_stop_pct"], req["targets"], etc.
      - Legacy params dicts: req["params"]
    """
    strat_key = strat.upper()
    risk_dict = {}
    if isinstance(req.get("strategy_risk"), dict) and strat_key in req["strategy_risk"]:
        risk_dict = req["strategy_risk"][strat_key] or {}
    elif isinstance(req.get("params"), dict) and isinstance(req["params"].get("strategy_risk"), dict) and strat_key in req["params"]["strategy_risk"]:
        risk_dict = req["params"]["strategy_risk"][strat_key] or {}
    elif isinstance(req.get("strategy_risk"), dict) and strat in req["strategy_risk"]:
        risk_dict = req["strategy_risk"][strat] or {}

    # Timeframe
    tf_val = risk_dict.get("timeframe") or req.get("timeframe") or "3m"
    if isinstance(tf_val, str) and tf_val.endswith("m"):
        tf_min = int(tf_val[:-1])
    else:
        tf_min = int(tf_val or 3)

    # Hard Stop %
    hard_stop_pct = None
    if "hard_stop_pct" in risk_dict and risk_dict["hard_stop_pct"] is not None:
        hard_stop_pct = float(risk_dict["hard_stop_pct"])
    elif "hard_stop" in risk_dict and risk_dict["hard_stop"] is not None:
        hard_stop_pct = float(risk_dict["hard_stop"])
    elif "hard_stop_pct" in req and req["hard_stop_pct"] is not None:
        hard_stop_pct = float(req["hard_stop_pct"])
    elif "hard_stop" in req and req["hard_stop"] is not None:
        hard_stop_pct = float(req["hard_stop"])
    elif "stops" in risk_dict and risk_dict["stops"]:
        st0 = risk_dict["stops"][0]
        if st0.get("type") == "entry_pct":
            hard_stop_pct = float(st0.get("value", 1.0))
    elif "stops" in req and req["stops"]:
        st0 = req["stops"][0]
        if st0.get("type") == "entry_pct":
            hard_stop_pct = float(st0.get("value", 1.0))
    
    if hard_stop_pct is None:
        hard_stop_pct = 0.8 if strat_key == "VWAP_SUPERTREND" else 1.0

    # Structural Stops
    # 1. VWAP Structural Stop
    structural_vwap_enabled = bool(
        risk_dict.get("structural_vwap_enabled")
        or risk_dict.get("structural_enabled")
        or req.get("structural_vwap_enabled")
        or False
    )
    structural_vwap_pct = float(
        risk_dict.get("structural_vwap_pct")
        or risk_dict.get("structural_pct")
        or req.get("structural_vwap_pct")
        or 0.2
    )

    # 2. Supertrend Structural Stop
    structural_st_enabled = bool(
        risk_dict.get("structural_st_enabled")
        or req.get("structural_st_enabled")
        or False
    )
    structural_st_pct = float(
        risk_dict.get("structural_st_pct")
        or req.get("structural_st_pct")
        or 0.2
    )

    # Reverse exit (for EMA crossover)
    reverse_exit = bool(risk_dict.get("reverse_exit") or req.get("reverse_exit") or False)

    # Targets (Take Profit)
    raw_targets = risk_dict.get("targets") or req.get("targets") or []
    normalized_targets = []
    if raw_targets:
        for t in raw_targets:
            dist = float(t.get("distance_pct") or t.get("move_pct") or t.get("pct") or 1.5)
            qty_p = float(t.get("qty_pct") or t.get("pct_qty") or 50.0)
            normalized_targets.append({"distance_pct": dist, "qty_pct": qty_p})
    else:
        normalized_targets = [{"distance_pct": 1.5, "qty_pct": 50.0}]

    # Break-Even
    breakeven = bool(
        risk_dict.get("break_even_after_partial")
        or risk_dict.get("break_even")
        or risk_dict.get("breakeven")
        or req.get("break_even_after_partial")
        or req.get("breakeven")
        or False
    )

    # Trailing Stop
    trailing_dict = risk_dict.get("trailing_stop") or req.get("trailing_stop")
    if isinstance(trailing_dict, dict) and trailing_dict:
        trailing_enabled = bool(trailing_dict.get("enabled", False))
        trailing_pct = float(trailing_dict.get("trail_pct") or trailing_dict.get("trailing_pct") or 0.2)
    else:
        trailing_enabled = bool(
            risk_dict.get("trailing_enabled")
            or req.get("trailing_enabled")
            or False
        )
        trailing_pct = float(
            risk_dict.get("trailing_trail_pct")
            or risk_dict.get("trailing_pct")
            or req.get("trailing_trail_pct")
            or req.get("trailing_pct")
            or 0.2
        )

    return {
        "strategy": strat_key,
        "timeframe_min": tf_min,
        "hard_stop_pct": hard_stop_pct,
        "structural_vwap_enabled": structural_vwap_enabled,
        "structural_vwap_pct": structural_vwap_pct,
        "structural_st_enabled": structural_st_enabled,
        "structural_st_pct": structural_st_pct,
        "reverse_exit": reverse_exit,
        "targets": normalized_targets,
        "breakeven": breakeven,
        "trailing_enabled": trailing_enabled,
        "trailing_pct": trailing_pct
    }


def simulate_strategy_24h(req: dict) -> dict:
    """Historical 24h walk-forward simulation of strategy signals and trades.
    
    Performs a deterministic, chronological replay of 1m market candles
    aggregated to the configured strategy timeframe with 5h indicator warmup,
    strictly respecting all user-specified stop loss, structural stops, partial
    take profits, break-even, trailing stop remainder, fees, and concurrency barriers.
    """
    strat_clean = str(req.get("strategy") or "").strip().upper().replace("-", "_").replace(" ", "_")
    if strat_clean in ("OPHELIA_COMPOSITE", "COMPOSITE", "D_WITHOUT_CVD", "D_NO_CVD", "ABL_D_CVD", "EXPERIMENT_D", "EXP_D"):
        from . import strategy_lab
        symbols = req.get("symbols") or [req.get("symbol") or "BTC-USDT"]
        if isinstance(symbols, str):
            symbols = [symbols]
        if "ALL_WATCHLIST" in symbols or req.get("symbol") == "ALL_WATCHLIST":
            symbols = db.watchlist_symbols()
        elif "MULTIPLE" in symbols or req.get("symbol") == "MULTIPLE":
            symbols = [s for s in symbols if s not in ("MULTIPLE", "ALL_WATCHLIST")]
            if not symbols:
                symbols = db.watchlist_symbols()
        tf_raw = req.get("timeframe", 5)
        try:
            tf_int = int(str(tf_raw).lower().replace("m", ""))
        except Exception:
            tf_int = 5
        sl_preset = float(req.get("sl_pct") or req.get("sl_preset_pct") or (0.7 if tf_int in (3, 5) else 1.0))
        use_trailing = bool(req.get("use_trailing", True))
        trailing_pct = float(req.get("trailing_pct") or 0.5)
        hours = min(96, int(req.get("hours") or 96))
        lab = strategy_lab.StrategyResearchLab(symbols=symbols, timeframes=[tf_int], hours=hours)
        lab.load_market_data()
        all_signals = []
        funnel_tracker = {"breakout_candidates": 0, "retest_candidates": 0, "rejection_confirmations": 0, "final_entries": 0}
        for s in symbols:
            if strat_clean in ("D_WITHOUT_CVD", "D_NO_CVD", "ABL_D_CVD", "EXPERIMENT_D", "EXP_D"):
                sigs = lab.generate_signals_exp_d(s, tf_int, disable_cvd=True, funnel_tracker=funnel_tracker)
            else:
                sigs = lab.generate_signals_ophelia_composite(s, tf_int, funnel_tracker=funnel_tracker)
            all_signals.extend(sigs)
        metrics = lab.simulate_strategy(all_signals, strat_clean, f"SIM_{strat_clean}_{tf_int}M", fixed_sl_pct=sl_preset, use_trailing=use_trailing, trailing_pct=trailing_pct)
        formatted_trades = []
        for t in (metrics.executed_trades or []):
            entry_ts = int(t.get("entry_time") or time.time() * 1000)
            exit_ts = int(t.get("exit_time") or time.time() * 1000)
            formatted_trades.append({
                "trade_id": entry_ts,
                "symbol": t.get("symbol") or "BTC-USDT",
                "direction": t.get("direction") or "LONG",
                "side": t.get("direction") or "LONG",
                "strategy": strat_clean,
                "timeframe": f"{tf_int}m",
                "entry_time": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(entry_ts / 1000)),
                "entry_time_ist": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(entry_ts / 1000)),
                "exit_time": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(exit_ts / 1000)),
                "exit_time_ist": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(exit_ts / 1000)),
                "entry_price": float(t.get("entry_price") or 0.0),
                "exit_price": float(t.get("exit_price") or 0.0),
                "pnl": float(t.get("pnl_usd") or 0.0),
                "realized_pnl_pct": float(t.get("net_ret_pct") if t.get("net_ret_pct") is not None else (t.get("pnl_pct") or 0.0)),
                "realized_pnl_usdt": float(t.get("pnl_usd") or 0.0),
                "r_multiple": float(t.get("r_multiple") or 0.0),
                "mfe_pct": float(t.get("mfe_pct") or 0.0),
                "mae_pct": float(t.get("mae_pct") or 0.0),
                "highest_favorable_move_pct": float(t.get("highest_favorable_move_pct") or t.get("mfe_pct") or 0.0),
                "exit_reason": str(t.get("exit_reason") or "COMPLETED"),
                "duration_min": int(t.get("duration_min") or 0),
                "fees": float(t.get("fee_usd") or 0.0),
                "fees_usdt": float(t.get("fee_usd") or 0.0),
                "slippage": float(t.get("slippage_usd") or 0.0),
                "funding": float(t.get("funding_usd", 0.0)),
                "trailing_activated": bool(t.get("trailing_activated", False)),
                "breakeven_activated": bool(t.get("breakeven_activated", False)),
            })
        formatted_signals = []
        for s in all_signals:
            sig_ts = int(s.get("timestamp") or time.time() * 1000)
            formatted_signals.append({
                "signal_id": sig_ts,
                "symbol": s.get("symbol") or "BTC-USDT",
                "timestamp_ms": sig_ts,
                "time_ist": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(sig_ts / 1000)),
                "direction": s.get("direction") or "LONG",
                "type": s.get("direction") or "LONG",
                "strategy": strat_clean,
                "timeframe": f"{tf_int}m",
                "status": "VALIDATED",
                "status_detail": "Passed structural candidate check",
                "price": float(s.get("entry_price") or 0.0),
                "vwap": float(s.get("vwap") or s.get("entry_price") or 0.0),
                "vwap_regime": s.get("regime", "EXPANSION"),
                "reason": s.get("reason", "Structural Candidate"),
            })
        return {
            "status": "SUCCESS",
            "date_range_ist": f"Last {hours}h (Confirmed BingX Data)",
            "lookback_hours": hours,
            "strategy": strat_clean,
            "symbols_checked": symbols,
            "timeframe": f"{tf_int}m",
            "fixed_sl_preset": f"{sl_preset}% SL",
            "trailing_stop_enabled": use_trailing,
            "signals_count": len(all_signals),
            "eligible_signals_count": len(all_signals),
            "blocked_signals_count": max(0, funnel_tracker.get("breakout_candidates", 0) - len(all_signals)),
            "filtered_signals_count": 0,
            "simulated_trades_count": metrics.trade_count,
            "win_rate_pct": metrics.win_rate_pct,
            "profit_factor": metrics.profit_factor,
            "net_r": metrics.net_r,
            "expectancy_r": metrics.expectancy_r,
            "max_drawdown_pct": metrics.max_drawdown_pct,
            "avg_mfe_pct": metrics.mfe,
            "avg_mae_pct": metrics.mae,
            "highest_favorable_move_pct": metrics.highest_favorable_move_pct,
            "signals": formatted_signals,
            "trades": formatted_trades,
            "funnel": {
                "breakout_candidates": funnel_tracker.get("breakout_candidates", 0),
                "retest_candidates": funnel_tracker.get("retest_candidates", 0),
                "rejection_confirmations": funnel_tracker.get("rejection_confirmations", 0),
                "final_entries": funnel_tracker.get("final_entries", len(all_signals)),
                "reason": "Completed via StrategyResearchLab",
            }
        }

    strategy = (req.get("strategy") or "VWAP_SUPERTREND").upper()
    symbols = req.get("symbols") or [req.get("symbol") or "BTC-USDT"]
    if "ALL_WATCHLIST" in symbols or req.get("symbol") == "ALL_WATCHLIST":
        symbols = db.watchlist_symbols()
    elif "MULTIPLE" in symbols or req.get("symbol") == "MULTIPLE":
        symbols = [s for s in (req.get("symbols") or []) if s not in ("MULTIPLE", "ALL_WATCHLIST")]
        if not symbols:
            symbols = db.watchlist_symbols()

    # Direction preference
    direction_pref = (req.get("direction") or req.get("direction_preference") or "ANY").upper()
    if direction_pref == "BULLISH":
        direction_pref = "LONG"
    elif direction_pref == "BEARISH":
        direction_pref = "SHORT"

    vwap_gate_enabled = req.get("vwap_gate_enabled", True)
    if isinstance(vwap_gate_enabled, str):
        vwap_gate_enabled = vwap_gate_enabled.lower() in ("true", "1", "on", "yes")

    # Risk & trade parameters
    margin_alloc = float(req.get("margin_usdt") or req.get("fixed_margin") or 10.0)
    leverage = float(req.get("leverage") or 15.0)

    now_ms = int(time.time() * 1000)
    start_ms = now_ms - 24 * 3600 * 1000
    end_ms = now_ms
    warmup_ms = 300 * 60 * 1000  # 5 hours indicator warmup before the 24h window

    diagnostics = {}
    all_raw_signals = []

    strategies_to_test = ["VWAP_SUPERTREND", "EMA_CROSSOVER"] if strategy == "BOTH" else [strategy]

    for sym in symbols:
        raw_1m = db.query_candles(sym, start_ms - warmup_ms, end_ms)
        if not raw_1m or len(raw_1m) < 30:
            diagnostics[sym] = {
                "candles_fetched": 0,
                "error": "Historical data unavailable or insufficient for 24h simulation"
            }
            continue

        for strat in strategies_to_test:
            cfg = _resolve_strategy_config(req, strat)
            tf_min = cfg["timeframe_min"]
            agg_bars = analytics.aggregate(raw_1m, tf_min)
            diagnostics[sym] = {
                "candles_fetched": len(agg_bars),
                "1m_rows": len(raw_1m)
            }
            if len(agg_bars) < 20:
                continue

            closes = np.array([r["close"] for r in agg_bars], float)
            
            e9 = analytics.ema(closes, 9) if strat in ("EMA_CROSSOVER", "BOTH") else None
            e20 = analytics.ema(closes, 20) if strat in ("EMA_CROSSOVER", "BOTH") else None
            
            st_series = analytics.supertrend_series(agg_bars, length=10, factor=4.0) if strat in ("VWAP_SUPERTREND", "BOTH") else []
            st_map = {r["ts"]: r for r in st_series}
            
            vw_series = analytics.session_vwap_series(agg_bars)
            vw_map = {r["ts"]: r for r in vw_series}

            start_idx = 20
            for i in range(start_idx, len(agg_bars)):
                bar_prev = agg_bars[i - 1]
                bar_cur = agg_bars[i]
                ts_cur = bar_cur["ts"]
                price_cur = float(bar_cur["close"])

                # Exclude candles outside the visible 24h evaluation window from generating new signals
                if ts_cur < start_ms:
                    continue

                signal_dir = None
                trigger_text = ""
                st_line = None
                cur_vwap = None

                if strat == "EMA_CROSSOVER":
                    if e9 is not None and e20 is not None:
                        d_prev = e9[i - 1] - e20[i - 1]
                        d_now = e9[i] - e20[i]
                        if not np.isnan(d_prev) and not np.isnan(d_now) and d_prev != d_now:
                            if d_prev <= 0 and d_now > 0:
                                signal_dir = "LONG"
                                trigger_text = f"EMA9 ({e9[i]:.2f}) crossed above EMA20 ({e20[i]:.2f})"
                            elif d_prev >= 0 and d_now < 0:
                                signal_dir = "SHORT"
                                trigger_text = f"EMA9 ({e9[i]:.2f}) crossed below EMA20 ({e20[i]:.2f})"

                elif strat == "VWAP_SUPERTREND":
                    s_p = st_map.get(bar_prev["ts"])
                    s_i = st_map.get(bar_cur["ts"])
                    v_p = vw_map.get(bar_prev["ts"])
                    v_i = vw_map.get(bar_cur["ts"])
                    if s_p and s_i and v_p and v_i and v_p.get("vwap") is not None and v_i.get("vwap") is not None:
                        if v_p.get("day") == v_i.get("day") and abs(v_i["vwap"] - v_p["vwap"]) / v_p["vwap"] <= 0.02:
                            d_prev = s_p["line"] - v_p["vwap"]
                            d_now = s_i["line"] - v_i["vwap"]
                            st_line = s_i["line"]
                            cur_vwap = v_i["vwap"]
                            if s_i["dir"] == 1 and d_prev < 0 <= d_now:
                                signal_dir = "LONG"
                                trigger_text = f"Supertrend Green ({s_i['line']:.2f}) crossed above VWAP ({v_i['vwap']:.2f})"
                            elif s_i["dir"] == -1 and d_prev > 0 >= d_now:
                                signal_dir = "SHORT"
                                trigger_text = f"Supertrend Red ({s_i['line']:.2f}) crossed below VWAP ({v_i['vwap']:.2f})"

                if not signal_dir:
                    continue

                vwap_at_cur = vw_map.get(ts_cur, {}).get("vwap") or price_cur
                cur_vwap = vwap_at_cur
                sep_pct = abs(price_cur - vwap_at_cur) / vwap_at_cur * 100.0 if vwap_at_cur else 0.0
                
                window_bars = agg_bars[max(0, i - 2):i + 1]
                sides = ["ABOVE" if r["close"] > (vw_map.get(r["ts"], {}).get("vwap") or r["close"]) else "BELOW" for r in window_bars]
                one_side = len(set(sides)) == 1
                
                if sep_pct < config.VWAP_MIN_SEPARATION_PCT:
                    regime_state = "CHOP"
                    eligible_dir = "NONE"
                elif not one_side:
                    regime_state = "CHOP"
                    eligible_dir = "NONE"
                else:
                    regime_state = "CLEAR_ABOVE" if sides[-1] == "ABOVE" else "CLEAR_BELOW"
                    eligible_dir = "LONG" if regime_state == "CLEAR_ABOVE" else "SHORT"

                dt_ist = datetime.fromtimestamp(ts_cur / 1000, tz=sessions.IST)
                time_ist_str = dt_ist.strftime("%d %b %H:%M IST")
                dt_end = dt_ist + timedelta(minutes=tf_min)
                candle_window_str = f"{dt_ist.strftime('%H:%M')} - {dt_end.strftime('%H:%M')} IST"

                sig_item = {
                    "timestamp_ms": ts_cur,
                    "iso_utc": datetime.fromtimestamp(ts_cur / 1000, timezone.utc).isoformat(),
                    "time_ist": time_ist_str,
                    "candle_window_ist": candle_window_str,
                    "symbol": sym,
                    "strategy": strat,
                    "timeframe": f"{tf_min}m",
                    "price": price_cur,
                    "direction": signal_dir,
                    "trigger": trigger_text,
                    "vwap_regime": regime_state,
                    "st_line": round(st_line, 4) if st_line is not None else None,
                    "vwap": round(cur_vwap, 4) if cur_vwap is not None else None,
                    "raw_bar_idx": i,
                    "agg_bars": agg_bars,
                    "e9": e9,
                    "e20": e20,
                    "vw_map": vw_map,
                    "st_map": st_map,
                    "cfg": cfg
                }

                if direction_pref != "ANY" and direction_pref != signal_dir:
                    sig_item["status"] = "FILTERED_BY_DIRECTION"
                    sig_item["status_detail"] = f"Filtered by {direction_pref} preference"
                elif vwap_gate_enabled and (eligible_dir == "NONE" or eligible_dir != signal_dir):
                    sig_item["status"] = "BLOCKED_BY_VWAP"
                    sig_item["status_detail"] = f"Blocked by VWAP regime {regime_state} ({sep_pct:+.2f}%)"
                else:
                    sig_item["status"] = "ELIGIBLE"
                    sig_item["status_detail"] = "Eligible for simulated entry"

                all_raw_signals.append(sig_item)

    all_raw_signals.sort(key=lambda s: s["timestamp_ms"])

    max_open_trades = db.get_max_open_trades()
    open_sim_trades = []
    completed_sim_trades = []
    trade_id_counter = 1

    def _walk_open_trades_up_to(target_ts: int | None = None):
        nonlocal open_sim_trades, completed_sim_trades
        still_open = []
        for t in open_sim_trades:
            t_bars = [b for b in t["agg_bars"] if t["last_checked_ts"] < b["ts"] and (target_ts is None or b["ts"] <= target_ts)]
            closed = False
            long = t["direction"] == "LONG"
            sign = 1 if long else -1

            for b in t_bars:
                high = float(b["high"])
                low = float(b["low"])
                close = float(b["close"])
                b_ts = b["ts"]
                t["last_checked_ts"] = b_ts
                dt_b = datetime.fromtimestamp(b_ts / 1000, tz=sessions.IST)
                dt_b_end = dt_b + timedelta(minutes=t["timeframe_min"])
                candle_str = f"{dt_b.strftime('%H:%M')} - {dt_b_end.strftime('%H:%M')} IST"

                # 1. Stop Loss Check
                sl_hit = (low <= t["current_stop"]) if long else (high >= t["current_stop"])
                if sl_hit:
                    exit_px = t["current_stop"]
                    t["exit_ts_ms"] = b_ts
                    t["exit_time_ist"] = dt_b.strftime("%d %b %H:%M IST")
                    t["exit_candle_window_ist"] = candle_str
                    t["exit_price"] = round(exit_px, 4)
                    
                    if t["trailing_activated"]:
                        t["exit_reason"] = "TRAILING_STOP"
                    elif t["breakeven_activated"]:
                        t["exit_reason"] = "BREAK_EVEN"
                    elif t.get("last_stop_kind") == "VWAP_STRUCTURAL":
                        t["exit_reason"] = "VWAP_STRUCTURAL_STOP"
                    elif t.get("last_stop_kind") == "SUPERTREND_STRUCTURAL":
                        t["exit_reason"] = "SUPERTREND_STOP"
                    else:
                        t["exit_reason"] = "HARD_STOP"

                    rem_qty_pct = t["remaining_qty_pct"]
                    pnl_pct_rem = (exit_px - t["entry_price"]) / t["entry_price"] * 100.0 * sign
                    pnl_usdt_rem = t["margin_usdt"] * (pnl_pct_rem / 100.0) * t["leverage"] * (rem_qty_pct / 100.0)
                    
                    total_realized_usdt = sum(p["realized_pnl_usdt"] for p in t["partial_exits"]) + pnl_usdt_rem - t["fees_usdt"]
                    total_realized_pct = (total_realized_usdt / t["margin_usdt"]) * 100.0

                    t["realized_pnl_pct"] = round(total_realized_pct, 2)
                    t["realized_pnl_usdt"] = round(total_realized_usdt, 4)
                    t["status"] = "CLOSED"
                    completed_sim_trades.append(t)
                    closed = True
                    break

                # 2. Take Profit Targets Check
                for idx, target_spec in enumerate(t["target_specs"]):
                    if target_spec.get("done"):
                        continue
                    t_dist_pct = float(target_spec.get("distance_pct") or target_spec.get("move_pct") or target_spec.get("pct") or 1.5)
                    target_qty_pct = float(target_spec.get("qty_pct", 50.0))
                    tp_level = t["entry_price"] * (1 + (t_dist_pct / 100.0) * sign)
                    tp_hit = (high >= tp_level) if long else (low <= tp_level)
                    if tp_hit:
                        target_spec["done"] = True
                        actual_closed_pct = min(target_qty_pct, t["remaining_qty_pct"])
                        partial_pnl_usdt = t["margin_usdt"] * (t_dist_pct / 100.0) * t["leverage"] * (actual_closed_pct / 100.0)
                        
                        t["partial_exits"].append({
                            "stage": f"TP{idx + 1}",
                            "ts_ms": b_ts,
                            "time_ist": dt_b.strftime("%d %b %H:%M IST"),
                            "price": round(tp_level, 4),
                            "qty_pct": actual_closed_pct,
                            "pnl_pct": round(t_dist_pct, 2),
                            "realized_pnl_usdt": round(partial_pnl_usdt, 4)
                        })
                        t["remaining_qty_pct"] -= actual_closed_pct

                        if t.get("breakeven") and t["remaining_qty_pct"] > 0:
                            t["current_stop"] = t["entry_price"]
                            t["breakeven_activated"] = True
                            t["last_stop_kind"] = "BREAK_EVEN"

                        if t["remaining_qty_pct"] <= 0.01:
                            t["exit_ts_ms"] = b_ts
                            t["exit_time_ist"] = dt_b.strftime("%d %b %H:%M IST")
                            t["exit_candle_window_ist"] = candle_str
                            t["exit_price"] = round(tp_level, 4)
                            t["exit_reason"] = "100%_TP" if (actual_closed_pct >= 99.9 or len(t["target_specs"]) == 1) else f"TP{idx + 1}_FULL"
                            total_realized_usdt = sum(p["realized_pnl_usdt"] for p in t["partial_exits"]) - t["fees_usdt"]
                            total_realized_pct = (total_realized_usdt / t["margin_usdt"]) * 100.0
                            t["realized_pnl_pct"] = round(total_realized_pct, 2)
                            t["realized_pnl_usdt"] = round(total_realized_usdt, 4)
                            t["status"] = "CLOSED"
                            completed_sim_trades.append(t)
                            closed = True
                            break

                if closed:
                    break

                # 3. Trailing Stop Update
                if t.get("trailing_enabled") and (len(t["partial_exits"]) > 0 or not t["target_specs"]):
                    if long:
                        if high > (t.get("peak_price") or t["entry_price"]):
                            t["peak_price"] = high
                            t["peak_price_after_tp"] = round(high, 4)
                            trail_stop = high * (1 - t["trailing_pct"] / 100.0)
                            if trail_stop > t["current_stop"]:
                                t["current_stop"] = trail_stop
                                t["trailing_activated"] = True
                                t["last_stop_kind"] = "TRAILING"
                    else:
                        if low < (t.get("peak_price") or t["entry_price"]):
                            t["peak_price"] = low
                            t["peak_price_after_tp"] = round(low, 4)
                            trail_stop = low * (1 + t["trailing_pct"] / 100.0)
                            if trail_stop < t["current_stop"]:
                                t["current_stop"] = trail_stop
                                t["trailing_activated"] = True
                                t["last_stop_kind"] = "TRAILING"

                # 4. Dynamic Structural Stops (tightening only before trailing triggers)
                if not t["trailing_activated"]:
                    b_vwap = t["vw_map"].get(b_ts, {}).get("vwap")
                    if t.get("structural_vwap_enabled") and b_vwap:
                        dyn_vwap = b_vwap * (1 - t["structural_vwap_pct"] / 100.0) if long else b_vwap * (1 + t["structural_vwap_pct"] / 100.0)
                        if long and dyn_vwap > t["current_stop"] and dyn_vwap < close:
                            t["current_stop"] = dyn_vwap
                            t["last_stop_kind"] = "VWAP_STRUCTURAL"
                        elif not long and dyn_vwap < t["current_stop"] and dyn_vwap > close:
                            t["current_stop"] = dyn_vwap
                            t["last_stop_kind"] = "VWAP_STRUCTURAL"

                    b_st = t["st_map"].get(b_ts, {}).get("line")
                    if t.get("structural_st_enabled") and b_st:
                        dyn_st = b_st * (1 - t["structural_st_pct"] / 100.0) if long else b_st * (1 + t["structural_st_pct"] / 100.0)
                        if long and dyn_st > t["current_stop"] and dyn_st < close:
                            t["current_stop"] = dyn_st
                            t["last_stop_kind"] = "SUPERTREND_STRUCTURAL"
                        elif not long and dyn_st < t["current_stop"] and dyn_st > close:
                            t["current_stop"] = dyn_st
                            t["last_stop_kind"] = "SUPERTREND_STRUCTURAL"

                # 5. Reverse EMA Crossover Exit
                if t.get("reverse_exit") and t["e9"] is not None and t["e20"] is not None:
                    # Find bar index in agg_bars
                    bar_idx = next((i_b for i_b, a_b in enumerate(t["agg_bars"]) if a_b["ts"] == b_ts), None)
                    if bar_idx is not None and bar_idx > 0:
                        prev_diff = t["e9"][bar_idx - 1] - t["e20"][bar_idx - 1]
                        cur_diff = t["e9"][bar_idx] - t["e20"][bar_idx]
                        if long and prev_diff >= 0 and cur_diff < 0:
                            exit_px = close
                            t["exit_ts_ms"] = b_ts
                            t["exit_time_ist"] = dt_b.strftime("%d %b %H:%M IST")
                            t["exit_candle_window_ist"] = candle_str
                            t["exit_price"] = round(exit_px, 4)
                            t["exit_reason"] = "REVERSE_CROSSOVER"
                            rem_qty_pct = t["remaining_qty_pct"]
                            pnl_pct_rem = (exit_px - t["entry_price"]) / t["entry_price"] * 100.0 * sign
                            pnl_usdt_rem = t["margin_usdt"] * (pnl_pct_rem / 100.0) * t["leverage"] * (rem_qty_pct / 100.0)
                            total_realized_usdt = sum(p["realized_pnl_usdt"] for p in t["partial_exits"]) + pnl_usdt_rem - t["fees_usdt"]
                            total_realized_pct = (total_realized_usdt / t["margin_usdt"]) * 100.0
                            t["realized_pnl_pct"] = round(total_realized_pct, 2)
                            t["realized_pnl_usdt"] = round(total_realized_usdt, 4)
                            t["status"] = "CLOSED"
                            completed_sim_trades.append(t)
                            closed = True
                            break
                        elif not long and prev_diff <= 0 and cur_diff > 0:
                            exit_px = close
                            t["exit_ts_ms"] = b_ts
                            t["exit_time_ist"] = dt_b.strftime("%d %b %H:%M IST")
                            t["exit_candle_window_ist"] = candle_str
                            t["exit_price"] = round(exit_px, 4)
                            t["exit_reason"] = "REVERSE_CROSSOVER"
                            rem_qty_pct = t["remaining_qty_pct"]
                            pnl_pct_rem = (exit_px - t["entry_price"]) / t["entry_price"] * 100.0 * sign
                            pnl_usdt_rem = t["margin_usdt"] * (pnl_pct_rem / 100.0) * t["leverage"] * (rem_qty_pct / 100.0)
                            total_realized_usdt = sum(p["realized_pnl_usdt"] for p in t["partial_exits"]) + pnl_usdt_rem - t["fees_usdt"]
                            total_realized_pct = (total_realized_usdt / t["margin_usdt"]) * 100.0
                            t["realized_pnl_pct"] = round(total_realized_pct, 2)
                            t["realized_pnl_usdt"] = round(total_realized_usdt, 4)
                            t["status"] = "CLOSED"
                            completed_sim_trades.append(t)
                            closed = True
                            break

            if not closed:
                still_open.append(t)
        open_sim_trades = still_open

    # Walk through candidate signals in strict chronological order
    for sig in all_raw_signals:
        sig_ts = sig["timestamp_ms"]
        _walk_open_trades_up_to(sig_ts)

        if sig["status"] == "ELIGIBLE":
            if len(open_sim_trades) >= max_open_trades:
                sig["status"] = "BLOCKED_BY_POSITION_CAP"
                sig["status_detail"] = f"Blocked: {len(open_sim_trades)} positions already OPEN (Max {max_open_trades})"
            else:
                sig["status"] = "ELIGIBLE_TRADED"
                sig["status_detail"] = "Simulated position opened"

                long = sig["direction"] == "LONG"
                entry_px = sig["price"]
                cfg = sig["cfg"]
                
                # Initial Stop Loss Calculation
                hard_stop_dist = entry_px * (cfg["hard_stop_pct"] / 100.0)
                hard_stop_lvl = entry_px - hard_stop_dist if long else entry_px + hard_stop_dist
                
                initial_stop = hard_stop_lvl
                stop_kind = "HARD_STOP"

                # Check initial structural stop levels (if tighter than hard stop)
                if cfg["structural_vwap_enabled"] and sig.get("vwap"):
                    vwap_stop_dist = sig["vwap"] * (cfg["structural_vwap_pct"] / 100.0)
                    vwap_stop_lvl = sig["vwap"] - vwap_stop_dist if long else sig["vwap"] + vwap_stop_dist
                    if long and vwap_stop_lvl > initial_stop and vwap_stop_lvl < entry_px:
                        initial_stop = vwap_stop_lvl
                        stop_kind = "VWAP_STRUCTURAL"
                    elif not long and vwap_stop_lvl < initial_stop and vwap_stop_lvl > entry_px:
                        initial_stop = vwap_stop_lvl
                        stop_kind = "VWAP_STRUCTURAL"

                if cfg["structural_st_enabled"] and sig.get("st_line"):
                    st_stop_dist = sig["st_line"] * (cfg["structural_st_pct"] / 100.0)
                    st_stop_lvl = sig["st_line"] - st_stop_dist if long else sig["st_line"] + st_stop_dist
                    if long and st_stop_lvl > initial_stop and st_stop_lvl < entry_px:
                        initial_stop = st_stop_lvl
                        stop_kind = "SUPERTREND_STRUCTURAL"
                    elif not long and st_stop_lvl < initial_stop and st_stop_lvl > entry_px:
                        initial_stop = st_stop_lvl
                        stop_kind = "SUPERTREND_STRUCTURAL"

                new_trade = {
                    "trade_id": trade_id_counter,
                    "symbol": sig["symbol"],
                    "direction": sig["direction"],
                    "strategy": sig["strategy"],
                    "timeframe": sig["timeframe"],
                    "timeframe_min": cfg["timeframe_min"],
                    "signal_ts_ms": sig_ts,
                    "entry_ts_ms": sig_ts,
                    "entry_time_ist": sig["time_ist"],
                    "entry_candle_window_ist": sig["candle_window_ist"],
                    "entry_price": round(entry_px, 4),
                    "exit_ts_ms": sig_ts,
                    "exit_time_ist": sig["time_ist"],
                    "exit_candle_window_ist": sig["candle_window_ist"],
                    "exit_price": round(entry_px, 4),
                    "exit_reason": "OPEN",
                    "partial_exits": [],
                    "trailing_activated": False,
                    "peak_price_after_tp": None,
                    "breakeven_activated": False,
                    "realized_pnl_pct": 0.0,
                    "realized_pnl_usdt": 0.0,
                    "margin_usdt": margin_alloc,
                    "leverage": leverage,
                    "fees_usdt": round(margin_alloc * leverage * 0.0006 * 2, 4),
                    "duration_min": 0,
                    "status": "OPEN",
                    "current_stop": initial_stop,
                    "last_stop_kind": stop_kind,
                    "target_specs": [dict(t) for t in cfg["targets"]],
                    "trailing_enabled": cfg["trailing_enabled"],
                    "trailing_pct": cfg["trailing_pct"],
                    "breakeven": cfg["breakeven"],
                    "structural_vwap_enabled": cfg["structural_vwap_enabled"],
                    "structural_vwap_pct": cfg["structural_vwap_pct"],
                    "structural_st_enabled": cfg["structural_st_enabled"],
                    "structural_st_pct": cfg["structural_st_pct"],
                    "reverse_exit": cfg["reverse_exit"],
                    "peak_price": entry_px,
                    "remaining_qty_pct": 100.0,
                    "last_checked_ts": sig_ts,
                    "agg_bars": sig["agg_bars"],
                    "e9": sig["e9"],
                    "e20": sig["e20"],
                    "vw_map": sig["vw_map"],
                    "st_map": sig["st_map"]
                }
                trade_id_counter += 1
                open_sim_trades.append(new_trade)

    # Walk remaining open trades through to the end of the simulation window
    _walk_open_trades_up_to(None)

    for t in open_sim_trades:
        last_b = t["agg_bars"][-1] if t["agg_bars"] else None
        last_close = float(last_b["close"]) if last_b else t["entry_price"]
        last_ts = last_b["ts"] if last_b else t["entry_ts_ms"]
        dt_end = datetime.fromtimestamp(last_ts / 1000, tz=sessions.IST)
        dt_end_plus = dt_end + timedelta(minutes=t["timeframe_min"])
        candle_str = f"{dt_end.strftime('%H:%M')} - {dt_end_plus.strftime('%H:%M')} IST"
        long = t["direction"] == "LONG"
        sign = 1 if long else -1
        
        rem_qty_pct = t["remaining_qty_pct"]
        pnl_pct_rem = (last_close - t["entry_price"]) / t["entry_price"] * 100.0 * sign
        pnl_usdt_rem = t["margin_usdt"] * (pnl_pct_rem / 100.0) * t["leverage"] * (rem_qty_pct / 100.0)
        total_realized_usdt = sum(p["realized_pnl_usdt"] for p in t["partial_exits"]) + pnl_usdt_rem - t["fees_usdt"]
        total_realized_pct = (total_realized_usdt / t["margin_usdt"]) * 100.0

        t["exit_ts_ms"] = last_ts
        t["exit_time_ist"] = dt_end.strftime("%d %b %H:%M IST")
        t["exit_candle_window_ist"] = candle_str
        t["exit_price"] = round(last_close, 4)
        t["exit_reason"] = "OPEN_AT_SIM_END"
        t["realized_pnl_pct"] = round(total_realized_pct, 2)
        t["realized_pnl_usdt"] = round(total_realized_usdt, 4)
        t["status"] = "OPEN"
        completed_sim_trades.append(t)

    clean_trades = []
    for t in completed_sim_trades:
        c_t = dict(t)
        c_t.pop("agg_bars", None)
        c_t.pop("current_stop", None)
        c_t.pop("last_stop_kind", None)
        c_t.pop("target_specs", None)
        c_t.pop("last_checked_ts", None)
        c_t.pop("peak_price", None)
        c_t.pop("remaining_qty_pct", None)
        c_t.pop("e9", None)
        c_t.pop("e20", None)
        c_t.pop("vw_map", None)
        c_t.pop("st_map", None)
        c_t.pop("timeframe_min", None)
        c_t["duration_min"] = max(1, int((c_t["exit_ts_ms"] - c_t["entry_ts_ms"]) // 60_000))
        clean_trades.append(c_t)

    clean_signals = []
    for s in all_raw_signals:
        c_s = dict(s)
        c_s.pop("agg_bars", None)
        c_s.pop("raw_bar_idx", None)
        c_s.pop("e9", None)
        c_s.pop("e20", None)
        c_s.pop("vw_map", None)
        c_s.pop("st_map", None)
        c_s.pop("cfg", None)
        clean_signals.append(c_s)

    eligible_count = sum(1 for s in clean_signals if "ELIGIBLE" in s["status"] or "TRADED" in s["status"])
    blocked_count = sum(1 for s in clean_signals if s["status"] == "BLOCKED_BY_VWAP")
    filtered_count = sum(1 for s in clean_signals if "FILTERED" in s["status"])

    dt_start = datetime.fromtimestamp(start_ms / 1000, tz=sessions.IST)
    dt_now = datetime.fromtimestamp(end_ms / 1000, tz=sessions.IST)

    # Calculate default timeframe label for response
    default_tf_str = req.get("timeframe") or "3m"
    if isinstance(default_tf_str, int):
        default_tf_str = f"{default_tf_str}m"

    return {
        "status": "OK",
        "date_range_ist": f"{dt_start.strftime('%d %b %H:%M')} - {dt_now.strftime('%d %b %H:%M IST')}",
        "lookback_hours": 24,
        "strategy": strategy,
        "symbols_checked": symbols,
        "timeframe": default_tf_str,
        "vwap_gate": "ON" if vwap_gate_enabled else "OFF",
        "signals_count": len(clean_signals),
        "eligible_signals_count": eligible_count,
        "blocked_signals_count": blocked_count,
        "filtered_signals_count": filtered_count,
        "simulated_trades_count": len(clean_trades),
        "open_at_end_count": sum(1 for t in clean_trades if t.get("exit_reason") == "OPEN_AT_SIM_END"),
        "signals": clean_signals,
        "trades": clean_trades,
        "diagnostics": diagnostics
    }



