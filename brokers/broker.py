from abc import ABC, abstractmethod


class Broker(ABC):

    @abstractmethod
    def process_signal(self, signal, risk_manager=None):
        pass

    @abstractmethod
    def get_open_positions(self):
        pass

    @abstractmethod
    def get_protected_symbols(self, watchlist):
        pass