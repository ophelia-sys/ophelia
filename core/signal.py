from dataclasses import dataclass


@dataclass
class Signal:

    symbol: str

    signal: str

    price: float

    ema8: float

    ema18: float

    ema200: float

    time: int

    reason: str