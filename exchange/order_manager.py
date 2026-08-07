from config import LEVERAGE, MARGIN_USDT


class OrderManager:

    def __init__(self, client):

        self.client = client
        self._symbol_cache = {}

    # =====================================================
    # SYMBOL INFO
    # =====================================================

    def get_symbol_info(self, symbol):

        if symbol in self._symbol_cache:
            return self._symbol_cache[symbol]

        response = self.client.get_symbols()

        if response["code"] != 0:
            raise Exception(response)

        for item in response["data"]:

            if item["symbol"] == symbol:
                self._symbol_cache[symbol] = item
                return item

        raise Exception(f"{symbol} not found.")

    # =====================================================
    # PRICE
    # =====================================================

    def get_current_price(self, symbol):

        response = self.client.get_latest_price(symbol)

        if response["code"] != 0:
            raise Exception(response)

        return float(response["data"]["price"])

    # =====================================================
    # LEVERAGE
    # =====================================================

    def ensure_leverage(self, symbol, side):

        response = self.client.get_leverage(symbol)

        if response["code"] != 0:
            raise Exception(response)

        data = response["data"]

        current = (
            int(data["longLeverage"])
            if side == "LONG"
            else int(data["shortLeverage"])
        )

        if current != LEVERAGE:

            print(f"Setting {side} leverage to {LEVERAGE}x")

            result = self.client.set_leverage(
                symbol=symbol,
                leverage=LEVERAGE,
                side=side
            )

            if result["code"] != 0:
                raise Exception(result)

    # =====================================================
    # QUANTITY
    # =====================================================

    def calculate_quantity(self, symbol):

        info = self.get_symbol_info(symbol)

        price = self.get_current_price(symbol)

        precision = int(info["quantityPrecision"])
        minimum = float(info["tradeMinQuantity"])

        quantity = (MARGIN_USDT * LEVERAGE) / price
        quantity = max(quantity, minimum)
        quantity = round(quantity, precision)

        return quantity

    # =====================================================
    # OPEN LONG
    # =====================================================

    def open_long(self, symbol):

        self.ensure_leverage(symbol, "LONG")

        quantity = self.calculate_quantity(symbol)

        print("\n" + "=" * 60)
        print("OPEN LONG")
        print("=" * 60)
        print(f"Symbol    : {symbol}")
        print(f"Quantity  : {quantity}")
        print(f"Leverage  : {LEVERAGE}x")

        return self.client.place_market_order(
            symbol=symbol,
            side="BUY",
            position_side="LONG",
            quantity=quantity
        )

    # =====================================================
    # OPEN SHORT
    # =====================================================

    def open_short(self, symbol):

        self.ensure_leverage(symbol, "SHORT")

        quantity = self.calculate_quantity(symbol)

        print("\n" + "=" * 60)
        print("OPEN SHORT")
        print("=" * 60)
        print(f"Symbol    : {symbol}")
        print(f"Quantity  : {quantity}")
        print(f"Leverage  : {LEVERAGE}x")

        return self.client.place_market_order(
            symbol=symbol,
            side="SELL",
            position_side="SHORT",
            quantity=quantity
        )

    # =====================================================
    # CLOSE
    # =====================================================

    def close_position(self, symbol, position_side):

        response = self.client.get_positions(symbol)

        if response["code"] != 0:
            raise Exception(response)

        for position in response["data"]:

            if (
                position["symbol"] == symbol
                and position["positionSide"] == position_side
            ):

                quantity = abs(float(position["positionAmt"]))

                if quantity <= 0:
                    continue

                print("\n" + "=" * 60)
                print(f"CLOSE {position_side}")
                print("=" * 60)
                print(f"Quantity : {quantity}")

                return self.client.close_position(
                    symbol=symbol,
                    position_side=position_side,
                    quantity=quantity
                )

        print("No open position found.")
        return None

    # =====================================================
    # HELPERS
    # =====================================================

    def close_long(self, symbol):
        return self.close_position(symbol, "LONG")

    def close_short(self, symbol):
        return self.close_position(symbol, "SHORT")