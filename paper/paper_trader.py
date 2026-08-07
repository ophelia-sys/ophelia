from utils.logger import logger


class PaperTrader:

    def __init__(self, position_manager):

        self.position_manager = position_manager

        self.trade_history = []

    def process_signal(self, signal):

        logger.info(f"{signal.symbol} -> {signal.signal}")

        if signal.signal == "NO SIGNAL":
            return

        if not self.position_manager.has_position(signal.symbol):

            self.position_manager.open_position(
                symbol=signal.symbol,
                side=signal.signal,
                price=signal.price,
                quantity=1,
                leverage=10,
                entry_time=signal.time
            )

            logger.info(
                f"Paper Entry {signal.signal} {signal.symbol}"
            )

            return

        current = self.position_manager.get_position(signal.symbol)

        if current.side == signal.signal:

            logger.info("Already in same direction")

            return

        self.position_manager.close_position(signal.symbol)

        logger.info("Position Closed")

        self.position_manager.open_position(
            symbol=signal.symbol,
            side=signal.signal,
            price=signal.price,
            quantity=1,
            leverage=10,
            entry_time=signal.time
        )

        logger.info(
            f"Paper Reverse -> {signal.signal}"
        )