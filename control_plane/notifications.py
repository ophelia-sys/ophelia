"""
Ophelia Authoritative Notification Subsystem
Deterministic, event-driven, idempotent notification manager.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional
from . import db


def _dispatch(
    user_id: int,
    event_type: str,
    dedup_key: str,
    severity: str,
    title: str,
    message: str,
    mode: str,
    category: str,
    payload: Optional[Dict[str, Any]] = None
) -> Optional[dict]:
    """Internal helper to filter by user settings, persist with dedup, and emit via WS outbox."""
    if not user_id or user_id < 1:
        return None
    settings = db.get_notification_settings(user_id)
    
    # Master switch check (unless CRITICAL which always bypasses to alert operator of safety issues)
    if not settings.get("enabled", True) and severity != "CRITICAL":
        return None

    # Category checks
    if category == "TRADES":
        if event_type in ("TP_HIT", "SL_HIT", "PARTIAL_CLOSE", "TRAILING_STOP_UPDATE"):
            if not settings.get("tp_sl_enabled", True) and severity != "CRITICAL":
                return None
        elif not settings.get("trades_enabled", True) and severity != "CRITICAL":
            return None
    elif category == "RISK" and not settings.get("risk_enabled", True) and severity != "CRITICAL":
        return None
    elif category == "AUTOMATIONS" and not settings.get("automations_enabled", True) and severity != "CRITICAL":
        return None
    elif category == "SYSTEM":
        if event_type == "EQUITY_REPORT_4H":
            if not settings.get("equity_4h_enabled", True) and severity != "CRITICAL":
                return None
        elif not settings.get("system_enabled", True) and severity != "CRITICAL":
            return None

    # Idempotent database insertion
    notif, created = db.create_notification(
        user_id=user_id,
        event_type=event_type,
        dedup_key=dedup_key,
        severity=severity,
        title=title,
        message=message,
        mode=mode,
        category=category,
        payload=payload or {}
    )

    if created and notif:
        # Emit over WebSocket for real-time mobile reception
        db.emit_ws_event("NOTIFICATION", notif, user_id)
        return notif

    return None


# 1. TRADE OPENED
def notify_trade_opened(pos: dict, user_id: int) -> Optional[dict]:
    pid = pos.get("id") or pos.get("position_id")
    symbol = pos.get("symbol", "UNKNOWN")
    direction = pos.get("direction", "LONG")
    entry = pos.get("entry", 0.0)
    margin = pos.get("margin_usdt") or pos.get("margin") or 0.0
    lev = pos.get("leverage", 15)
    mode = pos.get("mode") or db.get_mode()
    
    dedup = f"TRADE_OPENED:{pid}"
    title = f"OPHELIA — TRADE OPENED ({mode})"
    msg = (
        f"{symbol} {direction}\n"
        f"Entry: ${entry:,.4f} | Margin: ${margin:.2f} USDT ({lev}x)\n"
        f"Mode: {mode}"
    )
    return _dispatch(user_id, "TRADE_OPENED", dedup, "INFO", title, msg, mode, "TRADES", pos)


# 2. TRADE CLOSED
def notify_trade_closed(
    pos: dict,
    realized_pnl: float,
    pnl_pct: float,
    reason: str = "TAKE_PROFIT",
    duration_str: str = "",
    user_id: int = 0
) -> Optional[dict]:
    pid = pos.get("id") or pos.get("position_id")
    now_ms = int(time.time() * 1000)
    symbol = pos.get("symbol", "UNKNOWN")
    direction = pos.get("direction", "LONG")
    exit_px = pos.get("exit_price", 0.0)
    mode = pos.get("mode") or db.get_mode()
    
    sign = "+" if realized_pnl >= 0 else ""
    sign_pct = "+" if pnl_pct >= 0 else ""
    dedup = f"TRADE_CLOSED:{pid}:{now_ms}"
    title = f"OPHELIA — TRADE CLOSED ({mode})"
    dur_line = f"\nDuration: {duration_str}" if duration_str else ""
    msg = (
        f"{symbol} {direction}\n"
        f"Exit: ${exit_px:,.4f}\n"
        f"Realized PnL: {sign}${realized_pnl:.2f} USDT ({sign_pct}{pnl_pct:.2f}%)\n"
        f"Reason: {reason}{dur_line}\n"
        f"Mode: {mode}"
    )
    severity = "INFO" if realized_pnl >= 0 else "WARNING"
    payload = {**pos, "realized_pnl": realized_pnl, "pnl_pct": pnl_pct, "reason": reason}
    return _dispatch(user_id, "TRADE_CLOSED", dedup, severity, title, msg, mode, "TRADES", payload)


# 3. PARTIAL CLOSE
def notify_partial_close(
    pos: dict,
    stage_pct: float,
    realized_pnl: float,
    pnl_pct: float,
    remaining_qty: float,
    user_id: int = 0
) -> Optional[dict]:
    pid = pos.get("id") or pos.get("position_id")
    now_ms = int(time.time() * 1000)
    symbol = pos.get("symbol", "UNKNOWN")
    direction = pos.get("direction", "LONG")
    mode = pos.get("mode") or db.get_mode()
    
    sign = "+" if realized_pnl >= 0 else ""
    sign_pct = "+" if pnl_pct >= 0 else ""
    dedup = f"PARTIAL_CLOSE:{pid}:{stage_pct}:{now_ms}"
    title = f"OPHELIA — {stage_pct:.0f}% POSITION CLOSED"
    msg = (
        f"{symbol} {direction}\n"
        f"Realized PnL: {sign}${realized_pnl:.2f} USDT ({sign_pct}{pnl_pct:.2f}%)\n"
        f"Remaining Qty: {remaining_qty}\n"
        f"Mode: {mode}"
    )
    payload = {**pos, "stage_pct": stage_pct, "realized_pnl": realized_pnl, "remaining_qty": remaining_qty}
    return _dispatch(user_id, "PARTIAL_CLOSE", dedup, "INFO", title, msg, mode, "TRADES", payload)


# 4. TAKE PROFIT HIT
def notify_tp_hit(
    pos: dict,
    target_index: int,
    gain_pct: float,
    qty_pct: float,
    realized_pnl: float,
    user_id: int = 0
) -> Optional[dict]:
    pid = pos.get("id") or pos.get("position_id")
    now_ms = int(time.time() * 1000)
    symbol = pos.get("symbol", "UNKNOWN")
    direction = pos.get("direction", "LONG")
    mode = pos.get("mode") or db.get_mode()
    
    sign = "+" if realized_pnl >= 0 else ""
    dedup = f"TP_HIT:{pid}:{target_index}:{now_ms}"
    title = f"OPHELIA — TP{target_index} HIT"
    msg = (
        f"{symbol} {direction}\n"
        f"TP{target_index}: +{gain_pct:.2f}%\n"
        f"Closed Qty: {qty_pct:.1f}%\n"
        f"Realized PnL: {sign}${realized_pnl:.2f} USDT\n"
        f"Mode: {mode}"
    )
    payload = {**pos, "target_index": target_index, "gain_pct": gain_pct, "qty_pct": qty_pct, "realized_pnl": realized_pnl}
    return _dispatch(user_id, "TP_HIT", dedup, "INFO", title, msg, mode, "TRADES", payload)


# 5. STOP LOSS HIT
def notify_sl_hit(
    pos: dict,
    loss_usdt: float,
    loss_pct: float,
    reason: str = "HARD_STOP",
    user_id: int = 0
) -> Optional[dict]:
    pid = pos.get("id") or pos.get("position_id")
    now_ms = int(time.time() * 1000)
    symbol = pos.get("symbol", "UNKNOWN")
    direction = pos.get("direction", "LONG")
    mode = pos.get("mode") or db.get_mode()
    
    dedup = f"SL_HIT:{pid}:{reason}:{now_ms}"
    title = f"OPHELIA — STOP LOSS HIT"
    msg = (
        f"{symbol} {direction}\n"
        f"Loss: -${abs(loss_usdt):.2f} USDT (-{abs(loss_pct):.2f}%)\n"
        f"Reason: {reason}\n"
        f"Mode: {mode}"
    )
    payload = {**pos, "loss_usdt": loss_usdt, "loss_pct": loss_pct, "reason": reason}
    return _dispatch(user_id, "SL_HIT", dedup, "WARNING", title, msg, mode, "TRADES", payload)


# 6. TRAILING STOP / BREAKEVEN UPDATE
def notify_trailing_stop(
    pos: dict,
    action: str,
    new_stop: float,
    user_id: int = 0
) -> Optional[dict]:
    pid = pos.get("id") or pos.get("position_id")
    now_ms = int(time.time() * 1000)
    symbol = pos.get("symbol", "UNKNOWN")
    direction = pos.get("direction", "LONG")
    mode = pos.get("mode") or db.get_mode()
    
    dedup = f"TRAILING:{pid}:{action}:{now_ms}"
    title = f"OPHELIA — {action}"
    msg = (
        f"{symbol} {direction}\n"
        f"Action: {action}\n"
        f"New Protected Stop: ${new_stop:,.4f}\n"
        f"Mode: {mode}"
    )
    payload = {**pos, "action": action, "new_stop": new_stop}
    return _dispatch(user_id, "TRAILING_STOP_UPDATE", dedup, "INFO", title, msg, mode, "TRADES", payload)


# 7. EXTERNAL POSITION DETECTED
def notify_external_position(pos: dict, user_id: int) -> Optional[dict]:
    symbol = pos.get("symbol", "UNKNOWN")
    direction = pos.get("direction") or pos.get("side") or "LONG"
    entry = pos.get("entry", 0.0)
    mark = pos.get("current_price") or pos.get("mark") or entry
    upnl = pos.get("unrealized_pnl", 0.0)
    lev = pos.get("leverage", 1.0)
    liq = pos.get("liquidation_price")
    
    # Dedup per symbol per hour to prevent spamming
    hour_bucket = int(time.time() // 3600)
    dedup = f"EXT_POS:{symbol}:{direction}:{hour_bucket}"
    title = "OPHELIA — EXTERNAL POSITION DETECTED"
    sign = "+" if upnl >= 0 else ""
    liq_str = f"\nLiquidation Price: ${liq:,.4f}" if liq else ""
    msg = (
        f"{symbol} {direction}\n"
        f"Entry: ${entry:,.4f} | Mark: ${mark:,.4f}\n"
        f"Unrealized PnL: {sign}${upnl:.2f} ({lev}x){liq_str}\n"
        f"Status: BINGX MANUAL / EXTERNAL POSITION"
    )
    return _dispatch(user_id, "EXTERNAL_POSITION_DETECTED", dedup, "WARNING", title, msg, "LIVE", "RISK", pos)


# 8. LIQUIDATION RISK
def notify_liquidation_risk(
    pos: dict,
    mark_price: float,
    liq_price: float,
    distance_pct: float,
    user_id: int = 0
) -> Optional[dict]:
    symbol = pos.get("symbol", "UNKNOWN")
    direction = pos.get("direction") or pos.get("side") or "LONG"
    # Dedup per 30 minutes
    half_hour_bucket = int(time.time() // 1800)
    dedup = f"LIQ_RISK:{symbol}:{direction}:{half_hour_bucket}"
    title = "OPHELIA — LIQUIDATION RISK ALERT"
    msg = (
        f"{symbol} {direction}\n"
        f"Mark Price: ${mark_price:,.4f}\n"
        f"Liquidation Price: ${liq_price:,.4f}\n"
        f"Distance to Liquidation: {distance_pct:.2f}%\n"
        f"ACTION REQUIRED: Review position margin immediately."
    )
    payload = {**pos, "mark_price": mark_price, "liq_price": liq_price, "distance_pct": distance_pct}
    return _dispatch(user_id, "LIQUIDATION_RISK", dedup, "CRITICAL", title, msg, "LIVE", "RISK", payload)


# 9. EMERGENCY ACTION
def notify_emergency_action(action: str, details: str, mode: str = "LIVE", user_id: int = 0) -> Optional[dict]:
    now_ms = int(time.time() * 1000)
    dedup = f"EMERGENCY:{action}:{now_ms}"
    title = f"OPHELIA — {action.upper()}"
    msg = f"{details}\nExecution Mode: {mode}"
    return _dispatch(user_id, "EMERGENCY_ACTION", dedup, "CRITICAL", title, msg, mode, "SYSTEM", {"action": action, "details": details})


# 10. AUTOMATION EVENT
def notify_automation_event(
    event_type: str,
    auto_id: int,
    strategy: str,
    mode: str,
    scope: str = "ALL_WATCHLIST",
    margin_str: str = "50%",
    leverage: int = 15,
    user_id: int = 0
) -> Optional[dict]:
    now_ms = int(time.time() * 1000)
    dedup = f"AUTO_EVENT:{event_type}:{auto_id}:{now_ms}"
    title = f"OPHELIA — AUTOMATION {event_type.upper()}"
    msg = (
        f"Strategy: {strategy} (#{auto_id})\n"
        f"Mode: {mode}\n"
        f"Scope: {scope}\n"
        f"Allocation: {margin_str} ({leverage}x Leverage)"
    )
    payload = {"auto_id": auto_id, "strategy": strategy, "mode": mode, "scope": scope, "margin": margin_str, "leverage": leverage}
    return _dispatch(user_id, "AUTOMATION_EVENT", dedup, "INFO", title, msg, mode, "AUTOMATIONS", payload)


# 11. SYSTEM CONNECTIVITY
def notify_system_connectivity(issue: str, severity: str = "WARNING", details: str = "", user_id: int = 0) -> Optional[dict]:
    hour_bucket = int(time.time() // 3600)
    dedup = f"SYS_CONN:{issue}:{hour_bucket}"
    title = "OPHELIA — SYSTEM / EXCHANGE CONNECTIVITY"
    msg = f"{issue}\n{details}" if details else issue
    return _dispatch(user_id, "SYSTEM_CONNECTIVITY", dedup, severity, title, msg, db.get_mode(), "SYSTEM", {"issue": issue, "details": details})


# 12. RISK BARRIER REJECTED
def notify_risk_barrier_rejected(
    reason: str,
    symbol: str = "N/A",
    direction: str = "N/A",
    active_count: int = 2,
    max_count: int = 2,
    user_id: int = 0
) -> Optional[dict]:
    now_ms = int(time.time() * 1000)
    dedup = f"RISK_REJECT:{reason}:{symbol}:{now_ms}"
    title = "OPHELIA — TRADE EXECUTION REJECTED"
    msg = (
        f"Target: {symbol} {direction}\n"
        f"Reason: {reason}\n"
        f"Active Positions: {active_count} / {max_count} (Hard Cap)\n"
        f"Status: Safe Fail-Closed (No order submitted)."
    )
    payload = {"reason": reason, "symbol": symbol, "direction": direction, "active_count": active_count, "max_count": max_count}
    return _dispatch(user_id, "RISK_BARRIER_REJECTED", dedup, "WARNING", title, msg, db.get_mode(), "RISK", payload)


# 13. FOUR-HOUR ACCOUNT EQUITY REPORT
def notify_4h_equity_report(
    current_equity: float,
    prev_equity: float,
    realized_pnl_4h: float = 0.0,
    unrealized_pnl: float = 0.0,
    open_positions: int = 0,
    mode: str = "LIVE",
    user_id: int = 0
) -> Optional[dict]:
    # 4-hour window identifier: e.g. timestamp // 14400 (4h in seconds)
    window_id = int(time.time() // (4 * 3600))
    dedup = f"EQUITY_4H:{user_id}:{window_id}"
    
    delta_usdt = current_equity - prev_equity
    delta_pct = (delta_usdt / prev_equity * 100.0) if prev_equity > 0 else 0.0
    
    sign_d = "+" if delta_usdt >= 0 else ""
    sign_dp = "+" if delta_pct >= 0 else ""
    sign_r = "+" if realized_pnl_4h >= 0 else ""
    sign_u = "+" if unrealized_pnl >= 0 else ""
    
    title = "OPHELIA — 4H ACCOUNT REPORT"
    msg = (
        f"Equity: ${current_equity:,.2f} USDT\n"
        f"4H Change: {sign_d}${delta_usdt:,.2f} USDT ({sign_dp}{delta_pct:.2f}%)\n"
        f"Realized PnL: {sign_r}${realized_pnl_4h:,.2f} | Unrealized: {sign_u}${unrealized_pnl:,.2f}\n"
        f"Open Positions: {open_positions}\n"
        f"Mode: {mode}"
    )
    payload = {
        "current_equity": current_equity,
        "prev_equity": prev_equity,
        "delta_usdt": delta_usdt,
        "delta_pct": delta_pct,
        "realized_pnl_4h": realized_pnl_4h,
        "unrealized_pnl": unrealized_pnl,
        "open_positions": open_positions,
        "mode": mode
    }
    return _dispatch(user_id, "EQUITY_REPORT_4H", dedup, "INFO", title, msg, mode, "SYSTEM", payload)


# 14. EXPLICIT ALIASES & HELPERS
def notify_breakeven_activated(pos: dict, new_stop: float, user_id: int = 0) -> Optional[dict]:
    return notify_trailing_stop(pos, "BREAKEVEN ACTIVATED", new_stop, user_id=user_id)


def notify_trailing_stop_update(pos: dict, new_stop: float, user_id: int = 0) -> Optional[dict]:
    return notify_trailing_stop(pos, "TRAILING STOP UPDATED", new_stop, user_id=user_id)


def notify_automation_deployed(auto_dict: dict, user_id: int = 0) -> Optional[dict]:
    aid = auto_dict.get("id", 0)
    strat = auto_dict.get("strategy", "UNKNOWN")
    mode = auto_dict.get("mode", db.get_mode())
    scope = auto_dict.get("symbol", "ALL_WATCHLIST")
    margin_str = f"{auto_dict.get('margin_usage_pct', 50.0)}%"
    lev = int(float(auto_dict.get("leverage", 15)))
    return notify_automation_event("DEPLOYED", aid, strat, mode, scope, margin_str, lev, user_id)


def notify_automation_rejected(auto_dict: dict, reason: str, user_id: int = 0) -> Optional[dict]:
    now_ms = int(time.time() * 1000)
    aid = auto_dict.get("id", 0)
    dedup = f"AUTO_REJECT:{aid}:{now_ms}"
    title = "OPHELIA — AUTOMATION DEPLOYMENT REJECTED"
    msg = f"Automation #{aid} rejected: {reason}"
    return _dispatch(user_id, "AUTOMATION_REJECTED", dedup, "WARNING", title, msg, db.get_mode(), "AUTOMATIONS", {"auto": auto_dict, "reason": reason})


def notify_automation_paused(auto_id: int = 0, user_id: int = 0) -> Optional[dict]:
    now_ms = int(time.time() * 1000)
    dedup = f"AUTO_PAUSED:{auto_id}:{now_ms}"
    title = "OPHELIA — AUTOMATIONS PAUSED"
    msg = "All automated signal evaluations paused. Existing positions remain protected."
    return _dispatch(user_id, "AUTOMATION_PAUSED", dedup, "INFO", title, msg, db.get_mode(), "AUTOMATIONS", {"auto_id": auto_id})


def notify_automation_resumed(auto_id: int = 0, user_id: int = 0) -> Optional[dict]:
    now_ms = int(time.time() * 1000)
    dedup = f"AUTO_RESUMED:{auto_id}:{now_ms}"
    title = "OPHELIA — AUTOMATIONS RESUMED"
    msg = "Automated signal evaluation and trade execution resumed."
    return _dispatch(user_id, "AUTOMATION_RESUMED", dedup, "INFO", title, msg, db.get_mode(), "AUTOMATIONS", {"auto_id": auto_id})


def notify_bingx_auth_failure(err_msg: str, user_id: int = 0) -> Optional[dict]:
    now_ms = int(time.time() * 1000)
    dedup = f"BINGX_AUTH_ERR:{now_ms // 300000}" # 5m dedup
    title = "OPHELIA — BINGX AUTHENTICATION FAILURE"
    msg = f"Critical exchange authentication failure: {err_msg}\nLive execution is halted."
    return _dispatch(user_id, "BINGX_AUTHENTICATION_FAILURE", dedup, "CRITICAL", title, msg, "LIVE", "SYSTEM", {"error": err_msg})


def notify_market_data_failure(symbol: str, details: str, user_id: int = 0) -> Optional[dict]:
    now_ms = int(time.time() * 1000)
    dedup = f"MKT_DATA_ERR:{symbol}:{now_ms // 300000}"
    title = "OPHELIA — MARKET DATA INGESTION FAILURE"
    msg = f"Candle data feed stale or missing for {symbol}: {details}"
    return _dispatch(user_id, "MARKET_DATA_FAILURE", dedup, "WARNING", title, msg, db.get_mode(), "SYSTEM", {"symbol": symbol, "details": details})


def notify_preflight_failure(reasons: list[str], user_id: int = 0) -> Optional[dict]:
    now_ms = int(time.time() * 1000)
    dedup = f"PREFLIGHT_ERR:{now_ms // 300000}"
    title = "OPHELIA — LIVE PRE-FLIGHT CHECK FAILED"
    msg = "Live trading pre-flight safety checks failed:\n• " + "\n• ".join(reasons)
    return _dispatch(user_id, "PRE-FLIGHT_FAILURE", dedup, "WARNING", title, msg, "LIVE", "RISK", {"reasons": reasons})

