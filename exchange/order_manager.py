from config import LEVERAGE, MARGIN_USDT
from core.enums import OrderSide, OrderType, PositionSide
from models.order_request import OrderRequest


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

        contract = self.client.get_contract(symbol)
        if contract is None:
            raise Exception(f"{symbol} not found.")

        info = {
            "symbol": contract.symbol,
            "quantityPrecision": contract.quantity_precision,
            "tradeMinQuantity": contract.min_quantity,
        }
        self._symbol_cache[symbol] = info
        return info

    # =====================================================
    # PRICE
    # =====================================================

    def get_current_price(self, symbol):

        return float(self.client.get_latest_price(symbol))

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

    def open_long(self, symbol, client_order_id=None):

        self.ensure_leverage(symbol, "LONG")

        quantity = self.calculate_quantity(symbol)

        print("\n" + "=" * 60)
        print("OPEN LONG")
        print("=" * 60)
        print(f"Symbol    : {symbol}")
        print(f"Quantity  : {quantity}")
        print(f"Leverage  : {LEVERAGE}x")

        request = OrderRequest(
            symbol=symbol,
            side=OrderSide.BUY,
            position_side=PositionSide.LONG,
            order_type=OrderType.MARKET,
            quantity=quantity,
            client_order_id=client_order_id,
        )
        return self.client.place_order(request)

    # =====================================================
    # OPEN SHORT
    # =====================================================

    def open_short(self, symbol, client_order_id=None):

        self.ensure_leverage(symbol, "SHORT")

        quantity = self.calculate_quantity(symbol)

        print("\n" + "=" * 60)
        print("OPEN SHORT")
        print("=" * 60)
        print(f"Symbol    : {symbol}")
        print(f"Quantity  : {quantity}")
        print(f"Leverage  : {LEVERAGE}x")

        request = OrderRequest(
            symbol=symbol,
            side=OrderSide.SELL,
            position_side=PositionSide.SHORT,
            order_type=OrderType.MARKET,
            quantity=quantity,
            client_order_id=client_order_id,
        )
        return self.client.place_order(request)

    # =====================================================
    # CLOSE
    # =====================================================

    def close_position(self, symbol, position_side):

        positions = self.client.get_positions(symbol)

        for position in positions:

            if (
                position.symbol == symbol
                and position.side.value == position_side
            ):

                quantity = position.quantity

                if quantity <= 0:
                    continue

                print("\n" + "=" * 60)
                print(f"CLOSE {position_side}")
                print("=" * 60)
                print(f"Quantity : {quantity}")

                if position.position_id is None:
                    raise Exception("Position ID is required to close position.")

                return self.client.close_position(
                    position.position_id
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