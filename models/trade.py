from dataclasses import dataclass
from datetime import datetime


@dataclass
class Trade:
    """
    Represents the currently active trade.

    This object is maintained by TradeManager and contains
    all information required to manage an open position.
    """

    symbol: str

    side: str

    quantity: float

    entry_price: float

    opened_at: datetime

    # -----------------------------------------------------
    # Dynamic Stop Management
    # -----------------------------------------------------

    initial_stop_price: float

    current_stop_price: float

    locked_profit_percent: float = 0.0

    highest_profit_percent: float = 0.0

    trailing_active: bool = False

    # -----------------------------------------------------
    # Exchange Information
    # -----------------------------------------------------

    order_id: str | None = None

    position_id: str | None = None

    stop_order_id: str | None = None

    take_profit_order_id: str | None = None

    # -----------------------------------------------------
    # Runtime Statistics
    # -----------------------------------------------------

    stop_updates: int = 0

    reversal_count: int = 0

    is_open: bool = True

    # =====================================================
    # UPDATE HIGHEST PROFIT
    # =====================================================

    def update_highest_profit(
        self,
        profit_percent: float,
    ):

        self.highest_profit_percent = max(self.highest_profit_percent, profit_percent)

    # =====================================================
    # UPDATE LOCKED PROFIT
    # =====================================================

    def update_locked_profit(
        self,
        locked_profit: float,
    ):

        self.locked_profit_percent = max(self.locked_profit_percent, locked_profit)

    # =====================================================
    # UPDATE STOP PRICE
    # =====================================================

    def update_stop_price(
        self,
        stop_price: float,
    ):

        self.current_stop_price = stop_price

        self.stop_updates += 1

    # =====================================================
    # MARK CLOSED
    # =====================================================

    def close(self):

        self.is_open = False

    # =====================================================
    # REVERSE
    # =====================================================

    def reverse(self):

        self.reversal_count += 1

    # =====================================================
    # SUMMARY
    # =====================================================

    def summary(self):

        return {
            "symbol": self.symbol,
            "side": self.side,
            "entry_price": self.entry_price,
            "quantity": self.quantity,
            "initial_stop_price": self.initial_stop_price,
            "current_stop_price": self.current_stop_price,
            "locked_profit_percent": self.locked_profit_percent,
            "highest_profit_percent": self.highest_profit_percent,
            "trailing_active": self.trailing_active,
            "stop_updates": self.stop_updates,
            "reversal_count": self.reversal_count,
            "is_open": self.is_open,
        }