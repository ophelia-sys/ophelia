import hashlib
import hmac
import os
import time
from typing import Any
from urllib.parse import urlencode

import requests
from core.errors import (
    BingXAPIError,
    BingXNetworkError,
)
from dotenv import load_dotenv
from models.balance import Balance
from requests import Response
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from core.endpoints import Endpoint
from core.serializer import Serializer
from core.validator import Validator
from models.contract import Contract
from models.order_request import OrderRequest
from models.order_response import OrderResponse
from models.position import Position
from models.ticker import Ticker

load_dotenv()


class BingXClient:
    """
    Production BingX Swap V3 REST client.

    This class is the ONLY component allowed
    to communicate directly with the BingX API.
    """

    BASE_URL = "https://open-api.bingx.com"

    DEFAULT_TIMEOUT = 15

    RECV_WINDOW = 5000

    def __init__(self):

        self.api_key = os.getenv("BINGX_API_KEY")
        self.secret_key = os.getenv("BINGX_SECRET_KEY")

        if not self.api_key:
            raise ValueError(
                "Missing environment variable: BINGX_API_KEY"
            )

        if not self.secret_key:
            raise ValueError(
                "Missing environment variable: BINGX_SECRET_KEY"
            )

        self.session = self._create_session()

    # =====================================================
    # SESSION
    # =====================================================

    def _create_session(self) -> requests.Session:

        session = requests.Session()

        retry = Retry(

            total=3,

            connect=3,

            read=3,

            backoff_factor=0.5,

            status_forcelist=[
                429,
                500,
                502,
                503,
                504,
            ],

            allowed_methods=[
                "GET",
                "POST",
                "DELETE",
            ],

            raise_on_status=False,

            respect_retry_after_header=True,

        )

        adapter = HTTPAdapter(
            max_retries=retry
        )

        session.mount(
            "https://",
            adapter,
        )

        session.mount(
            "http://",
            adapter,
        )

        session.headers.update({

            "X-BX-APIKEY": self.api_key,

        })

        session.trust_env = False

        return session

    # =====================================================
    # SIGNING
    # =====================================================

    @staticmethod
    def _timestamp() -> int:

        return int(time.time() * 1000)

    def _sign(
        self,
        params: dict[str, Any],
    ) -> str:

        ordered = sorted(
            params.items()
        )

        query = urlencode(
            ordered,
            doseq=True,
        )

        signature = hmac.new(

            self.secret_key.encode(),

            query.encode(),

            hashlib.sha256,

        ).hexdigest()

        return f"{query}&signature={signature}"

        # =====================================================
    # REQUEST ENGINE
    # =====================================================

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        params = params.copy() if params else {}

        params["timestamp"] = self._timestamp()
        params["recvWindow"] = self.RECV_WINDOW

        signed_query = self._sign(params)

        url = (
            f"{self.BASE_URL}"
            f"{endpoint}"
            f"?{signed_query}"
        )

        try:

            response: Response = self.session.request(
                method=method.upper(),
                url=url,
                timeout=self.DEFAULT_TIMEOUT,
            )

            response.raise_for_status()

        except requests.exceptions.RequestException as exc:

            raise BingXNetworkError(
                str(exc)
            ) from exc

        try:

            payload = response.json()

        except Exception as exc:

            raise BingXNetworkError(
                "Invalid JSON received from BingX."
            ) from exc

        code = payload.get("code", -1)

        if code != 0:

            raise BingXAPIError(
                code=code,
                message=payload.get(
                    "msg",
                    "Unknown BingX error.",
                ),
            )

        return payload

    # =====================================================
    # HTTP HELPERS
    # =====================================================

    def _get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self._request(
            "GET",
            endpoint,
            params,
        )

    def _post(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self._request(
            "POST",
            endpoint,
            params,
        )

    def _delete(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self._request(
            "DELETE",
            endpoint,
            params,
        )

    # =====================================================
    # MARKET API
    # =====================================================
    def get_contracts(self) -> list[Contract]:
        """
        Return all available perpetual contracts.
        """

        response = self._get(
            Endpoint.CONTRACTS
        )

        return Serializer.contracts(
            response
        )

    def get_contract(
        self,
        symbol: str,
    ) -> Contract | None:
        """
        Return one contract by symbol.
        """

        contracts = self.get_contracts()

        for contract in contracts:

            if contract.symbol == symbol:

                return contract

        return None

    def get_latest_price(
        self,
        symbol: str,
    ) -> float:
        """
        Return latest traded price.
        """

        response = self._get(
            Endpoint.PRICE,
            {
                "symbol": symbol,
            },
        )

        data = Serializer.raw_data(
            response
        )

        return float(
            data["price"]
        )

    def get_ticker(
        self,
        symbol: str,
    ) -> Ticker:
        """
        Return ticker information.
        """

        response = self._get(
            Endpoint.TICKER,
            {
                "symbol": symbol,
            },
        )

        return Serializer.ticker(
            response
        )

    def get_book_ticker(
        self,
        symbol: str,
    ) -> dict:
        """
        Return best bid / ask.

        A typed model can be introduced later.
        """

        response = self._get(
            Endpoint.BOOK_TICKER,
            {
                "symbol": symbol,
            },
        )

        return Serializer.raw_data(
            response
        )

    def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        start_time: int | None = None,
        end_time: int | None = None,
        time_zone: int = 0,
    ) -> dict:
        """
        Download historical candles.
        """

        params = {

            "symbol": symbol,

            "interval": interval,

            "limit": limit,

            "timeZone": time_zone,

        }

        if start_time is not None:

            params["startTime"] = start_time

        if end_time is not None:

            params["endTime"] = end_time

        response = self._get(

            Endpoint.KLINES,

            params,

        )

        return Serializer.raw_data(
            response
        )

    # =====================================================
    # ACCOUNT API
    # =====================================================
    
    def get_balance(self) -> Balance:
        """
        Return futures account balance.
        """

        response = self._get(
            Endpoint.BALANCE
        )

        return Serializer.balance(
            response
        )

    # =====================================================
    # POSITIONS
    # =====================================================

    def get_positions(
        self,
        symbol: str | None = None,
    ) -> list[Position]:
        """
        Return all active positions.
        """

        params = {}

        if symbol is not None:
            params["symbol"] = symbol

        response = self._get(
            Endpoint.POSITIONS,
            params,
        )

        return Serializer.positions(
            response
        )

    # =====================================================
    # LEVERAGE
    # =====================================================

    def get_leverage(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """
        Get current leverage settings.
        """

        return self._get(
            Endpoint.LEVERAGE,
            {
                "symbol": symbol,
            },
        )

    def set_leverage(
        self,
        symbol: str,
        leverage: int,
        side: str = "LONG",
    ) -> dict[str, Any]:
        """
        Set leverage.

        side:
            LONG
            SHORT
        """

        return self._post(
            Endpoint.LEVERAGE,
            {
                "symbol": symbol,
                "side": side,
                "leverage": leverage,
            },
        )

    # =====================================================
    # MARGIN MODE
    # =====================================================

    def get_margin_mode(
        self,
        symbol: str,
    ) -> dict[str, Any]:

        return self._get(
            Endpoint.MARGIN_MODE,
            {
                "symbol": symbol,
            },
        )

    def set_margin_mode(
        self,
        symbol: str,
        margin_type: str,
    ) -> dict[str, Any]:

        return self._post(
            Endpoint.MARGIN_MODE,
            {
                "symbol": symbol,
                "marginType": margin_type,
            },
        )

    # =====================================================
    # POSITION MODE
    # =====================================================

    def get_position_mode(self) -> dict[str, Any]:

        return self._get(
            Endpoint.POSITION_MODE
        )

    def set_position_mode(
        self,
        dual_side_position: bool,
    ) -> dict[str, Any]:

        return self._post(
            Endpoint.POSITION_MODE,
            {
                "dualSidePosition": str(
                    dual_side_position
                ).lower()
            },
        )

    # =====================================================
    # TRADING API
    # =====================================================

    # =====================================================
    # ORDERS
    # =====================================================

    def place_order(
        self,
        request: OrderRequest,
    ) -> OrderResponse:
        """
        Submit any supported BingX order.

        Market
        Limit
        Trigger
        Stop Loss
        Take Profit
        Trailing Stop
        """

        Validator.validate(request)

        response = self._post(
            Endpoint.ORDER,
            request.to_params(),
        )

        return Serializer.order(
            response
        )

    def get_order(
        self,
        symbol: str,
        order_id: int | None = None,
        client_order_id: str | None = None,
    ) -> OrderResponse:
        """
        Query a single order.
        """

        if order_id is None and client_order_id is None:
            raise ValueError(
                "Either order_id or client_order_id must be supplied."
            )

        params = {
            "symbol": symbol,
        }

        if order_id is not None:
            params["orderId"] = order_id

        if client_order_id is not None:
            params["clientOrderId"] = client_order_id

        response = self._get(
            Endpoint.ORDER,
            params,
        )

        return Serializer.order(
            response
        )

    def get_open_orders(
        self,
        symbol: str | None = None,
    ) -> list[OrderResponse]:
        """
        Return all currently open orders.
        """

        params = {}

        if symbol:
            params["symbol"] = symbol

        response = self._get(
            Endpoint.OPEN_ORDERS,
            params,
        )

        payload = Serializer.raw_data(
            response
        )

        orders = []

        for item in payload:

            orders.append(

                Serializer.order(
                    {
                        "data": item
                    }
                )

            )

        return orders

    def cancel_order(
        self,
        symbol: str,
        order_id: int | None = None,
        client_order_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Cancel a single order.
        """

        if order_id is None and client_order_id is None:
            raise ValueError(
                "Either order_id or client_order_id must be supplied."
            )

        params = {
            "symbol": symbol,
        }

        if order_id is not None:
            params["orderId"] = order_id

        if client_order_id is not None:
            params["clientOrderId"] = client_order_id

        return self._delete(
            Endpoint.ORDER,
            params,
        )

    def cancel_all_orders(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """
        Cancel every open order for a symbol.
        """

        return self._delete(
            Endpoint.ALL_OPEN_ORDERS,
            {
                "symbol": symbol,
            },
        )

    def get_order_history(
        self,
        symbol: str,
        limit: int = 100,
    ) -> list[OrderResponse]:
        """
        Historical order list.
        """

        response = self._get(
            Endpoint.ORDER_HISTORY,
            {
                "symbol": symbol,
                "limit": limit,
            },
        )

        payload = Serializer.raw_data(
            response
        )

        history = []

        for item in payload:

            history.append(

                Serializer.order(
                    {
                        "data": item
                    }
                )

            )

        return history

    def get_trade_history(
        self,
        symbol: str,
        limit: int = 100,
    ) -> dict[str, Any]:
        """
        Trade execution history.

        A dedicated TradeFill model will replace
        this in a later sprint.
        """

        return self._get(
            Endpoint.TRADE_HISTORY,
            {
                "symbol": symbol,
                "limit": limit,
            },
        )

    # =====================================================
    # POSITION API
    # =====================================================

    def close_position(
        self,
        position_id: int,
    ) -> dict[str, Any]:
        """
        Close a single position by position ID.
        """

        return self._post(
            Endpoint.CLOSE_POSITION,
            {
                "positionId": position_id,
            },
        )

    def close_all_positions(
        self,
        symbol: str | None = None,
    ) -> dict[str, Any]:
        """
        Close all open positions.

        If symbol is provided, only positions for that
        contract are closed.
        """

        params = {}

        if symbol is not None:
            params["symbol"] = symbol

        return self._post(
            Endpoint.CLOSE_ALL_POSITIONS,
            params,
        )

    # =====================================================
    # UTILITIES
    # =====================================================

    def ping(self) -> bool:
        """
        Check API connectivity.
        """

        try:
            self.get_contracts()
            return True
        except Exception:
            return False

    def close(self) -> None:
        """
        Close underlying HTTP session.
        """

        self.session.close()

    @property
    def connected(self) -> bool:
        """
        Returns True if API is reachable.
        """

        return self.ping()

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc_val,
        exc_tb,
    ) -> None:

        self.close()

    def __repr__(self) -> str:

        return (
            f"{self.__class__.__name__}("
            f"base_url='{self.BASE_URL}')"
        )