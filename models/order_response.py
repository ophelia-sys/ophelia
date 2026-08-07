from dataclasses import dataclass
from typing import Any

from core.enums import (
    OrderSide,
    OrderStatus,
    OrderType,
    PositionSide,
    WorkingType,
)


@dataclass(slots=True)
class OrderResponse:
    """
    Normalized BingX order response.

    Every successful order placed through BingXClient
    should be converted into this model instead of
    passing raw dictionaries throughout the project.
    """

    symbol: str

    order_id: int

    side: OrderSide

    position_side: PositionSide

    order_type: OrderType

    status: OrderStatus | None = None

    client_order_id: str | None = None

    working_type: WorkingType | None = None

    avg_price: float | None = None

    executed_quantity: float | None = None

    raw: dict[str, Any] | None = None

    # =====================================================
    # DESERIALIZATION
    # =====================================================

    @classmethod
    def from_api(cls, response: dict[str, Any]) -> "OrderResponse":
        """
        Build OrderResponse from BingX REST response.
        """

        payload = response.get("data", {})

        # BingX sometimes wraps the order object.
        if "order" in payload:
            payload = payload["order"]

        return cls(

            symbol=payload["symbol"],

            order_id=int(
                payload.get(
                    "orderId",
                    payload.get("orderID")
                )
            ),

            side=OrderSide(
                payload["side"]
            ),

            position_side=PositionSide(
                payload["positionSide"]
            ),

            order_type=OrderType(
                payload["type"]
            ),

            status=(
                OrderStatus(payload["status"])
                if payload.get("status")
                else None
            ),

            client_order_id=payload.get(
                "clientOrderId"
            ),

            working_type=(
                WorkingType(payload["workingType"])
                if payload.get("workingType")
                else None
            ),

            avg_price=(
                float(payload["avgPrice"])
                if payload.get("avgPrice")
                else None
            ),

            executed_quantity=(
                float(payload["executedQty"])
                if payload.get("executedQty")
                else None
            ),

            raw=response,
        )

    # =====================================================
    # HELPERS
    # =====================================================

    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED

    @property
    def is_new(self) -> bool:
        return self.status == OrderStatus.NEW

    @property
    def is_cancelled(self) -> bool:
        return self.status == OrderStatus.CANCELLED

    @property
    def is_failed(self) -> bool:
        return self.status == OrderStatus.FAILED

    @property
    def is_partial(self) -> bool:
        return self.status == OrderStatus.PARTIALLY_FILLED