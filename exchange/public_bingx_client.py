import requests

from core.endpoints import Endpoint
from core.serializer import Serializer


class PublicBingXClient:
    """
    Read-only BingX market data client.

    This client intentionally supports only public endpoints and
    requires no API credentials.
    """

    BASE_URL = "https://open-api.bingx.com"
    DEFAULT_TIMEOUT = 15

    def _get(self, endpoint: str, params: dict | None = None) -> dict:
        response = requests.get(
            f"{self.BASE_URL}{endpoint}",
            params=params or {},
            timeout=self.DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code", -1) != 0:
            raise ValueError(
                f"BingX public API error: {payload.get('msg', 'Unknown error')}"
            )
        return payload

    def get_contracts(self):
        response = self._get(Endpoint.CONTRACTS)
        return Serializer.contracts(response)

    def get_contract(self, symbol: str):
        contracts = self.get_contracts()
        for contract in contracts:
            if contract.symbol == symbol:
                return contract
        return None

    def get_latest_price(self, symbol: str) -> float:
        response = self._get(
            Endpoint.PRICE,
            {"symbol": symbol},
        )
        data = Serializer.raw_data(response)
        return float(data["price"])

    def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        start_time: int | None = None,
        end_time: int | None = None,
        time_zone: int = 0,
    ):
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
        response = self._get(Endpoint.KLINES, params)
        return Serializer.raw_data(response)
