from typing import Any

from models.balance import Balance

from models.contract import Contract
from models.order_response import OrderResponse
from models.position import Position
from models.ticker import Ticker


class Serializer:
    """
    Centralized BingX response deserializer.

    All JSON returned by BingXClient should be converted
    into strongly typed model objects here.
    """

    # =====================================================
    # POSITION
    # =====================================================

    @staticmethod
    def position(data: dict[str, Any]) -> Position:
        return Position.from_api(data)

    @staticmethod
    def positions(response: dict[str, Any]) -> list[Position]:

        payload = response.get("data", [])

        return [
            Position.from_api(item)
            for item in payload
        ]

    # =====================================================
    # BALANCE
    # =====================================================

    @staticmethod
    def balance(response: dict[str, Any]) -> Balance:

        payload = response.get("data", response)

        if isinstance(payload, list):
            payload = payload[0]

        return Balance.from_api(payload)

    # =====================================================
    # CONTRACT
    # =====================================================

    @staticmethod
    def contract(data: dict[str, Any]) -> Contract:
        return Contract.from_api(data)

    @staticmethod
    def contracts(response: dict[str, Any]) -> list[Contract]:

        payload = response.get("data", [])

        return [
            Contract.from_api(item)
            for item in payload
        ]

    # =====================================================
    # TICKER
    # =====================================================

    @staticmethod
    def ticker(response: dict[str, Any]) -> Ticker:

        payload = response.get("data", response)

        if isinstance(payload, list):
            payload = payload[0]

        return Ticker.from_api(payload)

    @staticmethod
    def tickers(response: dict[str, Any]) -> list[Ticker]:

        payload = response.get("data", [])

        return [
            Ticker.from_api(item)
            for item in payload
        ]

    # =====================================================
    # ORDER
    # =====================================================

    @staticmethod
    def order(response: dict[str, Any]) -> OrderResponse:
        return OrderResponse.from_api(response)

    # =====================================================
    # HELPERS
    # =====================================================

    @staticmethod
    def first(response: dict[str, Any]) -> dict[str, Any]:
        """
        Return the first element from a BingX list response.
        """

        payload = response.get("data", [])

        if not payload:
            return {}

        return payload[0]

    @staticmethod
    def raw_data(response: dict[str, Any]) -> Any:
        """
        Return response["data"] if present.
        """

        return response.get("data", response)