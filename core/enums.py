from enum import Enum


class Signal(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class PositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    BOTH = "BOTH"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"

    STOP_MARKET = "STOP_MARKET"
    STOP = "STOP"

    TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"
    TAKE_PROFIT = "TAKE_PROFIT"

    TRIGGER_MARKET = "TRIGGER_MARKET"
    TRIGGER_LIMIT = "TRIGGER_LIMIT"

    TRAILING_STOP_MARKET = "TRAILING_STOP_MARKET"
    TRAILING_TP_SL = "TRAILING_TP_SL"


class MarginMode(str, Enum):
    ISOLATED = "ISOLATED"
    CROSSED = "CROSSED"


class WorkingType(str, Enum):
    MARK_PRICE = "MARK_PRICE"
    CONTRACT_PRICE = "CONTRACT_PRICE"
    INDEX_PRICE = "INDEX_PRICE"


class TimeInForce(str, Enum):
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"
    POST_ONLY = "PostOnly"


class TradeState(str, Enum):
    IDLE = "IDLE"

    OPENING_LONG = "OPENING_LONG"
    LONG = "LONG"

    OPENING_SHORT = "OPENING_SHORT"
    SHORT = "SHORT"

    REVERSING_TO_LONG = "REVERSING_TO_LONG"
    REVERSING_TO_SHORT = "REVERSING_TO_SHORT"

    CLOSING = "CLOSING"

    ERROR = "ERROR"


class OrderStatus(str, Enum):
    NEW = "NEW"
    PENDING = "PENDING"

    PARTIALLY_FILLED = "PARTIALLYFILLED"
    FILLED = "FILLED"

    CANCELLED = "CANCELLED"
    FAILED = "FAILED"

    EXPIRED = "EXPIRED"


class TriggerType(str, Enum):
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"


class ExitReason(str, Enum):
    EMA_REVERSAL = "EMA_REVERSAL"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    TRAILING_STOP = "TRAILING_STOP"
    MANUAL = "MANUAL"


class Environment(str, Enum):
    LIVE = "LIVE"
    PAPER = "PAPER"