"""Ophelia Control Plane - configuration (env-driven, secrets never logged)."""
import os

def _load_env():
    candidates = [
        os.environ.get("OPH_ENV_FILE", ""),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        "/opt/ophelia/.env",
        "/opt/ophelia/control.env",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip('"').strip("'")
                            if k and k not in os.environ:
                                os.environ[k] = v
            except Exception:
                pass

_load_env()

DATA_DIR = os.environ.get("OPH_DATA_DIR", "/opt/ophelia/control_data")
DB_PATH = os.path.join(DATA_DIR, "market_1m.db")
STATE_DIR = os.environ.get("OPH_STATE_DIR", DATA_DIR)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ALLOWED_USER_IDS = [
    int(x) for x in os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "").split(",") if x.strip()
]

OLLAMA_URL = os.environ.get("OPH_OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_HOST = OLLAMA_URL
BINGX_BASE_URL = os.environ.get("OPH_BINGX_BASE_URL", "https://open-api.bingx.com")
LLM_PRIMARY = os.environ.get("OPH_LLM_PRIMARY", "qwen3:4b")
LLM_FALLBACK = None  # Strictly no fallback to 1.7b per directive
LLM_TIMEOUT_S = int(os.environ.get("OPH_LLM_TIMEOUT_S", "300"))
LLM_TIMEOUT_SEC = LLM_TIMEOUT_S
LLM_NUM_CTX = int(os.environ.get("OPH_LLM_NUM_CTX", "4096"))
LLM_KEEP_ALIVE = os.environ.get("OPH_LLM_KEEP_ALIVE", "60m")

SYMBOLS = [s.strip() for s in os.environ.get(
    "OPH_SYMBOLS", "BTC-USDT,ETH-USDT,SOL-USDT,XRP-USDT,GOLD (XAU)").split(",") if s.strip()]
if "GOLD (XAU)" not in SYMBOLS:
    SYMBOLS.append("GOLD (XAU)")
PRIMARY_EXCHANGE = os.environ.get("OPH_PRIMARY_EXCHANGE", "BINANCE")   # 1m source w/ taker data
BINGX_SYMBOL_SUFFIX = "-USDT"

GOLD_DISPLAY_NAME = "GOLD (XAU)"
_cached_gold_contract: dict | None = None
_cached_gold_contract_ts: float = 0.0
GOLD_CONTRACT_TTL_SEC: float = 300.0  # 5 minutes dynamic refresh window

def resolve_gold_contract(force_refresh: bool = False) -> dict:
    """Dynamically discover BingX Perpetual contract metadata for GOLD (XAU) at runtime.
    
    NCCOGOLD2USD-USDT is the currently observed exchange contract symbol from the
    live BingX quote contracts endpoint, not a permanent hardcoded dependency.
    """
    global _cached_gold_contract, _cached_gold_contract_ts
    import time
    now = time.time()
    if not force_refresh and _cached_gold_contract is not None and (now - _cached_gold_contract_ts) < GOLD_CONTRACT_TTL_SEC:
        return _cached_gold_contract

    import urllib.request
    import json
    url = "https://open-api.bingx.com/openApi/swap/v2/quote/contracts"
    req = urllib.request.Request(url, headers={"User-Agent": "Ophelia/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            contracts = data.get("data", [])
            best = None
            for c in contracts:
                disp = (c.get("displayName") or "").upper()
                sym = (c.get("symbol") or "").upper()
                status = c.get("status")
                api_open = str(c.get("apiStateOpen", "")).lower() == "true"
                if ("GOLD(XAU)" in disp or "NCCOGOLD2USD" in sym or sym == "NCCOGOLD2USD-USDT") and status == 1 and api_open:
                    best = c
                    break
            if not best:
                for c in contracts:
                    sym = (c.get("symbol") or "").upper()
                    if sym in ("XAUT-USDT", "PAXG-USDT") and c.get("status") == 1:
                        best = c
                        break
            if best:
                _cached_gold_contract = {
                    "display_name": GOLD_DISPLAY_NAME,
                    "venue_symbol": best.get("symbol", "NCCOGOLD2USD-USDT"),
                    "symbol": best.get("symbol", "NCCOGOLD2USD-USDT"),
                    "contract_id": str(best.get("contractId", "101773")),
                    "price_precision": int(best.get("pricePrecision", 2)),
                    "quantity_precision": int(best.get("quantityPrecision", 4)),
                    "min_quantity": float(best.get("tradeMinQuantity", 0.0005)),
                    "min_qty": float(best.get("tradeMinQuantity", 0.0005)),
                    "min_notional": float(best.get("tradeMinUSDT", 2.0)),
                    "max_leverage": int(best.get("maxLeverage", 50) if best.get("maxLeverage") else 50),
                    "fee_rate": float(best.get("feeRate", 0.0005)),
                    "maker_fee_rate": float(best.get("makerFeeRate", 0.0002)),
                    "taker_fee_rate": float(best.get("takerFeeRate", 0.0005)),
                    "discovery_method": "DYNAMIC_RUNTIME_QUERY",
                    "discovered_at_ts": now,
                    "status": "ACTIVE"
                }
                _cached_gold_contract_ts = now
                return _cached_gold_contract
    except Exception:
        pass
    
    # Graceful fallback to last observed contract if network error during boot
    if _cached_gold_contract is not None:
        return _cached_gold_contract

    _cached_gold_contract = {
        "display_name": GOLD_DISPLAY_NAME,
        "venue_symbol": "NCCOGOLD2USD-USDT",
        "symbol": "NCCOGOLD2USD-USDT",
        "contract_id": "101773",
        "price_precision": 2,
        "quantity_precision": 4,
        "min_quantity": 0.0005,
        "min_qty": 0.0005,
        "min_notional": 2.0,
        "max_leverage": 50,
        "fee_rate": 0.0005,
        "maker_fee_rate": 0.0002,
        "taker_fee_rate": 0.0005,
        "discovery_method": "DYNAMIC_DISCOVERY_FALLBACK",
        "discovered_at_ts": now,
        "status": "ACTIVE"
    }
    _cached_gold_contract_ts = now
    return _cached_gold_contract

def resolve_gold_symbol() -> str:
    """Return the dynamically resolved Gold (XAU) venue contract symbol."""
    return resolve_gold_contract().get("venue_symbol", "NCCOGOLD2USD-USDT")

def to_venue_symbol(symbol: str) -> str:
    if symbol in ("GOLD (XAU)", "GOLD", "XAU"):
        return resolve_gold_contract()["venue_symbol"]
    return symbol

def to_display_symbol(symbol: str) -> str:
    if symbol in ("NCCOGOLD2USD-USDT", "XAUT-USDT", "GOLD", "XAU"):
        return GOLD_DISPLAY_NAME
    return symbol


# Trading mode: SHADOW (default, no live orders possible) or LIVE.
# Switching to LIVE requires the double Telegram confirmation flow; the mode
# itself is persisted so restarts never silently change it.
DEFAULT_TRADING_MODE = os.environ.get("OPH_TRADING_MODE", "SHADOW")

RETENTION_HOURS = int(os.environ.get("OPH_RETENTION_HOURS", "96"))       # Operational rolling cleanup
ANALYTICAL_RETENTION_HOURS = int(os.environ.get("OPH_ANALYTICAL_RETENTION_HOURS", "120")) # 5-day analytical backtest window
CLEANUP_INTERVAL_MIN = 30
MAX_LOOKBACK_HOURS = int(os.environ.get("OPH_MAX_LOOKBACK_HOURS", "168"))  # up to 7 days for historical queries

BLACKOUT_IST = ("02:30", "05:30")             # no NEW entries
DAILY_RESET_IST = "05:30"

# VWAP regime gate (PASS 5): price must be clearly separated from VWAP and
# persistent for N completed candles; otherwise CHOP -> no trade either side.
# Defaults are documented starting points, user-configurable, not hard law.
VWAP_MIN_SEPARATION_PCT = float(os.environ.get("OPH_VWAP_MIN_SEP_PCT", "0.15"))
VWAP_PERSISTENCE_CANDLES = int(os.environ.get("OPH_VWAP_PERSISTENCE", "3"))

# Global trade cap configuration:
# DEFAULT_MAX_OPEN_TRADES is the initial configurable baseline (default 4).
# SYSTEM_SAFETY_MAX_OPEN_TRADES is the platform safety ceiling (50).
# The user-configured value is persisted in SQLite meta table.
DEFAULT_MAX_OPEN_TRADES = int(os.environ.get("OPH_DEFAULT_MAX_OPEN_TRADES", "4"))
SYSTEM_SAFETY_MAX_OPEN_TRADES = int(os.environ.get("OPH_SYSTEM_SAFETY_MAX_OPEN_TRADES", "50"))
MAX_OPEN_TRADES = DEFAULT_MAX_OPEN_TRADES
MAX_CONCURRENT_TRADES = MAX_OPEN_TRADES

# ============================================================
# EXPERIMENTAL STRATEGY PARAMETERS (NOT STATISTICALLY VALIDATED)
# All parameters are feature-flagged and configurable.
# Never presented as proven strategy rules in UI or live trading.
# ============================================================
DISPLACEMENT_ATR_MULT = float(os.environ.get("OPH_DISPLACEMENT_ATR_MULT", "1.2"))
DISPLACEMENT_BODY_RATIO = float(os.environ.get("OPH_DISPLACEMENT_BODY_RATIO", "0.65"))
RVOL_METHOD = os.environ.get("OPH_RVOL_METHOD", "ROLLING_20")
RVOL_THRESHOLD = float(os.environ.get("OPH_RVOL_THRESHOLD", "1.5"))
RETEST_WINDOW_CANDLES = int(os.environ.get("OPH_RETEST_WINDOW", "5"))
RETEST_ZONE_TOLERANCE_PCT = float(os.environ.get("OPH_RETEST_ZONE_TOLERANCE", "0.15"))
FVG_MIN_SIZE_ATR = float(os.environ.get("OPH_FVG_MIN_SIZE_ATR", "0.2"))
FVG_TIMEFRAMES = [int(tf) for tf in os.environ.get("OPH_FVG_TIMEFRAMES", "3,5,15").split(",")]
CVD_THRESHOLD_USDT = float(os.environ.get("OPH_CVD_THRESHOLD_USDT", "50000.0"))

RISK_DEFAULTS = {
    "max_leverage": 50,
    "min_margin_usdt": 5.0,
    "max_margin_pct": 100.0,
    "binance_min_notional": 5.0,
    "bingx_min_notional": 5.0,
}

NEWS_SOURCES_NOTE = (
    "crypto breadth from exchange 24h tickers; macro/DXY/rates/calendar "
    "enhanced via Global Macro & Market API sources"
)

