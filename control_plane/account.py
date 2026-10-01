"""Normalized account-position service - the SINGLE source of truth for
/position and /bingx.

Guarantees:
  - both commands read the same normalized exchange state (short TTL cache)
  - Ophelia-tracked PnL comes ONLY from Ophelia-created positions/trades
  - daily PnL boundary is the UTC day, derived from closed-trade timestamps
    (restart-safe by construction; no in-memory reset state)
  - local LIVE positions that disagree with the exchange are flagged
    RECONCILIATION_REQUIRED instead of being silently trusted
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone, timedelta

from . import db, core, symbols

_CACHE: dict[int, dict] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL_S = 4.0


def _utc_day_bounds() -> tuple[int, int, str]:
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_ms = int(start.timestamp() * 1000)
    return start_ms, start_ms + 86_400_000, start.strftime("%Y-%m-%d")


def invalidate_user_cache(user_id: int) -> None:
    """Evict cached account and positions snapshot for a specific user."""
    with _CACHE_LOCK:
        _CACHE.pop(user_id, None)


def exchange_snapshot(user_id: int | None = None, force: bool = False, is_admin_caller: bool = False) -> tuple[dict, list[dict]]:
    """(account, positions) from BingX with per-user TTL cache.
    
    CRITICAL ACCOUNT ISOLATION CONTRACT:
    - User A receives ONLY User A BingX state.
    - User B receives ONLY User B BingX state.
    - Server operational Admin account requires is_admin_caller=True AND user_id=1.
    - Standard users (and unauthorized user_id=1 requests) NEVER fall back to server operational credentials.
    - Unconnected users receive explicit connection_state with connected=False.
    """
    if user_id is None or user_id <= 0:
        empty_acc = {
            "asset": "USDT",
            "balance": 0.0,
            "available_margin": 0.0,
            "used_margin": 0.0,
            "equity": 0.0,
            "unrealized_pnl": 0.0,
            "user_id": 0,
            "connected": False,
            "connection_state": "NOT_CONFIGURED",
            "connection_status": "NOT_CONFIGURED",
            "account_type": "USER_BINGX_ACCOUNT"
        }
        return empty_acc, []

    from . import bingx_client, credential_vault
    effective_uid = user_id
    now = time.time()
    
    with _CACHE_LOCK:
        cached = _CACHE.get(effective_uid)
        if not force and cached is not None and now - cached.get("ts", 0.0) < _CACHE_TTL_S:
            return cached["account"], cached["positions"]

    # Standard & Admin users: ONLY use their isolated vault credentials, NEVER fall back to env!
    c = credential_vault.get_user_bingx_client(effective_uid, allow_trade=False)

    if not c:
        conn_state = credential_vault.get_user_connection_state(effective_uid)
        empty_acc = {
            "asset": "USDT",
            "balance": 0.0,
            "available_margin": 0.0,
            "used_margin": 0.0,
            "equity": 0.0,
            "unrealized_pnl": 0.0,
            "user_id": effective_uid,
            "connected": False,
            "connection_state": conn_state,
            "connection_status": conn_state,
            "account_type": "USER_BINGX_ACCOUNT"
        }
        with _CACHE_LOCK:
            _CACHE[effective_uid] = {"ts": now, "account": empty_acc, "positions": []}
        return empty_acc, []

    try:
        b_list = c.balance()
        b = {}
        if isinstance(b_list, list) and b_list:
            b = next((item for item in b_list if isinstance(item, dict) and item.get("asset") in ("USDT", "usdt")), b_list[0] if isinstance(b_list[0], dict) else {})
        elif isinstance(b_list, dict):
            inner_b = b_list.get("balance")
            if isinstance(inner_b, list) and inner_b:
                b = next((item for item in inner_b if isinstance(item, dict) and item.get("asset") in ("USDT", "usdt")), inner_b[0] if isinstance(inner_b[0], dict) else {})
            elif isinstance(inner_b, dict):
                b = inner_b
            else:
                b = b_list
        positions = c.positions()

        def f(*keys, default=0.0):
            for k in keys:
                v = b.get(k)
                if v not in (None, ""):
                    try:
                        return float(v)
                    except (ValueError, TypeError):
                        continue
            return default

        bal = f("balance", "walletBalance", "availableMargin")
        avail = f("availableMargin", "availableBalance", "balance")
        upnl = f("unrealizedProfit", "unrealizedPnL", "unrealizedPnl")
        eq = f("equity", "marginBalance")
        if eq == 0.0 and bal > 0.0:
            eq = bal + upnl

        account = {
            "asset": b.get("asset") or b.get("currency") or "USDT",
            "balance": bal,
            "available_margin": avail,
            "used_margin": f("usedMargin", "positionMargin"),
            "equity": eq,
            "unrealized_pnl": upnl,
            "user_id": effective_uid,
            "connected": True,
            "connection_state": "CONNECTED",
            "connection_status": "CONNECTED",
            "account_type": "SERVER_ADMIN_BINGX_ACCOUNT" if effective_uid == 1 else "USER_BINGX_ACCOUNT"
        }
        normalized = []
        for p in positions:
            qty = abs(float(p.get("positionAmt") or p.get("qty") or 0))
            if qty == 0:
                continue
            entry = float(p.get("avgPrice") or p.get("entry") or 0)
            mark = float(p.get("markPrice") or p.get("mark") or 0)
            side = p.get("positionSide") or p.get("side") or "LONG"
            if side not in ("LONG", "SHORT"):
                side = "LONG" if float(p.get("positionAmt") or p.get("qty") or 0) > 0 else "SHORT"
            p_upnl = float(p.get("unrealizedProfit") or p.get("unrealized_pnl") or 0)
            normalized.append({
                "symbol": p.get("symbol"),
                "side": side,
                "qty": qty,
                "entry": entry,
                "mark": mark,
                "leverage": float(p.get("leverage") or 1),
                "unrealized_pnl": p_upnl,
                "unrealized_pnl_pct": (round(p_upnl / (entry * qty) * 100, 3)
                                       if entry and qty else None),
                "move_from_entry_pct": (round((mark / entry - 1) * 100, 3)
                                        if entry and mark else None),
                "notional": round(mark * qty, 2) if mark else round(entry * qty, 2),
                "liquidation_price": (float(p["liquidationPrice"])
                                      if p.get("liquidationPrice") else None),
                "position_id": p.get("positionId"),
                "user_id": effective_uid,
            })
        with _CACHE_LOCK:
            _CACHE[effective_uid] = {"ts": now, "account": account, "positions": normalized}
        return account, normalized
    except Exception as e:
        empty_acc = {
            "asset": "USDT",
            "balance": 0.0,
            "available_margin": 0.0,
            "used_margin": 0.0,
            "equity": 0.0,
            "unrealized_pnl": 0.0,
            "user_id": effective_uid,
            "connected": False,
            "error": str(e)[:120]
        }
        with _CACHE_LOCK:
            _CACHE[effective_uid] = {"ts": now, "account": empty_acc, "positions": []}
        return empty_acc, []


def ophelia_daily_pnl(user_id: int) -> dict:
    """Ophelia-tracked PnL for the current UTC accounting day.

    Realized: only Ophelia-created positions and shadow trades CLOSED today.
    Closed trades from earlier today remain counted even if nothing is open.
    """
    if not user_id or user_id < 1:
        raise ValueError("Valid user_id required for ophelia_daily_pnl")
    day_start, _day_end, day_label = _utc_day_bounds()
    realized = 0.0
    realized_items = []
    for p in db.closed_positions_since(day_start, user_id=user_id):
        realized += float(p.get("realized_pnl") or 0)
        realized_items.append({"kind": "position", "id": p["id"],
                               "symbol": p["symbol"], "pnl": p["realized_pnl"]})
    c = db._auto_conn()
    with db._lock:
        rows = c.execute(
            "SELECT id, pnl_usdt FROM shadow_trades WHERE status IN "
            "('STOPPED_SHADOW','TARGET_SHADOW','CLOSED_MANUAL') "
            "AND ts_close_ms>=? AND user_id=?", (day_start, user_id)).fetchall()
    for tid, pnl in rows:
        realized += float(pnl or 0)
        realized_items.append({"kind": "shadow", "id": tid, "pnl": pnl})
    # unrealized: Ophelia-managed open positions only (marked to last price)
    unrealized = 0.0
    open_n = 0
    for p in db.open_positions(user_id=user_id):
        rows1m = db.query_candles(p["symbol"],
                                  int(time.time() * 1000) - 120_000,
                                  int(time.time() * 1000) + 1)
        px = rows1m[-1]["close"] if rows1m else p["entry"]
        sign = 1 if p["direction"] == "LONG" else -1
        unrealized += (px - p["entry"]) * p["qty"] * sign
        open_n += 1
    return {"day_utc": day_label, "resets": "00:00 UTC (05:30 IST)",
            "realized": round(realized, 4), "unrealized": round(unrealized, 4),
            "total": round(realized + unrealized, 4),
            "realized_items": realized_items, "open_ophelia_positions": open_n}


def reconcile(heal: bool = False, user_id: int = 0) -> dict:
    """Compare exchange positions against Ophelia-tracked LIVE positions.

    Returns flags; when heal=True, safely reconciles stale local records that
    do not exist on BingX into DESYNC_CLOSED state with full audit trail.
    """
    if not user_id or user_id < 1:
        return {"ok": False, "error": "Valid user_id required for reconciliation"}
    try:
        _account, ex = exchange_snapshot(user_id=user_id)
    except Exception as e:                                        # noqa: BLE001
        return {"ok": False, "error": str(e)[:140]}
    ex_by_sym: dict[str, list[dict]] = {}
    for p in ex:
        ex_by_sym.setdefault(p["symbol"], []).append(p)
    local = db.open_positions(mode="LIVE", user_id=user_id)
    issues = []
    now_ms = int(time.time() * 1000)
    for p in local:
        sym = symbols.to_bingx_symbol(p["symbol"]) if p.get("symbol") else ""
        matches = ex_by_sym.get(sym, [])
        side = p["direction"]
        hit = [x for x in matches if x["side"] == side]
        if not hit:
            age_sec = (now_ms - (p.get("opened_ms") or now_ms)) / 1000.0
            issues.append({"kind": "MISSING_ON_EXCHANGE", "symbol": sym,
                           "position_id": p["id"], "local_qty": p["qty"],
                           "age_sec": round(age_sec, 1),
                           "client_order_id": p.get("client_order_id")})
            if heal and age_sec > 15.0:
                detail = p.get("detail") or {}
                if isinstance(detail, str):
                    try:
                        detail = json.loads(detail)
                    except Exception:
                        detail = {}
                detail["closed_reason"] = "RECONCILED_MISSING_ON_EXCHANGE"
                db.update_position(p["id"], status="DESYNC_CLOSED",
                                   closed_ms=now_ms, exit_price=p["entry"],
                                   realized_pnl=0.0,
                                   detail_json=json.dumps(detail))
                db.audit("account", "RECONCILED_MISSING_POSITION",
                         {"position_id": p["id"], "symbol": sym,
                          "client_order_id": p.get("client_order_id")},
                         user_id=user_id)
        else:
            exq = hit[0]["qty"]
            if abs(exq - p["qty"]) > max(1e-9, exq * 0.001):
                issues.append({"kind": "QTY_MISMATCH", "symbol": sym,
                               "position_id": p["id"],
                               "local_qty": p["qty"], "exchange_qty": exq})
    local_syms = {symbols.to_bingx_symbol(p["symbol"]) for p in local if p.get("symbol")}
    for sym, plist in ex_by_sym.items():
        if sym not in local_syms:
            issues.append({"kind": "UNTRACKED_EXCHANGE_POSITION",
                           "symbol": sym, "side": plist[0]["side"],
                           "qty": plist[0]["qty"],
                           "note": "not created/managed by Ophelia"})
    return {"ok": True, "issues": issues,
            "reconciliation_required": bool(issues)}


def account_view(user_id: int = 0) -> dict:
    """Everything /bingx needs (Ophelia-tracked accounting only)."""
    if not user_id or user_id < 1:
        return {"error": "Valid user_id required for account view"}
    account, positions = exchange_snapshot(user_id=user_id)
    pnl = ophelia_daily_pnl(user_id=user_id)
    exposure = round(sum(p["notional"] for p in positions), 2)
    return {"account": account, "positions": positions, "pnl": pnl,
            "open_exposure": exposure}


def take_snapshot(user_id: int = 0) -> None:
    """Takes a snapshot of current equity and stores it in the DB."""
    if not user_id or user_id < 1:
        return
    try:
        account, _positions = exchange_snapshot(user_id=user_id)
        if account and account.get("equity", 0.0) > 0:
            db.insert_account_snapshot(
                user_id=user_id,
                equity=account.get("equity", 0.0),
                wallet_balance=account.get("balance", 0.0),
                margin_used=account.get("used_margin", 0.0),
                unrealized_pnl=account.get("unrealized_pnl", 0.0)
            )
    except Exception as e:
        print(f"Failed to take account snapshot: {e}")


def _pct_change(current: float, past: float | None) -> float:
    if not past or past <= 0:
        return 0.0
    return round((current / past - 1.0) * 100.0, 2)


def account_capacity(user_id: int = 0) -> dict:
    """Authoritative account margin capacity and active automation reservations."""
    if not user_id or user_id < 1:
        return {}
    try:
        acc, _ = exchange_snapshot(user_id=user_id)
    except Exception:
        acc = {}
        
    avail = float(acc.get("available_margin") or acc.get("balance") or 0.0)
    ex_used = float(acc.get("used_margin") or 0.0)
    
    # Ophelia open positions margin
    open_pos = db.open_positions(user_id=user_id)
    ophelia_used = sum(float(p.get("margin_usdt") or p.get("margin") or 0.0) for p in open_pos)
    
    # Active automations margin reservation
    active_autos = db.list_automations(status="ACTIVE", user_id=user_id)
    auto_reserved = 0.0
    for a in active_autos:
        fixed = a.get("margin_usdt") or a.get("params", {}).get("fixed_margin") or a.get("params", {}).get("margin_usdt")
        if fixed and float(fixed) > 0:
            auto_reserved += float(fixed)
        else:
            pct = float(a.get("margin_usage_pct") or a.get("params", {}).get("margin_pct") or 0.0)
            if pct > 0:
                auto_reserved += (pct / 100.0) * avail
                
    remaining = max(0.0, avail - auto_reserved)
    cap_metrics = db.get_capacity_metrics(user_id=user_id)
    return {
        "account_available": round(avail, 2),
        "exchange_used": round(ex_used, 2),
        "ophelia_used": round(ophelia_used, 2),
        "automation_reserved": round(auto_reserved, 2),
        "allocatable_remaining": round(remaining, 2),
        "configured_max_open_trades": cap_metrics["configured_max_open_trades"],
        "system_safety_max_open_trades": cap_metrics["system_safety_max_open_trades"],
        "open_positions_count": cap_metrics["open_positions_count"],
        "available_execution_slots": cap_metrics["available_execution_slots"],
        "active_automations_count": cap_metrics["active_automations_count"],
        "cap_state": cap_metrics["cap_state"],
        "cap_message": cap_metrics["cap_message"],
    }


def dashboard_view(user_id: int = 0, force: bool = False, is_admin_caller: bool = False) -> dict:
    """Aggregated view for the Android Home Dashboard."""
    if not user_id or user_id < 1:
        return {"error": "Valid user_id required for dashboard view"}
    from . import config
    from .provenance import DataProvenance
    connection_failed = False
    try:
        account, positions = exchange_snapshot(user_id=user_id, force=force, is_admin_caller=is_admin_caller)
    except Exception:
        account, positions = {}, []
        connection_failed = True
        
    if not account:
        account = {
            "equity": 0.0,
            "balance": 0.0,
            "available_margin": 0.0,
            "used_margin": 0.0,
            "unrealized_pnl": 0.0,
            "connected": False,
            "connection_state": "DISCONNECTED",
            "connection_status": "DISCONNECTED",
            "account_type": "USER_BINGX_ACCOUNT"
        }
        
    equity = account.get("equity", 0.0)
    is_conn = bool(account.get("connected", True))
    account_prov = DataProvenance.LIVE_BINGX.value if (is_conn and not connection_failed) else DataProvenance.NO_DATA.value
    
    now = datetime.now(timezone.utc)
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_today_ms = int(start_today.timestamp() * 1000)
    
    start_yesterday = start_today - timedelta(days=1)
    start_yesterday_ms = int(start_yesterday.timestamp() * 1000)
    
    start_week = start_today - timedelta(days=start_today.weekday())
    start_week_ms = int(start_week.timestamp() * 1000)
    
    start_month = start_today.replace(day=1)
    start_month_ms = int(start_month.timestamp() * 1000)
    
    eq_today = db.get_equity_at_or_before(start_today_ms, user_id)
    eq_yesterday = db.get_equity_at_or_before(start_yesterday_ms, user_id)
    eq_week = db.get_equity_at_or_before(start_week_ms, user_id)
    eq_month = db.get_equity_at_or_before(start_month_ms, user_id)
    
    perf = {
        "today_pct": _pct_change(equity, eq_today),
        "yesterday_pct": _pct_change(eq_today or equity, eq_yesterday) if eq_today is not None else 0.0,
        "week_pct": _pct_change(equity, eq_week),
        "month_pct": _pct_change(equity, eq_month),
    }
    
    closed_today = db.closed_positions_since(start_today_ms, user_id)
    wins = sum(1 for p in closed_today if (p.get("realized_pnl") or 0) > 0)
    losses = sum(1 for p in closed_today if (p.get("realized_pnl") or 0) < 0)
    n_trades = len(closed_today)
    win_rate = round(wins / n_trades * 100, 1) if n_trades > 0 else 0.0
    realized = sum((p.get("realized_pnl") or 0) for p in closed_today)
    
    today_stats = {
        "trades": n_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "realized_pnl": round(realized, 2),
        "fees": 0.0
    }
    
    open_pos = db.open_positions(user_id=user_id)
    pos_summaries = []
    matched_ex_keys = set()
    
    # 1. Ophelia-managed positions
    for p in open_pos:
        sym_clean = p["symbol"].replace("-USDT", "USDT") if p.get("symbol") else ""
        ex_pos = next((x for x in positions if (x["symbol"] == p["symbol"] or x["symbol"] == sym_clean) and x["side"] == p["direction"]), None)
        if ex_pos:
            matched_ex_keys.add((ex_pos["symbol"], ex_pos["side"]))
            mark = ex_pos.get("mark") or p["entry"]
            upnl = ex_pos.get("unrealized_pnl") or 0.0
            upnl_pct = ex_pos.get("unrealized_pnl_pct") or 0.0
            liq_price = ex_pos.get("liquidation_price")
        else:
            # Query authoritative 1m market feed for current mark price
            rows1m = db.query_candles(p["symbol"], int(time.time() * 1000) - 180_000, int(time.time() * 1000) + 1000)
            mark = float(rows1m[-1]["close"]) if rows1m else float(p["entry"])
            sign = 1 if p["direction"] == "LONG" else -1
            upnl = round((mark - float(p["entry"])) * float(p["qty"]) * sign, 2)
            margin_base = float(p.get("margin_usdt") or p.get("margin") or (float(p["entry"]) * float(p["qty"]) / float(p.get("leverage") or 1)))
            upnl_pct = round((upnl / margin_base) * 100.0, 2) if margin_base > 0 else 0.0
            liq_price = None
            
        pos_summaries.append({
            "id": str(p["id"]),
            "symbol": p["symbol"],
            "direction": p["direction"],
            "source": "OPHELIA_MANAGED",
            "management_status": "OPHELIA MANAGED" if ex_pos or p.get("mode") == "SHADOW" else "DESYNCED",
            "strategy": p.get("strategy") or "OPHELIA_CORE",
            "timeframe": p.get("timeframe") or "5m",
            "entry": p["entry"],
            "current_price": mark,
            "qty": p.get("qty") or (ex_pos.get("qty") if ex_pos else 0.0),
            "margin": p.get("margin_usdt") or p.get("margin") or 0.0,
            "leverage": p.get("leverage") or (ex_pos.get("leverage") if ex_pos else 1),
            "unrealized_pnl": round(upnl, 2),
            "unrealized_pnl_pct": upnl_pct,
            "liquidation_price": liq_price,
            "stops": [round(float(s["value"]) if isinstance(s, dict) and "value" in s else float(s), 2) for s in p.get("stops", []) if (isinstance(s, dict) and "value" in s) or isinstance(s, (int, float))],
            "targets": [round(float(t["value"]) if isinstance(t, dict) and "value" in t else float(t), 2) for t in p.get("targets", []) if (isinstance(t, dict) and "value" in t) or isinstance(t, (int, float))],
            "trailing_pct": p.get("trailing_pct"),
            "status": p.get("status", "ACTIVE"),
            "provenance": DataProvenance.SHADOW_PAPER.value if (p.get("mode") == "SHADOW" or db.get_mode() == "SHADOW") else DataProvenance.LIVE_BINGX.value
        })
        
    # 2. External / Manual BingX positions
    for ex_pos in positions:
        key = (ex_pos["symbol"], ex_pos["side"])
        if key not in matched_ex_keys:
            # External manual BingX position detected!
            notional = ex_pos.get("notional", 0.0)
            lev = ex_pos.get("leverage", 1.0) or 1.0
            calc_margin = round(notional / lev, 2) if notional and lev else 0.0
            pos_summaries.append({
                "id": str(ex_pos.get("position_id") or abs(hash(ex_pos["symbol"] + ex_pos["side"]))),
                "symbol": ex_pos["symbol"],
                "direction": ex_pos["side"],
                "source": "BINGX MANUAL",
                "management_status": "EXTERNAL POSITION",
                "strategy": "MANUAL",
                "timeframe": "N/A",
                "entry": ex_pos.get("entry", 0.0),
                "current_price": ex_pos.get("mark", 0.0),
                "qty": ex_pos.get("qty", 0.0),
                "margin": calc_margin,
                "leverage": lev,
                "unrealized_pnl": round(ex_pos.get("unrealized_pnl", 0.0), 2),
                "unrealized_pnl_pct": ex_pos.get("unrealized_pnl_pct", 0.0),
                "liquidation_price": ex_pos.get("liquidation_price"),
                "stops": [],
                "targets": [],
                "trailing_pct": None,
                "status": "EXTERNAL POSITION",
                "provenance": DataProvenance.LIVE_BINGX.value
            })
            try:
                from . import notifications
                notifications.notify_external_position(pos_summaries[-1], user_id=user_id)
                liq_p = ex_pos.get("liquidation_price")
                mark_p = ex_pos.get("mark", 0.0)
                if mark_p and liq_p and liq_p > 0:
                    dist_pct = abs(mark_p - liq_p) / mark_p * 100.0
                    if dist_pct < 8.0:
                        notifications.notify_liquidation_risk(
                            pos_summaries[-1],
                            mark_price=mark_p,
                            liq_price=liq_p,
                            distance_pct=round(dist_pct, 2),
                            user_id=user_id
                        )
            except Exception:
                pass
        
    pos_summary = pos_summaries[0] if pos_summaries else None
        
    margin_pct = round((account.get("used_margin", 0) / equity) * 100, 1) if equity > 0 else 0.0
    risk_status = "NORMAL"
    if margin_pct > 80:
        risk_status = "CRITICAL"
    elif margin_pct > 50:
        risk_status = "WARNING"
        
    risk = {
        "positions_count": len(pos_summaries),
        "positions_max": db.get_max_open_trades(),
        "margin_pct": margin_pct,
        "available": account.get("available_margin", 0.0),
        "status": risk_status
    }
    
    recent_trades = db.get_recent_completed_trades(limit=3, user_id=user_id)
    sanitized_trades = []
    for t in recent_trades:
        trade_prov = str(t.get("provenance") or (DataProvenance.SHADOW_PAPER.value if (t.get("mode") == "SHADOW" or db.get_mode() == "SHADOW") else DataProvenance.LIVE_BINGX.value))
        sanitized_trades.append({
            "id": str(t.get("id") or "0"),
            "symbol": str(t.get("symbol") or ""),
            "direction": str(t.get("direction") or "LONG"),
            "entry": float(t.get("entry") or 0.0),
            "exit_price": float(t.get("exit_price") or 0.0),
            "qty": float(t.get("qty") or 0.0),
            "realized_pnl": float(t.get("realized_pnl") or 0.0),
            "leverage": float(t.get("leverage") or 1.0),
            "margin": float(t.get("margin") or 0.0),
            "closed_ms": int(t.get("closed_ms") or 0),
            "pnl_pct": float(t.get("pnl_pct") or 0.0),
            "provenance": trade_prov
        })
    
    cap = account_capacity(user_id)
    h = core.health()
    
    perf["provenance"] = account_prov
    today_stats["provenance"] = DataProvenance.SHADOW_PAPER.value if (db.get_mode() == "SHADOW") else DataProvenance.LIVE_BINGX.value

    return {
        "health": h,
        "position": pos_summary,
        "positions": pos_summaries,
        "capacity": cap,
        "account": {
            "total_equity": equity,
            "wallet_balance": account.get("balance", 0.0),
            "balance": account.get("balance", 0.0),
            "equity": equity,
            "available_margin": account.get("available_margin", 0.0),
            "ophelia_used": account.get("used_margin", 0.0),
            "unrealized_pnl": account.get("unrealized_pnl", 0.0),
            "provenance": account_prov,
            "connected": account.get("connected", True),
            "connection_state": account.get("connection_state", "CONNECTED" if account.get("connected") else "DISCONNECTED"),
            "connection_status": account.get("connection_status", "CONNECTED" if account.get("connected") else "DISCONNECTED"),
            "account_type": account.get("account_type", "USER_BINGX_ACCOUNT"),
        },
        "performance": perf,
        "today": today_stats,
        "risk": risk,
        "last_trades": sanitized_trades,
        "provenance": account_prov,
        "account_provenance": account_prov,
        "system": {"status": "All systems operational"}
    }


def take_snapshot_all_users() -> None:
    """Take equity snapshots for all active users with connected exchange accounts."""
    try:
        from . import credential_vault
        users = db.list_all_users()
        for u in users:
            uid = u["id"]
            if uid and uid > 0 and credential_vault.user_has_credentials(uid):
                take_snapshot(user_id=uid)
    except Exception as e:
        print(f"Error in take_snapshot_all_users: {e}")

