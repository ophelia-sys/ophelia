from dataclasses import dataclass
from typing import Any

from core.enums import PositionSide


@dataclass(slots=True)
class Position:
    """
    Represents an active BingX futures position.
    """

    symbol: str

    side: PositionSide

    quantity: float

    entry_price: float

    mark_price: float

    unrealized_pnl: float

    leverage: int

    liquidation_price: float | None = None

    margin_type: str | None = None

    isolated: bool | None = None

    position_id: int | None = None

    raw: dict[str, Any] | None = None

    # =====================================================
    # DESERIALIZATION
    # =====================================================

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Position":

        quantity = abs(float(data.get("positionAmt", 0)))

        side = PositionSide(
            data.get("positionSide", "LONG")
        )

        return cls(

            symbol=data["symbol"],

            side=side,

            quantity=quantity,

            entry_price=float(
                data.get("avgPrice", 0)
            ),

            mark_price=float(
                data.get("markPrice", 0)
            ),

            unrealized_pnl=float(
                data.get("unrealizedProfit", 0)
            ),

            leverage=int(
                float(data.get("leverage", 1))
            ),

            liquidation_price=(
                float(data["liquidationPrice"])
                if data.get("liquidationPrice")
                else None
            ),

            margin_type=data.get("marginType"),

            isolated=(
                str(data.get("isolated")).lower() == "true"
                if data.get("isolated") is not None
                else None
            ),

            position_id=(
                int(data["positionId"])
                if data.get("positionId")
                else None
            ),

            raw=data,
        )

    # =====================================================
    # HELPERS
    # =====================================================

    @property
    def is_long(self) -> bool:
        return self.side == PositionSide.LONG

    @property
    def is_short(self) -> bool:
        return self.side == PositionSide.SHORT

    @property
    def has_position(self) -> bool:
        return self.quantity > 0

    @property
    def market_value(self) -> float:
        return self.quantity * self.mark_price

    @property
    def entry_value(self) -> float:
        return self.quantity * self.entry_price

    def __bool__(self) -> bool:
        return self.has_position