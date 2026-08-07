from dataclasses import dataclass


@dataclass
class Position:

    symbol: str
    side: str

    entry_price: float
    current_price: float

    quantity: float
    leverage: int

    entry_time: int


class PositionManager:

    def __init__(self):

        self.positions = {}

    def has_position(self, symbol):

        return symbol in self.positions

    def open_position(
        self,
        symbol,
        side,
        price,
        quantity,
        leverage,
        entry_time
    ):

        if self.has_position(symbol):

            return False

        self.positions[symbol] = Position(
            symbol=symbol,
            side=side,
            entry_price=price,
            current_price=price,
            quantity=quantity,
            leverage=leverage,
            entry_time=entry_time
        )

        return True

    def close_position(self, symbol, exit_price):

        if not self.has_position(symbol):

            return None

        position = self.positions.pop(symbol)

        position.current_price = exit_price

        return position

    def update_price(self, symbol, price):

        if self.has_position(symbol):

            self.positions[symbol].current_price = price

    def get_position(self, symbol):

        return self.positions.get(symbol)

    def get_all_positions(self):

        return self.positions

    def count(self):

        return len(self.positions)