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

    def ensure_leverage(self, symbol, side, leverage=None):

        target_leverage = int(leverage) if leverage is not None else LEVERAGE

        response = self.client.get_leverage(symbol)

        if response["code"] != 0:
            raise Exception(response)

        data = response["data"]

        current = (
            int(data["longLeverage"])
            if side == "LONG"
            else int(data["shortLeverage"])
        )

        if current != target_leverage:

            print(f"Setting {side} leverage to {target_leverage}x")

            result = self.client.set_leverage(
                symbol=symbol,
                leverage=target_leverage,
                side=side
            )

            if result["code"] != 0:
                raise Exception(result)

    # =====================================================
    # QUANTITY
    # =====================================================

    def calculate_quantity(self, symbol, margin=None, leverage=None):

        margin_val = float(margin) if margin is not None else MARGIN_USDT
        leverage_val = int(leverage) if leverage is not None else LEVERAGE

        info = self.get_symbol_info(symbol)

        price = self.get_current_price(symbol)

        precision = int(info["quantityPrecision"])
        minimum = float(info["tradeMinQuantity"])

        quantity = (margin_val * leverage_val) / price
        quantity = max(quantity, minimum)
        quantity = round(quantity, precision)

        return quantity

    # =====================================================
    # OPEN LONG
    # =====================================================

    def open_long(self, symbol, client_order_id=None, margin=None, leverage=None):

        target_leverage = int(leverage) if leverage is not None else LEVERAGE

        self.ensure_leverage(symbol, "LONG", leverage=target_leverage)

        quantity = self.calculate_quantity(symbol, margin=margin, leverage=target_leverage)

        print("\n" + "=" * 60)
        print("OPEN LONG")
        print("=" * 60)
        print(f"Symbol    : {symbol}")
        print(f"Quantity  : {quantity}")
        print(f"Leverage  : {target_leverage}x")

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

    def open_short(self, symbol, client_order_id=None, margin=None, leverage=None):

        target_leverage = int(leverage) if leverage is not None else LEVERAGE

        self.ensure_leverage(symbol, "SHORT", leverage=target_leverage)

        quantity = self.calculate_quantity(symbol, margin=margin, leverage=target_leverage)

        print("\n" + "=" * 60)
        print("OPEN SHORT")
        print("=" * 60)
        print(f"Symbol    : {symbol}")
        print(f"Quantity  : {quantity}")
        print(f"Leverage  : {target_leverage}x")

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

    def close_position(self, symbol, position_side, quantity=None, client_order_id=None):

        positions = self.client.get_positions(symbol)

        for position in positions:

            if (
                position.symbol == symbol
                and position.side.value == position_side
            ):

                pos_qty = position.quantity

                if pos_qty <= 0:
                    continue

                if quantity is not None and float(quantity) < float(pos_qty):
                    close_qty = float(quantity)
                    info = self.get_symbol_info(symbol)
                    precision = int(info["quantityPrecision"])
                    minimum = float(info["tradeMinQuantity"])
                    close_qty = max(close_qty, minimum)
                    close_qty = min(close_qty, float(pos_qty))
                    close_qty = round(close_qty, precision)

                    print("\n" + "=" * 60)
                    print(f"PARTIAL CLOSE {position_side}")
                    print("=" * 60)
                    print(f"Symbol    : {symbol}")
                    print(f"Quantity  : {close_qty}")

                    order_side = OrderSide.SELL if position_side == "LONG" else OrderSide.BUY
                    pos_side_enum = PositionSide.LONG if position_side == "LONG" else PositionSide.SHORT

                    request = OrderRequest(
                        symbol=symbol,
                        side=order_side,
                        position_side=pos_side_enum,
                        order_type=OrderType.MARKET,
                        quantity=close_qty,
                        client_order_id=client_order_id,
                        reduce_only=True,
                    )
                    return self.client.place_order(request)

                print("\n" + "=" * 60)
                print(f"CLOSE {position_side}")
                print("=" * 60)
                print(f"Quantity : {pos_qty}")

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

    def close_long(self, symbol, quantity=None, client_order_id=None):
        return self.close_position(symbol, "LONG", quantity=quantity, client_order_id=client_order_id)

    def close_short(self, symbol, quantity=None, client_order_id=None):
        return self.close_position(symbol, "SHORT", quantity=quantity, client_order_id=client_order_id)