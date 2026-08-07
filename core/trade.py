from dataclasses import dataclass


@dataclass
class Trade:

    symbol: str

    side: str

    entry_price: float

    exit_price: float

    quantity: float

    leverage: int

    entry_time: int

    exit_time: int

    pnl_percent: float

    pnl_amount: float

    status: str