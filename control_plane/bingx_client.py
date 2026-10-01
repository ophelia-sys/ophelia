"""Minimal BingX perpetual signed client for the control plane (stdlib only).

Endpoint paths and parameter names mirror exchange/bingx_client.py +
core/endpoints.py (single API contract, no invented fields). This client is
the ONLY module in control_plane that talks to signed BingX endpoints.

Defense in depth: trade endpoints are hard-disabled unless the client was
constructed with allow_trade=True, and core.py only constructs it that way
when the persisted trading mode is LIVE.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.parse
import urllib.request

BASE_URL = "https://open-api.bingx.com"

BALANCE = "/openApi/swap/v3/user/balance"
POSITIONS = "/openApi/swap/v2/user/positions"
LEVERAGE = "/openApi/swap/v2/trade/leverage"
ORDER = "/openApi/swap/v2/trade/order"
CLOSE_ALL_POSITIONS = "/openApi/swap/v2/trade/closeAllPositions"
KLINES = "/openApi/swap/v3/quote/klines"
CONTRACTS = "/openApi/swap/v2/quote/contracts"

RECV_WINDOW = 5000
TIMEOUT_S = 15


class BingXError(Exception):
    pass


class TradeDisabledError(BingXError):
    """Raised when a trade endpoint is called on a read-only client."""


class OrderValidationError(BingXError):
    """Raised when order parameters fail pre-submit validation locally."""


def validate_order_params(symbol: str, side: str | None = None, position_side: str | None = None,
                          quantity: float | None = None, client_order_id: str | None = None) -> str:
    """Pre-submit local parameter validator preventing malformed exchange requests.
    
    Ensures:
    1. Symbol ends with -USDT or -USDC (e.g. SOL-USDT, BTC-USDT).
    2. Side is 'BUY' or 'SELL' (if provided).
    3. PositionSide is 'LONG', 'SHORT', or 'BOTH' (if provided).
    4. Quantity is a positive float (if provided).
    5. ClientOrderId is 1-40 characters (if provided).
    
    Fails closed locally before reaching BingX API.
    """
    is_dict = isinstance(symbol, dict)
    orig_dict = None
    if is_dict:
        orig_dict = symbol
        side = orig_dict.get("side", side)
        position_side = orig_dict.get("positionSide", orig_dict.get("position_side", position_side))
        quantity = orig_dict.get("quantity", quantity)
        client_order_id = orig_dict.get("clientOrderID") or orig_dict.get("client_order_id", client_order_id)
        symbol = orig_dict.get("symbol")

    if not symbol or not isinstance(symbol, str):
        raise OrderValidationError(f"Invalid symbol: {symbol!r}")

    sym = symbol.strip().upper()
    if not (sym.endswith("-USDT") or sym.endswith("-USDC")):
        raise OrderValidationError(
            f"Invalid symbol '{symbol}': This field must end with -USDT or -USDC (hyphen required in Swap V2)")

    if side is not None:
        s = str(side).strip().upper()
        if not s or s not in ("BUY", "SELL"):
            raise OrderValidationError(f"Invalid side '{side}': This field is required and must be BUY or SELL")

    if position_side is not None:
        ps = str(position_side).strip().upper()
        if not ps or ps not in ("LONG", "SHORT", "BOTH"):
            raise OrderValidationError(f"Invalid positionSide '{position_side}': Must be LONG, SHORT, or BOTH")

    if quantity is not None:
        try:
            q = float(quantity)
            if q <= 0 or not (q == q):  # NaN check
                raise OrderValidationError(f"Invalid quantity '{quantity}': Must be positive float")
        except (TypeError, ValueError) as e:
            raise OrderValidationError(f"Invalid quantity '{quantity}': {e}") from e

    if client_order_id is not None:
        cid = str(client_order_id).strip()
        if not cid or len(cid) > 40:
            raise OrderValidationError(f"Invalid clientOrderId: Must be 1-40 characters, got {client_order_id!r}")

    if is_dict and orig_dict is not None:
        ret = dict(orig_dict)
        ret["symbol"] = sym
        if side is not None:
            ret["side"] = str(side).strip().upper()
        if position_side is not None:
            ret["positionSide"] = str(position_side).strip().upper()
        return ret

    return sym


class Client:
    def __init__(self, api_key: str, secret_key: str,
                 allow_trade: bool = False):
        self.api_key = api_key
        self.secret_key = secret_key
        self.allow_trade = allow_trade

    # ---------------- signing (mirrors exchange/bingx_client.py) ----------
    def _signed_query(self, params: dict) -> str:
        p = dict(params)
        p["timestamp"] = int(time.time() * 1000)
        p["recvWindow"] = RECV_WINDOW
        query = urllib.parse.urlencode(sorted(p.items()))
        sig = hmac.new(self.secret_key.encode(), query.encode(),
                       hashlib.sha256).hexdigest()
        return f"{query}&signature={sig}"

    def _request(self, method: str, endpoint: str, params: dict | None = None,
                 signed: bool = True) -> dict:
        if signed and not self.api_key:
            raise BingXError("BingX API keys not configured")
        url = BASE_URL + endpoint
        headers = {
            "X-BX-APIKEY": self.api_key,
            "User-Agent": "ophelia-cp/1.0"
        }
        data = None
        if method.upper() == "POST":
            if signed:
                body_str = self._signed_query(params or {})
            elif params:
                body_str = urllib.parse.urlencode(params)
            else:
                body_str = ""
            data = body_str.encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            if signed:
                url += "?" + self._signed_query(params or {})
            elif params:
                url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, data=data, method=method.upper(), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                body = json.loads(r.read().decode())
        except Exception as e:
            raise BingXError(f"network error: {str(e)[:140]}") from e
        code = body.get("code", -1)
        if code != 0:
            raise BingXError(f"bingx code {code}: {str(body.get('msg'))[:140]}")
        return body.get("data") or {}

    # ---------------- account (read-only) ---------------------------------
    def balance(self) -> dict:
        return self._request("GET", BALANCE)

    def positions(self) -> list[dict]:
        d = self._request("GET", POSITIONS)
        return d if isinstance(d, list) else []

    def test_connectivity(self) -> dict:
        """Safe zero-order connectivity test against BingX signed endpoint."""
        t0 = time.time()
        try:
            if not self.api_key or not self.secret_key:
                return {
                    "success": False,
                    "status": "NOT CONFIGURED",
                    "error": "API credentials missing or incomplete",
                    "latency_ms": 0.0
                }
            bal = self.balance()
            latency = round((time.time() - t0) * 1000, 1)
            return {
                "success": True,
                "status": "CONNECTED",
                "latency_ms": latency,
                "error": None
            }
        except Exception as e:
            latency = round((time.time() - t0) * 1000, 1)
            err_msg = str(e)
            if "api_key" in err_msg.lower() or "secret" in err_msg.lower():
                err_msg = "Authentication rejected by BingX API"
            return {
                "success": False,
                "status": "ERROR",
                "error": err_msg,
                "latency_ms": latency
            }

    def ping(self) -> dict:
        """Safe zero-order connectivity test returning ping-compatible format."""
        res = self.test_connectivity()
        if res.get("success"):
            return {"code": 0, "msg": "pong", "data": res}
        return {"code": -1, "msg": res.get("error", "Connectivity failed"), "data": res}

    # ---------------- trading (gated) --------------------------------------
    def _trade_guard(self, endpoint: str) -> None:
        if not self.allow_trade:
            raise TradeDisabledError(
                f"trade endpoint {endpoint} disabled: client is read-only "
                "(mode is not LIVE)")

    def set_leverage(self, symbol: str, leverage: int) -> dict:
        self._trade_guard(LEVERAGE)
        valid_sym = validate_order_params(symbol)
        return self._request("POST", LEVERAGE,
                             {"symbol": valid_sym, "leverage": int(leverage)})

    def market_order(self, symbol: str, side: str, position_side: str,
                     quantity: float, client_order_id: str) -> dict:
        """Market entry/exit. side: BUY|SELL; positionSide: LONG|SHORT
        (hedged) - exit uses the opposite side with same positionSide."""
        self._trade_guard(ORDER)
        valid_sym = validate_order_params(symbol, side=side, position_side=position_side,
                                          quantity=quantity, client_order_id=client_order_id)
        params = {"symbol": valid_sym, "side": side.upper(),
                  "positionSide": position_side.upper(), "type": "MARKET",
                  "quantity": float(quantity), "clientOrderId": client_order_id}
        return self._request("POST", ORDER, params)

    def close_all_positions(self) -> dict:
        self._trade_guard(CLOSE_ALL_POSITIONS)
        return self._request("POST", CLOSE_ALL_POSITIONS)

    # ---------------- public market data ------------------------------------
    def contract_spec(self, symbol: str) -> dict:
        """Exchange contract specifications for one symbol (public endpoint).

        Returns {price_precision, quantity_precision, min_qty, min_notional,
        max_leverage, contract_size} using the exact field names of the
        canonical Contract model (models/contract.py).
        The contracts endpoint requires the suffixed symbol form (XRP-USDT).
        """
        sym = symbol if "-" in symbol else \
            f"{symbol[:-4]}-{symbol[-4:]}" if symbol.endswith("USDT") else symbol
        d = self._request("GET", CONTRACTS, {"symbol": sym}, signed=False)
        rows: list = d if isinstance(d, list) else []
        if not rows:
            raise BingXError(f"contract spec not found for {symbol}")
        c = rows[0]
        return {
            "symbol": c.get("symbol", sym),
            "price_precision": int(c.get("pricePrecision", 3)),
            "quantity_precision": int(c.get("quantityPrecision", 3)),
            "min_qty": float(c.get("tradeMinQuantity") or 0),
            "min_notional": float(c.get("tradeMinUSDT") or 0) or None,
            "max_leverage": (int(float(c["maxLongLeverage"]))
                             if c.get("maxLongLeverage") else None),
            "contract_size": (float(c["contractSize"])
                              if c.get("contractSize") else None),
    }

    def klines(self, symbol: str, interval: str = "1m", limit: int = 1440,
               start_ms: int | None = None, end_ms: int | None = None) -> list[dict]:
        params: dict = {"symbol": symbol, "interval": interval,
                        "limit": int(limit)}
        if start_ms:
            params["startTime"] = int(start_ms)
        if end_ms:
            params["endTime"] = int(end_ms)
        d = self._request("GET", KLINES, params, signed=False)
        rows = d if isinstance(d, list) else d.get("list") or []
        out = []
        for k in rows:
            # BingX kline fields: time/open/high/low/close/volume/...
            if isinstance(k, dict):
                out.append({"ts": int(k["time"]), "open": float(k["open"]),
                            "high": float(k["high"]), "low": float(k["low"]),
                            "close": float(k["close"]),
                            "volume": float(k.get("volume") or 0)})
            elif isinstance(k, list):
                out.append({"ts": int(k[0]), "open": float(k[1]),
                            "high": float(k[2]), "low": float(k[3]),
                            "close": float(k[4]),
                            "volume": float(k[5])})
        return out


def public_client() -> Client:
    """Public unauthenticated client for public market data endpoints only."""
    return Client("", "", allow_trade=False)


def from_db(account_id: int | None = None) -> Client:
    """Legacy helper - returns unauthenticated client to prevent ambient account execution."""
    return public_client()


def from_env() -> Client:
    """Legacy helper - returns unauthenticated client to prevent ambient account execution."""
    return public_client()


BingXClient = Client

