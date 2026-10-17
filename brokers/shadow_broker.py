from brokers.broker import Broker
from core.errors import ShadowModeIsolationError
from utils.logger import logger


class ShadowBroker(Broker):
    """
    Dedicated Broker for Shadow Mode.
    Structurally guarantees NO order execution, NO paper simulation,
    and NO broker communication can occur.
    """

    def __init__(self, position_manager=None, trade_journal=None):
        self.position_manager = position_manager
        self.trade_journal = trade_journal
        logger.info("ShadowBroker initialized: Order execution is strictly ISOLATED.")

    def process_signal(self, signal, risk_manager=None, **kwargs):
        """
        Intercepts any attempt to process a signal (which could lead to an order).
        """
        if signal.get("signal") not in ("HOLD", "LONG_CANDIDATE"):
            raise ShadowModeIsolationError(
                f"Shadow mode isolation violation! Attempted to process active signal: {signal}"
            )
        
        # In Shadow Mode, we just return safely without taking action for HOLDs.
        return None

    def place_market_order(self, *args, **kwargs):
        raise ShadowModeIsolationError("Broker isolated in SHADOW mode. Market orders blocked.")

    def place_limit_order(self, *args, **kwargs):
        raise ShadowModeIsolationError("Broker isolated in SHADOW mode. Limit orders blocked.")

    def get_open_positions(self):
        # Shadow mode tracks no positions.
        return []

    def get_protected_symbols(self, watchlist):
        # Nothing to protect since there are no live/paper positions.
        return []
