import pandas as pd


class MarketData:

    def __init__(self, client):
        self.client = client
        self._symbol_cache = {}

    def get_symbol_info(self, symbol):

        if symbol not in self._symbol_cache:

            response = self.client.get_symbols()

            if response["code"] != 0:
                raise Exception(response)

            for item in response["data"]:
                self._symbol_cache[item["symbol"]] = item

        if symbol not in self._symbol_cache:
            raise Exception(f"{symbol} not found.")

        return self._symbol_cache[symbol]

    def get_current_price(self, symbol):
        return float(self.client.get_latest_price(symbol)["data"]["price"])

    def get_quantity_precision(self, symbol):
        return int(self.get_symbol_info(symbol)["quantityPrecision"])

    def get_price_precision(self, symbol):
        return int(self.get_symbol_info(symbol)["pricePrecision"])

    def get_min_quantity(self, symbol):
        return float(self.get_symbol_info(symbol)["tradeMinQuantity"])

    def get_min_notional(self, symbol):
        return float(self.get_symbol_info(symbol)["tradeMinUSDT"])

    def get_klines(self, symbol, interval="1m", limit=200):

        response = self.client.get_klines(
            symbol=symbol,
            interval=interval,
            limit=limit
        )

        df = pd.DataFrame(response["data"])

        df.rename(columns={"time": "timestamp"}, inplace=True)

        for c in ["timestamp", "open", "high", "low", "close", "volume"]:
            df[c] = pd.to_numeric(df[c])

        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            unit="ms",
            utc=True
        ).dt.tz_localize(None)

        df = df.sort_values("timestamp").reset_index(drop=True)

        return df[
            ["timestamp", "open", "high", "low", "close", "volume"]
        ]