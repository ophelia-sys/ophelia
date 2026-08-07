from brokers.broker import Broker
from utils.logger import logger


class PaperBroker(Broker):

    def __init__(
        self,
        position_manager,
        trade_journal
    ):

        self.position_manager = position_manager

        self.trade_journal = trade_journal

    def process_signal(self, signal):

        logger.info(
            f"{signal.symbol} -> {signal.signal}"
        )

        # We'll implement the full open/close logic
        # in the next step.

    def get_open_positions(self):

        return self.position_manager.get_all_positions()