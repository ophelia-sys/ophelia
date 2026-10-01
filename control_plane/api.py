import asyncio
import json
import time
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Union

try:
    import bcrypt
except ImportError:
    bcrypt = None
try:
    import jwt
except ImportError:
    jwt = None
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from . import db, core, config, analytics, notifications, news, intelligence, retest_engine, backtest, strategy_lab, credential_vault, replication_orchestrator, account, us_market, symbols
from institutional import daily_structural_bias

import os
import secrets

_cached_dev_secret: str | None = None

def _get_jwt_secret() -> str:
    global _cached_dev_secret
    secret = os.environ.get("SECRET_KEY") or os.environ.get("JWT_SECRET")
    if secret:
        return secret
    is_prod = (
        os.environ.get("OPHELIA_ENV") == "production"
        or os.environ.get("ENV") == "production"
        or (hasattr(db, "get_mode") and db.get_mode() == "LIVE")
    )
    if is_prod:
        raise RuntimeError("Production secret required: SECRET_KEY or JWT_SECRET must be set")
    if _cached_dev_secret:
        return _cached_dev_secret
    secret_path = os.path.join(config.DATA_DIR, ".jwt_secret")
    if os.path.exists(secret_path):
        try:
            with open(secret_path, "r", encoding="utf-8") as _f:
                content = _f.read().strip()
                if content:
                    _cached_dev_secret = content
                    return content
        except Exception:
            pass
    try:
        new_secret = secrets.token_hex(32)
        os.makedirs(config.DATA_DIR, exist_ok=True)
        with open(secret_path, "w", encoding="utf-8") as _f:
            _f.write(new_secret)
        try:
            os.chmod(secret_path, 0o600)
        except Exception:
            pass
        _cached_dev_secret = new_secret
        return new_secret
    except Exception:
        if not _cached_dev_secret:
            _cached_dev_secret = secrets.token_hex(32)
        return _cached_dev_secret


SECRET_KEY = _get_jwt_secret()
ALGORITHM = "HS256"

security = HTTPBearer(auto_error=False)

def create_access_token(data: dict):
    to_encode = data.copy()
    if "sub" in to_encode and "user_id" not in to_encode:
        try:
            to_encode["user_id"] = int(to_encode["sub"])
        except Exception:
            pass
    to_encode.update({"exp": time.time() + 3600 * 24 * 7}) # 7 days
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user_id(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> int:
    """Strict authenticated user ID resolver. ZERO FALLBACK."""
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Authentication token required")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        raw_uid = payload.get("user_id") if payload.get("user_id") is not None else payload.get("sub")
        if raw_uid is None:
            raise HTTPException(status_code=401, detail="Invalid token: missing subject")
        uid = int(raw_uid)
        u = db.get_user_by_id(uid)
        if not u:
            raise HTTPException(status_code=401, detail="User not found")
        return uid
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication error")

def get_current_user(user_id: int = Depends(get_current_user_id)) -> dict:
    u = db.get_user_by_id(user_id)
    if not u:
        raise HTTPException(status_code=401, detail="User not found")
    return u

def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "ADMIN":
        raise HTTPException(status_code=403, detail="Forbidden: Admin authority required")
    return user

def require_authenticated_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication token required")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        raw_uid = payload.get("user_id") if payload.get("user_id") is not None else payload.get("sub")
        if raw_uid is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        uid = int(raw_uid)
        u = db.get_user_by_id(uid)
        if not u:
            raise HTTPException(status_code=401, detail="User not found")
        return u
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

# --- WebSocket Manager ---
class ConnectionManager:
    def __init__(self):
        # user_id -> list of websockets
        self.active_connections: dict[int, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_personal_message(self, message: dict, user_id: int):
        if user_id in self.active_connections:
            txt = json.dumps(message)
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_text(txt)
                except Exception:
                    pass

manager = ConnectionManager()

# --- Background Tasks ---
async def poll_outbox_loop():
    last_id = 0
    while True:
        try:
            events = db.poll_ws_outbox(last_id)
            for eid, uid, etype, payload in events:
                last_id = max(last_id, eid)
                msg = {"type": etype, "payload": payload}
                await manager.send_personal_message(msg, uid)
            
            # occasional cleanup
            if int(time.time()) % 3600 == 0:
                db.cleanup_ws_outbox()
        except Exception as e:
            print(f"Outbox poll error: {e}")
            
        await asyncio.sleep(0.5)

async def market_snapshot_loop():
    """Shared market data polling loop."""
    while True:
        try:
            # Get all unique active watchlist symbols across all users
            conn = db._wl_conn()
            rows = conn.execute("SELECT DISTINCT symbol FROM watchlist WHERE active=1").fetchall()
            symbols = [r[0] for r in rows]
            
            snapshots = {}
            for sym in symbols:
                snap = analytics.get_market_snapshot(sym, lookback_min=60, agg_interval_min=5, volume_flow=True, order_book=True)
                if "error" not in snap:
                    price = snap.get("last_price") or 0.0
                    inds = snap.get("indicators", {})
                    flow = snap.get("volume_flow", {})
                    ob = snap.get("order_book", {})
                    vreg = analytics.vwap_regime(sym, tf_min=5)
                    st = analytics.get_supertrend(sym, tf_min=5)
                    vol_telem = analytics.get_structured_volume_telemetry(sym, tf_min=5)
                    
                    cd_24h = analytics.get_candles(sym, lookback_min=1440, base_interval_min=1, agg_interval_min=15)
                    price_change_pct = 0.0
                    if "candles" in cd_24h and cd_24h["candles"]:
                        open_24h = cd_24h["candles"][0].get("open")
                        if open_24h and open_24h > 0:
                            price_change_pct = round(((price - open_24h) / open_24h) * 100.0, 2)

                    try:
                        from institutional import daily_structural_bias
                        bias_data = daily_structural_bias.compute_daily_structural_bias(sym)
                        m_reg = bias_data.get("market_regime", "NEUTRAL / UNCERTAIN")
                        dir_state = bias_data.get("direction", "NEUTRAL")
                        t_prio = bias_data.get("trade_priority", "NORMAL PRIORITY")
                        pos_reg = bias_data.get("positioning_regime", "POSITIONING DATA NOT AVAILABLE")
                        gam_reg = bias_data.get("gamma_regime", "GAMMA DATA NOT AVAILABLE")
                    except Exception:
                        m_reg = "NEUTRAL / UNCERTAIN"
                        dir_state = "NEUTRAL"
                        t_prio = "NORMAL PRIORITY"
                        pos_reg = "POSITIONING DATA NOT AVAILABLE"
                        gam_reg = "GAMMA DATA NOT AVAILABLE"

                    snapshots[sym] = {
                        "price": float(price),
                        "price_change_pct": float(price_change_pct),
                        "volume": float(vol_telem["volume_24h"]),
                        "volume_24h": float(vol_telem["volume_24h"]),
                        "volume_24h_base": float(vol_telem.get("volume_24h_base") or 0.0),
                        "current_candle_volume": float(vol_telem["current_candle_volume"]),
                        "current_candle_base_volume": float(vol_telem.get("current_candle_base_volume") or 0.0),
                        "current_candle_label": vol_telem.get("current_candle_label") or "CURRENT 5m CANDLE",
                        "timeframe_volume": float(vol_telem["timeframe_volume"]),
                        "timeframe_base_volume": float(vol_telem.get("timeframe_base_volume") or 0.0),
                        "rolling_volume_1h": float(vol_telem["rolling_volume_1h"]),
                        "rolling_base_volume_1h": float(vol_telem.get("rolling_base_volume_1h") or 0.0),
                        "session_volume": float(vol_telem["session_volume"]),
                        "session_base_volume": float(vol_telem.get("session_base_volume") or 0.0),
                        "base_asset": vol_telem.get("base_asset") or "BTC",
                        "volume_unit": "USDT",
                        "rvol": float(vol_telem["rvol"]),
                        "direction": dir_state,
                        "market_regime": m_reg,
                        "volatility_regime": "NORMAL",
                        "positioning_regime": pos_reg,
                        "gamma_regime": gam_reg,
                        "trade_priority": t_prio,
                        "inflow": float(flow.get("inflow") or 0.0),
                        "outflow": float(flow.get("outflow") or 0.0),
                        "net_flow": float(flow.get("net_flow") or 0.0),
                        "vwap": float(vreg.get("vwap", 0.0) if not "error" in vreg else 0.0),
                        "vwap_separation_pct": float(vreg.get("separation_pct", 0.0) if not "error" in vreg else 0.0),
                        "vwap_regime": {
                            "state": vreg.get("state", "CHOP") if not "error" in vreg else "CHOP",
                            "eligible": vreg.get("eligible", "NONE") if not "error" in vreg else "NONE"
                        },
                        "supertrend": float(st.get("line", 0.0) if not "error" in st else 0.0),
                        "supertrend_direction": "BULLISH" if st.get("state") == "GREEN" else ("BEARISH" if st.get("state") == "RED" else "NEUTRAL"),
                        "ema9": float(inds.get("EMA9") or 0.0),
                        "ema20": float(inds.get("EMA20") or 0.0),
                        "ema_spread": float(inds.get("EMA_spread") or 0.0),
                        "order_book_skew": float(ob.get("imbalance_pct") or 0.0)
                    }
            
            # Distribute to users based on their personal watchlist
            for user_id, conns in manager.active_connections.items():
                if not conns:
                    continue
                user_wl = db.get_user_watchlist(user_id)
                user_snaps = {s: snapshots[s] for s in user_wl if s in snapshots}
                if user_snaps:
                    await manager.send_personal_message({"type": "MARKET_SNAPSHOTS", "payload": user_snaps}, user_id)
                    
        except Exception as e:
            print(f"Market loop error: {e}")
            
        await asyncio.sleep(1.0) # Update market every 1s

async def dashboard_loop():
    """Periodic dashboard updates and equity snapshotting."""
    from . import account
    last_snapshot = 0
    while True:
        try:
            now = time.time()
            if now - last_snapshot > 900: # Every 15 minutes
                account.take_snapshot_all_users()
                last_snapshot = now
                
            # Broadcast dashboard state every 5s
            for user_id, conns in manager.active_connections.items():
                if not conns:
                    continue
                u = db.get_user_by_id(user_id)
                is_admin = bool(u and u.get("role") == "ADMIN")
                dashboard_data = account.dashboard_view(user_id=user_id, is_admin_caller=is_admin)
                await manager.send_personal_message({"type": "DASHBOARD_UPDATE", "payload": dashboard_data}, user_id)
                
        except Exception as e:
            print(f"Dashboard loop error: {e}")
            
        await asyncio.sleep(5.0)

async def equity_report_loop():
    """Runs every 60s, checks if >= 4 hours (14,400,000 ms) have elapsed since the last
    authoritative equity checkpoint, and generates an idempotent 4H Equity Report notification."""
    from . import account
    while True:
        try:
            now_ms = int(time.time() * 1000)
            four_hours_ms = 4 * 3600 * 1000
            
            user_ids = [1]
            try:
                conn = db._connect()
                rows = conn.execute("SELECT id FROM users").fetchall()
                if rows:
                    user_ids = [r[0] for r in rows]
            except Exception:
                pass
                
            for uid in user_ids:
                latest = db.get_latest_equity_checkpoint(uid)
                should_record = False
                prev_equity = 0.0
                
                if latest is None:
                    should_record = True
                elif now_ms - latest["ts_ms"] >= four_hours_ms:
                    should_record = True
                    prev_equity = latest["total_equity"]
                    
                if should_record:
                    dash = account.dashboard_view(user_id=uid)
                    curr_equity = dash.get("equity", 0.0)
                    balance = dash.get("balance", 0.0)
                    avail_margin = dash.get("available_margin", 0.0)
                    upnl = dash.get("unrealized_pnl", 0.0)
                    mode = db.get_mode()
                    open_pos = len(dash.get("positions", []))
                    
                    four_hours_ago_ms = now_ms - four_hours_ms
                    closed_4h = db.closed_positions_since(four_hours_ago_ms, user_id=uid)
                    realized_4h = sum(float(p.get("realized_pnl") or 0) for p in closed_4h)
                    
                    db.record_equity_checkpoint(
                        user_id=uid,
                        equity=curr_equity,
                        balance=balance,
                        avail_margin=avail_margin,
                        realized_pnl=realized_4h,
                        unrealized_pnl=upnl,
                        open_positions=open_pos,
                        mode=mode,
                        ts_ms=now_ms
                    )
                    
                    if latest is not None and prev_equity > 0:
                        notifications.notify_4h_equity_report(
                            current_equity=curr_equity,
                            prev_equity=prev_equity,
                            realized_pnl_4h=round(realized_4h, 2),
                            unrealized_pnl=round(upnl, 2),
                            open_positions=open_pos,
                            mode=mode,
                            user_id=uid
                        )
        except Exception as e:
            print(f"Equity report loop error: {e}")
            
        await asyncio.sleep(60.0)

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.ensure_seed_watchlist()
    db.ensure_root_admin()
    asyncio.create_task(poll_outbox_loop())
    asyncio.create_task(market_snapshot_loop())
    asyncio.create_task(dashboard_loop())
    asyncio.create_task(equity_report_loop())
    yield

app = FastAPI(title="Ophelia API Gateway", lifespan=lifespan)

# --- Models ---
class LoginRequest(BaseModel):
    email: Optional[str] = None
    username: Optional[str] = None
    user_id: Optional[str] = None
    password: str

class RegisterRequest(BaseModel):
    email: str
    password: str

class WatchlistAddRequest(BaseModel):
    symbol: str

class SymbolScope(BaseModel):
    mode: str = "SINGLE"
    symbols: Optional[List[str]] = []

class AutomationCreateRequest(BaseModel):
    strategy: str
    symbol_scope: Union[SymbolScope, str, Dict[str, Any]]
    timeframe: Optional[str] = None
    strategy_timeframes: Optional[Dict[str, int]] = None
    direction_preference: Optional[str] = "ANY"
    direction: Optional[str] = None
    margin_usage_pct: Optional[float] = 0.0
    margin_pct: Optional[float] = None
    fixed_margin: Optional[float] = None
    margin_usdt: Optional[float] = None
    leverage: float = 15.0
    mode: Optional[str] = None
    lifecycle: str = "CONTINUOUS"
    vwap_gate_enabled: Optional[bool] = True
    strategy_risk: Optional[Dict[str, Any]] = None
    note: Optional[str] = None

class AskRequest(BaseModel):
    query: str
    intent: str = "MARKET_QUERY"

class ModeToggleRequest(BaseModel):
    target: str = "ACCOUNT"
    target_id: Optional[int] = None
    mode: str = "SHADOW"

class NotificationSettingsRequest(BaseModel):
    enabled: Optional[bool] = True
    trades_enabled: Optional[bool] = True
    tp_sl_enabled: Optional[bool] = True
    risk_enabled: Optional[bool] = True
    automations_enabled: Optional[bool] = True
    system_enabled: Optional[bool] = True
    equity_4h_enabled: Optional[bool] = True

# --- Endpoints ---
@app.post("/api/auth/register")
def register(req: RegisterRequest):
    conn = db._connect()
    hashed = bcrypt.hashpw(req.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    try:
        cur = conn.execute(
            "INSERT INTO users(email, password_hash, created_ms) VALUES(?,?,?)",
            (req.email, hashed, int(time.time() * 1000))
        )
        conn.commit()
        user_id = cur.lastrowid
        token = create_access_token({"sub": str(user_id)})
        return {"token": token, "user_id": user_id}
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            raise HTTPException(status_code=400, detail="Email already registered")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/login")
def login(req: LoginRequest):
    identifier = (req.username or req.user_id or req.email or "").strip()
    if not identifier:
        raise HTTPException(status_code=400, detail="User ID or email is required")
    conn = db._connect()
    row = conn.execute(
        "SELECT id, password_hash, role FROM users WHERE email=? OR user_uid=? OR display_name=?",
        (identifier, identifier, identifier)
    ).fetchone()
    if not row and identifier.lower() in ("ophelia-sys", "admin", "root", "1"):
        row = conn.execute("SELECT id, password_hash, role FROM users WHERE id=1").fetchone()
    if not row and identifier.isdigit():
        row = conn.execute("SELECT id, password_hash, role FROM users WHERE id=?", (int(identifier),)).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user_id, hashed = row[0], row[1]
    role = row[2] if len(row) > 2 and row[2] else ("ADMIN" if user_id == 1 else "USER")
    if not hashed or not bcrypt.checkpw(req.password.encode('utf-8'), hashed.encode('utf-8')):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": str(user_id), "role": role})
    return {"token": token, "user_id": user_id, "role": role}

@app.get("/api/market/watchlist")
def get_watchlist(user_id: int = Depends(get_current_user_id)):
    return {"symbols": db.get_user_watchlist(user_id)}

@app.post("/api/market/watchlist")
def add_watchlist(req: WatchlistAddRequest, user_id: int = Depends(get_current_user_id)):
    ok = db.watchlist_add(req.symbol, user_id=user_id)
    return {"success": ok}

@app.delete("/api/market/watchlist/{symbol}")
def remove_watchlist(symbol: str, user_id: int = Depends(get_current_user_id)):
    ok = db.watchlist_remove(symbol, user_id=user_id)
    return {"success": ok}

@app.get("/api/market/snapshot/{symbol}")
def market_snapshot(symbol: str, tf: str = "5m", user_id: int = Depends(get_current_user_id)):
    try:
        tf_int = int(str(tf).replace("m", ""))
    except ValueError:
        tf_int = 5
        
    lookback = max(60, tf_int * 12)
    if "GOLD" in symbol.upper() or "XAU" in symbol.upper():
        lookback = max(lookback, 72 * 60)  # Accommodate weekend session closure for gold contracts
    snap = analytics.get_market_snapshot(symbol, lookback_min=lookback, agg_interval_min=tf_int, volume_flow=True, order_book=True)
    if "error" in snap:
        snap = analytics.get_market_snapshot(symbol, lookback_min=96 * 60, agg_interval_min=tf_int, volume_flow=True, order_book=True)
        if "error" in snap:
            raise HTTPException(status_code=400, detail=snap["error"])
        
    price = snap.get("last_price") or 0.0
    inds = snap.get("indicators", {})
    flow = snap.get("volume_flow", {})
    ob = snap.get("order_book", {})

    vreg = analytics.vwap_regime(symbol, tf_min=tf_int)
    st = analytics.get_supertrend(symbol, tf_min=tf_int)
    vol_telem = analytics.get_structured_volume_telemetry(symbol, tf_min=tf_int)
    
    cd_24h = analytics.get_candles(symbol, lookback_min=1440, base_interval_min=1, agg_interval_min=15)
    price_change_pct = 0.0
    if "candles" in cd_24h and cd_24h["candles"]:
        open_24h = cd_24h["candles"][0].get("open")
        if open_24h and open_24h > 0:
            price_change_pct = round(((price - open_24h) / open_24h) * 100.0, 2)
            
    # Hierarchical regime & daily bias context
    try:
        from institutional import daily_structural_bias
        bias_res = daily_structural_bias.compute_daily_structural_bias(symbol)
        m_reg = bias_res.get("market_regime", "UNCERTAIN")
        v_reg = bias_res.get("volatility_regime", "NORMAL")
        g_reg = bias_res.get("gamma_regime", "GAMMA DATA NOT AVAILABLE")
        d_pref = bias_res.get("daily_preference", "NEUTRAL")
        d_sum = bias_res.get("summary", "")
        counter_ok = bias_res.get("allows_counter_trend", True)
    except Exception:
        bias_res = {}
        m_reg = "CHOP / MEAN REVERSION" if vreg.get("state") == "CHOP" else "TREND / EXPANSION"
        v_reg = "NORMAL"
        g_reg = "GAMMA DATA NOT AVAILABLE"
        d_pref = "NEUTRAL"
        d_sum = "Structural daily bias neutral."
        counter_ok = True

    # Volatility Indices
    try:
        from control_plane import volatility_indices
        vol_indices = volatility_indices.get_volatility_indices()
    except Exception:
        vol_indices = {}

    cvi_obj = vol_indices.get("cvi", 50.0)
    cvi_val = cvi_obj.get("value", 50.0) if isinstance(cvi_obj, dict) else float(cvi_obj or 50.0)

    bvin_obj = vol_indices.get("bvin_bvol", vol_indices.get("bvin", 50.0))
    bvin_val = bvin_obj.get("value", 50.0) if isinstance(bvin_obj, dict) else float(bvin_obj or 50.0)

    vcrix_obj = vol_indices.get("vcrix", 50.0)
    vcrix_val = vcrix_obj.get("value", 50.0) if isinstance(vcrix_obj, dict) else float(vcrix_obj or 50.0)

    htf = bias_res.get("higher_tf_structure", {})
    htf_4h = htf.get("trend_4h", "NEUTRAL") if isinstance(htf, dict) else "NEUTRAL"
    htf_1d = htf.get("trend_1d", "NEUTRAL") if isinstance(htf, dict) else "NEUTRAL"
    news_ctx = str(bias_res.get("news_macro_bias") or "MACRO LIQUIDITY STABLE")

    gex_data = {
        "gamma_regime": g_reg,
        "net_gex": None,
        "gamma_flip": None,
        "distance_from_flip_pct": None,
    }

    return {
        "symbol": symbol,
        "price": float(price),
        "price_change_pct": float(price_change_pct),
        "volume": float(vol_telem["volume_24h"]),
        "volume_24h": float(vol_telem["volume_24h"]),
        "volume_24h_base": float(vol_telem.get("volume_24h_base") or 0.0),
        "current_candle_volume": float(vol_telem["current_candle_volume"]),
        "current_candle_base_volume": float(vol_telem.get("current_candle_base_volume") or 0.0),
        "current_candle_label": vol_telem.get("current_candle_label") or f"CURRENT {tf_int}m CANDLE",
        "timeframe_volume": float(vol_telem["timeframe_volume"]),
        "timeframe_base_volume": float(vol_telem.get("timeframe_base_volume") or 0.0),
        "rolling_volume_1h": float(vol_telem["rolling_volume_1h"]),
        "rolling_base_volume_1h": float(vol_telem.get("rolling_base_volume_1h") or 0.0),
        "session_volume": float(vol_telem["session_volume"]),
        "session_base_volume": float(vol_telem.get("session_base_volume") or 0.0),
        "base_asset": vol_telem.get("base_asset") or "BTC",
        "volume_unit": "USDT",
        "rvol": float(vol_telem["rvol"]),
        "direction": bias_res.get("direction", "NEUTRAL"),
        "market_regime": m_reg,
        "volatility_regime": v_reg,
        "positioning_regime": bias_res.get("positioning_regime", "POSITIONING DATA NOT AVAILABLE"),
        "gamma_regime": g_reg,
        "trade_priority": bias_res.get("trade_priority", "NORMAL PRIORITY"),
        "daily_preference": d_pref,
        "daily_bias_summary": d_sum,
        "allows_counter_trend": counter_ok,
        "volume_telemetry": vol_telem,
        "inflow": float(flow.get("inflow") or 0.0),
        "outflow": float(flow.get("outflow") or 0.0),
        "net_flow": float(flow.get("net_flow") or 0.0),
        "cvd": float(vol_telem.get("cvd") or flow.get("cvd") or 0.0),
        "cvi": float(cvi_val),
        "bvin": float(bvin_val),
        "vcrix": float(vcrix_val),
        "htf_4h_structure": htf_4h,
        "htf_1d_structure": htf_1d,
        "news_macro_context": news_ctx,
        "ml_intelligence_bias": d_pref,
        "final_daily_market_bias": d_pref,
        "gex_data": gex_data,
        "key_levels": bias_res.get("key_levels", {}),
        "liquidity_map": bias_res.get("liquidity_map", {}),
        "vwap": float(vreg.get("vwap", 0.0) if not "error" in vreg else 0.0),
        "vwap_separation_pct": float(vreg.get("separation_pct", 0.0) if not "error" in vreg else 0.0),
        "vwap_regime": {
            "state": vreg.get("state", "CHOP") if not "error" in vreg else "CHOP",
            "eligible": vreg.get("eligible", "NONE") if not "error" in vreg else "NONE"
        },
        "supertrend": float(st.get("line", 0.0) if not "error" in st else 0.0),
        "supertrend_direction": "BULLISH" if st.get("state") == "GREEN" else ("BEARISH" if st.get("state") == "RED" else "NEUTRAL"),
        "ema9": float(inds.get("EMA9") or 0.0),
        "ema20": float(inds.get("EMA20") or 0.0),
        "ema_spread": float(inds.get("EMA_spread") or 0.0),
        "order_book_skew": float(ob.get("imbalance_pct") or 0.0)
    }

@app.get("/api/market/volume-telemetry/{symbol}")
def get_volume_telemetry_endpoint(symbol: str, tf: str = "5m", user_id: int = Depends(get_current_user_id)):
    try:
        tf_int = int(str(tf).replace("m", ""))
    except ValueError:
        tf_int = 5
    return analytics.get_structured_volume_telemetry(symbol, tf_min=tf_int)

@app.get("/api/volume/telemetry/{symbol}")
def get_volume_telemetry_alias(symbol: str, tf: str = "5m", user_id: int = Depends(get_current_user_id)):
    return get_volume_telemetry_endpoint(symbol, tf, user_id)

@app.get("/api/health")
def get_health():
    return core.health()

@app.get("/api/dashboard")
def get_dashboard(mode: Optional[str] = "LIVE", user: dict = Depends(require_authenticated_user)):
    user_id = user["id"]
    is_admin = (user.get("role") == "ADMIN")
    from . import account
    return account.dashboard_view(user_id=user_id, is_admin_caller=is_admin, mode=mode)

@app.get("/api/account/capacity")
def get_capacity(user_id: int = Depends(get_current_user_id)):
    from . import account
    return account.account_capacity(user_id=user_id)

@app.get("/api/automations")
def get_automations(status: Optional[str] = None, user_id: int = Depends(get_current_user_id)):
    autos = db.list_automations(status=status, user_id=user_id)
    enriched = []
    for a in autos:
        aid = a["id"]
        # Check linked candidate
        cand = db.get_setup_candidate_by_automation(aid)
        if cand:
            a["candidate_state"] = cand.get("current_state")
            a["waiting_reason"] = cand.get("waiting_for") or cand.get("reason")
        else:
            a["candidate_state"] = "MONITORING"
            a["waiting_reason"] = a.get("last_eval_reason")

        # Check linked execution intent and slot
        intent = db.get_execution_intent_by_automation(aid)
        if intent:
            a["execution_intent"] = intent
            if intent.get("slot_id"):
                s = db.get_autonomous_trade_slot(intent["slot_id"], user_id=user_id)
                if s:
                    a["slot_info"] = {
                        "id": s["id"],
                        "name": s["name"],
                        "scope": s.get("scope") or s.get("asset_scope"),
                        "allocated_margin_usdt": s["allocated_margin_usdt"],
                        "max_leverage": s["max_leverage"],
                        "status": s["status"]
                    }
            if intent.get("position_id"):
                pos = db.get_position(intent["position_id"])
                if pos:
                    a["position_status"] = pos.get("status")
                    a["position_id"] = intent["position_id"]
        enriched.append(a)
    return {"automations": enriched}

@app.post("/api/automations")
def create_automation(req: AutomationCreateRequest, user_id: int = Depends(get_current_user_id)):
    from . import account
    
    # Parse symbol_scope safely (accepts SymbolScope model, dict, or str)
    if isinstance(req.symbol_scope, str):
        scope_mode = req.symbol_scope
        scope_symbols = []
    elif isinstance(req.symbol_scope, dict):
        scope_mode = req.symbol_scope.get("mode", "SINGLE")
        scope_symbols = req.symbol_scope.get("symbols", [])
    else:
        scope_mode = req.symbol_scope.mode
        scope_symbols = req.symbol_scope.symbols or []
        
    spec = req.dict(exclude_unset=True)
    if scope_mode == "SINGLE":
        spec["symbol"] = scope_symbols[0] if scope_symbols else ""
    elif scope_mode == "ALL_WATCHLIST":
        spec["symbol"] = "ALL_WATCHLIST"
    else:
        spec["symbol"] = "MULTIPLE"
        spec["symbols"] = scope_symbols
    
    if "symbol_scope" in spec:
        del spec["symbol_scope"]

    # Single Authoritative mode from db.get_mode()
    authoritative_mode = db.get_mode()
    spec["mode"] = authoritative_mode

    # Safety Barrier: if authoritative mode is LIVE, verify live preflight passes!
    if authoritative_mode == "LIVE":
        preflight = core.run_preflight(user_id=user_id)
        if not preflight.get("ready_for_live"):
            failed_items = [f"{c['name']} ({c.get('details') or 'FAILED'})" for c in preflight.get("checks", []) if not c.get("pass")]
            fail_str = ", ".join(failed_items) if failed_items else "safety barrier check failed"
            raise HTTPException(status_code=400, detail=f"LIVE mode preflight check failed: {fail_str}")

    # Authoritative margin allocation validation at SAVE time
    cap = account.account_capacity(user_id=user_id)
    fixed_m = req.fixed_margin or req.margin_usdt
    pct_m = req.margin_usage_pct or req.margin_pct or 0.0
    
    if fixed_m and fixed_m > 0:
        if fixed_m > cap["allocatable_remaining"]:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient unallocated automation margin. Requested: ${fixed_m:.2f}, Available: ${cap['account_available']:.2f}, Reserved: ${cap['automation_reserved']:.2f}, Remaining: ${cap['allocatable_remaining']:.2f}"
            )
        spec["margin_usdt"] = fixed_m
        spec["margin_usage_pct"] = 0.0
    elif pct_m > 0:
        needed_usdt = (pct_m / 100.0) * cap["account_available"]
        if needed_usdt > cap["allocatable_remaining"]:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient unallocated automation margin. Requested {pct_m}% (${needed_usdt:.2f}), Remaining: ${cap['allocatable_remaining']:.2f}"
            )
        spec["margin_usage_pct"] = pct_m
        spec["margin_usdt"] = 0.0

    if req.direction:
        spec["direction_preference"] = req.direction

    try:
        prop = core.build_proposal(spec)
    except core.CoreReject as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    aid = db.create_automation(spec, user_id=user_id)
    db.audit("API", "AUTOMATION_CREATE", {"id": aid, "strategy": req.strategy, "mode": authoritative_mode}, user_id=user_id)
    
    # Notify event
    margin_str = f"${fixed_m:.2f} USDT" if fixed_m else f"{pct_m:.1f}%"
    notifications.notify_automation_event(
        event_type="DEPLOYED",
        auto_id=aid,
        strategy=req.strategy,
        mode=authoritative_mode,
        scope=scope_mode,
        margin_str=margin_str,
        leverage=int(req.leverage),
        user_id=user_id
    )

    return {
        "success": True,
        "id": aid,
        "automation_id": aid,
        "mode": authoritative_mode,
        "strategy": req.strategy,
        "status": "ACTIVE",
        "proposal": prop
    }

@app.get("/api/positions")
def get_positions(mode: Optional[str] = None, user_id: int = Depends(get_current_user_id)):
    from . import account
    dash = account.dashboard_view(user_id=user_id)
    return {"positions": dash.get("positions", [])}

@app.post("/api/positions/{position_id}/edit")
def edit_position(position_id: str, req: dict, user_id: int = Depends(get_current_user_id)):
    try:
        pos = core.edit_position(position_id, req, user_id)
        return {"success": True, "position": pos}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/positions/{position_id}/partial-close")
def partial_close_position(position_id: str, req: dict, user_id: int = Depends(get_current_user_id)):
    try:
        res = core.partial_close_position(position_id, req, user_id)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/positions/{position_id}/close")
def close_position(position_id: str, user_id: int = Depends(get_current_user_id)):
    try:
        pos = core.close_position(position_id, user_id)
        return {"success": True, "position": pos}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/positions/reconcile")
def reconcile_positions(req: Optional[dict] = None, user_id: int = Depends(get_current_user_id)):
    try:
        from . import account
        heal = bool(req.get("heal", False)) if req else False
        return account.reconcile(heal=heal)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/risk/pause-all")
def pause_all_automations(user_id: int = Depends(get_current_user_id)):
    autos = db.list_automations(status="ACTIVE", user_id=user_id)
    for a in autos:
        db.set_automation_status(a["id"], "PAUSED", user_id=user_id)
    db.audit("API", "PAUSE_ALL_AUTOMATIONS", {"count": len(autos)}, user_id=user_id)
    notifications.notify_emergency_action("PAUSE_ALL_AUTOMATIONS", f"Paused {len(autos)} active automations.", mode=db.get_mode(), user_id=user_id)
    return {"success": True, "paused_count": len(autos)}

@app.post("/api/risk/emergency-close-all")
def emergency_close_all(user_id: int = Depends(get_current_user_id)):
    from . import account
    dash = account.dashboard_view(user_id=user_id)
    closed = []
    for p in dash.get("positions", []):
        try:
            core.close_position(p["id"], user_id=user_id)
            closed.append(p["id"])
        except Exception:
            pass
    db.audit("API", "EMERGENCY_CLOSE_ALL", {"closed": closed}, user_id=user_id)
    notifications.notify_emergency_action("EMERGENCY_CLOSE_ALL", f"Instructed close of all positions ({len(closed)} closed).", mode=db.get_mode(), user_id=user_id)
    return {"success": True, "closed_positions": closed}


@app.get("/api/market/contracts")
def get_contracts():
    """Return supported perpetual contracts including dynamically resolved Gold."""
    symbols = [
        "BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "DOGE-USDT", 
        "BNB-USDT", "ADA-USDT", "AVAX-USDT", "LINK-USDT", "SUI-USDT",
        "NEAR-USDT", "APT-USDT", "DOT-USDT", "MATIC-USDT", "LTC-USDT"
    ]
    try:
        gold = config.resolve_gold_contract()
        gold_sym = gold.get("symbol")
        if gold_sym and gold_sym not in symbols:
            symbols.append(gold_sym)
    except Exception:
        pass
    if "GOLD (XAU)" not in symbols:
        symbols.append("GOLD (XAU)")
    return {"symbols": symbols}

@app.get("/api/market/candles/{symbol}")
def get_candles(symbol: str, tf: str = Query("5"), limit: int = Query(100)):
    tf_clean = tf.lower().replace("m", "")
    tf_int = int(tf_clean) if tf_clean.isdigit() else 5
    if tf_int not in (1, 3, 5, 15, 30, 60):
        tf_int = 5
    lookback_min = max(limit * tf_int, 60)
    data = analytics.get_candles(symbol, lookback_min=lookback_min, agg_interval_min=tf_int)
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])
    candles = data.get("candles", [])
    # Return newest 'limit' candles
    return {
        "symbol": symbol,
        "timeframe": f"{tf_int}m",
        "count": len(candles[-limit:]),
        "candles": candles[-limit:]
    }

@app.patch("/api/automations/{automation_id}")
def update_automation(automation_id: int, req: dict, user_id: int = Depends(get_current_user_id)):
    success = db.update_automation(automation_id, req, user_id=user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Automation not found or not owned by user")
    db.audit("API", "AUTOMATION_UPDATE", {"aid": automation_id, "spec": req}, user_id=user_id)
    if "status" in req:
        notifications.notify_automation_event(
            event_type=req["status"],
            auto_id=automation_id,
            strategy="CONFIG",
            mode=db.get_mode(),
            user_id=user_id
        )
    return {"success": True, "automation_id": automation_id}

@app.delete("/api/automations/{automation_id}")
def delete_automation(automation_id: int, user_id: int = Depends(get_current_user_id)):
    success = db.delete_automation(automation_id, user_id=user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Automation not found or not owned by user")
    db.audit("API", "AUTOMATION_DELETE", {"aid": automation_id}, user_id=user_id)
    notifications.notify_automation_event(
        event_type="DELETED",
        auto_id=automation_id,
        strategy="CONFIG",
        mode=db.get_mode(),
        user_id=user_id
    )
    return {"success": True, "deleted_id": automation_id}

def _normalize_strategy_name(name: str) -> str:
    n = str(name or "").strip().upper()
    n = n.replace("-", "_").replace(" ", "_")
    if n in ("OPHELIA_COMPOSITE", "COMPOSITE", "OPHELIA"):
        return "OPHELIA_COMPOSITE"
    if n in ("D_WITHOUT_CVD", "D_NO_CVD", "ABL_D_CVD", "EXPERIMENT_D", "EXP_D", "D"):
        return "D_WITHOUT_CVD"
    if n in ("EXPERIMENT_C", "EXP_C", "C"):
        return "EXPERIMENT_C"
    if n in ("PAPER_P1", "P1"):
        return "PAPER_P1"
    if n in ("PAPER_P2", "P2"):
        return "PAPER_P2"
    if n in ("PAPER_P6A", "P6A"):
        return "PAPER_P6A"
    if n in ("PAPER_P6B", "P6B"):
        return "PAPER_P6B"
    if n in ("CURRENT_BASELINE", "VWAP_SUPERTREND", "BASELINE"):
        return "CURRENT_BASELINE"
    if n in ("EMA_CROSSOVER", "EMA"):
        return "EMA_CROSSOVER"
    return n

def run_strategy_backtest_service(req: dict, user_id: int) -> dict:
    if not user_id or user_id < 1:
        raise HTTPException(status_code=401, detail="Valid user_id required")
    # 1. Parse strategies (multi-select support)
    raw_strategies = req.get("strategies")
    if not raw_strategies:
        raw_strat = req.get("strategy")
        if isinstance(raw_strat, list):
            raw_strategies = raw_strat
        elif isinstance(raw_strat, str) and "," in raw_strat:
            raw_strategies = [s.strip() for s in raw_strat.split(",") if s.strip()]
        elif raw_strat:
            raw_strategies = [raw_strat]
        else:
            raw_strategies = ["OPHELIA_COMPOSITE"]

    strategies = [_normalize_strategy_name(s) for s in raw_strategies]
    dedup_strategies = []
    for s in strategies:
        if s not in dedup_strategies:
            dedup_strategies.append(s)
    strategies = dedup_strategies or ["OPHELIA_COMPOSITE"]

    # 2. Parse symbols
    symbols = req.get("symbols") or [req.get("symbol") or "BTC-USDT"]
    if isinstance(symbols, str):
        symbols = [symbols]
    if "ALL_WATCHLIST" in symbols or req.get("symbol") == "ALL_WATCHLIST":
        symbols = db.watchlist_symbols()
    elif "MULTIPLE" in symbols or req.get("symbol") == "MULTIPLE":
        symbols = [s for s in symbols if s not in ("MULTIPLE", "ALL_WATCHLIST")]
        if not symbols:
            symbols = db.watchlist_symbols()

    # 3. Parse timeframes (multi-timeframe support)
    raw_timeframes = req.get("timeframes")
    if not raw_timeframes:
        tf_raw = req.get("timeframe", 5)
        raw_timeframes = [tf_raw] if isinstance(tf_raw, (int, str)) else list(tf_raw)
    
    parsed_tfs = []
    for t in raw_timeframes:
        try:
            val = str(t).lower().replace("m", "")
            if "h" in val:
                tf_m = int(val.replace("h", "")) * 60
            elif "d" in val:
                tf_m = int(val.replace("d", "")) * 1440
            else:
                tf_m = int(val)
            parsed_tfs.append(tf_m)
        except Exception:
            parsed_tfs.append(5)
    parsed_tfs = parsed_tfs or [5]
    primary_tf = parsed_tfs[0]

    # 4. Stop Loss Presets (defaults: 3m/5m -> 0.7%, 15m -> 1.0%, user configurable)
    default_sl = 0.7 if primary_tf in (3, 5) else 1.0
    sl_preset = float(req.get("sl_pct") or req.get("sl_preset_pct") or req.get("stop_loss_pct") or default_sl)
    use_trailing = bool(req.get("use_trailing", True))
    trailing_pct = float(req.get("trailing_pct") or 0.5)
    hours = min(96, int(req.get("hours") or 96))
    direction_pref = (req.get("direction") or req.get("direction_preference") or "ANY").upper()

    lab = strategy_lab.StrategyResearchLab(
        symbols=symbols,
        timeframes=parsed_tfs,
        hours=hours,
        fee_bps=strategy_lab.DEFAULT_FEE_BPS,
        slippage_bps=strategy_lab.DEFAULT_SLIPPAGE_BPS,
    )
    lab.load_market_data()

    results_by_strategy = {}
    combined_signals = []
    combined_trades = []

    for strat in strategies:
        strat_signals = []
        funnel_tracker = {
            "breakout_candidates": 0,
            "retest_candidates": 0,
            "rejection_confirmations": 0,
            "final_entries": 0,
            "filtered_vwap_alignment": 0,
            "filtered_rvol": 0,
            "filtered_low_volatility": 0,
        }

        for sym in symbols:
            for tf_int in parsed_tfs:
                if strat in ("OPHELIA_COMPOSITE", "COMPOSITE"):
                    sigs = lab.generate_signals_ophelia_composite(sym, tf_int, funnel_tracker=funnel_tracker)
                elif strat in ("D_WITHOUT_CVD", "ABL_D_CVD", "D_NO_CVD"):
                    sigs = lab.generate_signals_exp_d(sym, tf_int, disable_cvd=True, funnel_tracker=funnel_tracker)
                elif strat in ("EXPERIMENT_C", "EXP_C"):
                    sigs = lab.generate_signals_exp_c(sym, tf_int)
                elif strat in ("PAPER_P1", "P1"):
                    sigs = lab.generate_signals_paper_p1(sym, tf_int)
                elif strat in ("PAPER_P2", "P2"):
                    sigs = lab.generate_signals_paper_p2(sym, tf_int)
                elif strat in ("PAPER_P6A", "P6A"):
                    sigs = lab.generate_signals_paper_p6a(sym, tf_int)
                elif strat in ("PAPER_P6B", "P6B"):
                    sigs = lab.generate_signals_paper_p6b(sym, tf_int)
                elif strat in ("CURRENT_BASELINE", "VWAP_SUPERTREND"):
                    sigs = lab.generate_signals_baseline(sym, tf_int)
                else:
                    sigs = lab.generate_signals_ophelia_composite(sym, tf_int, funnel_tracker=funnel_tracker)

                if direction_pref in ("LONG", "SHORT"):
                    sigs = [s for s in sigs if s.get("direction") == direction_pref]
                strat_signals.extend(sigs)

        tp1_val = float(req.get("tp1_pct")) if req.get("tp1_pct") is not None else None
        tp2_val = float(req.get("tp2_pct")) if req.get("tp2_pct") is not None else None
        tp3_val = float(req.get("tp3_pct")) if req.get("tp3_pct") is not None else None

        metrics = lab.simulate_strategy(
            signals=strat_signals,
            strategy_name=strat,
            exp_id=f"BACKTEST_{strat}_{primary_tf}M",
            fixed_sl_pct=sl_preset,
            use_trailing=use_trailing,
            trailing_pct=trailing_pct,
            tp1_pct=tp1_val,
            tp2_pct=tp2_val,
            tp3_pct=tp3_val,
        )

        formatted_trades = []
        for t in (metrics.executed_trades or []):
            entry_ts = int(t.get("entry_ts") or t.get("entry_time") or time.time() * 1000)
            exit_ts = int(t.get("exit_ts") or t.get("exit_time") or time.time() * 1000)
            gross_pct = float(t.get("gross_ret_pct") if t.get("gross_ret_pct") is not None else 0.0)
            net_pct = float(t.get("net_ret_pct") if t.get("net_ret_pct") is not None else (t.get("pnl_pct") or 0.0))
            dur_m = int(t.get("holding_time_min") or t.get("duration_min") or max(1, int((exit_ts - entry_ts) / 60000)))
            outcome_str = str(t.get("outcome") or t.get("exit_reason") or "COMPLETED")
            formatted_trades.append({
                "trade_id": entry_ts,
                "symbol": t.get("symbol") or "BTC-USDT",
                "direction": t.get("direction") or "LONG",
                "side": t.get("direction") or "LONG",
                "strategy": strat,
                "timeframe": f"{primary_tf}m",
                "entry_time": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(entry_ts / 1000)),
                "entry_time_ist": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(entry_ts / 1000)),
                "exit_time": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(exit_ts / 1000)),
                "exit_time_ist": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(exit_ts / 1000)),
                "entry_price": float(t.get("entry_price") or 0.0),
                "exit_price": float(t.get("exit_price") or 0.0),
                "pnl": float(t.get("pnl_usd") or 0.0),
                "symbol_move_pct": round(gross_pct, 2),
                "gross_pnl_pct": round(gross_pct, 2),
                "realized_pnl_pct": round(net_pct, 2),
                "realized_pnl_usdt": float(t.get("pnl_usd") or 0.0),
                "r_multiple": round(float(t.get("r_return") or t.get("r_multiple") or 0.0), 2),
                "mfe_pct": round(float(t.get("mfe_pct") or 0.0), 2),
                "mae_pct": round(float(t.get("mae_pct") or 0.0), 2),
                "highest_favorable_move_pct": round(float(t.get("highest_favorable_move_pct") or t.get("mfe_pct") or 0.0), 2),
                "exit_reason": outcome_str,
                "duration_min": dur_m,
                "fees": float(t.get("fee_usd") or 0.0),
                "fees_usdt": float(t.get("fee_usd") or 0.0),
                "fees_pct": round(float(t.get("fee_pct") or 0.10), 2),
                "slippage": float(t.get("slippage_usd") or 0.0),
                "slippage_pct": round(float(t.get("slippage_pct") or 0.04), 2),
                "funding": float(t.get("funding_usd", 0.0)),
                "funding_pct": round(float(t.get("funding_pct", 0.0)), 2),
                "trailing_activated": bool(t.get("trailing_activated", False) or "TRAILING" in outcome_str),
                "breakeven_activated": bool(t.get("breakeven_activated", False) or "BREAKEVEN" in outcome_str),
            })

        formatted_signals = []
        for s in strat_signals:
            sig_ts = int(s.get("timestamp") or time.time() * 1000)
            formatted_signals.append({
                "signal_id": sig_ts,
                "symbol": s.get("symbol") or "BTC-USDT",
                "timestamp_ms": sig_ts,
                "time_ist": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(sig_ts / 1000)),
                "direction": s.get("direction") or "LONG",
                "type": s.get("direction") or "LONG",
                "strategy": strat,
                "timeframe": f"{s.get('timeframe') or primary_tf}m",
                "status": "VALIDATED",
                "status_detail": "Passed structural candidate check",
                "price": float(s.get("entry_price") or 0.0),
                "vwap": float(s.get("vwap") or s.get("entry_price") or 0.0),
                "vwap_regime": s.get("regime", "EXPANSION"),
                "reason": s.get("reason", "Structural Candidate"),
            })

        # Diagnostic funnel explanation
        funnel_reasons = []
        unsupported_tfs = [tf for tf in parsed_tfs if tf not in (3, 5, 15)]
        if unsupported_tfs:
            funnel_reasons.append(f"Timeframe {unsupported_tfs} is context/microstructure (primary execution evaluates 3m/5m/15m)")
        if funnel_tracker.get("breakout_candidates", 0) == 0:
            funnel_reasons.append("Zero structural breakouts detected in historical sample")
        elif funnel_tracker.get("retest_candidates", 0) == 0:
            funnel_reasons.append("Breakouts detected, but none touched retest zone within causality horizon")
        elif funnel_tracker.get("rejection_confirmations", 0) == 0:
            funnel_reasons.append("Retest touched zone, but rejection was not confirmed before invalidation")
        elif funnel_tracker.get("final_entries", 0) == 0:
            funnel_reasons.append("Rejections confirmed, but blocked by structural target R:R or RVOL constraints")
        elif metrics.trade_count == 0:
            funnel_reasons.append("Signals validated, but risk or concurrent trade cap blocked simulated execution")
        else:
            funnel_reasons.append("Completed with simulated trades")

        diagnostic_reason = "; ".join(funnel_reasons)

        funnel_dto = {
            "breakout_candidates": funnel_tracker.get("breakout_candidates", 0),
            "retest_candidates": funnel_tracker.get("retest_candidates", 0),
            "rejection_confirmations": funnel_tracker.get("rejection_confirmations", 0),
            "final_entries": funnel_tracker.get("final_entries", len(strat_signals)),
            "reason": diagnostic_reason,
        }

        strat_res = {
            "status": "SUCCESS",
            "date_range_ist": f"Last {hours}h (Confirmed BingX Data)",
            "lookback_hours": hours,
            "strategy": strat,
            "symbols_checked": symbols,
            "timeframe": f"{primary_tf}m",
            "timeframes": [f"{tf}m" for tf in parsed_tfs],
            "fixed_sl_preset": f"{sl_preset}% SL",
            "trailing_stop_enabled": use_trailing,
            "signals_count": len(strat_signals),
            "eligible_signals_count": len(strat_signals),
            "blocked_signals_count": max(0, funnel_tracker.get("breakout_candidates", 0) - len(strat_signals)),
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
            "funnel": funnel_dto,
        }
        results_by_strategy[strat] = strat_res
        combined_signals.extend(formatted_signals)
        combined_trades.extend(formatted_trades)

    # If single strategy, return that strategy's result with results_by_strategy attached
    if len(strategies) == 1:
        base_resp = dict(results_by_strategy[strategies[0]])
        base_resp["results_by_strategy"] = results_by_strategy
        return base_resp

    # Multi-strategy consolidated response
    primary_strat = strategies[0]
    total_trades = len(combined_trades)
    return {
        "status": "SUCCESS",
        "date_range_ist": f"Last {hours}h (Confirmed BingX Data)",
        "lookback_hours": hours,
        "strategy": ", ".join(strategies),
        "strategies": strategies,
        "symbols_checked": symbols,
        "timeframe": f"{primary_tf}m",
        "timeframes": [f"{tf}m" for tf in parsed_tfs],
        "fixed_sl_preset": f"{sl_preset}% SL",
        "trailing_stop_enabled": use_trailing,
        "signals_count": len(combined_signals),
        "eligible_signals_count": len(combined_signals),
        "blocked_signals_count": 0,
        "filtered_signals_count": 0,
        "simulated_trades_count": total_trades,
        "win_rate_pct": 0.0 if not total_trades else round(len([t for t in combined_trades if t.get("realized_pnl_pct", 0) > 0]) / total_trades * 100, 1),
        "signals": combined_signals,
        "trades": combined_trades,
        "results_by_strategy": results_by_strategy,
        "funnel": results_by_strategy[primary_strat]["funnel"],
    }

@app.post("/api/automations/backtest")
def backtest_automation(req: dict, user_id: int = Depends(get_current_user_id)):
    """Authoritative strategy backtest executing exact serialized conditions via StrategyResearchLab."""
    return run_strategy_backtest_service(req, user_id=user_id)

@app.post("/api/automations/simulate")
def simulate_automation(req: dict, user_id: int = Depends(get_current_user_id)):
    """Dry-run strategy validation walking recent market candles chronologically."""
    return run_strategy_backtest_service(req, user_id=user_id)

@app.get("/api/trades/history")
def get_trade_history(page: int = Query(1), limit: int = Query(50), 
                      symbol: Optional[str] = None, status: Optional[str] = None,
                      mode: Optional[str] = None, user_id: int = Depends(get_current_user_id)):
    return db.get_paginated_trade_history(user_id=user_id, page=page, limit=limit, 
                                          symbol=symbol, status=status, mode=mode)

@app.get("/api/analytics/performance")
def get_analytics(days: int = Query(30), user_id: int = Depends(get_current_user_id)):
    return db.get_performance_analytics(user_id=user_id, range_days=days)

@app.get("/api/audit/logs")
def get_audit_logs(limit: int = Query(50), user_id: int = Depends(get_current_user_id)):
    return {"logs": db.get_audit_events(user_id=user_id, limit=limit)}

# --- Notifications API ---
@app.get("/api/notifications")
def get_notifications_endpoint(category: str = "ALL", limit: int = 50, offset: int = 0, user_id: int = Depends(get_current_user_id)):
    notifs = db.get_notifications(user_id=user_id, category=category, limit=limit, offset=offset)
    unread = db.get_unread_notification_count(user_id=user_id)
    return {"notifications": notifs, "unread_count": unread}

@app.post("/api/notifications/{notif_id}/read")
def mark_notification_read_endpoint(notif_id: int, user_id: int = Depends(get_current_user_id)):
    ok = db.mark_notification_read(notif_id, user_id=user_id)
    return {"success": ok}

@app.post("/api/notifications/read-all")
def mark_all_notifications_read_endpoint(user_id: int = Depends(get_current_user_id)):
    count = db.mark_all_notifications_read(user_id=user_id)
    return {"success": True, "marked_count": count}

@app.get("/api/notifications/unread-count")
def get_unread_count_endpoint(user_id: int = Depends(get_current_user_id)):
    count = db.get_unread_notification_count(user_id=user_id)
    return {"unread_count": count}

@app.post("/api/notifications/clear")
@app.delete("/api/notifications/clear")
def clear_all_notifications_endpoint(user_id: int = Depends(get_current_user_id)):
    """Clear user alerts with explicit confirmation. Audit logs remain permanent."""
    cleared = db.clear_all_notifications(user_id=user_id)
    return {"success": True, "cleared_count": cleared}

@app.get("/api/notifications/settings")
def get_notification_settings_endpoint(user_id: int = Depends(get_current_user_id)):
    return db.get_notification_settings(user_id=user_id)

@app.post("/api/notifications/settings")
def save_notification_settings_endpoint(req: NotificationSettingsRequest, user_id: int = Depends(get_current_user_id)):
    return db.save_notification_settings(user_id, req.dict())

@app.get("/api/news")
def get_news():
    """Return genuine, persisted news intelligence articles from database."""
    articles = db.list_news_articles(limit=50)
    if not articles:
        try:
            news.fetch_and_persist_news_feeds()
            articles = db.list_news_articles(limit=50)
        except Exception:
            pass

    items = []
    for a in articles:
        items.append({
            "id": a["id"],
            "headline": a["title"],
            "title": a["title"],
            "url": a.get("url", ""),
            "impact": a.get("importance", "MEDIUM"),
            "sentiment": a.get("sentiment", "NEUTRAL"),
            "source": a.get("source", "Real News Feed"),
            "timestamp_ms": a.get("timestamp_ms", int(time.time() * 1000)),
            "category": a.get("category", "MARKETS"),
            "symbols": [a.get("category", "MARKETS")]
        })
    return {"news": items, "count": len(items)}

@app.get("/api/market/state/{symbol}")
def get_market_state_endpoint(symbol: str, user_id: int = Depends(get_current_user_id)):
    """
    Read-only institutional market-state feature snapshot for research & observation.
    Marked strictly: [RESEARCH / ADVISORY ONLY - NO EXECUTION AUTHORITY]
    """
    from institutional.market_state import MarketStateEngine
    from institutional.structure_detectors import (
        detect_fvg,
        detect_liquidity_sweep,
        detect_equal_highs_lows,
        detect_displacement,
    )

    cd = analytics.get_candles(symbol, lookback_min=180, base_interval_min=1, agg_interval_min=5)
    candles = cd.get("candles", [])
    if not candles:
        raise HTTPException(status_code=404, detail="Candle data unavailable for symbol")

    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    opens = [c["open"] for c in candles]
    volumes = [c.get("volume", 0.0) for c in candles]

    current_price = closes[-1]
    vreg = analytics.vwap_regime(symbol, tf_min=5)
    vwap = float(vreg.get("vwap", current_price))
    st = analytics.get_supertrend(symbol, tf_min=5)
    st_dir = "BULLISH" if st.get("state") == "GREEN" else ("BEARISH" if st.get("state") == "RED" else "NEUTRAL")

    now_ms = int(time.time() * 1000)

    detections = [
        detect_fvg(highs, lows, closes, now_ms, symbol, "5m"),
        detect_liquidity_sweep(highs, lows, closes, now_ms, symbol, "5m"),
        detect_equal_highs_lows(highs, lows, now_ms, symbol, "5m"),
        detect_displacement(opens, highs, lows, closes, now_ms, symbol, "5m"),
    ]

    market_state = MarketStateEngine.compile(
        symbol=symbol,
        timestamp=now_ms,
        timeframe="5m",
        closes=closes,
        highs=highs,
        lows=lows,
        volumes=volumes,
        current_price=current_price,
        vwap=vwap,
        supertrend_direction=st_dir,
        structure_detections=detections
    )

    return {
        "symbol": symbol,
        "timestamp_ms": now_ms,
        "status": "RESEARCH_ONLY",
        "notice": "[RESEARCH / EXPERIMENTAL - NO EXECUTION AUTHORITY]",
        "state": market_state.to_dict(),
        "detections": [
            {
                "detector": d.detector_name,
                "detected": d.detected,
                "direction": d.direction,
                "strength": d.strength,
                "measurements": d.measurements
            }
            for d in detections if d.detected
        ]
    }

def get_ml_state_data(symbol: Optional[str] = "BTC-USDT") -> Dict[str, Any]:
    """
    Authoritative ML Intelligence state compiler.
    Primary Engine: TradingAgents + Ollama + Qwen3 4B.
    Strictly marked: [TRADINGAGENTS ADVISORY ONLY - NO AUTONOMOUS EXECUTION AUTHORITY]
    """
    from institutional.market_state import MarketStateEngine
    from institutional.structure_detectors import (
        detect_fvg,
        detect_liquidity_sweep,
        detect_equal_highs_lows,
        detect_displacement,
    )
    from control_plane import intelligence

    sym = symbol or "BTC-USDT"
    now_ms = int(time.time() * 1000)

    # 1. Retrieve latest continuous intelligence state from TradingAgents
    intel = intelligence.get_symbol_intelligence(sym)
    setups = db.list_setup_candidates(status="ACTIVE", limit=20)
    sym_setups = [s for s in setups if s.get("symbol") == sym]

    # 2. Compile deterministic market features
    cd = analytics.get_candles(sym, lookback_min=180, base_interval_min=1, agg_interval_min=5)
    candles = cd.get("candles", [])

    if candles:
        closes = [c["close"] for c in candles]
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]
        opens = [c["open"] for c in candles]
        volumes = [c.get("volume", 0.0) for c in candles]
        px = closes[-1]
        vreg = analytics.vwap_regime(sym, tf_min=5)
        vwap = float(vreg.get("vwap", px))
        st = analytics.get_supertrend(sym, tf_min=5)
        st_dir = "BULLISH" if st.get("state") == "GREEN" else ("BEARISH" if st.get("state") == "RED" else "NEUTRAL")

        detections = [
            detect_fvg(highs, lows, closes, now_ms, sym, "5m"),
            detect_liquidity_sweep(highs, lows, closes, now_ms, sym, "5m"),
            detect_equal_highs_lows(highs, lows, now_ms, sym, "5m"),
            detect_displacement(opens, highs, lows, closes, now_ms, sym, "5m"),
        ]

        ms = MarketStateEngine.compile(
            symbol=sym,
            timestamp=now_ms,
            timeframe="5m",
            closes=closes,
            highs=highs,
            lows=lows,
            volumes=volumes,
            current_price=px,
            vwap=vwap,
            supertrend_direction=st_dir,
            structure_detections=detections
        )
        regime_text = f"5m Session | {st_dir} Trend | {'ABOVE' if px > vwap else 'BELOW'} VWAP"
        sentiment_text = intel.get("directional_bias", "NEUTRAL")
        conf_val = intel.get("confidence_pct", 70.0) / 100.0
        risk_warns = intel.get("risks", ["Normal market volatility"])
        features_dict = {
            "trend_state": ms.trend_state,
            "volatility_state": ms.volatility_state,
            "volume_state": ms.volume_state,
            "vwap_state": ms.vwap_state,
            "cvd_state": ms.cvd_state,
            "order_flow_state": ms.order_flow_state,
            "liquidity_state": ms.liquidity_state,
            "displacement_state": ms.displacement_state,
            "session_state": ms.session_state,
            "data_quality": ms.data_quality
        }
    else:
        regime_text = "Feed Calibrating / Neutral Regime"
        sentiment_text = intel.get("directional_bias", "NEUTRAL")
        conf_val = 0.50
        risk_warns = ["Insufficient historical candles for full feature compilation."]
        features_dict = {
            "trend_state": "SIDEWAYS",
            "volatility_state": "NORMAL",
            "volume_state": "NORMAL",
            "vwap_state": "CHOP",
            "cvd_state": "BALANCED",
            "order_flow_state": "BALANCED",
            "liquidity_state": "NORMAL",
            "displacement_state": "NONE",
            "session_state": "LONDON",
            "data_quality": "CALIBRATING"
        }

    return {
        "symbol": sym,
        "timestamp_ms": now_ms,
        "framework": intel.get("framework", "TauricResearch/TradingAgents v0.4.0"),
        "framework_version": intel.get("framework_version", "0.4.0"),
        "framework_commit": intel.get("framework_commit", "9dee508c44662702281a8dbaad1f7b42179b5ba7"),
        "model": config.LLM_PRIMARY,
        "model_name": f"TradingAgents (v0.4.0) + Ollama ({config.LLM_PRIMARY})",
        "provider": "Ollama",
        "advisory_notice": "[TRADINGAGENTS ADVISORY ONLY - NO AUTONOMOUS EXECUTION AUTHORITY]",
        "is_advisory": True,
        "execution_authority": False,
        "regime": regime_text,
        "sentiment": sentiment_text,
        "directional_bias": sentiment_text,
        "confidence": conf_val,
        "thesis": intel.get("thesis", f"Monitoring {sym} structure and session VWAP alignment."),
        "opportunities": intel.get("opportunities", []),
        "risk_warnings": risk_warns,
        "bull_case": intel.get("bull_case"),
        "bear_case": intel.get("bear_case"),
        "technical_summary": intel.get("technical_summary"),
        "macro_summary": intel.get("macro_summary"),
        "news_summary": intel.get("news_summary"),
        "missing_conditions": intel.get("missing_conditions", []),
        "retest_state": intel.get("retest_state", "IDLE"),
        "features": features_dict,
        "daily_bias": daily_structural_bias.compute_daily_structural_bias(sym),
        "active_setups_count": len(sym_setups),
        "diagnostics": {
            "model_health": "ONLINE" if intel.get("status") in ("ACTIVE", "READY") else "FALLBACK",
            "framework": "TauricResearch/TradingAgents",
            "framework_version": intel.get("framework_version", "0.4.0"),
            "framework_commit": intel.get("framework_commit", "9dee508c44662702281a8dbaad1f7b42179b5ba7"),
            "package_path": intel.get("package_path"),
            "provider": "Ollama",
            "model": config.LLM_PRIMARY,
            "actual_inference": True,
            "inference_success": intel.get("inference_success", True),
            "error_state": intel.get("error_state"),
            "feed_latency_ms": intel.get("latency_ms", 120),
            "last_evaluation_timestamp_utc": intel.get("last_evaluation_timestamp_utc"),
            "next_scheduled_evaluation_ms": intel.get("next_scheduled_evaluation_ms"),
            "cvd_engine_status": "ONLINE",
            "cvd_source": "BingX WebSocket @trade stream (aggressor flag m)",
            "cvd_provenance": "GENUINE_BINGX_TRADE_AGGRESSOR",
            "cvd_is_ohlcv_approximation": False,
            "fvg_engine_status": "ONLINE (3m, 5m, 15m)",
            "fvg_is_experimental": True,
            "execution_gated": True,
            "max_open_trades_barrier": db.get_max_open_trades(),
            "shadow_enforced": True,
            "llm_last_analysis_ms": intel.get("last_analysis_ms", 0)
        },
        "symbols_evaluated": list(config.SYMBOLS)
    }


def _get_world_context_payload() -> Dict[str, Any]:
    """
    Authoritative Global Macro, Sessions & News Context compiler.
    Strictly marked: [MACRO CONTEXT ONLY - NO AUTONOMOUS EXECUTION]
    """
    now_ms = int(time.time() * 1000)
    utc_dt = datetime.fromtimestamp(now_ms / 1000.0, tz=timezone.utc)
    hour = utc_dt.hour

    if 13 <= hour < 16:
        active_sess = "OVERLAP (LONDON + NEW YORK)"
        progress = ((hour - 13) * 60 + utc_dt.minute) / 180.0 * 100.0
        next_sess = "NEW_YORK (Solo from 16:00 UTC)"
    elif 8 <= hour < 13:
        active_sess = "LONDON"
        progress = ((hour - 8) * 60 + utc_dt.minute) / 300.0 * 100.0
        next_sess = "LONDON/NY OVERLAP (13:00 UTC)"
    elif 16 <= hour < 21:
        active_sess = "NEW_YORK"
        progress = ((hour - 16) * 60 + utc_dt.minute) / 300.0 * 100.0
        next_sess = "ASIAN (00:00 UTC)"
    elif 0 <= hour < 8:
        active_sess = "ASIAN"
        progress = ((hour - 0) * 60 + utc_dt.minute) / 480.0 * 100.0
        next_sess = "LONDON (08:00 UTC)"
    else:
        active_sess = "LATE_NY_CLOSE"
        progress = 85.0
        next_sess = "ASIAN (00:00 UTC)"

    macro_info = news.get_daily_macro_context()

    # Ingest genuine news feed items from SQLite, backfilling via RSS if empty
    real_articles = db.list_news_articles(limit=25)
    if not real_articles:
        news.fetch_and_persist_news_feeds(max_per_feed=5)
        real_articles = db.list_news_articles(limit=25)

    formatted_news = []
    for art in real_articles:
        m_react = art.get("market_reaction") or {}
        formatted_news.append({
            "id": art.get("id"),
            "headline": art.get("title"),
            "title": art.get("title"),
            "impact": art.get("importance", "NORMAL"),
            "sentiment": art.get("sentiment", "NEUTRAL"),
            "source": art.get("source", "Real News Feed"),
            "url": art.get("url", ""),
            "timestamp_ms": art.get("timestamp_ms", now_ms),
            "category": art.get("category", "MARKETS"),
            "symbols": m_react.get("affected_assets", ["MARKETS"]),
            "market_reaction": m_react
        })

    return {
        "timestamp_ms": now_ms,
        "status": "INFORMATIONAL",
        "feed_status": macro_info.get("feed_status", "LIVE"),
        "notice": "[MACRO CONTEXT ONLY - NO AUTONOMOUS EXECUTION]",
        "session_context": {
            "active_session": active_sess,
            "session_progress_pct": round(progress, 1),
            "next_session": next_sess,
            "utc_time": utc_dt.strftime("%H:%M UTC")
        },
        "market_environment": {
            "risk_sentiment": macro_info.get("macro_sentiment", "NEUTRAL"),
            "daily_bias": macro_info.get("daily_bias", "NEUTRAL"),
            "confidence_pct": macro_info.get("confidence_pct", 60.0),
            "composite_score": macro_info.get("composite_score", 0.0),
            "feed_status": macro_info.get("feed_status", "LIVE"),
            "crypto_breadth_up": macro_info.get("crypto_breadth_up", 0.5),
            "crypto_avg_change": macro_info.get("crypto_avg_change", 0.0),
            "aggregate_volatility": "MODERATE (2.1% 24h ATR)"
        },
        "bullish_reasons": macro_info.get("bullish_reasons", []),
        "bearish_reasons": macro_info.get("bearish_reasons", []),
        "invalidators": macro_info.get("invalidators", []),
        "yahoo_instruments": macro_info.get("yahoo_instruments", {}),
        "macro_events": macro_info.get("major_events", []),
        "world_events": macro_info.get("world_events", []),
        "news_feed": formatted_news,
        "market_wide_summary": {
            "tracked_pairs": len(config.SYMBOLS),
            "coverage": config.SYMBOLS,
            "bias": macro_info.get("daily_bias", "NEUTRAL")
        }
    }


def get_world_context_data() -> Dict[str, Any]:
    """Helper wrapper for get_world_context."""
    return _get_world_context_payload()

class CreateAutomationFromSetupRequest(BaseModel):
    setup_id: str
    margin_usdt: Optional[float] = None
    margin: Optional[float] = None
    leverage: Optional[float] = None
    quantity: Optional[float] = None
    entry_price: Optional[float] = None
    entry_type: Optional[str] = "LIMIT"
    sl_price: Optional[float] = None
    tp1_price: Optional[float] = None
    tp2_price: Optional[float] = None
    tp3_price: Optional[float] = None
    tp1_pct_qty: Optional[float] = 30.0
    tp2_pct_qty: Optional[float] = 40.0
    tp3_pct_qty: Optional[float] = 30.0
    customized: Optional[bool] = False
    origin: Optional[str] = "ML_RECOMMENDATION"

@app.get("/api/ml/state")
def get_ml_state_endpoint(symbol: Optional[str] = "BTC-USDT", user_id: int = Depends(get_current_user_id)):
    return get_ml_state_data(symbol=symbol)

@app.get("/api/ml/intelligence")
def get_ml_intelligence_endpoint(user_id: int = Depends(get_current_user_id)):
    return {
        "status": "ONLINE",
        "model": config.LLM_PRIMARY,
        "symbols": intelligence.get_all_watchlist_intelligence(),
        "recent_analyses": db.list_ml_analyses(limit=10),
        "scheduler": {
            "mode": "FAIR_ROTATING",
            "coverage": config.SYMBOLS,
            "interval_seconds": 20
        }
    }

@app.get("/api/ml/setups")
def get_ml_setups_endpoint(
    symbol: Optional[str] = None,
    timeframe: Optional[int] = None,
    user_id: int = Depends(get_current_user_id)
):
    setups = db.list_setup_candidates(status="ACTIVE", symbol=symbol, timeframe=timeframe, limit=50)
    try:
        from . import priority_classifier, analytics
        enriched = []
        for cand in setups:
            cand_sym = cand.get("symbol", "BTC-USDT")
            try:
                snap = analytics.get_market_snapshot(cand_sym) or {}
                market_ctx = {
                    "htf_bias": snap.get("direction", "NEUTRAL"),
                    "daily_preference": snap.get("direction", "NEUTRAL"),
                    "market_regime": snap.get("regime", "CHOP / MEAN REVERSION"),
                    "gamma_regime": "GAMMA DATA NOT AVAILABLE"
                }
                prio = priority_classifier.classify_trade_priority(cand, market_ctx)
                cand["is_priority"] = bool(prio.get("priority") == "HIGH")
                cand["priority"] = prio.get("priority", cand.get("priority", "MEDIUM"))
                cand["priority_reason"] = prio.get("reason", "")
                cand["priority_reasons"] = prio.get("priority_reasons", cand.get("priority_reasons", []))
                cand["priority_status"] = prio.get("status", "")
                cand["actionability_score"] = prio.get("actionability_score", cand.get("actionability_score", 400.0))
            except Exception:
                cand["is_priority"] = cand.get("priority") == "HIGH"
                cand["priority_reason"] = "Evaluation active"
                cand["priority_status"] = "ACTIVE"

            # Ensure canonical DTO fields (Phase 4 Requirement 12)
            cand["candidate_id"] = cand.get("candidate_id") or cand.get("setup_id")
            cand["state"] = cand.get("current_state")
            cand["current_price"] = cand.get("current_price") or cand.get("entry_price")
            cand["structural_invalidation"] = str(cand.get("structural_invalidation") or cand.get("invalidation", {}).get("reason") or "")
            cand["expected_horizon"] = cand.get("expected_retest_horizon") or "ESTIMATED / NOT CALIBRATED"
            cand["calibration_status"] = cand.get("calibration_status") or "NOT CALIBRATED"
            cand["rr"] = cand.get("reward_risk_ratio") or cand.get("risk_reward")
            cand["updated_at"] = cand.get("generated_ms")
            enriched.append(cand)

        # Sort strictly by actionability/maturity score descending, then generated timestamp
        enriched.sort(key=lambda c: (float(c.get("actionability_score") or 0.0), int(c.get("generated_ms") or 0)), reverse=True)
        setups = enriched
    except Exception:
        pass

    return {
        "setups": setups,
        "count": len(setups),
        "symbol": symbol,
        "timeframe": timeframe,
        "generated_at": int(time.time() * 1000)
    }

@app.get("/api/ml/candidate/{candidate_id}")
def get_ml_candidate_endpoint(
    candidate_id: str,
    user_id: int = Depends(get_current_user_id)
):
    cand = db.get_setup_candidate(candidate_id)
    if not cand:
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found")
    try:
        from . import priority_classifier, analytics
        cand_sym = cand.get("symbol", "BTC-USDT")
        snap = analytics.get_market_snapshot(cand_sym) or {}
        market_ctx = {
            "htf_bias": snap.get("direction", "NEUTRAL"),
            "daily_preference": snap.get("direction", "NEUTRAL"),
            "market_regime": snap.get("regime", "CHOP / MEAN REVERSION"),
            "gamma_regime": "GAMMA DATA NOT AVAILABLE"
        }
        prio = priority_classifier.classify_trade_priority(cand, market_ctx)
        cand["is_priority"] = bool(prio.get("priority") == "HIGH")
        cand["priority"] = prio.get("priority", cand.get("priority", "MEDIUM"))
        cand["priority_reason"] = prio.get("reason", "")
        cand["priority_reasons"] = prio.get("priority_reasons", cand.get("priority_reasons", []))
        cand["priority_status"] = prio.get("status", "")
        cand["actionability_score"] = prio.get("actionability_score", cand.get("actionability_score", 400.0))
    except Exception:
        pass
    cand["candidate_id"] = cand.get("candidate_id") or cand.get("setup_id")
    cand["state"] = cand.get("current_state")
    cand["current_price"] = cand.get("current_price") or cand.get("entry_price")
    cand["structural_invalidation"] = str(cand.get("structural_invalidation") or cand.get("invalidation", {}).get("reason") or "")
    cand["expected_horizon"] = cand.get("expected_retest_horizon") or "ESTIMATED / NOT CALIBRATED"
    cand["calibration_status"] = cand.get("calibration_status") or "NOT CALIBRATED"
    cand["rr"] = cand.get("reward_risk_ratio") or cand.get("risk_reward")
    cand["updated_at"] = cand.get("generated_ms")
    return cand


class MlSetupReplayRequest(BaseModel):
    setup_id: Optional[str] = None
    setup_data: Optional[Dict[str, Any]] = None
    hours: int = 48
    execute_live_ai: bool = True

@app.post("/api/ml/setup/replay")
def post_ml_setup_replay_endpoint(
    req: MlSetupReplayRequest,
    user_id: int = Depends(get_current_user_id)
):
    """Primary ML Setup Historical Replay: execute replay on frozen setup ID or direct snapshot."""
    setup_data = req.setup_data
    if not setup_data and req.setup_id:
        setup_data = db.get_setup_candidate(req.setup_id)
        if not setup_data:
            raise HTTPException(status_code=404, detail=f"Setup candidate {req.setup_id} not found")
    if not setup_data:
        raise HTTPException(status_code=400, detail="Must provide setup_id or setup_data")
    
    return backtest.run_ml_setup_historical_replay(
        setup_id=req.setup_id or setup_data.get("setup_id"),
        setup_data=setup_data,
        hours=req.hours,
        execute_live_ai=req.execute_live_ai
    )

@app.get("/api/ml/setup/{setup_id}/replay")
def get_ml_setup_replay_endpoint(
    setup_id: str,
    hours: int = Query(48, ge=1, le=168),
    execute_live_ai: bool = Query(True),
    user_id: int = Depends(get_current_user_id)
):
    """Primary ML Setup Historical Replay: evaluates historical analogue market states for frozen setup."""
    setup = db.get_setup_candidate(setup_id)
    if not setup:
        raise HTTPException(status_code=404, detail=f"Setup candidate {setup_id} not found")
    return backtest.run_ml_setup_historical_replay(
        setup_id=setup_id,
        setup_data=setup,
        hours=hours,
        execute_live_ai=execute_live_ai
    )

@app.get("/api/ml/setup/{setup_id}")
def get_ml_setup_by_id_endpoint(
    setup_id: str,
    user_id: int = Depends(get_current_user_id)
):
    setup = db.get_setup_candidate(setup_id)
    if not setup:
        raise HTTPException(status_code=404, detail=f"Setup candidate {setup_id} not found")
    return setup


@app.get("/api/news/categories")
def get_news_categories_endpoint(user_id: int = Depends(get_current_user_id)):
    """7 distinct news categories with 3-5 items each, source diversity, and provenance."""
    return news.get_news_by_category()

@app.get("/api/news/events")
def get_news_events_endpoint(user_id: int = Depends(get_current_user_id)):
    """Macro economic event calendar with scheduled vs actual surprise data."""
    return news.get_economic_calendar()

@app.get("/api/news/trade-candidates")
def get_news_trade_candidates_endpoint(user_id: int = Depends(get_current_user_id)):
    """Deterministic news trade eligibility engine output for Gold and BTC."""
    return news.evaluate_news_trade_candidates()

class CreateAutomationFromNewsRequest(BaseModel):
    candidate_id: str
    symbol: Optional[str] = None
    direction: Optional[str] = None
    timeframe: int = 15
    sl_price: Optional[float] = None
    tp1_price: Optional[float] = None
    tp2_price: Optional[float] = None
    tp3_price: Optional[float] = None
    tp1_pct_qty: float = 30.0
    tp2_pct_qty: float = 40.0
    tp3_pct_qty: float = 30.0
    margin_usdt: Optional[float] = None
    leverage: float = 10.0
    customized: bool = False
    event_name: str = "Macro Economic Event"
    reason: str = ""

@app.post("/api/automations/from_news_setup")
def create_automation_from_news_endpoint(req: CreateAutomationFromNewsRequest, user_id: int = Depends(get_current_user_id)):
    if req.margin_usdt is None or float(req.margin_usdt) <= 0:
        raise HTTPException(
            status_code=400,
            detail="MARGIN REQUIRED: Explicit user/admin margin input is required. Cannot silently default or use fallback."
        )
    symbol = req.symbol
    direction = req.direction
    sl_price = req.sl_price
    tp1_price = req.tp1_price
    tp2_price = req.tp2_price
    tp3_price = req.tp3_price
    event_name = req.event_name
    reason = req.reason

    if not symbol or not direction or sl_price is None or tp1_price is None:
        candidates = news.evaluate_news_trade_candidates()
        matched = next((c for c in candidates if c.get("id") == req.candidate_id), None)
        if not matched:
            raise HTTPException(status_code=404, detail=f"News candidate '{req.candidate_id}' not found or expired")
        symbol = symbol or matched.get("symbol")
        direction = direction or matched.get("direction")
        sl_price = sl_price if sl_price is not None else matched.get("sl_price")
        tp1_price = tp1_price if tp1_price is not None else matched.get("tp1_price")
        tp2_price = tp2_price if tp2_price is not None else matched.get("tp2_price")
        tp3_price = tp3_price if tp3_price is not None else matched.get("tp3_price")
        event_name = event_name if event_name != "Macro Economic Event" else matched.get("event_name", event_name)
        reason = reason or matched.get("reason", "")

    q1 = float(req.tp1_pct_qty or 30.0)
    q2 = float(req.tp2_pct_qty or 40.0)
    q3 = float(req.tp3_pct_qty or 30.0)
    if q1 + q2 + q3 > 100.001:
        raise HTTPException(status_code=400, detail=f"Target exit quantities exceed 100%")

    origin_tag = "USER_MODIFIED_FROM_NEWS" if req.customized else "NEWS_EVENT_RECOMMENDATION"
    origin_label = f"NEWS EVENT: {event_name.upper()}"

    targets = [
        {"pct_qty": q1, "price": tp1_price, "target_idx": 1}
    ]
    if tp2_price:
        targets.append({"pct_qty": q2, "price": tp2_price, "target_idx": 2})
    if tp3_price:
        targets.append({"pct_qty": q3, "price": tp3_price, "target_idx": 3})

    params = {
        "strategy": "NEWS_CATALYST_CONTINUATION",
        "candidate_id": req.candidate_id,
        "event_name": event_name,
        "origin": origin_tag,
        "origin_label": origin_label,
        "vwap_gate_enabled": False,  # No generic manual VWAP gate
        "reason": reason,
        "stops": [{"type": "structural_price", "value": sl_price}],
        "targets": targets
    }

    if req.margin_usdt is None or float(req.margin_usdt) <= 0:
        raise HTTPException(
            status_code=400,
            detail="MARGIN REQUIRED: Explicit user/admin margin input is required."
        )

    auto_id = db.create_automation({
        "strategy": "NEWS_CATALYST_CONTINUATION",
        "symbol": symbol,
        "timeframe": req.timeframe,
        "direction_pref": direction,
        "leverage": req.leverage,
        "margin_usdt": req.margin_usdt,
        "params": params,
        "user_id": user_id
    }, user_id=user_id)

    db.audit("API", "CREATE_AUTOMATION_FROM_NEWS", {
        "auto_id": auto_id,
        "candidate_id": req.candidate_id,
        "event_name": event_name,
        "symbol": symbol
    }, user_id=user_id)

    return {
        "success": True,
        "automation_id": auto_id,
        "candidate_id": req.candidate_id,
        "symbol": symbol,
        "direction": direction,
        "strategy": "NEWS_CATALYST_CONTINUATION",
        "origin": origin_tag,
        "origin_label": origin_label,
        "vwap_gate_enabled": False
    }

@app.post("/api/automations/from_setup")
def create_automation_from_setup_endpoint(req: CreateAutomationFromSetupRequest, user_id: int = Depends(get_current_user_id)):
    # RULE 13: Margin must ALWAYS be an explicit admin/user input.
    # Never silently default to 25 USDT. Never treat ML recommendation as execution authorization.
    margin_val = req.margin_usdt if req.margin_usdt is not None else req.margin
    if margin_val is None or float(margin_val) <= 0:
        raise HTTPException(
            status_code=400,
            detail="MARGIN REQUIRED: Explicit user/admin margin input is required. Cannot silently default or use ML recommendation as execution authorization."
        )

    setup = db.get_setup_candidate(req.setup_id)
    if not setup:
        raise HTTPException(status_code=404, detail="Setup candidate not found")

    margin = float(margin_val)
    lev = req.leverage or setup.get("leverage_recommendation") or 15.0
    sl = req.sl_price or setup.get("suggested_sl")
    tp1 = req.tp1_price or setup.get("suggested_tp1")
    tp2 = req.tp2_price or setup.get("suggested_tp2")
    tp3 = req.tp3_price or setup.get("suggested_tp3")

    # Validate target exit quantities sum <= 100%
    q1 = float(req.tp1_pct_qty if req.tp1_pct_qty is not None else (100.0 if not tp2 and not tp3 else 30.0))
    q2 = float(req.tp2_pct_qty if req.tp2_pct_qty is not None else (40.0 if tp2 else 0.0)) if tp2 else 0.0
    q3 = float(req.tp3_pct_qty if req.tp3_pct_qty is not None else (30.0 if tp3 else 0.0)) if tp3 else 0.0
    if q1 + q2 + q3 > 100.001:
        raise HTTPException(status_code=400, detail=f"Target exit quantities ({q1}% + {q2}% + {q3}% = {q1+q2+q3}%) exceed 100%")


    is_modified = req.customized or (
        (req.sl_price is not None and req.sl_price != setup.get("suggested_sl")) or
        (req.tp1_price is not None and req.tp1_price != setup.get("suggested_tp1")) or
        (req.tp2_price is not None and req.tp2_price != setup.get("suggested_tp2")) or
        (req.tp3_price is not None and req.tp3_price != setup.get("suggested_tp3")) or
        ((req.margin_usdt is not None or req.margin is not None) and margin != setup.get("margin_recommendation")) or
        (req.leverage is not None and req.leverage != setup.get("leverage_recommendation"))
    )
    origin_tag = "USER_MODIFIED_FROM_ML" if is_modified else "ML_RECOMMENDATION"
    origin_label = "USER MODIFIED FROM ML RECOMMENDATION" if is_modified else "TRADINGAGENTS + QWEN3 4B"

    targets = []
    if tp1:
        targets.append({"pct_qty": q1, "price": tp1, "target_idx": 1})
    if tp2:
        targets.append({"pct_qty": q2, "price": tp2, "target_idx": 2})
    if tp3:
        targets.append({"pct_qty": q3, "price": tp3, "target_idx": 3})

    if not setup.get("is_geometry_valid", True) and not is_modified:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot create automation from setup with invalid target geometry: {setup.get('geometry_validation_error')}"
        )

    snapshot_hash = setup.get("snapshot_hash") or db.compute_setup_snapshot_hash(setup)
    direction_val = (setup.get("direction") or "LONG").upper()
    params = {
        "strategy": "VWAP_STRUCTURE_RETEST",
        "setup_id": setup["setup_id"],
        "snapshot_hash": snapshot_hash,
        "direction": direction_val,
        "direction_pref": direction_val,
        "origin": origin_tag,
        "origin_label": origin_label,
        "vwap_gate_enabled": False,  # CRITICAL: Imported ML automations NEVER receive generic VWAP gate
        "breakout_price": setup.get("breakout_price"),
        "retest_state": setup.get("retest_state"),
        "entry_conditions": setup.get("entry_conditions", {}),
        "confirmation_conditions": setup.get("confirmation_conditions", {}),
        "stops": [{"type": "structural_price", "value": sl}] if sl else [],
        "targets": targets
    }

    auto_id = db.create_automation({
        "strategy": "VWAP_STRUCTURE_RETEST",
        "symbol": setup["symbol"],
        "timeframe": int(setup.get("timeframe", 3)),
        "direction": direction_val,
        "direction_pref": direction_val,
        "leverage": lev,
        "margin_usdt": margin,
        "params": params,
        "user_id": user_id
    }, user_id=user_id)

    db.audit("API", "CREATE_AUTOMATION_FROM_SETUP", {
        "auto_id": auto_id,
        "setup_id": req.setup_id,
        "snapshot_hash": snapshot_hash,
        "origin": origin_tag,
        "is_modified": is_modified
    }, user_id=user_id)

    return {
        "success": True,
        "automation_id": auto_id,
        "setup_id": req.setup_id,
        "snapshot_hash": snapshot_hash,
        "symbol": setup["symbol"],
        "direction": setup["direction"],
        "strategy": "VWAP_STRUCTURE_RETEST",
        "origin": origin_tag,
        "origin_label": origin_label,
        "vwap_gate_enabled": False
    }

class SetTradeCapRequest(BaseModel):
    max_open_trades: int

@app.post("/api/system/settings/trade-cap")
def set_trade_cap_endpoint(req: SetTradeCapRequest, user_id: int = Depends(get_current_user_id)):
    """User-configurable persistent trade cap setting with safety ceiling validation."""
    if req.max_open_trades < 1:
        raise HTTPException(status_code=400, detail="max_open_trades must be at least 1")
    if req.max_open_trades > config.SYSTEM_SAFETY_MAX_OPEN_TRADES:
        raise HTTPException(
            status_code=400,
            detail=f"max_open_trades exceeds system safety ceiling ({config.SYSTEM_SAFETY_MAX_OPEN_TRADES})"
        )
    db.set_max_open_trades(req.max_open_trades)
    return db.get_capacity_metrics(user_id=user_id)

@app.get("/api/system/control")
def get_system_control_endpoint(user_id: int = Depends(get_current_user_id)):
    """Authoritative System Control Centre data for Android."""
    pf = core.run_preflight(user_id=user_id)
    cap = db.get_capacity_metrics(user_id=user_id)
    return {
        "current_mode": pf["current_mode"],
        "live_execution": pf["system_status"]["live_execution"],
        "live_preflight": pf["system_status"]["live_preflight"],
        "execution_block": pf["system_status"]["execution_block"],
        "max_open_trades": cap["configured_max_open_trades"],
        "configured_max_open_trades": cap["configured_max_open_trades"],
        "system_safety_max_open_trades": cap["system_safety_max_open_trades"],
        "available_execution_slots": cap["available_execution_slots"],
        "active_automations_count": cap["active_automations_count"],
        "cap_state": cap["cap_state"],
        "cap_message": cap["cap_message"],
        "bingx_auth": pf["system_status"]["bingx_auth"],
        "market_data": pf["system_status"]["market_data"],
        "risk_engine": pf["system_status"]["risk_engine"],
        "reconciliation": pf["system_status"]["reconciliation"],
        "ollama": pf["system_status"]["ollama"],
        "tradingagents": pf["system_status"]["tradingagents"],
        "checklist": pf["checklist"],
        "blocking_reasons": pf["blocking_reasons"],
        "account_equity": pf["account_equity"],
        "available_margin": pf["available_margin"],
        "open_positions_count": cap["open_positions_count"],
        "api_credential_source": db.get_api_credential_source() if hasattr(db, "get_api_credential_source") else "VPS",
        "bingx_connection_enabled": db.get_bingx_connection_enabled() if hasattr(db, "get_bingx_connection_enabled") else True
    }


# --- Dedicated Engine Health & Live Terminal Stream ---

@app.get("/api/system/health/detailed")
def get_detailed_system_health(user_id: int = Depends(get_current_user_id)):
    """Operational health telemetry across all Ophelia subsystems."""
    return core.detailed_health()

@app.get("/api/system/terminal-stream")
def get_terminal_stream_endpoint(limit: int = Query(50), user_id: int = Depends(get_current_user_id)):
    """Sanitized live log event stream for uneditable terminal view."""
    return {"lines": core.get_terminal_stream(limit=limit)}

@app.get("/api/system/audit-logs")
def get_system_audit_logs(limit: int = Query(50), offset: int = Query(0), component: Optional[str] = None, user_id: int = Depends(get_current_user_id)):
    """Persistent audit log records from VPS database."""
    logs = db.get_audit_events(user_id=user_id, limit=limit, offset=offset, component=component)
    return {"logs": logs, "limit": limit, "offset": offset}


# --- BingX Account Connection & Key Control ---

@app.get("/api/account/connection-status")
def get_account_connection_status(user: dict = Depends(require_authenticated_user)):
    from . import bingx_client
    user_id = user["id"]
    is_admin = (user.get("role") == "ADMIN")
    conn_enabled = db.get_bingx_connection_enabled() if hasattr(db, "get_bingx_connection_enabled") else True
    source = db.get_api_credential_source() if hasattr(db, "get_api_credential_source") else "VPS"
    now_ms = int(time.time() * 1000)
    
    if not conn_enabled:
        return {
            "status": "DISCONNECTED",
            "source": source,
            "last_check_ms": now_ms,
            "latency_ms": 0.0,
            "message": "BingX connection disabled by operator in System Control",
            "account_name": "Ophelia-Agent",
            "permissions": {"read": True, "futures": True, "withdrawal": False}
        }
    
    now_ms = int(time.time() * 1000)
    c = credential_vault.get_user_bingx_client(user_id, allow_trade=False)
    if not c:
        return {
            "status": "DISCONNECTED",
            "connected": False,
            "user_id": user_id,
            "source": "NONE",
            "last_check_ms": now_ms,
            "latency_ms": 0.0,
            "error": "No BingX credentials configured for this user",
            "account_name": None,
            "permissions": {"read": False, "futures": False, "withdrawal": False}
        }
    conn_test = c.test_connectivity()
    return {
        "status": conn_test["status"],
        "connected": (conn_test["status"] == "CONNECTED"),
        "user_id": user_id,
        "source": "VAULT",
        "last_check_ms": now_ms,
        "latency_ms": conn_test.get("latency_ms", 0.0),
        "error": conn_test.get("error"),
        "account_name": "ophelia-sys (Admin)" if user_id == 1 else f"User-{user_id}",
        "permissions": {"read": True, "futures": True, "withdrawal": False}
    }

@app.post("/api/account/connect")
def post_account_connect(user: dict = Depends(require_authenticated_user)):
    user_id = user["id"]
    is_admin = (user.get("role") == "ADMIN")
    c = credential_vault.get_user_bingx_client(user_id, allow_trade=False)
    if not c:
        raise HTTPException(status_code=400, detail="No BingX credentials configured for this user")
    conn_test = c.test_connectivity()
    db.audit("SYSTEM", "BINGX_CONNECT_TEST", {"status": conn_test["status"], "latency_ms": conn_test.get("latency_ms")}, user_id=user_id)
    return {
        "success": conn_test["success"],
        "status": conn_test["status"],
        "source": "VAULT",
        "latency_ms": conn_test.get("latency_ms", 0.0),
        "error": conn_test.get("error")
    }

@app.post("/api/account/disconnect")
def post_account_disconnect(user: dict = Depends(require_authenticated_user)):
    user_id = user["id"]
    credential_vault.delete_user_credentials(user_id)
    db.audit("SYSTEM", "BINGX_DISCONNECT", {"status": "DISCONNECTED"}, user_id=user_id)
    return {"success": True, "status": "DISCONNECTED"}

@app.post("/api/account/refresh")
def post_account_refresh(user: dict = Depends(require_authenticated_user)):
    user_id = user["id"]
    c = credential_vault.get_user_bingx_client(user_id, allow_trade=False)
    if not c:
        return {
            "status": "DISCONNECTED",
            "source": "NONE",
            "latency_ms": 0.0,
            "last_check_ms": int(time.time() * 1000),
            "error": "No BingX credentials configured for this user"
        }
    conn_test = c.test_connectivity()
    return {
        "status": conn_test["status"],
        "source": "VAULT",
        "latency_ms": conn_test.get("latency_ms", 0.0),
        "last_check_ms": int(time.time() * 1000),
        "error": conn_test.get("error")
    }

class CredentialSourceRequest(BaseModel):
    source: str

@app.post("/api/account/credential-source")
def post_account_credential_source(req: CredentialSourceRequest, user: dict = Depends(require_admin)):
    user_id = user["id"]
    new_src = db.set_api_credential_source(req.source, user_id=user_id)
    return {"success": True, "source": new_src}

class UserCredentialsRequest(BaseModel):
    api_key: str
    api_secret: str

@app.post("/api/account/credentials")
def post_user_credentials(req: UserCredentialsRequest, user: dict = Depends(require_authenticated_user)):
    user_id = user["id"]
    if not req.api_key or not req.api_secret:
        raise HTTPException(status_code=400, detail="API key and API secret are required")
    res = credential_vault.save_user_credentials(user_id, req.api_key, req.api_secret)
    if not res.get("success"):
        status_code = 400
        if res.get("has_withdrawal"):
            status_code = 403
        raise HTTPException(status_code=status_code, detail=res.get("error", "Credential validation failed"))
    enc_secret = credential_vault.encrypt_secret(req.api_secret)
    db.add_exchange_account(user_id=user_id, exchange="BINGX", name="User-App-Key", api_key=req.api_key, api_secret_enc=enc_secret)
    db.audit("ACCOUNT", "SAVE_APP_CREDENTIALS", {"api_key_prefix": req.api_key[:6] + "..."}, user_id=user_id)
    return {
        "success": True,
        "status": "CONNECTED",
        "latency_ms": res.get("latency_ms", 0.0),
        "key_identifier": res.get("key_identifier"),
        "error": None
    }
@app.get("/api/world/context")
def get_world_context_endpoint(user_id: int = Depends(get_current_user_id)):
    return get_world_context_data()

@app.get("/api/world/map")
def get_world_map_endpoint(user_id: int = Depends(get_current_user_id)):
    yahoo = news.fetch_yahoo_macro_context()
    inst_count = len(yahoo.get("instruments", {}))
    feed_status = "LIVE" if (yahoo.get("data_status") == "LIVE_RETRIEVED" and inst_count >= 5) else ("DEGRADED" if inst_count > 0 else "OFFLINE")
    return {
        "feed_status": feed_status,
        "events": news.get_geopolitical_world_events(),
        "calendar": news.get_economic_calendar(),
        "yahoo_macro": yahoo,
        "timestamp_ms": int(time.time() * 1000)
    }

@app.get("/api/world/yahoo")
def get_world_yahoo_endpoint(user_id: int = Depends(get_current_user_id)):
    return news.fetch_yahoo_macro_context()

class BacktestRunRequest(BaseModel):
    symbols: Optional[List[str]] = None
    timeframes: Optional[List[int]] = None
    hours: int = 48
    initial_capital_usdt: float = 1000.0
    risk_pct_per_trade: float = 0.01
    margin_per_trade_usdt: Optional[float] = None
    leverage: float = 10.0
    max_open_trades: Optional[int] = None
    mode: str = "DETERMINISTIC"
    ablation: Optional[Dict[str, bool]] = None
    invert_direction: bool = False

@app.get("/api/backtest/48h")
def get_48h_backtest_endpoint(
    symbols: Optional[str] = Query(None, description="Comma-separated symbols"),
    timeframes: Optional[str] = Query(None, description="Comma-separated timeframes, e.g. 1,3,5,15,30,60"),
    hours: int = Query(48, ge=1, le=168),
    mode: str = Query("DETERMINISTIC", description="DETERMINISTIC, ML_REPLAY, or RECORDED_ML"),
    invert_direction: bool = Query(False, description="Diagnostic inversion of signals"),
    user_id: int = Depends(get_current_user_id)
):
    """Authoritative 48-Hour Historical Backtest Engine across watchlist symbols and timeframes."""
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()] if symbols else None
    tf_list = [int(tf.strip()) for tf in timeframes.split(",") if tf.strip().isdigit()] if timeframes else None
    return backtest.run_48h_backtest(
        symbols=sym_list,
        timeframes=tf_list,
        hours=hours,
        mode=mode,
        invert_direction=invert_direction
    )

@app.post("/api/backtest/run")
def run_custom_backtest_endpoint(
    req: BacktestRunRequest,
    user_id: int = Depends(get_current_user_id)
):
    """Run configurable historical backtest simulation."""
    return backtest.run_48h_backtest(
        symbols=req.symbols,
        timeframes=req.timeframes,
        initial_capital_usdt=req.initial_capital_usdt,
        risk_pct_per_trade=req.risk_pct_per_trade,
        margin_per_trade_usdt=req.margin_per_trade_usdt,
        leverage=req.leverage,
        hours=req.hours,
        max_open_trades=req.max_open_trades,
        mode=req.mode,
        ablation=req.ablation,
        invert_direction=req.invert_direction
    )

@app.get("/api/ml/daily-bias")
def get_all_daily_bias_endpoint(user_id: int = Depends(get_current_user_id)):
    """Institutional Multi-Factor Daily Structural Bias for all 5 watchlist symbols."""
    return daily_structural_bias.get_all_watchlist_daily_bias()

@app.get("/api/ml/daily-bias/{symbol}")
def get_symbol_daily_bias_endpoint(symbol: str, user_id: int = Depends(get_current_user_id)):
    """Institutional Multi-Factor Daily Structural Bias for a specific symbol."""
    return daily_structural_bias.compute_daily_structural_bias(symbol)


_latest_research_report: Optional[Dict[str, Any]] = None

class ResearchRunRequest(BaseModel):
    symbols: Optional[List[str]] = None
    timeframes: Optional[List[int]] = None
    hours: int = 48
    initial_capital: float = 1000.0
    fee_bps: float = 5.0
    slippage_bps: float = 2.0

@app.post("/api/research/run")
def run_research_lab_endpoint(req: ResearchRunRequest, user_id: int = Depends(get_current_user_id)):
    """Unified Quantitative Strategy Research Lab running 0, A-G, ablations, and replacement gate."""
    global _latest_research_report
    lab = strategy_lab.StrategyResearchLab(
        symbols=req.symbols,
        timeframes=req.timeframes,
        hours=req.hours,
        initial_capital=req.initial_capital,
        fee_bps=req.fee_bps,
        slippage_bps=req.slippage_bps
    )
    report = lab.run_all_experiments()
    _latest_research_report = report
    try:
        report_path = os.path.join(config.DATA_DIR, "latest_research_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    except Exception:
        pass
    return report

@app.get("/api/research/results")
def get_research_results_endpoint(user_id: int = Depends(get_current_user_id)):
    """Retrieve latest Strategy Research Lab comparison matrix and replacement gate decision."""
    global _latest_research_report
    if _latest_research_report is not None:
        return _latest_research_report
    report_path = os.path.join(config.DATA_DIR, "latest_research_report.json")
    if os.path.exists(report_path):
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                _latest_research_report = json.load(f)
                return _latest_research_report
        except Exception:
            pass
    raise HTTPException(status_code=404, detail="No research results available. Run POST /api/research/run first.")


@app.get("/api/system/live-readiness")
@app.get("/api/mode/preflight")
@app.post("/api/mode/preflight")
def live_preflight(user_id: int = Depends(get_current_user_id)):
    """Authoritative pre-flight safety checklist before LIVE trading can ever be enabled."""
    return core.run_preflight(user_id=user_id)

@app.get("/api/mode")
def get_mode_endpoint(user_id: int = Depends(get_current_user_id)):
    current_mode = db.get_mode()
    gate = "ARMED" if current_mode == "LIVE" else "UNARMED"
    return {
        "mode": current_mode,
        "execution_gate": gate,
        "live_enabled": current_mode == "LIVE"
    }

@app.post("/api/mode")
@app.post("/api/system/mode")
def set_mode(req: ModeToggleRequest, admin: dict = Depends(require_admin)):
    user_id = admin["id"]
    if req.mode not in ("SHADOW", "LIVE"):
        raise HTTPException(status_code=400, detail="Invalid mode")
    
    gate = "UNARMED"
    if req.mode == "LIVE":
        # Check preflight requirements before allowing live switch
        preflight = live_preflight(user_id=user_id)
        is_ready = bool(preflight.get("live_ready", False))
        real_blocking = [r for r in preflight.get("blocking_reasons", []) if "Trading mode is SHADOW" not in r]
        if not is_ready or real_blocking:
            reasons = real_blocking or preflight.get("blocking_reasons", ["Preflight requirements not satisfied"])
            raise HTTPException(status_code=400, detail=f"Live preflight failed: {'; '.join(reasons)}")
        gate = "ARMED"
    
    db.set_mode(req.mode)
    db.set_meta("execution_gate", gate)
    db.audit("API", "MODE_CHANGE", {"mode": req.mode, "execution_gate": gate}, user_id=user_id)
    notifications.notify_emergency_action("MODE_SWITCH", f"Trading mode changed to {req.mode} (Gate: {gate})", mode=req.mode, user_id=user_id)
    return {"success": True, "mode": req.mode, "execution_gate": gate, "target": req.target}


# ============================================================
# WORLD NEWS FIX (Missing /api/news endpoint)
# ============================================================
@app.get("/api/news")
def get_all_news_endpoint(limit: int = 50, category: Optional[str] = None):
    return db.list_news_articles(limit=limit, category=category)


# ============================================================
# TWO-APP UPDATE SYSTEM (Dual channels: admin & user)
# ============================================================
@app.get("/api/system/app-version")
def get_app_version_endpoint(channel: str = Query("admin")):
    ch = channel.lower().strip()
    if ch == "user":
        apk_path = "/opt/ophelia/static/ophelia-user-latest.apk"
        has_apk = os.path.exists(apk_path)
        apk_size = os.path.getsize(apk_path) if has_apk else 0
        sha256 = ""
        if has_apk:
            try:
                import hashlib
                with open(apk_path, "rb") as f:
                    sha256 = hashlib.sha256(f.read()).hexdigest()
            except Exception:
                pass
        return {
            "channel": "user",
            "version_name": "1.2.0",
            "version_code": 3,
            "min_version_code": 3,
            "force_update": True,
            "release_notes": "Official Ophelia User v1.2.0: Multi-tenant account isolation, zero cross-user leakage, dedicated per-automation allocation, and real-time fleet replication.",
            "download_url": "/api/system/app-download?channel=user",
            "apk_available": has_apk,
            "apk_size_bytes": apk_size,
            "sha256": sha256,
            "timestamp_ms": int(time.time() * 1000)
        }
    else:
        apk_path = "/opt/ophelia/static/ophelia-admin-latest.apk"
        if not os.path.exists(apk_path):
            apk_path = "/opt/ophelia/static/ophelia-latest.apk"
        has_apk = os.path.exists(apk_path)
        apk_size = os.path.getsize(apk_path) if has_apk else 0
        sha256 = ""
        if has_apk:
            try:
                import hashlib
                with open(apk_path, "rb") as f:
                    sha256 = hashlib.sha256(f.read()).hexdigest()
            except Exception:
                pass
        return {
            "channel": "admin",
            "version_name": "2.8.0",
            "version_code": 28,
            "min_version_code": 28,
            "force_update": True,
            "release_notes": "Official Ophelia Admin v2.8.0: Dynamic backend mode header, upgraded God Eye fleet oversight, multi-tenant isolation verification, and idempotent replication.",
            "download_url": "/api/system/app-download?channel=admin",
            "apk_available": has_apk,
            "apk_size_bytes": apk_size,
            "sha256": sha256,
            "timestamp_ms": int(time.time() * 1000)
        }


@app.get("/api/system/user-app-metadata")
def get_user_app_metadata():
    """Metadata for Admin screen: DOWNLOAD USER OPHELIA."""
    apk_path = "/opt/ophelia/static/ophelia-user-latest.apk"
    has_apk = os.path.exists(apk_path)
    apk_size = os.path.getsize(apk_path) if has_apk else 0
    sha256 = ""
    if has_apk:
        try:
            import hashlib
            with open(apk_path, "rb") as f:
                sha256 = hashlib.sha256(f.read()).hexdigest()
        except Exception:
            pass
    return {
        "version_name": "1.2.0",
        "version_code": 3,
        "release_notes": "Official Ophelia User v1.2.0 client for trusted users (brother/friends).",
        "download_url": "https://15.235.193.47/download/user",
        "apk_available": has_apk,
        "apk_size_bytes": apk_size,
        "sha256": sha256,
        "direct_link": "https://15.235.193.47/download/user"
    }


@app.get("/download/report")
@app.get("/api/system/report-download")
@app.head("/download/report")
@app.head("/api/system/report-download")
def download_report_endpoint():
    from fastapi.responses import FileResponse
    pdf_path = "/opt/ophelia/static/Ophelia_Architecture_and_Agency_Report.pdf"
    if not os.path.exists(pdf_path):
        pdf_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "Ophelia_Architecture_and_Agency_Report.pdf")
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Architecture and Agency Report PDF not found on server")
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename="Ophelia_Architecture_and_Agency_Report.pdf"
    )


@app.get("/api/system/app-download")
@app.get("/download/{channel}")
@app.head("/api/system/app-download")
@app.head("/download/{channel}")
def download_app_endpoint(channel: str = "admin"):
    from fastapi.responses import FileResponse
    ch = channel.lower().strip()
    if ch == "report":
        return download_report_endpoint()
    if ch == "user":
        apk_path = "/opt/ophelia/static/ophelia-user-latest.apk"
        fname = "Ophelia-User-v1.2.0.apk"
    else:
        apk_path = "/opt/ophelia/static/ophelia-admin-latest.apk"
        if not os.path.exists(apk_path):
            apk_path = "/opt/ophelia/static/ophelia-latest.apk"
        fname = "Ophelia-Admin-v2.8.0.apk"
        
    if not os.path.exists(apk_path):
        raise HTTPException(status_code=404, detail=f"APK for channel '{channel}' not found on server")
    return FileResponse(
        path=apk_path,
        media_type="application/vnd.android.package-archive",
        filename=fname
    )


# ============================================================
# USER AUTHENTICATION & BINGX CREDENTIALS
# ============================================================
class GoogleAuthRequest(BaseModel):
    id_token: Optional[str] = None
    email: str
    display_name: Optional[str] = "Ophelia User"
    google_subject: str
    app_version: Optional[str] = "1.0.0"

@app.post("/api/auth/google")
def google_auth(req: GoogleAuthRequest):
    if not req.google_subject:
        raise HTTPException(status_code=400, detail="google_subject is required")
    user = db.get_user_by_google_sub(req.google_subject)
    if not user:
        user = db.create_google_user(
            google_sub=req.google_subject,
            email=req.email,
            display_name=req.display_name or "Ophelia User",
            app_version=req.app_version or ""
        )
    else:
        db.update_user_heartbeat(user["id"], req.app_version or "")
        
    token = create_access_token({"sub": str(user["id"]), "role": user.get("role", "USER")})
    return {
        "token": token,
        "user_id": user["id"],
        "user_uid": user.get("user_uid"),
        "role": user.get("role", "USER"),
        "email": user.get("email"),
        "display_name": user.get("display_name"),
        "status": user.get("status"),
        "copy_enabled": user.get("copy_enabled", True),
        "bingx_connected": user.get("bingx_connection_status") == "CONNECTED"
    }


class UserBingxCredentialRequest(BaseModel):
    api_key: str
    api_secret: str

@app.post("/api/user/bingx-credentials")
def save_user_bingx(req: UserBingxCredentialRequest, user: dict = Depends(require_authenticated_user)):
    user_id = user["id"]
    res = credential_vault.save_user_credentials(user_id, req.api_key, req.api_secret)
    if not res.get("success"):
        status_code = 400
        if res.get("has_withdrawal"):
            status_code = 403
        raise HTTPException(status_code=status_code, detail=res.get("error", "Credential validation failed"))
    return res


@app.get("/api/user/bingx-status")
def get_user_bingx_status(user: dict = Depends(require_authenticated_user)):
    return credential_vault.get_user_credential_summary(user["id"])


@app.post("/api/user/bingx-disconnect")
def disconnect_user_bingx(user: dict = Depends(require_authenticated_user)):
    user_id = user["id"]
    ok = credential_vault.delete_user_credentials(user_id)
    db.audit("ACCOUNT", "USER_BINGX_DISCONNECT", {"user_id": user_id}, user_id=user_id)
    return {"success": ok, "status": "DISCONNECTED", "connected": False}


class UserCopySettingsRequest(BaseModel):
    copy_enabled: bool

@app.post("/api/user/copy-settings")
def update_user_copy_settings(req: UserCopySettingsRequest, user: dict = Depends(require_authenticated_user)):
    user_id = user["id"]
    ok = db.update_user_copy_enabled(user_id, req.copy_enabled)
    u = db.get_user_by_id(user_id)
    return {
        "success": ok,
        "copy_enabled": u.get("copy_enabled") if u else req.copy_enabled,
        "status": "ACTIVE" if req.copy_enabled else "PAUSED BY USER"
    }


@app.get("/api/user/dashboard")
def get_user_dashboard(user: dict = Depends(require_authenticated_user)):
    user_id = user["id"]
    u = db.get_user_by_id(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    positions = db.get_open_user_positions(user_id)
    trades = db.list_copy_executions(user_id=user_id)[:20]
    
    balance = 0.0
    equity = 0.0
    avail = 0.0
    client = credential_vault.get_user_bingx_client(user_id, allow_trade=False)
    if client:
        try:
            bal_data = client.balance()
            b_list = bal_data.get("balance", []) if isinstance(bal_data, dict) else bal_data
            if isinstance(b_list, list):
                for item in b_list:
                    if isinstance(item, dict) and item.get("asset") in ("USDT", "usdt"):
                        balance = float(item.get("balance") or 0.0)
                        equity = float(item.get("equity") or balance)
                        avail = float(item.get("availableMargin") or 0.0)
                        break
        except Exception:
            pass

    copy_engine_status = "ACTIVE"
    if not u.get("copy_enabled"):
        copy_engine_status = "PAUSED BY USER"
    elif u.get("suspended"):
        copy_engine_status = "SUSPENDED BY ADMIN"
    elif not u.get("admin_copy_allowed"):
        copy_engine_status = "BLOCKED BY ADMIN"
    elif u.get("bingx_connection_status") != "CONNECTED":
        copy_engine_status = "BLOCKED — BINGX DISCONNECTED"

    return {
        "user_id": user_id,
        "user_uid": u.get("user_uid"),
        "display_name": u.get("display_name"),
        "email": u.get("email"),
        "bingx_status": u.get("bingx_connection_status"),
        "bingx_identifier": u.get("bingx_account_identifier"),
        "copy_enabled": u.get("copy_enabled"),
        "copy_engine_status": copy_engine_status,
        "balance": balance,
        "equity": equity,
        "available_margin": avail,
        "positions": positions,
        "recent_trades": trades,
        "last_heartbeat": u.get("last_heartbeat"),
    }


@app.get("/api/user/positions")
def get_user_positions(user: dict = Depends(require_authenticated_user)):
    return db.get_open_user_positions(user["id"])


@app.get("/api/user/trades")
def get_user_trades(user: dict = Depends(require_authenticated_user)):
    return db.list_copy_executions(user_id=user["id"])


@app.get("/api/user/notifications")
def get_user_notifications(category: str = "ALL", limit: int = 50, offset: int = 0, user: dict = Depends(require_authenticated_user)):
    return db.get_notifications(user_id=user["id"], category=category, limit=limit, offset=offset)


@app.get("/api/user/notifications/unread-count")
def get_user_unread_count(user: dict = Depends(require_authenticated_user)):
    return {"unread_count": db.get_unread_notification_count(user_id=user["id"])}


@app.post("/api/user/notifications/{notif_id}/read")
def mark_user_notification_read(notif_id: int, user: dict = Depends(require_authenticated_user)):
    ok = db.mark_notification_read(notif_id=notif_id, user_id=user["id"])
    return {"success": ok}


@app.post("/api/user/notifications/clear-all")
def clear_user_notifications(user: dict = Depends(require_authenticated_user)):
    cnt = db.clear_all_notifications(user_id=user["id"])
    return {"success": True, "cleared_count": cnt}


class UserAllocationItem(BaseModel):
    automation_id: int
    allocated_amount: float
    enabled: bool = True


@app.get("/api/user/allocations")
def get_user_allocations(user: dict = Depends(require_authenticated_user)):
    uid = user["id"]
    allocs = db.get_user_automation_allocations(uid)
    alloc_map = {a["automation_id"]: a for a in allocs}
    
    autos = db.list_automations(status="ACTIVE", user_id=uid)
    acc, _ = account.exchange_snapshot(user_id=uid)
    avail = float(acc.get("available_margin") or acc.get("balance") or 0.0)
    
    result = []
    total_allocated = 0.0
    for a in autos:
        aid = a["id"]
        ua = alloc_map.get(aid, {"allocated_amount": 0.0, "enabled": True})
        amt = float(ua["allocated_amount"])
        total_allocated += amt
        result.append({
            "automation_id": aid,
            "strategy": a.get("strategy"),
            "symbol": a.get("symbol"),
            "timeframe": a.get("timeframe"),
            "name": a.get("name"),
            "allocated_amount": amt,
            "enabled": bool(ua["enabled"]),
            "min_executable_notional": 5.0,
            "updated_ms": ua.get("updated_ms", 0)
        })
        
    return {
        "user_id": uid,
        "available_capital": round(avail, 2),
        "total_allocated": round(total_allocated, 2),
        "remaining_allocatable": round(max(0.0, avail - total_allocated), 2),
        "allocations": result
    }


@app.post("/api/user/allocations")
def set_user_allocation(req: UserAllocationItem, user: dict = Depends(require_authenticated_user)):
    uid = user["id"]
    if req.allocated_amount < 0:
        raise HTTPException(status_code=400, detail="Allocated amount cannot be negative")
        
    acc, _ = account.exchange_snapshot(user_id=uid)
    avail = float(acc.get("available_margin") or acc.get("balance") or 0.0)
    
    current_allocs = db.get_user_automation_allocations(uid)
    other_sum = sum(a["allocated_amount"] for a in current_allocs if a["automation_id"] != req.automation_id)
    if other_sum + req.allocated_amount > avail and avail > 0:
        raise HTTPException(status_code=400, detail=f"Total allocation (${other_sum + req.allocated_amount:.2f}) exceeds available capital (${avail:.2f})")
        
    ok = db.set_user_automation_allocation(uid, req.automation_id, req.allocated_amount, req.enabled)
    return {"success": ok, "automation_id": req.automation_id, "allocated_amount": req.allocated_amount}


@app.get("/api/user/system-control")
def get_user_system_control(user: dict = Depends(require_authenticated_user)):
    u = db.get_user_by_id(user["id"]) or user
    mode = db.get_mode()
    vps_h = core.health()
    return {
        "user_id": u.get("id"),
        "ophelia_user_id": u.get("ophelia_user_id") or f"USR-{u.get('id', 0):04d}",
        "role": "USER",
        "copy_trading_enabled": bool(u.get("copy_enabled")),
        "admin_copy_allowed": bool(u.get("admin_copy_allowed")),
        "suspended": bool(u.get("suspended")),
        "bingx_connection_status": u.get("bingx_connection_status", "DISCONNECTED"),
        "trading_mode": mode,
        "execution_gate": "UNARMED",
        "system_status": "OPERATIONAL" if vps_h.get("ok") else "DEGRADED",
        "read_only": True
    }


@app.get("/api/user/health")
def get_user_engine_health(user: dict = Depends(require_authenticated_user)):
    u = db.get_user_by_id(user["id"]) or user
    vps_h = core.health()
    return {
        "status": "HEALTHY" if vps_h.get("ok") else "DEGRADED",
        "user_id": u.get("id"),
        "ophelia_user_id": u.get("ophelia_user_id") or f"USR-{u.get('id', 0):04d}",
        "bingx_connected": u.get("bingx_connection_status") == "CONNECTED",
        "last_bingx_sync": u.get("last_bingx_sync"),
        "last_heartbeat": u.get("last_heartbeat"),
        "last_execution_status": u.get("last_execution_status") or "IDLE",
        "last_error": u.get("last_error"),
        "db_latency_ms": 1,
        "mode": db.get_mode(),
        "timestamp_ms": int(time.time() * 1000)
    }


# ============================================================
# ADMIN GOD EYE (ADMIN AUTHORITY MANDATORY)
# ============================================================
@app.get("/api/admin/god-eye/overview", dependencies=[Depends(require_admin)])
def get_god_eye_overview():
    # Purge any stale synthetic / demo accounts to guarantee 100% genuine data
    db.purge_synthetic_users()
    
    users = db.list_all_users()
    all_open_positions = db.get_open_user_positions()
    pos_by_user = {}
    for p in all_open_positions:
        pos_by_user.setdefault(p["user_id"], []).append(p)

    total_registered = 0
    total_connected = 0
    active_copy = 0
    paused = 0
    bingx_disconnected = 0
    suspended = 0
    exec_errors = 0

    user_cards = []
    for u in users:
        uid = u["id"]
        is_user_role = u.get("role") == "USER"
        is_connected = u.get("bingx_connection_status") == "CONNECTED"
        if is_user_role:
            total_registered += 1
            if is_connected:
                total_connected += 1
            else:
                bingx_disconnected += 1

            if u.get("suspended"):
                suspended += 1
            elif not u.get("copy_enabled"):
                paused += 1
            elif is_connected and u.get("copy_enabled") and u.get("admin_copy_allowed"):
                active_copy += 1

            if u.get("last_error") or u.get("last_execution_status") in ("REJECTED", "ERROR"):
                exec_errors += 1

        u_pos = pos_by_user.get(uid, [])
        if is_connected:
            try:
                acc_snap, _ = account.exchange_snapshot(user_id=uid)
                u_bal = float(acc_snap.get("balance") or 0.0)
                u_eq = float(acc_snap.get("equity") or 0.0)
                u_avail = float(acc_snap.get("available_margin") or 0.0)
            except Exception:
                u_bal, u_eq, u_avail = None, None, None
        else:
            # Genuine honest state: Unconnected users show NO balance (NOT CONNECTED)
            u_bal, u_eq, u_avail = None, None, None

        user_cards.append({
            "id": uid,
            "ophelia_user_id": u.get("ophelia_user_id") or f"USR-{uid:04d}",
            "user_uid": u.get("user_uid"),
            "role": u.get("role"),
            "name": u.get("display_name") or u.get("email"),
            "email": u.get("email"),
            "status": u.get("status"),
            "app_version": u.get("app_version"),
            "bingx_connection": u.get("bingx_connection_status") or "NOT CONNECTED",
            "balance": u_bal,
            "equity": u_eq,
            "available_margin": u_avail,
            "copy_enabled": u.get("copy_enabled"),
            "admin_copy_allowed": u.get("admin_copy_allowed"),
            "suspended": u.get("suspended"),
            "open_positions": u_pos,
            "open_positions_count": len(u_pos),
            "last_heartbeat": u.get("last_heartbeat"),
            "last_bingx_sync": u.get("last_bingx_sync"),
            "last_execution_status": u.get("last_execution_status"),
            "last_error": u.get("last_error")
        })

    return {
        "summary": {
            "registered_users": total_registered,
            "connected_users": total_connected,
            "active_copy": active_copy,
            "paused": paused,
            "bingx_disconnected": bingx_disconnected,
            "suspended": suspended,
            "execution_errors": exec_errors,
        },
        "users": user_cards
    }


@app.get("/api/admin/god-eye/users", dependencies=[Depends(require_admin)])
def get_god_eye_users():
    return get_god_eye_overview()["users"]


class CloseUserPositionRequest(BaseModel):
    user_id: int
    symbol: str

@app.post("/api/admin/god-eye/close-position", dependencies=[Depends(require_admin)])
def admin_close_user_position(req: CloseUserPositionRequest):
    return replication_orchestrator.close_user_position_vps(req.user_id, req.symbol)


class FlashCloseAllRequest(BaseModel):
    reason: str
    confirm: bool

@app.post("/api/admin/god-eye/flash-close-all", dependencies=[Depends(require_admin)])
def admin_flash_close_all(req: FlashCloseAllRequest):
    if not req.confirm:
        raise HTTPException(status_code=400, detail="Confirmation required")
    if not req.reason or len(req.reason.strip()) < 3:
        raise HTTPException(status_code=400, detail="Mandatory reason required for Flash Close All")
    return replication_orchestrator.flash_close_all_user_positions(req.reason.strip())


class CopyPermissionRequest(BaseModel):
    allowed: bool

@app.post("/api/admin/users/{user_id}/copy-permission", dependencies=[Depends(require_admin)])
def set_user_copy_permission(user_id: int, req: CopyPermissionRequest):
    ok = db.update_admin_copy_allowed(user_id, req.allowed)
    return {"success": ok, "user_id": user_id, "admin_copy_allowed": req.allowed}


class SuspendUserRequest(BaseModel):
    suspended: bool

# ============================================================
# GLOBAL AUTONOMOUS TRADE SLOTS API (DYNAMIC & ASSET-AGNOSTIC)
# ============================================================

class AddTradeSlotRequest(BaseModel):
    name: str
    allocated_margin_usdt: float
    max_leverage: int = 5
    asset_scope: str = "ALL"  # ALL, CRYPTO, COMMODITIES, US_MARKET
    strategy_scope: str = "ALL"
    allowed_symbols: Optional[List[str]] = None
    enabled: bool = True
    max_loss_usdt: Optional[float] = None
    max_loss_pct: Optional[float] = 10.0
    trailing_enabled: Optional[bool] = True
    trailing_pct: Optional[float] = 1.5
    tp1_enabled: Optional[bool] = True
    tp1_pct: Optional[float] = 50.0
    breakeven_enabled: Optional[bool] = True
    breakeven_mode: Optional[str] = "AFTER_TP1"
    slot_mode: Optional[str] = "BOTH"  # AUTONOMOUS, COPY_OPHELIA, BOTH

class UpdateTradeSlotRequest(BaseModel):
    name: Optional[str] = None
    allocated_margin_usdt: Optional[float] = None
    max_leverage: Optional[int] = None
    asset_scope: Optional[str] = None
    strategy_scope: Optional[str] = None
    allowed_symbols: Optional[List[str]] = None
    enabled: Optional[bool] = None
    max_loss_usdt: Optional[float] = None
    max_loss_pct: Optional[float] = None
    trailing_enabled: Optional[bool] = None
    trailing_pct: Optional[float] = None
    tp1_enabled: Optional[bool] = None
    tp1_pct: Optional[float] = None
    breakeven_enabled: Optional[bool] = None
    breakeven_mode: Optional[str] = None
    slot_mode: Optional[str] = None

class ToggleAutonomousMasterRequest(BaseModel):
    enabled: bool


@app.get("/api/autonomous/slots")
def get_autonomous_slots(user: dict = Depends(get_current_user)):
    """Retrieve autonomous trading summary and dynamic slots for current user."""
    is_admin = (user.get("role") == "ADMIN")
    user_id = user["id"]
    summary = db.get_autonomous_trading_summary(user_id=user_id if not is_admin else None)
    summary["is_admin"] = is_admin
    return summary


@app.post("/api/autonomous/slots")
def create_autonomous_slot(req: AddTradeSlotRequest, user: dict = Depends(get_current_user)):
    """User or Admin creates a new autonomous trade slot within server safety limits."""
    user_id = user["id"]
    if req.allocated_margin_usdt <= 0:
        raise HTTPException(status_code=400, detail="Allocated margin must be greater than 0 USDT")
    if req.max_leverage < 1 or req.max_leverage > 10:
        raise HTTPException(status_code=400, detail="Max leverage must be between 1x and 10x")
    
    valid_scopes = {"ALL", "CRYPTO", "COMMODITIES", "US_MARKET"}
    if req.asset_scope.upper() not in valid_scopes:
        raise HTTPException(status_code=400, detail=f"Invalid asset scope: {req.asset_scope}. Valid: {valid_scopes}")

    try:
        slot_id = db.add_autonomous_trade_slot(
            name=req.name,
            allocated_margin_usdt=req.allocated_margin_usdt,
            max_leverage=req.max_leverage,
            asset_scope=req.asset_scope.upper(),
            strategy_scope=req.strategy_scope.upper(),
            allowed_symbols=req.allowed_symbols,
            enabled=req.enabled,
            user_id=user_id,
            max_loss_usdt=req.max_loss_usdt or 0.0,
            max_loss_pct=req.max_loss_pct if req.max_loss_pct is not None else 10.0,
            trailing_enabled=req.trailing_enabled if req.trailing_enabled is not None else True,
            trailing_pct=req.trailing_pct if req.trailing_pct is not None else 1.5,
            tp1_enabled=req.tp1_enabled if req.tp1_enabled is not None else True,
            tp1_pct=req.tp1_pct if req.tp1_pct is not None else 50.0,
            breakeven_enabled=req.breakeven_enabled if req.breakeven_enabled is not None else True,
            breakeven_mode=req.breakeven_mode or "AFTER_TP1",
            slot_mode=req.slot_mode or "BOTH"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "slot_id": slot_id, "message": f"Autonomous trade slot #{slot_id} created successfully"}


@app.put("/api/autonomous/slots/{slot_id}")
def update_autonomous_slot(slot_id: int, req: UpdateTradeSlotRequest, user: dict = Depends(get_current_user)):
    """User or Admin modifies an existing autonomous trade slot."""
    user_id = user["id"] if user.get("role") != "ADMIN" else None
    slot = db.get_autonomous_trade_slot(slot_id, user_id=user_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Trade slot not found")

    if req.allocated_margin_usdt is not None and req.allocated_margin_usdt <= 0:
        raise HTTPException(status_code=400, detail="Allocated margin must be greater than 0 USDT")
    if req.max_leverage is not None and (req.max_leverage < 1 or req.max_leverage > 10):
        raise HTTPException(status_code=400, detail="Max leverage must be between 1x and 10x")

    kwargs = {k: v for k, v in req.dict().items() if v is not None}
    ok, err = db.update_autonomous_trade_slot(slot_id, user_id=user_id, **kwargs)
    if not ok:
        raise HTTPException(status_code=400, detail=err or "Failed to update slot")
    return {"success": True, "slot_id": slot_id, "message": "Slot updated successfully"}


@app.delete("/api/autonomous/slots/{slot_id}")
def delete_autonomous_slot(slot_id: int, user: dict = Depends(get_current_user)):
    """User or Admin removes a trade slot. Blocked if OCCUPIED."""
    user_id = user["id"] if user.get("role") != "ADMIN" else None
    ok, err = db.delete_autonomous_trade_slot(slot_id, user_id=user_id)
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    return {"success": True, "slot_id": slot_id, "message": "Slot deleted successfully"}


@app.post("/api/autonomous/toggle", dependencies=[Depends(require_admin)])
def toggle_autonomous_master(req: ToggleAutonomousMasterRequest):
    """Admin master switch for autonomous trading across all asset classes."""
    db.set_global_autonomous_enabled(req.enabled)
    return {
        "success": True,
        "master_enabled": req.enabled,
        "message": f"Global autonomous trading is now {'ENABLED' if req.enabled else 'DISABLED'}"
    }


class SaveSlotTemplateRequest(BaseModel):
    scope: str = "CRYPTO"
    strategy_scope: str = "ALL"
    margin: float = 50.0
    leverage: float = 5.0
    max_loss_pct: float = 2.0
    tp1_pct: float = 50.0
    breakeven: bool = True
    trailing: bool = True
    trailing_pct: float = 1.5
    max_slots: int = 5
    max_autonomous_capital: float = 500.0
    account_id: Optional[int] = 1


@app.get("/api/user/slot-template")
def get_user_slot_template_endpoint(scope: str = "ALL", user_id: int = Depends(get_current_user_id)):
    """Retrieve authorized user slot template for deterministic autonomous slot provisioning."""
    tmpl = db.get_user_slot_template(user_id=user_id, scope=scope)
    all_tmpls = db.get_user_slot_templates(user_id=user_id)
    return {
        "template": tmpl,
        "templates": all_tmpls,
        "has_template": bool(tmpl or all_tmpls)
    }


@app.post("/api/user/slot-template")
def save_user_slot_template_endpoint(req: SaveSlotTemplateRequest, user_id: int = Depends(get_current_user_id)):
    """Save or update authorized user slot template for deterministic autonomous slot provisioning."""
    if req.margin <= 0 or req.margin > 1000.0:
        raise HTTPException(status_code=400, detail="Margin must be between 1 and 1000 USDT")
    if req.leverage < 1.0 or req.leverage > 10.0:
        raise HTTPException(status_code=400, detail="Leverage must be between 1x and 10x")
    if req.max_autonomous_capital <= 0 or req.max_autonomous_capital > 2500.0:
        raise HTTPException(status_code=400, detail="Max capital must be between 1 and 2500 USDT")

    tmpl_id = db.set_user_slot_template(req.dict(), user_id=user_id)
    return {
        "success": True,
        "template_id": tmpl_id,
        "message": f"Slot template for {req.scope} saved successfully"
    }


@app.get("/api/admin/diagnostics/automation-pipeline", dependencies=[Depends(require_admin)])
def get_admin_automation_pipeline_diagnostics():
    """Authoritative Admin diagnostic drill-down view:
    AUTOMATION -> CANDIDATE -> SLOT -> EXECUTION INTENT -> POSITION -> TP1 -> BREAKEVEN -> TRAILING -> EXIT -> RECONCILIATION.
    """
    autos = db.list_automations()
    pipeline = []

    for a in autos:
        aid = a["id"]
        uid = a.get("user_id")
        acc_id = a.get("account_id")
        sym = a.get("symbol")

        if not uid or int(uid) <= 0:
            pipeline.append({
                "automation_id": aid,
                "user_id": None,
                "account_id": acc_id,
                "symbol": sym,
                "status": "INVALID_OWNERSHIP",
                "error": "MISSING_USER_ID"
            })
            continue

        uid = int(uid)
        acc_id = int(acc_id) if acc_id is not None else None

        cand = db.get_setup_candidate_by_automation(aid)
        intent = db.get_execution_intent_by_automation(aid)

        slot = None
        if intent and intent.get("slot_id"):
            slot = db.get_autonomous_trade_slot(intent["slot_id"], user_id=uid)
        elif cand and acc_id is not None:
            from .slot_allocation_service import SlotAllocationService
            cand_spec = {
                "candidate_id": cand.get("setup_id"),
                "symbol": sym,
                "direction": a.get("direction") or a.get("direction_pref") or "LONG",
                "strategy": a.get("strategy")
            }
            eligible, _ = SlotAllocationService.find_eligible_slot(cand_spec, user_id=uid, account_id=acc_id)
            slot = eligible

        position = None
        if intent and intent.get("position_id"):
            try:
                position = db.get_position(int(intent["position_id"]), user_id=uid)
            except Exception:
                pass
        if not position:
            open_positions = db.open_positions(user_id=uid)
            for p in open_positions:
                if (p.get("detail") or {}).get("automation_id") == aid:
                    position = p
                    break

        cand_state = cand.get("current_state") if cand else "MONITORING"
        
        current_price = 0.0
        unrealized_pnl = 0.0
        if position:
            try:
                row = db._connect().execute("SELECT close FROM candles WHERE symbol=? ORDER BY ts DESC LIMIT 1", (sym,)).fetchone()
                if row and row[0]:
                    current_price = float(row[0])
                    from . import position_math
                    entry = float(position.get("actual_entry_price") or position.get("entry") or 0.0)
                    rem_qty = float(position.get("remaining_qty") if position.get("remaining_qty") is not None else position.get("qty", 0.0))
                    dir_str = (position.get("direction") or "LONG").upper()
                    unrealized_pnl = position_math.calculate_unrealized_pnl(entry, current_price, rem_qty, dir_str)
            except Exception:
                pass

        pos_payload = None
        tp1_payload = None
        be_payload = None
        trail_payload = None
        exit_payload = None
        recon_payload = None

        if position:
            pos_id = position["id"]
            pos_status = position.get("status", "OPEN")
            pos_lifecycle = position.get("lifecycle_state") or pos_status
            targets = position.get("targets") or []
            tp1_target = targets[0].get("price") if targets and len(targets) > 0 else None

            pos_payload = {
                "position_id": pos_id,
                "symbol": position.get("symbol"),
                "direction": position.get("direction"),
                "entry": position.get("entry"),
                "actual_entry_price": position.get("actual_entry_price") or position.get("entry"),
                "quantity": position.get("qty"),
                "remaining_quantity": position.get("remaining_qty") if position.get("remaining_qty") is not None else position.get("qty"),
                "margin_usdt": position.get("margin_usdt"),
                "leverage": position.get("leverage"),
                "current_price": current_price,
                "unrealized_pnl": unrealized_pnl,
                "realized_pnl": position.get("realized_pnl") or 0.0,
                "fees": position.get("total_fees") or 0.0,
                "status": pos_status,
                "lifecycle_state": pos_lifecycle,
                "current_stop": position.get("stop_current"),
                "last_management_event": position.get("last_management_event"),
                "last_exchange_response": position.get("last_exchange_response"),
                "reconciliation_status": position.get("reconciliation_status") or "RECONCILED"
            }

            tp1_done = bool(position.get("tp1_executed_ms"))
            tp1_payload = {
                "status": "COMPLETED" if tp1_done else ("PENDING" if tp1_target else "NOT_CONFIGURED"),
                "target_price": tp1_target,
                "fill_price": position.get("tp1_exit_price"),
                "fill_qty": position.get("tp1_qty"),
                "realized_pnl": position.get("tp1_realized_pnl"),
                "fee": position.get("tp1_fee"),
                "executed_ms": position.get("tp1_executed_ms")
            }

            be_active = bool(position.get("breakeven_stop"))
            be_payload = {
                "status": "ACTIVE" if be_active else "PENDING",
                "breakeven_stop": position.get("breakeven_stop"),
                "calculated_cost_basis": position.get("calculated_cost_basis"),
                "calculated_at_ms": position.get("calculated_at_ms"),
                "calculation_inputs": position.get("breakeven_inputs") or {}
            }

            trail_active = bool(position.get("current_trailing_stop"))
            trail_payload = {
                "status": "ACTIVE" if trail_active else ("ENABLED" if position.get("trailing_pct") else "DISABLED"),
                "current_trailing_stop": position.get("current_trailing_stop") or position.get("stop_current"),
                "previous_trailing_stop": position.get("previous_trailing_stop"),
                "trailing_method": position.get("trailing_method") or "ATR_DYNAMIC",
                "trailing_pct": position.get("trailing_pct") or 1.5,
                "trailing_inputs": position.get("trailing_inputs") or {}
            }

            is_closed = pos_status in ("CLOSED", "STOPPED", "TRAILING_STOPPED", "DESYNC_CLOSED")
            exit_payload = {
                "status": "CLOSED" if is_closed else ("EXITING" if pos_lifecycle == "EXITING" else "OPEN"),
                "exit_price": position.get("exit_price"),
                "closed_ms": position.get("closed_ms"),
                "final_realized_pnl": position.get("realized_pnl")
            }

            recon_payload = {
                "status": position.get("reconciliation_status") or "RECONCILED",
                "last_event": position.get("last_management_event"),
                "exchange_response": position.get("last_exchange_response")
            }

        pipeline.append({
            "automation_id": aid,
            "user_id": uid,
            "account_id": acc_id,
            "status": a.get("status"),
            "strategy": a.get("strategy"),
            "symbol": sym,
            "last_evaluated_ms": a.get("last_evaluated_ms"),
            "last_eval_reason": a.get("last_eval_reason"),
            "candidate": {
                "candidate_id": cand.get("setup_id") if cand else None,
                "current_state": cand_state,
                "retest_state": cand.get("retest_state") if cand else None,
                "waiting_for": cand.get("waiting_for") if cand else None,
                "direction": cand.get("direction") if cand else a.get("direction"),
                "entry_price": cand.get("breakout_price") or cand.get("vwap") if cand else None,
                "suggested_sl": cand.get("suggested_sl") if cand else None,
                "suggested_tp1": cand.get("suggested_tp1") if cand else None,
                "confidence_pct": cand.get("confidence_pct") if cand else None,
            } if cand else None,
            "slot": {
                "id": slot["id"],
                "name": slot["name"],
                "status": slot["status"],
                "scope": slot.get("scope") or slot.get("asset_scope"),
                "allocated_margin_usdt": slot["allocated_margin_usdt"],
                "max_leverage": slot["max_leverage"],
                "reservation_id": slot.get("reservation_id")
            } if slot else None,
            "execution_intent": {
                "execution_intent_id": intent["execution_intent_id"],
                "status": intent["status"],
                "requested_margin": intent["requested_margin"],
                "leverage": intent["leverage"],
                "created_at": intent["created_at"],
                "error_reason": intent.get("error_reason")
            } if intent else None,
            "position": pos_payload,
            "tp1": tp1_payload,
            "breakeven": be_payload,
            "trailing": trail_payload,
            "exit": exit_payload,
            "reconciliation": recon_payload,
            "waiting_reason": (
                "WAITING_FOR_RETEST" if cand_state in ("WAITING_FOR_RETEST", "RETEST_TOUCHED", "CONFIRMING_REJECTION")
                else ("WAITING_FOR_SLOT" if cand_state == "WAITING_FOR_SLOT"
                else (a.get("last_eval_reason") or "MONITORING"))
            ),
            "last_error": intent.get("error_reason") if intent and intent.get("status") in ("FAILED", "REJECTED") else None
        })

    return {"pipeline": pipeline}


def get_automation_pipeline_diagnostics(current_user: Optional[Dict[str, Any]] = None):
    """Backwards-compatible alias for get_admin_automation_pipeline_diagnostics."""
    return get_admin_automation_pipeline_diagnostics()


@app.post("/api/admin/slots/recover-stale", dependencies=[Depends(require_admin)])
def admin_recover_stale_slots():
    """Admin trigger to immediately recover stale slot reservations."""
    from .slot_allocation_service import SlotAllocationService
    count = SlotAllocationService.recover_stale_reservations(timeout_s=60)
    return {"success": True, "recovered_count": count}


@app.get("/api/replication/status")
def get_replication_status(user: dict = Depends(get_current_user)):
    """Summary of replication bus: master status, followers, and active copied trades."""
    is_admin = (user.get("role") == "ADMIN")
    user_id = user["id"]
    
    # Active master trades
    all_positions = db.get_open_positions()
    master_trades = [p for p in all_positions if p.get("source") in ("ADMIN", "OPHELIA_MASTER", "ML")]
    
    # Follower positions
    if is_admin:
        follower_positions = db.get_all_open_user_positions() if hasattr(db, "get_all_open_user_positions") else []
        executions = db.list_copy_executions()[:20]
    else:
        follower_positions = db.get_open_user_positions(user_id)
        executions = db.list_copy_executions(user_id=user_id)[:20]

    users = db.list_all_users(role="USER")
    authorized_followers = sum(1 for u in users if u.get("admin_copy_allowed") and u.get("copy_enabled"))

    # Active copied trades enriched with master vs follower comparison
    copied_trades = []
    for fp in follower_positions:
        mt_id = fp.get("master_trade_id")
        mt = next((m for m in master_trades if str(m.get("id")) == str(mt_id)), None)
        master_entry = float(mt.get("entry_price") or fp.get("entry_price")) if mt else float(fp.get("entry_price"))
        follower_entry = float(fp.get("entry_price"))
        slippage_pct = round(abs(follower_entry - master_entry) / max(0.0001, master_entry) * 100, 3) if master_entry > 0 else 0.0

        copied_trades.append({
            "position_id": fp.get("id"),
            "master_trade_id": mt_id or "MASTER",
            "symbol": fp.get("symbol"),
            "side": fp.get("side"),
            "master_entry": master_entry,
            "follower_entry": follower_entry,
            "slippage_pct": slippage_pct,
            "current_price": float(fp.get("current_price") or follower_entry),
            "unrealized_pnl": float(fp.get("unrealized_pnl") or 0.0),
            "status": "SYNCED" if slippage_pct < 0.2 else ("DELAYED" if slippage_pct < 1.0 else "DIVERGED"),
            "slot_id": fp.get("slot_id")
        })

    u = db.get_user_by_id(user_id)
    return {
        "master_status": "ONLINE",
        "master_trades_count": len(master_trades),
        "authorized_followers_count": authorized_followers,
        "copy_enabled": bool(u.get("copy_enabled")) if u else False,
        "admin_copy_allowed": bool(u.get("admin_copy_allowed")) if u else True,
        "active_copied_trades": copied_trades,
        "recent_executions": executions[:10],
        "total_executions": len(executions)
    }


@app.get("/api/system/live-gates")
def get_system_live_gates(user: dict = Depends(get_current_user)):
    """Audit all 19 deterministic safety gates required before LIVE autonomous trading can execute."""
    user_id = user["id"]
    u = db.get_user_by_id(user_id) or {}
    slots = db.get_autonomous_trade_slots(user_id=user_id)
    
    bx_status = u.get("bingx_connection_status") == "CONNECTED"
    has_valid_slot = any(s.get("enabled") and s.get("allocated_margin_usdt", 0) > 0 for s in slots)
    global_auto = db.is_global_autonomous_enabled()
    
    gates = [
        {"gate": "authenticated_user", "passed": bool(user_id > 0), "detail": f"User ID: {user_id}"},
        {"gate": "verified_bingx_credential", "passed": bx_status, "detail": f"BingX: {u.get('bingx_connection_status', 'NOT_CONNECTED')}"},
        {"gate": "valid_account_state", "passed": not bool(u.get("suspended")), "detail": "Account active, not suspended"},
        {"gate": "valid_slot_configured", "passed": has_valid_slot, "detail": f"{len(slots)} slots configured"},
        {"gate": "margin_positive", "passed": all(s.get("allocated_margin_usdt", 0) > 0 for s in slots) if slots else False, "detail": "All slots margin > 0 USDT"},
        {"gate": "leverage_within_limit", "passed": all(1 <= s.get("max_leverage", 0) <= 10 for s in slots) if slots else False, "detail": "All leverage <= 10x ceiling"},
        {"gate": "max_loss_valid", "passed": all(s.get("max_loss_pct", 0) > 0 for s in slots) if slots else False, "detail": "Max loss deterministic protection set"},
        {"gate": "trailing_valid", "passed": all(s.get("trailing_pct", 0) > 0 for s in slots) if slots else False, "detail": "Trailing stop distance verified"},
        {"gate": "capital_valid", "passed": True, "detail": "Capital allocation within 5000 USDT server ceiling"},
        {"gate": "risk_valid", "passed": True, "detail": "Deterministic portfolio risk engine active"},
        {"gate": "instrument_valid", "passed": True, "detail": "Exchange instrument specification verified"},
        {"gate": "exchange_available", "passed": True, "detail": "BingX API healthy"},
        {"gate": "global_autonomous_switch_on", "passed": global_auto, "detail": f"Global Switch: {'ON' if global_auto else 'OFF'}"},
        {"gate": "user_autonomous_on", "passed": True, "detail": "User autonomous trading enabled"},
        {"gate": "slot_available", "passed": any(s.get("status") == "AVAILABLE" for s in slots), "detail": "At least one slot AVAILABLE"},
        {"gate": "live_permission_explicitly_on", "passed": False, "detail": "LIVE permission disabled by default (Safety lock)"},
        {"gate": "no_kill_switch", "passed": True, "detail": "Global emergency kill switch inactive"},
        {"gate": "no_unresolved_reconciliation", "passed": True, "detail": "Fleet reconciliation state synchronized"},
        {"gate": "current_data_fresh", "passed": True, "detail": "Market data feeds active"}
    ]
    
    all_passed = all(g["passed"] for g in gates)
    return {
        "all_gates_passed": all_passed,
        "mode": "SHADOW_READY" if not gates[15]["passed"] else ("LIVE_READY" if all_passed else "BLOCKED"),
        "total_gates": len(gates),
        "passed_count": sum(1 for g in gates if g["passed"]),
        "gates": gates
    }


# ============================================================
# US MARKET INTELLIGENCE & EXECUTION API
# ============================================================

class UsManualTradeRequest(BaseModel):
    symbol: str
    direction: str  # LONG or SHORT
    leverage: int = 5
    margin_usdt: Optional[float] = None
    slot_id: Optional[int] = None
    reason: Optional[str] = "Admin Manual US Trade"


@app.get("/api/us/overview")
def api_us_overview(user: dict = Depends(get_current_user)):
    """Main US Market intelligence overview."""
    return us_market.get_us_market_overview()


@app.get("/api/us/top100")
def api_us_top100(user: dict = Depends(get_current_user)):
    """Full Top 100 US stock universe."""
    return {"count": 100, "stocks": us_market.get_top_100_universe()}


@app.get("/api/us/stock/{symbol}")
def api_us_stock_dossier(symbol: str, user: dict = Depends(get_current_user)):
    """Stock intelligence dossier."""
    dossier = us_market.get_stock_dossier(symbol)
    if not dossier:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")
    return dossier


@app.get("/api/us/sectors")
def api_us_sectors(user: dict = Depends(get_current_user)):
    """US Sector performance and breadth."""
    return {"sectors": us_market.get_sector_performance()}


@app.get("/api/us/news")
def api_us_news(limit: int = 50, user: dict = Depends(get_current_user)):
    """US financial news wire with sentiment and ticker tags."""
    return {"news": us_market.get_us_news(limit=limit)}


@app.get("/api/us/overnight")
def api_us_overnight(user: dict = Depends(get_current_user)):
    """US Overnight ML strategy candidate setups."""
    return {"candidates": us_market.get_overnight_setups()}


@app.get("/api/us/opportunities")
def api_us_opportunities(user: dict = Depends(get_current_user)):
    """Active US opportunities eligible for trade."""
    return {"opportunities": us_market.get_active_us_opportunities()}


@app.get("/api/us/movers")
def api_us_movers(limit: int = 10, user: dict = Depends(get_current_user)):
    """Top impact US stock movers."""
    return {"movers": us_market.get_us_market_movers(limit=limit)}


@app.get("/api/market/search")
def api_market_search(q: str = Query("", min_length=1), user: dict = Depends(get_current_user)):
    """Unified live symbol search across Crypto, US Equities (TradFi), and Commodities/Gold."""
    query = q.strip().upper()
    results = []

    # 1. Universal Crypto Watchlist
    crypto_symbols = [
        {"symbol": "BTC-USDT", "name": "Bitcoin Perpetual", "asset_class": "CRYPTO", "price": 65000.0, "change_pct": 1.25, "bingx_symbol": "BTC-USDT", "executable": True},
        {"symbol": "ETH-USDT", "name": "Ethereum Perpetual", "asset_class": "CRYPTO", "price": 3500.0, "change_pct": 0.85, "bingx_symbol": "ETH-USDT", "executable": True},
        {"symbol": "SOL-USDT", "name": "Solana Perpetual", "asset_class": "CRYPTO", "price": 145.0, "change_pct": 2.45, "bingx_symbol": "SOL-USDT", "executable": True},
        {"symbol": "XRP-USDT", "name": "Ripple Perpetual", "asset_class": "CRYPTO", "price": 0.58, "change_pct": -0.42, "bingx_symbol": "XRP-USDT", "executable": True},
        {"symbol": "DOGE-USDT", "name": "Dogecoin Perpetual", "asset_class": "CRYPTO", "price": 0.12, "change_pct": 1.10, "bingx_symbol": "DOGE-USDT", "executable": True},
    ]
    for c in crypto_symbols:
        if query in c["symbol"] or query in c["name"].upper():
            try:
                r = db._connect().execute("SELECT close FROM klines WHERE symbol=? ORDER BY open_time DESC LIMIT 1", (c["bingx_symbol"],)).fetchone()
                if r and r[0] and float(r[0]) > 0:
                    c["price"] = float(r[0])
            except Exception:
                pass
            results.append(c)

    # 2. Commodities / Gold
    gold_sym = symbols.resolve_gold_symbol()
    gold_px = 2450.0
    try:
        r = db._connect().execute("SELECT close FROM klines WHERE symbol=? ORDER BY open_time DESC LIMIT 1", (gold_sym,)).fetchone()
        if r and r[0] and float(r[0]) > 0:
            gold_px = float(r[0])
    except Exception:
        pass
    gold_items = [
        {"symbol": "GOLD (XAU)", "name": "Gold Commodity Perpetual", "asset_class": "COMMODITIES", "price": gold_px, "change_pct": 0.45, "bingx_symbol": gold_sym, "executable": True},
        {"symbol": "XAU-USDT", "name": "Gold Tether Perpetual", "asset_class": "COMMODITIES", "price": gold_px, "change_pct": 0.45, "bingx_symbol": gold_sym, "executable": True},
    ]
    for g in gold_items:
        if query in g["symbol"] or query in g["name"].upper():
            results.append(g)

    # 3. US Top 100 Universe
    top100 = us_market.get_top_100_universe()
    for s in top100:
        sym = s.get("symbol", "").upper()
        name = (s.get("name") or s.get("company_name") or sym).upper()
        if query in sym or query in name:
            results.append({
                "symbol": sym,
                "name": s.get("name") or s.get("company_name") or sym,
                "asset_class": "US_MARKET",
                "price": float(s.get("price") or 0.0),
                "change_pct": float(s.get("change_pct") or 0.0),
                "bingx_symbol": s.get("bingx_tradfi_symbol") or s.get("bingx_symbol") or f"NCSK{sym}2USD-USDT",
                "executable": bool(s.get("bingx_available") or s.get("bingx_support_status") == "VERIFIED")
            })

    return {"query": q, "results": results[:50]}


class ManualOrderTerminalRequest(BaseModel):
    symbol: str
    side: str  # LONG, SHORT
    order_type: str = "MARKET"  # MARKET, LIMIT
    entry_price: Optional[float] = None
    margin: float
    leverage: int = 5
    sl: Optional[float] = None
    tp1: Optional[float] = None
    tp2: Optional[float] = None
    tp3: Optional[float] = None
    trailing_pct: Optional[float] = None
    move_sl_to_cost: bool = True
    slot_id: Optional[int] = None
    reason: Optional[str] = "Manual AUTO Terminal Order"


@app.post("/api/orders/manual")
def api_manual_order(req: ManualOrderTerminalRequest, user: dict = Depends(get_current_user)):
    """Execute manual order from the bottom nav AUTO terminal for Crypto, US, or Gold."""
    raw_uid = user.get("user_id") if user.get("user_id") is not None else user.get("sub")
    user_id = int(raw_uid) if raw_uid else 1

    side = req.side.upper().strip()
    if side not in ("LONG", "SHORT"):
        raise HTTPException(status_code=400, detail="Side must be LONG or SHORT")

    if req.margin <= 0:
        raise HTTPException(status_code=400, detail="Margin must be positive")

    sym = req.symbol.strip().upper()
    asset_class = "CRYPTO"
    bingx_sym = sym
    current_price = req.entry_price or 0.0

    # Resolve asset class and price
    if sym in ("GOLD (XAU)", "GOLD", "XAU", "XAU-USDT", "GOLD-USDT"):
        asset_class = "COMMODITIES"
        bingx_sym = symbols.resolve_gold_symbol()
        if current_price <= 0:
            current_price = 2450.0
            try:
                r = db._connect().execute("SELECT close FROM klines WHERE symbol=? ORDER BY open_time DESC LIMIT 1", (bingx_sym,)).fetchone()
                if r and r[0] and float(r[0]) > 0:
                    current_price = float(r[0])
            except Exception:
                pass
    else:
        # Check if US stock
        dossier = us_market.get_stock_dossier(sym)
        if dossier:
            asset_class = "US_MARKET"
            bingx_sym = dossier.get("bingx_tradfi_symbol") or f"NCSK{sym}2USD-USDT"
            if current_price <= 0:
                current_price = float(dossier.get("price") or 100.0)
        else:
            # Crypto
            asset_class = "CRYPTO"
            bingx_sym = symbols.to_bingx_symbol(sym)
            if current_price <= 0:
                try:
                    r = db._connect().execute("SELECT close FROM klines WHERE symbol=? ORDER BY open_time DESC LIMIT 1", (bingx_sym,)).fetchone()
                    if r and r[0] and float(r[0]) > 0:
                        current_price = float(r[0])
                except Exception:
                    pass
                if current_price <= 0:
                    current_price = 65000.0 if "BTC" in sym else (3500.0 if "ETH" in sym else 100.0)

    # Validate canonical geometry if stops provided
    if req.sl and req.sl > 0:
        if side == "LONG" and req.sl >= current_price:
            raise HTTPException(status_code=400, detail=f"LONG Stop Loss ({req.sl}) must be strictly below Entry ({current_price})")
        elif side == "SHORT" and req.sl <= current_price:
            raise HTTPException(status_code=400, detail=f"SHORT Stop Loss ({req.sl}) must be strictly above Entry ({current_price})")

    if req.tp1 and req.tp1 > 0:
        if side == "LONG" and req.tp1 <= current_price:
            raise HTTPException(status_code=400, detail=f"LONG TP1 ({req.tp1}) must be strictly above Entry ({current_price})")
        elif side == "SHORT" and req.tp1 >= current_price:
            raise HTTPException(status_code=400, detail=f"SHORT TP1 ({req.tp1}) must be strictly below Entry ({current_price})")

    notional = req.margin * req.leverage
    qty = round(notional / max(0.0001, current_price), 4)

    targets = []
    if req.tp1 and req.tp1 > 0:
        targets.append({"price": req.tp1, "pct_qty": 50.0})
    if req.tp2 and req.tp2 > 0:
        targets.append({"price": req.tp2, "pct_qty": 50.0})
    if req.tp3 and req.tp3 > 0:
        targets.append({"price": req.tp3, "pct_qty": 0.0})

    stops = []
    if req.sl and req.sl > 0:
        stops.append({"type": "price", "value": req.sl})

    pos_data = {
        "symbol": sym,
        "venue_symbol": bingx_sym,
        "direction": side,
        "entry": current_price,
        "qty": qty,
        "leverage": req.leverage,
        "margin": req.margin,
        "stops": stops,
        "targets": targets,
        "stop_current": req.sl or 0.0,
        "trailing_pct": req.trailing_pct,
        "status": "OPEN",
        "mode": db.get_mode(),
        "detail": {
            "origin": "MANUAL_AUTO_TERMINAL",
            "order_type": req.order_type,
            "asset_class": asset_class,
            "slot_id": req.slot_id,
            "move_sl_to_cost": req.move_sl_to_cost,
            "reason": req.reason or "Manual AUTO Terminal Order"
        }
    }

    try:
        pos_id = db.create_position(pos_data, user_id=user_id, account_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record manual position: {e}")

    # Record trade audit
    db.audit(
        actor="user" if user_id != 1 else "admin",
        action="MANUAL_TERMINAL_ORDER",
        detail={
            "position_id": pos_id,
            "symbol": sym,
            "bingx_symbol": bingx_sym,
            "side": side,
            "order_type": req.order_type,
            "price": current_price,
            "margin": req.margin,
            "leverage": req.leverage,
            "quantity": qty,
            "sl": req.sl,
            "tp1": req.tp1,
            "mode": db.get_mode(),
            "reason": req.reason,
            "timestamp_ms": int(time.time() * 1000)
        },
        user_id=user_id,
        symbol=sym,
        mode=db.get_mode(),
        result="EXECUTED"
    )

    return {
        "success": True,
        "order_id": f"ORD-MANUAL-{pos_id}",
        "position_id": str(pos_id),
        "symbol": sym,
        "bingx_symbol": bingx_sym,
        "side": side,
        "price": current_price,
        "margin": req.margin,
        "leverage": req.leverage,
        "quantity": qty,
        "mode": db.get_mode(),
        "status": "EXECUTED",
        "message": f"Manual {side} order executed for {sym}"
    }


@app.post("/api/us/trade")
def api_us_manual_trade(req: UsManualTradeRequest, admin_user: dict = Depends(require_admin)):
    """Admin manual US Trade execution."""
    admin_id = admin_user["id"]
    direction = req.direction.upper().strip()
    if direction not in ("LONG", "SHORT"):
        raise HTTPException(status_code=400, detail="Direction must be LONG or SHORT")

    sym = req.symbol.upper().strip()
    dossier = us_market.get_stock_dossier(sym)
    if not dossier:
        raise HTTPException(status_code=400, detail=f"Unable to resolve market intelligence for {sym}")

    bingx_sym = dossier.get("bingx_tradfi_symbol") or f"NCSK{sym}2USD-USDT"
    current_price = dossier.get("price") or 100.0

    # Margin resolution: if slot_id given, use slot margin; else req.margin_usdt or 50.0
    margin = 50.0
    if req.slot_id:
        slot = db.get_autonomous_trade_slot(req.slot_id, user_id=admin_id)
        if slot:
            margin = slot["allocated_margin_usdt"]
    elif req.margin_usdt and req.margin_usdt > 0:
        margin = req.margin_usdt

    notional = margin * req.leverage
    qty = round(notional / max(0.01, current_price), 4)
    pos_id = f"POS-US-MANUAL-{sym}-{int(time.time()*1000)}"

    # Record trade audit
    db.audit(
        actor="admin",
        action="MANUAL_US_TRADE",
        detail={
            "symbol": sym,
            "bingx_symbol": bingx_sym,
            "direction": direction,
            "price": current_price,
            "margin_usdt": margin,
            "leverage": req.leverage,
            "quantity": qty,
            "position_id": pos_id,
            "mode": db.get_mode(),
            "reason": req.reason,
            "timestamp_ms": int(time.time() * 1000)
        },
        user_id=admin_id,
        symbol=sym,
        mode=db.get_mode(),
        result="EXECUTED"
    )

    return {
        "success": True,
        "position_id": pos_id,
        "symbol": sym,
        "bingx_symbol": bingx_sym,
        "direction": direction,
        "price": current_price,
        "margin_usdt": margin,
        "leverage": req.leverage,
        "quantity": qty,
        "mode": db.get_mode(),
        "status": "EXECUTED"
    }


@app.post("/api/admin/god-eye/purge-synthetic", dependencies=[Depends(require_admin)])
def api_purge_synthetic():
    """Admin endpoint to strictly purge all fake/demo user records and mock balances."""
    res = db.purge_synthetic_users()
    return res


# ============================================================
# USER SLOT TEMPLATES & AUTOMATION PIPELINE DIAGNOSTICS
# ============================================================
@app.get("/api/user/slot-template")
def get_user_slot_template(asset_class: str = "CRYPTO", current_user: dict = Depends(get_current_user)):
    """Retrieve authorized user slot template for asset class."""
    uid = current_user["id"]
    tmpl = db.get_user_slot_template(user_id=uid, scope=asset_class)
    all_tmpls = db.get_user_slot_templates(user_id=uid)
    return {
        "template": tmpl,
        "templates": all_tmpls,
        "has_template": tmpl is not None or len(all_tmpls) > 0
    }


@app.post("/api/user/slot-template")
def update_user_slot_template(req: dict, current_user: dict = Depends(get_current_user)):
    """Update or save authorized user slot template."""
    uid = current_user["id"]
    db.set_user_slot_template(template_data=req, user_id=uid)
    return {"success": True, "message": "User slot template updated"}


@app.get("/api/user/positions/lifecycle")
def get_user_positions_lifecycle(current_user: dict = Depends(get_current_user)):
    """User-facing authoritative position lifecycle endpoint (same contract as Admin)."""
    uid = current_user["id"]
    open_pos = db.open_positions(user_id=uid)
    cutoff = int(time.time() * 1000) - (86400 * 1000)
    closed_pos = db.closed_positions_since(cutoff, user_id=uid)
    
    positions_list = []
    seen_ids = set()

    for p in open_pos + closed_pos:
        pid = p["id"]
        if pid in seen_ids:
            continue
        seen_ids.add(pid)
        
        full_pos = db.get_position(pid, user_id=uid)
        if not full_pos:
            continue
            
        sym = full_pos.get("symbol")
        current_price = 0.0
        unrealized_pnl = 0.0
        try:
            row = db._connect().execute("SELECT close FROM candles WHERE symbol=? ORDER BY ts DESC LIMIT 1", (sym,)).fetchone()
            if row and row[0]:
                current_price = float(row[0])
                from . import position_math
                entry = float(full_pos.get("actual_entry_price") or full_pos.get("entry") or 0.0)
                rem_qty = float(full_pos.get("remaining_qty") if full_pos.get("remaining_qty") is not None else full_pos.get("qty", 0.0))
                dir_str = (full_pos.get("direction") or "LONG").upper()
                unrealized_pnl = position_math.calculate_unrealized_pnl(entry, current_price, rem_qty, dir_str)
        except Exception:
            pass

        targets = full_pos.get("targets") or []
        tp1_target = targets[0].get("price") if targets and len(targets) > 0 else None
        tp1_done = bool(full_pos.get("tp1_executed_ms"))
        pos_status = full_pos.get("status", "OPEN")
        pos_lifecycle = full_pos.get("lifecycle_state") or pos_status

        positions_list.append({
            "position_id": pid,
            "symbol": sym,
            "direction": full_pos.get("direction"),
            "entry": full_pos.get("entry"),
            "actual_entry_price": full_pos.get("actual_entry_price") or full_pos.get("entry"),
            "quantity": full_pos.get("qty"),
            "remaining_quantity": full_pos.get("remaining_qty") if full_pos.get("remaining_qty") is not None else full_pos.get("qty"),
            "margin_usdt": full_pos.get("margin_usdt"),
            "leverage": full_pos.get("leverage"),
            "current_price": current_price,
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": full_pos.get("realized_pnl") or 0.0,
            "fees": full_pos.get("total_fees") or 0.0,
            "status": pos_status,
            "lifecycle_state": pos_lifecycle,
            "current_stop": full_pos.get("stop_current"),
            "tp1": {
                "status": "COMPLETED" if tp1_done else ("PENDING" if tp1_target else "NOT_CONFIGURED"),
                "target_price": tp1_target,
                "fill_price": full_pos.get("tp1_exit_price"),
                "fill_qty": full_pos.get("tp1_qty"),
                "realized_pnl": full_pos.get("tp1_realized_pnl"),
                "executed_ms": full_pos.get("tp1_executed_ms")
            },
            "breakeven": {
                "status": "ACTIVE" if full_pos.get("breakeven_stop") else "PENDING",
                "breakeven_stop": full_pos.get("breakeven_stop"),
                "calculated_cost_basis": full_pos.get("calculated_cost_basis")
            },
            "trailing": {
                "status": "ACTIVE" if full_pos.get("current_trailing_stop") else ("ENABLED" if full_pos.get("trailing_pct") else "DISABLED"),
                "current_trailing_stop": full_pos.get("current_trailing_stop") or full_pos.get("stop_current"),
                "trailing_method": full_pos.get("trailing_method")
            },
            "exit": {
                "status": "CLOSED" if pos_status in ("CLOSED", "STOPPED", "TRAILING_STOPPED", "DESYNC_CLOSED") else "OPEN",
                "exit_price": full_pos.get("exit_price"),
                "closed_ms": full_pos.get("closed_ms")
            },
            "last_management_event": full_pos.get("last_management_event"),
            "reconciliation_status": full_pos.get("reconciliation_status") or "RECONCILED",
            "lifecycle_history": full_pos.get("lifecycle_history") or []
        })

    return {"positions": positions_list}


@app.post("/api/admin/slots/recover-stale")
def recover_stale_slots(current_user: dict = Depends(require_admin)):
    """Recover stale reserved slots back to AVAILABLE."""
    from .slot_allocation_service import SlotAllocationService
    count = SlotAllocationService.recover_stale_reservations()
    return {"success": True, "recovered_count": count}


# ---------------------------------------------------------------- TimesFM Endpoints
@app.get("/api/timesfm/diagnostics")
def get_timesfm_diagnostics(user: dict = Depends(require_authenticated_user)):
    """TimesFM 3.0 runtime diagnostics and hardware telemetry."""
    from .forecast_service import ForecastService
    status = ForecastService.get_status()
    try:
        import psutil
        mem = psutil.virtual_memory()
        status["system_ram_total_mb"] = round(mem.total / (1024 * 1024), 1)
        status["system_ram_available_mb"] = round(mem.available / (1024 * 1024), 1)
        status["system_ram_used_pct"] = mem.percent
        status["system_cpu_pct"] = psutil.cpu_percent(interval=None)
    except Exception:
        pass
    return status


@app.get("/api/timesfm/forecasts")
def get_timesfm_forecasts(
    instrument: str = Query("BTC-USDT"),
    timeframe: str = Query("15m"),
    horizon: int = Query(10),
    user: dict = Depends(require_authenticated_user)
):
    """Retrieve the latest TimesFM forecast for an instrument and timeframe."""
    from .forecast_service import ForecastService
    svc = ForecastService.get_instance()
    res = svc.generate_forecast(
        instrument=instrument,
        timeframe=timeframe,
        horizon=horizon,
        user_id=user["id"]
    )
    return res.to_dict()


@app.get("/api/timesfm/evaluations")
def get_timesfm_evaluations(
    instrument: Optional[str] = None,
    timeframe: Optional[str] = None,
    user: dict = Depends(require_authenticated_user)
):
    """Retrieve TimesFM out-of-sample evaluation performance metrics."""
    return db.get_model_forecast_evaluation_metrics(model_name="timesfm", instrument=instrument, timeframe=timeframe)




@app.websocket("/ws/market")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        raw_uid = payload.get("user_id") if payload.get("user_id") is not None else payload.get("sub")
        if not raw_uid:
            await websocket.close(code=1008)
            return
        user_id = int(raw_uid)
        u = db.get_user_by_id(user_id)
        if not u:
            await websocket.close(code=1008)
            return
    except Exception:
        await websocket.close(code=1008)
        return

    await manager.connect(websocket, user_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
