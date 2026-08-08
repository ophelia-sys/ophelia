from brokers.broker import Broker
from config import LEVERAGE, MARGIN_USDT, MAX_OPEN_POSITIONS, USE_TRAILING_STOP
from core.trade import Trade
from utils.logger import logger


class PaperBroker(Broker):

    def __init__(
        self,
        position_manager,
        trade_journal
    ):

        self.position_manager = position_manager

        self.trade_journal = trade_journal
        self.stop_prices = {}
        self.locked_profits = {}

    def _close_and_record_trade(
        self,
        symbol,
        exit_price,
        exit_time,
        status,
    ):
        closed = self.position_manager.close_position(
            symbol,
            exit_price,
        )
        if closed is None:
            return

        self.stop_prices.pop(symbol, None)
        self.locked_profits.pop(symbol, None)

        if closed.side == "LONG":
            pnl_percent = (
                (exit_price - closed.entry_price)
                / closed.entry_price
            ) * 100
        else:
            pnl_percent = (
                (closed.entry_price - exit_price)
                / closed.entry_price
            ) * 100

        pnl_amount = (
            (pnl_percent / 100)
            * closed.entry_price
            * closed.quantity
        )

        self.trade_journal.save_trade(
            Trade(
                symbol=closed.symbol,
                side=closed.side,
                entry_price=closed.entry_price,
                exit_price=exit_price,
                quantity=closed.quantity,
                leverage=closed.leverage,
                entry_time=closed.entry_time,
                exit_time=exit_time,
                pnl_percent=round(pnl_percent, 4),
                pnl_amount=round(pnl_amount, 4),
                status=status,
            )
        )

    def process_signal(self, signal, risk_manager=None):

        symbol = signal.get("symbol", "UNKNOWN")
        signal_type = signal.get("signal", "HOLD")
        price = float(signal.get("price", 0.0))
        entry_time = signal.get("timestamp", 0)
        side = None
        if signal_type == "BUY":
            side = "LONG"
        elif signal_type == "SELL":
            side = "SHORT"

        logger.info(
            f"{symbol} -> {signal_type}"
        )

        current = self.position_manager.get_position(symbol)
        if current is not None:
            self.position_manager.update_price(symbol, price)

        if (
            current is not None
            and risk_manager is not None
            and USE_TRAILING_STOP
            and symbol in self.stop_prices
        ):
            trail = risk_manager.next_stop(
                entry_price=current.entry_price,
                current_price=price,
                side=current.side,
                current_locked_profit=self.locked_profits.get(symbol, 0.0),
            )
            candidate_stop = trail.get("stop_price")
            if trail.get("move_stop") and candidate_stop is not None:
                current_stop = self.stop_prices[symbol]
                if (
                    (current.side == "LONG" and candidate_stop > current_stop)
                    or (current.side == "SHORT" and candidate_stop < current_stop)
                ):
                    self.stop_prices[symbol] = candidate_stop
                    self.locked_profits[symbol] = trail.get(
                        "candidate_locked_profit",
                        self.locked_profits.get(symbol, 0.0),
                    )

        stop_price = self.stop_prices.get(symbol)
        if (
            current is not None
            and stop_price is not None
            and (side is None or side == current.side)
            and (
                (current.side == "LONG" and price <= stop_price)
                or (current.side == "SHORT" and price >= stop_price)
            )
        ):
            self._close_and_record_trade(
                symbol=symbol,
                exit_price=price,
                exit_time=entry_time,
                status="STOP_LOSS",
            )
            return

        if signal_type == "HOLD":
            return

        if side is None:
            return

        if current is not None and current.side == side:
            return

        if current is None and self.position_manager.count() >= MAX_OPEN_POSITIONS:
            return

        if current is not None:
            self._close_and_record_trade(
                symbol=symbol,
                exit_price=price,
                exit_time=entry_time,
                status="CLOSED",
            )

        if price <= 0:
            return

        quantity = (MARGIN_USDT * LEVERAGE) / price
        self.position_manager.open_position(
            symbol=symbol,
            side=side,
            price=price,
            quantity=quantity,
            leverage=LEVERAGE,
            entry_time=entry_time,
        )
        if risk_manager is not None:
            self.stop_prices[symbol] = risk_manager.calculate_initial_stop(
                price,
                side,
            )
            self.locked_profits[symbol] = 0.0
        self.trade_journal.save_trade(
            Trade(
                symbol=symbol,
                side=side,
                entry_price=price,
                exit_price=price,
                quantity=quantity,
                leverage=LEVERAGE,
                entry_time=entry_time,
                exit_time=entry_time,
                pnl_percent=0.0,
                pnl_amount=0.0,
                status="OPEN",
            )
        )

    def get_open_positions(self):

        return self.position_manager.get_all_positions()