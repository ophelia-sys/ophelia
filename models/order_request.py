from dataclasses import dataclass

from core.enums import (
    OrderSide,
    OrderType,
    PositionSide,
    TimeInForce,
    WorkingType,
)


@dataclass(slots=True)
class OrderRequest:
    """
    Generic BingX order request.

    This model is used for every order type:
        - MARKET
        - LIMIT
        - STOP_MARKET
        - TAKE_PROFIT_MARKET
        - TRIGGER_MARKET
        - TRIGGER_LIMIT
        - TRAILING_STOP_MARKET
    """

    # =====================================================
    # REQUIRED
    # =====================================================

    symbol: str

    side: OrderSide

    position_side: PositionSide

    order_type: OrderType

    # =====================================================
    # OPTIONAL
    # =====================================================

    quantity: float | None = None

    quote_order_qty: float | None = None

    price: float | None = None

    stop_price: float | None = None

    activation_price: float | None = None

    price_rate: float | None = None

    reduce_only: bool = False

    close_position: bool = False

    working_type: WorkingType = WorkingType.MARK_PRICE

    time_in_force: TimeInForce = TimeInForce.GTC

    client_order_id: str | None = None

    stop_guaranteed: str | None = None

    position_id: int | None = None

    recv_window: int | None = None

    # =====================================================
    # TP / SL
    # =====================================================

    stop_loss: str | None = None

    take_profit: str | None = None

    # =====================================================
    # SERIALIZATION
    # =====================================================

    def to_params(self) -> dict:
        """
        Convert the request into BingX API parameters.
        """

        params = {
            "symbol": self.symbol,
            "side": self.side.value,
            "positionSide": self.position_side.value,
            "type": self.order_type.value,
            "workingType": self.working_type.value,
            "timeInForce": self.time_in_force.value,
            "reduceOnly": str(self.reduce_only).lower(),
            "closePosition": str(self.close_position).lower(),
        }

        optional = {
            "quantity": self.quantity,
            "quoteOrderQty": self.quote_order_qty,
            "price": self.price,
            "stopPrice": self.stop_price,
            "activationPrice": self.activation_price,
            "priceRate": self.price_rate,
            "clientOrderId": self.client_order_id,
            "stopGuaranteed": self.stop_guaranteed,
            "positionId": self.position_id,
            "recvWindow": self.recv_window,
            "stopLoss": self.stop_loss,
            "takeProfit": self.take_profit,
        }

        for key, value in optional.items():
            if value is not None:
                params[key] = value

        return params