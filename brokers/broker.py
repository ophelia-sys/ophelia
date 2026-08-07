from abc import ABC, abstractmethod


class Broker(ABC):

    @abstractmethod
    def process_signal(self, signal):
        pass

    @abstractmethod
    def get_open_positions(self):
        pass