from config import (
    INITIAL_STOP_PERCENT,
    STOP_UPDATE_STEP,
    TRAILING_BUFFER,
    TRAILING_TRIGGER,
)


class RiskManager:
    """
    Handles all mathematical risk calculations.

    This class knows NOTHING about:

    - BingX
    - Orders
    - EMA
    - Positions
    - API

    It only performs calculations.
    """

    LONG = "LONG"
    SHORT = "SHORT"

    # =====================================================
    # PROFIT %
    # =====================================================

    @staticmethod
    def calculate_profit_percent(
        entry_price: float,
        current_price: float,
        side: str,
    ) -> float:

        if entry_price <= 0:
            raise ValueError("Invalid entry price.")

        side = side.upper()

        if side == RiskManager.LONG:

            return (
                (current_price - entry_price)
                / entry_price
            ) * 100

        elif side == RiskManager.SHORT:

            return (
                (entry_price - current_price)
                / entry_price
            ) * 100

        raise ValueError(f"Invalid side: {side}")

    # =====================================================
    # INITIAL STOP PRICE
    # =====================================================

    @staticmethod
    def calculate_initial_stop(
        entry_price: float,
        side: str,
    ) -> float:

        side = side.upper()

        if side == RiskManager.LONG:

            return entry_price * (
                1 - INITIAL_STOP_PERCENT / 100
            )

        elif side == RiskManager.SHORT:

            return entry_price * (
                1 + INITIAL_STOP_PERCENT / 100
            )

        raise ValueError(f"Invalid side: {side}")

    # =====================================================
    # TRAILING ACTIVE
    # =====================================================

    @staticmethod
    def should_activate_trailing(
        profit_percent: float,
    ) -> bool:

        return profit_percent >= TRAILING_TRIGGER

    # =====================================================
    # LOCKED PROFIT %
    # =====================================================

    @staticmethod
    def calculate_locked_profit(
        profit_percent: float,
    ) -> float:

        if profit_percent < TRAILING_TRIGGER:

            return 0.0

        return max(
            0.0,
            profit_percent - TRAILING_BUFFER,
        )

    # =====================================================
    # STOP PRICE FROM LOCKED PROFIT
    # =====================================================

    @staticmethod
    def calculate_stop_price(
        entry_price: float,
        locked_profit_percent: float,
        side: str,
    ) -> float:

        side = side.upper()

        if side == RiskManager.LONG:

            return entry_price * (
                1 + locked_profit_percent / 100
            )

        elif side == RiskManager.SHORT:

            return entry_price * (
                1 - locked_profit_percent / 100
            )

        raise ValueError(f"Invalid side: {side}")

    # =====================================================
    # SHOULD MOVE STOP
    # =====================================================

    @staticmethod
    def should_move_stop(
        current_locked_profit: float,
        candidate_locked_profit: float,
    ) -> bool:

        improvement = (
            candidate_locked_profit
            - current_locked_profit
        )

        return improvement >= STOP_UPDATE_STEP

    # =====================================================
    # NEXT STOP
    # =====================================================

    @staticmethod
    def next_stop(
        entry_price: float,
        current_price: float,
        side: str,
        current_locked_profit: float,
    ) -> dict:

        profit = RiskManager.calculate_profit_percent(
            entry_price,
            current_price,
            side,
        )

        trailing_active = (
            RiskManager.should_activate_trailing(
                profit
            )
        )

        candidate_locked_profit = (
            RiskManager.calculate_locked_profit(
                profit
            )
        )

        move_stop = (
            RiskManager.should_move_stop(
                current_locked_profit,
                candidate_locked_profit,
            )
        )

        stop_price = None

        if move_stop:

            stop_price = (
                RiskManager.calculate_stop_price(
                    entry_price,
                    candidate_locked_profit,
                    side,
                )
            )

        return {
            "profit_percent": round(profit, 4),
            "trailing_active": trailing_active,
            "current_locked_profit": round(
                current_locked_profit,
                4,
            ),
            "candidate_locked_profit": round(
                candidate_locked_profit,
                4,
            ),
            "move_stop": move_stop,
            "stop_price": stop_price,
        }

    # =====================================================
    # POSITION SUMMARY
    # =====================================================

    @staticmethod
    def summary(
        entry_price: float,
        current_price: float,
        side: str,
        current_locked_profit: float,
    ) -> dict:

        data = RiskManager.next_stop(
            entry_price,
            current_price,
            side,
            current_locked_profit,
        )

        data["initial_stop"] = (
            RiskManager.calculate_initial_stop(
                entry_price,
                side,
            )
        )

        return data