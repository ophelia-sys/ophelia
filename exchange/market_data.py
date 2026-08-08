from typing import Any

import pandas as pd


class MarketData:

    def __init__(self, client):
        self.client = client
        self._symbol_cache = {}

    def get_symbol_info(self, symbol):

        if symbol not in self._symbol_cache:

            contract = self.client.get_contract(symbol)

            if contract is None:
                raise ValueError(f"{symbol} not found.")

            self._symbol_cache[symbol] = {
                "symbol": contract.symbol,
                "quantityPrecision": contract.quantity_precision,
                "pricePrecision": contract.price_precision,
                "tradeMinQuantity": contract.min_quantity,
                "tradeMinUSDT": contract.min_notional,
            }

        if symbol not in self._symbol_cache:
            raise ValueError(f"{symbol} not found.")

        return self._symbol_cache[symbol]

    def get_current_price(self, symbol):
        return float(self.client.get_latest_price(symbol))

    def get_quantity_precision(self, symbol):
        return int(self.get_symbol_info(symbol)["quantityPrecision"])

    def get_price_precision(self, symbol):
        return int(self.get_symbol_info(symbol)["pricePrecision"])

    def get_min_quantity(self, symbol):
        return float(self.get_symbol_info(symbol)["tradeMinQuantity"])

    def get_min_notional(self, symbol):
        min_notional = self.get_symbol_info(symbol)["tradeMinUSDT"]
        if min_notional is None:
            raise ValueError(
                f"Minimum notional unavailable for {symbol}."
            )
        return float(min_notional)

    def get_klines(self, symbol, interval="1m", limit=200):

        payload = self.client.get_klines(
            symbol=symbol,
            interval=interval,
            limit=limit
        )

        rows: Any = (
            payload.get("data", [])
            if isinstance(payload, dict)
            else payload
        )
        if not isinstance(rows, list):
            raise ValueError(
                "Kline payload must be a list of rows."
            )

        df = pd.DataFrame(rows)

        df.rename(columns={"time": "timestamp"}, inplace=True)

        required_columns = [
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]

        if df.empty:
            return pd.DataFrame(columns=required_columns)

        missing_columns = [
            column
            for column in required_columns
            if column not in df.columns
        ]
        if missing_columns:
            missing = ", ".join(missing_columns)
            raise ValueError(
                f"Kline payload missing columns: {missing}"
            )

        for column in required_columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            unit="ms",
            utc=True
        ).dt.tz_localize(None)

        df = df.sort_values("timestamp").reset_index(drop=True)

        return df[required_columns]