"""
=====================================================
OPHELIA EXCEPTION HIERARCHY
=====================================================

Centralized exception definitions for the Ophelia
trading system.

All custom exceptions should inherit from OpheliaError.
"""

from __future__ import annotations


# =====================================================
# BASE EXCEPTIONS
# =====================================================


class OpheliaError(Exception):
    """
    Base exception for the entire application.
    """


# =====================================================
# CONFIGURATION
# =====================================================


class ConfigurationError(OpheliaError):
    """
    Raised when application configuration is invalid.
    """


class ValidationError(OpheliaError):
    """
    Raised when request validation fails.
    """


# =====================================================
# BINGX
# =====================================================


class BingXError(OpheliaError):
    """
    Base BingX exception.
    """


class AuthenticationError(BingXError):
    """
    Authentication with BingX failed.
    """


class BingXNetworkError(BingXError):
    """
    Network communication failed.
    """


class RateLimitError(BingXError):
    """
    BingX rate limit exceeded.
    """


# =====================================================
# API
# =====================================================


class BingXAPIError(BingXError):
    """
    Raised when BingX returns a non-zero response code.
    """

    def __init__(
        self,
        code: int,
        message: str,
    ) -> None:
        self.code = code
        self.message = message

        super().__init__(f"[{code}] {message}")


# =====================================================
# ORDERS
# =====================================================


class OrderError(BingXError):
    """
    Base order exception.
    """


class OrderRejected(OrderError):
    """
    Raised when BingX rejects an order.
    """

    def __init__(
        self,
        code: int,
        message: str,
    ) -> None:
        self.code = code
        self.message = message

        super().__init__(f"Order rejected [{code}] {message}")


class OrderNotFound(OrderError):
    """
    Requested order does not exist.
    """


class InsufficientMargin(OrderError):
    """
    Not enough available margin.
    """


# =====================================================
# POSITIONS
# =====================================================


class PositionError(BingXError):
    """
    Base position exception.
    """


class PositionNotFound(PositionError):
    """
    Requested position does not exist.
    """


class PositionAlreadyClosed(PositionError):
    """
    Position is already closed.
    """


# =====================================================
# MARKET
# =====================================================


class SymbolNotFound(BingXError):
    """
    Trading symbol does not exist.
    """


class InvalidInterval(BingXError):
    """
    Invalid timeframe or interval.
    """


# =====================================================
# SERIALIZATION
# =====================================================


class SerializationError(OpheliaError):
    """
    Failed to serialize or deserialize data.
    """


# =====================================================
# RISK
# =====================================================


class RiskError(OpheliaError):
    """
    Risk management violation.
    """


class MaxPositionExceeded(RiskError):
    """
    Maximum number of open positions exceeded.
    """


class InvalidPositionSize(RiskError):
    """
    Invalid calculated position size.
    """

# =====================================================
# ISOLATION / SHADOW
# =====================================================

class ShadowModeIsolationError(OpheliaError):
    """
    Raised when the system attempts a prohibited action in SHADOW mode.
    """