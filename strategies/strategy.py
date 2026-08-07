from abc import ABC, abstractmethod


class Strategy(ABC):

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

    @abstractmethod
    def get_signal(self, candles):
        """Return a dictionary with signal details."""
